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
        "process_epg_health_rate_limit_fallback",
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


class GitHubRateLimitFallbackTests(
    unittest.TestCase
):

    def check_429_without_headers_waits_60(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {},
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
            60
        )

    def check_invalid_secondary_retry_after_waits_60(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "Retry-After": "Borys",
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
            60
        )

    def test_stream_429_without_headers_waits_60(self):
        self.check_429_without_headers_waits_60(
            stream_health
        )

    def test_epg_429_without_headers_waits_60(self):
        self.check_429_without_headers_waits_60(
            epg_health
        )

    def test_stream_invalid_secondary_retry_after_waits_60(
        self,
    ):
        self.check_invalid_secondary_retry_after_waits_60(
            stream_health
        )

    def test_epg_invalid_secondary_retry_after_waits_60(
        self,
    ):
        self.check_invalid_secondary_retry_after_waits_60(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
