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
        "process_epg_health_retry_budget",
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


class GitHubRetryDelayBudgetTests(
    unittest.TestCase
):

    def check_excessive_retry_after_fails_closed(
        self,
        module,
    ):
        body = io.BytesIO(
            b"rate limited"
        )

        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "86400",
            },
            body,
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
                    "retry delay",
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

        self.assertTrue(
            body.closed
        )

    def check_excessive_reset_fails_closed(
        self,
        module,
    ):
        body = io.BytesIO(
            b"primary rate limit exceeded"
        )

        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "87400",
            },
            body,
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=error,
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
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "retry delay",
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

        self.assertTrue(
            body.closed
        )

    def test_stream_excessive_retry_after_fails_closed(
        self,
    ):
        self.check_excessive_retry_after_fails_closed(
            stream_health
        )

    def test_epg_excessive_retry_after_fails_closed(
        self,
    ):
        self.check_excessive_retry_after_fails_closed(
            epg_health
        )

    def test_stream_excessive_reset_fails_closed(
        self,
    ):
        self.check_excessive_reset_fails_closed(
            stream_health
        )

    def test_epg_excessive_reset_fails_closed(
        self,
    ):
        self.check_excessive_reset_fails_closed(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
