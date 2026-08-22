import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

import promote_testing_to_stable as stable


class StablePromotionTests(unittest.TestCase):

    def channel(self):
        return {
            "id": "example-tv-cz",
            "name": "Example TV",
            "country": "CZ",
            "category": "general",
            "status": "testing",
            "stream": {
                "url": "https://example.com/live.m3u8",
            },
        }

    def report(self):
        return {
            "id": "example-tv-cz",
            "eligible": True,
            "counted_passes": 3,
            "required_passes": 3,
            "last_result": "pass",
            "stream_url": "https://example.com/live.m3u8",
        }

    def decision(self):
        return {
            "id": "example-tv-cz",
            "decision": "approve",
            "stream_url": "https://example.com/live.m3u8",
            "note": "Manual Bondik stable review completed.",
        }

    def test_clean_candidate_is_allowed(self):
        self.assertEqual(
            stable.promotion_reasons(
                self.channel(),
                self.report(),
                self.decision(),
            ),
            [],
        )

    def test_not_eligible_is_blocked(self):
        report = self.report()
        report["eligible"] = False

        reasons = stable.promotion_reasons(
            self.channel(),
            report,
            self.decision(),
        )

        self.assertIn(
            "promotion gate says not eligible",
            reasons,
        )

    def test_insufficient_passes_are_blocked(self):
        report = self.report()
        report["counted_passes"] = 2

        reasons = stable.promotion_reasons(
            self.channel(),
            report,
            self.decision(),
        )

        self.assertIn(
            "insufficient counted passes: 2/3",
            reasons,
        )

    def test_last_failure_is_blocked(self):
        report = self.report()
        report["last_result"] = "fail"

        reasons = stable.promotion_reasons(
            self.channel(),
            report,
            self.decision(),
        )

        self.assertIn(
            "last promotion-gate result is fail",
            reasons,
        )

    def test_report_url_mismatch_is_blocked(self):
        report = self.report()
        report["stream_url"] = (
            "https://example.com/old.m3u8"
        )

        reasons = stable.promotion_reasons(
            self.channel(),
            report,
            self.decision(),
        )

        self.assertIn(
            (
                "promotion report stream URL "
                "does not match current channel"
            ),
            reasons,
        )

    def test_decision_url_mismatch_is_blocked(self):
        decision = self.decision()
        decision["stream_url"] = (
            "https://example.com/old.m3u8"
        )

        reasons = stable.promotion_reasons(
            self.channel(),
            self.report(),
            decision,
        )

        self.assertIn(
            (
                "decision stream URL does not "
                "match current channel"
            ),
            reasons,
        )

    def test_non_testing_channel_is_blocked(self):
        channel = self.channel()
        channel["status"] = "stable"

        reasons = stable.promotion_reasons(
            channel,
            self.report(),
            self.decision(),
        )

        self.assertIn(
            "channel status is stable, not testing",
            reasons,
        )

    def test_status_replacement_changes_only_target(self):
        source = (
            "channels:\n"
            "  - id: first-tv\n"
            "    name: First TV\n"
            "    status: testing\n"
            "  - id: second-tv\n"
            "    name: Second TV\n"
            "    status: testing\n"
        )

        result = stable.promote_status_in_text(
            source,
            "second-tv",
        )

        self.assertIn(
            (
                "  - id: first-tv\n"
                "    name: First TV\n"
                "    status: testing\n"
            ),
            result,
        )

        self.assertIn(
            (
                "  - id: second-tv\n"
                "    name: Second TV\n"
                "    status: stable\n"
            ),
            result,
        )


if __name__ == "__main__":
    unittest.main()
