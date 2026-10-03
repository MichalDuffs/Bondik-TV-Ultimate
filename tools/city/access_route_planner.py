from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.agent_safety import (
    SAFETY_PROTOCOL,
    AgentSafetyError,
    evaluate_access,
    load_policy,
)
from tools.city.service_directory import (
    DIRECTORY_PROTOCOL,
    CityDirectoryError,
    build_directory,
)

ROUTE_PROTOCOL = "bondik-city-access-route/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-access-route-contract.json"
)


class CityRouteError(ValueError):
    pass


def _load_json(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except OSError as error:
        raise CityRouteError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityRouteError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="access route contract",
    )

    if not isinstance(payload, dict):
        raise CityRouteError(
            "access route contract root must be an object"
        )

    if payload.get("protocol") != ROUTE_PROTOCOL:
        raise CityRouteError(
            "unsupported access route protocol"
        )

    if payload.get("version") != VERSION:
        raise CityRouteError(
            "unsupported access route version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityRouteError(
            "access route cityId mismatch"
        )

    if payload.get("directoryProtocol") != (
        DIRECTORY_PROTOCOL
    ):
        raise CityRouteError(
            "directory protocol mismatch"
        )

    if payload.get("safetyProtocol") != (
        SAFETY_PROTOCOL
    ):
        raise CityRouteError(
            "safety protocol mismatch"
        )

    if payload.get("authority") != "plan-only":
        raise CityRouteError(
            "access route authority must be plan-only"
        )

    if payload.get("outputKind") != (
        "access-route-plan"
    ):
        raise CityRouteError(
            "access route output kind invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
    }:
        raise CityRouteError(
            "access route exposure contract invalid"
        )

    return payload


def _capability_location(
    directory: dict[str, Any],
    capability_id: str,
) -> dict[str, Any] | None:
    for location in directory[
        "locations"
    ]:
        for capability in location[
            "capabilities"
        ]:
            if capability["id"] == (
                capability_id
            ):
                return {
                    "locationId": location[
                        "id"
                    ],
                    "locationName": location[
                        "name"
                    ],
                    "locationStatus": location[
                        "status"
                    ],
                    "locationRole": location[
                        "role"
                    ],
                    "virtualMapping": location[
                        "virtualMapping"
                    ],
                    "capabilityStatus": (
                        capability["status"]
                    ),
                    "surfaces": capability[
                        "surfaces"
                    ],
                }

    return None


def plan_access_route(
    request: Any,
    *,
    contract: dict[str, Any] | None = None,
    directory: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(request, dict):
        raise CityRouteError(
            "request must be an object"
        )

    capability_id = request.get(
        "capabilityId"
    )

    if (
        not isinstance(
            capability_id,
            str,
        )
        or not capability_id
    ):
        raise CityRouteError(
            "capabilityId must be a non-empty string"
        )

    if directory is None:
        try:
            directory = build_directory()
        except CityDirectoryError as error:
            raise CityRouteError(
                str(error)
            ) from error

    if (
        directory.get("protocol")
        != contract["directoryProtocol"]
    ):
        raise CityRouteError(
            "directory protocol mismatch"
        )

    if (
        policy is None
        or registry is None
    ):
        try:
            loaded_policy, loaded_registry = (
                load_policy()
            )
        except AgentSafetyError as error:
            raise CityRouteError(
                str(error)
            ) from error

        policy = (
            policy
            if policy is not None
            else loaded_policy
        )
        registry = (
            registry
            if registry is not None
            else loaded_registry
        )

    try:
        decision = evaluate_access(
            request,
            policy=policy,
            registry=registry,
        )
    except AgentSafetyError as error:
        raise CityRouteError(
            str(error)
        ) from error

    location = _capability_location(
        directory,
        capability_id,
    )

    return {
        "protocol": ROUTE_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": contract["outputKind"],
        "authority": contract[
            "authority"
        ],
        "request": {
            "principal": {
                "id": decision.principal_id,
                "role": decision.role,
            },
            "operation": (
                decision.operation
            ),
            "capabilityId": (
                decision.capability_id
            ),
        },
        "access": {
            "decision": decision.decision,
            "reason": decision.reason,
            "grantsPermission": False,
        },
        "route": (
            {
                "status": "resolved",
                **location,
            }
            if location is not None
            else {
                "status": "unresolved",
                "locationId": None,
            }
        ),
        "exposure": contract["exposure"],
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Plan a non-executing Bondik City "
            "capability access route."
        )
    )
    return parser.parse_args()


def main() -> int:
    parse_arguments()

    try:
        plan = plan_access_route(
            {
                "principal": {
                    "id": "demo-agent",
                    "role": "observer",
                },
                "operation": (
                    "inspect-evidence"
                ),
                "capabilityId": (
                    "city.github.repository-snapshot"
                ),
            }
        )
    except CityRouteError as error:
        print(
            "Bondik City Access Route ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Access Route OK: "
        f"{plan['access']['decision']} -> "
        f"{plan['route']['locationId']} / "
        f"{ROUTE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
