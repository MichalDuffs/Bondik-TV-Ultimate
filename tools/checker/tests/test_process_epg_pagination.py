from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import process_epg_health as health


class EpgPaginationTests(unittest.TestCase):

    def test_github_paginated_list_combines_pages(self):
        page_one = [
            {"id": number}
            for number in range(100)
        ]

        page_two = [
            {"id": 100},
            {"id": 101},
        ]

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ) as github_json:
            result = health.github_paginated_list(
                (
                    "https://api.github.test/"
                    "repos/Bondik/Test/"
                    "issues?state=open"
                ),
                "test-token",
            )

        self.assertEqual(len(result), 102)
        self.assertEqual(github_json.call_count, 2)

        first_url = github_json.call_args_list[0].args[0]
        second_url = github_json.call_args_list[1].args[0]

        self.assertIn("per_page=100", first_url)
        self.assertIn("page=1", first_url)
        self.assertIn("page=2", second_url)

    def test_open_issues_reads_second_page(self):
        page_one = [
            {
                "number": number,
                "title": f"Issue {number}",
            }
            for number in range(1, 101)
        ]

        page_two = [
            {
                "number": 222,
                "title": "🚨 EPG outage: epgshare-cz",
            },
            {
                "number": 223,
                "title": "Pull request",
                "pull_request": {},
            },
        ]

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ):
            issues = health.list_open_issues(
                api_url="https://api.github.test",
                repository="Bondik/Test",
                token="test-token",
            )

        numbers = [
            issue["number"]
            for issue in issues
        ]

        self.assertIn(222, numbers)
        self.assertNotIn(223, numbers)

    def test_comment_marker_reads_second_page(self):
        marker = (
            "<!-- bondik-epg:"
            "outage:run:123 -->"
        )

        page_one = [
            {
                "body": f"Ordinary comment {number}"
            }
            for number in range(100)
        ]

        page_two = [
            {
                "body": "Bondik update\n" + marker
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
                api_url="https://api.github.test",
                repository="Bondik/Test",
                token="test-token",
                issue_number=7,
                marker=marker,
            )

        self.assertIs(found, True)

    def test_epg_labels_reads_second_page(self):
        page_one = [
            {
                "name": f"label-{number}"
            }
            for number in range(100)
        ]

        page_two = [
            {"name": "epg-health"},
            {"name": "automated"},
            {"name": "outage"},
        ]

        def fake_github_json(
            url,
            token,
            *,
            method="GET",
            payload=None,
        ):
            if method != "GET":
                raise AssertionError(
                    "Existing labels must not be created again"
                )

            if "page=2" in url:
                return page_two

            return page_one

        with patch.object(
            health,
            "github_json",
            side_effect=fake_github_json,
        ):
            health.ensure_epg_labels(
                api_url="https://api.github.test",
                repository="Bondik/Test",
                token="test-token",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
