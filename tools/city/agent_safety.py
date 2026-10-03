from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.validate_capability_registry import (
    load_capability_registry,
)

SAFETY_PROTOCOL = "bondik-city-agent-safety/1"
SAFETY_VERSION = 1

DEFAULT_POLICY_PATH = (
    ROOT / "config" / "city-agent-policy.json"
)

PRINCIPAL_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
ROLE_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)
OPERATION_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)


class AgentSafetyError(ValueError):
    pass


@dataclass(frozen=True)
class AccessDecision:
    decision: str
    reason: str
    principal_id: str
    role: str
    operation: str
    capability_id: str | None


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
        raise AgentSafetyError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise AgentSafetyError(
            f"{label} must be valid JSON"
        ) from error


def validate_policy(
    policy: Any,
    registry: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise AgentSafetyError(
            "policy root must be an object"
        )

    if policy.get("protocol") != SAFETY_PROTOCOL:
        raise AgentSafetyError(
            "unsupported safety protocol"
        )

    if policy.get("version") != SAFETY_VERSION:
        raise AgentSafetyError(
            "unsupported safety version"
        )

    if policy.get("cityId") != registry.get(
        "cityId"
    ):
        raise AgentSafetyError(
            "policy cityId must match registry"
        )

    if policy.get("mode") != "default-deny":
        raise AgentSafetyError(
            "policy mode must be default-deny"
        )

    if policy.get("defaultDecision") != "deny":
        raise AgentSafetyError(
            "default decision must be deny"
        )

    denied = policy.get("deniedOperations")

    if not isinstance(denied, list):
        raise AgentSafetyError(
            "deniedOperations must be a list"
        )

    required_denied = {
        "execute",
        "command",
        "mutate",
        "handoff",
        "publish-event",
    }

    if not required_denied.issubset(
        set(denied)
    ):
        raise AgentSafetyError(
            "required denied operations missing"
        )

    exposure = policy.get("exposure")

    if exposure != {
        "sensitiveState": "not-exposed",
        "commandAuthority": "none",
        "mutationAuthority": "none",
        "networkAuthority": "none",
    }:
        raise AgentSafetyError(
            "policy exposure contract invalid"
        )

    capabilities = {
        item["id"]: item
        for item in registry["capabilities"]
    }

    roles = policy.get("roles")

    if not isinstance(roles, dict):
        raise AgentSafetyError(
            "roles must be an object"
        )

    if not roles:
        raise AgentSafetyError(
            "at least one role is required"
        )

    for role, role_policy in roles.items():
        if not ROLE_RE.fullmatch(role):
            raise AgentSafetyError(
                "role name is invalid"
            )

        if not isinstance(role_policy, dict):
            raise AgentSafetyError(
                "role policy must be an object"
            )

        allow = role_policy.get("allow")

        if not isinstance(allow, dict):
            raise AgentSafetyError(
                "role allow must be an object"
            )

        operations = allow.get("operations")
        allowed_caps = allow.get(
            "capabilities"
        )

        if not isinstance(
            operations,
            list,
        ) or not isinstance(
            allowed_caps,
            list,
        ):
            raise AgentSafetyError(
                "role allow lists invalid"
            )

        for operation in operations:
            if (
                not isinstance(
                    operation,
                    str,
                )
                or not OPERATION_RE.fullmatch(
                    operation
                )
            ):
                raise AgentSafetyError(
                    "allowed operation invalid"
                )

            if operation in required_denied:
                raise AgentSafetyError(
                    "denied operation cannot be "
                    "allowed"
                )

        for capability_id in allowed_caps:
            capability = capabilities.get(
                capability_id
            )

            if capability is None:
                raise AgentSafetyError(
                    "policy references unknown "
                    "capability"
                )

            agent = capability.get("agent", {})

            if (
                capability.get("status")
                != "active"
                or agent.get("discoverable")
                is not True
                or agent.get("execution")
                != "not-exposed"
            ):
                raise AgentSafetyError(
                    "policy capability must be "
                    "active discoverable and "
                    "non-executable"
                )

    return policy


def load_policy(
    path: Path = DEFAULT_POLICY_PATH,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    registry = load_capability_registry()
    policy = _load_json(
        path,
        label="agent safety policy",
    )
    return (
        validate_policy(
            policy,
            registry,
        ),
        registry,
    )


def evaluate_access(
    request: Any,
    *,
    policy: dict[str, Any],
    registry: dict[str, Any],
) -> AccessDecision:
    if not isinstance(request, dict):
        raise AgentSafetyError(
            "request must be an object"
        )

    principal = request.get("principal")

    if not isinstance(principal, dict):
        raise AgentSafetyError(
            "principal must be an object"
        )

    principal_id = principal.get("id")
    role = principal.get("role")

    if (
        not isinstance(
            principal_id,
            str,
        )
        or not PRINCIPAL_ID_RE.fullmatch(
            principal_id
        )
    ):
        raise AgentSafetyError(
            "principal id is invalid"
        )

    if (
        not isinstance(role, str)
        or not ROLE_RE.fullmatch(role)
    ):
        raise AgentSafetyError(
            "principal role is invalid"
        )

    operation = request.get(
        "operation"
    )

    if (
        not isinstance(operation, str)
        or not OPERATION_RE.fullmatch(
            operation
        )
    ):
        raise AgentSafetyError(
            "operation is invalid"
        )

    capability_id = request.get(
        "capabilityId"
    )

    if (
        capability_id is not None
        and not isinstance(
            capability_id,
            str,
        )
    ):
        raise AgentSafetyError(
            "capabilityId must be a string"
        )

    if operation in set(
        policy["deniedOperations"]
    ):
        return AccessDecision(
            decision="deny",
            reason="operation-denied-by-policy",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    role_policy = policy["roles"].get(
        role
    )

    if role_policy is None:
        return AccessDecision(
            decision="deny",
            reason="unknown-role",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    allow = role_policy["allow"]

    if operation not in allow[
        "operations"
    ]:
        return AccessDecision(
            decision="deny",
            reason="operation-not-allowed",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    if operation == "discover":
        return AccessDecision(
            decision="allow",
            reason="role-allows-discovery",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=None,
        )

    if not capability_id:
        return AccessDecision(
            decision="deny",
            reason="capability-required",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=None,
        )

    capabilities = {
        item["id"]: item
        for item in registry[
            "capabilities"
        ]
    }
    capability = capabilities.get(
        capability_id
    )

    if capability is None:
        return AccessDecision(
            decision="deny",
            reason="unknown-capability",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    if capability_id not in allow[
        "capabilities"
    ]:
        return AccessDecision(
            decision="deny",
            reason="capability-not-allowed",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    agent = capability.get("agent", {})

    if (
        capability.get("status") != "active"
        or agent.get("discoverable")
        is not True
        or agent.get("execution")
        != "not-exposed"
    ):
        return AccessDecision(
            decision="deny",
            reason="capability-not-safe",
            principal_id=principal_id,
            role=role,
            operation=operation,
            capability_id=capability_id,
        )

    return AccessDecision(
        decision="allow",
        reason="explicit-role-capability-allow",
        principal_id=principal_id,
        role=role,
        operation=operation,
        capability_id=capability_id,
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the Bondik City Agent "
            "Safety Envelope self-test."
        )
    )
    return parser.parse_args()


def main() -> int:
    parse_arguments()
    policy, registry = load_policy()

    allowed = evaluate_access(
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
        },
        policy=policy,
        registry=registry,
    )

    denied = evaluate_access(
        {
            "principal": {
                "id": "demo-agent",
                "role": "observer",
            },
            "operation": "command",
            "capabilityId": (
                "city.command-boundary.local"
            ),
        },
        policy=policy,
        registry=registry,
    )

    if (
        allowed.decision != "allow"
        or denied.decision != "deny"
    ):
        print(
            "❌ Bondik City Agent Safety "
            "self-test failed"
        )
        return 1

    print(
        "Bondik City Agent Safety OK: "
        "inspect-evidence=allow / "
        "command=deny / "
        f"{SAFETY_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
