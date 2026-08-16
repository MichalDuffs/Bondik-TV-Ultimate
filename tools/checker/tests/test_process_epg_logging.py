from pathlib import Path
import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import process_epg_health as health


class EpgIssueLoggingTests(unittest.TestCase):

    def setUp(self):
        self.common = {
            "api_url": "https://api.github.test",
            "repository": "Bondik/Test",
            "token": "test-token",
            "server_url": "https://github.test",
            "run_id": 123,
            "sha": "abc123",
        }

    def test_duplicate_outage_comment_logs_as_already_recorded(self):
        issues = [
            {
                "number": 7,
                "title": "🚨 EPG outage: epgshare-cz",
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
                "comment_epg_issue",
                return_value=False,
            ):
                with redirect_stdout(output):
                    health.manage_issues(
                        **self.common,
                        repeated=["epgshare-cz"],
                        recovered=[],
                        streaks={
                            "epgshare-cz": 3,
                        },
                    )

        text = output.getvalue()

        self.assertNotIn(
            "Updated EPG issue",
            text,
        )

        self.assertIn(
            "already recorded",
            text,
        )

    def test_duplicate_recovery_comment_logs_as_already_recorded(self):
        issues = [
            {
                "number": 9,
                "title": "🚨 EPG outage: epgshare-cz",
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
                "comment_epg_recovery",
                return_value=False,
            ):
                with patch.object(
                    health,
                    "close_issue",
                ) as close_issue:
                    with redirect_stdout(output):
                        health.manage_issues(
                            **self.common,
                            repeated=[],
                            recovered=["epgshare-cz"],
                            previous_streaks={
                                "epgshare-cz": 5,
                            },
                        )

        text = output.getvalue()

        self.assertNotIn(
            "Added EPG recovery report",
            text,
        )

        self.assertIn(
            "already recorded",
            text,
        )

        close_issue.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
