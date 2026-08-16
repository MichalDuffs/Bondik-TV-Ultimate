from pathlib import Path
import io
import sys
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import process_epg_health as health


class EpgArtifactPaginationTests(unittest.TestCase):

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
            result = health.github_paginated_collection(
                (
                    "https://api.github.test/"
                    "repos/Bondik/Test/"
                    "actions/artifacts"
                ),
                "test-token",
                key="artifacts",
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

    def test_previous_health_state_finds_artifact_on_second_page(self):
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
                    "name": "epg-check-999",
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
                "epg-health-state.json",
                '{"epgshare-cz": 4}\n',
            )

        archive_bytes = buffer.getvalue()

        with patch.object(
            health,
            "github_json",
            side_effect=[
                page_one,
                page_two,
            ],
        ) as github_json:
            with patch.object(
                health,
                "github_request",
                return_value=archive_bytes,
            ) as github_request:
                state = (
                    health.find_previous_health_state(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=123,
                        token="test-token",
                    )
                )

        self.assertEqual(
            state,
            {
                "epgshare-cz": 4,
            },
        )

        self.assertEqual(
            github_json.call_count,
            2,
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
