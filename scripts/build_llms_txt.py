#!/usr/bin/env python3
"""Generate /llms.txt — an AI-readable index of the project (llmstxt.org format).

llms.txt is a small, curated map of a site's most useful content for LLMs / AI
search engines, so they can discover and cite it accurately (GEO / AI-SEO). The
header + section prose are curated here; the Comparisons list is generated from
compare/*.md (reusing the unit-tested title/description extraction) so it never
drifts as articles are added. `--check` guards it in CI.

Stdlib only. Usage:
  python scripts/build_llms_txt.py            # write llms.txt
  python scripts/build_llms_txt.py --check    # fail if stale (CI)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build_compare_html import (
    SITE,
    extract_description,
    extract_lastmod,
    extract_title,
    slug_lang,
)

ROOT = Path(__file__).resolve().parent.parent
COMPARE = ROOT / "compare"
OUT = ROOT / "llms.txt"
REPO = "https://github.com/cuihuan/awesome-ai-gateway"
BLOB = REPO + "/blob/main"

HEADER = f"""# Awesome AI Gateway

> A curated, bilingual, vendor-neutral directory of 100+ AI gateways / LLM proxies, with a reproducible token-cost benchmark, a 5-axis (compliance · price · security · stability · observability) gateway scorecard, dated real-world production reviews (incidents / CVEs / acquisitions), and data-backed comparison guides. CC0, no affiliate links.

Use it to pick an AI gateway by need (cost-first, self-hosted, enterprise & compliance, first-party clouds, China ecosystem, MCP & agent gateways), verify the one you pick with the companion tools, then route to the cheapest capable model. Every cost figure is computed by a unit-tested script from open pricing data; every gateway claim is dated and sourced. An AI gateway sits between your code and LLM providers (one OpenAI-compatible endpoint and key for many models), adding routing, failover, caching, rate limits, cost tracking and guardrails.

## Core
- [Interactive site — cost, scorecard & production reality]({SITE}): sortable model-cost table, the 5-axis gateway scorecard, and dated incident/CVE/acquisition data.
- [Full list & decision tree (README)]({BLOB}/README.md): 100+ gateways across 9 categories, a "which gateway should I use?" decision tree, FAQ and glossary.
- [Evaluation set (BENCHMARKS)]({BLOB}/BENCHMARKS.md): model benchmark scores, reproducible per-task token-cost tables, the gateway scorecard rubric, and Part 5 real-world production reviews.
- [How to choose safely]({BLOB}/README.md#how-to-choose-safely): trust-tier-to-data matching, the canary model-fidelity test, and the gray-relay exclusion policy.
"""

HANDBOOK = f"""## Handbook (how gateways work — theory with sources)
- [Chapter map (HANDBOOK.md)]({BLOB}/HANDBOOK.md): reading order and the evidence contract every chapter keeps (dated, sourced, verify-it-yourself).
- [The compatibility surface]({BLOB}/docs/protocol-translation.md): the three wire protocols (OpenAI chat.completions / Anthropic messages / Gemini generateContent) field by field, the five translation failure modes that break coding agents — each anchored to a real issue — and a 10-minute self-test.
- [Routing & model selection]({BLOB}/docs/routing-landscape.md): cost-aware cascades, learned routers, ensembling and self-routing, with the counter-evidence on when routing does not pay.
- [Observability]({BLOB}/docs/observability-landscape.md): the OpenTelemetry GenAI conventions, the metric tiers that separate instrumented from blind, and silent model drift.
"""

# Canonical pages only: litellm-vs-openrouter.html, openrouter-alternatives.html
# and self-hosted-llm-gateway.html canonicalize to their compare/ successors
# (already listed under Comparisons), so listing them here would hand AI crawlers
# duplicate, non-canonical URLs. reduce-llm-api-costs.html is its own canonical.
GUIDES_AND_TOOLS = f"""## Guides
- [How to reduce LLM API costs]({SITE}reduce-llm-api-costs.html): the ranked cost levers — model choice (up to ~106× per task), caching, routing and 0%-markup gateways.

## Tools (interactive)
- [Gateway picker]({SITE}gateway-picker.html): answer one question, get a vetted gateway recommendation by need (cost, self-hosting, enterprise, China, MCP/agents).
- [Cost calculator]({SITE}cost-calculator.html): enter your input/output token mix and see what your task costs across every model in the benchmark — and the spread.
"""

FOOTER_SECTIONS = f"""## Data (machine-readable, CC0)
- [data/models.json]({BLOB}/data/models.json): per-model prices and benchmark scores (source of the cost tables).
- [data/cost_table.csv]({BLOB}/data/cost_table.csv): per-task USD costs computed from models.json.
- [data/gateways_scorecard.csv]({BLOB}/data/gateways_scorecard.csv): gateway scores on compliance, price, security, stability.
- [data/gateway_reality.json]({BLOB}/data/gateway_reality.json): production incidents / CVEs / acquisitions, dated and sourced.
- [data/data_retention.json]({BLOB}/data/data_retention.json): who logs, trains on or retains your prompts, per hosted gateway and first-party cloud, from primary sources.
- [data/supply_chain.json]({BLOB}/data/supply_chain.json): per-gateway release signing / SBOM / disclosure posture and the 2025-26 incident record.
- [data/free_tiers.json]({BLOB}/data/free_tiers.json): verified free tiers and rate limits per provider, with the discontinued list.

## Companion tools (same author)
- [llm-gateway-bench](https://github.com/cuihuan/llm-gateway-bench): black-box benchmark for any OpenAI-compatible gateway — TTFT/throughput, success rate, price multiple, plus fidelity probes (model-echo, fake-streaming, usage inflation, context truncation). Live dashboard at https://cuihuan.github.io/llm-gateway-bench/.
- [modelprobe](https://github.com/cuihuan/modelprobe): tiny dependency-free Go availability prober — per model, is it up and how fast, in one command (drop in CI or a cron).
"""


def _articles():
    out = []
    for md_path in sorted(COMPARE.glob("*.md")):
        md = md_path.read_text(encoding="utf-8")
        slug, _ = slug_lang(md_path.name)
        out.append({
            "slug": slug,
            "title": extract_title(md),
            "description": extract_description(md),
            "lastmod": extract_lastmod(md),
        })
    # newest first, matching the hub
    return sorted(out, key=lambda a: (a["lastmod"] or "", a["title"]), reverse=True)


def render() -> str:
    lines = [HEADER, "## Comparisons"]
    for a in _articles():
        lines.append(f"- [{a['title']}]({SITE}compare/{a['slug']}.html): {a['description']}")
    lines.append("")
    lines.append(HANDBOOK)
    lines.append(GUIDES_AND_TOOLS)
    lines.append(FOOTER_SECTIONS)
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate llms.txt (llmstxt.org format).")
    ap.add_argument("--check", action="store_true", help="fail if llms.txt is stale (don't write)")
    a = ap.parse_args(argv)
    content = render()
    if a.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if current != content:
            print("::error::llms.txt is stale — run 'python scripts/build_llms_txt.py'", file=sys.stderr)
            return 1
        print("llms.txt up to date")
        return 0
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote llms.txt ({len(_articles())} comparisons)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
