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

GUIDE_PROTOCOL = "bondik-city-visitor-guide/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-visitor-guide-contract.json"
)


class CityVisitorGuideError(ValueError):
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
        raise CityVisitorGuideError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityVisitorGuideError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="visitor guide contract",
    )

    if not isinstance(payload, dict):
        raise CityVisitorGuideError(
            "visitor guide contract root must be an object"
        )

    if payload.get("protocol") != GUIDE_PROTOCOL:
        raise CityVisitorGuideError(
            "unsupported visitor guide protocol"
        )

    if payload.get("version") != VERSION:
        raise CityVisitorGuideError(
            "unsupported visitor guide version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityVisitorGuideError(
            "visitor guide cityId mismatch"
        )

    if payload.get("directoryProtocol") != (
        DIRECTORY_PROTOCOL
    ):
        raise CityVisitorGuideError(
            "directory protocol mismatch"
        )

    if payload.get("safetyProtocol") != (
        SAFETY_PROTOCOL
    ):
        raise CityVisitorGuideError(
            "safety protocol mismatch"
        )

    if payload.get("operation") != (
        "inspect-evidence"
    ):
        raise CityVisitorGuideError(
            "visitor guide v1 operation invalid"
        )

    if payload.get("authority") != (
        "advisory-only"
    ):
        raise CityVisitorGuideError(
            "visitor guide authority invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
    }:
        raise CityVisitorGuideError(
            "visitor guide exposure contract invalid"
        )

    return payload


def _location_index(
    directory: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    for location in directory["locations"]:
        for capability in location[
            "capabilities"
        ]:
            index[capability["id"]] = {
                "locationId": location["id"],
                "locationName": location["name"],
                "locationRole": location["role"],
                "locationStatus": location[
                    "status"
                ],
                "virtualMapping": location[
                    "virtualMapping"
                ],
            }

    return index


def build_visitor_guide(
    principal: Any,
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

    if not isinstance(principal, dict):
        raise CityVisitorGuideError(
            "principal must be an object"
        )

    if directory is None:
        try:
            directory = build_directory()
        except CityDirectoryError as error:
            raise CityVisitorGuideError(
                str(error)
            ) from error

    if (
        directory.get("protocol")
        != contract["directoryProtocol"]
    ):
        raise CityVisitorGuideError(
            "directory protocol mismatch"
        )

    if policy is None or registry is None:
        try:
            loaded_policy, loaded_registry = (
                load_policy()
            )
        except AgentSafetyError as error:
            raise CityVisitorGuideError(
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

    locations = _location_index(
        directory
    )

    allowed = []
    denied = []

    capabilities = sorted(
        registry["capabilities"],
        key=lambda item: item["id"],
    )

    for capability in capabilities:
        capability_id = capability["id"]

        if (
            capability.get("status")
            != "active"
            or capability.get(
                "agent",
                {},
            ).get("discoverable")
            is not True
        ):
            continue

        try:
            decision = evaluate_access(
                {
                    "principal": principal,
                    "operation": contract[
                        "operation"
                    ],
                    "capabilityId": (
                        capability_id
                    ),
                },
                policy=policy,
                registry=registry,
            )
        except AgentSafetyError as error:
            raise CityVisitorGuideError(
                str(error)
            ) from error

        item = {
            "capabilityId": capability_id,
            "decision": decision.decision,
            "reason": decision.reason,
            "location": locations.get(
                capability_id
            ),
            "grantsPermission": False,
        }

        if decision.decision == "allow":
            allowed.append(item)
        else:
            denied.append(item)

    return {
        "protocol": GUIDE_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "visitor-guide",
        "authority": contract["authority"],
        "principal": {
            "id": principal.get("id"),
            "role": principal.get("role"),
        },
        "operation": contract["operation"],
        "summary": {
            "allowed": len(allowed),
            "denied": len(denied),
        },
        "allowed": allowed,
        "denied": denied,
        "exposure": contract["exposure"],
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Build a permission-aware, "
            "non-executing Bondik City guide."
        )
    ).parse_args()

    try:
        guide = build_visitor_guide(
            {
                "id": "demo-agent",
                "role": "observer",
            }
        )
    except CityVisitorGuideError as error:
        print(
            "Bondik City Visitor Guide ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Visitor Guide OK: "
        f"{guide['summary']['allowed']} allowed / "
        f"{guide['summary']['denied']} denied / "
        f"{GUIDE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
