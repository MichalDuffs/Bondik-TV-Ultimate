from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ARCHIVE_PROTOCOL = "bondik-city-archive-index/1"
ARCHIVE_VERSION = 1
CITY_ID = "bondik-city"
BUILDING_ID = "archive"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "city-archive-index.json"

ARTIFACTS = (
    {
        "id": "capability-registry",
        "path": "config/city-capabilities.json",
        "kind": "committed-config",
    },
    {
        "id": "city-signal",
        "path": "config/city-signal.json",
        "kind": "committed-config",
    },
    {
        "id": "health-snapshot",
        "path": "city-health-snapshot.json",
        "kind": "generated-local",
    },
    {
        "id": "github-snapshot",
        "path": "city-github-snapshot.json",
        "kind": "generated-local",
    },
    {
        "id": "status-board",
        "path": "city-status.md",
        "kind": "generated-local",
    },
)

PROTOCOL_RE = re.compile(
    r"bondik-city-[a-z0-9-]+/\d+"
)


class CityArchiveError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_protocol(
    path: Path,
    data: bytes,
) -> str | None:
    if path.suffix == ".json":
        try:
            payload = json.loads(
                data.decode("utf-8-sig")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None

        if isinstance(payload, dict):
            protocol = payload.get("protocol")
            if isinstance(protocol, str):
                return protocol

        return None

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None

    match = PROTOCOL_RE.search(text)
    return match.group(0) if match else None


def build_archive_index(
    root: Path = ROOT,
) -> dict[str, Any]:
    entries = []

    for spec in ARTIFACTS:
        relative = Path(spec["path"])
        path = root / relative

        if not path.is_file():
            entries.append(
                {
                    "id": spec["id"],
                    "path": spec["path"],
                    "kind": spec["kind"],
                    "available": False,
                }
            )
            continue

        try:
            data = path.read_bytes()
        except OSError as error:
            raise CityArchiveError(
                f"cannot read {spec['path']}: {error}"
            ) from error

        entries.append(
            {
                "id": spec["id"],
                "path": spec["path"],
                "kind": spec["kind"],
                "available": True,
                "bytes": len(data),
                "sha256": _sha256(data),
                "protocol": _extract_protocol(
                    path,
                    data,
                ),
            }
        )

    return {
        "protocol": ARCHIVE_PROTOCOL,
        "version": ARCHIVE_VERSION,
        "cityId": CITY_ID,
        "buildingId": BUILDING_ID,
        "mode": "read-only-evidence-index",
        "entries": entries,
        "summary": {
            "known": len(entries),
            "available": sum(
                item["available"]
                for item in entries
            ),
            "missing": sum(
                not item["available"]
                for item in entries
            ),
        },
        "exposure": {
            "content": "not-copied",
            "mutation": "not-allowed",
            "execution": "not-exposed",
        },
    }


def write_archive_index(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only Bondik City "
            "Archive evidence index."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        payload = build_archive_index(
            args.root
        )
        write_archive_index(
            args.output,
            payload,
        )
    except CityArchiveError as error:
        print(
            f"❌ Bondik City Archive: {error}"
        )
        return 1

    summary = payload["summary"]
    print(
        "Bondik City Archive OK: "
        f"{summary['available']}/"
        f"{summary['known']} available / "
        f"{ARCHIVE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
