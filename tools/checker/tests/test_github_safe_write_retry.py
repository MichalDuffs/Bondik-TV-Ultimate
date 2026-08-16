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
        "process_epg_health_safe_write_retry",
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


class GitHubSafeWriteRetryTests(
    unittest.TestCase
):

    def check_post_503_is_not_retried(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/comments",
            503,
            "Service Unavailable",
            None,
            io.BytesIO(
                b"temporary failure"
            ),
        )

        response = io.BytesIO(
            b'{"created": true}'
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
                with self.assertRaisesRegex(
                    RuntimeError,
                    "HTTP 503",
                ):
                    module.github_request(
                        "https://api.github.test/comments",
                        "test-token",
                        method="POST",
                        payload={
                            "body": "Bondik"
                        },
                    )

        self.assertEqual(
            opener.call_count,
            1,
        )

        sleep.assert_not_called()

    def check_post_urlerror_is_not_retried(
        self,
        module,
    ):
        error = urllib.error.URLError(
            "connection lost"
        )

        response = io.BytesIO(
            b'{"created": true}'
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
                with self.assertRaisesRegex(
                    RuntimeError,
                    "connection lost",
                ):
                    module.github_request(
                        "https://api.github.test/comments",
                        "test-token",
                        method="POST",
                        payload={
                            "body": "Bondik"
                        },
                    )

        self.assertEqual(
            opener.call_count,
            1,
        )

        sleep.assert_not_called()

    def check_post_rate_limit_is_retried(
        self,
        module,
    ):
        error = urllib.error.HTTPError(
            "https://api.github.test/comments",
            429,
            "Too Many Requests",
            {
                "Retry-After": "2",
            },
            io.BytesIO(
                b"rate limited"
            ),
        )

        response = io.BytesIO(
            b'{"created": true}'
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
                    "https://api.github.test/comments",
                    "test-token",
                    method="POST",
                    payload={
                        "body": "Bondik"
                    },
                )

        self.assertEqual(
            result,
            b'{"created": true}',
        )

        self.assertEqual(
            opener.call_count,
            2,
        )

        sleep.assert_called_once_with(
            2
        )

    def test_stream_post_503_is_not_retried(self):
        self.check_post_503_is_not_retried(
            stream_health
        )

    def test_epg_post_503_is_not_retried(self):
        self.check_post_503_is_not_retried(
            epg_health
        )

    def test_stream_post_urlerror_is_not_retried(self):
        self.check_post_urlerror_is_not_retried(
            stream_health
        )

    def test_epg_post_urlerror_is_not_retried(self):
        self.check_post_urlerror_is_not_retried(
            epg_health
        )

    def test_stream_post_rate_limit_is_retried(self):
        self.check_post_rate_limit_is_retried(
            stream_health
        )

    def test_epg_post_rate_limit_is_retried(self):
        self.check_post_rate_limit_is_retried(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
