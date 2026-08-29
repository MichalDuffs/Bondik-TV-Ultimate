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
        "process_epg_health_encoded_control_chars",
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


class GitHubEncodedHostnameControlCharacterTests(
    unittest.TestCase
):

    ENCODED_CONTROL_CHARACTERS = (
        "%00",
        "%01",
        "%1F",
        "%7F",
    )

    def check_initial_url_is_rejected(
        self,
        module,
    ):
        for encoded_control in (
            self.ENCODED_CONTROL_CHARACTERS
        ):
            with self.subTest(
                encoded_control=encoded_control
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
                                f"{encoded_control}borys/"
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

        for encoded_control in (
            self.ENCODED_CONTROL_CHARACTERS
        ):
            with self.subTest(
                encoded_control=encoded_control
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
                        f"{encoded_control}borys/"
                        "target"
                    ),
                )

                self.assertIsNone(
                    redirected
                )

    def test_stream_rejects_encoded_hostname_control_characters(
        self,
    ):
        self.check_initial_url_is_rejected(
            stream_health
        )

    def test_epg_rejects_encoded_hostname_control_characters(
        self,
    ):
        self.check_initial_url_is_rejected(
            epg_health
        )

    def test_stream_rejects_encoded_redirect_hostname_control_characters(
        self,
    ):
        self.check_redirect_is_rejected(
            stream_health
        )

    def test_epg_rejects_encoded_redirect_hostname_control_characters(
        self,
    ):
        self.check_redirect_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)