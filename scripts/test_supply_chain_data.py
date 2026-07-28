"""Structural integrity tests for data/supply_chain.json.

The supply-chain matrix's promise is "machine-checked posture, primary-sourced,
dated" — these tests enforce the shape that promise depends on: every gateway
row carries all posture axes with at least one https source, every incident and
debunked claim is sourced, and the file-level as_of is a real ISO date wired
into the freshness gate.
"""

import datetime
import json
import unittest
from pathlib import Path

from check_freshness import TRACKED

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "supply_chain.json").read_text(encoding="utf-8"))

GATEWAY_KEYS = (
    "repo",
    "signed_releases",
    "provenance_sbom",
    "security_md",
    "advisories_2025_26",
    "posture_note",
    "sources",
)


class TestFileLevel(unittest.TestCase):
    def test_as_of_is_iso_date(self):
        datetime.date.fromisoformat(DATA["as_of"])  # raises if malformed

    def test_tracked_by_freshness_gate(self):
        self.assertIn("data/supply_chain.json", [path for _, path in TRACKED])

    def test_legend_covers_gateway_axes(self):
        for key in ("signed_releases", "provenance_sbom", "security_md", "advisories_2025_26"):
            self.assertIn(key, DATA["legend"])

    def test_top_level_sections_nonempty(self):
        for section in ("gateways", "incidents", "debunked"):
            self.assertIn(section, DATA)
            self.assertGreater(len(DATA[section]), 0)


class TestGatewayRows(unittest.TestCase):
    def test_every_row_has_all_keys(self):
        for row in DATA["gateways"]:
            for key in GATEWAY_KEYS:
                self.assertIn(key, row, f"{row.get('repo', '?')} missing {key}")

    def test_every_row_has_https_source(self):
        for row in DATA["gateways"]:
            self.assertTrue(
                any(s.startswith("https://") for s in row["sources"]),
                f"{row['repo']} has no https source",
            )

    def test_repo_slug_format(self):
        for row in DATA["gateways"]:
            self.assertRegex(row["repo"], r"^[\w.-]+/[\w.-]+$")

    def test_security_md_is_yes_or_no(self):
        for row in DATA["gateways"]:
            self.assertIn(row["security_md"], ("yes", "no"))


class TestIncidentsAndDebunked(unittest.TestCase):
    def test_incidents_dated_and_sourced(self):
        for inc in DATA["incidents"]:
            self.assertIn("id", inc)
            self.assertIn("date", inc)
            self.assertRegex(str(inc["date"]), r"^\d{4}-\d{2}")
            self.assertTrue(any(s.startswith("https://") for s in inc["sources"]))

    def test_debunked_have_verdict_and_source(self):
        for item in DATA["debunked"]:
            self.assertIn("claim", item)
            self.assertIn("verdict", item)
            self.assertTrue(any(s.startswith("https://") for s in item["sources"]))


if __name__ == "__main__":
    unittest.main()
