#!/usr/bin/env python3
"""Freshness guard for the hand-maintained dated snapshots.

The daily CI auto-refreshes star counts and releases, but the pricing/benchmark
snapshot (`data/models.json`), the gateway scorecard (`data/gateways_eval.json`),
the free-tier table and the data-retention matrix carry a manual `as_of` date
that only a human review should move. Left unwatched they silently rot while
the page still advertises "updated daily".

This script asserts each tracked `as_of` is within --max-age-days of today and
exits non-zero (listing the stale ones) otherwise. It is a forcing function to
prompt a *real* re-review — deliberately NOT a way to rubber-stamp today's date
onto data nobody re-checked (that would defeat the list's "sourced, not asserted"
promise).

Usage:
    python scripts/check_freshness.py [--max-age-days 30] [--today YYYY-MM-DD]

Exit code 0 = all fresh, 1 = at least one snapshot is stale, 2 = read error.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (human label, repo-relative path) — each file's date is read from its top-level
# "as_of" field. The BENCHMARKS.md "Last reviewed" line mirrors models.json, so
# guarding the canonical JSON covers it too.
TRACKED = [
    ("data/models.json (pricing & benchmark snapshot)", "data/models.json"),
    ("data/gateways_eval.json (gateway scorecard snapshot)", "data/gateways_eval.json"),
    ("data/free_tiers.json (verified free-tier / rate-limit table)", "data/free_tiers.json"),
    # The README calls this matrix the answer to "the #1 trust question" and
    # prints its verified-date in prose — the one snapshot that most needs a
    # rot alarm (it sat unwatched while everything else had one).
    ("data/data_retention.json (who-sees-your-prompts retention matrix)", "data/data_retention.json"),
]


def parse_date(s):
    """Parse an ISO YYYY-MM-DD date. Raises ValueError on a malformed string."""
    return datetime.date.fromisoformat(str(s).strip())


def load_tracked_dates(root=ROOT, tracked=TRACKED):
    """Read each tracked file's `as_of` field → list of (label, 'YYYY-MM-DD').

    Raises FileNotFoundError / KeyError / ValueError on a missing file or field
    so a broken data file fails loudly rather than silently passing the guard.
    """
    out = []
    for label, rel in tracked:
        data = json.loads((Path(root) / rel).read_text(encoding="utf-8"))
        if "as_of" not in data:
            raise KeyError(f"{rel} has no 'as_of' field")
        out.append((label, data["as_of"]))
    return out


def stale_entries(items, today, max_age_days):
    """Pure core: given [(label, 'YYYY-MM-DD'), ...], return the entries whose age
    in days exceeds max_age_days as [(label, datestr, age_days), ...]."""
    stale = []
    for label, datestr in items:
        age = (today - parse_date(datestr)).days
        if age > max_age_days:
            stale.append((label, datestr, age))
    return stale


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assert dated data snapshots are fresh.")
    ap.add_argument("--max-age-days", type=int, default=30,
                    help="fail if a snapshot's as_of is older than this many days (default 30)")
    ap.add_argument("--today", default=None,
                    help="override today's date (YYYY-MM-DD), for tests/reproducibility")
    args = ap.parse_args(argv)

    today = parse_date(args.today) if args.today else datetime.date.today()

    try:
        items = load_tracked_dates()
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"::error::cannot read tracked snapshot dates: {e}", file=sys.stderr)
        return 2

    stale = stale_entries(items, today, args.max_age_days)
    for label, datestr in items:
        age = (today - parse_date(datestr)).days
        mark = "STALE" if any(s[0] == label for s in stale) else "ok"
        print(f"[{mark:>5}] {label}: as_of {datestr} ({age}d old, limit {args.max_age_days}d)")

    if stale:
        print(
            f"::error::{len(stale)} snapshot(s) older than {args.max_age_days}d — "
            "re-review the prices/scores against current sources, then bump 'as_of'. "
            "Do not bump the date without an actual review.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
