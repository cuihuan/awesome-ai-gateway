#!/usr/bin/env python3
"""Count the entries the list actually holds, so the README's own claim can be checked.

Why this exists: the README, llms.txt, CITATION.cff and the repository description
all advertise a size ("100+ gateways"). That number was typed once and then the list
grew past it — for months it undersold itself by more than sixty entries, which is
the same class of bug as a stale star count, just pointing the other way. Nothing
compared the claim against the list.

So the claim becomes checkable: this module counts distinct linked entries in the
category sections that make up the list proper, and scripts/test_entry_count.py
fails the build when an advertised figure overstates the list or falls too far
behind it.

Deliberately conservative — it counts only markdown bullets of the form
``- [Name](url)``. Entries that live in tables (several first-party cloud gateways)
are not counted, so the real list is at least this large. Undercounting is the safe
direction for a claim we publish.

Stdlib only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

#: Section headings whose bullets are list entries. Keep in sync with the README's
#: category sections — a renamed heading should fail loudly (see verify_sections).
LIST_SECTIONS = (
    "💰 Cost-first: cheapest multi-model access",
    "🔓 Self-hosted open source",
    "🏢 Enterprise & compliance",
    "🌐 First-party gateways (cloud & model vendors)",
    "🇨🇳 China ecosystem",
    "🤖 MCP & agent gateways",
    "🔧 More by capability (cross-cutting)",
)

HEADING_RE = re.compile(r"^## (.+)$", re.M)
ENTRY_RE = re.compile(r"^- \[([^\]]+)\]\(", re.M)
#: An advertised size claim, either language: "160+ gateways", "over 100 gateways", "160+ 网关".
CLAIM_RE = re.compile(
    r"(?:(\d{2,4})\+|over (\d{2,4}))\s+(?:AI\s+)?(?:gateways|网关)", re.I
)


def section_bodies(text: str) -> dict[str, str]:
    """Map each `## ` heading to the text beneath it, up to the next `## `."""
    heads = list(HEADING_RE.finditer(text))
    bodies: dict[str, str] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        bodies[m.group(1).strip()] = text[m.end() : end]
    return bodies


def count_entries(text: str) -> tuple[int, dict[str, int]]:
    """Distinct entry names across the list sections, plus the per-section tally.

    Distinct, because CONTRIBUTING lets one project appear in up to two sections —
    counting occurrences would inflate the published figure.
    """
    bodies = section_bodies(text)
    names: set[str] = set()
    per_section: dict[str, int] = {}
    for title in LIST_SECTIONS:
        body = bodies.get(title, "")
        found = {m.group(1).strip() for m in ENTRY_RE.finditer(body)}
        per_section[title] = len(found)
        names |= found
    return len(names), per_section


def missing_sections(text: str) -> list[str]:
    """List sections named here that no longer exist in the README.

    A rename silently drops a whole section from the count, which would make the
    published figure quietly wrong — so it is an error, not a warning.
    """
    bodies = section_bodies(text)
    return [t for t in LIST_SECTIONS if t not in bodies]


def claims(text: str) -> list[int]:
    """Every advertised entry-count in a piece of text."""
    return [int(m.group(1) or m.group(2)) for m in CLAIM_RE.finditer(text)]


def main() -> int:
    text = README.read_text(encoding="utf-8")
    gone = missing_sections(text)
    if gone:
        print(f"error: list sections not found in README.md: {gone}", file=sys.stderr)
        return 1
    total, per_section = count_entries(text)
    for title, n in per_section.items():
        print(f"{n:>4}  {title}")
    print(f"\n{total} distinct entries across the list sections")
    print(f"advertised in README.md: {claims(text) or 'no claim found'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
