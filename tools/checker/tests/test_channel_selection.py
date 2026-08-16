from pathlib import Path
import sys
import unittest

CHECKER_DIR = Path(__file__).resolve().parents[1]

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import check_channels as checker


class ChannelSelectionTests(unittest.TestCase):

    def setUp(self):
        self.channels = [
            {"id": "stable-tv-cz", "status": "stable"},
            {"id": "testing-tv-cz", "status": "testing"},
            {"id": "archived-tv-cz", "status": "archived"},
        ]

    def test_exact_channel_id_selects_one_testing_channel(self):
        selected = checker.select_channels(
            self.channels,
            "testing",
            "testing-tv-cz",
        )

        self.assertEqual(
            [channel["id"] for channel in selected],
            ["testing-tv-cz"],
        )

    def test_unknown_channel_id_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown channel id 'missing-tv-cz'",
        ):
            checker.select_channels(
                self.channels,
                "testing",
                "missing-tv-cz",
            )

    def test_channel_id_status_mismatch_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Channel 'stable-tv-cz' does not match status 'testing'",
        ):
            checker.select_channels(
                self.channels,
                "testing",
                "stable-tv-cz",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
