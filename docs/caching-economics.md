# Caching Economics — the two cache layers, what they actually save, and how to prove it

*Last updated 2026-07-29 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

**Languages:** English · [简体中文](caching-economics.zh-CN.md)


> 📊 **Key numbers** · Three things share the word "cache" and only one of them can hand you a wrong answer. **Provider prompt caching** reads at exactly **0.1× base input** on every current Anthropic, OpenAI and Gemini flagship — derived from the official price sheets on **2026-07-29**, not from vendor prose (Claude Opus 5: $0.50 read vs $5.00 input) — and at **0.02×** / **0.008333×** on DeepSeek V4-Flash / V4-Pro. But writes are not free, and that is the fact missing from every "90% discount" writeup: Anthropic bills a 5-minute cache write at **1.25×** base input and a 1-hour write at **2×**, and **OpenAI now bills 1.25× on GPT-5.6 and later**. So below a **21.74%** hit rate (Anthropic 5m / OpenAI 5.6+) or **52.63%** (Anthropic 1h), turning prompt caching on costs you *more* than leaving it off. On our worked 50-turn Claude Opus 5 coding session the bill goes **$6.6250 → $2.2400 (−66.19%)** — and a gateway that writes the cache but never hits it makes that same session **18.87% more expensive than never enabling caching at all**. **Gateway response caching** is a different animal with a different risk: Higress's `ai-cache` keys on the last message and nothing else — not the model, not the tenant — with a default TTL of **0, meaning never expires** (read at `c8b8279`). And **KV-cache-aware routing**, the third thing called "cache", is not a cache at all: its worst case is latency, never a wrong answer.

[Chapter 4](gateway-anatomy.md) established *where* a cache sits in the request path, and found that in two of seven gateways a cache hit escapes budget enforcement entirely. This chapter answers the next question: **what is the cache actually worth, and how do you prove you're getting it?** The honest answer has three parts — a formula whose dominant term is not the discount, a set of vendor rules that decide whether you get the discount at all, and a class of gateway-side caches whose *correctness* is the thing at risk rather than your bill.

Sourcing is stated inline. Vendor pricing and behaviour are quoted from the official pages with a retrieval date; gateway behaviour is read from source at a pinned commit; arithmetic and derivations are marked as ours and are re-runnable; figures taken from this repo's data files are marked *repo-sourced* with their `as_of`. Where something could not be verified, that is said in place rather than smoothed over.

---

## 1. The concept in 60 seconds

Three distinct mechanisms wear the word "cache" in this category — the title says *two* layers because only two of them are caches you are billed for and can be wrong about; the third borrows the word and is neither. Conflating them is the single most common error in gateway evaluations, because they differ on the only axis that matters — **what happens when the cache is wrong.**

| Tier | What is stored | Who owns it | Charged how | Worst case when it misbehaves |
|---|---|---|---|---|
| **1 · Provider prompt cache** | The model server's attention state for an exact byte prefix of your prompt | The provider (Anthropic, OpenAI, Google, DeepSeek) | Write premium + read discount, per token | You silently pay full price — or, if writes are charged and never hit, **more than full price** |
| **2 · Gateway response cache** | A whole prior response, keyed on some function of the request | The gateway you installed | Free (you skip the provider call entirely) | **A confidently wrong answer, 200 OK, no error** |
| **3 · KV-cache-aware routing** | *Nothing.* An index of which replica recently saw which prefix | Your inference platform (vLLM/EPP) | Free | Slower time-to-first-token. The response is always generated fresh |

The README's [prompt-caching section](../README.md#-prompt-caching-through-a-gateway--the-money-question) owns tier 1's headline and the 30-second test. This chapter goes one level down on all three: the arithmetic that decides whether tier 1 pays, the key contents that decide whether tier 2 is safe, and why tier 3 belongs in a different mental bucket entirely.

The framing that keeps people honest: **tier 1 is a billing optimization that can only cost you money; tier 2 is a correctness surface that can only cost you trust.** They are not substitutes and their risks do not net out.

---

## 2. The savings formula, and what actually dominates it

### 2.1 The formula

**Ours**, derived from the verified multipliers in §3. Let `p` = input price/token, `q` = output price/token, `C` = cached-prefix tokens, `U_tot` = uncached input tokens over the session, `O_tot` = output tokens, `N` = turns, `w` = write multiplier, `d` = read multiplier, `h` = fraction of turns that hit.

Define two workload shape terms:

- **`f`** = `N·C / (N·C + U_tot)` — the share of would-be input tokens that live in the stable, cacheable prefix.
- **`r`** = `q·O_tot / [p(N·C + U_tot) + q·O_tot]` — output's share of the uncached bill.

Then session savings are:

```text
S  =  f · (1 − r) · (A·h − B)          where   A = w − d      B = w − 1
```

Only `A` and `B` are provider-specific. Everything else is *your* workload.

| Provider / mode | `w` (write) | `d` (read) | `A = w−d` | `B = w−1` | Break-even `h = B/A` | Ceiling at `h = 1` |
|---|---|---|---|---|---|---|
| Anthropic, 5-minute TTL | 1.25× | 0.1× | 1.15 | 0.25 | **21.74%** | 90.00% |
| Anthropic, 1-hour TTL | 2.00× | 0.1× | 1.90 | 1.00 | **52.63%** | 90.00% |
| OpenAI GPT-5.6 and later | 1.25× | 0.1× | 1.15 | 0.25 | **21.74%** | 90.00% |
| OpenAI before GPT-5.6 | 1.00× | 0.1× | 0.90 | 0 | **0%** | 90.00% |
| Gemini, implicit caching | 1.00× | 0.1× | 0.90 | 0 | **0%** | 90.00% |
| DeepSeek V4-Flash | 1.00× | 0.02× | 0.98 | 0 | **0%** | 98.00% |
| DeepSeek V4-Pro | 1.00× | 0.008333× | 0.9917 | 0 | **0%** | 99.17% |

**Read the break-even column before the ceiling column.** `S` is negative whenever `h < B/A`. On Anthropic's 1-hour cache you must hit **more than half the time just to break even against not caching at all**. Anthropic's own pricing page states the same thing in prose, and it matches our per-turn form exactly: *"caching pays off after just one cache read for the 5-minute duration (1.25x write), or after two cache reads for the 1-hour duration (2x write)"* — our break-even lands at N = 1.15/0.9 = 1.28 turns (so N=2, one read) and N = 1.90/0.9 = 2.11 turns (so N=3, two reads). Exact match.

### 2.2 Worked example — a Claude Opus 5 coding agent

Assumptions **stated up front and ours, not sourced**: static prefix `C` = 20,000 tokens (system prompt + tool definitions + `CLAUDE.md`); `N` = 50 turns, all inside the rolling 5-minute TTL; new uncached input `U` = 3,000 tok/turn (tool results, file reads); output `O` = 700 tok/turn. Prices are Anthropic's official Opus 5 rates, retrieved 2026-07-29: **$5.00 input / $6.25 5m-write / $10.00 1h-write / $0.50 read / $25.00 output** per MTok.

