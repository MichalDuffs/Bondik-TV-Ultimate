from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import process_epg_health as health


class EpgHealthHistoryTests(unittest.TestCase):

    def test_extract_failures_detects_failed_source(self):
        report = """
📡 epgshare-cz
   ├─ ✅ 4/4 IDs found
   └─ ❌ 1 ID(s) have no fresh programme data
      • POLAR.cz

📡 epgshare-sk
   ├─ ✅ 4/4 IDs found
   └─ ✅ 4/4 IDs have fresh programme data
"""

        self.assertEqual(
            health.extract_failures(report),
            {"epgshare-cz"},
        )

    def test_extract_failures_detects_download_failure(self):
        report = """
📡 epgshare-cz
   └─ ❌ HTTP Error 503: Service Unavailable

📡 epgshare-sk
   └─ ✅ 4/4 IDs have fresh programme data
"""

        self.assertEqual(
            health.extract_failures(report),
            {"epgshare-cz"},
        )

    def test_advance_streaks_tracks_repeated_failure(self):
        streaks = health.advance_streaks(
            {"epgshare-cz", "epgshare-sk"},
            {
                "epgshare-cz": 2,
            },
        )

        self.assertEqual(
            streaks,
            {
                "epgshare-cz": 3,
                "epgshare-sk": 1,
            },
        )

    def test_history_reports_recovery_and_repeat(self):
        history, repeated, recovered = health.build_history(
            {"epgshare-cz"},
            {
                "epgshare-cz": 2,
                "epgshare-sk": 4,
            },
        )

        self.assertIn(
            "Repeated EPG failure: epgshare-cz",
            history,
        )

        self.assertIn(
            "EPG recovered: epgshare-sk",
            history,
        )

        self.assertEqual(
            repeated,
            ["epgshare-cz"],
        )

        self.assertEqual(
            recovered,
            ["epgshare-sk"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
