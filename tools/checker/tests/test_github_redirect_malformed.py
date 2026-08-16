from pathlib import Path
import importlib.util
import sys
import unittest
import urllib.request


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
        "process_epg_health_redirect_malformed",
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


class GitHubRedirectMalformedURLTests(
    unittest.TestCase
):

    def check_malformed_redirect_is_rejected(
        self,
        module,
    ):
        request = urllib.request.Request(
            "https://api.github.test/source",
            headers={
                "Authorization": "Bearer secret",
            },
        )

        handler = module.SafeRedirectHandler()

        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://[borys/target",
        )

        self.assertIsNone(
            redirected
        )

    def test_stream_rejects_malformed_redirect(
        self,
    ):
        self.check_malformed_redirect_is_rejected(
            stream_health
        )

    def test_epg_rejects_malformed_redirect(
        self,
    ):
        self.check_malformed_redirect_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
