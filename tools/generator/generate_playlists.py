#!/usr/bin/env python3
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]

SETTINGS = ROOT / "config" / "settings.yaml"
COUNTRIES = ROOT / "config" / "countries.yaml"
CATEGORIES = ROOT / "config" / "categories.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root: {path}")

    return data


def escape(value) -> str:
    return str(value).replace('"', "'")

def validate_channels(
    channels: list,
    requirements: dict,
) -> None:
    """Validate channel metadata before writing playlists."""

    for index, channel in enumerate(
        channels,
        start=1,
    ):
        if not isinstance(channel, dict):
            raise ValueError(
                f"Invalid channel at index {index}: "
                "expected YAML mapping"
            )

        stream = channel.get("stream", {})

        stream_url = (
            stream.get("url")
            if isinstance(stream, dict)
            else None
        )

        checks = {
            "channel_name": (
                "name",
                channel.get("name"),
            ),
            "country": (
                "country",
                channel.get("country"),
            ),
            "category": (
                "category",
                channel.get("category"),
            ),
            "provider": (
                "provider",
                channel.get("provider"),
            ),
            "stream_url": (
                "stream.url",
                stream_url,
            ),
        }

        missing = []

        for rule, (label, value) in checks.items():
            if not requirements.get(rule, False):
                continue

            if value is None or not str(value).strip():
                missing.append(label)

        if missing:
            channel_id = channel.get(
                "id",
                f"index-{index}",
            )

            raise ValueError(
                f"Invalid channel '{channel_id}': "
                f"missing {', '.join(missing)}"
            )

def channel_lines(channel: dict) -> list[str]:
    name = str(channel["name"])
    country = str(channel["country"])

    stream = channel.get("stream", {})
    url = stream.get("url")

    if not url:
        raise ValueError(
            f"Channel '{name}' has no stream URL"
        )

    attributes = [
        f'tvg-name="{escape(name)}"',
        f'group-title="{escape(country)}"',
    ]

    epg = channel.get("epg", {})

    if (
        isinstance(epg, dict)
        and epg.get("enabled")
        and epg.get("id")
    ):
        epg_id = epg["id"]
        attributes.append(
            f'tvg-id="{escape(epg_id)}"'
        )

    logo = channel.get("logo", {})

    if isinstance(logo, dict) and logo.get("url"):
        logo_url = logo["url"]
        attributes.append(
            f'tvg-logo="{escape(logo_url)}"'
        )

    return [
        f'#EXTINF:-1 {" ".join(attributes)},{name}',
        str(url),
    ]


def write_playlist(
    path: Path,
    channels: list[dict],
    title: str,
) -> None:
    lines = [
        "#EXTM3U",
        f"# Bondik TV Ultimate - {title}",
        "# Generated automatically from channels/channels.yaml",
        "# Quality checked by Bondik",
        "",
    ]

    for channel in channels:
        lines.extend(channel_lines(channel))
        lines.append("")

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write("\n".join(lines))

def cleanup_generated_playlists(
    directory: Path,
    expected_names: set[str],
) -> list[Path]:
    """Remove obsolete playlists previously created by the generator."""

    if not directory.exists():
        return []

    marker = (
        "# Generated automatically from "
        "channels/channels.yaml"
    )

    removed = []

    for path in directory.glob("*.m3u"):
        if path.name in expected_names:
            continue

        try:
            content = path.read_text(
                encoding="utf-8",
            )
        except UnicodeDecodeError:
            continue

        if marker not in content:
            continue

        path.unlink()
        removed.append(path)

    return removed        