| Line item | No cache | 5-minute cache | 1-hour cache |
|---|---|---|---|
| Cache write | — | 20,000 tok @ $6.25/MTok = **$0.1250** | 20,000 tok @ $10.00/MTok = **$0.2000** |
| Cache reads | — | 49 × 20,000 = 980,000 @ $0.50 = **$0.4900** | 980,000 @ $0.50 = **$0.4900** |
| Uncached input | 50 × 23,000 = 1,150,000 @ $5.00 = **$5.7500** | 150,000 @ $5.00 = **$0.7500** | 150,000 @ $5.00 = **$0.7500** |
| Output | 35,000 @ $25.00 = **$0.8750** | **$0.8750** | **$0.8750** |
| **Session total** | **$6.6250** | **$2.2400** | **$2.3150** |
| **Saved** | — | **$4.3850 = 66.19%** | **$4.3100 = 65.06%** |

Closed-form cross-check: `f` = 1,000,000/1,150,000 = 0.869565, `r` = 0.8750/6.6250 = 0.132075, `h` = 49/50 = 0.98 → `S` = 0.869565 × 0.867925 × (1.15×0.98 − 0.25) = 0.6619 ✓. The ladder is plain arithmetic from the published multipliers — the formula is stated above, so any spreadsheet reproduces it.

### 2.3 What dominates — `f` sets the prize, `h` decides whether you get one

One-at-a-time sensitivity around that baseline (**ours**). Partial derivatives at the baseline: `∂S/∂f` = 0.7612, `∂S/∂r` = −0.7626, `∂S/∂h` = 0.8679 — all three look comparable per unit. **Ranking on derivatives is the mistake.** What decides dominance is how far each variable actually moves in real workloads:

| Variable | Realistic range | `S` over that range | Swing |
|---|---|---|---|
| **`f`** — prefix share of input | 0.50 → 0.95 | 38.06% → 72.31% | **34.3 pp** |
| **`r`** — output share of bill | 0.05 → 0.40 | 72.45% → 45.76% | 26.7 pp |
| **`h`** — hit rate, *inside a working cache* | 0.80 → 1.00 (any session with N ≥ 5) | 50.57% → 67.92% | 17.4 pp |
| **`h`** — hit rate, *full range* | 0.00 → 1.00 | **−18.87%** → 67.92% | **86.8 pp** |

Two conclusions, and they are not the same conclusion. **(1) Inside a cache that works, `f` dominates** — how much of your input is a stable prefix is worth roughly twice what session length is worth, and that is a prompt-architecture decision, not a gateway decision. **(2) `h` is the only variable that crosses zero** — every other term scales the prize; `h` decides its sign. And `h` is precisely the variable a gateway sits on top of and can silently destroy (§5.1).

**`N` is a red herring.** The single-write form is `S = f(1−r)(0.9 − 1.15/N)`, and `(0.9 − 1.15/N)` reaches 74.4% of its 0.9 ceiling by N=5, 87.2% by N=10, 93.6% by N=20 and 97.4% by N=50. Past about ten turns, session length is worth under 9 pp and is the least actionable knob you have.

