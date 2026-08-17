import json
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHECKER_DIR))

import koberec_watchtower as tower


class KoberecWatchtowerTests(unittest.TestCase):

    def item(self, **overrides):
        base = {
            "review_bucket": "parking",
            "bondik_score": 50,
            "candidate_name": "Demo TV",
            "country_inferred": "CZ",
            "category_inferred": "general",
            "response_ms": 300,
            "stream_host": "demo.example.org",
            "url": "https://demo.example.org/live.m3u8",
            "review_flags": ["manual-provenance-review"],
            "source": "https://example.org/list.m3u",
        }
        base.update(overrides)
        return base

    def test_raw_ip_stays_parked(self):
        action, reasons = tower.classify_parking(self.item(
            review_flags=["manual-provenance-review", "raw-ip-host"]
        ))
        self.assertEqual(action, "keep-parked")
        self.assertIn("hard:raw-ip-host", reasons)

    def test_restream_domain_stays_parked(self):
        action, reasons = tower.classify_parking(self.item(
            review_flags=["suspicious-restream-domain"]
        ))
        self.assertEqual(action, "keep-parked")
        self.assertIn("hard:suspicious-restream-domain", reasons)

    def test_test_feed_stays_parked(self):
        action, reasons = tower.classify_parking(self.item(
            review_flags=["test-feed-path"]
        ))
        self.assertEqual(action, "keep-parked")
        self.assertIn("hard:test-feed-path", reasons)

    def test_geo_only_can_enter_manual_rescue_review(self):
        action, reasons = tower.classify_parking(self.item(
            review_flags=["manual-provenance-review", "geo-labelled"]
        ))
        self.assertEqual(action, "manual-rescue-review")
        self.assertIn("soft:geo-labelled", reasons)

    def test_hard_signal_wins_over_geo(self):
        action, _ = tower.classify_parking(self.item(
            review_flags=["geo-labelled", "raw-ip-host"]
        ))
        self.assertEqual(action, "keep-parked")

    def test_unrecognized_parking_reason_stays_parked(self):
        action, reasons = tower.classify_parking(self.item(
            review_flags=["manual-provenance-review"]
        ))
        self.assertEqual(action, "keep-parked")
        self.assertEqual(reasons, ["unrecognized-parking-reason"])

    def test_non_parking_candidates_are_not_inspected(self):
        candidates = [
            self.item(review_bucket="priority"),
            self.item(review_bucket="review"),
            self.item(review_bucket="parking", review_flags=["geo-labelled"]),
        ]
        parked, hard, rescue, stats = tower.analyze(candidates)
        self.assertEqual(len(parked), 1)
        self.assertEqual(len(hard), 0)
        self.assertEqual(len(rescue), 1)
        self.assertEqual(stats["input_candidates"], 3)
        self.assertEqual(stats["parking_candidates"], 1)

    def test_rescue_queue_is_sorted_by_bondik_score(self):
        candidates = [
            self.item(candidate_name="Low", bondik_score=20, review_flags=["geo-labelled"]),
            self.item(candidate_name="High", bondik_score=80, review_flags=["geo-labelled"]),
        ]
        _, _, rescue, _ = tower.analyze(candidates)
        self.assertEqual([item["candidate_name"] for item in rescue], ["High", "Low"])

    def test_domain_rows_group_candidates(self):
        candidates = [
            self.item(candidate_name="One", stream_host="same.example", review_flags=["raw-ip-host"]),
            self.item(candidate_name="Two", stream_host="same.example", review_flags=["geo-labelled"]),
        ]
        parked, _, _, _ = tower.analyze(candidates)
        rows = tower.domain_rows(parked)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidate_count"], 2)
        self.assertEqual(rows[0]["hard_count"], 1)
        self.assertEqual(rows[0]["rescue_review_count"], 1)

    def test_load_candidates_reads_gate_version(self):
        payload = {
            "candidate_gate_version": "0.5.1",
            "candidates": [self.item()],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidates.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            version, candidates = tower.load_candidates(path)
        self.assertEqual(version, "0.5.1")
        self.assertEqual(len(candidates), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
