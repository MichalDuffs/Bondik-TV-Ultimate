import json
from pathlib import Path
import subprocess
import sys

from tools.city.build_archive_index import (
    ARCHIVE_PROTOCOL,
    ARTIFACTS,
    build_archive_index,
)


ROOT = Path(__file__).resolve().parents[3]


def test_missing_optional_artifacts_are_indexed(
    tmp_path,
):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "city-capabilities.json").write_text(
        json.dumps(
            {
                "protocol": (
                    "bondik-city-capability-registry/1"
                )
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config" / "city-signal.json").write_text(
        json.dumps(
            {
                "protocol": (
                    "bondik-city-agent-signal/1"
                )
            }
        ),
        encoding="utf-8",
    )

    index = build_archive_index(tmp_path)

    assert index["protocol"] == ARCHIVE_PROTOCOL
    assert index["summary"]["known"] == len(ARTIFACTS)
    assert index["summary"]["available"] == 2
    assert index["summary"]["missing"] == 3


def test_index_hashes_content_without_copying_it(
    tmp_path,
):
    (tmp_path / "config").mkdir()
    for relative in (
        "config/city-capabilities.json",
        "config/city-signal.json",
    ):
        path = tmp_path / relative
        path.write_text(
            '{"protocol":"bondik-city-test/1"}',
            encoding="utf-8",
        )

    (tmp_path / "city-status.md").write_text(
        "Protocol: bondik-city-status-board/1\n"
        "SECRETISH-CONTENT\n",
        encoding="utf-8",
    )

    index = build_archive_index(tmp_path)
    board = next(
        item
        for item in index["entries"]
        if item["id"] == "status-board"
    )

    assert board["available"] is True
    assert len(board["sha256"]) == 64
    assert board["protocol"] == (
        "bondik-city-status-board/1"
    )
    assert "SECRETISH-CONTENT" not in json.dumps(index)


def test_generated_json_protocol_is_detected(
    tmp_path,
):
    (tmp_path / "config").mkdir()
    for relative in (
        "config/city-capabilities.json",
        "config/city-signal.json",
    ):
        (tmp_path / relative).write_text(
            "{}",
            encoding="utf-8",
        )

    (tmp_path / "city-github-snapshot.json").write_text(
        json.dumps(
            {
                "protocol": (
                    "bondik-city-github-service/1"
                )
            }
        ),
        encoding="utf-8",
    )

    index = build_archive_index(tmp_path)
    github = next(
        item
        for item in index["entries"]
        if item["id"] == "github-snapshot"
    )

    assert github["protocol"] == (
        "bondik-city-github-service/1"
    )


def test_archive_contract_is_read_only(
    tmp_path,
):
    (tmp_path / "config").mkdir()

    index = build_archive_index(tmp_path)

    assert index["exposure"] == {
        "content": "not-copied",
        "mutation": "not-allowed",
        "execution": "not-exposed",
    }


def test_direct_cli_writes_index(tmp_path):
    output = tmp_path / "index.json"

    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "build_archive_index.py"
            ),
            "--root",
            str(ROOT),
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
    assert payload["protocol"] == ARCHIVE_PROTOCOL
    assert "Bondik City Archive OK:" in result.stdout