def main() -> int:
    settings = load_yaml(SETTINGS)
    countries_config = load_yaml(COUNTRIES)
    categories_config = load_yaml(CATEGORIES)

    generator = settings.get(
        "generator",
        {},
    )

    input_config = generator.get(
        "input",
        {},
    )

    output_config = generator.get(
        "output",
        {},
    )

    required_status = (
        settings
        .get("quality", {})
        .get("minimum_status", "stable")
    )

    channels_file = (
        ROOT
        / input_config.get(
            "channels",
            "channels/channels.yaml",
        )
    )

    database = load_yaml(channels_file)

    channels = database.get(
        "channels",
        [],
    )

    if not isinstance(channels, list):
        raise ValueError(
            "'channels' must be a list"
        )

    requirements = (
        settings
        .get("quality", {})
        .get("require", {})
    )

    validate_channels(
        channels,
        requirements,
    )

    stable = [
        channel
        for channel in channels
        if isinstance(channel, dict)
        and channel.get("status") == required_status
    ]

    # Ultimate
    write_playlist(
        ROOT
        / output_config.get(
            "ultimate",
            "playlists/ultimate.m3u",
        ),
        stable,
        "Ultimate",
    )

    # Countries
    country_count = 0

    for country in countries_config.get(
        "countries",
        [],
    ):
        if not isinstance(country, dict):
            continue

        code = country.get("code")

        if not code:
            continue

        code = str(code)

        selected = [
            channel
            for channel in stable
            if channel.get("country") == code
        ]

        output_file = (
            ROOT
            / output_config.get(
                "countries",
                "playlists/countries",
            )
            / f"{code.lower()}.m3u"
        )

        write_playlist(
            output_file,
            selected,
            f'Country: {country.get("name", code)}',
        )

        country_count += 1

    # Categories
    category_count = 0

    for category in categories_config.get(
        "categories",
        [],
    ):
        if not isinstance(category, dict):
            continue

        category_id = category.get("id")

        if not category_id:
            continue

        category_id = str(category_id)

        selected = [
            channel
            for channel in stable
            if channel.get("category")
            == category_id
        ]

        filename = str(
            category.get(
                "playlist",
                f"{category_id}.m3u",
            )
        )

        output_file = (
            ROOT
            / output_config.get(
                "categories",
                "playlists/categories",
            )
            / filename
        )

        write_playlist(
            output_file,
            selected,
            f'Category: {category.get("name", category_id)}',
        )

        category_count += 1

    # Providers
    provider_count = 0

    providers = sorted(
        {
            str(channel["provider"])
            for channel in stable
            if channel.get("provider")
        }
    )

    for provider in providers:
        selected = [
            channel
            for channel in stable
            if channel.get("provider") == provider
        ]

        output_file = (
            ROOT
            / output_config.get(
                "providers",
                "playlists/providers",
            )
            / f"{provider.lower()}.m3u"
        )

        write_playlist(
            output_file,
            selected,
            f"Provider: {provider}",
        )

        provider_count += 1

    # Cleanup obsolete generated playlists
    country_names = {
        f"{str(country['code']).lower()}.m3u"
        for country in countries_config.get(
            "countries",
            [],
        )
        if isinstance(country, dict)
        and country.get("code")
    }

    category_names = {
        str(
            category.get(
                "playlist",
                f"{category['id']}.m3u",
            )
        )
        for category in categories_config.get(
            "categories",
            [],
        )
        if isinstance(category, dict)
        and category.get("id")
    }

    provider_names = {
        f"{provider.lower()}.m3u"
        for provider in providers
    }

    removed = []

    removed.extend(
        cleanup_generated_playlists(
            ROOT
            / output_config.get(
                "countries",
                "playlists/countries",
            ),
            country_names,
        )
    )

    removed.extend(
        cleanup_generated_playlists(
            ROOT
            / output_config.get(
                "categories",
                "playlists/categories",
            ),
            category_names,
        )
    )

    removed.extend(
        cleanup_generated_playlists(
            ROOT
            / output_config.get(
                "providers",
                "playlists/providers",
            ),
            provider_names,
        )
    )    


    print()
    print("🐾 Bondik TV Ultimate")
    print("📺 Playlist Generator v5")
    print("=" * 60)
    print(f"🔎 Validated channels: {len(channels)}")
    print(f"✅ Ultimate channels : {len(stable)}")
    print(f"🌍 Country playlists : {country_count}")
    print(f"🎬 Category playlists: {category_count}")
    print(f"📡 Provider playlists: {provider_count}")
    print(f"🧹 Obsolete removed  : {len(removed)}")
    print(f"🏷️ Status            : {required_status}")
    print("=" * 60)
    print("🟢 RESULT: PLAYLISTS GENERATED 🐾")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())