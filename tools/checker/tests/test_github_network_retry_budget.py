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
        "process_epg_health_network_budget",
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


class GitHubNetworkRetryBudgetTests(
    unittest.TestCase
):

    def check_network_delay_counts_toward_budget(
        self,
        module,
    ):
        first_body = io.BytesIO(
            b"rate limited"
        )

        first_error = urllib.error.HTTPError(
            "https://api.github.test/test",
            429,
            "Too Many Requests",
            {
                "Retry-After": "299",
            },
            first_body,
        )

        network_error = urllib.error.URLError(
            "temporary network failure"
        )

        response = io.BytesIO(
            b'{"ok": true}'
        )

        with patch.object(
            module.OPENER,
            "open",
            side_effect=[
                first_error,
                network_error,
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
                call(299),
            ],
        )

        self.assertTrue(
            first_body.closed
        )

    def test_stream_network_delay_counts_toward_budget(
        self,
    ):
        self.check_network_delay_counts_toward_budget(
            stream_health
        )

    def test_epg_network_delay_counts_toward_budget(
        self,
    ):
        self.check_network_delay_counts_toward_budget(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
