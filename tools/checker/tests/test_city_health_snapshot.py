import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.build_health_snapshot import (
    BUILDING_ID,
    HEALTH_PROTOCOL,
    HEALTH_VERSION,
    CityHealthSnapshotError,
    build_health_snapshot,
    parse_failure_state,
)


ROOT = Path(__file__).resolve().parents[3]


def test_missing_artifacts_are_unknown(
    tmp_path,
):
    snapshot = build_health_snapshot(
        stream_state=(
            tmp_path / "stream.json"
        ),
        epg_state=(
            tmp_path / "epg.json"
        ),
    )

    assert snapshot["protocol"] == (
        HEALTH_PROTOCOL
    )
    assert snapshot["version"] == (
        HEALTH_VERSION
    )
    assert snapshot["buildingId"] == (
        BUILDING_ID
    )
    assert snapshot["status"] == "unknown"
    assert (
        snapshot["sources"]["stream"][
            "available"
        ]
        is False
    )
    assert (
        snapshot["sources"]["epg"][
            "available"
        ]
        is False
    )


def test_empty_states_are_healthy(
    tmp_path,
):
    stream = tmp_path / "stream.json"
    epg = tmp_path / "epg.json"
    stream.write_text(
        "{}\n",
        encoding="utf-8",
    )
    epg.write_text(
        "{}\n",
        encoding="utf-8",
    )

    snapshot = build_health_snapshot(
        stream_state=stream,
        epg_state=epg,
    )

    assert snapshot["status"] == "healthy"
    assert (
        snapshot["sources"]["stream"][
            "failureCount"
        ]
        == 0
    )
    assert (
        snapshot["sources"]["epg"][
            "failureCount"
        ]
        == 0
    )


def test_failures_are_sorted_and_degraded(
    tmp_path,
):
    stream = tmp_path / "stream.json"
    epg = tmp_path / "epg.json"
    stream.write_text(
        json.dumps(
            {
                "TV Ružinov": 4,
                "Alpha": 2,
            }
        ),
        encoding="utf-8",
    )
    epg.write_text(
        json.dumps(
            {
                "epgshare-cz": 3,
            }
        ),
        encoding="utf-8",
    )

    snapshot = build_health_snapshot(
        stream_state=stream,
        epg_state=epg,
    )

    assert snapshot["status"] == "degraded"
    assert (
        snapshot["sources"]["stream"][
            "failures"
        ]
        == [
            {
                "name": "Alpha",
                "streak": 2,
            },
            {
                "name": "TV Ružinov",
                "streak": 4,
            },
        ]
    )
    assert (
        snapshot["sources"]["epg"][
            "failures"
        ]
        == [
            {
                "name": "epgshare-cz",
                "streak": 3,
            }
        ]
    )


def test_degraded_wins_over_unknown(
    tmp_path,
):
    stream = tmp_path / "stream.json"
    stream.write_text(
        '{"Broken": 1}\n',
        encoding="utf-8",
    )

    snapshot = build_health_snapshot(
        stream_state=stream,
        epg_state=(
            tmp_path / "missing-epg.json"
        ),
    )

    assert snapshot["status"] == "degraded"


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '{"": 1}',
        '{"bad": 0}',
        '{"bad": true}',
        '{"bad": "3"}',
    ],
)
def test_invalid_state_is_rejected(raw):
    with pytest.raises(
        CityHealthSnapshotError
    ):
        parse_failure_state(
            raw,
            source="stream",
        )


def test_snapshot_is_read_only_by_contract(
    tmp_path,
):
    snapshot = build_health_snapshot(
        stream_state=(
            tmp_path / "stream.json"
        ),
        epg_state=(
            tmp_path / "epg.json"
        ),
    )

    assert snapshot["exposure"] == {
        "sensitiveState": "not-exposed",
        "execution": "not-exposed",
        "mutation": "not-allowed",
    }


def test_direct_cli_writes_snapshot(
    tmp_path,
):
    output = tmp_path / "snapshot.json"

    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "build_health_snapshot.py"
            ),
            "--stream-state",
            str(tmp_path / "missing-stream"),
            "--epg-state",
            str(tmp_path / "missing-epg"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(
        output.read_text(encoding="utf-8")
    )
    assert payload["status"] == "unknown"
    assert (
        "Bondik City Control Tower OK:"
        in result.stdout
    )
