from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from tools.city.validate_capability_registry import (
    validate_capability_registry,
)
from tools.city.validate_city_signal import (
    validate_city_signal,
)

STATUS_BOARD_PROTOCOL = (
    "bondik-city-status-board/1"
)
STATUS_BOARD_VERSION = 1

DEFAULT_CAPABILITY_PATH = (
    ROOT / "config" / "city-capabilities.json"
)
DEFAULT_SIGNAL_PATH = (
    ROOT / "config" / "city-signal.json"
)
DEFAULT_HEALTH_PATH = (
    ROOT / "city-health-snapshot.json"
)
DEFAULT_OUTPUT = (
    ROOT / "city-status.md"
)


class CityStatusBoardError(ValueError):
    pass


def _load_json(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig",
            )
        )
    except OSError as error:
        raise CityStatusBoardError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityStatusBoardError(
            f"{label} must be valid JSON"
        ) from error


def load_capabilities(
    path: Path,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="capability registry",
    )
    return validate_capability_registry(
        payload
    )


def load_signal(
    path: Path,
    registry: dict[str, Any],
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="city signal",
    )
    return validate_city_signal(
        payload,
        registry,
    )


def load_health(
    path: Path,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None

    payload = _load_json(
        path,
        label="health snapshot",
    )

    if not isinstance(payload, dict):
        raise CityStatusBoardError(
            "health snapshot must be an object"
        )

    if payload.get("protocol") != (
        "bondik-city-health-snapshot/1"
    ):
        raise CityStatusBoardError(
            "unsupported health snapshot protocol"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityStatusBoardError(
            "health snapshot cityId mismatch"
        )

    if payload.get("status") not in {
        "healthy",
        "degraded",
        "unknown",
    }:
        raise CityStatusBoardError(
            "health snapshot status invalid"
        )

    return payload


def _status_emoji(status: str) -> str:
    return {
        "healthy": "🟢",
        "degraded": "🔴",
        "unknown": "⚪",
        "active": "✅",
        "planned": "🧭",
        "disabled": "⛔",
    }.get(status, "•")


def _health_lines(
    health: dict[str, Any] | None,
) -> list[str]:
    if health is None:
        return [
            "## Control Tower",
            "",
            "⚪ **UNKNOWN** — health snapshot is "
            "not available in this workspace.",
            "",
            "Missing evidence is not treated "
            "as GREEN.",
        ]

    status = health["status"]
    lines = [
        "## Control Tower",
        "",
        (
            f"{_status_emoji(status)} "
            f"**{status.upper()}**"
        ),
        "",
    ]

    sources = health.get("sources", {})

    for source_name in ("stream", "epg"):
        source = sources.get(
            source_name,
            {},
        )
        source_status = source.get(
            "status",
            "unknown",
        )
        lines.append(
            (
                f"- {_status_emoji(source_status)} "
                f"{source_name}: "
                f"{source_status}"
            )
        )

        for failure in source.get(
            "failures",
            [],
        ):
            lines.append(
                (
                    "  - "
                    f"{failure.get('name')} "
                    f"(streak ×"
                    f"{failure.get('streak')})"
                )
            )

    return lines


def _capability_lines(
    registry: dict[str, Any],
) -> list[str]:
    capabilities = registry[
        "capabilities"
    ]
    active = [
        item
        for item in capabilities
        if item["status"] == "active"
    ]
    planned = [
        item
        for item in capabilities
        if item["status"] == "planned"
    ]

    lines = [
        "## City capabilities",
        "",
        (
            f"Active: **{len(active)}** · "
            f"Planned: **{len(planned)}**"
        ),
        "",
    ]

    for capability in capabilities:
        status = capability["status"]
        surfaces = capability.get(
            "surfaces",
            [],
        )
        surface_text = (
            ", ".join(surfaces)
            if surfaces
            else "none"
        )
        lines.append(
            (
                f"- {_status_emoji(status)} "
                f"`{capability['id']}` — "
                f"{status}; surfaces: "
                f"{surface_text}"
            )
        )

    return lines


def _signal_lines(
    signal: dict[str, Any],
) -> list[str]:
    exposure = signal["exposure"]
    handoff = signal["handoff"]

    return [
        "## AI city signal",
        "",
        (
            f"- protocol: "
            f"`{signal['protocol']}`"
        ),
        (
            f"- mode: "
            f"`{signal['identity']['mode']}`"
        ),
        (
            f"- execution: "
            f"`{exposure['execution']}`"
        ),
        (
            f"- sensitive state: "
            f"`{exposure['sensitiveState']}`"
        ),
        (
            f"- command endpoint: "
            f"`{exposure['commandEndpoint']}`"
        ),
        (
            f"- handoff: "
            f"`{handoff['status']}`"
        ),
    ]


def render_status_board(
    *,
    registry: dict[str, Any],
    signal: dict[str, Any],
    health: dict[str, Any] | None,
) -> str:
    lines = [
        "# 🏙️ Bondík City — Status Board",
        "",
        (
            f"Protocol: "
            f"`{STATUS_BOARD_PROTOCOL}`"
        ),
        "",
        (
            "Same project reality for humans "
            "and future agents."
        ),
        "",
    ]

    lines.extend(
        _health_lines(health)
    )
    lines.extend(["", ""])
    lines.extend(
        _capability_lines(registry)
    )
    lines.extend(["", ""])
    lines.extend(
        _signal_lines(signal)
    )
    lines.extend(
        [
            "",
            "",
            "## Safety",
            "",
            (
                "This board is a read-only "
                "projection. It does not execute "
                "capabilities, mutate health "
                "state, or enable agent handoff."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_status_board(
    path: Path,
    content: str,
) -> None:
    path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Render a human-readable Bondik "
            "City Control Tower status board."
        )
    )
    parser.add_argument(
        "--capabilities",
        type=Path,
        default=DEFAULT_CAPABILITY_PATH,
    )
    parser.add_argument(
        "--signal",
        type=Path,
        default=DEFAULT_SIGNAL_PATH,
    )
    parser.add_argument(
        "--health",
        type=Path,
        default=DEFAULT_HEALTH_PATH,
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
        registry = load_capabilities(
            args.capabilities
        )
        signal = load_signal(
            args.signal,
            registry,
        )
        health = load_health(
            args.health
        )
        rendered = render_status_board(
            registry=registry,
            signal=signal,
            health=health,
        )
        write_status_board(
            args.output,
            rendered,
        )
    except CityStatusBoardError as error:
        print(
            f"❌ Bondik City status board: {error}"
        )
        return 1

    health_status = (
        health["status"]
        if health is not None
        else "unknown"
    )

    print(
        "Bondik City Status Board OK: "
        f"{health_status} / "
        f"{STATUS_BOARD_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
