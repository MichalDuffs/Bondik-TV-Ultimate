from pathlib import Path
import sys
import unittest

CHECKER_DIR = Path(__file__).resolve().parents[1]

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import check_channels as checker


class EpgValidationTests(unittest.TestCase):

    def setUp(self):
        self.countries = {"CZ"}
        self.categories = {"general"}
        self.protocols = {"https"}
        self.statuses = {"stable"}

    def channel(
        self,
        *,
        channel_id="polar-tv-cz",
        name="POLAR",
        url="https://example.test/stream.m3u8",
        epg=None,
    ):
        return {
            "id": channel_id,
            "name": name,
            "country": "CZ",
            "category": "general",
            "status": "stable",
            "stream": {
                "url": url,
                "format": "hls",
            },
            "epg": (
                {"id": None, "enabled": False}
                if epg is None
                else epg
            ),
        }

    def validate(self, channel):
        return checker.validate_channel(
            channel,
            self.countries,
            self.categories,
            self.protocols,
            self.statuses,
        )

    def test_enabled_epg_requires_id(self):
        channel = self.channel(
            epg={
                "id": None,
                "enabled": True,
            }
        )

        errors = self.validate(channel)

        self.assertIn(
            "EPG is enabled but 'epg.id' is missing",
            errors,
        )

    def test_enabled_epg_with_id_is_valid(self):
        channel = self.channel(
            epg={
                "id": "polar.cz",
                "enabled": True,
            }
        )

        errors = self.validate(channel)

        epg_errors = [
            error
            for error in errors
            if "EPG" in error or "epg." in error
        ]

        self.assertEqual(epg_errors, [])

    def test_epg_enabled_must_be_boolean(self):
        channel = self.channel(
            epg={
                "id": "polar.cz",
                "enabled": "yes",
            }
        )

        errors = self.validate(channel)

        self.assertIn(
            "'epg.enabled' must be boolean",
            errors,
        )

    def test_duplicate_enabled_epg_ids_are_rejected(self):
        first = self.channel(
            epg={
                "id": "polar.cz",
                "enabled": True,
            }
        )

        second = self.channel(
            channel_id="other-tv-cz",
            name="OTHER",
            url="https://example.test/other.m3u8",
            epg={
                "id": "polar.cz",
                "enabled": True,
            },
        )

        problems = checker.find_duplicates(
            [first, second]
        )

        self.assertIn(
            "duplicate EPG ID 'polar.cz' (POLAR / OTHER)",
            problems,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
