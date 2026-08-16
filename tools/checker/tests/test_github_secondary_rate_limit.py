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
        "process_epg_health_secondary_limit",
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


class GitHubSecondaryRateLimitTests(
    unittest.TestCase
):

    def check_secondary_403_retry_after(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "Retry-After": "7",
                "X-RateLimit-Remaining": "4999",
            },
            io.BytesIO(
                b"secondary rate limit exceeded"
            ),
        )

        response = io.BytesIO(
            b'{"ok": true}'
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=[
                error,
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
            2,
        )

        sleep.assert_called_once_with(
            7
        )

    def check_permission_403_not_retried(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "4999",
            },
            io.BytesIO(
                b"Resource not accessible"
            ),
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=error,
        ) as opener:
            with patch.object(
                module.time,
                "sleep",
            ) as sleep:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "HTTP 403",
                ):
                    module.github_request(
                        "https://api.github.test/test",
                        "test-token",
                    )

        self.assertEqual(
            opener.call_count,
            1,
        )

        sleep.assert_not_called()

    def test_stream_retries_secondary_403(
        self,
    ):
        self.check_secondary_403_retry_after(
            stream_health
        )

    def test_epg_retries_secondary_403(
        self,
    ):
        self.check_secondary_403_retry_after(
            epg_health
        )

    def test_stream_permission_403_is_not_retried(
        self,
    ):
        self.check_permission_403_not_retried(
            stream_health
        )

    def test_epg_permission_403_is_not_retried(
        self,
    ):
        self.check_permission_403_not_retried(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
