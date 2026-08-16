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
        "process_epg_health_rate_limit",
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


class GitHubRateLimitTests(unittest.TestCase):

    def check_retry_after(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "7",
            },
            io.BytesIO(
                b"rate limited"
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

    def check_primary_rate_limit_403(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1005",
            },
            io.BytesIO(
                b"rate limit exceeded"
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
                "time",
                return_value=1000,
            ):
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
            5
        )

    def test_stream_respects_retry_after(self):
        self.check_retry_after(
            stream_health
        )

    def test_epg_respects_retry_after(self):
        self.check_retry_after(
            epg_health
        )

    def test_stream_retries_primary_rate_limit_403(
        self,
    ):
        self.check_primary_rate_limit_403(
            stream_health
        )

    def test_epg_retries_primary_rate_limit_403(
        self,
    ):
        self.check_primary_rate_limit_403(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
