#!/usr/bin/env python3
from __future__ import annotations

import ast
import tempfile
from types import SimpleNamespace
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

class StreamHealthMainTests(unittest.TestCase):
    def test_main_processes_streak_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            report = temp_path / "stream-check-report.txt"
            history = temp_path / "stream-history.txt"
            state = temp_path / "stream-health-state.json"

            report.write_text(
                report_with_failures("POLAR"),
                encoding="utf-8",
            )

            args = SimpleNamespace(
                report=report,
                history=history,
                state=state,
            )

            required_env = {
                "GITHUB_TOKEN": "test-token",
                "GITHUB_API_URL": "https://api.github.test",
                "GITHUB_REPOSITORY": "Bondik/Test",
                "GITHUB_RUN_ID": "123",
                "GITHUB_SHA": "abc123",
            }

            def fake_require_env(name):
                return required_env[name]

            previous_report = report_with_failures("POLAR")

            with patch.dict(
                health.os.environ,
                {"GITHUB_SERVER_URL": "https://github.test"},
                clear=True,
            ):
                with patch.object(
                    health,
                    "parse_arguments",
                    return_value=args,
                ):
                    with patch.object(
                        health,
                        "require_env",
                        side_effect=fake_require_env,
                    ):
                        with patch.object(
                            health,
                            "find_previous_health_data",
                            return_value=(
                                previous_report,
                                {"POLAR": 2},
                            ),
                        ):
                            with patch.object(
                                health,
                                "manage_issues",
                            ) as manage_issues:
                                result = health.main()

            self.assertEqual(result, 0)

            self.assertEqual(
                health.parse_streak_state(
                    state.read_text(encoding="utf-8")
                ),
                {"POLAR": 3},
            )

            self.assertIn(
                "🚨 Repeated failure: POLAR (streak ×3)",
                history.read_text(encoding="utf-8"),
            )

            manage_issues.assert_called_once()

            call_kwargs = manage_issues.call_args.kwargs
            self.assertEqual(call_kwargs["repeated"], ["POLAR"])
            self.assertEqual(call_kwargs["recovered"], [])

            self.assertEqual(
                call_kwargs["streaks"],
                {"POLAR": 3},
            )

    def test_main_guard_is_at_module_level(self):
        source_path = CHECKER_DIR / "process_stream_health.py"

        tree = ast.parse(
            source_path.read_text(encoding="utf-8")
        )

        has_main_guard = False

        for node in tree.body:
            if not isinstance(node, ast.If):
                continue

            test = node.test

            if not isinstance(test, ast.Compare):
                continue

            if not isinstance(test.left, ast.Name):
                continue

            if test.left.id != "__name__":
                continue

            if len(test.comparators) != 1:
                continue

            comparator = test.comparators[0]

            if (
                isinstance(comparator, ast.Constant)
                and comparator.value == "__main__"
            ):
                has_main_guard = True
                break

        self.assertTrue(
            has_main_guard,
            '__main__ guard must exist at module level',
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


    def test_ensure_outage_labels_creates_only_missing_labels(self):
        existing_labels = [
            {"name": "automated"},
        ]

        with patch.object(
            health,
            "github_json",
            return_value=existing_labels,
        ) as github_json:
            health.ensure_outage_labels(
                api_url=self.common["api_url"],
                repository=self.common["repository"],
                token=self.common["token"],
            )

        first_call = github_json.call_args_list[0]

        self.assertEqual(
            first_call.args[0],
            (
                f'{self.common["api_url"]}/repos/'
                f'{self.common["repository"]}/labels?per_page=100'
            ),
        )

        created_names = {
            call.kwargs["payload"]["name"]
            for call in github_json.call_args_list[1:]
        }

        self.assertEqual(
            created_names,
            {"stream-health", "outage"},
        )

    def test_create_outage_issue_attaches_automation_labels(self):
        with patch.object(
            health,
            "ensure_outage_labels",
        ) as ensure_labels:
            with patch.object(
                health,
                "github_json",
                return_value={"number": 42},
            ) as github_json:
                issue = health.create_outage_issue(
                    api_url=self.common["api_url"],
                    repository=self.common["repository"],
                    token=self.common["token"],
                    server_url=self.common["server_url"],
                    run_id=self.common["run_id"],
                    sha=self.common["sha"],
                    channel="POLAR",
                )

        ensure_labels.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common["repository"],
            token=self.common["token"],
        )

        payload = github_json.call_args.kwargs["payload"]

        self.assertEqual(
            payload["labels"],
            ["stream-health", "automated", "outage"],
        )

        self.assertEqual(issue["number"], 42)

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


    def test_repeated_failure_comments_on_existing_issue_from_streak_three(self):
        open_issues = [
            {
                "number": 7,
                "title": "\U0001f6a8 Stream outage: POLAR",
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(
                health,
                "comment_outage_issue",
            ) as comment_issue:
                with patch.object(
                    health,
                    "create_outage_issue",
                ) as create_issue:
                    health.manage_issues(
                        **self.common,
                        repeated=["POLAR"],
                        recovered=[],
                        streaks={"POLAR": 3},
                    )

        comment_issue.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common["repository"],
            token=self.common["token"],
            server_url=self.common["server_url"],
            run_id=self.common["run_id"],
            sha=self.common["sha"],
            channel="POLAR",
            streak=3,
            issue_number=7,
        )

        create_issue.assert_not_called()

    def test_repeated_failure_does_not_comment_before_streak_three(self):
        open_issues = [
            {
                "number": 7,
                "title": "\U0001f6a8 Stream outage: POLAR",
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(
                health,
                "comment_outage_issue",
            ) as comment_issue:
                health.manage_issues(
                    **self.common,
                    repeated=["POLAR"],
                    recovered=[],
                    streaks={"POLAR": 2},
                )

        comment_issue.assert_not_called()


    def test_outage_comment_milestones(self):
        expected = {
            1: False,
            2: False,
            3: True,
            4: False,
            5: True,
            6: False,
            9: False,
            10: True,
            14: False,
            15: True,
            20: True,
        }

        for streak, should_comment in expected.items():
            with self.subTest(streak=streak):
                self.assertEqual(
                    health.should_comment_on_streak(streak),
                    should_comment,
                )

    def test_existing_issue_is_quiet_between_milestones(self):
        open_issues = [
            {
                "number": 7,
                "title": "\U0001f6a8 Stream outage: POLAR",
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(
                health,
                "comment_outage_issue",
            ) as comment_issue:
                health.manage_issues(
                    **self.common,
                    repeated=["POLAR"],
                    recovered=[],
                    streaks={"POLAR": 4},
                )

        comment_issue.assert_not_called()

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
