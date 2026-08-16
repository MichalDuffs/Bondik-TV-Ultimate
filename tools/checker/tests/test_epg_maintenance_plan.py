import gzip
import unittest

import plan_epg_maintenance as planner


class EpgMaintenancePlannerTests(unittest.TestCase):

    def test_normalize_label_removes_diacritics_and_punctuation(self):
        self.assertEqual(
            planner.normalize_label("Óčko Star"),
            "ockostar",
        )

    def test_extract_xmltv_catalog_reads_ids_and_names(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<tv>
  <channel id='Praha.TV.cz'>
    <display-name>Praha TV</display-name>
  </channel>
</tv>
"""

        catalog = planner.extract_xmltv_catalog(
            gzip.compress(xml),
            "xmltv-gzip",
        )

        self.assertEqual(
            catalog,
            [
                {
                    "id": "Praha.TV.cz",
                    "names": ["Praha TV"],
                }
            ],
        )

    def test_exact_candidate_can_match_epg_id_without_country_suffix(self):
        catalog = [
            {
                "id": "Praha.TV.cz",
                "names": [],
            }
        ]

        self.assertEqual(
            planner.find_exact_candidates(
                "Praha TV",
                "CZ",
                catalog,
            ),
            ["Praha.TV.cz"],
        )

    def test_plan_proposes_single_exact_match(self):
        channels = [
            {
                "id": "praha-tv-cz",
                "name": "Praha TV",
                "country": "CZ",
                "status": "stable",
                "epg": {
                    "id": None,
                    "enabled": False,
                },
            }
        ]
        sources = {
            "epgshare-cz": {
                "country": "CZ",
            }
        }
        catalogs = {
            "epgshare-cz": [
                {
                    "id": "Praha.TV.cz",
                    "names": ["Praha TV"],
                }
            ]
        }

        report = planner.plan_maintenance(
            channels,
            sources,
            catalogs,
        )

        self.assertEqual(
            report["proposal_count"],
            1,
        )
        self.assertEqual(
            report["proposals"][0]["epg_id"],
            "Praha.TV.cz",
        )
        self.assertEqual(
            report["proposals"][0]["source"],
            "epgshare-cz",
        )

    def test_ambiguous_exact_match_requires_manual_review(self):
        channels = [
            {
                "id": "demo-cz",
                "name": "Demo TV",
                "country": "CZ",
                "status": "stable",
                "epg": {
                    "enabled": False,
                },
            }
        ]
        sources = {
            "epgshare-cz": {
                "country": "CZ",
            }
        }
        catalogs = {
            "epgshare-cz": [
                {
                    "id": "Demo.TV.cz",
                    "names": ["Demo TV"],
                },
                {
                    "id": "DemoTV.cz",
                    "names": ["Demo TV"],
                },
            ]
        }

        report = planner.plan_maintenance(
            channels,
            sources,
            catalogs,
        )

        self.assertEqual(
            report["proposal_count"],
            0,
        )
        self.assertEqual(
            report["unresolved"][0]["reason"],
            "ambiguous-exact-match",
        )

    def test_testing_channel_is_skipped(self):
        channels = [
            {
                "id": "praha-tv-cz",
                "name": "Praha TV",
                "country": "CZ",
                "status": "testing",
                "epg": {
                    "enabled": False,
                },
            }
        ]

        report = planner.plan_maintenance(
            channels,
            {
                "epgshare-cz": {
                    "country": "CZ",
                }
            },
            {
                "epgshare-cz": [
                    {
                        "id": "PRAHA.TV.cz",
                        "names": ["Praha TV"],
                    }
                ]
            },
        )

        self.assertEqual(
            report["proposal_count"],
            0,
        )
        self.assertEqual(
            report["unresolved_count"],
            0,
        )
        self.assertEqual(
            report["skipped_count"],
            1,
        )
        self.assertEqual(
            report["skipped"][0]["reason"],
            "channel-not-stable",
        )
        self.assertEqual(
            report["skipped"][0]["status"],
            "testing",
        )

    def test_missing_status_is_skipped(self):
        channels = [
            {
                "id": "demo-cz",
                "name": "Demo TV",
                "country": "CZ",
                "epg": {
                    "enabled": False,
                },
            }
        ]

        report = planner.plan_maintenance(
            channels,
            {
                "epgshare-cz": {
                    "country": "CZ",
                }
            },
            {},
        )

        self.assertEqual(
            report["skipped_count"],
            1,
        )
        self.assertIsNone(
            report["skipped"][0]["status"]
        )
        self.assertEqual(
            report["unresolved_count"],
            0,
        )

    def test_proposed_patch_updates_only_epg_block(self):
        original = """version: 1

channels:
  - id: "demo-cz"
    name: "Demo TV"
    country: "CZ"
    status: "stable"

    stream:
      url: "https://example.test/live.m3u8"
      format: "hls"

    epg:
      id: null
      enabled: false

    logo:
      url: null
"""

        patch = planner.build_proposed_patch(
            original,
            [
                {
                    "channel_id": "demo-cz",
                    "channel_name": "Demo TV",
                    "country": "CZ",
                    "source": "epgshare-cz",
                    "epg_id": "Demo.TV.cz",
                    "match": "exact-normalized-name",
                }
            ],
        )

        self.assertIn(
            "--- a/channels/channels.yaml",
            patch,
        )
        self.assertIn(
            "+++ b/channels/channels.yaml",
            patch,
        )
        self.assertIn(
            '-      id: null',
            patch,
        )
        self.assertIn(
            '+      id: "Demo.TV.cz"',
            patch,
        )
        self.assertIn(
            '+      source: "epgshare-cz"',
            patch,
        )
        self.assertIn(
            '-      enabled: false',
            patch,
        )
        self.assertIn(
            '+      enabled: true',
            patch,
        )
        self.assertNotIn(
            '-      url: "https://example.test/live.m3u8"',
            patch,
        )

    def test_proposed_patch_is_empty_without_proposals(self):
        original = """version: 1
channels: []
"""

        self.assertEqual(
            planner.build_proposed_patch(
                original,
                [],
            ),
            "",
        )

    def test_enabled_epg_is_left_untouched(self):
        channels = [
            {
                "id": "polar-tv-cz",
                "name": "POLAR",
                "country": "CZ",
                "epg": {
                    "id": "POLAR.cz",
                    "source": "epgshare-cz",
                    "enabled": True,
                },
            }
        ]

        report = planner.plan_maintenance(
            channels,
            {
                "epgshare-cz": {
                    "country": "CZ",
                }
            },
            {},
        )

        self.assertEqual(
            report["already_enabled"],
            1,
        )
        self.assertEqual(
            report["proposal_count"],
            0,
        )
        self.assertEqual(
            report["unresolved_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
