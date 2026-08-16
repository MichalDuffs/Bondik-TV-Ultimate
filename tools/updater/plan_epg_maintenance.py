#!/usr/bin/env python3
"""Create a report-only plan for improving EPG coverage.

The planner never edits channels.yaml. It downloads configured XMLTV sources,
looks at stable channels whose EPG is disabled, and proposes only exact normalized
matches. Ambiguous or fuzzy cases stay in manual review.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANNELS_FILE = REPO_ROOT / "channels" / "channels.yaml"
EPG_SOURCES_FILE = REPO_ROOT / "epg" / "sources.yaml"

DEFAULT_REPORT = Path("epg-maintenance-report.json")
DEFAULT_SUMMARY = Path("epg-maintenance-summary.md")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
    )
    return parser.parse_args()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_label(value: str) -> str:
    """Normalize a channel label for conservative exact matching."""

    decomposed = unicodedata.normalize(
        "NFKD",
        str(value).casefold(),
    )

    return "".join(
        character
        for character in decomposed
        if character.isalnum()
        and not unicodedata.combining(character)
    )


def extract_xmltv_catalog(
    payload: bytes,
    source_format: str,
) -> list[dict]:
    """Extract XMLTV channel IDs and display names from one feed."""

    if source_format != "xmltv-gzip":
        raise ValueError(
            f"Unsupported EPG format: {source_format}"
        )

    try:
        xml_data = gzip.decompress(payload)
    except (
        gzip.BadGzipFile,
        EOFError,
        OSError,
    ) as exc:
        raise ValueError(
            "Invalid gzip EPG payload"
        ) from exc

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValueError(
            "Invalid XML EPG payload"
        ) from exc

    if local_name(root.tag) != "tv":
        raise ValueError(
            "Invalid XMLTV document: root element must be <tv>"
        )

    catalog: list[dict] = []

    for element in root.iter():
        if local_name(element.tag) != "channel":
            continue

        epg_id = str(
            element.get("id", "")
        ).strip()

        if not epg_id:
            continue

        names = []

        for child in element:
            if local_name(child.tag) != "display-name":
                continue

            name = str(
                child.text or ""
            ).strip()

            if name and name not in names:
                names.append(name)

        catalog.append(
            {
                "id": epg_id,
                "names": names,
            }
        )

    return catalog


def epg_id_alias(
    epg_id: str,
    country: str,
) -> str:
    """Remove only an exact trailing country suffix from an XMLTV ID."""

    parts = str(epg_id).split(".")

    if (
        len(parts) > 1
        and parts[-1].casefold()
        == str(country).casefold()
    ):
        parts = parts[:-1]

    return ".".join(parts)


def find_exact_candidates(
    channel_name: str,
    country: str,
    catalog: list[dict],
) -> list[str]:
    """Return XMLTV IDs that exactly match after conservative normalization."""

    target = normalize_label(
        channel_name
    )

    if not target:
        return []

    candidates: set[str] = set()

    for entry in catalog:
        epg_id = str(
            entry.get("id", "")
        ).strip()

        if not epg_id:
            continue

        aliases = list(
            entry.get("names", [])
        )
        aliases.append(
            epg_id_alias(
                epg_id,
                country,
            )
        )

        if any(
            normalize_label(alias) == target
            for alias in aliases
            if str(alias).strip()
        ):
            candidates.add(epg_id)

    return sorted(candidates)


def source_ids_for_country(
    sources: dict[str, dict],
    country: str,
) -> list[str]:
    return sorted(
        source_id
        for source_id, source in sources.items()
        if str(
            source.get("country", "")
        ).strip().casefold()
        == str(country).strip().casefold()
    )


def choose_source(
    channel: dict,
    sources: dict[str, dict],
) -> tuple[str | None, str | None]:
    """Choose an explicit source first, otherwise the unique country source."""

    country = str(
        channel.get("country", "")
    ).strip()

    epg = channel.get("epg")
    explicit_source = None

    if isinstance(epg, dict):
        raw_source = epg.get("source")

        if raw_source is not None:
            explicit_source = str(
                raw_source
            ).strip() or None

    if explicit_source:
        source = sources.get(
            explicit_source
        )

        if source is None:
            return None, "explicit-source-not-found"

        source_country = str(
            source.get("country", "")
        ).strip()

        if (
            country
            and source_country
            and country.casefold()
            != source_country.casefold()
        ):
            return None, "explicit-source-country-mismatch"

        return explicit_source, None

    matching = source_ids_for_country(
        sources,
        country,
    )

    if not matching:
        return None, "no-country-source"

    if len(matching) > 1:
        return None, "multiple-country-sources"

    return matching[0], None


def is_stable_channel(channel: dict) -> bool:
    """Return True only for channels explicitly marked stable."""

    return (
        str(channel.get("status", ""))
        .strip()
        .casefold()
        == "stable"
    )


def plan_maintenance(
    channels: list,
    sources: dict[str, dict],
    catalogs: dict[str, list[dict]],
    source_errors: dict[str, str] | None = None,
) -> dict:
    """Build a read-only EPG maintenance plan."""

    source_errors = source_errors or {}
    proposals = []
    unresolved = []
    skipped = []
    already_enabled = 0

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        epg = channel.get("epg")

        if (
            isinstance(epg, dict)
            and epg.get("enabled") is True
        ):
            already_enabled += 1
            continue

        channel_id = str(
            channel.get("id", "<unknown>")
        )
        channel_name = str(
            channel.get("name", channel_id)
        )
        country = str(
            channel.get("country", "")
        ).strip()
        status = str(
            channel.get("status", "")
        ).strip()

        base = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "country": country,
        }

        if not is_stable_channel(channel):
            skipped.append(
                {
                    **base,
                    "status": status or None,
                    "reason": "channel-not-stable",
                }
            )
            continue

        source_id, source_reason = choose_source(
            channel,
            sources,
        )

        if source_reason:
            unresolved.append(
                {
                    **base,
                    "reason": source_reason,
                }
            )
            continue

        if source_id in source_errors:
            unresolved.append(
                {
                    **base,
                    "source": source_id,
                    "reason": "source-unavailable",
                }
            )
            continue

        catalog = catalogs.get(
            source_id,
        )

        if catalog is None:
            unresolved.append(
                {
                    **base,
                    "source": source_id,
                    "reason": "source-catalog-missing",
                }
            )
            continue

        candidates = find_exact_candidates(
            channel_name,
            country,
            catalog,
        )

        if len(candidates) == 1:
            proposals.append(
                {
                    **base,
                    "source": source_id,
                    "epg_id": candidates[0],
                    "match": "exact-normalized-name",
                }
            )
            continue

        if len(candidates) > 1:
            unresolved.append(
                {
                    **base,
                    "source": source_id,
                    "reason": "ambiguous-exact-match",
                    "candidates": candidates,
                }
            )
            continue

        unresolved.append(
            {
                **base,
                "source": source_id,
                "reason": "no-exact-match",
            }
        )

    return {
        "mode": "report-only",
        "already_enabled": already_enabled,
        "proposal_count": len(proposals),
        "unresolved_count": len(unresolved),
        "skipped_count": len(skipped),
        "proposals": proposals,
        "unresolved": unresolved,
        "skipped": skipped,
    }


def render_summary(report: dict) -> str:
    lines = [
        "# 🐾 Bondík EPG Maintenance",
        "",
        "**Mode:** report-only — no repository files were changed.",
        "",
        f"- EPG already enabled: {report['already_enabled']}",
        f"- Safe exact proposals: {report['proposal_count']}",
        f"- Skipped non-stable: {report.get('skipped_count', 0)}",
        f"- Manual review: {report['unresolved_count']}",
    ]

    proposals = report.get(
        "proposals",
        [],
    )

    if proposals:
        lines.extend(
            [
                "",
                "## Safe exact proposals",
                "",
            ]
        )

        for item in proposals:
            lines.append(
                "- "
                f"{item['channel_name']} → "
                f"`{item['epg_id']}` "
                f"({item['source']})"
            )

    skipped = report.get(
        "skipped",
        [],
    )

    if skipped:
        lines.extend(
            [
                "",
                "## Skipped non-stable channels",
                "",
            ]
        )

        for item in skipped:
            status = item.get("status") or "missing"
            lines.append(
                "- "
                f"{item['channel_name']}: "
                f"status `{status}`"
            )

    unresolved = report.get(
        "unresolved",
        [],
    )

    if unresolved:
        lines.extend(
            [
                "",
                "## Manual review",
                "",
            ]
        )

        for item in unresolved:
            lines.append(
                "- "
                f"{item['channel_name']}: "
                f"{item['reason']}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_arguments()

    # Import the existing runtime helpers lazily so unit tests for this planner
    # remain pure and network-free.
    from check_epg_sources import (
        download_source,
        load_sources,
        load_yaml,
    )

    try:
        channels_data = load_yaml(
            CHANNELS_FILE
        )
        sources_data = load_yaml(
            EPG_SOURCES_FILE
        )

        channels = channels_data.get(
            "channels",
            [],
        )

        if not isinstance(channels, list):
            raise ValueError(
                "'channels' must be a list"
            )

        sources = load_sources(
            sources_data
        )

    except Exception as exc:
        print(
            f"❌ EPG maintenance configuration error: {exc}"
        )
        return 2

    needed_sources = set()

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        epg = channel.get("epg")

        if (
            isinstance(epg, dict)
            and epg.get("enabled") is True
        ):
            continue

        if not is_stable_channel(channel):
            continue

        source_id, _ = choose_source(
            channel,
            sources,
        )

        if source_id:
            needed_sources.add(
                source_id
            )

    catalogs = {}
    source_errors = {}

    for source_id in sorted(
        needed_sources
    ):
        source = sources[
            source_id
        ]

        try:
            payload = download_source(
                str(source["url"]).strip()
            )
            catalogs[source_id] = (
                extract_xmltv_catalog(
                    payload,
                    str(source["format"]).strip(),
                )
            )

        except Exception as exc:
            source_errors[source_id] = str(
                exc
            )

    report = plan_maintenance(
        channels,
        sources,
        catalogs,
        source_errors,
    )
    report["generated_at"] = (
        datetime.now(timezone.utc)
        .isoformat()
    )
    report["source_errors"] = source_errors

    args.report.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    args.summary.write_text(
        render_summary(report),
        encoding="utf-8",
        newline="\n",
    )

    print(
        render_summary(report),
        end="",
    )

    return 1 if source_errors else 0


if __name__ == "__main__":
    sys.exit(main())
