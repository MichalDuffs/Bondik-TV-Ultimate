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
        "process_epg_health_unusable_history",
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


class UnusableArtifactHistoryTests(
    unittest.TestCase
):

    def test_stream_raises_if_all_artifacts_corrupt(
        self,
    ):
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
                    b"broken-200",
                    b"broken-100",
                ],
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "No usable stream health artifact",
                ):
                    stream_health.find_previous_health_data(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )

    def test_stream_raises_if_all_artifacts_empty(
        self,
    ):
        empty_200 = make_zip(
            {
                "other.txt": "Borys was here\n",
            }
        )

        empty_100 = make_zip(
            {
                "another.txt": "still Borys\n",
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
                    empty_200,
                    empty_100,
                ],
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "No usable stream health artifact",
                ):
                    stream_health.find_previous_health_data(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )

    def test_epg_raises_if_all_artifacts_corrupt(
        self,
    ):
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
                    b"broken-200",
                    b"broken-100",
                ],
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "No usable EPG health artifact",
                ):
                    epg_health.find_previous_health_state(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )

    def test_epg_raises_if_all_states_missing(
        self,
    ):
        empty_200 = make_zip(
            {
                "other.txt": "Borys was here\n",
            }
        )

        empty_100 = make_zip(
            {
                "another.txt": "still Borys\n",
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
                    empty_200,
                    empty_100,
                ],
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "No usable EPG health artifact",
                ):
                    epg_health.find_previous_health_state(
                        api_url=(
                            "https://api.github.test"
                        ),
                        repository="Bondik/Test",
                        run_id=999,
                        token="test-token",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
