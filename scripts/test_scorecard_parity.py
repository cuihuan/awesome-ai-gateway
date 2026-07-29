"""The rendered scorecards must agree with the data file — and with each other.

data/gateways_eval.json is the source of truth for every gateway score, but
the star cells are hand-maintained in two languages. A score can therefore be
corrected in one place and left stale in the other two, which is exactly what
happened: Kong's security score was lowered to 4.0 in the data file and the
English table, while the Chinese table kept ★★★★½ for a day.

These tests read the header row to find each axis column (the hosted and
self-hosted tables order their columns differently), so they check the cell
that actually holds the score rather than a fixed index.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "gateways_eval.json").read_text(encoding="utf-8"))
ROWS = {g["name"]: g for g in DATA.get("gateways", DATA.get("rows", []))}

# axis -> the header labels that introduce its column, per language
AXES = {
    "compliance": ("Compliance", "合规"),
    "security": ("Security", "安全"),
    "stability": ("Stability", "稳定"),
    "observability": ("Observability", "可观测"),
}
FILES = ("BENCHMARKS.md", "BENCHMARKS.zh-CN.md")


def to_stars(value):
    full = int(value)
    return "★" * full + ("½" if value - full >= 0.5 else "")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def score_cells(path):
    """Yield (gateway_name, axis, cell_text) for every scorecard row found."""
    lines = (ROOT / path).read_text(encoding="utf-8").split("\n")
    sep = re.compile(r"^\|[\s:|-]+\|$")
    header_cols = None
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            header_cols = None
            continue
        row = cells(line)
        # A header is a row *followed by the separator* — not merely a row whose
        # prose happens to contain the word "Security"/"安全". A note cell reading
        # "OSS security = Prompt Guard…" was silently promoted to a header once,
        # which made the parser skip the very row it was meant to check.
        is_header = i + 1 < len(lines) and sep.match(lines[i + 1].strip())
        if is_header and any(any(lbl in c for lbl in AXES["security"]) for c in row):
            header_cols = {}
            for axis, labels in AXES.items():
                for i, c in enumerate(row):
                    if any(lbl in c for lbl in labels):
                        header_cols[axis] = i
                        break
            continue
        if header_cols is None or len(row) < 2:
            continue
        name = re.sub(r"[*`]", "", row[0]).strip()
        name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
        for candidate in ROWS:
            base = re.sub(r"\s*\(.*?\)\s*$", "", candidate).strip()
            if name in (candidate, base):
                for axis, idx in header_cols.items():
                    if idx < len(row):
                        yield candidate, axis, row[idx]
                break


class TestScorecardParity(unittest.TestCase):
    def test_star_cells_match_the_data_file(self):
        problems = []
        for path in FILES:
            for name, axis, cell in score_cells(path):
                stripped = cell.replace("⚠️", "").replace("🏠", "").strip()
                if not stripped or set(stripped) - set("★½"):
                    continue  # markup cell, N/A, or a prose note that merely contains a star
                expected = to_stars(ROWS[name][axis])
                actual = cell.replace("⚠️", "").replace("🏠", "").strip()
                if actual != expected:
                    problems.append(f"{path}: {name} {axis} shows {actual!r}, data says {expected!r}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_both_languages_agree(self):
        def snapshot(path):
            return {(n, a): c.replace("⚠️", "").replace("🏠", "").strip()
                    for n, a, c in score_cells(path)
                    if (lambda t: t and not (set(t) - set("★½")))(c.replace("⚠️", "").replace("🏠", "").strip())}
        en, zh = snapshot(FILES[0]), snapshot(FILES[1])
        shared = set(en) & set(zh)
        self.assertGreater(len(shared), 10, "parity check found too few comparable cells")
        diffs = [f"{k}: en={en[k]!r} zh={zh[k]!r}" for k in sorted(shared) if en[k] != zh[k]]
        self.assertEqual(diffs, [], "\n".join(diffs))


if __name__ == "__main__":
    unittest.main()
