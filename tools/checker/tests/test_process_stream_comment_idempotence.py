from pathlib import Path
import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
CHECKER_DIR = ROOT / "tools" / "checker"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import process_stream_health as health


class StreamCommentIdempotenceTests(unittest.TestCase):

    def setUp(self):
        self.common = {
            "api_url": "https://api.github.test",
            "repository": "Bondik/Test",
            "token": "test-token",
            "server_url": "https://github.test",
            "run_id": 123,
            "sha": "abc123",
        }

    def test_comment_marker_reads_second_page(self):
        marker = (
            "<!-- bondik-stream:"
            "outage:run:123 -->"
        )

        page_one = [
            {
                "body": f"Comment {number}",
            }
            for number in range(100)
        ]

        page_two = [
            {
                "body": (
                    "Existing automated comment\n"
                    f"{marker}"
                ),
            }
        ]

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ):
            found = health.has_issue_comment_marker(
                api_url=self.common["api_url"],
                repository=self.common["repository"],
                token=self.common["token"],
                issue_number=7,
                marker=marker,
            )

        self.assertTrue(found)

    def test_outage_comment_posts_marker_for_new_run(self):
        with patch.object(
            health,
            "has_issue_comment_marker",
            return_value=False,
            create=True,
        ):
            with patch.object(
                health,
                "github_json",
                return_value={},
            ) as github_json:
                added = health.comment_outage_issue(
                    **self.common,
                    channel="POLAR",
                    streak=5,
                    issue_number=7,
                )

        call = github_json.call_args

        body = call.kwargs[
            "payload"
        ]["body"]

        self.assertIn(
            "<!-- bondik-stream:"
            "outage:run:123 -->",
            body,
        )

        self.assertTrue(added)

    def test_outage_comment_skips_duplicate_same_run(self):
        with patch.object(
            health,
            "has_issue_comment_marker",
            return_value=True,
            create=True,
        ):
            with patch.object(
                health,
                "github_json",
            ) as github_json:
                added = health.comment_outage_issue(
                    **self.common,
                    channel="POLAR",
                    streak=5,
                    issue_number=7,
                )

        self.assertFalse(added)
        github_json.assert_not_called()

    def test_duplicate_outage_comment_logs_as_already_recorded(
        self,
    ):
        issues = [
            {
                "number": 7,
                "title": "🚨 Stream outage: POLAR",
            }
        ]

        output = io.StringIO()

        with patch.object(
            health,
            "list_open_issues",
            return_value=issues,
        ):
            with patch.object(
                health,
                "comment_outage_issue",
                return_value=False,
            ):
                with redirect_stdout(output):
                    health.manage_issues(
                        **self.common,
                        repeated=["POLAR"],
                        recovered=[],
                        streaks={
                            "POLAR": 3,
                        },
                    )

        text = output.getvalue()

        self.assertNotIn(
            "Updated issue",
            text,
        )

        self.assertIn(
            "already recorded",
            text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
