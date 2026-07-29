"""Structural integrity tests for data/mcp_gateways.json.

This matrix answers "can this gateway actually govern agent traffic?" — a
question where an unsupported ✅ is worse than a blank, because the reader
is deciding whether an agent's tool calls are authorized at all. So the
shape these tests enforce is: every capability claim carries evidence, and
every row that was not verified says so instead of implying it was.
"""

import datetime
import json
import unittest
from pathlib import Path

from check_freshness import TRACKED

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "mcp_gateways.json").read_text(encoding="utf-8"))
ROWS = DATA["gateways"]

CAPABILITY_FIELDS = (
    "tool_level_authorization",
    "oauth_obo_token_exchange",
    "secret_brokering",
    "audit_of_tool_invocations",
)
VERIFICATION_LEVELS = {"source_read", "docs_read", "readme_only", "not_assessed"}


class TestFileLevel(unittest.TestCase):
    def test_as_of_is_iso_date(self):
        datetime.date.fromisoformat(DATA["as_of"])

    def test_tracked_by_freshness_gate(self):
        self.assertIn("data/mcp_gateways.json", [path for _, path in TRACKED])

    def test_legend_documents_every_capability_field(self):
        for field in CAPABILITY_FIELDS:
            self.assertIn(field, DATA["legend"], f"legend is missing {field}")

    def test_rows_present(self):
        self.assertGreater(len(ROWS), 0)


class TestRows(unittest.TestCase):
    def test_every_row_names_its_verification_level(self):
        for row in ROWS:
            self.assertIn(
                row.get("verification"), VERIFICATION_LEVELS,
                f"{row.get('gateway', '?')}: verification must be one of {sorted(VERIFICATION_LEVELS)}",
            )

    def test_source_read_rows_pin_a_commit(self):
        """A source_read claim without a commit cannot be re-checked later."""
        for row in ROWS:
            if row.get("verification") == "source_read":
                self.assertTrue(
                    row.get("pinned_commit"),
                    f"{row['gateway']}: source_read rows must carry pinned_commit",
                )

    def test_unverified_rows_do_not_assert_capabilities(self):
        """The failure mode this guards: a row nobody checked still printing
        a confident yes, which reads identically to a verified one."""
        for row in ROWS:
            if row.get("verification") in {"not_assessed", "unknown"}:
                for field in CAPABILITY_FIELDS:
                    value = row.get(field)
                    text = json.dumps(value, ensure_ascii=False).lower() if value is not None else ""
                    self.assertNotIn(
                        '"yes"', text,
                        f"{row['gateway']}: {field} asserts yes on an unverified row",
                    )

    def test_gateway_names_unique(self):
        names = [row["gateway"] for row in ROWS]
        self.assertEqual(len(names), len(set(names)), "duplicate gateway rows")


if __name__ == "__main__":
    unittest.main()
