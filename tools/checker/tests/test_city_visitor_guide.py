import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.agent_safety import (
    load_policy,
)
from tools.city.service_directory import (
    build_directory,
)
from tools.city.visitor_guide import (
    GUIDE_PROTOCOL,
    CityVisitorGuideError,
    build_visitor_guide,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[3]


def observer():
    return {
        "id": "demo-agent",
        "role": "observer",
    }


def test_observer_guide_current_counts():
    guide = build_visitor_guide(
        observer()
    )

    assert guide["summary"] == {
        "allowed": 6,
        "denied": 21,
    }


def test_allowed_capabilities_match_policy():
    guide = build_visitor_guide(
        observer()
    )
    policy, _registry = load_policy()

    allowed_ids = {
        item["capabilityId"]
        for item in guide["allowed"]
    }
    policy_ids = set(
        policy["roles"]["observer"][
            "allow"
        ]["capabilities"]
    )

    assert allowed_ids == policy_ids


def test_allowed_items_include_location():
    guide = build_visitor_guide(
        observer()
    )

    github = next(
        item
        for item in guide["allowed"]
        if item["capabilityId"]
        == "city.github.repository-snapshot"
    )

    assert github["location"][
        "locationId"
    ] == "github-service"


def test_denied_command_surface_is_visible_but_not_granted():
    guide = build_visitor_guide(
        observer()
    )

    dispatch = next(
        item
        for item in guide["denied"]
        if item["capabilityId"]
        == "city.command-boundary.local"
    )

    assert dispatch["reason"] == (
        "capability-not-allowed"
    )
    assert dispatch["location"][
        "locationId"
    ] == "dispatch-office"
    assert dispatch["grantsPermission"] is False


def test_guide_never_grants_permission():
    guide = build_visitor_guide(
        observer()
    )

    assert all(
        item["grantsPermission"] is False
        for item in (
            guide["allowed"]
            + guide["denied"]
        )
    )


def test_unknown_role_denies_everything():
    guide = build_visitor_guide(
        {
            "id": "demo-agent",
            "role": "visitor",
        }
    )

    assert guide["summary"] == {
        "allowed": 0,
        "denied": 27,
    }
    assert {
        item["reason"]
        for item in guide["denied"]
    } == {"unknown-role"}


def test_directory_protocol_mismatch_fails_closed():
    directory = build_directory()
    broken = copy.deepcopy(directory)
    broken["protocol"] = "wrong/1"

    with pytest.raises(
        CityVisitorGuideError,
        match="directory protocol mismatch",
    ):
        build_visitor_guide(
            observer(),
            directory=broken,
        )


def test_invalid_principal_is_rejected():
    with pytest.raises(
        CityVisitorGuideError,
        match="principal must be an object",
    ):
        build_visitor_guide(
            "demo-agent"
        )


def test_contract_is_advisory_only():
    contract = load_contract()

    assert contract["authority"] == (
        "advisory-only"
    )
    assert contract["operation"] == (
        "inspect-evidence"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
    }


def test_direct_cli_builds_guide():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "visitor_guide.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Visitor Guide OK: "
        "6 allowed / 21 denied / "
        "bondik-city-visitor-guide/1"
        in result.stdout
    )
