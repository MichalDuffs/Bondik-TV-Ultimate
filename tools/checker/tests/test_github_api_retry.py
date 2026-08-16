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
        "process_epg_health_retry",
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


class GitHubRetryTests(unittest.TestCase):

    def check_urlerror_retry(self, module):
        temporary_error = (
            urllib.error.URLError(
                "temporary network failure"
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
        ) as opener:
            with patch(
                "time.sleep"
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

        sleep.assert_called_once()

    def check_http_503_retry(self, module):
        temporary_error = (
            urllib.error.HTTPError(
                (
                    "https://api.github.test/"
                    "test"
                ),
                503,
                "Service Unavailable",
                None,
                io.BytesIO(
                    b"temporary"
                ),
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
        ) as opener:
            with patch(
                "time.sleep"
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

        sleep.assert_called_once()

    def check_http_404_not_retried(
        self,
        module,
    ):
        permanent_error = (
            urllib.error.HTTPError(
                (
                    "https://api.github.test/"
                    "missing"
                ),
                404,
                "Not Found",
                None,
                io.BytesIO(
                    b'{"message":"Not Found"}'
                ),
            )
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=permanent_error,
        ) as opener:
            with patch(
                "time.sleep"
            ) as sleep:
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

        self.assertEqual(
            opener.call_count,
            1,
        )

        sleep.assert_not_called()

    def test_stream_retries_temporary_network_error(
        self,
    ):
        self.check_urlerror_retry(
            stream_health
        )

    def test_stream_retries_http_503(
        self,
    ):
        self.check_http_503_retry(
            stream_health
        )

    def test_stream_does_not_retry_http_404(
        self,
    ):
        self.check_http_404_not_retried(
            stream_health
        )

    def test_epg_retries_temporary_network_error(
        self,
    ):
        self.check_urlerror_retry(
            epg_health
        )

    def test_epg_retries_http_503(
        self,
    ):
        self.check_http_503_retry(
            epg_health
        )

    def test_epg_does_not_retry_http_404(
        self,
    ):
        self.check_http_404_not_retried(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
