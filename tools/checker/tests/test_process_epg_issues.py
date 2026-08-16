from pathlib import Path
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import process_epg_health as health


class EpgHealthIssueTests(unittest.TestCase):

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

        with patch.object(
            health,
            "list_open_issues",
        ) as list_open:
            with redirect_stdout(output):
                health.manage_issues(
                    **self.common,
                    repeated=[],
                    recovered=[],
                )

        list_open.assert_not_called()

        self.assertIn(
            "No EPG issue action required.",
            output.getvalue(),
        )

    def test_epg_labels_include_health_automation_and_outage(self):
        names = [
            label["name"]
            for label in health.EPG_OUTAGE_LABELS
        ]

        self.assertEqual(
            names,
            [
                "epg-health",
                "automated",
                "outage",
            ],
        )

    def test_create_epg_issue_uses_expected_title(self):
        with patch.object(
            health,
            "ensure_epg_labels",
        ):
            with patch.object(
                health,
                "github_json",
                return_value={"number": 42},
            ) as github_json:

                issue = health.create_epg_issue(
                    **self.common,
                    source="epgshare-cz",
                )

        payload = github_json.call_args.kwargs[
            "payload"
        ]

        self.assertEqual(
            payload["title"],
            "🚨 EPG outage: epgshare-cz",
        )

        self.assertEqual(
            payload["labels"],
            [
                "epg-health",
                "automated",
                "outage",
            ],
        )

        self.assertEqual(
            issue["number"],
            42,
        )

    def test_repeated_failure_creates_issue(self):
        with patch.object(
            health,
            "list_open_issues",
            return_value=[],
        ):
            with patch.object(
                health,
                "create_epg_issue",
                return_value={
                    "number": 42,
                    "title": (
                        "🚨 EPG outage: epgshare-cz"
                    ),
                },
            ) as create_issue:

                health.manage_issues(
                    **self.common,
                    repeated=["epgshare-cz"],
                    recovered=[],
                )

        create_issue.assert_called_once_with(
            **self.common,
            source="epgshare-cz",
        )

    def test_repeated_failure_does_not_duplicate_open_issue(self):
        existing = {
            "number": 7,
            "title": "🚨 EPG outage: epgshare-cz",
        }

        with patch.object(
            health,
            "list_open_issues",
            return_value=[existing],
        ):
            with patch.object(
                health,
                "create_epg_issue",
            ) as create_issue:

                health.manage_issues(
                    **self.common,
                    repeated=["epgshare-cz"],
                    recovered=[],
                )

        create_issue.assert_not_called()

    def test_recovery_closes_matching_issue(self):
        existing = {
            "number": 9,
            "title": "🚨 EPG outage: epgshare-cz",
        }

        with patch.object(
            health,
            "list_open_issues",
            return_value=[existing],
        ):
            with patch.object(
                health,
                "close_issue",
            ) as close_issue:

                health.manage_issues(
                    **self.common,
                    repeated=[],
                    recovered=["epgshare-cz"],
                )

        close_issue.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common["repository"],
            token=self.common["token"],
            issue_number=9,
        )


    def test_epg_comment_milestones(self):
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
                    health.should_comment_on_streak(
                        streak
                    ),
                    should_comment,
                )

    def test_existing_epg_issue_gets_comment_at_streak_three(self):
        open_issues = [
            {
                "number": 7,
                "title": (
                    "🚨 EPG outage: epgshare-cz"
                ),
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(
                health,
                "comment_epg_issue",
            ) as comment_issue:
                with patch.object(
                    health,
                    "create_epg_issue",
                ) as create_issue:

                    health.manage_issues(
                        **self.common,
                        repeated=[
                            "epgshare-cz"
                        ],
                        recovered=[],
                        streaks={
                            "epgshare-cz": 3
                        },
                    )

        comment_issue.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common[
                "repository"
            ],
            token=self.common["token"],
            server_url=self.common[
                "server_url"
            ],
            run_id=self.common["run_id"],
            sha=self.common["sha"],
            source="epgshare-cz",
            streak=3,
            issue_number=7,
        )

        create_issue.assert_not_called()

    def test_existing_epg_issue_is_quiet_between_milestones(self):
        open_issues = [
            {
                "number": 7,
                "title": (
                    "🚨 EPG outage: epgshare-cz"
                ),
            }
        ]

        with patch.object(
            health,
            "list_open_issues",
            return_value=open_issues,
        ):
            with patch.object(
                health,
                "comment_epg_issue",
            ) as comment_issue:

                health.manage_issues(
                    **self.common,
                    repeated=[
                        "epgshare-cz"
                    ],
                    recovered=[],
                    streaks={
                        "epgshare-cz": 4
                    },
                )

        comment_issue.assert_not_called()

    def test_comment_epg_issue_posts_update(self):
        with patch.object(
            health,
            "github_json",
            return_value={},
        ) as github_json:

            health.comment_epg_issue(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=7,
            )

        call = github_json.call_args

        self.assertEqual(
            call.args[0],
            (
                "https://api.github.test/"
                "repos/Bondik/Test/"
                "issues/7/comments"
            ),
        )

        self.assertEqual(
            call.kwargs["method"],
            "POST",
        )

        body = call.kwargs[
            "payload"
        ]["body"]

        self.assertIn(
            "epgshare-cz",
            body,
        )

        self.assertIn(
            "×5",
            body,
        )

    def test_main_passes_current_streaks_to_issue_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            report = temp / (
                "epg-check-report.txt"
            )
            history = temp / (
                "epg-history.txt"
            )
            state = temp / (
                "epg-health-state.json"
            )

            report.write_text(
                """
📡 epgshare-cz
   └─ ❌ HTTP Error 503: Service Unavailable
""",
                encoding="utf-8",
            )

            args = SimpleNamespace(
                report=report,
                history=history,
                state=state,
            )

            env_values = {
                "GITHUB_API_URL": (
                    "https://api.github.test"
                ),
                "GITHUB_REPOSITORY": (
                    "Bondik/Test"
                ),
                "GITHUB_TOKEN": (
                    "test-token"
                ),
                "GITHUB_RUN_ID": "123",
                "GITHUB_SHA": "abc123",
            }

            def fake_require_env(name):
                return env_values[name]

            with patch.dict(
                health.os.environ,
                {
                    "GITHUB_ACTIONS": "true",
                    "GITHUB_SERVER_URL": (
                        "https://github.test"
                    ),
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
                        "load_previous_streaks",
                        return_value={
                            "epgshare-cz": 2
                        },
                    ):
                        with patch.object(
                            health,
                            "require_env",
                            side_effect=(
                                fake_require_env
                            ),
                        ):
                            with patch.object(
                                health,
                                "manage_issues",
                            ) as manage_issues:

                                result = (
                                    health.main()
                                )

            self.assertEqual(
                result,
                0,
            )

            kwargs = (
                manage_issues
                .call_args
                .kwargs
            )

            self.assertEqual(
                kwargs["streaks"],
                {
                    "epgshare-cz": 3
                },
            )


    def test_comment_epg_recovery_posts_update(self):
        with patch.object(
            health,
            "github_json",
            return_value={},
        ) as github_json:

            health.comment_epg_recovery(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=9,
            )

        call = github_json.call_args

        self.assertEqual(
            call.args[0],
            (
                "https://api.github.test/"
                "repos/Bondik/Test/"
                "issues/9/comments"
            ),
        )

        self.assertEqual(
            call.kwargs["method"],
            "POST",
        )

        body = call.kwargs[
            "payload"
        ]["body"]

        self.assertIn(
            "epgshare-cz",
            body,
        )

        self.assertIn(
            "recovered",
            body.lower(),
        )

        self.assertIn(
            "×5",
            body,
        )

    def test_recovery_comments_before_closing_issue(self):
        existing = {
            "number": 9,
            "title": (
                "🚨 EPG outage: epgshare-cz"
            ),
        }

        events = []

        with patch.object(
            health,
            "list_open_issues",
            return_value=[existing],
        ):
            with patch.object(
                health,
                "comment_epg_recovery",
                side_effect=lambda **kwargs: (
                    events.append("comment")
                ),
            ) as recovery_comment:
                with patch.object(
                    health,
                    "close_issue",
                    side_effect=lambda **kwargs: (
                        events.append("close")
                    ),
                ) as close_issue:

                    health.manage_issues(
                        **self.common,
                        repeated=[],
                        recovered=[
                            "epgshare-cz"
                        ],
                        previous_streaks={
                            "epgshare-cz": 5
                        },
                    )

        self.assertEqual(
            events,
            [
                "comment",
                "close",
            ],
        )

        recovery_comment.assert_called_once_with(
            api_url=self.common["api_url"],
            repository=self.common[
                "repository"
            ],
            token=self.common["token"],
            server_url=self.common[
                "server_url"
            ],
            run_id=self.common["run_id"],
            sha=self.common["sha"],
            source="epgshare-cz",
            streak=5,
            issue_number=9,
        )

        close_issue.assert_called_once()

    def test_recovery_without_open_issue_does_not_comment(self):
        with patch.object(
            health,
            "list_open_issues",
            return_value=[],
        ):
            with patch.object(
                health,
                "comment_epg_recovery",
            ) as recovery_comment:
                with patch.object(
                    health,
                    "close_issue",
                ) as close_issue:

                    health.manage_issues(
                        **self.common,
                        repeated=[],
                        recovered=[
                            "epgshare-cz"
                        ],
                        previous_streaks={
                            "epgshare-cz": 5
                        },
                    )

        recovery_comment.assert_not_called()
        close_issue.assert_not_called()

    def test_main_passes_previous_streaks_to_issue_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            report = temp / (
                "epg-check-report.txt"
            )
            history = temp / (
                "epg-history.txt"
            )
            state = temp / (
                "epg-health-state.json"
            )

            report.write_text(
                """
📡 epgshare-cz
   ├─ ✅ 4/4 IDs found
   └─ ✅ 4/4 IDs have fresh programme data
""",
                encoding="utf-8",
            )

            args = SimpleNamespace(
                report=report,
                history=history,
                state=state,
            )

            previous = {
                "epgshare-cz": 5
            }

            env_values = {
                "GITHUB_API_URL": (
                    "https://api.github.test"
                ),
                "GITHUB_REPOSITORY": (
                    "Bondik/Test"
                ),
                "GITHUB_TOKEN": (
                    "test-token"
                ),
                "GITHUB_RUN_ID": "123",
                "GITHUB_SHA": "abc123",
            }

            def fake_require_env(name):
                return env_values[name]

            with patch.dict(
                health.os.environ,
                {
                    "GITHUB_ACTIONS": "true",
                    "GITHUB_SERVER_URL": (
                        "https://github.test"
                    ),
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
                        "load_previous_streaks",
                        return_value=previous,
                    ):
                        with patch.object(
                            health,
                            "require_env",
                            side_effect=(
                                fake_require_env
                            ),
                        ):
                            with patch.object(
                                health,
                                "manage_issues",
                            ) as manage_issues:

                                result = (
                                    health.main()
                                )

            self.assertEqual(
                result,
                0,
            )

            kwargs = (
                manage_issues
                .call_args
                .kwargs
            )

            self.assertEqual(
                kwargs[
                    "previous_streaks"
                ],
                previous,
            )

            self.assertEqual(
                kwargs["recovered"],
                [
                    "epgshare-cz"
                ],
            )


    def test_outage_comment_skips_duplicate_same_run(self):
        run_marker = (
            "<!-- bondik-epg:outage:run:123 -->"
        )

        comments = [
            {
                "body": (
                    "Previous update\n"
                    + run_marker
                )
            }
        ]

        with patch.object(
            health,
            "github_json",
            return_value=comments,
        ) as github_json:

            posted = health.comment_epg_issue(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=7,
            )

        self.assertIs(
            posted,
            False,
        )

        self.assertEqual(
            github_json.call_count,
            1,
        )

        call = github_json.call_args

        self.assertEqual(
            call.kwargs.get(
                "method",
                "GET",
            ),
            "GET",
        )

    def test_outage_comment_posts_marker_for_new_run(self):
        run_marker = (
            "<!-- bondik-epg:outage:run:123 -->"
        )

        with patch.object(
            health,
            "github_json",
            side_effect=[
                [],
                {},
            ],
        ) as github_json:

            posted = health.comment_epg_issue(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=7,
            )

        self.assertIs(
            posted,
            True,
        )

        self.assertEqual(
            github_json.call_count,
            2,
        )

        first_call = (
            github_json.call_args_list[0]
        )

        self.assertEqual(
            first_call.kwargs.get(
                "method",
                "GET",
            ),
            "GET",
        )

        second_call = (
            github_json.call_args_list[1]
        )

        self.assertEqual(
            second_call.kwargs["method"],
            "POST",
        )

        body = second_call.kwargs[
            "payload"
        ]["body"]

        self.assertIn(
            run_marker,
            body,
        )

    def test_recovery_comment_skips_duplicate_same_run(self):
        run_marker = (
            "<!-- bondik-epg:recovery:run:123 -->"
        )

        comments = [
            {
                "body": (
                    "Previous recovery\n"
                    + run_marker
                )
            }
        ]

        with patch.object(
            health,
            "github_json",
            return_value=comments,
        ) as github_json:

            posted = health.comment_epg_recovery(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=9,
            )

        self.assertIs(
            posted,
            False,
        )

        self.assertEqual(
            github_json.call_count,
            1,
        )

        call = github_json.call_args

        self.assertEqual(
            call.kwargs.get(
                "method",
                "GET",
            ),
            "GET",
        )

    def test_recovery_comment_posts_marker_for_new_run(self):
        run_marker = (
            "<!-- bondik-epg:recovery:run:123 -->"
        )

        with patch.object(
            health,
            "github_json",
            side_effect=[
                [],
                {},
            ],
        ) as github_json:

            posted = health.comment_epg_recovery(
                **self.common,
                source="epgshare-cz",
                streak=5,
                issue_number=9,
            )

        self.assertIs(
            posted,
            True,
        )

        self.assertEqual(
            github_json.call_count,
            2,
        )

        second_call = (
            github_json.call_args_list[1]
        )

        self.assertEqual(
            second_call.kwargs["method"],
            "POST",
        )

        body = second_call.kwargs[
            "payload"
        ]["body"]

        self.assertIn(
            run_marker,
            body,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
