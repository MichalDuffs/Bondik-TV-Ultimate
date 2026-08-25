import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

import promote_approved_candidates as promotion


class PromotionRiskTests(unittest.TestCase):

    def test_clean_https_candidate_is_allowed(self):
        candidate = {
            "url": "https://example.com/live/index.m3u8",
            "review_bucket": "priority",
            "review_flags": [],
        }

        self.assertEqual(
            promotion.promotion_risks(candidate),
            [],
        )

    def test_http_raw_ip_test_feed_is_blocked(self):
        candidate = {
            "url": (
                "http://88.212.15.19/"
                "live/test_cnn_prima_news/playlist.m3u8"
            ),
            "review_bucket": "priority",
            "review_flags": [],
        }

        risks = promotion.promotion_risks(candidate)

        self.assertIn(
            "unencrypted-or-non-https-stream",
            risks,
        )
        self.assertIn("raw-ip-host", risks)
        self.assertIn("test-feed-path", risks)

    def test_parking_candidate_is_blocked(self):
        candidate = {
            "url": "https://example.com/live/index.m3u8",
            "review_bucket": "parking",
            "review_flags": [],
        }

        self.assertIn(
            "candidate-parking-bucket",
            promotion.promotion_risks(candidate),
        )

    def test_risky_review_flags_are_blocked(self):
        candidate = {
            "url": "https://example.com/live/index.m3u8",
            "review_bucket": "priority",
            "review_flags": [
                "suspicious-restream-domain",
                "geo-labelled",
            ],
        }

        risks = promotion.promotion_risks(candidate)

        self.assertIn(
            "suspicious-restream-domain",
            risks,
        )
        self.assertIn("geo-labelled", risks)

    def test_duplicate_risk_is_reported_once(self):
        candidate = {
            "url": "https://127.0.0.1/live/index.m3u8",
            "review_bucket": "priority",
            "review_flags": ["raw-ip-host"],
        }

        risks = promotion.promotion_risks(candidate)

        self.assertEqual(
            risks.count("raw-ip-host"),
            1,
        )


class ProvenanceTests(unittest.TestCase):

    def valid_decision(self):
        return {
            "url": "https://example.com/live/index.m3u8",
            "decision": "approve",
            "provenance": {
                "verified": True,
                "website": "https://example.com/",
                "evidence": [
                    "https://example.com/live/",
                ],
                "note": "Official broadcaster page confirms the stream.",
            },
        }

    def test_valid_provenance_is_accepted(self):
        provenance, errors = promotion.validate_provenance(
            self.valid_decision()
        )

        self.assertEqual(errors, [])
        self.assertTrue(provenance["verified"])
        self.assertEqual(
            provenance["website"],
            "https://example.com/",
        )

    def test_missing_provenance_is_rejected(self):
        provenance, errors = promotion.validate_provenance(
            {
                "url": "https://example.com/live/index.m3u8",
                "decision": "approve",
            }
        )

        self.assertEqual(provenance, {})
        self.assertIn("missing provenance object", errors)

    def test_unverified_provenance_is_rejected(self):
        decision = self.valid_decision()
        decision["provenance"]["verified"] = False

        _, errors = promotion.validate_provenance(decision)

        self.assertIn("provenance not verified", errors)

    def test_missing_evidence_is_rejected(self):
        decision = self.valid_decision()
        decision["provenance"]["evidence"] = []

        _, errors = promotion.validate_provenance(decision)

        self.assertIn("missing provenance evidence", errors)

    def test_build_channel_preserves_provenance(self):
        decision = self.valid_decision()

        provenance, errors = promotion.validate_provenance(
            decision
        )

        self.assertEqual(errors, [])

        channel = promotion.build_channel(
            {
                "candidate_name": "Example TV",
                "url": "https://example.com/live/index.m3u8",
                "validation": "hls-segment",
                "source": "https://example.org/source.m3u",
                "tvg_id": "ExampleTV.cz",
            },
            "CZ",
            "general",
            provenance,
        )

        self.assertEqual(
            channel["metadata"]["website"],
            "https://example.com/",
        )
        self.assertTrue(
            channel["metadata"]["provenance"]["verified"]
        )
        self.assertEqual(
            channel["metadata"]["provenance"]["evidence"],
            ["https://example.com/live/"],
        )


    def test_manual_category_override_wins(self):
        candidate = {
            "category_inferred": "",
        }

        decision = {
            "category": "news",
        }

        self.assertEqual(
            promotion.resolve_category(
                candidate,
                decision,
            ),
            "news",
        )

    def test_build_channel_accepts_manual_channel_id(self):
        decision = self.valid_decision()

        provenance, errors = promotion.validate_provenance(
            decision
        )

        self.assertEqual(errors, [])

        channel = promotion.build_channel(
            {
                "candidate_name": "????????? ?????",
                "url": "https://example.com/live/index.m3u8",
                "validation": "hls-segment",
                "source": "https://example.org/source.m3u",
                "tvg_id": "CurrentTimeTV.cz@SD",
            },
            "CZ",
            "news",
            provenance,
            "current-time-tv-cz",
        )

        self.assertEqual(
            channel["id"],
            "current-time-tv-cz",
        )


if __name__ == "__main__":
    unittest.main()
