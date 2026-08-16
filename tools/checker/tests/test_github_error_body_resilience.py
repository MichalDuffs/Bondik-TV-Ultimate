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
        "process_epg_health_error_body",
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


class BrokenBody(io.BytesIO):

    def read(self, *args, **kwargs):
        raise OSError(
            "Borys ate the error body"
        )


class GitHubErrorBodyResilienceTests(
    unittest.TestCase
):

    def check_rate_limit_survives_broken_body(
        self,
        module,
    ):
        body = BrokenBody(
            b"rate limited"
        )

        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "2",
            },
            body,
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
            2
        )

        self.assertTrue(
            body.closed
        )

    def check_permanent_error_survives_broken_body(
        self,
        module,
    ):
        body = BrokenBody(
            b"permission denied"
        )

        error = urllib.error.HTTPError(
            "https://api.github.test/test",
            403,
            "Forbidden",
            {
                "X-RateLimit-Remaining": "4999",
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

        self.assertTrue(
            body.closed
        )

    def test_stream_rate_limit_survives_broken_body(
        self,
    ):
        self.check_rate_limit_survives_broken_body(
            stream_health
        )

    def test_epg_rate_limit_survives_broken_body(
        self,
    ):
        self.check_rate_limit_survives_broken_body(
            epg_health
        )

    def test_stream_permanent_error_survives_broken_body(
        self,
    ):
        self.check_permanent_error_survives_broken_body(
            stream_health
        )

    def test_epg_permanent_error_survives_broken_body(
        self,
    ):
        self.check_permanent_error_survives_broken_body(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
