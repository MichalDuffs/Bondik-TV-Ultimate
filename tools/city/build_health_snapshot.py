from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HEALTH_PROTOCOL = "bondik-city-health-snapshot/1"
HEALTH_VERSION = 1
CITY_ID = "bondik-city"
BUILDING_ID = "control-tower"

DEFAULT_STREAM_STATE = Path(
    "stream-health-state.json"
)
DEFAULT_EPG_STATE = Path(
    "epg-health-state.json"
)
DEFAULT_OUTPUT = Path(
    "city-health-snapshot.json"
)


class CityHealthSnapshotError(ValueError):
    pass


def parse_failure_state(
    raw: str,
    *,
    source: str,
) -> dict[str, int]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CityHealthSnapshotError(
            f"{source} state must be valid JSON"
        ) from error

    if not isinstance(payload, dict):
        raise CityHealthSnapshotError(
            f"{source} state must be a JSON object"
        )

    failures: dict[str, int] = {}

    for name, streak in payload.items():
        if (
            not isinstance(name, str)
            or not name.strip()
        ):
            raise CityHealthSnapshotError(
                f"{source} state contains "
                "an invalid name"
            )

        if (
            not isinstance(streak, int)
            or isinstance(streak, bool)
            or streak < 1
        ):
            raise CityHealthSnapshotError(
                f"{source} state contains "
                f"an invalid streak for {name}"
            )

        failures[name] = streak

    return failures


def build_source_snapshot(
    path: Path,
    *,
    source: str,
) -> dict[str, Any]:
    if not path.is_file():
        return {
            "available": False,
            "status": "unknown",
            "failureCount": 0,
            "failures": [],
        }

    try:
        raw = path.read_text(
            encoding="utf-8-sig",
        )
    except OSError as error:
        raise CityHealthSnapshotError(
            f"cannot read {source} state: {error}"
        ) from error

    failures = parse_failure_state(
        raw,
        source=source,
    )

    return {
        "available": True,
        "status": (
            "degraded"
            if failures
            else "healthy"
        ),
        "failureCount": len(failures),
        "failures": [
            {
                "name": name,
                "streak": failures[name],
            }
            for name
            in sorted(failures)
        ],
    }


def overall_status(
    sources: dict[str, dict[str, Any]],
) -> str:
    statuses = {
        source["status"]
        for source in sources.values()
    }

    if "degraded" in statuses:
        return "degraded"

    if "unknown" in statuses:
        return "unknown"

    return "healthy"


def build_health_snapshot(
    *,
    stream_state: Path,
    epg_state: Path,
) -> dict[str, Any]:
    sources = {
        "stream": build_source_snapshot(
            stream_state,
            source="stream",
        ),
        "epg": build_source_snapshot(
            epg_state,
            source="epg",
        ),
    }

    return {
        "protocol": HEALTH_PROTOCOL,
        "version": HEALTH_VERSION,
        "cityId": CITY_ID,
        "buildingId": BUILDING_ID,
        "mode": "read-only-health-snapshot",
        "status": overall_status(sources),
        "sources": sources,
        "exposure": {
            "sensitiveState": "not-exposed",
            "execution": "not-exposed",
            "mutation": "not-allowed",
        },
    }


def write_health_snapshot(
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
            "Control Tower health snapshot."
        )
    )
    parser.add_argument(
        "--stream-state",
        type=Path,
        default=DEFAULT_STREAM_STATE,
    )
    parser.add_argument(
        "--epg-state",
        type=Path,
        default=DEFAULT_EPG_STATE,
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
        snapshot = build_health_snapshot(
            stream_state=args.stream_state,
            epg_state=args.epg_state,
        )
        write_health_snapshot(
            args.output,
            snapshot,
        )
    except CityHealthSnapshotError as error:
        print(
            f"❌ Bondik City health snapshot: {error}"
        )
        return 1

    print(
        "Bondik City Control Tower OK: "
        f"{snapshot['status']} / "
        f"{snapshot['protocol']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
