from pathlib import Path
import importlib.util
import sys
import unittest
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
        "process_epg_health_url_port",
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


class GitHubURLPortTests(
    unittest.TestCase
):

    def check_invalid_port_is_rejected(
        self,
        module,
    ):
        with patch.object(
            module.OPENER,
            "open",
        ) as opener:
            with self.assertRaisesRegex(
                RuntimeError,
                "port",
            ):
                module.github_request(
                    (
                        "https://api.github.test:"
                        "not-a-port/test"
                    ),
                    "test-token",
                )

        opener.assert_not_called()

    def test_stream_rejects_invalid_port(
        self,
    ):
        self.check_invalid_port_is_rejected(
            stream_health
        )

    def test_epg_rejects_invalid_port(
        self,
    ):
        self.check_invalid_port_is_rejected(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
