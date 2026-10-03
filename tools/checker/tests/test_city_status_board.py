import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.render_status_board import (
    CityStatusBoardError,
    STATUS_BOARD_PROTOCOL,
    load_health,
    render_status_board,
)
from tools.city.validate_capability_registry import (
    load_capability_registry,
)
from tools.city.validate_city_signal import (
    load_city_signal,
)


ROOT = Path(__file__).resolve().parents[3]


def registry():
    return load_capability_registry()


def signal():
    return load_city_signal()


def test_missing_health_is_explicitly_unknown():
    rendered = render_status_board(
        registry=registry(),
        signal=signal(),
        health=None,
    )

    assert "⚪ **UNKNOWN**" in rendered
    assert (
        "Missing evidence is not treated "
        "as GREEN."
        in rendered
    )


def test_degraded_health_lists_failures():
    health = {
        "protocol": (
            "bondik-city-health-snapshot/1"
        ),
        "cityId": "bondik-city",
        "status": "degraded",
        "sources": {
            "stream": {
                "status": "degraded",
                "failures": [
                    {
                        "name": "TV Ružinov",
                        "streak": 4,
                    }
                ],
            },
            "epg": {
                "status": "degraded",
                "failures": [
                    {
                        "name": "epgshare-cz",
                        "streak": 3,
                    }
                ],
            },
        },
    }

    rendered = render_status_board(
        registry=registry(),
        signal=signal(),
        health=health,
    )

    assert "🔴 **DEGRADED**" in rendered
    assert "TV Ružinov (streak ×4)" in rendered
    assert "epgshare-cz (streak ×3)" in rendered


def test_registry_counts_are_rendered():
    payload = registry()
    rendered = render_status_board(
        registry=payload,
        signal=signal(),
        health=None,
    )

    active = sum(
        item["status"] == "active"
        for item in payload["capabilities"]
    )
    planned = sum(
        item["status"] == "planned"
        for item in payload["capabilities"]
    )

    assert (
        f"Active: **{active}**"
        in rendered
    )
    assert (
        f"Planned: **{planned}**"
        in rendered
    )


def test_signal_safety_is_visible():
    rendered = render_status_board(
        registry=registry(),
        signal=signal(),
        health=None,
    )

    assert "execution: `not-exposed`" in rendered
    assert (
        "sensitive state: `not-exposed`"
        in rendered
    )
    assert "command endpoint: `None`" in rendered
    assert "handoff: `not-enabled`" in rendered


def test_wrong_health_protocol_is_rejected(
    tmp_path,
):
    path = tmp_path / "health.json"
    path.write_text(
        json.dumps(
            {
                "protocol": "other/1",
                "cityId": "bondik-city",
                "status": "healthy",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        CityStatusBoardError,
        match="unsupported health snapshot",
    ):
        load_health(path)


def test_direct_cli_writes_human_board(
    tmp_path,
):
    output = tmp_path / "city-status.md"

    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "render_status_board.py"
            ),
            "--health",
            str(tmp_path / "missing-health.json"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    rendered = output.read_text(
        encoding="utf-8"
    )
    assert "# 🏙️ Bondík City — Status Board" in rendered
    assert STATUS_BOARD_PROTOCOL in rendered
    assert "⚪ **UNKNOWN**" in rendered
    assert (
        "Bondik City Status Board OK:"
        in result.stdout
    )
