#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import urllib.request
from pathlib import Path


VERSION = "0.4.0"

METADATA_URL = "https://iptv-org.github.io/api/channels.json"

DEFAULT_METADATA_CACHE = Path(
    "hunt-results/metadata/iptv-org-channels.json"
)

METADATA_TIMEOUT_SECONDS = 20

GOODIES = {
    "movies",
    "cinema",
    "film",
    "action",
    "comedy",
    "animation",
    "cartoon",
    "kids",
    "music",
    "concerts",
    "live music",
    "rock",
    "pop",
    "documentary",
    "history",
    "science",
    "technology",
    "space",
    "astronomy",
    "wildlife",
    "animals",
    "pets",
    "food",
    "hobby",
    "gardening",
}

PARKING = {
    "religion",
    "religious",
    "finance",
    "business",
    "economics",
    "shopping",
}


# Exact identity overrides beat fuzzy name/category inference.
# Keep this deliberately conservative: one known tvg-id = one reviewed rule.
TVG_CATEGORY_OVERRIDES = {
    "tinypop.uk": "kids",
    "pop.uk": "kids",
    "hobbymaker.uk": "shopping",
}


# iptv-org metadata categories mapped into BAGTOP's deliberately
# narrow content model. Categories not listed here stay in REVIEW.
METADATA_CATEGORY_MAP = {
    "movies": "movies",
    "music": "music",
    "kids": "kids",
    "animation": "animation",
    "documentary": "documentary",
    "science": "science",
    "cooking": "food",

    "shop": "shopping",
    "religious": "religion",
    "business": "business",
}

# Parking categories win over GOODIES if metadata ever contains both.
METADATA_CATEGORY_PRIORITY = (
    "shop",
    "religious",
    "business",
    "movies",
    "music",
    "kids",
    "animation",
    "documentary",
    "science",
    "cooking",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"Bondik BAGTOP v{VERSION}"
    )

    parser.add_argument(
        "--candidates",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help=(
            "Optional maximum number of TOP GOODIES. "
            "0 means use the full top one-third."
        ),
    )

    parser.add_argument(
        "--channel-metadata",
        type=Path,
        help=(
            "Explicit channels.json metadata file. "
            "When supplied, automatic metadata cache handling is disabled."
        ),
    )

    parser.add_argument(
        "--metadata-cache",
        type=Path,
        default=DEFAULT_METADATA_CACHE,
        help=(
            "Automatic iptv-org metadata cache path. "
            f"Default: {DEFAULT_METADATA_CACHE}"
        ),
    )

    parser.add_argument(
        "--refresh-metadata",
        action="store_true",
        help=(
            "Refresh the automatic metadata cache from iptv-org. "
            "If refresh fails and a cache already exists, use the cache."
        ),
    )

    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help=(
            "Disable metadata completely and use only local "
            "category inference."
        ),
    )

    args = parser.parse_args()

    if args.no_metadata and args.channel_metadata is not None:
        parser.error(
            "--no-metadata cannot be combined with --channel-metadata"
        )

    if args.no_metadata and args.refresh_metadata:
        parser.error(
            "--no-metadata cannot be combined with --refresh-metadata"
        )

    if args.channel_metadata is not None and args.refresh_metadata:
        parser.error(
            "--channel-metadata cannot be combined with --refresh-metadata"
        )

    return args


def validate_metadata_payload(data: bytes) -> None:
    raw = json.loads(
        data.decode("utf-8-sig")
    )

    if not isinstance(raw, list):
        raise ValueError(
            "iptv-org metadata payload must be a JSON array"
        )

    if not raw:
        raise ValueError(
            "iptv-org metadata payload is empty"
        )


