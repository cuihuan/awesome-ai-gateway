#!/usr/bin/env bash
# Regenerate every derived artifact, in dependency order, then run the gates.
#
# Why this exists: the repo has six generators and each CI job checks a
# different one. Editing a compare page, a data file or a README table
# invalidates artifacts you weren't thinking about — compare HTML, sitemap,
# llms.txt, cost tables, CSV exports, the reality JSON, the feed, table
# alignment, the ToC. Forgetting one turns into a red build on the *next*
# push, which is a slow and confusing way to find out.
#
# Run this before committing any content change. It is idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ cost tables + CSV exports (from data/models.json)"
python3 scripts/cost_calc.py
python3 scripts/export_csv.py

echo "→ production-reality JSON (from BENCHMARKS Part 5)"
python3 scripts/build_reality.py

echo "→ compare HTML + sitemap (from compare/*.md)"
python3 scripts/build_compare_html.py

echo "→ llms.txt (embeds each compare page's key-numbers line)"
python3 scripts/build_llms_txt.py

echo "→ release feed (from data/releases.json)"
python3 scripts/build_feed.py

echo "→ README table alignment + Contents (lint gate is blocking)"
node scripts/format_tables.mjs README.md
node scripts/build_toc.mjs README.md

echo "→ tests"
python3 -m unittest discover -s scripts -p 'test_*.py' -q

echo "→ bilingual figure diff (advisory)"
python3 scripts/bilingual_figure_diff.py

echo "→ freshness (advisory)"
python3 scripts/check_freshness.py --max-age-days 30 || echo "  (stale snapshot — re-review and bump as_of)"

echo
echo "Done. Still worth running before a push: npx --yes awesome-lint (CI-blocking)."
