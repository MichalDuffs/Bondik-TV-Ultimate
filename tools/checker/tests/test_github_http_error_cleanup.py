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
        "process_epg_health_http_cleanup",
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


class GitHubHTTPErrorCleanupTests(
    unittest.TestCase
):

    def check_retryable_error_is_closed(
        self,
        module,
    ):
        body = io.BytesIO(
            b"temporary failure"
        )

        temporary_error = (
            urllib.error.HTTPError(
                "https://api.github.test/test",
                503,
                "Service Unavailable",
                None,
                body,
            )
        )

        response = io.BytesIO(
            b'{"ok": true}'
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=[
                temporary_error,
                response,
            ],
        ):
            with patch(
                "time.sleep"
            ):
                result = module.github_request(
                    "https://api.github.test/test",
                    "test-token",
                )

        self.assertEqual(
            result,
            b'{"ok": true}',
        )

        self.assertTrue(
            body.closed,
            "Retryable HTTPError body was not closed",
        )

    def check_permanent_error_is_closed(
        self,
        module,
    ):
        body = io.BytesIO(
            b'{"message":"Not Found"}'
        )

        permanent_error = (
            urllib.error.HTTPError(
                "https://api.github.test/missing",
                404,
                "Not Found",
                None,
                body,
            )
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=permanent_error,
        ):
            with patch(
                "time.sleep"
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "HTTP 404",
                ):
                    module.github_request(
                        (
                            "https://api.github.test/"
                            "missing"
                        ),
                        "test-token",
                    )

        self.assertTrue(
            body.closed,
            "Permanent HTTPError body was not closed",
        )

    def test_stream_closes_retryable_http_error(
        self,
    ):
        self.check_retryable_error_is_closed(
            stream_health
        )

    def test_stream_closes_permanent_http_error(
        self,
    ):
        self.check_permanent_error_is_closed(
            stream_health
        )

    def test_epg_closes_retryable_http_error(
        self,
    ):
        self.check_retryable_error_is_closed(
            epg_health
        )

    def test_epg_closes_permanent_http_error(
        self,
    ):
        self.check_permanent_error_is_closed(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
