import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.command_boundary import (
    LocalCommandDispatcher,
)
from tools.city.dispatch_preflight import (
    PREFLIGHT_PROTOCOL,
    CityDispatchPreflightError,
    _build_demo_packet,
    load_contract,
    validate_dispatch_preflight,
)
from tools.city.service_directory import (
    build_directory,
)


ROOT = Path(__file__).resolve().parents[3]


def source():
    return _build_demo_packet()


def preflight(
    packet=None,
    dispatcher=None,
    **kwargs,
):
    default_packet, default_dispatcher = (
        source()
    )
    return validate_dispatch_preflight(
        packet
        if packet is not None
        else default_packet,
        dispatcher=(
            dispatcher
            if dispatcher is not None
            else default_dispatcher
        ),
        **kwargs,
    )


def test_preflight_is_validated_not_dispatched():
    value = preflight()

    assert value["protocol"] == (
        PREFLIGHT_PROTOCOL
    )
    assert value["state"] == (
        "validated-not-dispatched"
    )
    assert value["preflightPassed"] is True


def test_preflight_does_not_dispatch_or_execute():
    value = preflight()

    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False
    assert value["consumerConnected"] is False
    assert value["grantConsumed"] is False


def test_preflight_requires_future_single_use_consumption():
    value = preflight()

    assert value["singleUseRequired"] is True
    assert value[
        "grantConsumptionRequired"
    ] is True
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_registration_is_rechecked_at_final_boundary():
    value = preflight()

    assert value["registration"] == {
        "commandType": "city.status.read",
        "buildingId": "control-tower",
        "capabilityId": (
            "city.control-tower.status-board"
        ),
        "mutation": "read-only",
    }


def test_packet_digest_is_bound():
    packet, dispatcher = source()
    value = validate_dispatch_preflight(
        packet,
        dispatcher=dispatcher,
    )

    assert value["packet"][
        "packetId"
    ] == packet["packetId"]
    assert value["packet"][
        "packetDigest"
    ].startswith("sha256:")


def test_preflight_id_is_deterministic():
    packet, dispatcher = source()

    first = validate_dispatch_preflight(
        packet,
        dispatcher=dispatcher,
    )
    second = validate_dispatch_preflight(
        packet,
        dispatcher=dispatcher,
    )

    assert first["preflightId"] == (
        second["preflightId"]
    )


def test_wrong_packet_state_is_rejected():
    packet, dispatcher = source()
    packet["state"] = "dispatched"

    with pytest.raises(
        CityDispatchPreflightError,
        match="ready-not-dispatched",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_tampered_packet_id_is_rejected():
    packet, dispatcher = source()
    packet["packetId"] = "packet-tampered"

    with pytest.raises(
        CityDispatchPreflightError,
        match="packetId integrity mismatch",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_tampered_arguments_digest_is_rejected():
    packet, dispatcher = source()
    packet["command"][
        "argumentsDigest"
    ] = "sha256:" + "0" * 64

    with pytest.raises(
        CityDispatchPreflightError,
        match="arguments digest mismatch",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_unregistered_command_is_rejected():
    packet, _dispatcher = source()
    dispatcher = LocalCommandDispatcher()

    with pytest.raises(
        CityDispatchPreflightError,
        match="not registered",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_registration_target_drift_is_rejected():
    packet, _dispatcher = source()
    dispatcher = LocalCommandDispatcher()
    dispatcher.register(
        command_type="city.status.read",
        building_id="github-service",
        capability_id=(
            "city.github.repository-snapshot"
        ),
        handler=lambda _arguments: {},
    )

    with pytest.raises(
        CityDispatchPreflightError,
        match="registration target mismatch",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_directory_target_drift_is_rejected():
    packet, dispatcher = source()
    directory = build_directory()

    for location in directory["locations"]:
        location["capabilities"] = [
            item
            for item in location["capabilities"]
            if item["id"]
            != "city.control-tower.status-board"
        ]

    with pytest.raises(
        CityDispatchPreflightError,
        match="resolve exactly once",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
            directory=directory,
        )


@pytest.mark.parametrize(
    "field",
    [
        "grantConsumed",
        "consumerConnected",
        "dispatchesCommand",
        "executesAction",
        "mutatesPolicy",
    ],
)
def test_unsafe_packet_flags_are_rejected(
    field,
):
    packet, dispatcher = source()
    packet[field] = True

    with pytest.raises(
        CityDispatchPreflightError,
        match="unsafe field",
    ):
        validate_dispatch_preflight(
            packet,
            dispatcher=dispatcher,
        )


def test_inputs_are_not_mutated():
    packet, dispatcher = source()
    snapshot = copy.deepcopy(packet)

    validate_dispatch_preflight(
        packet,
        dispatcher=dispatcher,
    )

    assert packet == snapshot


def test_contract_is_final_preflight_only():
    contract = load_contract()

    assert contract["authority"] == (
        "final-preflight-only"
    )
    assert contract[
        "preflightState"
    ] == "validated-not-dispatched"
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "grantConsumption": "not-allowed",
    }


def test_direct_cli_runs_without_dispatch():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "dispatch_preflight.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Dispatch Gate OK: "
        "validated-not-dispatched / "
        "command=city.status.read / "
        "preflight=true / dispatched=false / "
        "bondik-city-dispatch-preflight-record/1"
        in result.stdout
    )
