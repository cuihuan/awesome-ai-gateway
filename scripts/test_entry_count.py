#!/usr/bin/env python3
"""Gate the advertised list size against the list itself.

Two failure directions, both real:
  - overstating ("200+" when there are 169) is a credibility bug, the kind that
    makes a reader distrust every other number on the page;
  - understating badly ("100+" when there are 169) is what actually happened here
    for months — the list undersold itself by more than a third.

So the claim must sit in a band around the true count. Widen SLACK deliberately if
the list is meant to advertise a round number; do not widen it to silence a failure.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from count_entries import claims, count_entries, missing_sections

ROOT = Path(__file__).resolve().parent.parent
#: How far below the true count an advertised figure may sit. Claims are rounded
#: down to a marketable number, so some lag is intended — 25 covers "160+" against
#: a true 169 with room for a few additions before anyone has to touch it.
SLACK = 25
#: Files that advertise the size to a reader or to a machine.
CLAIMING_FILES = ("README.md", "README.zh-CN.md", "llms.txt", "CITATION.cff")


class EntryCountClaims(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.total, _ = count_entries(self.readme)

    def test_list_sections_still_exist(self):
        self.assertEqual(
            missing_sections(self.readme),
            [],
            "a list section was renamed — count_entries.LIST_SECTIONS must be updated, "
            "or the published entry count silently drops that whole section",
        )

    def test_readme_has_a_countable_list(self):
        self.assertGreater(self.total, 50, "entry parsing broke — no list sections matched")

    def test_advertised_counts_are_honest(self):
        for name in CLAIMING_FILES:
            path = ROOT / name
            if not path.exists():
                continue
            for claimed in claims(path.read_text(encoding="utf-8")):
                with self.subTest(file=name, claimed=claimed):
                    self.assertLessEqual(
                        claimed,
                        self.total,
                        f"{name} advertises {claimed}+ gateways but the list holds {self.total}",
                    )
                    self.assertGreaterEqual(
                        claimed,
                        self.total - SLACK,
                        f"{name} advertises {claimed}+ but the list has grown to {self.total} — "
                        "raise the claim (run scripts/count_entries.py)",
                    )


if __name__ == "__main__":
    unittest.main()
