"""Structural integrity tests for data/identity_matrix.json.

The SSO-tax table's whole value is "the vendor's own tier wording, from primary
sources, dated" — these tests enforce the shape that promise depends on: every
vendor row must carry all four governance axes (sso / scim / rbac / audit_logs),
each axis must state a value, a tier and at least one https source, and the
file-level as_of must be a real ISO date the freshness gate can read.
"""

import datetime
import json
import unittest
from pathlib import Path

from check_freshness import TRACKED, load_tracked_dates

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "identity_matrix.json").read_text(encoding="utf-8"))

AXES = ("sso", "scim", "rbac", "audit_logs")
AXIS_KEYS = ("value", "tier", "source")
VENDOR_KEYS = ("vendor", "type", "pricing_tiers", "notes") + AXES


class TestFileLevel(unittest.TestCase):
    def test_as_of_is_iso_date(self):
        datetime.date.fromisoformat(DATA["as_of"])  # raises if malformed

    def test_vendors_present_and_nonempty(self):
        self.assertIn("vendors", DATA)
        self.assertGreater(len(DATA["vendors"]), 0)

    def test_legend_covers_all_axes(self):
        for axis in AXES:
            self.assertIn(axis, DATA["legend"])

    def test_tracked_by_freshness_gate(self):
        self.assertTrue(
            any(rel == "data/identity_matrix.json" for _, rel in TRACKED))
        labels = [label for label, _ in load_tracked_dates()]
        self.assertTrue(any("identity_matrix" in label for label in labels))


class TestVendorEntries(unittest.TestCase):
    def test_every_vendor_has_all_four_axes(self):
        for entry in DATA["vendors"]:
            for axis in AXES:
                self.assertIn(axis, entry, entry.get("vendor"))

    def test_entries_carry_all_fields_nonempty(self):
        for entry in DATA["vendors"]:
            for key in VENDOR_KEYS:
                self.assertIn(key, entry, entry.get("vendor"))
                self.assertTrue(str(entry[key]).strip(),
                                f"{entry.get('vendor')}: empty {key}")

    def test_each_axis_has_value_tier_source(self):
        for entry in DATA["vendors"]:
            for axis in AXES:
                cell = entry[axis]
                for key in AXIS_KEYS:
                    self.assertIn(key, cell, f"{entry['vendor']}.{axis}")
                    self.assertTrue(str(cell[key]).strip(),
                                    f"{entry['vendor']}.{axis}: empty {key}")

    def test_sources_are_https_urls(self):
        for entry in DATA["vendors"]:
            for axis in AXES:
                sources = entry[axis]["source"]
                self.assertIsInstance(sources, list,
                                      f"{entry['vendor']}.{axis}")
                self.assertGreater(len(sources), 0,
                                   f"{entry['vendor']}.{axis}")
                for url in sources:
                    self.assertTrue(url.startswith("https://"),
                                    f"{entry['vendor']}.{axis}: {url}")

    def test_vendors_unique(self):
        names = [e["vendor"] for e in DATA["vendors"]]
        self.assertEqual(len(names), len(set(names)))

    def test_undocumented_cells_say_so_not_guess(self):
        # A cell that is wholly undocumented (value leads with "not
        # documented") must not assert an invented tier — its tier must say
        # "not documented" or "n/a". Mixed cells (OSS undocumented + paid
        # edition documented) legitimately carry the paid edition's tier.
        for entry in DATA["vendors"]:
            for axis in AXES:
                tier = entry[axis]["tier"].lower()
                if entry[axis]["value"].lower().startswith("not documented"):
                    self.assertTrue(
                        "not documented" in tier or "n/a" in tier,
                        f"{entry['vendor']}.{axis}: undocumented value but "
                        f"asserted tier {entry[axis]['tier']!r}")


if __name__ == "__main__":
    unittest.main()
