# State of the AI Gateway landscape — 2026

_Companion to [the list](README.md). The list tells you **which** gateway; this page tells you **where the space is**, **how to measure anything in it**, and **where it is heading** — with the evidence and a stated way to prove each claim wrong._

Last reviewed: 2026-08-12 · Star counts and repo states verified against the GitHub API on that date.

**Languages:** English · [简体中文](LANDSCAPE.zh-CN.md)

## Contents

- [The one-paragraph version](#the-one-paragraph-version)
- [What happened to the independent layer](#what-happened-to-the-independent-layer)
- [What is growing at the same time](#what-is-growing-at-the-same-time)
- [What it means when you pick today](#what-it-means-when-you-pick-today)
- [The evaluation standard: six checks](#the-evaluation-standard-six-checks)
- [Where it heads next](#where-it-heads-next)
- [How to argue with this page](#how-to-argue-with-this-page)

## The one-paragraph version

The standalone AI gateway is being squeezed from both ends. Underneath, the hyperscalers now ship routing, spend caps and observability natively, so "buy a gateway" stopped being the obvious answer for single-cloud traffic. Above, the coding-agent wave produced a second class of gateway — subscription wrappers, protocol translators, token compressors — that out-stars most of the infrastructure the phrase "AI gateway" used to mean. The part that consolidated is the independent middle: a company whose entire product was the gateway. What survives that squeeze is open-source code you can keep, or a gateway absorbed into a platform you were already paying for.

## What happened to the independent layer

| What | When | Evidence |
| --- | --- | --- |
| **TensorZero** archived — VC-backed OSS LLMOps gateway ($7.3M seed) | 2026-06-11 | Repo read-only, verified `archived: true`; Apache-2.0 code and community forks remain usable |
| **Pydantic AI Gateway** archived, folded into Logfire | 2026-03-30 | Repo `archived: true`; the gateway became a feature of a platform |
| **Helicone** acquired by Mintlify, positioned as maintenance | 2026-03 | Repo still receiving commits — usable today; the open question is roadmap, not liveness |
| **Portkey** acquired by Palo Alto Networks (announced 2026-04-30) | closed 2026-05-29 | The gateway became the control plane for a security platform |
| **Stripe reportedly in talks for OpenRouter** (~$10B) | 2026-07-23 | WSJ report — **unconfirmed**; a signal about where value is accruing, not a fact |
| **BricksLLM** and **Glide** — quiet, never archived | since 2025-01 / 2024-08 | No commits. The common failure mode is silence, not a shutdown notice |

The pattern is not "open source lost." Three of the six kept their code alive and lost their company. That distinction is the actionable part.

## What is growing at the same time

Consolidation, not collapse — the same year produced clear winners:

- **LiteLLM** keeps compounding as the default self-hosted choice, and is the reference implementation most clients are tested against.
- **Bifrost** won on a number rather than a narrative: the lowest independently measured per-request overhead.
- **Envoy AI Gateway** reached v1.0 on 2026-06-23 — the first CNCF-backed, production-stable open-source option, which matters to buyers who need a foundation behind the project.
- **The coding-agent tier** — CLIProxyAPI, OmniRoute, sub2api, 9router — now out-stars most "serious" gateway infrastructure. Whatever one thinks of the terms-of-service risk, this is where the users went.
- **Token-compression proxies** (headroom, Paritok) are the fastest-rising category, and they are not routers at all. They attack the bill from the token side rather than the price side.

## What it means when you pick today

1. **Bus factor is a selection criterion, not a footnote.** Two projects above went read-only while still being recommended in current blog posts. Check the last commit date before the feature matrix — the list now does that check for you and publishes the result: [Maintenance signal](README.md#-maintenance-signal--what-the-star-count-hides) lists every tracked repo that is archived or has gone six months without a commit, refreshed daily from the GitHub API. Stars are cumulative and never fall when a project stops shipping; that table is the correction.
2. **Prefer the layer you can keep.** Permissively licensed code with forks survives its company; a hosted control plane does not. TensorZero's code is still usable, its company is not.
3. **If your traffic lives in one cloud, the native gateway is now a real answer.** Bedrock, Azure API Management, Vertex and Databricks Unity all shipped routing plus spend caps during 2026. Worse portability, far less to operate — a trade worth making explicitly rather than by default.
4. **Star count is popularity, not fitness.** The most-starred project in the list is a compression proxy that cannot route between providers. Read what a thing *is* before reading how popular it is.

## The evaluation standard: six checks

Six checks decide whether a gateway is right, ordered by how early they usually bite. They apply to anything on any list — use them on entries here, and use them on the ones we have not found yet.

| # | Check | What good looks like | How to verify |
| --- | --- | --- | --- |
| 1 | **Protocol fidelity** — does it break your client? | Claude Code / Codex traffic survives translation with tools and streaming intact | [The compatibility surface](docs/protocol-translation.md) · [measured results](https://cuihuan.github.io/llm-gateway-bench/article.html?slug=does-your-gateway-break-claude-code) |
| 2 | **Added latency** — the tax on every single request | Single-digit milliseconds, measured rather than claimed | [overhead.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/overhead.json) |
| 3 | **Cache economics** — is the discount still reaching you? | Cache reads actually billed at the provider's discounted rate; hit rate above the break-even point | [Caching economics](docs/caching-economics.md) |
| 4 | **Metering honesty** — does its count match the invoice? | Spend survives a crash mid-stream; reasoning and cached tokens counted correctly | [Virtual keys, budgets and metering](docs/virtual-keys-metering.md) |
| 5 | **Failure behaviour** — what happens when a provider dies | Retries by default, no double billing on retry, a documented rate-limit contract | [Failover and reliability](docs/failover-reliability.md) |
| 6 | **Trust surface** — who sees the prompt, who signs the release | Stated retention, signed releases, patched CVEs, a real bus factor | [Retention matrix](README.md#-who-sees-your-prompts--the-data-retention-matrix) · [supply chain](README.md#-supply-chain-security--who-signs-their-releases-and-what-actually-got-hacked) |

Scored per gateway across compliance, markup, security, stability and observability in the [scorecard](BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). Checks 1 and 2 are reproducible with [llm-gateway-bench](https://github.com/cuihuan/llm-gateway-bench); the fidelity probe behind check 6 is [canary_check.py](scripts/canary_check.py).

A gateway that fails check 1 is disqualified regardless of the other five — a router that silently drops your tool calls is not cheaper, it is broken. Checks 3 and 4 are where money quietly leaks, and they are the two nobody markets against.

## Where it heads next

Three calls, each with the observation that would prove it wrong. They are dated so they can be scored later rather than quietly forgotten.

| Call | Proved wrong if… |
| --- | --- |
| The independent hosted gateway keeps consolidating; survivors are open-source-core or absorbed into a platform | A new independent hosted gateway reaches a public SLA and named enterprise customers without being acquired |
| Coding-agent traffic becomes the default meaning of "gateway", making protocol fidelity matter more than provider count | Clients converge on one wire format, so translation stops being a source of failure |
| Token compression becomes a standard gateway feature rather than a separate proxy | Two of the top self-hosted gateways ship it natively and the standalone compressors stop growing |

## How to argue with this page

Every claim above is dated and sourced, which means it is falsifiable. If a call is wrong, the useful response is evidence, not a counter-opinion: a repo state, a measured number, a dated announcement. [Open an issue](https://github.com/cuihuan/awesome-ai-gateway/issues/new) with it and this page changes — that is the whole point of writing the disproof conditions down first.
