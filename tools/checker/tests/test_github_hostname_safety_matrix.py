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
        "process_epg_health_hostname_safety_matrix",
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


class GitHubHostnameSafetyMatrixTests(
    unittest.TestCase
):

    ENCODED_UNSAFE_HOSTNAMES = (
        "%2F",
        "%252F",
        "%5C",
        "%255C",
        "%3F",
        "%253F",
        "%23",
        "%2523",
        "%3A",
        "%253A",
        "%5B",
        "%255B",
        "%5D",
        "%255D",
        "%25",
        "%2525",
        "%00",
        "%01",
        "%1F",
        "%7F",
    )

    def check_initial_url_is_rejected(
        self,
        module,
    ):
        for encoded_value in (
            self.ENCODED_UNSAFE_HOSTNAMES
        ):
            with self.subTest(
                encoded_value=encoded_value
            ):
                with mock.patch.object(
                    module,
                    "OPENER",
                ) as opener:
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "hostname",
                    ):
                        module.github_request(
                            (
                                "https://"
                                "api.github.test"
                                f"{encoded_value}borys/"
                                "repos/bondik"
                            ),
                            "secret",
                        )

                    opener.open.assert_not_called()

    def check_redirect_is_rejected(
        self,
        module,
    ):
        request = urllib.request.Request(
            "https://api.github.test/source",
            headers={
                "Authorization": "Bearer secret",
            },
        )

        for encoded_value in (
            self.ENCODED_UNSAFE_HOSTNAMES
        ):
            with self.subTest(
                encoded_value=encoded_value
            ):
                handler = module.SafeRedirectHandler()

                redirected = handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    (
                        "https://"
                        "api.github.test"
                        f"{encoded_value}borys/"
                        "target"
                    ),
                )

                self.assertIsNone(
                    redirected
                )

    def test_stream_initial_url_matrix(
        self,
    ):
        self.check_initial_url_is_rejected(
            stream_health
        )

    def test_epg_initial_url_matrix(
        self,
    ):
        self.check_initial_url_is_rejected(
            epg_health
        )

    def test_stream_redirect_matrix(
        self,
    ):
        self.check_redirect_is_rejected(
            stream_health
        )

    def test_epg_redirect_matrix(
        self,
    ):
        self.check_redirect_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)