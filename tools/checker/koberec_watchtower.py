#!/usr/bin/env python3
"""Bondik Hunter v0.6 - Koberec Watchtower.

Audit Candidate Gate parking results without changing channels.yaml.

The Watchtower is deliberately conservative:
- raw IP hosts stay parked
- configured suspicious/restream domains stay parked
- test-feed paths stay parked
- geo-labelled-only parking can be surfaced for manual rescue review
- no item is approved or promoted automatically

Input is candidates.json produced by prepare_hunt_candidates.py v0.5+.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "0.6"

HARD_PARK_FLAGS = {
    "raw-ip-host",
    "suspicious-restream-domain",
    "test-feed-path",
}

SOFT_PARK_FLAGS = {
    "geo-labelled",
}

CSV_FIELDS = [
    "watchtower_action",
    "bondik_score",
    "candidate_name",
    "country_inferred",
    "category_inferred",
    "response_ms",
    "stream_host",
    "url",
    "review_flags",
    "watchtower_reasons",
    "source",
]

DOMAIN_FIELDS = [
    "stream_host",
    "candidate_count",
    "hard_count",
    "rescue_review_count",
    "max_bondik_score",
    "countries",
    "categories",
    "parking_flags",
    "candidate_names",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Bondik Candidate Gate parking results."
    )
    parser.add_argument(
        "candidates_json",
        type=Path,
        help="Candidate Gate candidates.json.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("hunt-results/watchtower"),
        help="Output directory.",
    )
    return parser.parse_args()


def load_candidates(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"{path}: candidates must be a list")
    version = str(payload.get("candidate_gate_version", "unknown"))
    return version, [dict(item) for item in candidates if isinstance(item, dict)]


def normalize_flags(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        raw = [part.strip() for part in value.split(";")]
    else:
        raw = []

    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        flag = str(item).strip()
        if flag and flag not in seen:
            seen.add(flag)
            result.append(flag)
    return result


def classify_parking(item: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify a parked candidate without approving it.

    keep-parked:
      at least one hard parking signal is present.

    manual-rescue-review:
      no hard signal exists and parking is explained only by soft parking
      signals such as geo-labelled. This is NOT an approval.
    """
    flags = set(normalize_flags(item.get("review_flags")))
    hard = sorted(flags & HARD_PARK_FLAGS)
    soft = sorted(flags & SOFT_PARK_FLAGS)

    if hard:
        return "keep-parked", [f"hard:{flag}" for flag in hard]

    if soft:
        return "manual-rescue-review", [f"soft:{flag}" for flag in soft]

    # Defensive fallback: an item claiming to be parked with no recognized
    # parking signal should not silently escape the parking lot.
    return "keep-parked", ["unrecognized-parking-reason"]


def score_value(item: dict[str, Any]) -> int:
    try:
        return int(item.get("bondik_score", 0))
    except (TypeError, ValueError):
        return 0


def response_value(item: dict[str, Any]) -> int:
    try:
        return int(item.get("response_ms"))
    except (TypeError, ValueError):
        return 10**9


def analyze(candidates: list[dict[str, Any]]) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    parked: list[dict[str, Any]] = []
    hard: list[dict[str, Any]] = []
    rescue: list[dict[str, Any]] = []
    stats = Counter()

    for source_item in candidates:
        stats["input_candidates"] += 1
        if str(source_item.get("review_bucket", "")).strip() != "parking":
            continue

        stats["parking_candidates"] += 1
        item = dict(source_item)
        flags = normalize_flags(item.get("review_flags"))
        action, reasons = classify_parking(item)
        item["review_flags"] = flags
        item["watchtower_action"] = action
        item["watchtower_reasons"] = reasons
        parked.append(item)

        if action == "manual-rescue-review":
            rescue.append(item)
            stats["manual_rescue_review"] += 1
        else:
            hard.append(item)
            stats["keep_parked"] += 1

        for flag in flags:
            if flag in HARD_PARK_FLAGS or flag in SOFT_PARK_FLAGS:
                stats[f"flag_{flag}"] += 1

    sort_key = lambda item: (
        -score_value(item),
        response_value(item),
        str(item.get("candidate_name", "")).casefold(),
    )
    parked.sort(key=sort_key)
    hard.sort(key=sort_key)
    rescue.sort(key=sort_key)

    return parked, hard, rescue, dict(stats)


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return value


