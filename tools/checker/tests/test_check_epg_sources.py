from pathlib import Path
import gzip
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
UPDATER_DIR = ROOT / "tools" / "updater"

if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

import check_epg_sources as checker


class EpgSourceCheckerTests(unittest.TestCase):

    def xmltv_payload(self, channel_ids):
        channels = "".join(
            f'<channel id="{channel_id}"></channel>'
            for channel_id in channel_ids
        )

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<tv>{channels}</tv>'
        )

        return gzip.compress(
            xml.encode("utf-8")
        )

    def source_data(self, **overrides):
        source = {
            "id": "epgshare-cz",
            "name": "Example EPG",
            "country": "CZ",
            "format": "xmltv-gzip",
            "url": "https://example.com/epg.xml.gz",
        }

        source.update(overrides)

        return {
            "version": 1,
            "sources": [source],
        }

    def test_extracts_xmltv_channel_ids(self):
        payload = self.xmltv_payload(
            [
                "POLAR.cz",
                "Óčko.cz",
            ]
        )

        channel_ids = checker.extract_xmltv_channel_ids(
            payload,
            "xmltv-gzip",
        )

        self.assertEqual(
            channel_ids,
            {
                "POLAR.cz",
                "Óčko.cz",
            },
        )

    def test_invalid_gzip_is_rejected(self):
        with self.assertRaises(ValueError):
            checker.extract_xmltv_channel_ids(
                b"not-a-gzip-file",
                "xmltv-gzip",
            )

    def test_invalid_xmltv_root_is_rejected(self):
        payload = gzip.compress(
            b"<something></something>"
        )

        with self.assertRaises(ValueError):
            checker.extract_xmltv_channel_ids(
                payload,
                "xmltv-gzip",
            )

    def test_missing_required_epg_ids_are_reported(self):
        missing = checker.find_missing_epg_ids(
            {
                "POLAR.cz",
                "Óčko.cz",
            },
            {
                "POLAR.cz",
            },
        )

        self.assertEqual(
            missing,
            {
                "Óčko.cz",
            },
        )

    def test_source_requires_country(self):
        data = self.source_data()
        del data["sources"][0]["country"]

        with self.assertRaises(ValueError):
            checker.load_sources(data)

    def test_source_url_requires_http_or_https(self):
        data = self.source_data(
            url="ftp://example.com/epg.xml.gz"
        )

        with self.assertRaises(ValueError):
            checker.load_sources(data)

    def test_source_format_must_be_supported(self):
        data = self.source_data(
            format="borys-json"
        )

        with self.assertRaises(ValueError):
            checker.load_sources(data)

    def test_channel_country_must_match_source_country(self):
        sources = checker.load_sources(
            self.source_data(
                id="epgshare-sk",
                country="SK",
            )
        )

        channels = [
            {
                "name": "POLAR",
                "country": "CZ",
                "epg": {
                    "enabled": True,
                    "id": "POLAR.cz",
                    "source": "epgshare-sk",
                },
            }
        ]

        with self.assertRaises(ValueError):
            checker.validate_epg_source_countries(
                channels,
                sources,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
