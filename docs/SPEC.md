# awesome-ai-gateway — Project Spec

## Goal

A curated, pain-point-oriented list of AI gateways / LLM proxies **plus a handbook
that explains how they work and fail**, together becoming the default answer to both
"which AI gateway should I use" and "how do AI gateways actually work".

**Success metric (revised 2026-07-29, when the handbook completed):** not a star count.
Stars measure a launch; what this project is trying to be is *cited*. The metric is
**weekly passive citations** — new referrer domains in Traffic Insights, unsolicited
mentions in threads and vendor docs, and AI-answer-engine citation share — with star
count kept only as a lagging sanity check. Rationale and the comparable-repo evidence
are in `OPERATIONS.md` §13; the earlier "400+ stars, then sindresorhus/awesome" target
was list-shaped thinking and is retired (the awesome-lint conformance it implied is
done and CI-gated regardless).

## Principles

1. **Pain-point first, not vendor first.** Sections answer a user need
   (cheapest access, compliance, self-hosting, China ecosystem, MCP/agents),
   not a vendor taxonomy.
2. **The shareable asset is the comparison table + decision tree**, not the link list.
3. **Every automated commit must change real content** (star counts, new releases).
   No timestamp-only commits.
4. **Accuracy over completeness.** Stars are approximate and refreshed daily by CI.
   Dead/stale projects are labeled, not silently kept.

## Repository contract

| Path | Purpose |
|---|---|
| `README.md` | English main list. Star cells wrapped in `<!--s:owner/repo-->…<!--/s-->` markers. |
| `README.zh-CN.md` | Simplified-Chinese mirror, same markers. |
| `data/projects.json` | Repos tracked for the auto-updated "Recent releases" section. |
| `data/releases.json` | Machine-readable output of the last refresh (for agents/consumers). |
| `scripts/update_readme.py` | Stdlib-only updater: refreshes star markers in both READMEs and rewrites the block between `<!-- RELEASES:START -->` / `<!-- RELEASES:END -->`. |
| `scripts/test_update_readme.py` | Unit tests for all pure functions of the updater (required by project rule: interfaces ship with tests). |
| `.github/workflows/daily-update.yml` | Daily cron (02:23 UTC); commits only when content changed. |
| `.github/workflows/ci.yml` | Unit tests (blocking) + cost-table freshness check (blocking) + awesome-lint (advisory). |

### Evaluation set (demonstrates rigor)

| Path | Purpose |
|---|---|
| `BENCHMARKS.md` / `BENCHMARKS.zh-CN.md` | The evaluation hub: model benchmarks, scenario picks, computed token cost, gateway scorecard. Cost cells live between `<!-- COST:<id>:START/END -->` markers. |
| `data/models.json` | Source of truth for model pricing (drives cost tables) + a dated benchmark snapshot. `scenario_cost: true` flags the representative cost set; `reasoning: true` bills thinking tokens as output. |
| `data/gateways_eval.json` | Gateway scorecard snapshot (★1–5 on compliance/security/stability + markup), per the rubric in BENCHMARKS.md. |
| `scripts/cost_calc.py` | Recomputes every cost cell from `models.json` and rewrites the COST blocks in both docs (EN/zh localized). No cost number is ever hand-typed. |
| `scripts/test_cost_calc.py` | Unit tests for the cost engine (required by project rule). |

**Evaluation principles:** every figure is sourced + dated; costs are *computed and reproducible*, not asserted; benchmarks pair static scores with human-preference + contamination-resistant sets; gateway scores follow a published rubric; CVEs are disclosed honestly (credibility > marketing).

## Update cadence

- **Daily (automated):** star counts, recent releases block, `data/releases.json`.
- **Weekly (human):** new projects, "What's new" curated news, category adjustments.

## Out of scope

- Pricing scraping (link to source pages instead; avoid stale-price liability).
- Gray-area reverse-engineered "free-api" relays (ToS risk — excluded by policy).
