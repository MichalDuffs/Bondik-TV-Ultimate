from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

MEDIA_CONTRACT_PROTOCOL = (
    "bondik-city-media-contract/1"
)
MEDIA_SOURCE_PROTOCOL = (
    "bondik-city-media-source/1"
)
MEDIA_VERSION = 1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-media-contract.json"
)
DEFAULT_CATALOG_PATH = (
    ROOT / "channels" / "channels.yaml"
)


class CityMediaError(ValueError):
    pass


def _load_json(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except OSError as error:
        raise CityMediaError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityMediaError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="media contract",
    )

    if not isinstance(payload, dict):
        raise CityMediaError(
            "media contract root must be an object"
        )

    if payload.get("protocol") != (
        MEDIA_CONTRACT_PROTOCOL
    ):
        raise CityMediaError(
            "unsupported media contract protocol"
        )

    if payload.get("version") != MEDIA_VERSION:
        raise CityMediaError(
            "unsupported media contract version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityMediaError(
            "media contract cityId mismatch"
        )

    if payload.get("sourceProtocol") != (
        MEDIA_SOURCE_PROTOCOL
    ):
        raise CityMediaError(
            "media source protocol mismatch"
        )

    if payload.get("catalogPath") != (
        "channels/channels.yaml"
    ):
        raise CityMediaError(
            "media catalog path mismatch"
        )

    formats = payload.get(
        "supportedFormats"
    )

    if formats != ["hls"]:
        raise CityMediaError(
            "media contract v1 supports hls only"
        )

    schemes = payload.get("urlSchemes")

    if schemes != ["http", "https"]:
        raise CityMediaError(
            "media contract URL schemes invalid"
        )

    if payload.get("headerPolicy") != (
        "preserve-string-map"
    ):
        raise CityMediaError(
            "media header policy invalid"
        )

    if payload.get("exposure") != {
        "playbackExecution": "not-exposed",
        "agentExecution": "not-exposed",
        "networkMutation": "not-exposed",
    }:
        raise CityMediaError(
            "media exposure contract invalid"
        )

    return payload


def load_catalog(
    path: Path = DEFAULT_CATALOG_PATH,
) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except OSError as error:
        raise CityMediaError(
            f"cannot read channel catalog: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise CityMediaError(
            "channel catalog must be valid YAML"
        ) from error

    if not isinstance(payload, dict):
        raise CityMediaError(
            "channel catalog root must be an object"
        )

    if payload.get("version") != 1:
        raise CityMediaError(
            "channel catalog version unsupported"
        )

    channels = payload.get("channels")

    if not isinstance(channels, list):
        raise CityMediaError(
            "channel catalog channels must be a list"
        )

    return payload


def _required_text(
    value: Any,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise CityMediaError(
            f"{label} must be a non-empty string"
        )

    return value


def _validate_headers(
    value: Any,
) -> dict[str, str]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise CityMediaError(
            "stream headers must be an object"
        )

    result: dict[str, str] = {}

    for key, header_value in value.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(
                header_value,
                str,
            )
        ):
            raise CityMediaError(
                "stream headers must map "
                "strings to strings"
            )

        result[key] = header_value

    return result


def media_source_from_channel(
    channel: Any,
    *,
    contract: dict[str, Any],
    catalog_version: int = 1,
) -> dict[str, Any]:
    if not isinstance(channel, dict):
        raise CityMediaError(
            "channel must be an object"
        )

    channel_id = _required_text(
        channel.get("id"),
        label="channel id",
    )
    name = _required_text(
        channel.get("name"),
        label="channel name",
    )

    stream = channel.get("stream")

    if not isinstance(stream, dict):
        raise CityMediaError(
            "channel stream must be an object"
        )

    uri = _required_text(
        stream.get("url"),
        label="stream url",
    )
    parsed = urlparse(uri)

    if (
        parsed.scheme
        not in contract["urlSchemes"]
        or not parsed.netloc
    ):
        raise CityMediaError(
            "stream url must use an approved "
            "absolute scheme"
        )

    stream_format = _required_text(
        stream.get("format"),
        label="stream format",
    )

    if stream_format not in contract[
        "supportedFormats"
    ]:
        raise CityMediaError(
            "stream format is not supported "
            "by media contract"
        )

    headers = _validate_headers(
        stream.get("headers")
    )

    return {
        "protocol": MEDIA_SOURCE_PROTOCOL,
        "version": MEDIA_VERSION,
        "sourceId": channel_id,
        "kind": contract["sourceKind"],
        "displayName": name,
        "media": {
            "uri": uri,
            "format": stream_format,
            "headers": headers,
        },
        "channel": {
            "id": channel_id,
            "name": name,
            "country": channel.get("country"),
            "language": channel.get(
                "language"
            ),
            "category": channel.get(
                "category"
            ),
            "provider": channel.get(
                "provider"
            ),
            "status": channel.get("status"),
        },
        "provenance": {
            "catalogPath": contract[
                "catalogPath"
            ],
            "catalogVersion": (
                catalog_version
            ),
        },
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def build_media_sources(
    catalog: dict[str, Any],
    *,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    channels = catalog["channels"]
    seen: set[str] = set()
    sources = []

    for channel in channels:
        source = media_source_from_channel(
            channel,
            contract=contract,
            catalog_version=catalog[
                "version"
            ],
        )

        source_id = source["sourceId"]

        if source_id in seen:
            raise CityMediaError(
                "duplicate channel id"
            )

        seen.add(source_id)
        sources.append(source)

    return sources


def resolve_media_source(
    channel_id: str,
    *,
    catalog: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    for channel in catalog["channels"]:
        if (
            isinstance(channel, dict)
            and channel.get("id")
            == channel_id
        ):
            return media_source_from_channel(
                channel,
                contract=contract,
                catalog_version=catalog[
                    "version"
                ],
            )

    raise CityMediaError(
        f"unknown channel id: {channel_id}"
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Bondik City media "
            "source contract against the current "
            "channel catalog."
        )
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        contract = load_contract(
            args.contract
        )
        catalog = load_catalog(
            args.catalog
        )
        sources = build_media_sources(
            catalog,
            contract=contract,
        )
    except CityMediaError as error:
        print(
            f"❌ Bondik City Media Contract: {error}"
        )
        return 1

    formats = sorted(
        {
            source["media"]["format"]
            for source in sources
        }
    )

    print(
        "Bondik City Media Contract OK: "
        f"{len(sources)} sources / "
        f"{','.join(formats)} / "
        f"{MEDIA_SOURCE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
