import sys
import unittest
from pathlib import Path

CHECKER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHECKER_DIR))

import hunt_m3u as hunter


class HuntM3UV02Tests(unittest.TestCase):

    def test_github_blob_to_raw(self):
        self.assertEqual(
            hunter.github_blob_to_raw(
                "https://github.com/acme/demo/blob/main/playlists/cz.m3u"
            ),
            "https://raw.githubusercontent.com/acme/demo/main/playlists/cz.m3u",
        )

    def test_parse_m3u_reads_metadata(self):
        text = '''#EXTM3U
#EXTINF:-1 tvg-id="CT1.cz" tvg-name="CT 1" group-title="CZ",ČT1
https://example.test/ct1/index.m3u8
'''
        channel = hunter.parse_m3u(text, "demo.m3u")[0]
        self.assertEqual(channel.name, "ČT1")
        self.assertEqual(channel.group, "CZ")
        self.assertEqual(channel.tvg_id, "CT1.cz")

    def test_extinf_comma_inside_quoted_user_agent(self):
        text = '''#EXTM3U
#EXTINF:-1 http-user-agent="Mozilla/5.0 (X11, Linux x86_64) AppleWebKit/537.36" group-title="Movies",AMC Europe Czech Republic
https://example.test/amc.m3u8
'''
        channel = hunter.parse_m3u(text, "demo.m3u")[0]
        self.assertEqual(channel.name, "AMC Europe Czech Republic")
        self.assertEqual(channel.group, "Movies")
        self.assertIn("X11, Linux", channel.user_agent)

    def test_vlcopt_headers_are_preserved(self):
        text = '''#EXTM3U
#EXTINF:-1 group-title="CZ",Demo
#EXTVLCOPT:http-user-agent=Bondik Browser
#EXTVLCOPT:http-referrer=https://example.test/
https://cdn.example.test/live.m3u8
'''
        channel = hunter.parse_m3u(text, "demo.m3u")[0]
        self.assertEqual(channel.user_agent, "Bondik Browser")
        self.assertEqual(channel.referer, "https://example.test/")

    def test_dedupe_distinguishes_header_profiles(self):
        first = hunter.Channel(
            name="A",
            url="https://example.test/live.m3u8",
            user_agent="UA-1",
        )
        second = hunter.Channel(
            name="B",
            url="https://example.test/live.m3u8",
            user_agent="UA-2",
        )
        self.assertEqual(len(hunter.dedupe_channels([first, second])), 2)

    def test_match_checks_metadata(self):
        channel = hunter.Channel(
            name="ČT1",
            url="https://example.test/live.m3u8",
            group="Česko",
        )
        pattern = hunter.re.compile("česko|prima", hunter.re.IGNORECASE)
        self.assertTrue(hunter.matches(channel, pattern))

    def test_master_playlist_selects_variant(self):
        text = '''#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1000000
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000
high/index.m3u8
'''
        self.assertEqual(hunter.hls_playlist_kind(text), "master")
        self.assertEqual(hunter.first_master_variant(text), "low/index.m3u8")

    def test_media_playlist_selects_segment(self):
        text = '''#EXTM3U
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:100
#EXTINF:6.0,
segment100.ts
#EXTINF:6.0,
segment101.ts
'''
        self.assertEqual(hunter.hls_playlist_kind(text), "media")
        self.assertEqual(hunter.first_media_uri(text), "segment100.ts")

    def test_html_detection(self):
        self.assertTrue(
            hunter.looks_like_html(
                "text/html; charset=utf-8",
                b"<html><body>error</body></html>",
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
