# Changelog

All notable changes to this curated list are documented here.
The list's data (stars, releases) is refreshed daily by CI; this changelog tracks
structural and editorial changes.

## [Unreleased]

### 2026-07-28 — user-value batch: supply-chain matrix + July scoreboard rebase

- **🛡️ Supply-chain security matrix (new buying axis)** — per-gateway release signing / SBOM /
  SECURITY.md / 2025–26 advisories, machine-checked against repos, registries and CVE.org, plus a
  primary-sourced incident record (LiteLLM PyPI backdoor & the TeamPCP chain, Shai-Hulud worms,
  the malicious-relay measurement study) and a debunked-claims list (two blogspam Kong CVEs that
  don't exist). Machine-readable `data/supply_chain.json`, 30-day freshness CI, both languages.
- **📊 Benchmark table rebased to consistent single sources** — AA Index v4.1 (the v4.0 column was
  a dead scale), AA independent GPQA/HLE runs, BenchLM SWE boards, arena.ai Elo. Five July
  flagships added (Claude Opus 5, GPT-5.6 Sol, Kimi K3, GLM-5.2, Gemini 3.6 Flash); the
  Fable-5-vs-Mythos-5 SWE-Pro misattribution fixed.
- **💰 Pricing re-verified 12/13 exact** against official pages; the exception was the *retired*
  Grok 4 whose stand-in price was 2.4× the real successor rate — cost tables and charts rebuilt,
  every previously-cited figure (83×/106× spreads, $0.21-vs-$17.50) still holds.
- **Otari (Mozilla AI) added** to Self-hosted (66→344★ in three weeks); DEEIX-Chat evaluated and
  kept off-list (workspace/UI, not on the request path).

## [1.1.0] - 2026-07-08

The "evidence engine" release — three things **no other gateway list measures**, plus an answer-first rebuild grounded in what developers actually ask.

### Added — independent measurements (exclusive)
- **⏱️ Gateway overhead, measured** — a reproducible harness (mock upstream, interleaved rounds,
  no API keys, monthly CI on a neutral runner) benchmarks the latency each self-hosted gateway
  *itself* adds: **Bifrost 0.56 ms · Portkey OSS 2.69 ms · LiteLLM 5.41 ms** per request. Reads
  vendor marketing honestly (Bifrost's "50×" is loaded-throughput, not per-request; Portkey's
  "<1 ms" didn't reproduce on shared CI). Data: `llm-gateway-bench/data/overhead.json`.
- **🔌 Protocol-translation fidelity, measured** — does the gateway relay tool-calls / streaming /
  usage intact (the #1 real-world failure — "claude code" is in 400+ LiteLLM issues)? **LiteLLM 3/3
  · Bifrost 3/3 · Portkey OSS v1.15.2 1/3** (its custom-host streaming errored on a clean CI runner;
  hosted product untested, caveated). Data: `llm-gateway-bench/data/fidelity.json`.
- **🔒 Data-retention / ZDR / logging matrix** — primary-source answer to "who sees/logs/trains on my
  prompts?" across 12 hosted gateways + first-party clouds. Surfaces facts no other list has: Martian's
  ToS licenses your prompts to train its models; OpenAI's 30-day deletion is under the NYT legal hold;
  Azure dropped its 30-day figure; Vertex logs standard non-invoiced accounts. Machine-readable
  `data/data_retention.json`.

### Added — answer-first UX (grounded in mined Reddit/HN questions)
- **⚡ 10-second answers** block above the fold — the 7 questions developers actually ask, answered in
  one line each (cheapest access, model-cost 106× spread, proxy overhead, does caching survive the
  router, who sees my prompts, LiteLLM alternatives, will it break my Claude Code).
- **The requirements map** — the 9 jobs a gateway is bought for, each → the question it answers + where
  the evidence lives; survey-grounded (Amplify 2026: 87% run multiple models, cost = #2 monitored metric).
- **💾 "Prompt caching through a gateway"** — the ecosystem's most-asked, worst-answered question,
  answered with evidence + a 30-second usage-field self-test.
- **🔌 Use the data — it's an API** — every dataset as a raw CC0 URL with a refresh cadence.
- Above-the-fold **animated demo GIF**; five-axis interactive scorecard on the Pages site.

### Added — scorecard, coverage, community
- **Observability is now a first-class scorecard axis** (2026-07-06): all 23 scored gateways
  re-reviewed against a published 5-pillar evidence rubric (metrics export · trace export ·
  per-key token/cost attribution · log export · dashboard) — four parallel research passes over
  official docs, per-gateway evidence machine-readable in
  [`data/gateways_eval.json`](data/gateways_eval.json) (`observability_note`) and exported to
  CSV. The scorecard is five-axis (合规·价格·安全·稳定·可观测); README gained a
  **requirements map** (the 9 jobs a gateway is bought for → where the evidence lives) and
  "How to choose safely" gained a **supply-chain step** grounded in the 2026 LiteLLM incidents.
- Coverage sweep (2026-07-06) added **6 verified gateways** the list was missing — led by
  the two glaring high-star gaps **[OmniRoute](https://github.com/diegosouzapw/OmniRoute)**
  (~12k★, coding-agent token-saver) and **[Chat Nio / CoAI](https://github.com/coaidev/coai)**
  (~9.2k★, multi-tenant billing panel) — plus **Traceloop Hub** (Rust/OTel), and the routers
  **workweave/router**, **UncommonRoute** and **OrcaRouter Lite**. Each verified live via the
  GitHub API (stars, license, activity) before listing; all release-tracked.
- Directory grown to **~122 entries** since 1.0.0. A multi-agent accuracy/coverage audit
  added **17 verified gateways** — including the previously-missing high-star projects
  **CLIProxyAPI**, **sub2api**, **9router** and **NVIDIA Dynamo**, plus enterprise/cloud
  vendors **Axway Amplify**, **Red Hat Connectivity Link**, **Sensedia** and
  **Tencent Cloud AI Gateway** — each with honest risk/maintenance caveats.
- **Bilingual high-intent guide cluster** (EN + Simplified Chinese): *LiteLLM vs OpenRouter*,
  *OpenRouter alternatives*, *self-hosted gateways*, and *how to cut LLM API costs* —
  cross-linked with an interactive **cost calculator** and **gateway picker**.
- First inbound community contribution — **nullsink** added by
  [@c99e](https://github.com/c99e) in [#14](https://github.com/cuihuan/awesome-ai-gateway/pull/14). 🙏
- **CoderPlan** (China-market relay) added by [@onepaperbox](https://github.com/onepaperbox) in
  [#21](https://github.com/cuihuan/awesome-ai-gateway/pull/21) — endpoint independently re-verified
  (`api.coderplan.ai/v1` → `new_api_error`, i.e. new-api-based) before listing, with the standard
  new-and-unverified caveat. 🙏
- **KeepRouter** (OpenAI+Anthropic-compatible gateway, native `/v1/messages`) added by
  [@Digidai](https://github.com/Digidai) in [#22](https://github.com/cuihuan/awesome-ai-gateway/pull/22)
  — live endpoint verified before merge; CoderPlan + KeepRouter also added to the relay watch-list. 🙏
- **RouterPlex** added by [@MaridWSH](https://github.com/MaridWSH) in
  [#23](https://github.com/cuihuan/awesome-ai-gateway/pull/23) and **AI快站 (aifast.club)** added by
  [@KKWANG4444](https://github.com/KKWANG4444) in [#24](https://github.com/cuihuan/awesome-ai-gateway/pull/24)
  — both live endpoints verified before merge (LiteLLM-style / new-api error signatures respectively);
  both on the relay watch-list. 🙏
- **TierUp** (tier-based relay via OpenRouter) added by [@atxapple](https://github.com/atxapple) in
  [#26](https://github.com/cuihuan/awesome-ai-gateway/pull/26) — exceptionally honest self-disclosure (solo-built, subsidized, ~zero users); live endpoint verified, on the watch-list. 🙏

### Changed
- Account-less / crypto-only relays (**Loop Gateway**, **nullsink**) now carry an explicit
  "new & unverified" caveat and sit on the community relay watch-list, matching the FlintAPI
  precedent — listed on evidence, with the resale/recourse risk stated plainly.
- Marked **TensorZero** (archived June 2026) and **Pydantic AI Gateway** (merged into
  Pydantic Logfire) as deprecated/renamed — both verified `archived` via the GitHub API.

### Contributors
Thanks to [@c99e](https://github.com/c99e), [@onepaperbox](https://github.com/onepaperbox),
[@Digidai](https://github.com/Digidai), [@MaridWSH](https://github.com/MaridWSH),
[@KKWANG4444](https://github.com/KKWANG4444) and [@atxapple](https://github.com/atxapple) for community PRs. Spotted a gateway we're missing, or run
one in production? See [CONTRIBUTING](CONTRIBUTING.md) — most additions are a 2-line PR.

## [1.0.0] - 2026-06-18

First tagged release. The list is stable, bilingual, and CI-verified.

### Added
- Pain-point-organized directory of **100+ AI gateways / LLM proxies** across 9 categories
  (cost-first, self-hosted, enterprise & compliance, first-party clouds, China ecosystem,
  MCP & agent gateways, and cross-cutting routing/observability).
- **Decision tree** ("which gateway should I use?") plus a 10-second fast-answer table.
- **Reproducible cost benchmark** — a unit-tested Python script computes per-task token costs
  from open pricing JSON (the 106× spread is recomputed, not hand-typed).
- **Gateway scorecard** — compliance / price / security / stability scored ★1–5 against a
  published rubric, with honest CVE disclosure.
- **Evidence-based gray-relay exclusion** citing measurement papers, plus `canary_check.py`,
  a runnable model-fidelity checker, and a community relay watch-list process.
- **6 deep-dive comparison pages** (LiteLLM/OpenRouter/Portkey, LiteLLM alternatives,
  OpenRouter alternatives, Cloudflare vs Vercel, best self-hosted, one-api vs new-api).
- Bilingual **English + Simplified Chinese** throughout; interactive companion site on GitHub Pages.

### Infrastructure
- Daily GitHub Actions refresh of star counts and latest releases.
- CI: 69 unit tests, cost-table/CSV drift checks, advisory awesome-lint, and link-health
  checking (lychee) on PRs and weekly.

[1.1.0]: https://github.com/cuihuan/awesome-ai-gateway/releases/tag/v1.1.0
[1.0.0]: https://github.com/cuihuan/awesome-ai-gateway/releases/tag/v1.0.0
