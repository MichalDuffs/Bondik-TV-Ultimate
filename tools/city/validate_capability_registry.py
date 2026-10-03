from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REGISTRY_PROTOCOL = "bondik-city-capability-registry/1"
REGISTRY_VERSION = 1

ALLOWED_STATUSES = {
    "active",
    "planned",
    "disabled",
}
ALLOWED_SURFACES = {
    "web",
    "android",
    "shared",
}
ALLOWED_AGENT_EXECUTION = {
    "not-exposed",
}

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "city-capabilities.json"
)


class CapabilityRegistryError(ValueError):
    pass


def _require_non_empty_string(
    value: Any,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise CapabilityRegistryError(
            f"{field} must be a non-empty string"
        )

    return value


def validate_capability_registry(
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CapabilityRegistryError(
            "registry root must be an object"
        )

    if payload.get("protocol") != REGISTRY_PROTOCOL:
        raise CapabilityRegistryError(
            "unsupported registry protocol"
        )

    if payload.get("version") != REGISTRY_VERSION:
        raise CapabilityRegistryError(
            "unsupported registry version"
        )

    _require_non_empty_string(
        payload.get("cityId"),
        "cityId",
    )

    capabilities = payload.get("capabilities")

    if not isinstance(capabilities, list):
        raise CapabilityRegistryError(
            "capabilities must be a list"
        )

    seen_ids: set[str] = set()

    for index, capability in enumerate(
        capabilities
    ):
        prefix = f"capabilities[{index}]"

        if not isinstance(capability, dict):
            raise CapabilityRegistryError(
                f"{prefix} must be an object"
            )

        capability_id = (
            _require_non_empty_string(
                capability.get("id"),
                f"{prefix}.id",
            )
        )

        if capability_id in seen_ids:
            raise CapabilityRegistryError(
                f"duplicate capability id: "
                f"{capability_id}"
            )

        seen_ids.add(capability_id)

        _require_non_empty_string(
            capability.get("buildingId"),
            f"{prefix}.buildingId",
        )

        status = capability.get("status")

        if status not in ALLOWED_STATUSES:
            raise CapabilityRegistryError(
                f"{prefix}.status must be one of "
                f"{sorted(ALLOWED_STATUSES)}"
            )

        surfaces = capability.get("surfaces")

        if not isinstance(surfaces, list):
            raise CapabilityRegistryError(
                f"{prefix}.surfaces must be a list"
            )

        if len(surfaces) != len(set(surfaces)):
            raise CapabilityRegistryError(
                f"{prefix}.surfaces must be unique"
            )

        unknown_surfaces = (
            set(surfaces) - ALLOWED_SURFACES
        )

        if unknown_surfaces:
            raise CapabilityRegistryError(
                f"{prefix}.surfaces contains "
                f"unsupported values: "
                f"{sorted(unknown_surfaces)}"
            )

        human = capability.get("human")

        if not isinstance(human, dict):
            raise CapabilityRegistryError(
                f"{prefix}.human must be an object"
            )

        _require_non_empty_string(
            human.get("name"),
            f"{prefix}.human.name",
        )
        _require_non_empty_string(
            human.get("description"),
            f"{prefix}.human.description",
        )

        agent = capability.get("agent")

        if not isinstance(agent, dict):
            raise CapabilityRegistryError(
                f"{prefix}.agent must be an object"
            )

        if not isinstance(
            agent.get("discoverable"),
            bool,
        ):
            raise CapabilityRegistryError(
                f"{prefix}.agent.discoverable "
                "must be boolean"
            )

        execution = agent.get("execution")

        if execution not in (
            ALLOWED_AGENT_EXECUTION
        ):
            raise CapabilityRegistryError(
                f"{prefix}.agent.execution "
                "must remain not-exposed in v1"
            )

        if (
            status == "active"
            and not surfaces
        ):
            raise CapabilityRegistryError(
                f"{prefix} active capability "
                "must expose at least one surface"
            )

    return payload


def load_capability_registry(
    path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise CapabilityRegistryError(
            f"cannot read registry: {error}"
        ) from error

    return validate_capability_registry(
        payload
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Bondik City "
            "capability registry."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
    )
    args = parser.parse_args()

    payload = load_capability_registry(
        args.path
    )

    print(
        "Bondik City capability registry "
        f"OK: {len(payload['capabilities'])} "
        "capabilities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
