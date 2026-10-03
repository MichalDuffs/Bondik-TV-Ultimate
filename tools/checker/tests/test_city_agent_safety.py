import copy
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.agent_safety import (
    SAFETY_PROTOCOL,
    AgentSafetyError,
    evaluate_access,
    load_policy,
    validate_policy,
)
from tools.city.validate_capability_registry import (
    load_capability_registry,
)


ROOT = Path(__file__).resolve().parents[3]


def loaded():
    return load_policy()


def request(
    operation="inspect-evidence",
    capability_id=(
        "city.github.repository-snapshot"
    ),
    role="observer",
):
    return {
        "principal": {
            "id": "demo-agent",
            "role": role,
        },
        "operation": operation,
        "capabilityId": capability_id,
    }


def test_policy_is_default_deny():
    policy, _registry = loaded()

    assert policy["protocol"] == (
        SAFETY_PROTOCOL
    )
    assert policy["mode"] == (
        "default-deny"
    )
    assert policy["defaultDecision"] == (
        "deny"
    )


def test_observer_can_inspect_allowed_evidence():
    policy, registry = loaded()

    decision = evaluate_access(
        request(),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "allow"
    assert decision.reason == (
        "explicit-role-capability-allow"
    )


def test_discovery_is_allowed_without_capability():
    policy, registry = loaded()

    decision = evaluate_access(
        request(
            operation="discover",
            capability_id=None,
        ),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "allow"
    assert decision.capability_id is None


@pytest.mark.parametrize(
    "operation",
    [
        "execute",
        "command",
        "mutate",
        "handoff",
        "publish-event",
    ],
)
def test_dangerous_operations_are_denied(
    operation,
):
    policy, registry = loaded()

    decision = evaluate_access(
        request(
            operation=operation,
            capability_id=(
                "city.command-boundary.local"
            ),
        ),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "deny"
    assert decision.reason == (
        "operation-denied-by-policy"
    )


def test_unknown_role_is_denied():
    policy, registry = loaded()

    decision = evaluate_access(
        request(role="unknown-role"),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "deny"
    assert decision.reason == "unknown-role"


def test_unlisted_capability_is_denied():
    policy, registry = loaded()

    decision = evaluate_access(
        request(
            capability_id="bondik-tv.playback"
        ),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "deny"
    assert decision.reason == (
        "capability-not-allowed"
    )


def test_unknown_capability_is_denied():
    policy, registry = loaded()

    decision = evaluate_access(
        request(
            capability_id=(
                "city.unknown.capability"
            )
        ),
        policy=policy,
        registry=registry,
    )

    assert decision.decision == "deny"
    assert decision.reason == (
        "unknown-capability"
    )


def test_policy_cannot_allow_denied_operation():
    policy, registry = loaded()
    broken = copy.deepcopy(policy)
    broken["roles"]["observer"][
        "allow"
    ]["operations"].append("command")

    with pytest.raises(
        AgentSafetyError,
        match="denied operation",
    ):
        validate_policy(
            broken,
            registry,
        )


def test_policy_cannot_reference_unknown_capability():
    policy, registry = loaded()
    broken = copy.deepcopy(policy)
    broken["roles"]["observer"][
        "allow"
    ]["capabilities"].append(
        "city.unknown.capability"
    )

    with pytest.raises(
        AgentSafetyError,
        match="unknown capability",
    ):
        validate_policy(
            broken,
            registry,
        )


def test_exposure_contract_is_fixed():
    policy, registry = loaded()
    broken = copy.deepcopy(policy)
    broken["exposure"][
        "commandAuthority"
    ] = "some"

    with pytest.raises(
        AgentSafetyError,
        match="exposure contract",
    ):
        validate_policy(
            broken,
            registry,
        )


def test_registry_is_current():
    _policy, registry = loaded()

    assert registry == (
        load_capability_registry()
    )


def test_direct_cli_runs_self_test():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "agent_safety.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Agent Safety OK: "
        "inspect-evidence=allow / "
        "command=deny / "
        "bondik-city-agent-safety/1"
        in result.stdout
    )
