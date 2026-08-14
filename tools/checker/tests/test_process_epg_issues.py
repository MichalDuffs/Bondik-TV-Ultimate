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


if __name__ == "__main__":
    unittest.main(verbosity=2)
