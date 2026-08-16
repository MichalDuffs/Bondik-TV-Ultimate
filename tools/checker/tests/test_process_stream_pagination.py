from pathlib import Path
import io
import sys
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
CHECKER_DIR = ROOT / "tools" / "checker"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import process_stream_health as health


class StreamPaginationTests(unittest.TestCase):

    def test_paginated_list_combines_pages(self):
        page_one = [
            {"number": number}
            for number in range(100)
        ]

        page_two = [
            {"number": 100},
            {"number": 101},
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
                    "repos/Bondik/Test/issues"
                    "?state=open"
                ),
                "test-token",
            )

        self.assertEqual(
            len(result),
            102,
        )

        self.assertEqual(
            github_json.call_count,
            2,
        )

        first_url = (
            github_json.call_args_list[0].args[0]
        )

        second_url = (
            github_json.call_args_list[1].args[0]
        )

        self.assertIn(
            "per_page=100",
            first_url,
        )

        self.assertIn(
            "page=1",
            first_url,
        )

        self.assertIn(
            "page=2",
            second_url,
        )

    def test_paginated_collection_combines_artifact_pages(self):
        page_one = {
            "artifacts": [
                {"id": number}
                for number in range(100)
            ]
        }

        page_two = {
            "artifacts": [
                {"id": 100},
                {"id": 101},
            ]
        }

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ) as github_json:
            result = (
                health.github_paginated_collection(
                    (
                        "https://api.github.test/"
                        "repos/Bondik/Test/"
                        "actions/artifacts"
                    ),
                    "test-token",
                    key="artifacts",
                )
            )

        self.assertEqual(
            len(result),
            102,
        )

        self.assertEqual(
            github_json.call_count,
            2,
        )

        second_url = (
            github_json.call_args_list[1].args[0]
        )

        self.assertIn(
            "page=2",
            second_url,
        )

    def test_open_issues_reads_second_page(self):
        page_one = [
            {
                "number": number,
                "title": f"Other issue {number}",
            }
            for number in range(100)
        ]

        page_two = [
            {
                "number": 777,
                "title": "🚨 Stream outage: POLAR",
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
            issues = health.list_open_issues(
                api_url="https://api.github.test",
                repository="Bondik/Test",
                token="test-token",
            )

        self.assertEqual(
            health.find_issue_number(
                issues,
                "🚨 Stream outage: POLAR",
            ),
            777,
        )

    def test_outage_labels_reads_second_page(self):
        page_one = [
            {
                "name": "stream-health",
            },
            {
                "name": "automated",
            },
        ] + [
            {
                "name": f"dummy-{number}",
            }
            for number in range(98)
        ]

        page_two = [
            {
                "name": "outage",
            }
        ]

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ) as github_json:
            health.ensure_outage_labels(
                api_url="https://api.github.test",
                repository="Bondik/Test",
                token="test-token",
            )

        post_calls = [
            call
            for call in github_json.call_args_list
            if call.kwargs.get("method") == "POST"
        ]

        self.assertEqual(
            post_calls,
            [],
        )

    def test_previous_health_data_finds_artifact_on_second_page(
        self,
    ):
        page_one = {
            "artifacts": [
                {
                    "id": number,
                    "name": f"other-{number}",
                    "expired": False,
                    "created_at": (
                        "2026-08-16T10:00:00Z"
                    ),
                    "workflow_run": {
                        "id": number,
                    },
                }
                for number in range(100)
            ]
        }

        page_two = {
            "artifacts": [
                {
                    "id": 999,
                    "name": "stream-check-999",
                    "expired": False,
                    "created_at": (
                        "2026-08-15T10:00:00Z"
                    ),
                    "workflow_run": {
                        "id": 555,
                    },
                }
            ]
        }

        buffer = io.BytesIO()

        with zipfile.ZipFile(
            buffer,
            "w",
        ) as archive:
            archive.writestr(
                "stream-check-report.txt",
                "❌ POLAR [stable]\n",
            )

            archive.writestr(
                "stream-health-state.json",
                '{"POLAR": 4}\n',
            )

        archive_bytes = buffer.getvalue()

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ):
            with patch.object(
                health,
                "github_request",
                return_value=archive_bytes,
            ) as github_request:
                previous_report, previous_streaks = (
                    health.find_previous_health_data(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=123,
                        token="test-token",
                    )
                )

        self.assertEqual(
            previous_streaks,
            {
                "POLAR": 4,
            },
        )

        self.assertIn(
            "POLAR",
            previous_report,
        )

        github_request.assert_called_once()

        download_url = (
            github_request.call_args.args[0]
        )

        self.assertIn(
            "/actions/artifacts/999/zip",
            download_url,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
