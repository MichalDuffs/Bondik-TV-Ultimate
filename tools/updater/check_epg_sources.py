#!/usr/bin/env python3
"""
Bondik TV Ultimate - EPG Source Checker

Downloads configured XMLTV feeds and verifies that enabled
channel EPG identifiers exist in their assigned source.

Exit codes:
    0 = all EPG sources passed
    1 = one or more EPG sources or mappings failed
    2 = configuration error
"""

from __future__ import annotations

import gzip
import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import truststore
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

CHANNELS_FILE = REPO_ROOT / "channels" / "channels.yaml"
EPG_SOURCES_FILE = REPO_ROOT / "epg" / "sources.yaml"

USER_AGENT = (
    "Bondik-TV-Ultimate/1.0 "
    "(+https://github.com/MichalDuffs/Bondik-TV-Ultimate)"
)

TIMEOUT = 20
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
FRESHNESS_HORIZON_HOURS = 24

SUPPORTED_EPG_FORMATS = {
    "xmltv-gzip",
}

SSL_CONTEXT = truststore.SSLContext(
    ssl.PROTOCOL_TLS_CLIENT
)


def load_yaml(path: Path) -> dict:
    """Load YAML file and require dictionary root."""

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid YAML root in {path}"
        )

    return data


def local_name(tag: str) -> str:
    """Return XML tag name without optional namespace."""

    return tag.rsplit("}", 1)[-1]


def extract_xmltv_channel_ids(
    payload: bytes,
    source_format: str,
) -> set[str]:
    """Extract channel IDs from an XMLTV payload."""

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
            "Invalid XMLTV document: "
            "root element must be <tv>"
        )

    channel_ids: set[str] = set()

    for element in root.iter():
        if local_name(element.tag) != "channel":
            continue

        channel_id = element.get("id")

        if channel_id is None:
            continue

        channel_id = channel_id.strip()

        if channel_id:
            channel_ids.add(channel_id)

    return channel_ids


def parse_xmltv_timestamp(
    value: str,
) -> datetime:
    """Parse a common XMLTV timestamp into datetime."""

    value = str(value).strip()

    formats = (
        "%Y%m%d%H%M%S %z",
        "%Y%m%d%H%M%S%z",
        "%Y%m%d%H%M%S",
    )

    for timestamp_format in formats:
        try:
            parsed = datetime.strptime(
                value,
                timestamp_format,
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            continue

    raise ValueError(
        f"Invalid XMLTV timestamp '{value}'"
    )


def extract_fresh_programme_ids(
    payload: bytes,
    source_format: str,
    now: datetime,
    horizon_hours: int = FRESHNESS_HORIZON_HOURS,
) -> set[str]:
    """Return channel IDs with current or near-future programmes."""

    if source_format != "xmltv-gzip":
        raise ValueError(
            f"Unsupported EPG format: {source_format}"
        )

    if now.tzinfo is None:
        raise ValueError(
            "'now' must be timezone-aware"
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
            "Invalid XMLTV document: "
            "root element must be <tv>"
        )

    horizon = now + timedelta(
        hours=horizon_hours
    )

    fresh_ids: set[str] = set()

    for element in root.iter():
        if local_name(element.tag) != "programme":
            continue

        channel_id = str(
            element.get("channel", "")
        ).strip()

        start_value = element.get("start")
        stop_value = element.get("stop")

        if (
            not channel_id
            or not start_value
            or not stop_value
        ):
            continue

        try:
            start = parse_xmltv_timestamp(
                start_value
            )

            stop = parse_xmltv_timestamp(
                stop_value
            )

        except ValueError:
            continue

        if stop <= start:
            continue

        current_programme = (
            start <= now < stop
        )

        future_programme = (
            now < start <= horizon
        )

        if (
            current_programme
            or future_programme
        ):
            fresh_ids.add(channel_id)

    return fresh_ids


def find_missing_epg_ids(
    required_ids: set[str],
    available_ids: set[str],
) -> set[str]:
    """Return required IDs missing from source."""

    return required_ids - available_ids


def collect_required_epg_ids(
    channels: list,
) -> dict[str, set[str]]:
    """Group enabled EPG IDs by source."""

    required: dict[str, set[str]] = {}

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        epg = channel.get("epg")

        if not isinstance(epg, dict):
            continue

        if epg.get("enabled") is not True:
            continue

        channel_name = str(
            channel.get("name", "<unknown>")
        )

        source = epg.get("source")
        epg_id = epg.get("id")

        if (
            source is None
            or not str(source).strip()
        ):
            raise ValueError(
                f"{channel_name}: "
                "enabled EPG has no source"
            )

        if (
            epg_id is None
            or not str(epg_id).strip()
        ):
            raise ValueError(
                f"{channel_name}: "
                "enabled EPG has no id"
            )

        source = str(source).strip()
        epg_id = str(epg_id).strip()

        required.setdefault(
            source,
            set(),
        ).add(epg_id)

    return required


def load_sources(
    data: dict,
) -> dict[str, dict]:
    """Load EPG source registry."""

    result: dict[str, dict] = {}

    sources = data.get(
        "sources",
        [],
    )

    if not isinstance(sources, list):
        raise ValueError(
            "'sources' must be a list"
        )

    for source in sources:
        if not isinstance(source, dict):
            raise ValueError(
                "Invalid EPG source entry"
            )

        source_id = source.get("id")
        source_url = source.get("url")
        source_format = source.get("format")
        source_country = source.get("country")

        if (
            source_id is None
            or not str(source_id).strip()
        ):
            raise ValueError(
                "EPG source has no id"
            )

        source_id = str(source_id).strip()

        if source_id in result:
            raise ValueError(
                f"Duplicate EPG source '{source_id}'"
            )

        if (
            source_country is None
            or not str(source_country).strip()
        ):
            raise ValueError(
                f"{source_id}: missing country"
            )

        if (
            source_url is None
            or not str(source_url).strip()
        ):
            raise ValueError(
                f"{source_id}: missing URL"
            )

        source_url = str(source_url).strip()

        parsed_url = urlparse(source_url)

        if parsed_url.scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                f"{source_id}: unsupported URL scheme "
                f"'{parsed_url.scheme}'"
            )

        if (
            source_format is None
            or not str(source_format).strip()
        ):
            raise ValueError(
                f"{source_id}: missing format"
            )

        source_format = str(source_format).strip()

        if source_format not in SUPPORTED_EPG_FORMATS:
            raise ValueError(
                f"{source_id}: unsupported format "
                f"'{source_format}'"
            )

        result[source_id] = source

    return result


