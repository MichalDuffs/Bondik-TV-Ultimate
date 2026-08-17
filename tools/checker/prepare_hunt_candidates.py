#!/usr/bin/env python3
"""Bondik Hunter v0.5.1 Candidate Gate.

Turn Hunter result JSON files into a review queue without modifying channels.yaml.

v0.5.1 tightens v0.5 scoring:
- explainable 0-100 Bondik triage score for ordering manual provenance work
- top.csv with highest-quality priority candidates first
- country aliases such as UK -> GB
- conservative parking for Antik-hosted candidates unless manually reviewed
- score reasons in CSV/JSON/summary; score never means approval

Safety / quality rules:
- deep HLS validation is required by default
- URLs already present in channels.yaml are excluded
- possible name collisions are flagged
- third-party index provenance always requires manual review
- country/category enrichment is conservative and never means approval
- parking is a review aid, not an automatic accusation or rejection
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import re
import unicodedata
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

VERSION = "0.5.1"

COUNTRY_SOURCE_RE = re.compile(r"/countries/([a-z]{2})\.m3u(?:$|[?#])", re.IGNORECASE)
CATEGORY_SOURCE_RE = re.compile(r"/categories/([a-z0-9_-]+)\.m3u(?:$|[?#])", re.IGNORECASE)
TVG_ID_COUNTRY_RE = re.compile(r"\.([a-z]{2})(?:@[^@]+)?$", re.IGNORECASE)
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

COUNTRY_ALIASES = {
    "UK": "GB",
}

# These are deliberately small and conservative. A match means "park for review",
# not "illegal" or "bad". Users can extend the list later if repeated batches justify it.
PARK_DOMAIN_SUFFIXES = {
    "freeott.top",
    "antik.sk",
}

# Generic delivery/CDN domains are not bad, but they reveal less about the
# broadcaster than a first-party hostname. They receive only a small triage
# penalty so direct-looking broadcaster hosts float above opaque CDN URLs.
GENERIC_CDN_SUFFIXES = {
    "akamaized.net",
    "akamaihd.net",
    "cloudfront.net",
    "amagi.tv",
    "wurl.com",
    "streamlock.net",
    "streamhoster.com",
}

PARK_FLAGS = {
    "raw-ip-host",
    "suspicious-restream-domain",
    "test-feed-path",
    "geo-labelled",
}

REVIEW_FLAGS = {
    "country-unknown",
    "country-unconfigured",
    "category-unknown",
    "possible-existing-channel-alternative",
    "duplicate-name-multiple-streams",
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
        "--countries",
        type=Path,
        default=Path("config/countries.yaml"),
        help="Bondik country config used to validate country enrichment.",
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


def load_country_codes(path: Path) -> set[str]:
    payload = load_yaml(path)
    result = set()
    for item in payload.get("countries", []):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip().upper()
        if len(code) == 2 and code.isalpha():
            result.add(code)
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
    """Backward-compatible country inference from /countries/xx.m3u."""
    match = COUNTRY_SOURCE_RE.search(source)
    return normalize_country_code(match.group(1)) if match else None


def normalize_country_code(code: str) -> str:
    value = str(code).strip().upper()
    return COUNTRY_ALIASES.get(value, value)


def infer_country_from_tvg_id(tvg_id: str) -> str | None:
    """Infer a 2-letter suffix from iptv-org style tvg-id values."""
    value = str(tvg_id).strip()
    match = TVG_ID_COUNTRY_RE.search(value)
    return normalize_country_code(match.group(1)) if match else None


def choose_country(
    row: dict[str, Any],
    country_codes: set[str] | None = None,
) -> tuple[str | None, str, bool]:
    """Return (country, basis, configured).

    Source-country playlists win. Category playlists may be enriched from tvg-id.
    An unconfigured tvg-id suffix is still exposed, but explicitly flagged later.
    """
    configured_codes = country_codes or set()

    source_country = infer_country(str(row.get("source", "")))
    if source_country:
        configured = not configured_codes or source_country in configured_codes
        return source_country, "source-country", configured

    tvg_country = infer_country_from_tvg_id(str(row.get("tvg_id", "")))
    if tvg_country:
        configured = not configured_codes or tvg_country in configured_codes
        return tvg_country, "tvg-id-suffix", configured

    return None, "unknown", False


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


def stream_host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").casefold()
    except ValueError:
        return ""


def is_raw_ip(host: str) -> bool:
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def domain_matches(host: str, suffixes: Iterable[str]) -> bool:
    host = host.casefold().rstrip(".")
    for suffix in suffixes:
        suffix = suffix.casefold().lstrip(".")
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def provenance_flags(url: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    host = stream_host(url)

    if is_raw_ip(host):
        flags.append("raw-ip-host")

    if domain_matches(host, PARK_DOMAIN_SUFFIXES):
        flags.append("suspicious-restream-domain")

    try:
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path).casefold()
        if re.search(r"(?:^|[/_-])test(?:[_/-]|$)", path):
            flags.append("test-feed-path")
        if parsed.scheme.casefold() == "http":
            flags.append("unencrypted-http")
    except ValueError:
        pass

    return host, flags


def assign_review_bucket(flags: list[str]) -> str:
    flag_set = set(flags)
    if flag_set & PARK_FLAGS:
        return "parking"
    if flag_set & REVIEW_FLAGS:
        return "review"
    return "priority"




def _name_host_affinity(name: str, host: str) -> bool:
    """Weak first-party signal: a meaningful channel-name token appears in host.

    This is deliberately only a ranking hint, never provenance proof.
    """
    host_key = NON_ALNUM_RE.sub("", normalize_text(host))
    if not host_key:
        return False

    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", normalize_text(name))
        if len(token) >= 4 and token not in {"television", "channel", "network", "international"}
    ]
    return any(token in host_key for token in tokens)


def bondik_score(item: dict[str, Any]) -> tuple[int, list[str]]:
    """Return an explainable triage score. This is NOT provenance approval.

    v0.5.1 intentionally prevents unreviewed candidates from reaching 90-100.
    The upper band is reserved for a future/manual provenance verification flag.
    """
    score = 30
    reasons: list[str] = ["base:30"]
    flags = set(item.get("review_flags", []))

    if item.get("validation") == "hls-segment":
        score += 20
        reasons.append("deep-hls:+20")

    url = str(item.get("url", ""))
    host = stream_host(url)
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.casefold() == "https":
            score += 8
            reasons.append("https:+8")
    except ValueError:
        pass

    country = str(item.get("country_inferred") or "")
    if country and "country-unknown" not in flags and "country-unconfigured" not in flags:
        score += 8
        reasons.append("configured-country:+8")

    if item.get("category_inferred"):
        score += 8
        reasons.append("known-category:+8")

    response = item.get("response_ms")
    try:
        response_ms = int(response)
        if response_ms <= 250:
            score += 8
            reasons.append("response<=250:+8")
        elif response_ms <= 500:
            score += 6
            reasons.append("response<=500:+6")
        elif response_ms <= 1000:
            score += 3
            reasons.append("response<=1000:+3")
        elif response_ms <= 2000:
            score += 1
            reasons.append("response<=2000:+1")
    except (TypeError, ValueError):
        pass

    name = str(item.get("candidate_name") or item.get("name") or "")
    if _name_host_affinity(name, host):
        score += 8
        reasons.append("name-host-affinity:+8")

    if domain_matches(host, GENERIC_CDN_SUFFIXES):
        score -= 3
        reasons.append("generic-cdn:-3")

    penalties = {
        "raw-ip-host": -40,
        "suspicious-restream-domain": -35,
        "test-feed-path": -30,
        "geo-labelled": -25,
        "unencrypted-http": -12,
        "country-unknown": -18,
        "country-unconfigured": -6,
        "category-unknown": -12,
        "possible-existing-channel-alternative": -12,
        "duplicate-name-multiple-streams": -12,
        "not-24-7": -6,
    }
    for flag, delta in penalties.items():
        if flag in flags:
            score += delta
            reasons.append(f"{flag}:{delta}")

    provenance_verified = item.get("provenance_verified") is True
    if provenance_verified:
        score += 10
        reasons.append("provenance-verified:+10")
        cap = 100
    else:
        # Candidate Gate always starts from third-party discovery. Until a human
        # explicitly verifies origin, the score is capped below the elite band.
        cap = 89
        if score > cap:
            reasons.append("unverified-provenance-cap:89")

    return max(0, min(cap, score)), reasons


def build_candidates(
    rows: list[dict[str, Any]],
    *,
    existing_urls: set[str],
    existing_names: set[str],
    existing_name_to_id: dict[str, str],
    category_ids: set[str],
    include_http_media: bool,
    country_codes: set[str] | None = None,
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
        country, country_basis, country_configured = choose_country(row, country_codes)
        host, provenance = provenance_flags(url)

        flags: list[str] = ["manual-provenance-review", *provenance]

        if key in existing_names:
            flags.append("possible-existing-channel-alternative")
        if not country:
            flags.append("country-unknown")
        elif country_codes and not country_configured:
            flags.append("country-unconfigured")
        if not category:
            flags.append("category-unknown")
        if "not 24/7" in raw_name.casefold():
            flags.append("not-24-7")
        if "geo-block" in raw_name.casefold():
            flags.append("geo-labelled")

        # Preserve order but collapse repeated flags.
        flags = list(dict.fromkeys(flags))

        item.update(
            {
                "candidate_name": display_name,
                "canonical_name": key,
                "country_inferred": country,
                "country_basis": country_basis,
                "category_inferred": category,
                "category_basis": category_reason,
                "stream_host": host,
                "existing_channel_id": existing_name_to_id.get(key),
                "review_flags": flags,
                "review_bucket": assign_review_bucket(flags),
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
            item["review_flags"] = list(dict.fromkeys(flags))
            item["review_bucket"] = assign_review_bucket(item["review_flags"])

    for item in candidates:
        score, reasons = bondik_score(item)
        item["bondik_score"] = score
        item["score_reasons"] = reasons

    bucket_rank = {"priority": 0, "review": 1, "parking": 2}
    candidates.sort(
        key=lambda item: (
            bucket_rank.get(str(item.get("review_bucket")), 9),
            -int(item.get("bondik_score", 0)),
            0 if item.get("country_inferred") in {"CZ", "SK"} else 1,
            candidate_rank(item),
            str(item.get("candidate_name") or "").casefold(),
        )
    )

    stats["candidates"] = len(candidates)
    for item in candidates:
        stats[f"bucket_{item.get('review_bucket', 'review')}"] += 1
        if item.get("country_basis") == "tvg-id-suffix":
            stats["country_enriched_tvg_id"] += 1

    return candidates, dict(stats)


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return value


CSV_FIELDS = [
    "review_bucket",
    "bondik_score",
    "score_reasons",
    "candidate_name",
    "country_inferred",
    "country_basis",
    "category_inferred",
    "category_basis",
    "validation",
    "response_ms",
    "stream_host",
    "url",
    "group",
    "tvg_id",
    "tvg_name",
    "source",
    "existing_channel_id",
    "review_flags",
    "detail",
]


def write_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in candidates:
            writer.writerow({field: csv_value(item.get(field)) for field in CSV_FIELDS})


def escape_m3u(value: str) -> str:
    return str(value).replace('"', "'").replace("\r", " ").replace("\n", " ")


def write_m3u(path: Path, candidates: list[dict[str, Any]]) -> None:
    lines = [f'#EXTM3U x-bondik-candidate-gate-version="{VERSION}"']

    for item in candidates:
        name = escape_m3u(item.get("candidate_name") or item.get("name") or "Unknown")
        country = item.get("country_inferred") or "??"
        category = item.get("category_inferred") or "review"
        bucket = item.get("review_bucket") or "review"
        group = f"Candidates | {bucket} | {country} | {category}"

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
    buckets = Counter()
    country_basis = Counter()
    score_bands = Counter()

    for item in candidates:
        countries[item.get("country_inferred") or "unknown"] += 1
        categories[item.get("category_inferred") or "unknown"] += 1
        buckets[item.get("review_bucket") or "review"] += 1
        country_basis[item.get("country_basis") or "unknown"] += 1
        flags.update(item.get("review_flags", []))
        score = int(item.get("bondik_score", 0))
        if score >= 90:
            score_bands["90-100"] += 1
        elif score >= 75:
            score_bands["75-89"] += 1
        elif score >= 50:
            score_bands["50-74"] += 1
        else:
            score_bands["0-49"] += 1

    lines = [
        "# 🐾 Bondík Hunter Candidate Gate",
        "",
        f"Version: {VERSION}",
        "",
        "This is a review queue. Nothing was added to channels.yaml.",
        "",
        f"- Input rows: {stats.get('input_rows', 0)}",
        f"- Candidates: {stats.get('candidates', 0)}",
        f"- Priority: {buckets.get('priority', 0)}",
        f"- Review: {buckets.get('review', 0)}",
        f"- Parking: {buckets.get('parking', 0)}",
        f"- Country enriched from tvg-id: {stats.get('country_enriched_tvg_id', 0)}",
        f"- Skipped already in channels.yaml: {stats.get('skip_existing_url', 0)}",
        f"- Skipped failed streams: {stats.get('skip_not_working', 0)}",
        f"- Skipped insufficient validation: {stats.get('skip_validation', 0)}",
        f"- Duplicate profiles collapsed: {stats.get('skip_duplicate_profile', 0)}",
        "",
        "## Review buckets",
        "",
    ]
    for key in ["priority", "review", "parking"]:
        lines.append(f"- {key}: {buckets.get(key, 0)}")

    lines.extend(["", "## Bondik score bands", ""])
    for key in ["90-100", "75-89", "50-74", "0-49"]:
        lines.append(f"- {key}: {score_bands.get(key, 0)}")

    lines.extend(["", "## Top priority", ""])
    top_priority = [item for item in candidates if item.get("review_bucket") == "priority"][:20]
    if top_priority:
        for item in top_priority:
            lines.append(
                f"- {item.get('bondik_score', 0):>3} | "
                f"{item.get('candidate_name', 'Unknown')} | "
                f"{item.get('country_inferred') or '??'} | "
                f"{item.get('category_inferred') or 'review'}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Country inference", ""])
    for key, value in sorted(country_basis.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Countries", ""])
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
            "## Bucket meaning",
            "",
            "- priority: cleaner candidate for manual provenance verification; NOT approved automatically.",
            "- review: incomplete metadata or ambiguity needs attention.",
            "- parking: provenance-risk signal such as raw IP, test feed, geo label or configured restream-domain pattern.",
            "- Bondik score: technical triage ordering only; it is never proof of rights, legality or official provenance.",
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

    for path in [*args.results, args.channels, args.categories, args.countries]:
        if not path.exists():
            raise SystemExit(f"ERROR: file not found: {path}")

    rows = load_results(args.results)
    existing_urls, existing_names, existing_name_to_id = load_existing_channels(
        args.channels
    )
    category_ids = load_category_ids(args.categories)
    country_codes = load_country_codes(args.countries)

    candidates, stats = build_candidates(
        rows,
        existing_urls=existing_urls,
        existing_names=existing_names,
        existing_name_to_id=existing_name_to_id,
        category_ids=category_ids,
        include_http_media=args.include_http_media,
        country_codes=country_codes,
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

    bucket_paths: dict[str, Path] = {}
    for bucket in ["priority", "review", "parking"]:
        bucket_path = args.out_dir / f"{bucket}.csv"
        write_csv(
            bucket_path,
            [item for item in candidates if item.get("review_bucket") == bucket],
        )
        bucket_paths[bucket] = bucket_path

    top_path = args.out_dir / "top.csv"
    write_csv(
        top_path,
        [item for item in candidates if item.get("review_bucket") == "priority"],
    )

    print(f"🐾 Bondik Hunter Candidate Gate v{VERSION}")
    print(f"Input rows: {stats.get('input_rows', 0)}")
    print(f"Candidates: {len(candidates)}")
    print(f"Priority: {stats.get('bucket_priority', 0)}")
    print(f"Review: {stats.get('bucket_review', 0)}")
    print(f"Parking: {stats.get('bucket_parking', 0)}")
    print(f"Country enriched from tvg-id: {stats.get('country_enriched_tvg_id', 0)}")
    print(f"Already in Bondik: {stats.get('skip_existing_url', 0)}")
    print(f"Failed streams skipped: {stats.get('skip_not_working', 0)}")
    print(f"Insufficient validation skipped: {stats.get('skip_validation', 0)}")
    print(f"Duplicate profiles collapsed: {stats.get('skip_duplicate_profile', 0)}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print(f"M3U:  {m3u_path}")
    print(f"MD:   {summary_path}")
    print(f"PRI:  {bucket_paths['priority']}")
    print(f"REV:  {bucket_paths['review']}")
    print(f"PARK: {bucket_paths['parking']}")
    print(f"TOP:  {top_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
