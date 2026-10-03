import copy
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.command_boundary import (
    COMMAND_PROTOCOL,
    CityCommandError,
    LocalCommandDispatcher,
    validate_command,
)


ROOT = Path(__file__).resolve().parents[3]


def command():
    return {
        "protocol": COMMAND_PROTOCOL,
        "version": 1,
        "kind": "command",
        "commandId": "cmd-001",
        "commandType": "city.status.read",
        "requestedAt": (
            "2026-10-03T19:30:00+02:00"
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
        "arguments": {
            "format": "summary",
        },
        "safety": {
            "authorization": (
                "explicit-registration"
            ),
            "agentExecution": (
                "not-exposed"
            ),
            "mutation": "read-only",
            "transport": "local-in-process",
        },
    }


def dispatcher():
    value = LocalCommandDispatcher()
    value.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda arguments: {
            "format": arguments["format"],
            "status": "available",
        },
    )
    return value


def test_registered_read_only_command_dispatches():
    report = dispatcher().dispatch(
        command()
    )

    assert report.command_id == "cmd-001"
    assert report.command_type == (
        "city.status.read"
    )
    assert report.target_building_id == (
        "control-tower"
    )
    assert report.result == {
        "format": "summary",
        "status": "available",
    }


def test_unregistered_command_is_denied():
    payload = command()
    payload["commandType"] = (
        "city.github.read"
    )

    with pytest.raises(
        CityCommandError,
        match="not registered",
    ):
        dispatcher().dispatch(payload)


def test_target_mismatch_is_denied():
    payload = command()
    payload["target"]["buildingId"] = (
        "github-service"
    )

    with pytest.raises(
        CityCommandError,
        match="target does not match",
    ):
        dispatcher().dispatch(payload)


def test_mutating_registration_is_denied():
    value = LocalCommandDispatcher()

    with pytest.raises(
        CityCommandError,
        match="read-only",
    ):
        value.register(
            command_type="city.issue.close",
            building_id="github-service",
            capability_id=(
                "city.github.repository-snapshot"
            ),
            handler=lambda _arguments: {},
            mutation="write",
        )


def test_duplicate_registration_is_denied():
    value = dispatcher()

    with pytest.raises(
        CityCommandError,
        match="already registered",
    ):
        value.register(
            command_type="city.status.read",
            building_id="control-tower",
            capability_id=(
                "city.control-tower.status-board"
            ),
            handler=lambda _arguments: {},
        )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("protocol",),
            "other/1",
            "unsupported command protocol",
        ),
        (
            ("commandType",),
            "bad type",
            "commandType is invalid",
        ),
        (
            ("requestedAt",),
            "2026-10-03T19:30:00",
            "include timezone",
        ),
        (
            ("requester", "kind"),
            "agent",
            "requester must be local-ui",
        ),
        (
            ("arguments",),
            [],
            "arguments must be an object",
        ),
        (
            ("safety", "agentExecution"),
            "exposed",
            "safety contract",
        ),
    ],
)
def test_invalid_command_is_rejected(
    path,
    value,
    message,
):
    payload = copy.deepcopy(command())
    target = payload

    for key in path[:-1]:
        target = target[key]

    target[path[-1]] = value

    with pytest.raises(
        CityCommandError,
        match=message,
    ):
        validate_command(payload)


def test_handler_failure_is_not_hidden():
    value = LocalCommandDispatcher()

    def broken(_arguments):
        raise RuntimeError("boom")

    value.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=broken,
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        value.dispatch(command())


def test_non_object_result_is_rejected():
    value = LocalCommandDispatcher()
    value.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda _arguments: [],
    )

    with pytest.raises(
        CityCommandError,
        match="result must be an object",
    ):
        value.dispatch(command())


def test_direct_cli_runs_self_test():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "command_boundary.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Command Boundary OK: "
        "city.status.read -> control-tower / "
        "bondik-city-command/1"
        in result.stdout
    )
