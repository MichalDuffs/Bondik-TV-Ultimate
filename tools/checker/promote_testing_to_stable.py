#!/usr/bin/env python3
"""Bondik TV STABLE PROMOTION v1.0.

Safely promote manually approved testing channels to stable.

Requirements:
- channel must currently be status=testing
- manual stable approval must exist
- approval must be bound to the current stream URL
- Testing Promotion Gate must say eligible=true
- counted passes must meet the required threshold
- last gate result must be pass
- gate report stream URL must match the current channel URL
- promotion report must be recent
- DRY-RUN by default
- --apply is required to edit channels.yaml
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CHANNELS = ROOT / "channels" / "channels.yaml"
DEFAULT_REPORT = (
    ROOT
    / "hunt-results"
    / "testing-promotion"
    / "promotion_status.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Bondik STABLE PROMOTION v{VERSION}"
    )

    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help="Manual stable-promotion decisions JSON",
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Testing Promotion Gate promotion_status.json",
    )

    parser.add_argument(
        "--channels",
        type=Path,
        default=DEFAULT_CHANNELS,
        help="Central channels.yaml",
    )

    parser.add_argument(
        "--max-report-age-hours",
        type=float,
        default=24.0,
        help="Maximum accepted Promotion Gate report age",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually change approved testing channels to stable",
    )

    args = parser.parse_args()

    if args.max_report_age_hours <= 0:
        parser.error("--max-report-age-hours must be greater than zero")

    return args


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON root: {path}")

    return payload


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML root: {path}")

    return payload


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def stream_url(channel: dict[str, Any]) -> str:
    stream = channel.get("stream")

    if not isinstance(stream, dict):
        return ""

    return str(stream.get("url", "")).strip()


def approved_decisions(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    entries = payload.get("channels", [])

    if not isinstance(entries, list):
        return result

    for item in entries:
        if not isinstance(item, dict):
            continue

        decision = str(
            item.get("decision", "")
        ).strip().casefold()

        channel_id = str(
            item.get("id", "")
        ).strip()

        if decision == "approve" and channel_id:
            result[channel_id] = item

    return result


def channel_index(
    database: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for channel in database.get("channels", []):
        if not isinstance(channel, dict):
            continue

        channel_id = str(
            channel.get("id", "")
        ).strip()

        if channel_id:
            result[channel_id] = channel

    return result


def report_index(
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in report.get("channels", []):
        if not isinstance(row, dict):
            continue

        channel_id = str(
            row.get("id", "")
        ).strip()

        if channel_id:
            result[channel_id] = row

    return result


def report_freshness_reasons(
    report: dict[str, Any],
    *,
    max_age_hours: float,
    now: datetime | None = None,
) -> list[str]:
    generated = parse_time(
        report.get("generated_at")
    )

    if generated is None:
        return ["promotion report has invalid generated_at"]

    if now is None:
        now = datetime.now(timezone.utc)

    age_hours = (
        now.astimezone(timezone.utc) - generated
    ).total_seconds() / 3600.0

    if age_hours < -0.1:
        return ["promotion report generated_at is in the future"]

    if age_hours > max_age_hours:
        return [
            (
                "promotion report is stale "
                f"({age_hours:.1f}h > {max_age_hours:g}h)"
            )
        ]

    return []


def promotion_reasons(
    channel: dict[str, Any],
    report_row: dict[str, Any],
    decision: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []

    status = str(
        channel.get("status", "")
    ).strip()

    current_url = stream_url(channel)

    decision_url = str(
        decision.get("stream_url", "")
    ).strip()

    note = str(
        decision.get("note", "")
    ).strip()

    report_url = str(
        report_row.get("stream_url", "")
    ).strip()

    try:
        counted = int(
            report_row.get("counted_passes", 0)
            or 0
        )
    except (TypeError, ValueError):
        counted = 0

    try:
        required = int(
            report_row.get("required_passes", 0)
            or 0
        )
    except (TypeError, ValueError):
        required = 0

    last_result = str(
        report_row.get("last_result", "")
    ).strip().casefold()

    if status != "testing":
        reasons.append(
            f"channel status is {status or 'missing'}, not testing"
        )

    if not current_url:
        reasons.append("current channel has no stream URL")

    if not decision_url:
        reasons.append("missing decision stream_url")
    elif current_url and decision_url != current_url:
        reasons.append(
            "decision stream URL does not match current channel"
        )

    if not note:
        reasons.append("missing manual review note")

    if not report_url:
        reasons.append("promotion report has no stream URL")
    elif current_url and report_url != current_url:
        reasons.append(
            "promotion report stream URL does not match current channel"
        )

    if report_row.get("eligible") is not True:
        reasons.append("promotion gate says not eligible")

    if required < 1:
        reasons.append("invalid required pass count")
    elif counted < required:
        reasons.append(
            f"insufficient counted passes: {counted}/{required}"
        )

    if last_result != "pass":
        reasons.append(
            f"last promotion-gate result is {last_result or 'missing'}"
        )

    return list(dict.fromkeys(reasons))


def promote_status_in_text(
    text: str,
    channel_id: str,
) -> str:
    """Change only the target channel status line."""

    lines = text.splitlines(keepends=True)

    start: int | None = None
    end = len(lines)

    for index, line in enumerate(lines):
        plain = line.rstrip("\r\n")

        if not plain.startswith("  - id: "):
            continue

        current_id = plain[len("  - id: "):].strip().strip('"').strip("'")

        if start is not None:
            end = index
            break

        if current_id == channel_id:
            start = index

    if start is None:
        raise ValueError(
            f"channel block not found: {channel_id}"
        )

    for index in range(start, end):
        plain = lines[index].rstrip("\r\n")

        if plain in {
            "    status: testing",
            '    status: "testing"',
            "    status: 'testing'",
        }:
            if lines[index].endswith("\r\n"):
                ending = "\r\n"
            elif lines[index].endswith("\n"):
                ending = "\n"
            else:
                ending = ""

            lines[index] = (
                plain.replace("testing", "stable", 1)
                + ending
            )

            return "".join(lines)

    raise ValueError(
        f"testing status line not found: {channel_id}"
    )


def read_text_preserving_bom(
    path: Path,
) -> tuple[str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")

    return raw.decode("utf-8-sig"), has_bom


def write_text_preserving_bom(
    path: Path,
    text: str,
    has_bom: bool,
) -> None:
    raw = text.encode("utf-8")

    if has_bom:
        raw = b"\xef\xbb\xbf" + raw

    path.write_bytes(raw)


def main() -> int:
    args = parse_args()

    for path in (
        args.channels,
        args.report,
        args.decisions,
    ):
        if not path.exists():
            raise SystemExit(
                f"ERROR: file not found: {path}"
            )

    database = load_yaml(args.channels)
    report = load_json(args.report)
    decisions = load_json(args.decisions)

    channels = channel_index(database)
    rows = report_index(report)
    approvals = approved_decisions(decisions)

    report_risks = report_freshness_reasons(
        report,
        max_age_hours=args.max_report_age_hours,
    )

    ready: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
        ]
    ] = []

    skipped: list[tuple[str, str]] = []

    for channel_id, decision in approvals.items():
        channel = channels.get(channel_id)

        if channel is None:
            skipped.append(
                (channel_id, "channel not found")
            )
            continue

        name = str(
            channel.get("name", channel_id)
        ).strip()

        row = rows.get(channel_id)

        if row is None:
            skipped.append(
                (
                    name,
                    "channel missing from promotion report",
                )
            )
            continue

        reasons = list(report_risks)

        reasons.extend(
            promotion_reasons(
                channel,
                row,
                decision,
            )
        )

        reasons = list(dict.fromkeys(reasons))

        if reasons:
            skipped.append(
                (name, "; ".join(reasons))
            )
            continue

        ready.append(
            (channel, row, decision)
        )

    print()
    print(
        f"🐾 Bondik STABLE PROMOTION v{VERSION}"
    )
    print("=" * 64)
    print(
        f"Manual approvals : {len(approvals)}"
    )
    print(
        f"Ready for stable : {len(ready)}"
    )
    print(
        f"Skipped          : {len(skipped)}"
    )
    print(
        f"Mode             : "
        f"{'APPLY' if args.apply else 'DRY-RUN'}"
    )
    print("=" * 64)

    for channel, row, _decision in ready:
        print(
            f"🏆 {channel['name']} "
            f"({channel['country']} / "
            f"{channel['category']}) "
            f"{row['counted_passes']}/"
            f"{row['required_passes']} "
            f"-> stable"
        )

    if skipped:
        print()
        print("Skipped:")

        for name, reason in skipped:
            print(
                f"⚠️ {name}: {reason}"
            )

    if not args.apply:
        print()
        print("No files changed.")
        print(
            "Review the proposal, then run again with --apply."
        )
        return 0

    if not ready:
        print()
        print("Nothing to apply.")
        return 0

    text, has_bom = read_text_preserving_bom(
        args.channels
    )

    for channel, _row, _decision in ready:
        text = promote_status_in_text(
            text,
            str(channel["id"]),
        )

    write_text_preserving_bom(
        args.channels,
        text,
        has_bom,
    )

    print()
    print(
        f"✅ Promoted {len(ready)} channel(s) "
        "from testing to stable"
    )
    print(
        f"📋 Updated: {args.channels}"
    )
    print(
        "🐾 Regenerate playlists and run the full test suite."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