def validate_epg_source_countries(
    channels: list,
    sources: dict[str, dict],
) -> None:
    """Ensure enabled channel EPG source matches channel country."""

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        epg = channel.get("epg")

        if (
            not isinstance(epg, dict)
            or epg.get("enabled") is not True
        ):
            continue

        channel_name = str(
            channel.get("name", "<unknown>")
        )

        channel_country = channel.get("country")
        source_id = epg.get("source")

        if (
            source_id is None
            or not str(source_id).strip()
        ):
            continue

        source_id = str(source_id).strip()
        source = sources.get(source_id)

        if source is None:
            continue

        source_country = str(
            source.get("country", "")
        ).strip()

        channel_country = str(
            channel_country or ""
        ).strip()

        if (
            channel_country
            and source_country
            and channel_country != source_country
        ):
            raise ValueError(
                f"{channel_name}: EPG source "
                f"'{source_id}' is for {source_country}, "
                f"but channel country is {channel_country}"
            )


def download_source(
    url: str,
) -> bytes:
    """Download an EPG source with size protection."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/xml,"
                "application/gzip,"
                "*/*"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
        context=SSL_CONTEXT,
    ) as response:
        payload = response.read(
            MAX_DOWNLOAD_BYTES + 1
        )

    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError(
            "EPG download exceeds size limit"
        )

    return payload


def main() -> int:
    print()
    print("🐾 Bondik TV Ultimate")
    print("📅 EPG Source Checker")
    print("=" * 60)

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

        required_by_source = (
            collect_required_epg_ids(
                channels
            )
        )

        sources = load_sources(
            sources_data
        )

        validate_epg_source_countries(
            channels,
            sources,
        )

    except (
        FileNotFoundError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        print()
        print(
            f"❌ Configuration error: {exc}"
        )
        return 2

    failed = 0
    passed = 0

    for source_id, required_ids in sorted(
        required_by_source.items()
    ):
        source = sources.get(
            source_id
        )

        print()
        print(
            f"📡 {source_id}"
        )

        if source is None:
            print(
                "   └─ ❌ source not found "
                "in epg/sources.yaml"
            )
            failed += 1
            continue

        url = str(
            source["url"]
        ).strip()

        source_format = str(
            source["format"]
        ).strip()

        try:
            payload = download_source(
                url
            )

            available_ids = (
                extract_xmltv_channel_ids(
                    payload,
                    source_format,
                )
            )

            missing_ids = find_missing_epg_ids(
                required_ids,
                available_ids,
            )

            if missing_ids:
                print(
                    "   └─ ❌ missing "
                    f"{len(missing_ids)} EPG ID(s)"
                )

                for epg_id in sorted(
                    missing_ids
                ):
                    print(
                        f"      • {epg_id}"
                    )

                failed += 1
                continue

            print(
                "   ├─ ✅ "
                f"{len(required_ids)}/"
                f"{len(required_ids)} IDs found"
            )

            print(
                "   │  XMLTV channels: "
                f"{len(available_ids)}"
            )

            now = datetime.now(
                timezone.utc
            )

            fresh_ids = (
                extract_fresh_programme_ids(
                    payload,
                    source_format,
                    now,
                )
            )

            stale_ids = (
                required_ids - fresh_ids
            )

            if stale_ids:
                print(
                    "   └─ ❌ "
                    f"{len(stale_ids)} ID(s) have "
                    "no fresh programme data"
                )

                for epg_id in sorted(
                    stale_ids
                ):
                    print(
                        f"      • {epg_id}"
                    )

                failed += 1
                continue

            print(
                "   └─ ✅ "
                f"{len(required_ids)}/"
                f"{len(required_ids)} IDs have "
                "fresh programme data"
            )

            passed += 1

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            ValueError,
        ) as exc:
            print(
                f"   └─ ❌ {exc}"
            )
            failed += 1

    print()
    print("=" * 60)
    print("🐾 Bondík EPG Quality Report")
    print(f"✅ Sources passed: {passed}")
    print(f"❌ Sources failed: {failed}")
    print(
        "📡 Sources checked: "
        f"{passed + failed}"
    )
    print("=" * 60)

    if failed:
        print(
            "🔴 RESULT: EPG CHECK FAILED"
        )
        return 1

    print(
        "🟢 RESULT: BONDÍK EPG APPROVED 🐾"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
