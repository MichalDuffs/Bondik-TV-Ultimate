import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.device_share_adapter import (
    ADAPTER_PROTOCOL,
    HANDOFF_PROTOCOL,
    CityDeviceShareError,
    load_contract,
    prepare_handoff,
)


ROOT = Path(__file__).resolve().parents[3]


def target():
    return {
        "targetId": "living-room-tv",
        "kind": "android-tv",
        "displayName": "Living Room TV",
    }


def test_prepare_handoff_from_current_catalog():
    handoff = prepare_handoff(
        "polar-tv-cz",
        target=target(),
        requested_at=(
            "2026-10-03T20:00:00+02:00"
        ),
    )

    assert handoff["protocol"] == (
        HANDOFF_PROTOCOL
    )
    assert handoff["source"][
        "sourceId"
    ] == "polar-tv-cz"
    assert handoff["target"] == target()
    assert handoff["delivery"] == {
        "state": "prepared",
        "transport": "not-selected",
        "endpoint": None,
    }


def test_source_remains_non_executable():
    handoff = prepare_handoff(
        "polar-tv-cz",
        target=target(),
        requested_at=(
            "2026-10-03T20:00:00+02:00"
        ),
    )

    assert handoff["source"][
        "exposure"
    ]["playbackExecution"] == (
        "not-exposed"
    )
    assert handoff["exposure"] == {
        "network": "not-exposed",
        "execution": "not-exposed",
        "agentExecution": "not-exposed",
        "mutation": "not-allowed",
    }


def test_target_endpoint_field_is_rejected():
    unsafe = target()
    unsafe["endpoint"] = (
        "http://192.0.2.10"
    )

    with pytest.raises(
        CityDeviceShareError,
        match="unsupported fields",
    ):
        prepare_handoff(
            "polar-tv-cz",
            target=unsafe,
            requested_at=(
                "2026-10-03T20:00:00+02:00"
            ),
        )


def test_unsupported_target_kind_is_rejected():
    unsupported = target()
    unsupported["kind"] = "chromecast"

    with pytest.raises(
        CityDeviceShareError,
        match="not supported",
    ):
        prepare_handoff(
            "polar-tv-cz",
            target=unsupported,
            requested_at=(
                "2026-10-03T20:00:00+02:00"
            ),
        )


def test_unknown_channel_is_rejected():
    with pytest.raises(
        CityDeviceShareError,
        match="unknown channel id",
    ):
        prepare_handoff(
            "missing-channel",
            target=target(),
            requested_at=(
                "2026-10-03T20:00:00+02:00"
            ),
        )


def test_timestamp_requires_timezone():
    with pytest.raises(
        CityDeviceShareError,
        match="include timezone",
    ):
        prepare_handoff(
            "polar-tv-cz",
            target=target(),
            requested_at=(
                "2026-10-03T20:00:00"
            ),
        )


def test_contract_is_prepare_only():
    payload = load_contract()

    assert payload["protocol"] == (
        ADAPTER_PROTOCOL
    )
    assert payload["handoffProtocol"] == (
        HANDOFF_PROTOCOL
    )
    assert payload[
        "supportedTargetKinds"
    ] == ["android-tv"]
    assert payload["transport"] == (
        "not-selected"
    )
    assert payload["endpoint"] == (
        "not-exposed"
    )


def test_contract_file_matches_boundary():
    payload = json.loads(
        (
            ROOT
            / "config"
            / "city-device-share-contract.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload["exposure"] == {
        "network": "not-exposed",
        "execution": "not-exposed",
        "agentExecution": "not-exposed",
        "mutation": "not-allowed",
    }


def test_prepared_handoff_isolated_from_target():
    original = target()
    handoff = prepare_handoff(
        "polar-tv-cz",
        target=original,
        requested_at=(
            "2026-10-03T20:00:00+02:00"
        ),
    )
    original["displayName"] = "Changed"

    assert handoff["target"][
        "displayName"
    ] == "Living Room TV"


def test_direct_cli_prepares_without_delivery():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "device_share_adapter.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Device Share OK: "
        "polar-tv-cz -> demo-tv / "
        "prepared / "
        "bondik-city-device-handoff/1"
        in result.stdout
    )
