import sys
import unittest
from pathlib import Path

CHECKER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHECKER_DIR))

import prepare_hunt_candidates as gate


class CandidateGateTests(unittest.TestCase):

    def build(self, rows, **kwargs):
        defaults = dict(
            existing_urls=set(),
            existing_names=set(),
            existing_name_to_id={},
            category_ids={"general", "education", "kids"},
            include_http_media=False,
            country_codes={"CZ", "SK", "TR", "DE", "US"},
        )
        defaults.update(kwargs)
        return gate.build_candidates(rows, **defaults)

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

    def test_infer_country_from_tvg_id(self):
        self.assertEqual(
            gate.infer_country_from_tvg_id("TRTEBAOrtaokul.tr"),
            "TR",
        )
        self.assertEqual(
            gate.infer_country_from_tvg_id("TRTEBA.tr@SD"),
            "TR",
        )
        self.assertEqual(
            gate.infer_country_from_tvg_id("GodStandsKidsClubTV.pk@English"),
            "PK",
        )

    def test_tvg_id_country_enrichment_for_category_playlist(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "https://tv-e-okul01.medya.trt.com.tr/master.m3u8",
            "name": "TRT EBA Ortaokul",
            "tvg_id": "TRTEBAOrtaokul.tr",
            "source": "https://iptv-org.github.io/iptv/categories/education.m3u",
        }]
        candidates, stats = self.build(rows)
        self.assertEqual(candidates[0]["country_inferred"], "TR")
        self.assertEqual(candidates[0]["country_basis"], "tvg-id-suffix")
        self.assertNotIn("country-unknown", candidates[0]["review_flags"])
        self.assertEqual(stats["country_enriched_tvg_id"], 1)

    def test_infer_category_alias(self):
        self.assertEqual(
            gate.infer_source_category(
                "https://iptv-org.github.io/iptv/categories/sports.m3u",
                {"sport", "music"},
            ),
            "sport",
        )

    def test_existing_url_is_excluded(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "https://example.test/live.m3u8",
            "name": "Demo",
            "source": "https://example.test/countries/cz.m3u",
        }]
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
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "https://example.test/new.m3u8",
            "name": "Óčko Star (1080p)",
            "source": "https://example.test/countries/cz.m3u",
        }]
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
        self.assertEqual(candidates[0]["existing_channel_id"], "ocko-star-cz")

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
        self.assertTrue(all(
            "duplicate-name-multiple-streams" in item["review_flags"]
            for item in candidates
        ))

    def test_raw_ip_goes_to_parking(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "http://88.212.15.19/live/channel/index.m3u8",
            "name": "Demo",
            "tvg_id": "Demo.hu",
            "source": "https://iptv-org.github.io/iptv/categories/kids.m3u",
        }]
        candidates, _ = self.build(rows, country_codes={"HU"})
        self.assertIn("raw-ip-host", candidates[0]["review_flags"])
        self.assertEqual(candidates[0]["review_bucket"], "parking")

    def test_freeott_goes_to_parking(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "http://hls127.freeott.top:8080/Demo/video.m3u8",
            "name": "Demo",
            "tvg_id": "Demo.de",
            "source": "https://iptv-org.github.io/iptv/categories/education.m3u",
        }]
        candidates, _ = self.build(rows)
        self.assertIn("suspicious-restream-domain", candidates[0]["review_flags"])
        self.assertEqual(candidates[0]["review_bucket"], "parking")

    def test_test_feed_path_goes_to_parking(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "https://dash4.antik.sk/live/test_kika_tizen/playlist.m3u8",
            "name": "KiKA HD",
            "tvg_id": "KiKA.de",
            "source": "https://iptv-org.github.io/iptv/categories/kids.m3u",
        }]
        candidates, _ = self.build(rows)
        self.assertIn("test-feed-path", candidates[0]["review_flags"])
        self.assertEqual(candidates[0]["review_bucket"], "parking")

    def test_clean_candidate_can_be_priority(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "url": "https://media.example.org/live/master.m3u8",
            "name": "Demo Education",
            "tvg_id": "DemoEducation.tr",
            "source": "https://iptv-org.github.io/iptv/categories/education.m3u",
        }]
        candidates, _ = self.build(rows)
        self.assertEqual(candidates[0]["review_bucket"], "priority")

    def test_country_alias_uk_to_gb(self):
        self.assertEqual(
            gate.infer_country_from_tvg_id("ExampleChannel.uk@HD"),
            "GB",
        )

    def test_antik_provider_domain_goes_to_review(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "response_ms": 127,
            "url": "https://dash3.antik.sk/live/duck_tv/index.m3u8",
            "name": "ducktv HD",
            "tvg_id": "ducktv.sk@HD",
            "source": "https://iptv-org.github.io/iptv/categories/kids.m3u",
        }]
        candidates, _ = self.build(rows, country_codes={"SK"})

        self.assertIn(
            "provider-host-review",
            candidates[0]["review_flags"],
        )
        self.assertNotIn(
            "suspicious-restream-domain",
            candidates[0]["review_flags"],
        )
        self.assertEqual(
            candidates[0]["review_bucket"],
            "review",
        )

    def test_bondik_score_rewards_clean_candidate(self):
        clean = {
            "validation": "hls-segment",
            "url": "https://media.example.org/live/master.m3u8",
            "country_inferred": "DE",
            "category_inferred": "education",
            "response_ms": 269,
            "review_flags": ["manual-provenance-review"],
        }
        risky = {
            "validation": "hls-segment",
            "url": "http://88.212.15.19/live/test_demo/playlist.m3u8",
            "country_inferred": "DE",
            "category_inferred": "education",
            "response_ms": 100,
            "review_flags": [
                "manual-provenance-review",
                "raw-ip-host",
                "test-feed-path",
                "unencrypted-http",
            ],
        }
        clean_score, clean_reasons = gate.bondik_score(clean)
        risky_score, _ = gate.bondik_score(risky)
        self.assertGreater(clean_score, risky_score)
        self.assertLessEqual(clean_score, 89)
        self.assertGreaterEqual(clean_score, 70)
        self.assertIn("https:+8", clean_reasons)

    def test_candidate_contains_score_and_reasons(self):
        rows = [{
            "ok": True,
            "validation": "hls-segment",
            "response_ms": 300,
            "url": "https://media.example.org/live/master.m3u8",
            "name": "Demo",
            "tvg_id": "Demo.de@HD",
            "source": "https://iptv-org.github.io/iptv/categories/education.m3u",
        }]
        candidates, _ = self.build(rows)
        self.assertIn("bondik_score", candidates[0])
        self.assertIn("score_reasons", candidates[0])
        self.assertGreaterEqual(candidates[0]["bondik_score"], 0)
        self.assertLessEqual(candidates[0]["bondik_score"], 100)


    def test_unverified_candidate_never_reaches_elite_band(self):
        item = {
            "validation": "hls-segment",
            "url": "https://demo.example.org/live/master.m3u8",
            "candidate_name": "Demo Example",
            "country_inferred": "DE",
            "category_inferred": "education",
            "response_ms": 80,
            "review_flags": ["manual-provenance-review"],
        }
        score, reasons = gate.bondik_score(item)
        self.assertLessEqual(score, 89)
        self.assertIn("unverified-provenance-cap:89", reasons)

    def test_verified_provenance_can_enter_elite_band(self):
        item = {
            "validation": "hls-segment",
            "url": "https://demo.example.org/live/master.m3u8",
            "candidate_name": "Demo Example",
            "country_inferred": "DE",
            "category_inferred": "education",
            "response_ms": 80,
            "review_flags": [],
            "provenance_verified": True,
        }
        score, reasons = gate.bondik_score(item)
        self.assertGreaterEqual(score, 90)
        self.assertIn("provenance-verified:+10", reasons)

    def test_name_host_affinity_rewards_direct_looking_host(self):
        direct = {
            "validation": "hls-segment",
            "url": "https://livestream.pbskids.org/live/master.m3u8",
            "candidate_name": "PBS Kids",
            "country_inferred": "US",
            "category_inferred": "kids",
            "response_ms": 300,
            "review_flags": ["manual-provenance-review"],
        }
        opaque = dict(direct)
        opaque["url"] = "https://d123.cloudfront.net/live/master.m3u8"
        direct_score, direct_reasons = gate.bondik_score(direct)
        opaque_score, opaque_reasons = gate.bondik_score(opaque)
        self.assertGreater(direct_score, opaque_score)
        self.assertIn("name-host-affinity:+8", direct_reasons)
        self.assertIn("generic-cdn:-3", opaque_reasons)

    def test_response_time_is_only_small_ranking_signal(self):
        fast = {
            "validation": "hls-segment",
            "url": "https://media.example.org/live/master.m3u8",
            "candidate_name": "Example",
            "country_inferred": "DE",
            "category_inferred": "education",
            "response_ms": 100,
            "review_flags": ["manual-provenance-review"],
        }
        slow = dict(fast)
        slow["response_ms"] = 1500
        fast_score, _ = gate.bondik_score(fast)
        slow_score, _ = gate.bondik_score(slow)
        self.assertGreater(fast_score, slow_score)
        self.assertLessEqual(fast_score - slow_score, 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