**An illustration, explicitly not a measurement.** This repo cites Datadog telemetry that *"only 28% of calls show any cached input"* while system prompts eat 69% of input tokens (repo-sourced, [README](../README.md#-latest-evaluations) citing [Datadog State of AI Engineering](https://www.datadoghq.com/state-of-ai-engineering/), 2026-04 — that underlying report was **not independently re-verified for this chapter**). Substituting `h = 0.28` into the baseline gives `S = 5.43%`. That substitution is **not** a claim about industry savings: Datadog's 28% is the share of *calls* with any cache read, not a per-token hit rate within a session. What it does show rigorously is the shape of the asymmetry — the entire gap between a 90% headline and a 5% outcome is `h`.

---

## 3. Provider prompt caching — four providers, no portable contract

Six axes decide whether you actually get the discount — write price, read price, minimum prefix, TTL, how you mark a cache, and how usage is reported — and the four providers disagree on **every one of them**. There is no portable prompt-caching contract for a gateway to normalize to. Everything below is quoted or derived from the official pages, retrieved **2026-07-29**; the multipliers are *derived from the price sheets by division*, not read out of marketing prose, so you can re-do them yourself in one line each (§8).

### 3.1 Write-vs-read pricing

| Provider | Cache write | Cache read | Storage rent | Free money? |
|---|---|---|---|---|
| **Anthropic** | **1.25×** base input (5m TTL) · **2×** (1h TTL) | **0.1×** | none | ❌ — must hit >21.74% (5m) / >52.63% (1h) |
| **OpenAI GPT-5.6+** | **1.25×** — *"cache writes cost 1.25× the uncached input token rate"* | **0.1×** | none | ❌ — must hit >21.74% |
| **OpenAI before GPT-5.6** | free — *"no additional fee on models before the GPT-5.6 family"* | **0.1×** | none | ✅ |
| **Gemini** (implicit) | free | **0.1×** | none | ✅ — but **no savings guarantee** (§3.4) |
| **Gemini** (explicit `CachedContent`) | standard input price to create | **0.1×** | **$1.00–$4.50 per 1M tok per hour** | ❌ — the only one of the four charging rent |
| **DeepSeek V4-Flash** | free — *"Storage usage for the cache is free"* | **0.02×** (1/50) | none | ✅ |
| **DeepSeek V4-Pro** | free | **0.008333×** (1/120) | none | ✅ |

Dollar checks, so nothing here rests on prose. Claude Opus 5 ($5.00 / $6.25 / $10.00 / $0.50): 1.25, 2.00, 0.10 exactly — and Fable 5 ($10/$12.50/$20/$1) and Haiku 4.5 ($1/$1.25/$2/$0.10) carry identical ratios. OpenAI gpt-5.6-sol ($5.00/$6.25/$0.50): 1.25 and 0.10, same across terra and luna. Gemini: 0.15/1.50 = 0.125/1.25 = 0.03/0.30 = 0.01/0.10 = 0.10 exactly. DeepSeek: 0.0028/0.14 = 0.0200 and 0.003625/0.435 = 1/120 exactly.

> ⚠️ **Two things this repo currently gets wrong, published here so the correction is dated.** (a) The README's *"75–90% cache discount"* band is wrong at both ends as of today: every current flagship read is exactly **90%**, and DeepSeek is **98.00%** / **99.17%**. Nothing in the current model set discounts at 75% — that was the Gemini 2.0-era figure, and Gemini 2.0 is not in this repo's model set. (b) The string "cache write" appears **nowhere** in the repo, and [data/models.json](../data/models.json) (`as_of` 2026-07-28) carries `input` / `output` / `cached_input` but **no cache-write field** — so the cost calculator structurally cannot model the 1.25×/2× premium, the break-even hit rate, or the TTL crossover in §3.5. Every `cached_input` value in that file was cross-checked against the official pages today and found exact; the gap is a missing dimension, not a wrong number.

### 3.2 Minimum cacheable prefix — the threshold nobody publishes

Below these token counts, **nothing caches and nothing tells you.** No error, no warning, no field.

| Provider | Minimum cacheable prefix | The trap |
|---|---|---|
| **Anthropic** | **512** (Opus 5, Fable 5, Mythos 5) · **1,024** (Opus 4.8, Sonnet 5, Sonnet 4.6/4.5, Opus 4.1, Opus 4, Sonnet 4) · **2,048** (Mythos Preview, Opus 4.7, Haiku 3.5) · **4,096** (Opus 4.6, Opus 4.5, **Haiku 4.5**) | **Not monotonic in model age or tier.** Opus 4.5/4.6 need 4,096; the *newer* Opus 4.7 needs 2,048, Opus 4.8 needs 1,024, Opus 5 needs 512. You cannot infer it. A Haiku 4.5 request under 4,096 tokens silently caches nothing |
| **OpenAI** | **1,024** — *"Caching is available for prompts containing 1024 tokens or more"* | The widely-cited *"cache hits occur in increments of 128 tokens"* wording is **not on the current page** (two targeted re-fetches for the string "128" returned nothing). Do not repeat it as current |
| **Gemini** | **2,048** (2.5 Flash, 2.5 Pro) · **4,096** (3.5 Flash, 3.1 Pro Preview) | The 3.x generation **doubled** the minimum, so a prompt that cached fine on 2.5 Flash can silently stop caching on 3.5 Flash |
| **Gemini 3.6 Flash** | **unstated by Google** | It has a $0.15/MTok cache-read rate on the price sheet but is **absent from the minimum-token table on all three of Google's caching pages**. Leave this cell null; do not interpolate |
| **DeepSeek** | **64** — *"content less than 64 tokens will not be cached"* | 8×–64× smaller than everyone else. Effectively no floor |

No minimum-prefix figures exist anywhere in this repo today — no hits for these numbers in a caching context across README, BENCHMARKS or `docs/`. For a "money question" section, this is the most actionable omission on the page.

### 3.3 What breaks a cache prefix

Anthropic documents the cache key as a **hierarchical exact-byte prefix**, and the hierarchy is the part that bites coding agents. Verbatim: *"Cache prefixes are created in the following order: `tools`, `system`, then `messages`. This order forms a hierarchy where each level builds upon the previous ones."* And: *"Changes at each level invalidate that level and all subsequent levels."* Matching is byte-exact — *"Cache hits require 100% identical prompt segments, including all text and images up to and including the block marked with cache control."*

The published invalidation matrix (✘ = invalidated, ✓ = survives):

| What you changed | Tools cache | System cache | Messages cache |
|---|---|---|---|
| Tool definitions | ✘ | ✘ | ✘ |
| Web search toggle | ✓ | ✘ | ✘ |
| Citations toggle | ✓ | ✘ | ✘ |
| Speed setting | ✓ | ✘ | ✘ |
| Tool choice | ✓ | ✓ | ✘ |
| Images | ✓ | ✓ | ✘ |
| Thinking parameters | model-specific | model-specific | ✘ |
| Effort setting | model-specific | model-specific | ✘ |

**The consequence for agents is in the first row.** Tool definitions sit at the *top* of the hierarchy, so adding, removing or reordering a single MCP tool mid-session invalidates everything below it — system prompt and full conversation history included. An agent that hot-loads MCP servers is an agent that pays a full cache write every time the tool list changes shape. Note also that Bifrost's semantic cache hashes tool objects as an order-*insensitive* set specifically to defend against *"MCP's randomized map iteration"* (read at `e6952b6`) — the same hazard, one layer up.

OpenAI's construction is looser but has the same shape: *"Requests are routed to a machine based on a hash of the initial prefix of the prompt. The hash typically uses the first 256 tokens, though the exact length varies depending on the model."* Both vendors give the identical structural advice — static content first, variable content last. Gemini says the same: *"Try putting large and common contents at the beginning of your prompt."*

### 3.4 Marking, TTLs, and the free refresh

| Axis | Anthropic | OpenAI | Gemini | DeepSeek |
|---|---|---|---|---|
| **How you mark it** | Explicit. Two modes: **automatic** (a single top-level `cache_control` field; the system moves the breakpoint forward as the conversation grows) or **explicit breakpoints** (`cache_control` on individual content blocks, **≤4 per request**) | Automatic by default, now with knobs: `prompt_cache_key`, `prompt_cache_options.mode` ∈ {`implicit`, `explicit`}, `prompt_cache_options.ttl`. On GPT-5.6+ *"you must set `prompt_cache_key` to use the more reliable matching"*, keeping each key under ~15 req/min | Implicit by default on 2.5+, plus optional `CachedContent` objects. **Explicit caching is not supported in the newer Interactions API** | Fully automatic, no knob — *"enabled by default for all users, allowing them to benefit without needing to modify their code"* |
| **Default TTL** | **5 minutes** | **≥30 minutes** on GPT-5.6+; 5–10 min idle / 1 h max before that | Explicit cache: **1 hour**, settable via `ttl` or `expireTime` | *"a few hours to a few days"* — **uncontracted in both directions** |
| **Longer TTL** | 1 hour at **2× write** | `prompt_cache_retention: "24h"` (deprecated param), up to 24 h | any, but you rent it hourly | n/a |
| **Refresh on hit** | **Free** — *"The cache is refreshed for no additional cost each time the cached content is used"* | prefix stays eligible *"for at least 30 minutes, but OpenAI may retain it longer"* | — | — |
| **Savings guaranteed?** | yes | yes | **no** — Google's own feature list says *"Implicit caching … no cost saving guarantee"* | yes |

Anthropic's **free refresh** is the load-bearing fact for agent economics: a session whose turns are less than five minutes apart pays exactly **one** cache write for the whole session, regardless of length. That is why the worked example in §2.2 has one write and 49 reads.

Gemini's row is the sharpest contrast in the table and deserves saying plainly: Anthropic and OpenAI-explicit let you *declare* a cache. Gemini implicit is a best-effort optimization you cannot force, **and Google says so in its own docs**. (A widely-quoted Google sentence putting the discount at *"90% … on Gemini 2.5 or later, 75% on Gemini 2.0"* could **not** be confirmed on any primary page we fetched — three direct fetches returned navigation shells or pages lacking it. We therefore cite the price-sheet ratio instead, which establishes 90% exactly and needs no prose.)

### 3.5 The TTL decision rule

**Ours.** With `G` idle gaps longer than 5 minutes, the 5-minute cache pays `G+1` writes and the 1-hour cache pays one:

```text
cost_5m = 1.25(G+1) + 0.1(N−G−1)          cost_1h = 2.00 + 0.1(N−1)
1h wins when  1.15G + 1.15 > 2.00   →   G > 0.7391   →   G ≥ 1
```

Numerically, at C = 20,000 tok and N = 50 on Opus 5 prices (prefix cost only):

| Gaps > 5 min (`G`) | 5-minute cache | 1-hour cache | Winner |
|---|---|---|---|
| 0 | **$0.6150** | $0.6900 | 5-minute |
| 1 | $0.7300 | **$0.6900** | 1-hour |
| 2 | $0.8450 | **$0.6900** | 1-hour |
| 3 | $0.9600 | **$0.6900** | 1-hour |

**One genuine pause is enough to flip it.** Because every hit refreshes the TTL for free, "a gap" means a real >5-minute idle — a human reading a diff, a long test run, a build. The practical rule: **continuous autonomous loops want 5m; human-in-the-loop sessions want 1h.** And note that OpenAI's GPT-5.6+ default already hands you a 30-minute floor at the 5-minute price — 6× Anthropic's default TTL at the identical 1.25× write multiplier.

### 3.6 Usage accounting — three different inclusion semantics for one concept

This is where gateway billing goes wrong, because the four providers do not agree on whether cached tokens are *inside* or *outside* the prompt count.

| Provider | Prompt-count semantics | Fields |
|---|---|---|
| **Anthropic** | **Excludes** — *"`input_tokens`: Number of input tokens which were not read from or used to create a cache (that is, tokens after the last cache breakpoint)"* | `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` = total. With 1h caching, `cache_creation` splits into `ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` |
| **OpenAI** | **Includes** | `prompt_tokens`, with `prompt_tokens_details.cached_tokens` and — new — `prompt_tokens_details.cache_write_tokens` (*"The unadjusted number of prompt tokens written to cache"*) as subsets |
| **Gemini** | **Includes** — *"When `cachedContent` is set, this is still the total effective prompt size meaning this includes the number of tokens in the cached content"* | `promptTokenCount`, `cachedContentTokenCount` (REST) / `usage.total_cached_tokens` (SDK) |
| **DeepSeek** | **Partitions** — a third scheme entirely | `prompt_cache_hit_tokens` + `prompt_cache_miss_tokens` |

The inclusion flip is **2-against-1** (OpenAI and Gemini include, Anthropic excludes), with DeepSeek off on its own axis. [Chapter 1 §3.3](protocol-translation.md#failure-3) documents what that costs when a translator maps fields 1:1. §5.2 below shows the newest instance.

Isolation, worth one line because auditors ask: Anthropic caches are isolated per organization and, on the Claude API / Claude Platform on AWS / Microsoft Foundry, per workspace — Bedrock and Google Cloud are org-level only. OpenAI: *"Prompt caches are not shared between organizations."* DeepSeek: *"Each user's cache is isolated and logically invisible to others."*

---

## 4. Gateway response caching — the key is the whole product

Tier 2 saves 100% of the provider call when it hits, which makes it sound strictly better than tier 1. It isn't, because a tier-2 hit **replaces the model's answer**. Everything therefore rests on one question no feature matrix asks: **what is actually in the cache key?** All rows below except Kong `ai-semantic-cache` are read from source at the pinned commits in the appendix; the Kong Enterprise row is read from its documentation, 2026-07-29.

| Gateway | What the key contains | Model in key? | Tenant in key? | Verdict |
|---|---|---|---|---|
| **Bifrost** `@e6952b6` | UUIDv5(fixed ns, `cache_key` + request hash + params hash); params hash covers temperature, top_p, max_tokens, stop, seed, response_format, reasoning_effort, tool_choice, a hash of the **full tool objects**, and attachment URLs | ✅ default | ✅ — caching is **off** unless a per-request `CacheKey` or `DefaultCacheKey` is set | **Fail-closed.** The only one of the six |
| **LiteLLM** `@c274cf3` (exact) | SHA-256 over every kwarg in `ModelParamHelper._get_all_llm_api_params()` — model, messages, temperature, tools all in | ✅ but it is the **model *group***, not the deployment | ❌ for redis/local/disk/s3 — tenant scope is appended **only** for semantic backends | Safe on params, **blind on tenant** unless you set a namespace |
| **Portkey OSS** `@669825c` | `SHA-256(JSON.stringify(transformedRequestBody) + '-' + endpointName)` | ✅ (inside the body) | ❌ — `getFromCache` *accepts* an org/cacheIdentifier argument and ignores it; `cacheIdentifier` is set **nowhere** in the OSS tree | No partitioning at all; **provider not in the key** |
| **Kong** `ai-semantic-cache` (Enterprise) | Vector of the last **`message_countback = 1`** message by default | — | — | Default is the classic multi-turn false hit (§5.3) |
| **Higress** `ai-cache` `@c8b8279` | The text of the **last message**, via `cacheKeyFrom` default `messages.@reverse.0.content` | ❌ | ❌ | **Thinnest key of the six.** And it is an *exact* match, so no threshold protects you |
| **Kong OSS** `proxy-cache` `@391ee48` | `SHA-256(consumer_id:route_id \| method \| uri \| query \| vary_headers)` — **the request body is never hashed** | ❌ | partial (consumer_id, nil on unauthenticated routes) | Cannot tell two prompts apart. See below |

**Kong OSS is the sharpest case and it is worth being precise about.** `build_cache_key(consumer_id, route_id, method, uri, params_table, headers_table, conf)` takes no body argument; the body is read only *after* a miss, for logging. Two defaults keep this from being reachable out of the box — `request_method` defaults to `{GET, HEAD}`, so LLM POSTs get `X-Cache-Status: Bypass` — but the schema's `one_of` explicitly permits POST, `content_type` defaults include `application/json`, and `vary_headers` has **no default**, so even `Authorization` is outside the key. **Enable POST on an LLM route and every prompt from one consumer collides into a single cache entry.**

**Higress is the sharpest case for a different reason: it proves exact-match caching can be more dangerous than semantic caching.** With only the last message in the key, (a) the same prompt sent to two different models returns whichever answer landed first, (b) any tenant sharing the gateway reads any other tenant's answers, and (c) two conversations with identical user turns but different system prompts collide. There is no similarity threshold to tune, because there is no similarity step.

### 4.1 The defaults that decide your risk

| Gateway | Cache TTL default | Similarity threshold default | Semantic available in OSS? |
|---|---|---|---|
| **Bifrost** | 5 minutes | **0.8** cosine (+ conversation-history cutoff at 3 messages — longer histories are not cached at all) | ✅ |
| **LiteLLM** | `ttl` / `default_in_memory_ttl` / `default_in_redis_ttl`, no implicit default | **none — refuses to start without an explicit threshold** | ✅ (redis · valkey · qdrant) |
| **Portkey OSS** | 24 h fallback in code; docs define `max_age` in **seconds** (min 60, default 7 days) | 0.95 — **hosted/Enterprise only** | ❌ |
| **Kong** `ai-semantic-cache` | 300 s | operator-set, required | ❌ Enterprise (`ai_gateway_enterprise`) |
| **Higress** `ai-cache` | **0 = never expires** | **1000**, relation `lt` | ✅ but silently off by default (§5.4) |
| **Kong OSS** `proxy-cache` | 300 s | n/a (exact only) | n/a |

Two defaults in that table are outliers by an order of magnitude. **Higress's TTL of 0 is implemented as a Redis `SET` with no expiry** — read from `cache/redis.go`: `if rp.config.cacheTTL == 0 { return rp.client.Set(...) } else { return rp.client.SetEx(...) }`, with the plugin's own README confirming *"Default is 0 (never expire)"*. Combined with the last-message-only key, **a wrong answer, once cached, is permanent until someone flushes Redis.** And **Higress's threshold of 1000 with relation `lt`** means, for a Euclidean store, that any neighbour under distance 1000 passes — i.e. accept the nearest neighbour at essentially any distance. Compare Bifrost's 0.8 and Portkey hosted's 0.95 — though Bifrost's 0.8 deserves a caveat rather than a gold star, because on modern embeddings *"capital of France"* and *"capital of Germany"* routinely score above 0.8 cosine. Fail-closed scoping and a permissive threshold are independent properties.

**Envoy AI Gateway has no gateway response cache at all.** A recursive tree listing at `6722cca` returns exactly two paths matching "cache" — `examples/cache` and `examples/cache/cache_control.md` — and that document is about forwarding Anthropic-style `cache_control` across Anthropic / Vertex / Bedrock, i.e. tier 1 passthrough. No cache filter, no cache CRD, no cache-status header.

---

## 5. The failure modes, with receipts

### 5.1 Stripped `cache_control` — 10× on the affected tokens, ~3× on the session

The mechanism is [chapter 1's failure mode 5](protocol-translation.md#failure-5): `cache_control` exists only in Anthropic's schema, so any "normalize to OpenAI internally" step drops it unless someone wrote explicit preservation code, per adapter. Nothing errors. The only symptom is `cache_read_input_tokens: 0` and a bigger bill. Verified receipts: [Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579) (2026-03-25, **open** — stripping en route to Vertex AI Anthropic models) and [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797) (2026-07-27, **open** — the same stripping in the SAP provider path), both re-verified via `gh api` on 2026-07-29.

**Three numbers, and they answer different questions — say all three or you will be misread.** Per token, input that should have been a cache read now bills at full price: **10×** on those tokens (1.0 ÷ 0.1). At the session level, on the §2.2 workload: $6.6250 ÷ $2.2400 = **2.96×**. And versus never having enabled caching at all: **−18.87%**, because a gateway that faithfully forwards your 1.25× cache write and then breaks the hit — by rotating a header, reordering tools, or appending a request id — leaves you at `h = 0`, and `S(h=0) = −18.87%`. Chapter 1's §3.5 arithmetic is correct, but its heading — *"the silent 10× bill"* — reads as an invoice multiplier and is not one. The README's 30-second snippet detects this case correctly; its surrounding prose says you are *"paying full price"*, when in fact you are paying about a fifth above it.

**A new, undocumented variant of this class.** Anthropic now documents a second marking mode: *"Automatic caching: Add a single `cache_control` field at the top level of your request."* Every stripping bug catalogued in this repo concerns **block-level** `cache_control`. A translator that scans `system[]` and `messages[].content[]` for `cache_control` and copies what it finds will **silently drop the top-level form** — identical signature (`cache_read_input_tokens: 0`, no error), new cause, currently documented nowhere. **Ours, by inspection of the vendor doc against the known bug shape; not yet observed in a filed issue.**

### 5.2 The double-count trap, now with an OpenAI variant

The precedent is verified and closed: LiteLLM once charged Anthropic's `cache_creation_input_tokens` *"once as prompt tokens and then again as cache creation tokens"*, reporting **$0.091311** against an Anthropic-console-verified **$0.05439** — ~1.7× ([BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812), 2025-04-08, closed).

The same shape is now reachable on OpenAI. `prompt_tokens` **includes** cached tokens; `cache_write_tokens` is described as *"the unadjusted number of prompt tokens written to cache"* — i.e. a **subset**; and GPT-5.6+ writes bill at 1.25×. A gateway computing `prompt_tokens × input_rate + cache_write_tokens × write_rate` therefore bills the written tokens twice.

> **⚠️ Demoted — hypothesis, not finding.** What we could **not** verify from primary docs is whether OpenAI bills write tokens *at* 1.25× (replacing the 1.0× input charge) or *at +0.25×* on top. The guide says only *"cache writes cost 1.25× the uncached input token rate"*; the pricing table's separate $6.25 column implies replacement. **Treat replacement as the working hypothesis.** It needs a live reconciliation against an OpenAI invoice — the procedure is step 10 in §8. This repo should not publish a number for it until someone runs that.

Related and verified: [BerriAI/litellm#34801](https://github.com/BerriAI/litellm/issues/34801) (2026-07-27, **open**) is a clean 40-request reconciliation where every field matched except cache reads — under-counted 24%, cost overstated 8.5%.

### 5.3 Semantic-cache false hits — the mechanism is vendor-documented

The strongest primary evidence in this category is a vendor's own merged PR. [BerriAI/litellm#26990](https://github.com/BerriAI/litellm/pull/26990) (*"chore(caching): isolate semantic cache entries"*) — **merged 2026-05-04** into `litellm_internal_staging` — says it verbatim (its sibling [#26992](https://github.com/BerriAI/litellm/pull/26992) against `main` was closed **unmerged**, so cite the staging PR, not that one):

> *"The semantic caches retrieve based on prompt embedding similarity, so two callers from different teams could retrieve each other's cached LLM responses by sending semantically similar prompts."*

Then the fix produced the mirror failure. [BerriAI/litellm#29086](https://github.com/BerriAI/litellm/issues/29086) (2026-05-27, closed): *"`redis-semantic` cache never produces semantic hits"* — the scope key still hashed the prompt and was used as a RediSearch pre-filter, making KNN unreachable. [PR #30339](https://github.com/BerriAI/litellm/issues/30339) (merged 2026-06-13) states both halves: *"Identical requests still hit … fuzzy requests always returned 0.0"*, and the fix excludes prompt content from the scope key **while** appending tenant identity *"so dropping prompt content cannot let one virtual key read another tenant's cached response."* [#31610](https://github.com/BerriAI/litellm/issues/31610) (2026-06-29, **open**) reports it still mostly missing, reopening [#6954](https://github.com/BerriAI/litellm/issues/6954) from 2024-11-28. That is the correctness/hit-rate seesaw in one repository, on the record.

Three shipped defaults that make the class likely, all read today:

- **Kong `ai-semantic-cache`**: `message_countback = 1` — only the last message is vectorized. Portkey's own blog uses exactly this shape as its cautionary example: ask *"What is the largest lake in North America?"*, then later, in an unrelated conversation, *"What is the second largest?"* — a trailing-phrase match returns "Lake Huron."
- **Portkey hosted semantic cache**: requires an exact match on model, temperature and max_tokens, but per Portkey's cache docs *"The system prompt is ignored — changing it does not affect cache hits"* — two callers with different system instructions and similar user text can share an answer.
- **Higress**: threshold 1000 / `lt`, i.e. no effective threshold once the semantic path is switched on (§4.1).

One user-reported symptom, **flagged as unconfirmed**: [BerriAI/litellm#28778](https://github.com/BerriAI/litellm/issues/28778) (2026-05-25, **open**) reports that with `redis-semantic` or `qdrant-semantic` on, an agent's tool-return content is lost and the agent re-issues tool calls. The reporter's root cause is a hypothesis, no maintainer has confirmed it, and we did not reproduce it. Cited as a symptom, not a proven false hit.

### 5.4 The quiet failure: caches that are off and don't say so

Worse than a false hit, in the sense that you keep paying and never learn:

- **Higress `ai-cache` semantic path is off by default because of a nil-check ordering bug.** `config.go`'s `FromJson` sets `EnableSemanticCache = true` only when `GetVectorProvider() != nil`, but the provider *instance* is constructed later, in `Complete()`; `parseConfig` runs `FromJson → Validate → Complete`, so the getter is always nil during `FromJson` and the "default true" branch is unreachable. The plugin is exact-match-only unless you set `enableSemanticCache` explicitly. Diagnosed identically in [higress-group/higress#4165](https://github.com/higress-group/higress/pull/4165) (2026-07-17, **open** as of 2026-07-29). Separately, `Validate()`'s check that semantic cache requires an embedding provider is **commented out**.
- **Bifrost semantic matching silently never fires for Ollama/vLLM model names.** [maximhq/bifrost#5333](https://github.com/maximhq/bifrost/issues/5333) (2026-07-17, **open**): RediSearch vector search fails with *"Syntax error"* for TAG values containing `:`. Because `CacheByModel` defaults to true, any model id with a colon (`gemma31b-q6:latest`) makes the `FT.SEARCH` illegal; the plugin logs *"semantic search skipped"* and direct hash caching keeps working. Fails safe — a miss, not a false hit — but silently. The reporter's words: *"so it's easy to miss."*
- **Higress reports a hit as a synthetic response whose `model` field is the literal string `from-cache`** and whose `usage` is all zeros (read from `config/config.go` at `c8b8279`). Any downstream meter keying on `response.model` sees `from-cache`; a hit contributes nothing to `ai-statistics` — mechanically, on top of the phase-ordering reason [chapter 4 §3.1](gateway-anatomy.md#31-where-the-cache-sits--five-orderings-two-of-which-let-a-hit-escape-budget-enforcement) already documents.
- **Portkey OSS never caches a request that explicitly sends `stream: false`.** The write guard reads `requestParams.stream === (false || undefined)`, and in JavaScript `(false || undefined)` is `undefined` — so the test is `stream === undefined`. Clients that omit the field are cached; clients that send `false` (LangChain and many raw HTTP clients do) never are. Separately, `max_age` is documented in **seconds** but added to `Date.now()` in **milliseconds**, so a documented `max_age: 3600` becomes 3.6 seconds of TTL. Code read at `669825c`; the runtime consequence is **our arithmetic, not an executed test**.

### 5.5 Honest negative — the field evidence you'd expect does not exist

**There is no verified public production-incident report of a semantic-cache false hit at any gateway on this list.** We searched GitHub issues across LiteLLM, Kong, Higress, Bifrost and Portkey, plus general web search. What exists is: (a) one vendor's own merged-PR admission that the bug class was live in its product (§5.3); (b) vendor-documented defaults that make false hits likely; (c) one open, unconfirmed user-reported symptom; and (d) a quantity of vendor blog content asserting false-positive rates with **no published methodology**, which we deliberately do not cite as measurement. The defensible framing: **the mechanism is documented by the vendors themselves and one vendor shipped and fixed it; user-visible field evidence is absent, and its absence is exactly what you would expect** — a false hit returns 200 OK with a confident wrong answer, and of the six implementations in §4 only Bifrost and LiteLLM emit the similarity score you would need to detect one.

---

## 6. KV-cache-aware routing is not a cache

The third tier shares the word and shares none of the risk, which is the most useful framing in this chapter for anyone evaluating Kubernetes-native inference. The Gateway API Inference Extension's proposal 0602 (status: **Implemented**, read at `415f528`) draws the line itself: *"we use the term 'request scheduling' to mean the process of estimating the cost of a request and placing it to the best backend server. This is different from 'model routing'."* Its stated non-goals include *"Change how model server manages prefix caches, or add any prefix cache APIs."*

The design is an **approximate prefix cache on the EPP**: split the request into fixed-size chunks and hash each as `hash(chunk_i content + hash(chunk_i−1))` — *"we don't necessarily need to tokenize"* — so a chunk-hash match implies all preceding chunks match. The EPP records which replica served which chunk hashes and routes a new request to the replica with the longest matching prefix, in order to maximize **the model server's own** prefix-cache hit (vLLM's automatic prefix caching).

**The response is always generated fresh.** A stale or wrong index entry costs time-to-first-token, never correctness. That is the entire difference from tier 2, and it should change how much scrutiny you apply. Two constraints buyers should still ask about, both stated in the proposal: matching must be per model/adapter because *"different adapters don't share the same kv cache"*, and the in-memory index means *"cache hit performance decreases with multiple active EPP replicas."*

Where it actually lives, since the marketing blurs this:

| Project | What it ships | Notable defaults (read at pinned commits) |
|---|---|---|
| **llm-d-router** `@c611977` | Two scorers: `prefix-cache-scorer` (approximate) and `preciseprefixcache`, as framework Scorers producing a 0..1 score blended with load/latency scorers | `blockSizeTokens` default 16 but *"values below the minimum of 64 are clamped up at request time"*; `maxPrefixTokensToMatch` 131072; `lruCapacityPerServer` 31250; `matchLengthWeight` **0.0** — by default only the match *ratio* counts |
| **AIBrix** `@a1626c8` | `pkg/plugins/gateway/algorithms/prefix_cache.go`, model-partitioned index (`modelToPods`) | tokenizer `character` (default) or `tiktoken`; block size 128; block number 200000; documented fallback to least-loaded routing when `max_running − min_running` exceeds the imbalance threshold |
| **kgateway** `@e448e21` | **Nothing.** Contains the Inference Extension support design doc and no prefix-scoring code | State it as *"kgateway supports the Inference Extension; the scoring lives in the EPP"* — it consumes, it does not implement |

One AIBrix detail worth a line because it is the concrete form of the GIE's multi-replica warning: `prefixCacheHashSeed()` uses `AIBRIX_PREFIX_CACHE_HASH_SEED` if set, a fixed seed if state-sync is enabled, and otherwise a **random seed from `time.Now().UnixNano()`**. Two gateway replicas therefore compute different block hashes for the same prompt and cannot pool their routing knowledge.

---

## 7. The 30-second self-test

The README owns the canonical version of this; here it is with the four provider field names side by side and — the part that is new — **what the answer costs you.**

Send the same long-prefix request twice, back to back, and diff one field:

| Provider | Field to read on the **second** call |
|---|---|
| Anthropic | `usage.cache_read_input_tokens` |
| OpenAI | `usage.prompt_tokens_details.cached_tokens` |
| Gemini | `usageMetadata.cachedContentTokenCount` (REST) / `usage.total_cached_tokens` (SDK) |
| DeepSeek | `usage.prompt_cache_hit_tokens` |

**Zero on the second call means `h = 0`.** On Anthropic 5m or OpenAI GPT-5.6+ that is not "you're paying full price" — it is **−18.87% on the §2.2 workload, i.e. you are paying about a fifth more than with caching switched off**, because you bought the 1.25× write and never collected the 0.1× read. On OpenAI ≤5.5, Gemini or DeepSeek, `h = 0` is merely a missed opportunity: writes are free there, so the floor is zero, not negative.

Before you conclude the gateway is at fault, rule out the two vendor-side reasons for a legitimate zero: your prefix may be **below the model's minimum** (§3.2 — 4,096 tokens on Haiku 4.5 and Gemini 3.5 Flash), or a **tool-definition change** may have invalidated the whole hierarchy (§3.3). Both look identical to a stripped breakpoint from outside.

---

## 8. Verify this yourself

Nothing above needs to be taken on faith. Ordered by how fast they pay off.

1. **Re-derive every multiplier by division — no keys, two minutes.** Anthropic [pricing](https://platform.claude.com/docs/en/about-claude/pricing): 6.25/5 = 1.25, 10/5 = 2.0, 0.50/5 = 0.10. OpenAI [pricing](https://developers.openai.com/api/docs/pricing): 6.25/5.00 = 1.25, 0.50/5.00 = 0.10. Gemini [pricing](https://ai.google.dev/gemini-api/docs/pricing): 0.15/1.50 = 0.10. DeepSeek [pricing](https://api-docs.deepseek.com/quick_start/pricing): 0.0028/0.14 = 0.02, 0.003625/0.435 = 1/120.
2. **Re-run our arithmetic.** Every figure below is closed-form from the published multipliers — the $6.6250 → $2.2400 ladder, the cross-check, every break-even, the sensitivity table, the N-saturation curve and the 5m-vs-1h crossover.
3. **Measure your own `h`** — the variable that decides the sign. §7, one field, two requests.
4. **Prove Kong OSS is body-blind, no keys needed.**
   ```bash
   grep -n "build_cache_key" kong/plugins/proxy-cache/cache_key.lua kong/plugins/proxy-cache/handler.lua
   # confirm the arg list has no body; then enable proxy-cache with request_method
   # including POST on an LLM route, send two DIFFERENT prompts, diff the responses
   ```
5. **Read a Higress cache key in plaintext.**
   ```bash
   redis-cli --scan --pattern "higress-ai-cache:*"   # these are your users' last messages
   redis-cli TTL <key>                               # -1 = never expires, the default
   ```
6. **Confirm what Kong and Envoy actually ship** — the first returns `proxy-cache` only (no `ai-semantic-cache` in OSS), the second returns two example paths and nothing else.
   ```bash
   gh api "repos/Kong/kong/contents/kong/plugins?ref=391ee48" --jq '.[].name' | grep -i cache
   gh api "repos/envoyproxy/ai-gateway/git/trees/6722cca?recursive=1" --jq '.tree[].path' | grep -i cache
   ```
7. **Test LiteLLM tenant leakage on exact caches.** With `cache: redis` and no namespace, send a byte-identical request under two different virtual keys and compare `x-litellm-cache-key`. Identical hashes mean shared entries.
8. **Audit semantic false hits where the signal exists.** LiteLLM sets `x-litellm-semantic-similarity` on **both** hit and miss (miss writes 0.0) — log it and plot the distribution; anything clustering just above your threshold is your false-hit population. Bifrost's `BifrostCacheDebug` carries `HitType` (`direct`/`semantic`), `Similarity` and `Threshold` per hit. The other four gateways emit nothing you could audit with.
9. **Prove KV-cache-aware routing is not a cache.** Send the same prompt twice to an AIBrix or llm-d pool and read the usage: `prompt_tokens` is charged both times. Only TTFT improves.
10. **Settle the one thing we could not.** Run a write-heavy request with `prompt_cache_options.mode: "explicit"`, record `prompt_tokens`, `cached_tokens` and `cache_write_tokens`, and reconcile against the invoice line to determine whether OpenAI bills writes at 1.25× or at 1.0× + 0.25× (§5.2). If you do, please [open an issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — it is the missing fact in this chapter.

---

## 9. Where to go next

If you're choosing a gateway, start at [the requirements map](../README.md#the-requirements-map) and the [Quick comparison](../README.md#quick-comparison) cache column — then treat every ✅ in that column as a question about §4's key table, not an answer. If you're already running one, §7 costs thirty seconds and §8 step 4 costs fifteen minutes. In this handbook (the map is in [HANDBOOK.md](../HANDBOOK.md)): [chapter 1 — The Compatibility Surface](protocol-translation.md) is where `cache_control` gets destroyed, at the translation stage, with the other four silent failure modes for company. [Chapter 4 — Anatomy of an AI Gateway](gateway-anatomy.md) is where the cache *sits* — §3.1 there shows the two gateways in which a hit escapes budget enforcement entirely, which is the exact complement of this chapter: chapter 4 asks whether a hit is governed, this chapter asks whether it is correct and whether it saves anything.

The three things this chapter deliberately leaves open, so nobody cites it for them: whether OpenAI's cache writes bill at 1.25× replacing or +0.25× on top (§5.2); whether a Bifrost semantic-cache hit is billed twice (mechanically plausible from plugin ordering, but it needs a black-box spend-delta measurement, per [chapter 4's appendix](gateway-anatomy.md#appendix--every-source-this-chapter-relies-on)); and Gemini 3.6 Flash's minimum cacheable prefix, which Google has not published.

---

## Appendix — every source this chapter relies on

**Vendor documentation** (all retrieved 2026-07-29):

| Source | What it establishes here |
|---|---|
| [Anthropic — prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | 1.25×/2× write, 0.1× read, per-model minimums 512–4,096, ≤4 breakpoints + the new top-level automatic mode, tools→system→messages hierarchy and invalidation matrix, free TTL refresh, usage fields, org/workspace isolation |
| [Anthropic — pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Per-model Base Input / 5m Write / 1h Write / Cache Hit / Output columns; the multiplier table; the break-even prose quoted in §2.1 |
| [OpenAI — prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching) | 1,024-token minimum, 256-token routing hash, 1.25× writes on GPT-5.6+ (free before), `prompt_cache_key`, `prompt_cache_options.mode`/`ttl`, `prompt_cache_retention`, 30m/1h/24h retention, no cross-org sharing |
| [OpenAI — pricing](https://developers.openai.com/api/docs/pricing) | The new **Cache Writes** column: gpt-5.6-sol $5.00/$0.50/$6.25/$30.00, terra, luna; older families show "—" |
| [OpenAI — Chat object reference](https://developers.openai.com/api/docs/api-reference/chat/object) | `prompt_tokens_details.cached_tokens` and `.cache_write_tokens` definitions; the cache parameter definitions |
| [Gemini — pricing](https://ai.google.dev/gemini-api/docs/pricing) | Per-model input / output / cache-read / cache-storage-per-hour; the exact 0.1× ratio across the range |
| [Gemini — context caching](https://ai.google.dev/gemini-api/docs/caching) · [generateContent caching](https://ai.google.dev/gemini-api/docs/generate-content/caching) · [Interactions caching](https://ai.google.dev/gemini-api/docs/interactions/caching) · [CachedContent](https://ai.google.dev/api/caching) · [generateContent reference](https://ai.google.dev/api/generate-content) | Implicit on by default for 2.5+, *"no cost saving guarantee"*, minimum-token table (and Gemini 3.6 Flash's absence from it), explicit cache default TTL 1 h and its `ttl`/`expireTime` fields, explicit caching unsupported in the Interactions API, `promptTokenCount` **includes** cached content |
| [DeepSeek — pricing](https://api-docs.deepseek.com/quick_start/pricing) · [KV cache guide](https://api-docs.deepseek.com/guides/kv_cache) · [launch note](https://api-docs.deepseek.com/news/news0802/) | V4-Flash $0.0028/$0.14, V4-Pro $0.003625/$0.435; 64-token storage unit; free storage; "hours to days" expiry; per-user isolation; `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` |
| [Kong — ai-semantic-cache reference](https://developer.konghq.com/plugins/ai-semantic-cache/reference/) | Tier `ai_gateway_enterprise`; `cache_ttl` 300 s, `message_countback` 1, `exact_caching` false, `ignore_*_prompts` false |
| [Portkey — cache docs](https://portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic) · [semantic thresholds blog](https://portkey.ai/blog/semantic-caching-thresholds/) | `max_age` in **seconds** (min 60, default 7 days); semantic Enterprise-only, 0.95, *"system prompt is ignored for matching purposes"*; the "largest lake / second largest" false-hit example |
| [LiteLLM — proxy caching](https://docs.litellm.ai/docs/proxy/caching) | Backend list, TTL knobs, `x-litellm-cache-key`, `x-litellm-semantic-similarity` |

**Attempted and not confirmed** (recorded so nobody re-cites it): Google Cloud's *"90% … on Gemini 2.5 or later; 75% on Gemini 2.0"* prose. Three direct fetches on 2026-07-29 — `docs.cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview`, `docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview`, `ai.google.dev/gemini-api/docs/caching.md.txt` — returned navigation shells or pages lacking the sentence. The 90% figure is established here from the price sheet instead, exactly and independently.

**Source trees, read at pinned commits** (each SHA re-confirmed via `gh api repos/OWNER/REPO/commits/SHA` on 2026-07-29; committer dates as returned):

| Project | Commit (committer date) | Files read |
|---|---|---|
| Portkey-AI/gateway | `669825cbe89ee51569918b8f78a9db486fd69dd4` (2026-05-25) | `src/middlewares/cache/index.ts` · `src/handlers/services/{cacheService,responseService,requestContext,logsService}.ts` · `src/globals.ts` |
| BerriAI/litellm | `c274cf321c5c35c629220a89bb497d15b56f870f` (2026-07-29) | `litellm/caching/{caching.py,caching_handler.py,redis_semantic_cache.py,s3_cache.py}` · `litellm_core_utils/prompt_templates/common_utils.py` |
| maximhq/bifrost | `e6952b6a7172658b2594208a59e064cd2b60b9cc` (2026-07-28) | `plugins/semanticcache/{main.go,utils.go,search.go}` — note the default branch is `dev`, not `main` |
| Kong/kong | `391ee48d3a68e8d0bbd0405ec1d02d75f768aa92` (2026-07-22) | `kong/plugins/proxy-cache/{cache_key.lua,handler.lua,schema.lua}` + plugin directory listing |
| higress-group/higress | `c8b82797c51a97faca46e2ae12990453f5026802` (2026-07-23) | `plugins/wasm-go/extensions/ai-cache/{main.go,core.go,README_EN.md}` · `config/config.go` · `cache/{provider.go,redis.go}` · `vector/provider.go` |
| envoyproxy/ai-gateway | `6722cca8d33896c4464c12f2de5aaf1238a569b6` (2026-07-23) | recursive tree listing + `examples/cache/cache_control.md` |
| kubernetes-sigs/gateway-api-inference-extension | `415f528f866ad5c1663ee7ebb80a0b0271725625` (2026-07-28) | `docs/proposals/0602-prefix-cache-aware-routing-proposal/README.md` (status: Implemented) |
| llm-d/llm-d-router | `c61197709c3318655ef290dcb8151397dd4fd236` (2026-07-28) | `pkg/epp/framework/plugins/scheduling/scorer/prefix/plugin.go` · `pkg/epp/framework/plugins/requestcontrol/dataproducer/approximateprefix/README.md` |
| vllm-project/aibrix | `a1626c811b3e399c0dd32f3a7aaada4ba747f622` (2026-07-29) | `pkg/plugins/gateway/algorithms/prefix_cache_readme.md` · `pkg/utils/prefixcacheindexer/hash.go` |
| kgateway-dev/kgateway | `e448e21dc0e89243f4d499b6a227828017321e8f` (2026-07-29) | `design/10411-gateway-api-inference-extension-support.md` (tree listing; no prefix-scoring code) |

**GitHub issues and PRs** (each fetched via `gh api` on 2026-07-29 and confirmed to exist and to say what it is cited for):

| Item | State · created | Cited for |
|---|---|---|
| [litellm#26990](https://github.com/BerriAI/litellm/pull/26990) merged 2026-05-04 · [#26992](https://github.com/BerriAI/litellm/pull/26992) closed unmerged |  | The cross-tenant semantic-cache false hit, admitted in the vendor's own PR body |
| [litellm#30339](https://github.com/BerriAI/litellm/issues/30339) | closed · 2026-06-13 | The fix that excluded prompt content from the scope key *and* re-added tenant identity |
| [litellm#29086](https://github.com/BerriAI/litellm/issues/29086) · [#31610](https://github.com/BerriAI/litellm/issues/31610) · [#6954](https://github.com/BerriAI/litellm/issues/6954) · [#32324](https://github.com/BerriAI/litellm/issues/32324) | closed · open · closed · open | The mirror failure — semantic caches that silently never hit |
| [litellm#28778](https://github.com/BerriAI/litellm/issues/28778) | **open** · 2026-05-25 | Agent tool-return content lost under semantic cache — **reporter's diagnosis, unconfirmed, not reproduced here** |
| [litellm#9812](https://github.com/BerriAI/litellm/issues/9812) | closed · 2025-04-08 | The double-count precedent: $0.091311 vs a console-verified $0.05439 |
| [litellm#34801](https://github.com/BerriAI/litellm/issues/34801) | **open** · 2026-07-27 | Cache-read undercount −24%, cost +8.5% in a clean 40-request reconciliation |
| [litellm#34797](https://github.com/BerriAI/litellm/issues/34797) · [Portkey#1579](https://github.com/Portkey-AI/gateway/issues/1579) | **open** · 2026-07-27 · 2026-03-25 | `cache_control` stripping, two adapters, two projects |
| [bifrost#5333](https://github.com/maximhq/bifrost/issues/5333) | **open** · 2026-07-17 | Semantic matching silently skipped for model ids containing `:` |
| [higress#4165](https://github.com/higress-group/higress/pull/4165) | **open** · 2026-07-17 | The nil-check ordering bug that leaves semantic cache off by default |

**Our arithmetic:** stated in full in §2 so it reproduces in any spreadsheet — the $6.6250 → $2.2400 ladder, the closed-form cross-check, all break-even hit rates, the sensitivity table, the N-saturation curve and the 5m-vs-1h TTL crossover. Written and run 2026-07-29; every number in §2 and §3.5 is printed by it.

**Repo files:** [README.md](../README.md) §*Prompt caching through a gateway* and the glossary rows for semantic caching / prompt cached input / KV cache / cache hit rate · [data/models.json](../data/models.json) (`as_of` 2026-07-28 — every `cached_input` value cross-checked against the official pages today and found exact) · [chapter 1](protocol-translation.md) §2 and §3.5 · [chapter 4](gateway-anatomy.md) §2.1 and §3.1.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every claim above is dated and linked to a price sheet, a commit, an issue or a re-runnable script, so you can re-check it. If a pinned commit has moved on, or if you settle the OpenAI cache-write billing question in §5.2, that's a PR we want.*
