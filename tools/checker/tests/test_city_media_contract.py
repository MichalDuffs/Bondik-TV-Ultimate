import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.media_contract import (
    MEDIA_CONTRACT_PROTOCOL,
    MEDIA_SOURCE_PROTOCOL,
    CityMediaError,
    build_media_sources,
    load_catalog,
    load_contract,
    media_source_from_channel,
    resolve_media_source,
)


ROOT = Path(__file__).resolve().parents[3]


def contract():
    return load_contract()


def sample_channel():
    return {
        "id": "demo-cz",
        "name": "Demo TV",
        "country": "CZ",
        "language": "cs",
        "category": "general",
        "provider": "demo",
        "status": "stable",
        "stream": {
            "url": (
                "https://example.test/live.m3u8"
            ),
            "format": "hls",
            "quality": "FHD",
            "headers": {
                "User-Agent": "Bondik",
                "Referer": (
                    "https://example.test/"
                ),
            },
        },
    }


def test_current_catalog_maps_to_media_sources():
    catalog = load_catalog()
    sources = build_media_sources(
        catalog,
        contract=contract(),
    )

    assert len(sources) == 39
    assert all(
        source["protocol"]
        == MEDIA_SOURCE_PROTOCOL
        for source in sources
    )
    assert {
        source["media"]["format"]
        for source in sources
    } == {"hls"}


def test_source_preserves_stream_headers():
    source = media_source_from_channel(
        sample_channel(),
        contract=contract(),
    )

    assert source["media"]["headers"] == {
        "User-Agent": "Bondik",
        "Referer": "https://example.test/",
    }


def test_source_keeps_channel_identity():
    source = media_source_from_channel(
        sample_channel(),
        contract=contract(),
    )

    assert source["sourceId"] == "demo-cz"
    assert source["displayName"] == "Demo TV"
    assert source["channel"]["country"] == "CZ"
    assert source["channel"]["status"] == "stable"


def test_resolve_by_channel_id():
    catalog = {
        "version": 1,
        "channels": [sample_channel()],
    }

    source = resolve_media_source(
        "demo-cz",
        catalog=catalog,
        contract=contract(),
    )

    assert source["sourceId"] == "demo-cz"


def test_unknown_channel_is_rejected():
    catalog = {
        "version": 1,
        "channels": [],
    }

    with pytest.raises(
        CityMediaError,
        match="unknown channel id",
    ):
        resolve_media_source(
            "missing",
            catalog=catalog,
            contract=contract(),
        )


def test_unsupported_format_is_rejected():
    channel = sample_channel()
    channel["stream"]["format"] = "dash"

    with pytest.raises(
        CityMediaError,
        match="not supported",
    ):
        media_source_from_channel(
            channel,
            contract=contract(),
        )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "file:///tmp/video.m3u8",
        "javascript:alert(1)",
        "/relative/live.m3u8",
    ],
)
def test_unapproved_url_is_rejected(url):
    channel = sample_channel()
    channel["stream"]["url"] = url

    with pytest.raises(
        CityMediaError,
        match=(
            "approved absolute scheme"
            "|non-empty string"
        ),
    ):
        media_source_from_channel(
            channel,
            contract=contract(),
        )


def test_invalid_headers_are_rejected():
    channel = sample_channel()
    channel["stream"]["headers"] = {
        "X-Number": 1,
    }

    with pytest.raises(
        CityMediaError,
        match="strings to strings",
    ):
        media_source_from_channel(
            channel,
            contract=contract(),
        )


def test_duplicate_channel_id_is_rejected():
    catalog = {
        "version": 1,
        "channels": [
            sample_channel(),
            copy.deepcopy(
                sample_channel()
            ),
        ],
    }

    with pytest.raises(
        CityMediaError,
        match="duplicate channel id",
    ):
        build_media_sources(
            catalog,
            contract=contract(),
        )


def test_contract_matches_v1_boundary():
    payload = json.loads(
        (
            ROOT
            / "config"
            / "city-media-contract.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload["protocol"] == (
        MEDIA_CONTRACT_PROTOCOL
    )
    assert payload["sourceProtocol"] == (
        MEDIA_SOURCE_PROTOCOL
    )
    assert payload["supportedFormats"] == [
        "hls"
    ]
    assert payload["platformMigration"] == {
        "web": "planned",
        "android": "planned",
    }
    assert payload["exposure"] == {
        "playbackExecution": "not-exposed",
        "agentExecution": "not-exposed",
        "networkMutation": "not-exposed",
    }


def test_direct_cli_validates_catalog():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "media_contract.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Media Contract OK: "
        "39 sources / hls / "
        "bondik-city-media-source/1"
        in result.stdout
    )
