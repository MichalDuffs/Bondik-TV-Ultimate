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
        "process_epg_health_encoded_brackets",
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


class GitHubEncodedHostnameBracketTests(
    unittest.TestCase
):

    ENCODED_BRACKETS = (
        "%5B",
        "%5D",
    )

    def check_initial_url_is_rejected(
        self,
        module,
    ):
        for encoded_bracket in (
            self.ENCODED_BRACKETS
        ):
            with self.subTest(
                encoded_bracket=encoded_bracket
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
                                f"{encoded_bracket}borys/"
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

        for encoded_bracket in (
            self.ENCODED_BRACKETS
        ):
            with self.subTest(
                encoded_bracket=encoded_bracket
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
                        f"{encoded_bracket}borys/"
                        "target"
                    ),
                )

                self.assertIsNone(
                    redirected
                )

    def test_stream_rejects_encoded_hostname_brackets(
        self,
    ):
        self.check_initial_url_is_rejected(
            stream_health
        )

    def test_epg_rejects_encoded_hostname_brackets(
        self,
    ):
        self.check_initial_url_is_rejected(
            epg_health
        )

    def test_stream_rejects_encoded_redirect_hostname_brackets(
        self,
    ):
        self.check_redirect_is_rejected(
            stream_health
        )

    def test_epg_rejects_encoded_redirect_hostname_brackets(
        self,
    ):
        self.check_redirect_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)