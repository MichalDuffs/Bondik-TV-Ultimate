#!/usr/bin/env python3
"""
Bondik TV Ultimate - Channel Checker

Validates channel metadata and tests public stream URLs defined in:
    channels/channels.yaml

Exit codes:
    0 = all checked channels passed
    1 = one or more channels failed
    2 = configuration/database error
"""

from __future__ import annotations

import argparse
import socket
import ssl
import sys
import urllib.error
import urllib.request
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml
import truststore


REPO_ROOT = Path(__file__).resolve().parents[2]

CHANNELS_FILE = REPO_ROOT / "channels" / "channels.yaml"
COUNTRIES_FILE = REPO_ROOT / "config" / "countries.yaml"
CATEGORIES_FILE = REPO_ROOT / "config" / "categories.yaml"
QUALITY_FILE = REPO_ROOT / "config" / "quality.yaml"
EPG_SOURCES_FILE = REPO_ROOT / "epg" / "sources.yaml"

USER_AGENT = (
    "Bondik-TV-Ultimate/1.0 "
    "(+https://github.com/MichalDuffs/Bondik-TV-Ultimate)"
)

READ_LIMIT = 64 * 1024
SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def load_yaml(path: Path) -> dict:
    """Load a YAML file and return a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root in {path}")

    return data


def load_configuration():
    """Load project configuration used by the checker."""
    countries_data = load_yaml(COUNTRIES_FILE)
    categories_data = load_yaml(CATEGORIES_FILE)
    quality_data = load_yaml(QUALITY_FILE)
    epg_sources_data = load_yaml(EPG_SOURCES_FILE)

    countries = {
        str(item["code"])
        for item in countries_data.get("countries", [])
        if isinstance(item, dict) and item.get("code")
    }

    categories = {
        str(item["id"])
        for item in categories_data.get("categories", [])
        if isinstance(item, dict) and item.get("id")
    }

    stream_rules = quality_data.get("quality_rules", {}).get("stream", {})

    timeout = int(stream_rules.get("timeout_seconds", 10))

    allowed_protocols = {
        str(protocol).lower()
        for protocol in stream_rules.get(
            "allowed_protocols",
            ["http", "https"],
        )
    }

    allowed_statuses = set(
        quality_data.get("quality_rules", {})
        .get("status", {})
        .keys()
    )

    if not allowed_statuses:
        allowed_statuses = {
            "stable",
            "testing",
            "archived",
        }

    epg_sources = {
        str(item["id"])
        for item in epg_sources_data.get("sources", [])
        if isinstance(item, dict) and item.get("id")
    }

    return (
        countries,
        categories,
        allowed_protocols,
        allowed_statuses,
        timeout,
        epg_sources,
    )


def validate_channel(
    channel: dict,
    countries: set[str],
    categories: set[str],
    allowed_protocols: set[str],
    allowed_statuses: set[str],
) -> list[str]:
    """Validate channel metadata before testing the network."""
    errors = []

    required = (
        "id",
        "name",
        "country",
        "category",
        "status",
    )

    for field in required:
        if not channel.get(field):
            errors.append(f"missing '{field}'")

    country = channel.get("country")

    if country and country not in countries:
        errors.append(f"unknown country '{country}'")

    category = channel.get("category")

    if category and category not in categories:
        errors.append(f"unknown category '{category}'")

    status = channel.get("status")

    if status and status not in allowed_statuses:
        errors.append(f"unknown status '{status}'")

    epg = channel.get("epg")

    if epg is not None:
        if not isinstance(epg, dict):
            errors.append("'epg' must be a mapping")
        else:
            epg_enabled = epg.get("enabled", False)

            if not isinstance(epg_enabled, bool):
                errors.append("'epg.enabled' must be boolean")

            elif epg_enabled:
                epg_id = epg.get("id")

                if (
                    epg_id is None
                    or not str(epg_id).strip()
                ):
                    errors.append(
                        "EPG is enabled but 'epg.id' is missing"
                    )

    stream = channel.get("stream")

    if not isinstance(stream, dict):
        errors.append("missing stream configuration")
        return errors

    url = stream.get("url")

    if not url:
        errors.append("missing stream URL")
        return errors

    parsed = urlparse(url)

    if parsed.scheme.lower() not in allowed_protocols:
        errors.append(
            f"protocol '{parsed.scheme}' is not allowed"
        )

    if not parsed.netloc:
        errors.append("invalid stream URL")

    return errors


def validate_epg_source(
    channel: dict,
    epg_sources: set[str],
) -> list[str]:
    """Validate enabled channel EPG source mapping."""
    errors = []

    epg = channel.get("epg")

    if not isinstance(epg, dict):
        return errors

    if epg.get("enabled") is not True:
        return errors

    source = epg.get("source")

    if (
        source is None
        or not str(source).strip()
    ):
        errors.append(
            "EPG is enabled but 'epg.source' is missing"
        )
        return errors

    source = str(source).strip()

    if source not in epg_sources:
        errors.append(
            f"unknown EPG source '{source}'"
        )

    return errors


def check_stream(channel: dict, timeout: int) -> tuple[bool, str]:
    """Test whether a channel stream can be reached."""
    stream = channel["stream"]
    url = stream["url"]
    stream_format = str(stream.get("format", "")).lower()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,"
            "text/plain,*/*"
        ),
        "Accept-Encoding": "identity",
    }

    channel_headers = stream.get("headers", {})

    if isinstance(channel_headers, dict):
        headers.update(
            {
                str(key): str(value)
                for key, value in channel_headers.items()
                if value is not None
            }
        )

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=SSL_CONTEXT,
        ) as response:
            status = getattr(response, "status", 200)

            if status < 200 or status >= 400:
                return False, f"HTTP {status}"

            content = response.read(READ_LIMIT)
            final_url = response.geturl()

            is_hls = (
                stream_format == "hls"
                or ".m3u8" in url.lower()
                or ".m3u8" in final_url.lower()
            )

            if is_hls:
                text = content.decode(
                    "utf-8-sig",
                    errors="replace",
                ).lstrip()

                if not text.startswith("#EXTM3U"):
                    return False, "response is not a valid HLS playlist"

            if final_url != url:
                return True, f"OK (redirected to {final_url})"

            return True, "OK"

    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}"

    except urllib.error.URLError as error:
        reason = error.reason

        if isinstance(reason, socket.timeout):
            return False, "timeout"

        return False, f"connection error: {reason}"

    except socket.timeout:
        return False, "timeout"

    except TimeoutError:
        return False, "timeout"

    except ssl.SSLError as error:
        return False, f"SSL error: {error}"

    except Exception as error:
        return False, f"{type(error).__name__}: {error}"

def check_stream_with_retries(
    channel: dict,
    timeout: int,
    attempts: int,
    retry_delay: float,
) -> tuple[bool, str, int, list[str]]:
    """Retry temporary stream failures before marking a stream as failed."""

    failures = []

    for attempt in range(1, attempts + 1):
        ok, message = check_stream(
            channel,
            timeout,
        )

        if ok:
            return (
                True,
                message,
                attempt,
                failures,
            )

        failures.append(message)

        if (
            attempt < attempts
            and retry_delay > 0
        ):
            time.sleep(retry_delay)

    return (
        False,
        failures[-1],
        attempts,
        failures,
    )        


def find_duplicates(channels: list[dict]) -> list[str]:
    """Find duplicate IDs and stream URLs."""
    problems = []

    ids = {}
    urls = {}
    epg_ids = {}

    for channel in channels:
        channel_id = channel.get("id")
        name = channel.get("name", "<unknown>")

        if channel_id:
            if channel_id in ids:
                problems.append(
                    f"duplicate ID '{channel_id}' "
                    f"({ids[channel_id]} / {name})"
                )
            else:
                ids[channel_id] = name

        stream = channel.get("stream")

        if isinstance(stream, dict):
            url = stream.get("url")

            if url:
                if url in urls:
                    problems.append(
                        f"duplicate URL "
                        f"({urls[url]} / {name})"
                    )
                else:
                    urls[url] = name

        epg = channel.get("epg")

        if (
            isinstance(epg, dict)
            and epg.get("enabled") is True
        ):
            epg_id = epg.get("id")

            if (
                epg_id is not None
                and str(epg_id).strip()
            ):
                epg_id = str(epg_id).strip()

                if epg_id in epg_ids:
                    problems.append(
                        f"duplicate EPG ID '{epg_id}' "
                        f"({epg_ids[epg_id]} / {name})"
                    )
                else:
                    epg_ids[epg_id] = name

    return problems


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="🐾 Bondik TV Ultimate channel checker"
    )

    parser.add_argument(
        "--status",
        choices=[
            "all",
            "stable",
            "testing",
            "archived",
        ],
        default="all",
        help="check only channels with selected status",
    )

    parser.add_argument(
        "--no-network",
        action="store_true",
        help="validate metadata only; do not test stream URLs",
    )

    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="number of network attempts per stream",
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0,
        help="seconds to wait between failed attempts",
    )

    args = parser.parse_args()

    if args.attempts < 1:
        parser.error(
            "--attempts must be at least 1"
        )

    if args.retry_delay < 0:
        parser.error(
            "--retry-delay cannot be negative"
        )

    return args


def main() -> int:
    args = parse_arguments()

    print()
    print("🐾 Bondik TV Ultimate")
    print("📺 Channel Checker")
    print("=" * 60)

    try:
        database = load_yaml(CHANNELS_FILE)

        (
            countries,
            categories,
            allowed_protocols,
            allowed_statuses,
            timeout,
            epg_sources,
        ) = load_configuration()

    except (FileNotFoundError, ValueError, yaml.YAMLError) as error:
        print(f"❌ Configuration error: {error}")
        return 2

    channels = database.get("channels")

    if not isinstance(channels, list):
        print("❌ 'channels' must be a YAML list.")
        return 2

    duplicates = find_duplicates(channels)

    if duplicates:
        print("\n❌ Duplicate database entries:")

        for problem in duplicates:
            print(f"   - {problem}")

        return 1

    selected_channels = []

    for channel in channels:
        if not isinstance(channel, dict):
            print("❌ Invalid channel entry.")
            return 2

        if args.status != "all":
            if channel.get("status") != args.status:
                continue

        if channel.get("status") == "archived" and args.status == "all":
            continue

        selected_channels.append(channel)

    if not selected_channels:
        print("ℹ️ No channels selected.")
        return 0

    passed = 0
    failed = 0
    recovered = 0

    for channel in selected_channels:
        name = channel.get("name", "<unknown>")
        status = channel.get("status", "unknown")

        metadata_errors = validate_channel(
            channel,
            countries,
            categories,
            allowed_protocols,
            allowed_statuses,
        )

        metadata_errors.extend(
            validate_epg_source(
                channel,
                epg_sources,
            )
        )

        if metadata_errors:
            failed += 1

            print(f"\n❌ {name} [{status}]")

            for error in metadata_errors:
                print(f"   └─ {error}")

            continue

        if args.no_network:
            passed += 1
            print(f"\n✅ {name} [{status}]")
            print("   └─ metadata OK")
            continue

        (
            ok,
            message,
            attempt,
            failures,
        ) = check_stream_with_retries(
            channel,
            timeout,
            args.attempts,
            args.retry_delay,
        )

        if ok:
            passed += 1

            if attempt == 1:
                print(f"\n✅ {name} [{status}]")
                print(f"   └─ {message}")
            else:
                recovered += 1

                print(f"\n⚠️ {name} [{status}]")
                print(
                    f"   └─ recovered on attempt "
                    f"{attempt}/{args.attempts}: "
                    f"{message}"
                )

                for number, failure in enumerate(
                    failures,
                    start=1,
                ):
                    print(
                        f"      attempt {number} "
                        f"failed: {failure}"
                    )

        else:
            failed += 1

            print(f"\n❌ {name} [{status}]")
            print(
                f"   └─ failed after "
                f"{attempt}/{args.attempts} attempts"
            )

            for number, failure in enumerate(
                failures,
                start=1,
            ):
                print(
                    f"      attempt {number}: "
                    f"{failure}"
                )

    total = passed + failed

    print()
    print("=" * 60)
    print("🐾 Bondík Quality Report")
    print(f"✅ Passed : {passed}")
    print(f"⚠️ Recovered: {recovered}")
    print(f"❌ Failed : {failed}")
    print(f"📺 Total  : {total}")
    print("=" * 60)

    if failed:
        print("🔴 RESULT: CHECK FAILED")
        return 1

    print("🟢 RESULT: BONDÍK APPROVED 🐾")
    return 0


if __name__ == "__main__":
    sys.exit(main())

