#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import urllib.request
from pathlib import Path


VERSION = "1.0.0"

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

CATEGORY_FAMILY_MAP = {
    # Film-family aliases and genres.
    "movies": "movies",
    "cinema": "movies",
    "film": "movies",
    "action": "movies",
    "comedy": "movies",

    # Music-family aliases and genres.
    "music": "music",
    "concerts": "music",
    "live music": "music",
    "rock": "music",
    "pop": "music",

    # Animation aliases.
    "animation": "animation",
    "cartoon": "animation",

    # Closely related specialist aliases.
    "space": "space",
    "astronomy": "space",
    "wildlife": "wildlife",
    "animals": "wildlife",
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
        "--top-strategy",
        choices=("score", "diverse"),
        default="score",
        help=(
            "TOP selection strategy. "
            "'score' preserves pure ranking; "
            "'diverse' spreads the first pass across categories."
        ),
    )

    parser.add_argument(
        "--diversity-score-gap",
        type=int,
        default=10,
        help=(
            "Maximum score drop allowed when diversity replaces "
            "a pure-score TOP candidate. Default: 10."
        ),
    )

    parser.add_argument(
        "--max-per-category",
        type=int,
        default=2,
        help=(
            "Maximum number of TOP channels from one category family "
            "when using the diverse strategy. "
            "0 disables the cap. Default: 2."
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

    if args.diversity_score_gap < 0:
        parser.error(
            "--diversity-score-gap must be >= 0"
        )

    if args.max_per_category < 0:
        parser.error(
            "--max-per-category must be >= 0"
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

    has_channel = any(
        isinstance(channel, dict)
        and str(
            channel.get("id") or ""
        ).strip()
        for channel in raw
    )

    if not has_channel:
        raise ValueError(
            "iptv-org metadata payload contains "
            "no channel records with an id"
        )


def validate_metadata_file(
    path: Path,
) -> None:
    validate_metadata_payload(
        path.read_bytes()
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

    # Explicit metadata is never modified automatically,
    # but production mode still requires it to be healthy.
    if channel_metadata is not None:
        if not channel_metadata.exists():
            raise FileNotFoundError(
                f"metadata file not found: {channel_metadata}"
            )

        validate_metadata_file(
            channel_metadata
        )

        return channel_metadata, "explicit"

    cache_exists = metadata_cache.exists()
    cache_valid = False
    cache_error: Exception | None = None

    if cache_exists:
        try:
            validate_metadata_file(
                metadata_cache
            )
            cache_valid = True

        except (
            OSError,
            ValueError,
            UnicodeError,
        ) as exc:
            cache_error = exc

    # Healthy automatic cache: normal fast path.
    if cache_valid and not refresh_metadata:
        return metadata_cache, "cache"

    # Corrupt automatic cache:
    # try to replace it immediately with a healthy download.
    if (
        cache_exists
        and not cache_valid
        and not refresh_metadata
    ):
        try:
            download_channel_metadata(
                metadata_cache
            )

            validate_metadata_file(
                metadata_cache
            )

            return (
                metadata_cache,
                "cache-repaired",
            )

        except Exception as exc:
            raise RuntimeError(
                "metadata cache is invalid and "
                "automatic repair failed: "
                f"cache_error={cache_error}; "
                f"repair_error={exc}"
            ) from exc

    # Missing cache or explicitly requested refresh.
    try:
        download_channel_metadata(
            metadata_cache
        )

        # Validate again even though the normal downloader
        # already validates. This also protects tests/custom
        # download implementations.
        validate_metadata_file(
            metadata_cache
        )

        return metadata_cache, "downloaded"

    except Exception as exc:
        # Only a previously verified cache may be used
        # as a network-failure fallback.
        if cache_valid:
            print(
                "WARN: Metadata refresh failed; "
                "using verified existing cache: "
                f"{exc}"
            )

            return (
                metadata_cache,
                "cache-fallback",
            )

        if cache_exists:
            raise RuntimeError(
                "metadata refresh failed and "
                "existing cache is invalid: "
                f"cache_error={cache_error}; "
                f"refresh_error={exc}"
            ) from exc

        raise RuntimeError(
            "metadata download failed and "
            "no valid cache exists: "
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


def write_json(
    path: Path,
    payload: dict,
) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def category_family(category: str) -> str:
    normalized = str(
        category or "unknown"
    ).strip().casefold()

    if not normalized:
        normalized = "unknown"

    return CATEGORY_FAMILY_MAP.get(
        normalized,
        normalized,
    )


def top_category(row: dict) -> str:
    explicit_family = str(
        row.get("bagtop_category_family")
        or ""
    ).strip().casefold()

    if explicit_family:
        return explicit_family

    return category_family(
        row.get("bagtop_category")
        or "unknown"
    )


def category_cap_allows(
    category_counts: dict[str, int],
    category: str,
    max_per_category: int,
) -> bool:
    if max_per_category == 0:
        return True

    return (
        category_counts.get(category, 0)
        < max_per_category
    )


def diversity_thresholds(
    rows: list[dict],
    count: int,
    max_score_gap: int,
) -> tuple[int | None, int | None]:
    if count <= 0 or not rows:
        return None, None

    baseline_count = min(
        count,
        len(rows),
    )

    baseline_cutoff = numeric(
        rows[baseline_count - 1],
        "bagtop_score",
        0,
    )

    return (
        baseline_cutoff,
        baseline_cutoff - max_score_gap,
    )


def trace_diverse_top(
    rows: list[dict],
    count: int,
    max_score_gap: int = 10,
    max_per_category: int = 2,
) -> tuple[
    list[tuple[dict, str]],
    dict[int, dict],
]:
    baseline_cutoff, minimum_diverse_score = (
        diversity_thresholds(
            rows,
            count,
            max_score_gap,
        )
    )

    trace: dict[int, dict] = {}

    for row in rows:
        score = numeric(
            row,
            "bagtop_score",
            0,
        )

        trace[id(row)] = {
            "decision": "skipped-top-limit",
            "rank": "",
            "family": top_category(row),
            "diversity_eligible": (
                minimum_diverse_score is not None
                and score >= minimum_diverse_score
            ),
            "baseline_cutoff": (
                ""
                if baseline_cutoff is None
                else baseline_cutoff
            ),
            "diversity_floor": (
                ""
                if minimum_diverse_score is None
                else minimum_diverse_score
            ),
        }

    if count <= 0 or not rows:
        return [], trace

    remaining = list(rows)
    selected: list[tuple[dict, str]] = []
    selected_ids: set[int] = set()
    category_counts: dict[str, int] = {}

    # Pass 1:
    # One strong representative from each category family.
    for row in remaining:
        score = numeric(
            row,
            "bagtop_score",
            0,
        )

        if (
            minimum_diverse_score is not None
            and score < minimum_diverse_score
        ):
            continue

        category = top_category(row)

        if category_counts.get(category, 0) >= 1:
            continue

        if not category_cap_allows(
            category_counts,
            category,
            max_per_category,
        ):
            trace[id(row)][
                "decision"
            ] = "skipped-category-cap"
            continue

        selected.append(
            (row, "diversity")
        )
        selected_ids.add(id(row))

        category_counts[category] = (
            category_counts.get(category, 0)
            + 1
        )

        trace[id(row)][
            "decision"
        ] = "selected-diversity"

        trace[id(row)][
            "rank"
        ] = len(selected)

        if len(selected) >= count:
            return selected, trace

    # Pass 2:
    # Normal score fill, still respecting family cap.
    for row in remaining:
        if id(row) in selected_ids:
            continue

        category = top_category(row)

        if not category_cap_allows(
            category_counts,
            category,
            max_per_category,
        ):
            trace[id(row)][
                "decision"
            ] = "skipped-category-cap"
            continue

        selected.append(
            (row, "score-fill")
        )
        selected_ids.add(id(row))

        category_counts[category] = (
            category_counts.get(category, 0)
            + 1
        )

        trace[id(row)][
            "decision"
        ] = "selected-score-fill"

        trace[id(row)][
            "rank"
        ] = len(selected)

        if len(selected) >= count:
            break

    return selected, trace


def select_diverse_top_entries(
    rows: list[dict],
    count: int,
    max_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[tuple[dict, str]]:
    selected, _trace = trace_diverse_top(
        rows,
        count,
        max_score_gap,
        max_per_category,
    )

    return selected


def select_diverse_top(
    rows: list[dict],
    count: int,
    max_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[dict]:
    return [
        row
        for row, _reason
        in select_diverse_top_entries(
            rows,
            count,
            max_score_gap,
            max_per_category,
        )
    ]


def select_top_entries(
    rows: list[dict],
    count: int,
    strategy: str,
    diversity_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[tuple[dict, str]]:
    if strategy == "diverse":
        return select_diverse_top_entries(
            rows,
            count,
            diversity_score_gap,
            max_per_category,
        )

    return [
        (row, "score")
        for row in rows[:count]
    ]


def select_top(
    rows: list[dict],
    count: int,
    strategy: str,
    diversity_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[dict]:
    return [
        row
        for row, _reason
        in select_top_entries(
            rows,
            count,
            strategy,
            diversity_score_gap,
            max_per_category,
        )
    ]


def annotated_top_row(
    row: dict,
    rank: int,
    reason: str,
) -> dict:
    annotated = dict(row)

    annotated[
        "bagtop_top_rank"
    ] = rank

    annotated[
        "bagtop_top_reason"
    ] = reason

    annotated[
        "bagtop_top_family"
    ] = top_category(row)

    return annotated


def select_top_with_reasons(
    rows: list[dict],
    count: int,
    strategy: str,
    diversity_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[dict]:
    entries = select_top_entries(
        rows,
        count,
        strategy,
        diversity_score_gap,
        max_per_category,
    )

    return [
        annotated_top_row(
            row,
            rank,
            reason,
        )
        for rank, (row, reason)
        in enumerate(
            entries,
            start=1,
        )
    ]


def build_selection_audit(
    rows: list[dict],
    count: int,
    strategy: str,
    diversity_score_gap: int = 10,
    max_per_category: int = 2,
) -> list[dict]:
    if strategy == "diverse":
        _selected, trace = trace_diverse_top(
            rows,
            count,
            diversity_score_gap,
            max_per_category,
        )
    else:
        trace = {}

        selected_count = min(
            count,
            len(rows),
        )

        for index, row in enumerate(
            rows,
            start=1,
        ):
            selected = (
                index <= selected_count
            )

            trace[id(row)] = {
                "decision": (
                    "selected-score"
                    if selected
                    else "skipped-top-limit"
                ),
                "rank": (
                    index
                    if selected
                    else ""
                ),
                "family": top_category(row),
                "diversity_eligible": "",
                "baseline_cutoff": "",
                "diversity_floor": "",
            }

    audit = []

    for row in rows:
        state = trace[id(row)]
        audited = dict(row)

        audited[
            "bagtop_audit_decision"
        ] = state["decision"]

        audited[
            "bagtop_audit_rank"
        ] = state["rank"]

        audited[
            "bagtop_audit_family"
        ] = state["family"]

        audited[
            "bagtop_diversity_eligible"
        ] = (
            str(
                state[
                    "diversity_eligible"
                ]
            ).lower()
            if isinstance(
                state[
                    "diversity_eligible"
                ],
                bool,
            )
            else ""
        )

        audited[
            "bagtop_baseline_cutoff"
        ] = state[
            "baseline_cutoff"
        ]

        audited[
            "bagtop_diversity_floor"
        ] = state[
            "diversity_floor"
        ]

        audit.append(audited)

    return audit


def build_run_manifest(
    *,
    metadata_mode: str,
    metadata_source: str,
    metadata_records: int,
    top_strategy: str,
    diversity_score_gap: int,
    max_per_category: int,
    input_candidates: int,
    raw_goodies: int,
    unique_goodies: int,
    review_count: int,
    parking_count: int,
    top_requested: int,
    top_selected: int,
) -> dict:
    return {
        "bagtop_version": VERSION,
        "metadata": {
            "mode": metadata_mode,
            "source": metadata_source,
            "records": metadata_records,
        },
        "selection": {
            "strategy": top_strategy,
            "diversity_score_gap": (
                diversity_score_gap
            ),
            "max_per_category_family": (
                max_per_category
            ),
            "top_requested": top_requested,
            "top_selected": top_selected,
        },
        "counts": {
            "input_candidates": input_candidates,
            "raw_goodies": raw_goodies,
            "unique_goodies": unique_goodies,
            "collapsed_alternatives": (
                raw_goodies
                - unique_goodies
            ),
            "review": review_count,
            "parking": parking_count,
        },
    }


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
            "bagtop_category_family"
        ] = category_family(
            category
        )

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

    top = select_top_with_reasons(
        goodies,
        top_count,
        args.top_strategy,
        args.diversity_score_gap,
        args.max_per_category,
    )

    selection_audit = build_selection_audit(
        goodies,
        top_count,
        args.top_strategy,
        args.diversity_score_gap,
        args.max_per_category,
    )

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

    write_csv(
        args.out_dir
        / "bagtop-selection-audit.csv",
        selection_audit,
    )

    manifest = build_run_manifest(
        metadata_mode=metadata_mode,
        metadata_source=metadata_source,
        metadata_records=len(metadata),
        top_strategy=args.top_strategy,
        diversity_score_gap=(
            args.diversity_score_gap
        ),
        max_per_category=(
            args.max_per_category
        ),
        input_candidates=len(rows),
        raw_goodies=len(goodies_raw),
        unique_goodies=len(goodies),
        review_count=len(review),
        parking_count=len(parking),
        top_requested=top_count,
        top_selected=len(top),
    )

    write_json(
        args.out_dir
        / "bagtop-manifest.json",
        manifest,
    )

    summary = [
        f"# Bondik BAGTOP v{VERSION}",
        "",
        f"- Metadata mode: {metadata_mode}",
        f"- Metadata source: {metadata_source}",
        f"- Metadata records: {len(metadata)}",
        f"- TOP strategy: {args.top_strategy}",
        (
            "- Diversity score gap: "
            f"{args.diversity_score_gap}"
        ),
        (
            "- Max per category family: "
            f"{args.max_per_category}"
        ),
        "- Category grouping: family",
        "- TOP selection ledger: enabled",
        "- Full selection audit: enabled",
        "- Run manifest: enabled",
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
    print(
        f"TOP strategy          : {args.top_strategy}"
    )
    print(
        "Diversity score gap   : "
        f"{args.diversity_score_gap}"
    )
    print(
        "Max per family        : "
        + (
            "unlimited"
            if args.max_per_category == 0
            else str(args.max_per_category)
        )
    )
    print(
        "TOP selection ledger  : enabled"
    )
    print(
        "Full selection audit  : enabled"
    )
    print(
        "Run manifest          : enabled"
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
