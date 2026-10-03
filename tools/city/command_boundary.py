from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

COMMAND_PROTOCOL = "bondik-city-command/1"
COMMAND_VERSION = 1
BUILDING_ID = "dispatch-office"
MAX_ARGUMENT_BYTES = 65536
MAX_RESULT_BYTES = 65536

COMMAND_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
NAMESPACED_ID_RE = re.compile(
    r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$"
)
BUILDING_ID_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)


class CityCommandError(ValueError):
    pass


CommandHandler = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


@dataclass(frozen=True)
class CommandRegistration:
    command_type: str
    building_id: str
    capability_id: str
    mutation: str


@dataclass(frozen=True)
class DispatchReport:
    command_id: str
    command_type: str
    target_building_id: str
    result: dict[str, Any]


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise CityCommandError(
            "requestedAt must be a string"
        )

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as error:
        raise CityCommandError(
            "requestedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityCommandError(
            "requestedAt must include timezone"
        )


def _validate_json_object(
    value: Any,
    *,
    label: str,
    byte_limit: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CityCommandError(
            f"{label} must be an object"
        )

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as error:
        raise CityCommandError(
            f"{label} must be JSON serializable"
        ) from error

    if len(encoded) > byte_limit:
        raise CityCommandError(
            f"{label} exceeds size limit"
        )

    return value


def validate_command(
    command: Any,
) -> dict[str, Any]:
    if not isinstance(command, dict):
        raise CityCommandError(
            "command must be an object"
        )

    if command.get("protocol") != COMMAND_PROTOCOL:
        raise CityCommandError(
            "unsupported command protocol"
        )

    if command.get("version") != COMMAND_VERSION:
        raise CityCommandError(
            "unsupported command version"
        )

    if command.get("kind") != "command":
        raise CityCommandError(
            "kind must be command"
        )

    command_id = command.get("commandId")

    if (
        not isinstance(command_id, str)
        or not COMMAND_ID_RE.fullmatch(
            command_id
        )
    ):
        raise CityCommandError(
            "commandId is invalid"
        )

    command_type = command.get(
        "commandType"
    )

    if (
        not isinstance(command_type, str)
        or not NAMESPACED_ID_RE.fullmatch(
            command_type
        )
    ):
        raise CityCommandError(
            "commandType is invalid"
        )

    _validate_timestamp(
        command.get("requestedAt")
    )

    requester = command.get("requester")

    if requester != {
        "kind": "local-ui",
    }:
        raise CityCommandError(
            "requester must be local-ui"
        )

    target = command.get("target")

    if not isinstance(target, dict):
        raise CityCommandError(
            "target must be an object"
        )

    building_id = target.get(
        "buildingId"
    )

    if (
        not isinstance(building_id, str)
        or not BUILDING_ID_RE.fullmatch(
            building_id
        )
    ):
        raise CityCommandError(
            "target buildingId is invalid"
        )

    capability_id = target.get(
        "capabilityId"
    )

    if (
        not isinstance(capability_id, str)
        or not NAMESPACED_ID_RE.fullmatch(
            capability_id
        )
    ):
        raise CityCommandError(
            "target capabilityId is invalid"
        )

    _validate_json_object(
        command.get("arguments"),
        label="arguments",
        byte_limit=MAX_ARGUMENT_BYTES,
    )

    safety = command.get("safety")

    if safety != {
        "authorization": "explicit-registration",
        "agentExecution": "not-exposed",
        "mutation": "read-only",
        "transport": "local-in-process",
    }:
        raise CityCommandError(
            "command safety contract is invalid"
        )

    return command


class LocalCommandDispatcher:
    def __init__(self) -> None:
        self._registrations: dict[
            str,
            tuple[
                CommandRegistration,
                CommandHandler,
            ],
        ] = {}

    def register(
        self,
        *,
        command_type: str,
        building_id: str,
        capability_id: str,
        handler: CommandHandler,
        mutation: str = "read-only",
    ) -> None:
        if not NAMESPACED_ID_RE.fullmatch(
            command_type
        ):
            raise CityCommandError(
                "registration command type "
                "is invalid"
            )

        if not BUILDING_ID_RE.fullmatch(
            building_id
        ):
            raise CityCommandError(
                "registration buildingId "
                "is invalid"
            )

        if not NAMESPACED_ID_RE.fullmatch(
            capability_id
        ):
            raise CityCommandError(
                "registration capabilityId "
                "is invalid"
            )

        if mutation != "read-only":
            raise CityCommandError(
                "v1 only allows read-only "
                "command registrations"
            )

        if not callable(handler):
            raise CityCommandError(
                "handler must be callable"
            )

        if command_type in self._registrations:
            raise CityCommandError(
                "command type already registered"
            )

        registration = CommandRegistration(
            command_type=command_type,
            building_id=building_id,
            capability_id=capability_id,
            mutation=mutation,
        )
        self._registrations[
            command_type
        ] = (
            registration,
            handler,
        )

    def describe_registration(
        self,
        command_type: str,
    ) -> CommandRegistration:
        if not isinstance(command_type, str):
            raise CityCommandError(
                "command type is not registered"
            )

        pair = self._registrations.get(
            command_type
        )

        if pair is None:
            raise CityCommandError(
                "command type is not registered"
            )

        registration, _handler = pair
        return registration

    def dispatch(
        self,
        command: dict[str, Any],
    ) -> DispatchReport:
        validated = validate_command(
            command
        )
        command_type = validated[
            "commandType"
        ]

        pair = self._registrations.get(
            command_type
        )

        if pair is None:
            raise CityCommandError(
                "command type is not registered"
            )

        registration, handler = pair
        target = validated["target"]

        if (
            target["buildingId"]
            != registration.building_id
            or target["capabilityId"]
            != registration.capability_id
        ):
            raise CityCommandError(
                "command target does not match "
                "registration"
            )

        result = handler(
            validated["arguments"]
        )
        result = _validate_json_object(
            result,
            label="result",
            byte_limit=MAX_RESULT_BYTES,
        )

        return DispatchReport(
            command_id=validated["commandId"],
            command_type=command_type,
            target_building_id=(
                registration.building_id
            ),
            result=result,
        )


def _demo_command() -> dict[str, Any]:
    return {
        "protocol": COMMAND_PROTOCOL,
        "version": COMMAND_VERSION,
        "kind": "command",
        "commandId": "city-command-self-test-1",
        "commandType": "city.status.read",
        "requestedAt": (
            "2026-01-01T00:00:00Z"
        ),
        "requester": {
            "kind": "local-ui",
        },
        "target": {
            "buildingId": "control-tower",
            "capabilityId": (
                "city.control-tower."
                "status-board"
            ),
        },
        "arguments": {},
        "safety": {
            "authorization": (
                "explicit-registration"
            ),
            "agentExecution": (
                "not-exposed"
            ),
            "mutation": "read-only",
            "transport": (
                "local-in-process"
            ),
        },
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the Bondik City local "
            "Command Boundary self-test."
        )
    )
    return parser.parse_args()


def main() -> int:
    parse_arguments()

    dispatcher = LocalCommandDispatcher()
    dispatcher.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda _arguments: {
            "status": "available",
        },
    )
    report = dispatcher.dispatch(
        _demo_command()
    )

    if report.result != {
        "status": "available"
    }:
        print(
            "❌ Bondik City Command Boundary "
            "self-test failed"
        )
        return 1

    print(
        "Bondik City Command Boundary OK: "
        f"{report.command_type} -> "
        f"{report.target_building_id} / "
        f"{COMMAND_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
