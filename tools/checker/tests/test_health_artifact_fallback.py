from pathlib import Path
import importlib.util
import io
import sys
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]

CHECKER_DIR = ROOT / "tools" / "checker"
UPDATER_DIR = ROOT / "tools" / "updater"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import process_stream_health as stream_health


def load_epg_health():
    path = (
        UPDATER_DIR
        / "process_epg_health.py"
    )

    spec = importlib.util.spec_from_file_location(
        "process_epg_health_fallback",
        path,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


epg_health = load_epg_health()


def make_zip(files):
    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
    ) as archive:
        for name, content in files.items():
            archive.writestr(
                name,
                content,
            )

    return buffer.getvalue()


def artifacts(prefix):
    return [
        {
            "id": 200,
            "name": f"{prefix}-200",
            "expired": False,
            "created_at": "2026-08-16T12:00:00Z",
            "workflow_run": {
                "id": 200,
            },
        },
        {
            "id": 100,
            "name": f"{prefix}-100",
            "expired": False,
            "created_at": "2026-08-15T12:00:00Z",
            "workflow_run": {
                "id": 100,
            },
        },
    ]


class ArtifactFallbackTests(unittest.TestCase):

    def test_stream_skips_corrupt_newest_artifact(
        self,
    ):
        older = make_zip(
            {
                "stream-check-report.txt":
                    "❌ POLAR [stable]\n",
                "stream-health-state.json":
                    '{"POLAR": 4}\n',
            }
        )

        with patch.object(
            stream_health,
            "github_paginated_collection",
            return_value=artifacts(
                "stream-check"
            ),
        ):
            with patch.object(
                stream_health,
                "github_request",
                side_effect=[
                    b"not-a-zip",
                    older,
                ],
            ) as request:
                report, state = (
                    stream_health
                    .find_previous_health_data(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )
                )

        self.assertEqual(
            state,
            {
                "POLAR": 4,
            },
        )

        self.assertIn(
            "POLAR",
            report,
        )

        self.assertEqual(
            request.call_count,
            2,
        )

    def test_stream_skips_unusable_newest_artifact(
        self,
    ):
        unusable = make_zip(
            {
                "other.txt": "nothing useful\n",
            }
        )

        older = make_zip(
            {
                "stream-check-report.txt":
                    "❌ POLAR [stable]\n",
                "stream-health-state.json":
                    '{"POLAR": 4}\n',
            }
        )

        with patch.object(
            stream_health,
            "github_paginated_collection",
            return_value=artifacts(
                "stream-check"
            ),
        ):
            with patch.object(
                stream_health,
                "github_request",
                side_effect=[
                    unusable,
                    older,
                ],
            ) as request:
                report, state = (
                    stream_health
                    .find_previous_health_data(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )
                )

        self.assertEqual(
            state,
            {
                "POLAR": 4,
            },
        )

        self.assertIn(
            "POLAR",
            report,
        )

        self.assertEqual(
            request.call_count,
            2,
        )

    def test_epg_skips_corrupt_newest_artifact(
        self,
    ):
        older = make_zip(
            {
                "epg-health-state.json":
                    '{"epgshare-cz": 5}\n',
            }
        )

        with patch.object(
            epg_health,
            "github_paginated_collection",
            return_value=artifacts(
                "epg-check"
            ),
        ):
            with patch.object(
                epg_health,
                "github_request",
                side_effect=[
                    b"not-a-zip",
                    older,
                ],
            ) as request:
                state = (
                    epg_health
                    .find_previous_health_state(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )
                )

        self.assertEqual(
            state,
            {
                "epgshare-cz": 5,
            },
        )

        self.assertEqual(
            request.call_count,
            2,
        )

    def test_epg_skips_artifact_without_state(
        self,
    ):
        unusable = make_zip(
            {
                "other.txt": "nothing useful\n",
            }
        )

        older = make_zip(
            {
                "epg-health-state.json":
                    '{"epgshare-cz": 5}\n',
            }
        )

        with patch.object(
            epg_health,
            "github_paginated_collection",
            return_value=artifacts(
                "epg-check"
            ),
        ):
            with patch.object(
                epg_health,
                "github_request",
                side_effect=[
                    unusable,
                    older,
                ],
            ) as request:
                state = (
                    epg_health
                    .find_previous_health_state(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )
                )

        self.assertEqual(
            state,
            {
                "epgshare-cz": 5,
            },
        )

        self.assertEqual(
            request.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
