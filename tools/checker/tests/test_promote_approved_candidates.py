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


if __name__ == "__main__":
    unittest.main()
