#!/usr/bin/env python3
"""Bondik TV AUTO-PROMOTION v1.1.

Convert manually approved Hunter/Candidate Gate results into
status=testing channel proposals.

Safety:
- DRY-RUN by default
- only decision=approve candidates are considered
- duplicate stream URLs are rejected
- duplicate channel IDs/names are rejected
- country/category must exist in project config
- custom User-Agent/Referer candidates are skipped for now
- this tool never promotes directly to stable
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


VERSION = "1.1.0"

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CHANNELS = ROOT / "channels" / "channels.yaml"
DEFAULT_CATEGORIES = ROOT / "config" / "categories.yaml"
DEFAULT_COUNTRIES = ROOT / "config" / "countries.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Bondik AUTO-PROMOTION v{VERSION}"
    )

    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="Candidate Gate candidates.json",
    )

    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help="Manual QC decision JSON containing approve/reject decisions",
    )

    parser.add_argument(
        "--channels",
        type=Path,
        default=DEFAULT_CHANNELS,
        help="Central Bondik channel database",
    )

    parser.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
    )

    parser.add_argument(
        "--countries",
        type=Path,
        default=DEFAULT_COUNTRIES,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write approved proposals to channels.yaml as testing",
    )

    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML root: {path}")

    return payload


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON root: {path}")

    return payload


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text)

    return text.strip("-")


def configured_countries(payload: dict[str, Any]) -> set[str]:
    result = set()

    for item in payload.get("countries", []):
        if isinstance(item, dict) and item.get("code"):
            result.add(str(item["code"]).strip().upper())

    return result


def configured_categories(payload: dict[str, Any]) -> set[str]:
    result = set()

    for item in payload.get("categories", []):
        if isinstance(item, dict) and item.get("id"):
            result.add(str(item["id"]).strip())

    return result


def is_web_url(value: str) -> bool:
    value = str(value).strip()

    if not value:
        return False

    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return (
        parsed.scheme.casefold() in {"http", "https"}
        and bool(parsed.netloc)
    )


def approved_decisions(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return manually approved decision records indexed by stream URL."""
    result: dict[str, dict[str, Any]] = {}

    for item in payload.get("candidates", []):
        if not isinstance(item, dict):
            continue

        decision = str(
            item.get("decision", "")
        ).strip().casefold()

        url = str(item.get("url", "")).strip()

        if decision == "approve" and url:
            result[url] = item

    return result


