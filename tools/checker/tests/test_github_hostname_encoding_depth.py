from pathlib import Path
import importlib.util
import sys
import unittest
import urllib.request
from unittest import mock


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
        "process_epg_health_hostname_depth",
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


def deeply_encoded_hostname():
    hostname = "%41pi.github.test"

    for _ in range(20):
        hostname = hostname.replace(
            "%",
            "%25",
        )

    return hostname


class GitHubHostnameEncodingDepthTests(
    unittest.TestCase
):

    def check_initial_url_is_rejected(
        self,
        module,
    ):
        hostname = deeply_encoded_hostname()

        with mock.patch.object(
            module,
            "OPENER",
        ) as opener:
            with self.assertRaisesRegex(
                RuntimeError,
                "hostname",
            ):
                module.github_request(
                    f"https://{hostname}/repos/borys",
                    "secret",
                )

            opener.open.assert_not_called()

    def check_redirect_is_rejected(
        self,
        module,
    ):
        hostname = deeply_encoded_hostname()

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
            f"https://{hostname}/target",
        )

        self.assertIsNone(
            redirected
        )

    def test_stream_rejects_excessive_hostname_encoding_depth(
        self,
    ):
        self.check_initial_url_is_rejected(
            stream_health
        )

    def test_epg_rejects_excessive_hostname_encoding_depth(
        self,
    ):
        self.check_initial_url_is_rejected(
            epg_health
        )

    def test_stream_rejects_excessive_redirect_hostname_encoding_depth(
        self,
    ):
        self.check_redirect_is_rejected(
            stream_health
        )

    def test_epg_rejects_excessive_redirect_hostname_encoding_depth(
        self,
    ):
        self.check_redirect_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
