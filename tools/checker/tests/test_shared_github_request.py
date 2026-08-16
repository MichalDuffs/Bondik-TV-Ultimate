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
        "process_epg_health_shared_api",
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


class SharedGitHubRequestTests(
    unittest.TestCase
):

    def check_uses_shared_helper(
        self,
        module,
    ):
        self.assertTrue(
            hasattr(
                module,
                "_shared_github_request",
            ),
            "shared GitHub request helper "
            "is not wired",
        )

        with patch.object(
            module,
            "_shared_github_request",
            return_value=b'{"ok": true}',
        ) as shared:
            result = module.github_request(
                "https://api.github.test/test",
                "test-token",
                method="POST",
                payload={
                    "borys": "denied",
                },
            )

        self.assertEqual(
            result,
            b'{"ok": true}',
        )

        shared.assert_called_once_with(
            "https://api.github.test/test",
            "test-token",
            method="POST",
            payload={
                "borys": "denied",
            },
            opener=module.OPENER,
            sleep=module.time.sleep,
            now=module.time.time,
        )

    def test_stream_uses_shared_github_request(
        self,
    ):
        self.check_uses_shared_helper(
            stream_health
        )

    def test_epg_uses_shared_github_request(
        self,
    ):
        self.check_uses_shared_helper(
            epg_health
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
