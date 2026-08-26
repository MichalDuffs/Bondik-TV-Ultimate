#!/usr/bin/env python3
"""Export Bondik TV channels.yaml to the Ultimate Search JSON catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = ROOT / "channels" / "channels.yaml"
DEFAULT_OUTPUT = ROOT / "web" / "public" / "data" / "channels.json"

CATALOG_SCHEMA_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Bondik TV channel data for Ultimate Search."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Source channels.yaml.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination channels.json.",
    )
    return parser.parse_args()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def normalize_channel(channel: dict[str, Any]) -> dict[str, Any]:
    stream = as_dict(channel.get("stream"))
    epg = as_dict(channel.get("epg"))
    logo = as_dict(channel.get("logo"))
    metadata = as_dict(channel.get("metadata"))

    channel_id = as_text(channel.get("id"))
    name = as_text(channel.get("name"))
    stream_url = as_text(stream.get("url"))

    if not channel_id:
        raise ValueError("Channel is missing id")
    if not name:
        raise ValueError(f"{channel_id}: channel is missing name")
    if not stream_url:
        raise ValueError(f"{channel_id}: channel is missing stream.url")

    return {
        "id": channel_id,
        "name": name,
        "country": as_text(channel.get("country"), "unknown").upper(),
        "language": as_text(channel.get("language"), "unknown"),
        "category": as_text(channel.get("category"), "unknown").casefold(),
        "provider": as_text(channel.get("provider"), "unknown"),
        "status": as_text(channel.get("status"), "unknown").casefold(),
        "stream": {
            "url": stream_url,
            "format": as_text(stream.get("format"), "unknown").casefold(),
            "quality": as_text(stream.get("quality"), "unknown"),
        },
        "epg": {
            "id": as_text(epg.get("id")) or None,
            "source": as_text(epg.get("source")) or None,
            "enabled": bool(epg.get("enabled", False)),
        },
        "logo": {
            "url": as_text(logo.get("url")) or None,
            "local": as_text(logo.get("local")) or None,
        },
        "metadata": {
            "website": as_text(metadata.get("website")) or None,
            "notes": as_text(metadata.get("notes")) or None,
        },
    }


def build_catalog(source: Path) -> dict[str, Any]:
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("channels.yaml root must be a mapping")

    source_channels = payload.get("channels")

    if not isinstance(source_channels, list):
        raise ValueError("channels.yaml must contain a channels list")

    channels: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for raw_channel in source_channels:
        if not isinstance(raw_channel, dict):
            raise ValueError("Each channel entry must be a mapping")

        channel = normalize_channel(raw_channel)
        channel_id = channel["id"]

        if channel_id in seen_ids:
            raise ValueError(f"Duplicate channel id: {channel_id}")

        seen_ids.add(channel_id)
        channels.append(channel)

    countries = sorted(
        {
            channel["country"]
            for channel in channels
            if channel["country"] != "unknown"
        }
    )

    categories = sorted(
        {
            channel["category"]
            for channel in channels
            if channel["category"] != "unknown"
        }
    )

    statuses = sorted(
        {
            channel["status"]
            for channel in channels
            if channel["status"] != "unknown"
        }
    )

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source_version": payload.get("version"),
        "channel_count": len(channels),
        "countries": countries,
        "categories": categories,
        "statuses": statuses,
        "channels": channels,
    }


def main() -> int:
    args = parse_args()

    source = args.input.resolve()
    output = args.output.resolve()

    catalog = build_catalog(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            catalog,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("🐾 Bondik TV Ultimate Search Catalog")
    print("=" * 60)
    print(f"Input      : {source}")
    print(f"Channels   : {catalog['channel_count']}")
    print(f"Countries  : {', '.join(catalog['countries'])}")
    print(f"Categories : {', '.join(catalog['categories'])}")
    print(f"Statuses   : {', '.join(catalog['statuses'])}")
    print(f"JSON       : {output}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
