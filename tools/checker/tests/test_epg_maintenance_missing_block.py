import unittest

import plan_epg_maintenance as planner


class EpgMaintenanceMissingBlockTests(unittest.TestCase):

    def test_proposed_patch_adds_missing_epg_block(self):
        original = """version: 1

channels:
  - id: "utv-cz"
    name: "ÚTV"
    country: "CZ"
    language: "cs"
    category: "general"
    provider: "utv"
    stream:
      url: "https://example.test/utv.m3u8"
      format: "hls"
      quality: "unknown"
    status: "stable"
    metadata:
      website: "https://example.test/"
"""

        patch = planner.build_proposed_patch(
            original,
            [
                {
                    "channel_id": "utv-cz",
                    "channel_name": "ÚTV",
                    "country": "CZ",
                    "source": "epgshare-cz",
                    "epg_id": "UTV.cz",
                    "match": "exact-normalized-name",
                }
            ],
        )

        self.assertIn("+    epg:", patch)
        self.assertIn('+      id: "UTV.cz"', patch)
        self.assertIn('+      source: "epgshare-cz"', patch)
        self.assertIn("+      enabled: true", patch)
        self.assertNotIn('-      url: "https://example.test/utv.m3u8"', patch)
        self.assertNotIn('-    status: "stable"', patch)

    def test_existing_epg_block_still_uses_core_behavior(self):
        original = """version: 1

channels:
  - id: "demo-cz"
    name: "Demo TV"
    country: "CZ"
    status: "stable"
    epg:
      id: null
      enabled: false
"""

        proposed = planner.build_proposed_channels_text(
            original,
            [
                {
                    "channel_id": "demo-cz",
                    "source": "epgshare-cz",
                    "epg_id": "Demo.TV.cz",
                }
            ],
        )

        self.assertEqual(proposed.count("    epg:"), 1)
        self.assertIn('      id: "Demo.TV.cz"', proposed)
        self.assertIn('      source: "epgshare-cz"', proposed)
        self.assertIn("      enabled: true", proposed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
