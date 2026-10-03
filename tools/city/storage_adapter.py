from __future__ import annotations

import argparse
import copy
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Protocol

ADAPTER_PROTOCOL = "bondik-city-storage-adapter/1"
RECORD_PROTOCOL = "bondik-city-storage-record/1"
FILE_PROTOCOL = "bondik-city-storage-file/1"
VERSION = 1
MAX_VALUE_BYTES = 65536

NAME_RE = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"
)


class CityStorageError(ValueError):
    pass


class StorageConflictError(
    CityStorageError
):
    pass


class StorageAdapter(Protocol):
    def read(
        self,
        namespace: str,
        key: str,
    ) -> dict[str, Any] | None:
        ...

    def write(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        ...

    def delete(
        self,
        namespace: str,
        key: str,
        *,
        expected_revision: int | None = None,
    ) -> bool:
        ...

    def list_keys(
        self,
        namespace: str,
    ) -> list[str]:
        ...


def _validate_name(
    value: Any,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not NAME_RE.fullmatch(value)
    ):
        raise CityStorageError(
            f"{label} is invalid"
        )

    return value


def _clone_json(
    value: Any,
    *,
    label: str,
) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as error:
        raise CityStorageError(
            f"{label} must be JSON serializable"
        ) from error

    if len(encoded) > MAX_VALUE_BYTES:
        raise CityStorageError(
            f"{label} exceeds size limit"
        )

    return json.loads(
        encoded.decode("utf-8")
    )


def _record(
    namespace: str,
    key: str,
    value: Any,
    revision: int,
) -> dict[str, Any]:
    return {
        "protocol": RECORD_PROTOCOL,
        "version": VERSION,
        "namespace": namespace,
        "key": key,
        "revision": revision,
        "value": _clone_json(
            value,
            label="value",
        ),
    }


def _check_expected_revision(
    current: dict[str, Any] | None,
    expected_revision: int | None,
) -> None:
    if expected_revision is None:
        return

    current_revision = (
        current.get("revision")
        if current is not None
        else 0
    )

    if current_revision != expected_revision:
        raise StorageConflictError(
            "expected revision mismatch"
        )


class MemoryStorageAdapter:
    def __init__(self) -> None:
        self._records: dict[
            str,
            dict[
                str,
                dict[str, Any],
            ],
        ] = {}

    def read(
        self,
        namespace: str,
        key: str,
    ) -> dict[str, Any] | None:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )

        record = self._records.get(
            namespace,
            {},
        ).get(key)

        return (
            copy.deepcopy(record)
            if record is not None
            else None
        )

    def write(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )
        current = self._records.get(
            namespace,
            {},
        ).get(key)

        _check_expected_revision(
            current,
            expected_revision,
        )

        revision = (
            current["revision"] + 1
            if current is not None
            else 1
        )
        record = _record(
            namespace,
            key,
            value,
            revision,
        )

        self._records.setdefault(
            namespace,
            {},
        )[key] = record

        return copy.deepcopy(record)

    def delete(
        self,
        namespace: str,
        key: str,
        *,
        expected_revision: int | None = None,
    ) -> bool:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )

        bucket = self._records.get(
            namespace
        )

        current = (
            bucket.get(key)
            if bucket is not None
            else None
        )

        _check_expected_revision(
            current,
            expected_revision,
        )

        if current is None:
            return False

        del bucket[key]

        if not bucket:
            self._records.pop(
                namespace,
                None,
            )

        return True

    def list_keys(
        self,
        namespace: str,
    ) -> list[str]:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )

        return sorted(
            self._records.get(
                namespace,
                {},
            )
        )


class JsonFileStorageAdapter:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = Path(path)

    def _load(
        self,
    ) -> dict[str, Any]:
        if not self.path.is_file():
            return {
                "protocol": FILE_PROTOCOL,
                "version": VERSION,
                "records": {},
            }

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8-sig",
                )
            )
        except OSError as error:
            raise CityStorageError(
                f"cannot read storage file: {error}"
            ) from error
        except json.JSONDecodeError as error:
            raise CityStorageError(
                "storage file must be valid JSON"
            ) from error

        if (
            not isinstance(payload, dict)
            or payload.get("protocol")
            != FILE_PROTOCOL
            or payload.get("version")
            != VERSION
            or not isinstance(
                payload.get("records"),
                dict,
            )
        ):
            raise CityStorageError(
                "storage file contract invalid"
            )

        return payload

    def _save(
        self,
        payload: dict[str, Any],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        content = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        fd, temp_name = tempfile.mkstemp(
            prefix=(
                f".{self.path.name}."
            ),
            suffix=".tmp",
            dir=self.path.parent,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temp_name,
                self.path,
            )
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def read(
        self,
        namespace: str,
        key: str,
    ) -> dict[str, Any] | None:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )
        payload = self._load()
        current = (
            payload["records"]
            .get(namespace, {})
            .get(key)
        )

        return (
            copy.deepcopy(current)
            if current is not None
            else None
        )

    def write(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )
        payload = self._load()
        bucket = payload[
            "records"
        ].setdefault(
            namespace,
            {},
        )
        current = bucket.get(key)

        _check_expected_revision(
            current,
            expected_revision,
        )

        revision = (
            current["revision"] + 1
            if current is not None
            else 1
        )
        record = _record(
            namespace,
            key,
            value,
            revision,
        )
        bucket[key] = record
        self._save(payload)

        return copy.deepcopy(record)

    def delete(
        self,
        namespace: str,
        key: str,
        *,
        expected_revision: int | None = None,
    ) -> bool:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        key = _validate_name(
            key,
            label="key",
        )
        payload = self._load()
        bucket = payload[
            "records"
        ].get(namespace)
        current = (
            bucket.get(key)
            if bucket is not None
            else None
        )

        _check_expected_revision(
            current,
            expected_revision,
        )

        if current is None:
            return False

        del bucket[key]

        if not bucket:
            del payload[
                "records"
            ][namespace]

        self._save(payload)
        return True

    def list_keys(
        self,
        namespace: str,
    ) -> list[str]:
        namespace = _validate_name(
            namespace,
            label="namespace",
        )
        payload = self._load()

        return sorted(
            payload["records"].get(
                namespace,
                {},
            )
        )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the Bondik City "
            "Storage Adapter self-test."
        )
    )
    return parser.parse_args()


def main() -> int:
    parse_arguments()

    with tempfile.TemporaryDirectory() as tmp:
        path = (
            Path(tmp)
            / "storage.json"
        )
        storage = JsonFileStorageAdapter(
            path
        )
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
            expected_revision=(
                first["revision"]
            ),
        )
        restored = storage.read(
            "bondik-tv",
            "session",
        )

        if (
            restored != second
            or second["revision"] != 2
        ):
            print(
                "❌ Bondik City Storage "
                "Adapter self-test failed"
            )
            return 1

    print(
        "Bondik City Storage Adapter OK: "
        "write=2 / restore=2 / "
        f"{ADAPTER_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
