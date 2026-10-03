import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.validate_capability_registry import (
    load_capability_registry,
)
from tools.city.validate_city_signal import (
    CitySignalError,
    SIGNAL_PROTOCOL,
    SIGNAL_VERSION,
    load_city_signal,
    validate_city_signal,
)


ROOT = Path(__file__).resolve().parents[3]
SIGNAL_PATH = ROOT / "config" / "city-signal.json"


def signal_payload():
    return json.loads(
        SIGNAL_PATH.read_text(encoding="utf-8")
    )


def registry_payload():
    return load_capability_registry()


def test_checked_in_signal_is_valid():
    payload = load_city_signal(SIGNAL_PATH)

    assert payload["protocol"] == SIGNAL_PROTOCOL
    assert payload["version"] == SIGNAL_VERSION


def test_signal_matches_registry_city():
    payload = signal_payload()
    registry = registry_payload()

    assert payload["cityId"] == registry["cityId"]


def test_signal_has_no_command_endpoint():
    payload = signal_payload()

    assert (
        payload["exposure"]["commandEndpoint"]
        is None
    )


def test_signal_exposes_no_execution_or_sensitive_state():
    payload = signal_payload()
    exposure = payload["exposure"]

    assert exposure["execution"] == "not-exposed"
    assert (
        exposure["sensitiveState"]
        == "not-exposed"
    )


def test_wrong_city_is_rejected():
    payload = signal_payload()
    payload["cityId"] = "other-city"

    with pytest.raises(
        CitySignalError,
        match="cityId must match registry",
    ):
        validate_city_signal(
            payload,
            registry_payload(),
        )


def test_command_endpoint_is_rejected():
    payload = signal_payload()
    payload["exposure"]["commandEndpoint"] = (
        "https://example.invalid/command"
    )

    with pytest.raises(
        CitySignalError,
        match="command endpoint must remain null",
    ):
        validate_city_signal(
            payload,
            registry_payload(),
        )


def test_execution_exposure_is_rejected():
    payload = signal_payload()
    payload["exposure"]["execution"] = "enabled"

    with pytest.raises(
        CitySignalError,
        match="execution must remain not-exposed",
    ):
        validate_city_signal(
            payload,
            registry_payload(),
        )


def test_handoff_cannot_be_enabled_in_v1():
    payload = signal_payload()
    payload["handoff"]["status"] = "enabled"

    with pytest.raises(
        CitySignalError,
        match="handoff must remain disabled",
    ):
        validate_city_signal(
            payload,
            registry_payload(),
        )


def test_signal_validator_runs_as_direct_script():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "validate_city_signal.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "Bondik City signal OK:"
        in result.stdout
    )
