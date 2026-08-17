#!/usr/bin/env python3
"""Bondik Hunter v0.3 Candidate Gate.

Turn Hunter result JSON files into a review queue without modifying channels.yaml.

Safety / quality rules:
- deep HLS validation is required by default
- URLs already present in channels.yaml are excluded
- possible name collisions are flagged
- third-party index provenance always requires manual review
- unknown country/category is never guessed aggressively
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

VERSION = "0.3"

COUNTRY_SOURCE_RE = re.compile(r"/countries/([a-z]{2})\.m3u(?:$|[?#])", re.IGNORECASE)
CATEGORY_SOURCE_RE = re.compile(r"/categories/([a-z0-9_-]+)\.m3u(?:$|[?#])", re.IGNORECASE)
QUALITY_PAREN_RE = re.compile(
    r"\s*\((?:\d{3,4}p|sd|hd|fhd|uhd|4k)\)\s*",
    re.IGNORECASE,
)
ANNOTATION_RE = re.compile(
    r"\s*\[(?:not\s+24/7|geo-?blocked|geo\s+blocked)\]\s*",
    re.IGNORECASE,
)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

CATEGORY_ALIASES = {
    "sports": "sport",
    "documentaries": "documentary",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Bondik-reviewed candidates from Hunter results."
    )
    parser.add_argument(
        "results",
        nargs="+",
        type=Path,
        help="One or more hunt-results/results.json files.",
    )
    parser.add_argument(
        "--channels",
        type=Path,
        default=Path("channels/channels.yaml"),
        help="Bondik channel database.",
    )
    parser.add_argument(
        "--categories",
        type=Path,
        default=Path("config/categories.yaml"),
        help="Bondik category config.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("hunt-results/candidates"),
    )
    parser.add_argument(
        "--include-http-media",
        action="store_true",
        help="Also admit successful non-HLS HTTP media into manual review.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(
        char for char in decomposed
        if not unicodedata.combining(char)
    )


def clean_display_name(name: str) -> str:
    value = str(name).strip()
    previous = None
    while previous != value:
        previous = value
        value = QUALITY_PAREN_RE.sub(" ", value)
        value = ANNOTATION_RE.sub(" ", value)
        value = re.sub(r"\s+", " ", value).strip()
    return value


def canonical_name(name: str) -> str:
    value = normalize_text(clean_display_name(name))
    return NON_ALNUM_RE.sub("", value)


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_existing_channels(path: Path) -> tuple[set[str], set[str], dict[str, str]]:
    payload = load_yaml(path)
    urls: set[str] = set()
    names: set[str] = set()
    name_to_id: dict[str, str] = {}

    for channel in payload.get("channels", []):
        if not isinstance(channel, dict):
            continue

        stream = channel.get("stream")
        if isinstance(stream, dict):
            url = str(stream.get("url", "")).strip()
            if url:
                urls.add(url)

        name = str(channel.get("name", "")).strip()
        key = canonical_name(name)
        if key:
            names.add(key)
            name_to_id[key] = str(channel.get("id", "")).strip()

    return urls, names, name_to_id


def load_category_ids(path: Path) -> set[str]:
    payload = load_yaml(path)
    result = set()
    for item in payload.get("categories", []):
        if isinstance(item, dict):
            category_id = str(item.get("id", "")).strip().casefold()
            if category_id:
                result.add(category_id)
    return result


def load_results(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        items = payload.get("results", [])
        if not isinstance(items, list):
            raise ValueError(f"{path}: results must be a list")
        for item in items:
            if isinstance(item, dict):
                copied = dict(item)
                copied["_result_file"] = str(path)
                rows.append(copied)
    return rows


def infer_country(source: str) -> str | None:
    match = COUNTRY_SOURCE_RE.search(source)
    return match.group(1).upper() if match else None


def infer_source_category(source: str, category_ids: set[str]) -> str | None:
    match = CATEGORY_SOURCE_RE.search(source)
    if not match:
        return None

    candidate = match.group(1).casefold()
    candidate = CATEGORY_ALIASES.get(candidate, candidate)
    return candidate if candidate in category_ids else None


def infer_group_category(group: str, category_ids: set[str]) -> str | None:
    candidate = normalize_text(group).strip().casefold()
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate).strip("-")
    candidate = CATEGORY_ALIASES.get(candidate, candidate)
    return candidate if candidate in category_ids else None


def choose_category(
    row: dict[str, Any],
    category_ids: set[str],
) -> tuple[str | None, str]:
    source_category = infer_source_category(
        str(row.get("source", "")),
        category_ids,
    )
    group_category = infer_group_category(
        str(row.get("group", "")),
        category_ids,
    )

    if source_category and group_category and source_category != group_category:
        return source_category, "source-category-preferred-group-conflict"
    if source_category:
        return source_category, "source-category"
    if group_category:
        return group_category, "group-category"
    return None, "unknown"


def candidate_rank(row: dict[str, Any]) -> tuple:
    validation = str(row.get("validation", ""))
    validation_rank = 0 if validation == "hls-segment" else 1
    response = row.get("response_ms")
    try:
        response_rank = int(response)
    except (TypeError, ValueError):
        response_rank = 10**9
    return validation_rank, response_rank, str(row.get("url", ""))


def build_candidates(
    rows: list[dict[str, Any]],
    *,
    existing_urls: set[str],
    existing_names: set[str],
    existing_name_to_id: dict[str, str],
    category_ids: set[str],
    include_http_media: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    eligible: list[dict[str, Any]] = []
    stats = Counter()

    for row in rows:
        stats["input_rows"] += 1

        if row.get("ok") is not True:
            stats["skip_not_working"] += 1
            continue

        validation = str(row.get("validation", "")).strip()
        if validation != "hls-segment":
            if not (include_http_media and validation == "http-media"):
                stats["skip_validation"] += 1
                continue

        url = str(row.get("url", "")).strip()
        if not url:
            stats["skip_missing_url"] += 1
            continue

        if url in existing_urls:
            stats["skip_existing_url"] += 1
            continue

        item = dict(row)
        raw_name = str(row.get("name", "")).strip() or url
        display_name = clean_display_name(raw_name)
        key = canonical_name(raw_name)
        category, category_reason = choose_category(row, category_ids)
        country = infer_country(str(row.get("source", "")))

        flags: list[str] = ["manual-provenance-review"]

        if key in existing_names:
            flags.append("possible-existing-channel-alternative")
        if not country:
            flags.append("country-unknown")
        if not category:
            flags.append("category-unknown")
        if "not 24/7" in raw_name.casefold():
            flags.append("not-24-7")
        if "geo-block" in raw_name.casefold():
            flags.append("geo-labelled")

        item.update(
            {
                "candidate_name": display_name,
                "canonical_name": key,
                "country_inferred": country,
                "category_inferred": category,
                "category_basis": category_reason,
                "existing_channel_id": existing_name_to_id.get(key),
                "review_flags": flags,
            }
        )
        eligible.append(item)

    # Deduplicate identical stream profiles across multiple result files.
    profile_best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in eligible:
        key = (
            str(item.get("url", "")).strip(),
            str(item.get("user_agent", "")).strip(),
            str(item.get("referer", "")).strip(),
        )
        previous = profile_best.get(key)
        if previous is None or candidate_rank(item) < candidate_rank(previous):
            profile_best[key] = item

    candidates = list(profile_best.values())
    stats["skip_duplicate_profile"] += len(eligible) - len(candidates)

    # Flag same logical name pointing at multiple surviving URLs.
    name_counts = Counter(
        item.get("canonical_name")
        for item in candidates
        if item.get("canonical_name")
    )
    for item in candidates:
        key = item.get("canonical_name")
        if key and name_counts[key] > 1:
            flags = list(item.get("review_flags", []))
            flags.append("duplicate-name-multiple-streams")
            item["review_flags"] = flags

    candidates.sort(
        key=lambda item: (
            0 if item.get("country_inferred") in {"CZ", "SK"} else 1,
            str(item.get("country_inferred") or ""),
            str(item.get("category_inferred") or ""),
            str(item.get("candidate_name") or "").casefold(),
            candidate_rank(item),
        )
    )
    stats["candidates"] = len(candidates)
    return candidates, dict(stats)


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return value


def write_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fields = [
        "candidate_name",
        "country_inferred",
        "category_inferred",
        "validation",
        "response_ms",
        "url",
        "group",
        "tvg_id",
        "tvg_name",
        "source",
        "existing_channel_id",
        "review_flags",
        "detail",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in candidates:
            writer.writerow(
                {
                    field: csv_value(item.get(field))
                    for field in fields
                }
            )


def escape_m3u(value: str) -> str:
    return str(value).replace('"', "'").replace("\r", " ").replace("\n", " ")


def write_m3u(path: Path, candidates: list[dict[str, Any]]) -> None:
    lines = [f'#EXTM3U x-bondik-candidate-gate-version="{VERSION}"']

    for item in candidates:
        name = escape_m3u(item.get("candidate_name") or item.get("name") or "Unknown")
        country = item.get("country_inferred") or "??"
        category = item.get("category_inferred") or "review"
        group = f"Candidates | {country} | {category}"

        attrs = [f'group-title="{escape_m3u(group)}"']
        if item.get("tvg_id"):
            attrs.append(f'tvg-id="{escape_m3u(item["tvg_id"])}"')
        if item.get("tvg_name"):
            attrs.append(f'tvg-name="{escape_m3u(item["tvg_name"])}"')

        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
        if item.get("user_agent"):
            lines.append(f'#EXTVLCOPT:http-user-agent={item["user_agent"]}')
        if item.get("referer"):
            lines.append(f'#EXTVLCOPT:http-referrer={item["referer"]}')
        lines.append(str(item["url"]))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(
    path: Path,
    candidates: list[dict[str, Any]],
    stats: dict[str, int],
) -> None:
    flags = Counter()
    countries = Counter()
    categories = Counter()

    for item in candidates:
        countries[item.get("country_inferred") or "unknown"] += 1
        categories[item.get("category_inferred") or "unknown"] += 1
        flags.update(item.get("review_flags", []))

    lines = [
        "# 🐾 Bondík Hunter Candidate Gate",
        "",
        f"Version: {VERSION}",
        "",
        "This is a review queue. Nothing was added to channels.yaml.",
        "",
        f"- Input rows: {stats.get('input_rows', 0)}",
        f"- Candidates: {stats.get('candidates', 0)}",
        f"- Skipped already in channels.yaml: {stats.get('skip_existing_url', 0)}",
        f"- Skipped failed streams: {stats.get('skip_not_working', 0)}",
        f"- Skipped insufficient validation: {stats.get('skip_validation', 0)}",
        f"- Duplicate profiles collapsed: {stats.get('skip_duplicate_profile', 0)}",
        "",
        "## Countries",
        "",
    ]
    for key, value in sorted(countries.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Categories", ""])
    for key, value in sorted(categories.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Review flags", ""])
    for key, value in sorted(flags.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## Rule",
            "",
            "A working stream is only a candidate. Before promotion to stable, "
            "verify that its origin is official/public and fill in the Bondík "
            "channel metadata deliberately.",
            "",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    for path in [*args.results, args.channels, args.categories]:
        if not path.exists():
            raise SystemExit(f"ERROR: file not found: {path}")

    rows = load_results(args.results)
    existing_urls, existing_names, existing_name_to_id = load_existing_channels(
        args.channels
    )
    category_ids = load_category_ids(args.categories)

    candidates, stats = build_candidates(
        rows,
        existing_urls=existing_urls,
        existing_names=existing_names,
        existing_name_to_id=existing_name_to_id,
        category_ids=category_ids,
        include_http_media=args.include_http_media,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.out_dir / "candidates.json"
    csv_path = args.out_dir / "candidates.csv"
    m3u_path = args.out_dir / "candidates.m3u"
    summary_path = args.out_dir / "summary.md"

    json_path.write_text(
        json.dumps(
            {
                "candidate_gate_version": VERSION,
                "stats": stats,
                "candidates": candidates,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    write_csv(csv_path, candidates)
    write_m3u(m3u_path, candidates)
    write_summary(summary_path, candidates, stats)

    print(f"🐾 Bondik Hunter Candidate Gate v{VERSION}")
    print(f"Input rows: {stats.get('input_rows', 0)}")
    print(f"Candidates: {len(candidates)}")
    print(f"Already in Bondik: {stats.get('skip_existing_url', 0)}")
    print(f"Failed streams skipped: {stats.get('skip_not_working', 0)}")
    print(f"Insufficient validation skipped: {stats.get('skip_validation', 0)}")
    print(f"Duplicate profiles collapsed: {stats.get('skip_duplicate_profile', 0)}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print(f"M3U:  {m3u_path}")
    print(f"MD:   {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
