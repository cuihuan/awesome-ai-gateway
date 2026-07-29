# The AI Gateway Handbook 📖

> Learn how AI gateways actually work — the same way this repo does everything else: **dated, sourced, reproducible**. The [list](README.md) tells you *which* gateway; the handbook teaches you *how they work and why they fail*, so the picks stop being magic.
>
> **Languages:** English · 中文版每章随英文版同步(见各章内语言切换)

## The contract every chapter keeps

- Every claim is **dated and linked** — primary sources, real GitHub issues, or our own measured data ([llm-gateway-bench](https://github.com/cuihuan/llm-gateway-bench)), never "everyone knows".
- Three levels of truth are always labeled: **standard/spec** · **vendor claim** · **our own measurement or synthesis**.
- Each chapter ends with **how to verify this yourself** — if you can't check it, we shouldn't have written it.
- Failure modes come with receipts: the incident, the issue number, the bill.

## Chapters

| # | Chapter | Status | What you'll understand |
|---|---|---|---|
| 1 | [The Compatibility Surface — why gateways break Claude Code](docs/protocol-translation.md) | ✅ **live** (2026-07-29) | The three wire protocols, field-by-field; the five translation failure modes (each anchored to a verified issue); the measured fidelity results; a 10-minute self-test |
| 2 | [Routing & model selection: the research landscape](docs/routing-landscape.md) | ✅ **live** | Cost-aware cascades, learned routers, ensembling, self-routing — and the honest counter-evidence on when routing *doesn't* pay |
| 3 | [Observability: what to measure and why](docs/observability-landscape.md) | ✅ **live** | The OTel GenAI conventions, the metric tiers that separate instrumented from blind, silent model drift |
| 4 | Anatomy of an AI gateway | 🚧 planned (next) | The canonical request lifecycle (auth → virtual key → guardrails → route → translate → retry → stream → meter → telemetry), where each failure mode lives — and when you *shouldn't* run a gateway at all |
| 5 | Failover & reliability | 🚧 planned | Retry-within vs across provider groups, cooldowns and circuit breakers, mid-stream failure semantics, retry idempotency and double-billing, the 429/TPM math |
| 6 | Caching economics | 🚧 planned | The two cache layers (provider prompt cache vs gateway response cache), savings = hit rate × discount × prefix share, the 30-second verification, KV-aware routing |
| 7 | Virtual keys, budgets & multi-tenancy | 🚧 planned | Metering pipelines, pre-check vs post-hoc budget enforcement under concurrency, accounting for streamed/reasoning/cached tokens, crash-safe billing |
| 8 | MCP & agent gateways | 🚧 planned | Why agent traffic ≠ completion traffic, tool-level authz, secret brokering, prompt-injection defenses, A2A — the first neutral survey of the fastest-moving category |

Reading order: 1 → 4 → 5 → 6 pick up the core; 2, 3, 7, 8 stand alone. Chapters ship roughly monthly; the freshest evidence always lives in the [list](README.md) and [BENCHMARKS](BENCHMARKS.md) — chapters link into both rather than duplicating them.

## Why a handbook inside an awesome list

Because "which gateway" is unanswerable without "how do gateways fail", and every existing explanation is written by a vendor selling one. The list supplies the evidence base (reproducible cost tables, scorecards, incident receipts, a canary you can run); the handbook supplies the theory that makes the evidence legible. Corrections and chapter requests: [open an issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every chapter is falsifiable by design.
