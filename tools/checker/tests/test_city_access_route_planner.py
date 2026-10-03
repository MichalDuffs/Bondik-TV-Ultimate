import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.agent_safety import (
    load_policy,
)
from tools.city.access_route_planner import (
    ROUTE_PROTOCOL,
    CityRouteError,
    load_contract,
    plan_access_route,
)


ROOT = Path(__file__).resolve().parents[3]


def allowed_request():
    return {
        "principal": {
            "id": "demo-agent",
            "role": "observer",
        },
        "operation": "inspect-evidence",
        "capabilityId": (
            "city.github.repository-snapshot"
        ),
    }


def test_allowed_route_resolves_to_github_service():
    plan = plan_access_route(
        allowed_request()
    )

    assert plan["protocol"] == (
        ROUTE_PROTOCOL
    )
    assert plan["access"] == {
        "decision": "allow",
        "reason": (
            "explicit-role-capability-allow"
        ),
        "grantsPermission": False,
    }
    assert plan["route"][
        "status"
    ] == "resolved"
    assert plan["route"][
        "locationId"
    ] == "github-service"


def test_denied_command_still_resolves_location():
    request = {
        "principal": {
            "id": "demo-agent",
            "role": "observer",
        },
        "operation": "command",
        "capabilityId": (
            "city.command-boundary.local"
        ),
    }

    plan = plan_access_route(request)

    assert plan["access"][
        "decision"
    ] == "deny"
    assert plan["access"][
        "reason"
    ] == "operation-denied-by-policy"
    assert plan["route"][
        "locationId"
    ] == "dispatch-office"
    assert plan["access"][
        "grantsPermission"
    ] is False


def test_unapproved_capability_is_denied_but_located():
    request = {
        "principal": {
            "id": "demo-agent",
            "role": "observer",
        },
        "operation": "inspect-evidence",
        "capabilityId": (
            "city.device-share.prepare"
        ),
    }

    plan = plan_access_route(request)

    assert plan["access"][
        "decision"
    ] == "deny"
    assert plan["access"][
        "reason"
    ] == "capability-not-allowed"
    assert plan["route"][
        "locationId"
    ] == "device-dock"


def test_unknown_capability_is_denied_and_unresolved():
    request = {
        "principal": {
            "id": "demo-agent",
            "role": "observer",
        },
        "operation": "inspect-evidence",
        "capabilityId": (
            "city.missing.capability"
        ),
    }

    plan = plan_access_route(request)

    assert plan["access"][
        "decision"
    ] == "deny"
    assert plan["access"][
        "reason"
    ] == "unknown-capability"
    assert plan["route"] == {
        "status": "unresolved",
        "locationId": None,
    }


def test_unknown_role_is_denied():
    request = {
        "principal": {
            "id": "demo-agent",
            "role": "visitor",
        },
        "operation": "inspect-evidence",
        "capabilityId": (
            "city.github.repository-snapshot"
        ),
    }

    plan = plan_access_route(request)

    assert plan["access"][
        "decision"
    ] == "deny"
    assert plan["access"][
        "reason"
    ] == "unknown-role"


def test_planner_never_grants_permission():
    for request in [
        allowed_request(),
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
    ]:
        plan = plan_access_route(
            request
        )
        assert plan["access"][
            "grantsPermission"
        ] is False
        assert plan["authority"] == (
            "plan-only"
        )


def test_missing_capability_id_is_rejected():
    request = allowed_request()
    del request["capabilityId"]

    with pytest.raises(
        CityRouteError,
        match="capabilityId",
    ):
        plan_access_route(request)


def test_directory_protocol_mismatch_fails_closed():
    from tools.city.service_directory import (
        build_directory,
    )

    directory = build_directory()
    broken = copy.deepcopy(directory)
    broken["protocol"] = "wrong/1"

    with pytest.raises(
        CityRouteError,
        match="directory protocol mismatch",
    ):
        plan_access_route(
            allowed_request(),
            directory=broken,
        )


def test_contract_is_plan_only():
    contract = load_contract()

    assert contract["authority"] == (
        "plan-only"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
    }


def test_contract_file_matches_protocols():
    payload = json.loads(
        (
            ROOT
            / "config"
            / "city-access-route-contract.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload[
        "directoryProtocol"
    ] == "bondik-city-service-directory/1"
    assert payload[
        "safetyProtocol"
    ] == "bondik-city-agent-safety/1"


def test_policy_remains_source_of_access_truth():
    policy, registry = load_policy()
    plan = plan_access_route(
        allowed_request(),
        policy=policy,
        registry=registry,
    )

    assert plan["access"][
        "decision"
    ] == "allow"


def test_direct_cli_plans_without_execution():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "access_route_planner.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Access Route OK: "
        "allow -> github-service / "
        "bondik-city-access-route/1"
        in result.stdout
    )
