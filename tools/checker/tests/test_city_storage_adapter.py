import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.storage_adapter import (
    ADAPTER_PROTOCOL,
    CityStorageError,
    JsonFileStorageAdapter,
    MemoryStorageAdapter,
    StorageConflictError,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "factory",
    [
        lambda tmp_path: (
            MemoryStorageAdapter()
        ),
        lambda tmp_path: (
            JsonFileStorageAdapter(
                tmp_path / "storage.json"
            )
        ),
    ],
)
def test_write_read_revision_and_list(
    factory,
    tmp_path,
):
    storage = factory(tmp_path)

    first = storage.write(
        "bondik-tv",
        "session",
        {
            "theme": "ultimate",
        },
        expected_revision=0,
    )
    second = storage.write(
        "bondik-tv",
        "session",
        {
            "theme": "ultimate",
            "activePlaylistId": "stable",
        },
        expected_revision=1,
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert storage.read(
        "bondik-tv",
        "session",
    ) == second
    assert storage.list_keys(
        "bondik-tv"
    ) == ["session"]


def test_file_adapter_persists_across_instances(
    tmp_path,
):
    path = tmp_path / "storage.json"

    first = JsonFileStorageAdapter(path)
    first.write(
        "bondik-tv",
        "session",
        {"theme": "ultimate"},
        expected_revision=0,
    )

    second = JsonFileStorageAdapter(path)

    assert second.read(
        "bondik-tv",
        "session",
    )["revision"] == 1


def test_stale_revision_is_rejected():
    storage = MemoryStorageAdapter()
    storage.write(
        "bondik-tv",
        "session",
        {},
        expected_revision=0,
    )

    with pytest.raises(
        StorageConflictError,
        match="revision mismatch",
    ):
        storage.write(
            "bondik-tv",
            "session",
            {},
            expected_revision=0,
        )


def test_delete_can_require_revision():
    storage = MemoryStorageAdapter()
    stored = storage.write(
        "bondik-tv",
        "session",
        {"theme": "ultimate"},
        expected_revision=0,
    )

    assert storage.delete(
        "bondik-tv",
        "session",
        expected_revision=(
            stored["revision"]
        ),
    ) is True
    assert storage.read(
        "bondik-tv",
        "session",
    ) is None


def test_read_returns_isolated_copy():
    storage = MemoryStorageAdapter()
    storage.write(
        "bondik-tv",
        "session",
        {
            "nested": {
                "value": 1,
            }
        },
        expected_revision=0,
    )

    first = storage.read(
        "bondik-tv",
        "session",
    )
    first["value"]["nested"][
        "value"
    ] = 99

    second = storage.read(
        "bondik-tv",
        "session",
    )

    assert second["value"][
        "nested"
    ]["value"] == 1


@pytest.mark.parametrize(
    ("namespace", "key"),
    [
        ("Bad Space", "session"),
        ("bondik-tv", "Bad Space"),
        ("", "session"),
        ("bondik-tv", ""),
    ],
)
def test_invalid_names_are_rejected(
    namespace,
    key,
):
    storage = MemoryStorageAdapter()

    with pytest.raises(
        CityStorageError,
        match="invalid",
    ):
        storage.write(
            namespace,
            key,
            {},
        )


def test_non_json_value_is_rejected():
    storage = MemoryStorageAdapter()

    with pytest.raises(
        CityStorageError,
        match="JSON serializable",
    ):
        storage.write(
            "bondik-tv",
            "session",
            {"bad": object()},
        )


def test_corrupt_file_fails_closed(
    tmp_path,
):
    path = tmp_path / "storage.json"
    path.write_text(
        "{bad-json",
        encoding="utf-8",
    )
    storage = JsonFileStorageAdapter(path)

    with pytest.raises(
        CityStorageError,
        match="valid JSON",
    ):
        storage.read(
            "bondik-tv",
            "session",
        )


def test_file_contract_is_versioned(
    tmp_path,
):
    path = tmp_path / "storage.json"
    storage = JsonFileStorageAdapter(path)
    storage.write(
        "bondik-tv",
        "session",
        {},
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert payload["protocol"] == (
        "bondik-city-storage-file/1"
    )
    assert payload["version"] == 1


def test_direct_cli_runs_self_test():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "storage_adapter.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Storage Adapter OK: "
        "write=2 / restore=2 / "
        f"{ADAPTER_PROTOCOL}"
        in result.stdout
    )