def download_channel_metadata(
    cache_path: Path,
) -> None:
    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = cache_path.with_name(
        cache_path.name + ".tmp"
    )

    request = urllib.request.Request(
        METADATA_URL,
        headers={
            "User-Agent": (
                f"Bondik-BAGTOP/{VERSION}"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=METADATA_TIMEOUT_SECONDS,
        ) as response:
            data = response.read()

        validate_metadata_payload(data)

        temporary_path.write_bytes(data)
        temporary_path.replace(cache_path)

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()

        raise


def resolve_metadata_source(
    channel_metadata: Path | None,
    metadata_cache: Path,
    refresh_metadata: bool,
    no_metadata: bool,
) -> tuple[Path | None, str]:
    if no_metadata:
        return None, "disabled"

    if channel_metadata is not None:
        if not channel_metadata.exists():
            raise FileNotFoundError(
                f"metadata file not found: {channel_metadata}"
            )

        return channel_metadata, "explicit"

    cache_exists = metadata_cache.exists()

    if cache_exists and not refresh_metadata:
        return metadata_cache, "cache"

    try:
        download_channel_metadata(
            metadata_cache
        )

        return metadata_cache, "downloaded"

    except Exception as exc:
        if cache_exists:
            print(
                "?? Metadata refresh failed; "
                "using existing cache: "
                f"{exc}"
            )

            return metadata_cache, "cache-fallback"

        raise RuntimeError(
            "metadata download failed and no cache exists: "
            f"{exc}"
        ) from exc


def load_channel_metadata(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}

    with path.open(
        encoding="utf-8-sig",
    ) as handle:
        raw = json.load(handle)

    metadata: dict[str, dict] = {}

    for channel in raw:
        if not isinstance(channel, dict):
            continue

        channel_id = normalized_tvg_id(
            channel.get("id") or ""
        )

        if channel_id:
            metadata[channel_id] = channel

    return metadata


def metadata_for_row(
    row: dict,
    metadata: dict[str, dict],
) -> dict | None:
    tvg_id = normalized_tvg_id(
        row.get("tvg_id") or ""
    )

    if not tvg_id:
        return None

    return metadata.get(tvg_id)


def metadata_categories(entry: dict | None) -> list[str]:
    if not entry:
        return []

    values = entry.get("categories") or []

    if isinstance(values, str):
        values = [values]

    return [
        str(value).strip().casefold()
        for value in values
        if str(value).strip()
    ]


def category_from_metadata(
    row: dict,
    metadata: dict[str, dict],
) -> str:
    entry = metadata_for_row(
        row,
        metadata,
    )

    categories = metadata_categories(entry)

    for source_category in METADATA_CATEGORY_PRIORITY:
        if source_category in categories:
            return METADATA_CATEGORY_MAP[source_category]

    return ""


def detect_category(
    row: dict,
    metadata: dict[str, dict] | None = None,
) -> str:
    tvg_id = normalized_tvg_id(
        row.get("tvg_id") or ""
    )

    override = TVG_CATEGORY_OVERRIDES.get(tvg_id)

    if override:
        return override

    metadata_category = category_from_metadata(
        row,
        metadata or {},
    )

    if metadata_category:
        return metadata_category

    category = str(
        row.get("category_inferred") or ""
    ).strip().casefold()

    if category and category not in {
        "unknown",
        "none",
        "null",
    }:
        return category

    text = " ".join(
        str(row.get(field) or "")
        for field in (
            "candidate_name",
            "tvg_id",
            "tvg_name",
            "group",
        )
    ).casefold()

    aliases = {
        "movie": "movies",
        "movies": "movies",
        "cinema": "cinema",
        "film": "film",
        "animation": "animation",
        "animated": "animation",
        "cartoon": "cartoon",
        "kids": "kids",
        "children": "kids",
        "music": "music",
        "concert": "concerts",
        "concerts": "concerts",
        "rock": "rock",
        "pop": "pop",
        "documentary": "documentary",
        "history": "history",
        "science": "science",
        "technology": "technology",
        "tech": "technology",
        "space": "space",
        "astronomy": "astronomy",
        "wildlife": "wildlife",
        "animals": "animals",
        "animal": "animals",
        "pets": "pets",
        "pet": "pets",
        "food": "food",
        "cooking": "food",
        "hobby": "hobby",
        "gardening": "gardening",
        "garden": "gardening",
        "religion": "religion",
        "religious": "religious",
        "faith": "religion",
        "finance": "finance",
        "financial": "finance",
        "business": "business",
        "economy": "economics",
        "economic": "economics",
        "shopping": "shopping",
    }

    # High-confidence compound/name patterns.
    # Word-boundary matching below intentionally stays conservative,
    # but names such as Totalmusic or Musical would otherwise be missed.
    compound_aliases = {
        "totalmusic": "music",
        "musical": "music",
        "livemusic": "music",
    }

    compact_text = re.sub(r"[^a-z0-9]+", "", text)

    for keyword, normalized in compound_aliases.items():
        if keyword in compact_text:
            return normalized

    for keyword, normalized in aliases.items():
        if re.search(
            rf"\b{re.escape(keyword)}\b",
            text,
        ):
            return normalized

    return "unknown"


def flag(row: dict, value: str) -> bool:
    flags = str(
        row.get("review_flags") or ""
    ).casefold()

    return value.casefold() in flags


def numeric(
    row: dict,
    field: str,
    default: int = 999999,
) -> int:
    try:
        return int(row.get(field) or default)
    except (TypeError, ValueError):
        return default


def classify(
    row: dict,
    category: str,
    metadata_entry: dict | None = None,
) -> str:
    if metadata_entry and metadata_entry.get("is_nsfw") is True:
        return "parking"

    if flag(row, "suspicious-restream-domain"):
        return "parking"

    if flag(row, "test-feed-path"):
        return "parking"

    if flag(row, "unencrypted-http"):
        return "parking"

    if category in PARKING:
        return "parking"

    if category in GOODIES:
        return "goodies"

    return "review"


def bagtop_score(row: dict, category: str) -> int:
    score = numeric(
        row,
        "bondik_score",
        0,
    )

    country = str(
        row.get("country_inferred") or ""
    ).upper()

    if country in {"CZ", "SK"}:
        score += 15

    if category in GOODIES:
        score += 15

    if category in PARKING:
        score -= 30

    if category == "unknown":
        score -= 5

    if str(
        row.get("validation") or ""
    ) == "hls-segment":
        score += 5

    response = numeric(
        row,
        "response_ms",
    )

    if response <= 300:
        score += 8
    elif response <= 500:
        score += 5
    elif response <= 1000:
        score += 2

    return score


def normalized_name(value: str) -> str:
    value = str(value or "").casefold()
    return "".join(
        char
        for char in value
        if char.isalnum()
    )


def normalized_tvg_id(value: str) -> str:
    value = str(value or "").strip().casefold()

    if not value:
        return ""

    # Quality/region suffix after @ should not make
    # identical channels separate identities.
    return value.split("@", 1)[0]


def identity_key(row: dict) -> str:
    tvg_id = normalized_tvg_id(
        row.get("tvg_id") or ""
    )

    if tvg_id:
        return f"tvg:{tvg_id}"

    return (
        "name:"
        + normalized_name(
            row.get("candidate_name") or ""
        )
    )


def variant_rank(row: dict):
    validation = str(
        row.get("validation") or ""
    )

    url = str(
        row.get("url") or ""
    )

    return (
        0 if validation == "hls-segment" else 1,
        0 if url.startswith("https://") else 1,
        1 if flag(
            row,
            "suspicious-restream-domain",
        ) else 0,
        1 if flag(
            row,
            "test-feed-path",
        ) else 0,
        -numeric(
            row,
            "bagtop_score",
            0,
        ),
        numeric(
            row,
            "response_ms",
        ),
    )


def cluster_goodies(rows: list[dict]):
    clusters: dict[str, list[dict]] = {}

    for row in rows:
        key = identity_key(row)
        clusters.setdefault(
            key,
            [],
        ).append(row)

    winners = []
    cluster_rows = []

    for key, variants in clusters.items():
        ordered = sorted(
            variants,
            key=variant_rank,
        )

        winner = dict(ordered[0])
        winner["bagtop_identity"] = key
        winner["bagtop_variants"] = len(ordered)

        winners.append(winner)

        for index, variant in enumerate(
            ordered,
            1,
        ):
            cluster_row = dict(variant)
            cluster_row["bagtop_identity"] = key
            cluster_row["bagtop_variants"] = len(
                ordered
            )
            cluster_row[
                "bagtop_variant_rank"
            ] = index
            cluster_row[
                "bagtop_selected"
            ] = (
                "yes"
                if index == 1
                else "no"
            )

            cluster_rows.append(
                cluster_row
            )

    return winners, cluster_rows


def write_csv(
    path: Path,
    rows: list[dict],
):
    if not rows:
        path.write_text(
            "",
            encoding="utf-8",
        )
        return

    fields = []

    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def output_sort_key(row: dict):
    return (
        -numeric(
            row,
            "bagtop_score",
            0,
        ),
        numeric(
            row,
            "response_ms",
        ),
        str(
            row.get("candidate_name") or ""
        ).casefold(),
    )


def main():
    args = parse_args()

    args.out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.candidates.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    try:
        metadata_path, metadata_mode = resolve_metadata_source(
            channel_metadata=args.channel_metadata,
            metadata_cache=args.metadata_cache,
            refresh_metadata=args.refresh_metadata,
            no_metadata=args.no_metadata,
        )

        metadata = load_channel_metadata(
            metadata_path
        )

    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(
            f"BAGTOP metadata error: {exc}"
        ) from exc

    metadata_source = (
        str(metadata_path)
        if metadata_path is not None
        else "-"
    )

    goodies_raw = []
    review = []
    parking = []

    for row in rows:
        metadata_entry = metadata_for_row(
            row,
            metadata,
        )

        category = detect_category(
            row,
            metadata,
        )

        bucket = classify(
            row,
            category,
            metadata_entry,
        )

        enriched = dict(row)

        enriched[
            "bagtop_category"
        ] = category

        enriched[
            "bagtop_metadata_categories"
        ] = ";".join(
            metadata_categories(
                metadata_entry
            )
        )

        enriched[
            "bagtop_metadata_nsfw"
        ] = (
            str(
                bool(
                    metadata_entry
                    and metadata_entry.get("is_nsfw") is True
                )
            ).lower()
        )

        enriched[
            "bagtop_score"
        ] = bagtop_score(
            row,
            category,
        )

        enriched[
            "bagtop_bucket"
        ] = bucket

        if bucket == "goodies":
            goodies_raw.append(
                enriched
            )
        elif bucket == "review":
            review.append(
                enriched
            )
        else:
            parking.append(
                enriched
            )

    goodies, clusters = cluster_goodies(
        goodies_raw
    )

    goodies.sort(
        key=output_sort_key
    )
    review.sort(
        key=output_sort_key
    )
    parking.sort(
        key=output_sort_key
    )

    # TOP is calculated only after identity clustering.
    top_count = (
        math.ceil(
            len(goodies) / 3
        )
        if goodies
        else 0
    )

    if args.top > 0:
        top_count = min(
            top_count,
            args.top,
        )

    top = goodies[:top_count]

    write_csv(
        args.out_dir
        / "bagtop-goodies.csv",
        goodies,
    )

    write_csv(
        args.out_dir
        / "bagtop-clusters.csv",
        clusters,
    )

    write_csv(
        args.out_dir
        / "bagtop-review.csv",
        review,
    )

    write_csv(
        args.out_dir
        / "bagtop-parking.csv",
        parking,
    )

    write_csv(
        args.out_dir
        / "bagtop-top.csv",
        top,
    )

    summary = [
        f"# Bondik BAGTOP v{VERSION}",
        "",
        f"- Metadata mode: {metadata_mode}",
        f"- Metadata source: {metadata_source}",
        f"- Metadata records: {len(metadata)}",
        "",
        f"- Input candidates: {len(rows)}",
        f"- Raw GOODIES streams: {len(goodies_raw)}",
        f"- Unique GOODIES channels: {len(goodies)}",
        (
            "- Duplicate/alternate GOODIES streams: "
            f"{len(goodies_raw) - len(goodies)}"
        ),
        f"- REVIEW: {len(review)}",
        f"- PARKING: {len(parking)}",
        f"- TOP 1/3: {len(top)}",
        "",
        "## TOP GOODIES",
        "",
    ]

    for index, row in enumerate(
        top,
        1,
    ):
        summary.append(
            f"{index}. "
            f"{row.get('candidate_name', '')} | "
            f"{row.get('country_inferred', '')} | "
            f"{row.get('bagtop_category', '')} | "
            f"score={row.get('bagtop_score', '')} | "
            f"{row.get('response_ms', '')} ms | "
            f"variants={row.get('bagtop_variants', 1)}"
        )

    (
        args.out_dir
        / "bagtop-summary.md"
    ).write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print()
    print(
        f"🚜🔗 Bondik BAGTOP v{VERSION}"
    )
    print("=" * 68)
    print(
        f"Metadata mode         : {metadata_mode}"
    )
    print(
        f"Metadata records      : {len(metadata)}"
    )
    print(
        f"Metadata source       : {metadata_source}"
    )
    print("-" * 68)
    print(
        f"Input candidates      : {len(rows)}"
    )
    print(
        f"Raw GOODIES streams   : {len(goodies_raw)}"
    )
    print(
        f"Unique GOODIES        : {len(goodies)}"
    )
    print(
        "Alternatives collapsed: "
        f"{len(goodies_raw) - len(goodies)}"
    )
    print(
        f"REVIEW                : {len(review)}"
    )
    print(
        f"PARKING               : {len(parking)}"
    )
    print(
        f"TOP 1/3               : {len(top)}"
    )
    print("=" * 68)

    print()
    print("🟢 TOP 1/3 GOODIES:")

    for index, row in enumerate(
        top,
        1,
    ):
        print(
            f"{index:2}. "
            f"{row.get('candidate_name', '')} | "
            f"{row.get('bagtop_category', '')} | "
            f"{row.get('bagtop_score', '')} | "
            f"{row.get('response_ms', '')} ms | "
            f"{row.get('bagtop_variants', 1)} variant(s)"
        )

    print()
    print(
        f"GOODIES : {args.out_dir}\\bagtop-goodies.csv"
    )
    print(
        f"CLUSTERS: {args.out_dir}\\bagtop-clusters.csv"
    )
    print(
        f"REVIEW  : {args.out_dir}\\bagtop-review.csv"
    )
    print(
        f"PARKING : {args.out_dir}\\bagtop-parking.csv"
    )
    print(
        f"TOP     : {args.out_dir}\\bagtop-top.csv"
    )
    print(
        f"SUMMARY : {args.out_dir}\\bagtop-summary.md"
    )


if __name__ == "__main__":
    main()
