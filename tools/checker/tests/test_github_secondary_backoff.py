from pathlib import Path
import importlib.util
import io
import sys
import unittest
import urllib.error
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
        "process_epg_health_secondary_backoff",
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


class GitHubSecondaryBackoffTests(
    unittest.TestCase
):

    def check_secondary_backoff_increases(
        self,
        module,
    ):
        first_error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "4999",
            },
            io.BytesIO(
                b'{"message":"secondary rate limit exceeded"}'
            ),
        )

        second_error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "4999",
            },
            io.BytesIO(
                b'{"message":"secondary rate limit exceeded"}'
            ),
        )

        response = io.BytesIO(
            b'{"ok": true}'
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=[
                first_error,
                second_error,
                response,
            ],
        ) as opener:
            with patch.object(
                module.time,
                "sleep",
            ) as sleep:
                result = module.github_request(
                    "https://api.github.test/test",
                    "test-token",
                )

        self.assertEqual(
            result,
            b'{"ok": true}',
        )

        self.assertEqual(
            opener.call_count,
            3,
        )

        self.assertEqual(
            sleep.call_args_list,
            [
                unittest.mock.call(60),
                unittest.mock.call(120),
            ],
        )

    def test_stream_secondary_backoff_increases(
        self,
    ):
        self.check_secondary_backoff_increases(
            stream_health
        )

    def test_epg_secondary_backoff_increases(
        self,
    ):
        self.check_secondary_backoff_increases(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