def validate_provenance(
    decision: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize manual provenance evidence."""
    errors: list[str] = []

    raw = decision.get("provenance")

    if not isinstance(raw, dict):
        return {}, ["missing provenance object"]

    verified = raw.get("verified") is True
    website = str(raw.get("website", "")).strip()
    note = str(raw.get("note", "")).strip()

    evidence_raw = raw.get("evidence", [])

    if not verified:
        errors.append("provenance not verified")

    if not is_web_url(website):
        errors.append("missing or invalid provenance website")

    evidence: list[str] = []

    if not isinstance(evidence_raw, list) or not evidence_raw:
        errors.append("missing provenance evidence")
    else:
        for value in evidence_raw:
            url = str(value).strip()

            if not is_web_url(url):
                errors.append(
                    f"invalid provenance evidence URL: {url or 'empty'}"
                )
                continue

            evidence.append(url)

    if not note:
        errors.append("missing provenance note")

    normalized = {
        "verified": verified,
        "website": website,
        "evidence": evidence,
        "note": note,
    }

    return normalized, errors


def existing_data(
    database: dict[str, Any],
) -> tuple[set[str], set[str], set[str]]:
    urls: set[str] = set()
    ids: set[str] = set()
    names: set[str] = set()

    for channel in database.get("channels", []):
        if not isinstance(channel, dict):
            continue

        channel_id = str(channel.get("id", "")).strip()
        name = str(channel.get("name", "")).strip().casefold()

        if channel_id:
            ids.add(channel_id)

        if name:
            names.add(name)

        stream = channel.get("stream")

        if isinstance(stream, dict):
            url = str(stream.get("url", "")).strip()

            if url:
                urls.add(url)

    return urls, ids, names


def language_for_country(country: str) -> str:
    return {
        "CZ": "cs",
        "SK": "sk",
    }.get(country, "und")


def stream_format(candidate: dict[str, Any]) -> str:
    validation = str(candidate.get("validation", "")).casefold()
    url = str(candidate.get("url", "")).casefold()

    if validation.startswith("hls") or ".m3u8" in url:
        return "hls"

    return "http"

def promotion_risks(candidate: dict[str, Any]) -> list[str]:
    """Return conservative reasons why a candidate must not auto-promote."""

    risks: list[str] = []

    url = str(candidate.get("url", "")).strip()

    try:
        parsed = urlparse(url)
    except ValueError:
        return ["invalid-url"]

    host = parsed.hostname or ""
    scheme = parsed.scheme.casefold()
    path = parsed.path.casefold()

    # AUTO-PROMOTION v1 accepts HTTPS only.
    if scheme != "https":
        risks.append("unencrypted-or-non-https-stream")

    # Raw IP streams require manual provenance work.
    try:
        import ipaddress
        ipaddress.ip_address(host)
        risks.append("raw-ip-host")
    except ValueError:
        pass

    # Test feeds must never enter automatic promotion.
    if re.search(r"(?:^|[/_-])test(?:[_/-]|$)", path):
        risks.append("test-feed-path")

    bucket = str(candidate.get("review_bucket", "")).strip().casefold()

    if bucket == "parking":
        risks.append("candidate-parking-bucket")

    review_flags = candidate.get("review_flags", [])

    if isinstance(review_flags, list):
        blocked_flags = {
            "raw-ip-host",
            "suspicious-restream-domain",
            "test-feed-path",
            "geo-labelled",
        }

        for flag in review_flags:
            flag = str(flag).strip()

            if flag in blocked_flags:
                risks.append(flag)

    return list(dict.fromkeys(risks))

def provider_for(candidate: dict[str, Any]) -> str:
    name = str(
        candidate.get("candidate_name")
        or candidate.get("name")
        or "unknown"
    )

    return slugify(name) or "unknown"


def resolve_category(
    candidate: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    return str(
        decision.get("category")
        or candidate.get("category_inferred")
        or ""
    ).strip()


def build_channel(
    candidate: dict[str, Any],
    country: str,
    category: str,
    provenance: dict[str, Any],
    channel_id_override: str = "",
) -> dict[str, Any]:
    name = str(
        candidate.get("candidate_name")
        or candidate.get("name")
        or ""
    ).strip()

    url = str(candidate.get("url", "")).strip()

    channel_id = (
        channel_id_override.strip()
        or f"{slugify(name)}-{country.casefold()}"
    )

    tvg_id = str(candidate.get("tvg_id", "")).strip() or None
    source = str(candidate.get("source", "")).strip()

    host = ""

    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        pass

    notes = (
        "AUTO-PROMOTION v1.1: manually approved candidate "
        "with verified provenance evidence. "
        "Inserted as testing; stable promotion still requires Bondik QC."
    )

    return {
        "id": channel_id,
        "name": name,
        "country": country,
        "language": language_for_country(country),
        "category": category,
        "provider": provider_for(candidate),
        "stream": {
            "url": url,
            "format": stream_format(candidate),
            "quality": "unknown",
        },
        "epg": {
            "id": tvg_id,
            "source": None,
            "enabled": False,
        },
        "logo": {
            "url": None,
            "local": None,
        },
        "status": "testing",
        "metadata": {
            "website": provenance["website"],
            "notes": notes,
            "provenance": {
                "verified": True,
                "evidence": provenance["evidence"],
                "note": provenance["note"],
                "discovery_source": source or None,
                "stream_host": host or None,
            },
        },
    }


def channel_yaml(channel: dict[str, Any]) -> str:
    """Serialize one channel without rewriting the existing database."""
    payload = yaml.safe_dump(
        [channel],
        allow_unicode=True,
        sort_keys=False,
        width=1000,
        default_flow_style=False,
    )

    lines = payload.rstrip().splitlines()

    if not lines:
        return ""

    # PyYAML creates:
    # - id: foo
    #   name: bar
    #
    # Existing channels.yaml uses two-space indentation below "channels:".
    return "\n".join("  " + line for line in lines)


def main() -> int:
    args = parse_args()

    required_files = (
        args.candidates,
        args.decisions,
        args.channels,
        args.categories,
        args.countries,
    )

    for path in required_files:
        if not path.exists():
            raise SystemExit(f"ERROR: file not found: {path}")

    database = load_yaml(args.channels)
    categories_payload = load_yaml(args.categories)
    countries_payload = load_yaml(args.countries)

    candidate_payload = load_json(args.candidates)
    decision_payload = load_json(args.decisions)

    approved = approved_decisions(decision_payload)

    categories = configured_categories(categories_payload)
    countries = configured_countries(countries_payload)

    existing_urls, existing_ids, existing_names = existing_data(database)

    proposals: list[dict[str, Any]] = []
    skipped: list[tuple[str, str]] = []

    candidates = candidate_payload.get("candidates", [])

    if not isinstance(candidates, list):
        raise SystemExit("ERROR: candidates JSON must contain a candidates list")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        url = str(candidate.get("url", "")).strip()

        if url not in approved:
            continue

        name = str(
            candidate.get("candidate_name")
            or candidate.get("name")
            or ""
        ).strip()

        provenance, provenance_errors = validate_provenance(
            approved[url]
        )

        if provenance_errors:
            skipped.append(
                (
                    name or url or "unknown",
                    "provenance: " + ", ".join(provenance_errors),
                )
            )
            continue

        country = str(
            candidate.get("country_inferred") or ""
        ).strip().upper()

        decision = approved[url]

        category = resolve_category(
            candidate,
            decision,
        )

        if not name:
            skipped.append((url or "unknown", "missing name"))
            continue

        if not url:
            skipped.append((name, "missing stream URL"))
            continue

        if not country or country not in countries:
            skipped.append(
                (name, f"invalid country: {country or 'missing'}")
            )
            continue

        if not category or category not in categories:
            skipped.append(
                (name, f"invalid category: {category or 'missing'}")
            )
            continue

        if url in existing_urls:
            skipped.append((name, "stream URL already exists"))
            continue

        risks = promotion_risks(candidate)

        if risks:
            skipped.append(
                (
                    name,
                    "promotion risk: " + ", ".join(risks),
                )
            )
            continue

        user_agent = str(candidate.get("user_agent", "")).strip()
        referer = str(candidate.get("referer", "")).strip()

        if user_agent or referer:
            skipped.append(
                (
                    name,
                    "custom User-Agent/Referer not supported by generator",
                )
            )
            continue

        decision = approved[url]

        channel_id_override = str(
            decision.get("channel_id") or ""
        ).strip()

        channel = build_channel(
            candidate,
            country,
            category,
            provenance,
            channel_id_override,
        )

        channel_id = str(channel["id"])

        if not channel_id or channel_id == f"-{country.casefold()}":
            skipped.append((name, "could not create channel ID"))
            continue

        if channel_id in existing_ids:
            skipped.append(
                (name, f"duplicate id: {channel_id}")
            )
            continue

        if name.casefold() in existing_names:
            skipped.append(
                (name, "channel name already exists")
            )
            continue

        proposals.append(channel)

        existing_urls.add(url)
        existing_ids.add(channel_id)
        existing_names.add(name.casefold())

    print()
    print(f"🐾 Bondik AUTO-PROMOTION v{VERSION}")
    print("=" * 64)
    print(f"Manual approvals : {len(approved)}")
    print(f"Ready for testing: {len(proposals)}")
    print(f"Skipped          : {len(skipped)}")
    print(f"Mode             : {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 64)

    for channel in proposals:
        print(
            f"🧪 {channel['name']} "
            f"({channel['country']} / {channel['category']}) "
            f"-> {channel['id']}"
        )

    if skipped:
        print()
        print("Skipped:")

        for name, reason in skipped:
            print(f"⚠️ {name}: {reason}")

    if not args.apply:
        print()
        print("No files changed.")
        print("Review the proposal, then run again with --apply.")
        return 0

    if not proposals:
        print()
        print("Nothing to apply.")
        return 0

    original = args.channels.read_text(encoding="utf-8").rstrip()

    additions = "\n\n".join(
        channel_yaml(channel)
        for channel in proposals
    )

    args.channels.write_text(
        original + "\n\n" + additions + "\n",
        encoding="utf-8",
    )

    print()
    print(
        f"✅ Added {len(proposals)} channel(s) "
        "with status=testing"
    )
    print(f"📋 Updated: {args.channels}")
    print("🐾 Stable promotion remains under Bondik QC.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
