import sys
import unittest
from pathlib import Path

CHECKER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHECKER_DIR))

import prepare_hunt_candidates as gate


class CandidateGateTests(unittest.TestCase):

    def test_clean_display_name_removes_quality_and_runtime_labels(self):
        self.assertEqual(
            gate.clean_display_name("TV Noe (720p) [Geo-blocked]"),
            "TV Noe",
        )
        self.assertEqual(
            gate.clean_display_name("Minimax (576p) (576p)"),
            "Minimax",
        )

    def test_canonical_name_handles_diacritics(self):
        self.assertEqual(
            gate.canonical_name("Óčko Star (1080p)"),
            "ockostar",
        )

    def test_infer_country_from_country_playlist(self):
        self.assertEqual(
            gate.infer_country(
                "https://iptv-org.github.io/iptv/countries/cz.m3u"
            ),
            "CZ",
        )

    def test_infer_category_alias(self):
        self.assertEqual(
            gate.infer_source_category(
                "https://iptv-org.github.io/iptv/categories/sports.m3u",
                {"sport", "music"},
            ),
            "sport",
        )

    def test_existing_url_is_excluded(self):
        rows = [
            {
                "ok": True,
                "validation": "hls-segment",
                "url": "https://example.test/live.m3u8",
                "name": "Demo",
                "source": "https://example.test/countries/cz.m3u",
            }
        ]
        candidates, stats = gate.build_candidates(
            rows,
            existing_urls={"https://example.test/live.m3u8"},
            existing_names=set(),
            existing_name_to_id={},
            category_ids={"general"},
            include_http_media=False,
        )
        self.assertEqual(candidates, [])
        self.assertEqual(stats["skip_existing_url"], 1)

    def test_http_media_requires_explicit_opt_in(self):
        row = {
            "ok": True,
            "validation": "http-media",
            "url": "https://example.test/live",
            "name": "Demo",
            "source": "https://example.test/countries/cz.m3u",
        }
        candidates, _ = gate.build_candidates(
            [row],
            existing_urls=set(),
            existing_names=set(),
            existing_name_to_id={},
            category_ids={"general"},
            include_http_media=False,
        )
        self.assertEqual(candidates, [])

        candidates, _ = gate.build_candidates(
            [row],
            existing_urls=set(),
            existing_names=set(),
            existing_name_to_id={},
            category_ids={"general"},
            include_http_media=True,
        )
        self.assertEqual(len(candidates), 1)

    def test_existing_name_alternative_is_flagged(self):
        rows = [
            {
                "ok": True,
                "validation": "hls-segment",
                "url": "https://example.test/new.m3u8",
                "name": "Óčko Star (1080p)",
                "source": "https://example.test/countries/cz.m3u",
            }
        ]
        candidates, _ = gate.build_candidates(
            rows,
            existing_urls=set(),
            existing_names={"ockostar"},
            existing_name_to_id={"ockostar": "ocko-star-cz"},
            category_ids={"music"},
            include_http_media=False,
        )
        self.assertIn(
            "possible-existing-channel-alternative",
            candidates[0]["review_flags"],
        )
        self.assertEqual(
            candidates[0]["existing_channel_id"],
            "ocko-star-cz",
        )

    def test_duplicate_name_multiple_streams_is_flagged(self):
        rows = [
            {
                "ok": True,
                "validation": "hls-segment",
                "response_ms": 100,
                "url": "https://example.test/a.m3u8",
                "name": "Demo TV",
                "source": "https://example.test/countries/cz.m3u",
            },
            {
                "ok": True,
                "validation": "hls-segment",
                "response_ms": 150,
                "url": "https://example.test/b.m3u8",
                "name": "Demo TV (1080p)",
                "source": "https://example.test/countries/cz.m3u",
            },
        ]
        candidates, _ = gate.build_candidates(
            rows,
            existing_urls=set(),
            existing_names=set(),
            existing_name_to_id={},
            category_ids={"general"},
            include_http_media=False,
        )
        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(
                "duplicate-name-multiple-streams" in item["review_flags"]
                for item in candidates
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
