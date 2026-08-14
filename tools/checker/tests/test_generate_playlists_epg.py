from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
GENERATOR_DIR = ROOT / "tools" / "generator"

if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import generate_playlists as generator


class EpgPlaylistHeaderTests(unittest.TestCase):

    def setUp(self):
        self.sources = {
            "epgshare-cz": (
                "https://example.test/cz.xml.gz"
            ),
            "epgshare-sk": (
                "https://example.test/sk.xml.gz"
            ),
        }

    def channel(
        self,
        *,
        source=None,
        enabled=True,
    ):
        epg = {
            "id": "example.tv",
            "enabled": enabled,
        }

        if source is not None:
            epg["source"] = source

        return {
            "name": "Example TV",
            "country": "CZ",
            "epg": epg,
        }

    def test_header_contains_used_epg_source(self):
        channels = [
            self.channel(source="epgshare-cz"),
        ]

        header = generator.build_m3u_header(
            channels,
            self.sources,
        )

        self.assertEqual(
            header,
            '#EXTM3U x-tvg-url="'
            'https://example.test/cz.xml.gz"',
        )

    def test_header_contains_multiple_sources_once(self):
        channels = [
            self.channel(source="epgshare-cz"),
            self.channel(source="epgshare-sk"),
            self.channel(source="epgshare-cz"),
        ]

        header = generator.build_m3u_header(
            channels,
            self.sources,
        )

        self.assertEqual(
            header,
            '#EXTM3U x-tvg-url="'
            'https://example.test/cz.xml.gz,'
            'https://example.test/sk.xml.gz"',
        )

    def test_disabled_epg_is_ignored(self):
        channels = [
            self.channel(
                source="epgshare-cz",
                enabled=False,
            ),
        ]

        header = generator.build_m3u_header(
            channels,
            self.sources,
        )

        self.assertEqual(
            header,
            "#EXTM3U",
        )

    def test_playlist_without_epg_uses_plain_header(self):
        header = generator.build_m3u_header(
            [],
            self.sources,
        )

        self.assertEqual(
            header,
            "#EXTM3U",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
