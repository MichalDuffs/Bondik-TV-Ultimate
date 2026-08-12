#!/usr/bin/env python3
"""
Bondik TV Ultimate - Playlist Generator

Reads the channel database and generates the main M3U playlist.

Source:
    channels/channels.yaml

Output:
    playlists/ultimate.m3u
"""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

SETTINGS_FILE = REPO_ROOT / "config" / "settings.yaml"


def load_yaml(path: Path) -> dict:
    """Load a UTF-8 YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root in {path}")

    return data


def escape_attribute(value) -> str:
    """Prepare a value for an M3U quoted attribute."""
    return str(value).replace('"', "'")


def build_channel_entry(channel: dict) -> list[str]:
    """Convert one channel entry to M3U lines."""
    name = str(channel["name"])
    country = str(channel["country"])

    stream = channel.get("stream", {})
    url = stream.get("url")

    if not url:
        raise ValueError(f"Channel '{name}' has no stream URL")

    attributes = [
        f'tvg-name="{escape_attribute(name)}"',
        f'group-title="{escape_attribute(country)}"',
    ]

    epg = channel.get("epg", {})

    if isinstance(epg, dict):
        epg_id = epg.get("id")

        if epg.get("enabled") and epg_id:
            attributes.append(
                f'tvg-id="{escape_attribute(epg_id)}"'
            )

    logo = channel.get("logo", {})

    if isinstance(logo, dict):
        logo_url = logo.get("url")

        if logo_url:
            attributes.append(
                f'tvg-logo="{escape_attribute(logo_url)}"'
            )

    extinf = (
        f'#EXTINF:-1 {" ".join(attributes)},'
        f'{name}'
    )

    return [
        extinf,
        str(url),
    ]


def main() -> int:
    settings = load_yaml(SETTINGS_FILE)

    generator_config = settings.get("generator", {})
    quality_config = settings.get("quality", {})

    channels_path = (
        generator_config
        .get("input", {})
        .get("channels", "channels/channels.yaml")
    )

    output_path = (
        generator_config
        .get("output", {})
        .get("ultimate", "playlists/ultimate.m3u")
    )

    required_status = quality_config.get(
        "minimum_status",
        "stable",
    )

    channels_file = REPO_ROOT / channels_path
    output_file = REPO_ROOT / output_path

    database = load_yaml(channels_file)

    channels = database.get("channels", [])

    if not isinstance(channels, list):
        raise ValueError("'channels' must be a list")

    selected = [
        channel
        for channel in channels
        if isinstance(channel, dict)
        and channel.get("status") == required_status
    ]

    lines = [
        "#EXTM3U",
        "# Bondik TV Ultimate",
        "# Generated automatically from channels/channels.yaml",
        "# Quality checked by Bondik",
        "",
    ]

    for channel in selected:
        lines.extend(build_channel_entry(channel))
        lines.append("")

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write("\n".join(lines))

    print()
    print("🐾 Bondik TV Ultimate")
    print("📺 Playlist Generator")
    print("=" * 60)
    print(f"✅ Generated : {output_file.relative_to(REPO_ROOT)}")
    print(f"📺 Channels  : {len(selected)}")
    print(f"🏷️ Status    : {required_status}")
    print("=" * 60)
    print("🟢 RESULT: PLAYLIST GENERATED 🐾")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())