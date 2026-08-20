import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scan_playlists-v03.py"
SPEC = importlib.util.spec_from_file_location("scan_playlists_v03", SCRIPT_PATH)
SCANNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCANNER
SPEC.loader.exec_module(SCANNER)


class ScanPlaylistsV03MetadataTests(unittest.TestCase):
    def test_parse_name_reads_normal_extinf(self):
        extinf = '#EXTINF:-1 group-title="News",CNN Prima News'

        self.assertEqual(SCANNER.parse_name(extinf), "CNN Prima News")

    def test_parse_name_ignores_comma_inside_quoted_user_agent(self):
        extinf = (
            '#EXTINF:-1 http-user-agent="Mozilla/5.0 '
            '(KHTML, like Gecko) Chrome/149.0" group-title="Movies",'
            'AMC Europe Czech Republic'
        )

        self.assertEqual(
            SCANNER.parse_name(extinf),
            "AMC Europe Czech Republic",
        )

    def test_playlist_keeps_name_after_quoted_user_agent(self):
        playlist = "\n".join(
            [
                "#EXTM3U",
                (
                    '#EXTINF:-1 http-user-agent="Mozilla/5.0 '
                    '(KHTML, like Gecko) Chrome/149.0" '
                    'group-title="Movies",AMC Europe Czech Republic'
                ),
                "https://example.com/live/playlist.m3u8",
            ]
        )

        candidates = SCANNER.parse_playlist(
            SCANNER.Source("test", "https://example.com/source.m3u"),
            playlist,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "AMC Europe Czech Republic")


if __name__ == "__main__":
    unittest.main()