def write_candidate_csv(path: Path, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow({
                field: csv_value(item.get(field))
                for field in CSV_FIELDS
            })


def domain_rows(parked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in parked:
        host = str(item.get("stream_host") or "").strip().casefold()
        grouped[host or "(unknown)"].append(item)

    rows: list[dict[str, Any]] = []
    for host, items in grouped.items():
        flags = Counter()
        countries = set()
        categories = set()
        names = []
        hard_count = 0
        rescue_count = 0

        for item in items:
            item_flags = normalize_flags(item.get("review_flags"))
            flags.update(
                flag for flag in item_flags
                if flag in HARD_PARK_FLAGS or flag in SOFT_PARK_FLAGS
            )
            if item.get("country_inferred"):
                countries.add(str(item["country_inferred"]))
            if item.get("category_inferred"):
                categories.add(str(item["category_inferred"]))
            if item.get("candidate_name"):
                names.append(str(item["candidate_name"]))

            if item.get("watchtower_action") == "manual-rescue-review":
                rescue_count += 1
            else:
                hard_count += 1

        rows.append({
            "stream_host": host,
            "candidate_count": len(items),
            "hard_count": hard_count,
            "rescue_review_count": rescue_count,
            "max_bondik_score": max((score_value(item) for item in items), default=0),
            "countries": sorted(countries),
            "categories": sorted(categories),
            "parking_flags": [
                f"{flag}:{count}" for flag, count in sorted(flags.items())
            ],
            "candidate_names": sorted(set(names), key=str.casefold),
        })

    rows.sort(key=lambda row: (
        -int(row["candidate_count"]),
        -int(row["hard_count"]),
        -int(row["max_bondik_score"]),
        str(row["stream_host"]),
    ))
    return rows


def write_domain_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DOMAIN_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                field: csv_value(row.get(field))
                for field in DOMAIN_FIELDS
            })


def write_summary(
    path: Path,
    gate_version: str,
    parked: list[dict[str, Any]],
    hard: list[dict[str, Any]],
    rescue: list[dict[str, Any]],
    domains: list[dict[str, Any]],
    stats: dict[str, int],
) -> None:
    lines = [
        "# 🐱🔭 Koberec Watchtower",
        "",
        f"Version: {VERSION}",
        f"Candidate Gate input version: {gate_version}",
        "",
        "The Watchtower audits parking only. It never approves a stream and never edits channels.yaml.",
        "",
        f"- Input candidates: {stats.get('input_candidates', 0)}",
        f"- Parking candidates inspected: {len(parked)}",
        f"- Keep parked: {len(hard)}",
        f"- Manual rescue review: {len(rescue)}",
        f"- Parking domains: {len(domains)}",
        "",
        "## Parking signals",
        "",
    ]

    for flag in sorted(HARD_PARK_FLAGS | SOFT_PARK_FLAGS):
        lines.append(f"- {flag}: {stats.get('flag_' + flag, 0)}")

    lines.extend([
        "",
        "## Manual rescue review",
        "",
        "These candidates have no recognized hard parking signal. They still require manual provenance review.",
        "",
    ])
    if rescue:
        for item in rescue[:25]:
            lines.append(
                f"- {score_value(item):>3} | "
                f"{item.get('candidate_name', 'Unknown')} | "
                f"{item.get('country_inferred') or '??'} | "
                f"{item.get('stream_host') or 'unknown'} | "
                f"{';'.join(item.get('watchtower_reasons', []))}"
            )
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Busiest parking domains",
        "",
    ])
    if domains:
        for row in domains[:20]:
            lines.append(
                f"- {row['candidate_count']:>3} | {row['stream_host']} | "
                f"hard={row['hard_count']} | rescue={row['rescue_review_count']} | "
                f"max-score={row['max_bondik_score']}"
            )
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Rule",
        "",
        "- keep-parked: raw IP, configured suspicious/restream domain, test-feed path, or unknown parking reason.",
        "- manual-rescue-review: soft parking signal only (currently geo-labelled).",
        "- A rescue-review candidate stays a candidate until official/public provenance is checked manually.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.candidates_json.exists():
        raise SystemExit(f"ERROR: file not found: {args.candidates_json}")

    gate_version, candidates = load_candidates(args.candidates_json)
    parked, hard, rescue, stats = analyze(candidates)
    domains = domain_rows(parked)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.out_dir / "watchtower.json"
    hard_path = args.out_dir / "hard_parking.csv"
    rescue_path = args.out_dir / "rescue_review.csv"
    domains_path = args.out_dir / "parking_domains.csv"
    summary_path = args.out_dir / "watchtower.md"

    json_path.write_text(
        json.dumps(
            {
                "watchtower_version": VERSION,
                "candidate_gate_version": gate_version,
                "stats": stats,
                "parking": parked,
                "hard_parking": hard,
                "rescue_review": rescue,
                "domains": domains,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    write_candidate_csv(hard_path, hard)
    write_candidate_csv(rescue_path, rescue)
    write_domain_csv(domains_path, domains)
    write_summary(
        summary_path,
        gate_version,
        parked,
        hard,
        rescue,
        domains,
        stats,
    )

    print(f"🐱🔭 Koberec Watchtower v{VERSION}")
    print(f"Candidate Gate input: v{gate_version}")
    print(f"Input candidates: {stats.get('input_candidates', 0)}")
    print(f"Parking inspected: {len(parked)}")
    print(f"Keep parked: {len(hard)}")
    print(f"Manual rescue review: {len(rescue)}")
    print(f"Parking domains: {len(domains)}")
    print(f"JSON:   {json_path}")
    print(f"HARD:   {hard_path}")
    print(f"RESCUE: {rescue_path}")
    print(f"DOMAINS:{domains_path}")
    print(f"MD:     {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
