from pathlib import Path
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
CHECKER_DIR = ROOT / "tools" / "checker"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import process_stream_health as health


class StreamRecoveryReportTests(unittest.TestCase):

    def setUp(self):
        self.common = {
            "api_url": "https://api.github.test",
            "repository": "Bondik/Test",
            "token": "test-token",
            "server_url": "https://github.test",
            "run_id": 123,
            "sha": "abc123",
        }

    def test_recovery_comment_posts_marker_for_new_run(self):
        with patch.object(
            health,
            "has_issue_comment_marker",
            return_value=False,
        ):
            with patch.object(
                health,
                "github_json",
                return_value={},
            ) as github_json:
                added = health.comment_stream_recovery(
                    **self.common,
                    channel="POLAR",
                    streak=5,
                    issue_number=9,
                )

        body = (
            github_json.call_args
            .kwargs["payload"]["body"]
        )

        self.assertIn(
            "<!-- bondik-stream:"
            "recovery:run:123 -->",
            body,
        )

        self.assertIn(
            "Previous failure streak: ×5",
            body,
        )

        self.assertTrue(added)

    def test_recovery_comment_skips_duplicate_same_run(self):
        with patch.object(
            health,
            "has_issue_comment_marker",
            return_value=True,
        ):
            with patch.object(
                health,
                "github_json",
            ) as github_json:
                added = health.comment_stream_recovery(
                    **self.common,
                    channel="POLAR",
                    streak=5,
                    issue_number=9,
                )

        self.assertFalse(added)
        github_json.assert_not_called()

    def test_recovery_report_is_added_before_issue_close(self):
        issues = [
            {
                "number": 9,
                "title": "🚨 Stream outage: POLAR",
            }
        ]

        events = []

        def fake_recovery(**kwargs):
            events.append("comment")
            return True

        def fake_close(**kwargs):
            events.append("close")

        output = io.StringIO()

        with patch.object(
            health,
            "list_open_issues",
            return_value=issues,
        ):
            with patch.object(
                health,
                "comment_stream_recovery",
                side_effect=fake_recovery,
                create=True,
            ):
                with patch.object(
                    health,
                    "close_issue",
                    side_effect=fake_close,
                ):
                    with redirect_stdout(output):
                        health.manage_issues(
                            **self.common,
                            repeated=[],
                            recovered=["POLAR"],
                            previous_streaks={
                                "POLAR": 5,
                            },
                        )

        self.assertEqual(
            events,
            [
                "comment",
                "close",
            ],
        )

        self.assertIn(
            "previous streak ×5",
            output.getvalue(),
        )

    def test_main_passes_previous_streaks_to_issue_manager(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            report = (
                temp_path
                / "stream-check-report.txt"
            )

            history = (
                temp_path
                / "stream-history.txt"
            )

            state = (
                temp_path
                / "stream-health-state.json"
            )

            report.write_text(
                (
                    "🐾 Bondik TV Ultimate\n"
                    "📺 Stream Health Report\n"
                ),
                encoding="utf-8",
            )

            args = SimpleNamespace(
                report=report,
                history=history,
                state=state,
            )

            required_env = {
                "GITHUB_TOKEN": "test-token",
                "GITHUB_API_URL": (
                    "https://api.github.test"
                ),
                "GITHUB_REPOSITORY": "Bondik/Test",
                "GITHUB_RUN_ID": "123",
                "GITHUB_SHA": "abc123",
            }

            def fake_require_env(name):
                return required_env[name]

            previous_report = (
                "❌ POLAR [stable]\n"
            )

            previous_streaks = {
                "POLAR": 5,
            }

            with patch.dict(
                health.os.environ,
                {
                    "GITHUB_SERVER_URL":
                    "https://github.test",
                },
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
                                previous_streaks,
                            ),
                        ):
                            with patch.object(
                                health,
                                "manage_issues",
                            ) as manage_issues:
                                result = health.main()

        self.assertEqual(result, 0)

        kwargs = (
            manage_issues
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["previous_streaks"],
            {
                "POLAR": 5,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
