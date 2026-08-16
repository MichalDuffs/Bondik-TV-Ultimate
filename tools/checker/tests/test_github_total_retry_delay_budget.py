from pathlib import Path
import importlib.util
import io
import sys
import unittest
import urllib.error
from unittest.mock import call, patch


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
        "process_epg_health_retry_budget_total",
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


class GitHubTotalRetryDelayBudgetTests(
    unittest.TestCase
):

    def check_total_delay_budget(
        self,
        module,
    ):
        first_body = io.BytesIO(
            b"rate limited"
        )

        second_body = io.BytesIO(
            b"rate limited again"
        )

        first_error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "200",
            },
            first_body,
        )

        second_error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "200",
            },
            second_body,
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
                with self.assertRaisesRegex(
                    RuntimeError,
                    "retry delay budget",
                ):
                    module.github_request(
                        "https://api.github.test/test",
                        "test-token",
                    )

        self.assertEqual(
            opener.call_count,
            2,
        )

        self.assertEqual(
            sleep.call_args_list,
            [
                call(200),
            ],
        )

        self.assertTrue(
            first_body.closed
        )

        self.assertTrue(
            second_body.closed
        )

    def test_stream_total_retry_delay_budget(
        self,
    ):
        self.check_total_delay_budget(
            stream_health
        )

    def test_epg_total_retry_delay_budget(
        self,
    ):
        self.check_total_delay_budget(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
