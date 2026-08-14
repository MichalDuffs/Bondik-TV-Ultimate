#!/usr/bin/env python3
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

CHECKER_DIR = Path(__file__).resolve().parents[1]
if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import process_stream_health as health


def report_with_failures(*channels: str) -> str:
    lines = [
        "🐾 Bondik TV Ultimate",
        "📺 Stream Health Report",
        "============================================================",
    ]
    for channel in channels:
        lines.extend(
            [
                f"❌ {channel} [stable]",
                "   └─ simulated failure",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


class StreamHealthHistoryTests(unittest.TestCase):
    def test_extract_failures_returns_unique_stable_channels(self):
        report = "\n".join(
            [
                "❌ POLAR [stable]",
                "❌ POLAR [stable]",
                "❌ JOJ [stable]",
                "❌ Praha TV [testing]",
                "✅ WAU [stable]",
            ]
        )

        self.assertEqual(health.extract_failures(report), {"POLAR", "JOJ"})

    def test_baseline_marks_current_failures_as_new(self):
        history, repeated, recovered = health.build_history({"POLAR"}, None)

        self.assertIn("ℹ️ No previous report available - baseline created.", history)
        self.assertIn("⚠️ New failure: POLAR", history)
        self.assertEqual(repeated, [])
        self.assertEqual(recovered, [])

    def test_new_failure_is_detected(self):
        previous = report_with_failures()

        history, repeated, recovered = health.build_history({"POLAR"}, previous)

        self.assertIn("⚠️ New failure: POLAR", history)
        self.assertNotIn("🚨 Repeated failure:", history)
        self.assertEqual(repeated, [])
        self.assertEqual(recovered, [])

    def test_repeated_failure_is_detected(self):
        previous = report_with_failures("POLAR")

        history, repeated, recovered = health.build_history({"POLAR"}, previous)

        self.assertIn("🚨 Repeated failure: POLAR", history)
        self.assertEqual(repeated, ["POLAR"])
        self.assertEqual(recovered, [])

    def test_recovery_is_detected(self):
        previous = report_with_failures("POLAR")

        history, repeated, recovered = health.build_history(set(), previous)

        self.assertIn("✅ Recovered since previous run: POLAR", history)
        self.assertEqual(repeated, [])
        self.assertEqual(recovered, ["POLAR"])

    def test_mixed_new_repeated_and_recovered_state(self):
        previous = report_with_failures("POLAR", "WAU")

        history, repeated, recovered = health.build_history(
            {"POLAR", "JOJ"},
            previous,
        )

        self.assertIn("⚠️ New failure: JOJ", history)
        self.assertIn("🚨 Repeated failure: POLAR", history)
        self.assertIn("✅ Recovered since previous run: WAU", history)
        self.assertEqual(repeated, ["POLAR"])
        self.assertEqual(recovered, ["WAU"])

    def test_healthy_state_remains_healthy(self):
        previous = report_with_failures()

        history, repeated, recovered = health.build_history(set(), previous)

        self.assertIn(
            "🟢 No stream health changes - all streams healthy.",
            history,
        )
        self.assertEqual(repeated, [])
        self.assertEqual(recovered, [])

class StreamHealthStreakTests(unittest.TestCase):
    def test_parse_streak_state(self):
        raw = '{"POLAR": 3, "JOJ": 1}'

        self.assertEqual(
            health.parse_streak_state(raw),
            {
                "POLAR": 3,
                "JOJ": 1,
            },
        )

    def test_parse_streak_state_rejects_invalid_value(self):
        with self.assertRaises(ValueError):
            health.parse_streak_state('{"POLAR": 0}')

    def test_advance_streaks_increments_failed_channels(self):
        streaks = health.advance_streaks(
            {"POLAR", "JOJ"},
            {
                "POLAR": 2,
                "WAU": 5,
            },
        )

        self.assertEqual(
            streaks,
            {
                "JOJ": 1,
                "POLAR": 3,
            },
        )

    def test_recovered_channel_is_removed_from_new_state(self):
        streaks = health.advance_streaks(
            {"POLAR"},
            {
                "POLAR": 2,
                "WAU": 4,
            },
        )

        self.assertEqual(
            streaks,
            {
                "POLAR": 3,
            },
        )


class StreamHealthIssueTests(unittest.TestCase):
    def setUp(self):
        self.common = {
            "api_url": "https://api.github.test",
            "repository": "Bondik/Test",
            "token": "test-token",
            "server_url": "https://github.test",
            "run_id": 123,
            "sha": "abc123",
        }

    def test_no_health_change_does_not_query_issues(self):
        output = io.StringIO()

        with patch.object(health, "list_open_issues") as list_open:
            with redirect_stdout(output):
                health.manage_issues(
                    **self.common,
                    repeated=[],
                    recovered=[],
                )

        list_open.assert_not_called()
        self.assertIn("No issue action required.", output.getvalue())

    def test_repeated_failure_creates_issue_when_none_exists(self):
        created_issue = {
            "number": 42,
            "title": "🚨 Stream outage: POLAR",
        }

        with patch.object(health, "list_open_issues", return_value=[]):
            with patch.object(
                health,
                "create_outage_issue",
                return_value=created_issue,
            ) as create_issue:
                with patch.object(health, "close_issue") as close_issue:
                    health.manage_issues(
                        **self.common,
                        repeated=["POLAR"],
                        recovered=[],
                    )

        create_issue.assert_called_once()
        close_issue.assert_not_called()

    def test_repeated_failure_does_not_duplicate_open_issue(self):
        open_issues = [
            {
                "number": 7,
                "title": "🚨 Stream outage: POLAR",
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(health, "create_outage_issue") as create_issue:
                health.manage_issues(
                    **self.common,
                    repeated=["POLAR"],
                    recovered=[],
                )

        create_issue.assert_not_called()

    def test_recovered_stream_closes_matching_issue(self):
        open_issues = [
            {
                "number": 9,
                "title": "🚨 Stream outage: POLAR",
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(health, "close_issue") as close_issue:
                health.manage_issues(
                    **self.common,
                    repeated=[],
                    recovered=["POLAR"],
                )

        close_issue.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common["repository"],
            token=self.common["token"],
            issue_number=9,
        )

    def test_recovered_stream_without_open_issue_is_safe(self):
        with patch.object(health, "list_open_issues", return_value=[]):
            with patch.object(health, "close_issue") as close_issue:
                health.manage_issues(
                    **self.common,
                    repeated=[],
                    recovered=["POLAR"],
                )

        close_issue.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
