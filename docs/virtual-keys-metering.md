# Virtual Keys, Budgets & Metering — how a gateway counts your money, and where the count goes wrong

*Last updated 2026-07-29 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

> 📊 **Key numbers** · Six open-source gateways, read at pinned commits on **2026-07-29**, answer "can this key afford this request?" three incompatible ways — and only **LiteLLM** makes the check and the counter mutation the *same operation* (one Redis `INCRBYFLOAT`, then compare the **post**-increment value). **new-api** and **one-api** debit an estimate up front, then disable that protection for exactly the accounts holding the most money, via a "trust" bypass. **Bifrost** and **Higress** compare a counter that only moves *after* the response, so N concurrent requests against a budget with one cent left all pass. **Kong OSS** performs no spend check in the open-source data path at all. Downstream of admission, the count itself is the larger problem: one production LiteLLM deployment reports **80.7% of streaming success rows (245,562 of 304,148)** written with real token counts and **$0 cost** ([litellm#34875](https://github.com/BerriAI/litellm/issues/34875), open, filed 2026-07-28). Reasoning tokens are arranged **three incompatible ways** by three vendors — a *subset* of the output count on OpenAI and Anthropic, a **separate addend** on Gemini — so billing `output` alone misses every thinking token on Gemini while `output + reasoning` double-counts on the other two. new-api has shipped the first of those errors for **14 months**, leaving **89.84%** of output tokens unbilled on the reporter's Gemini request ([new-api#1103](https://github.com/QuantumNous/new-api/issues/1103), open since 2025-05-25). A separate reasoning *price* exists in exactly **one of six** trees; separate cache prices in **three of six**. And the crash windows are seconds, not milliseconds: up to **~15 s** of spend rows in LiteLLM, **10 s** of budget deltas in Bifrost, **5 s** in new-api with batching enabled — while in Higress the debit is the final statement of the stream, so an aborted request is simply free.

[Chapter 4](gateway-anatomy.md) walked the request lifecycle and marked two stages as the ones that force a database: **stage 2, virtual key and budget**, and **stage 9, meter**. This chapter is those two stages at full depth. It answers four questions a feature matrix cannot: what a "virtual key" actually scopes (the term names two opposite objects), whether your budget survives concurrency, whether the token count you are billed on is the token count the provider produced, and what happens to both when the process dies.

The short version, and the reason this chapter exists: **admission control and metering are the same money, measured twice, by two mechanisms that almost never agree.** Admission runs before the call on an estimate; metering runs after it on a usage object that three vendors shape three different ways. Every failure in this chapter lives in the gap between those two numbers.

Sourcing is stated inline. Gateway behaviour is read from source at a pinned commit and quoted; vendor semantics are quoted verbatim from the official spec, SDK type or docs page with a retrieval date; arithmetic is marked **ours** and reproduces from the figures printed beside it; figures taken from this repo's data files are marked *repo-sourced* with their `as_of`. Where something could not be verified, it is marked as such in place rather than smoothed over — §12 lists what this chapter deliberately does not establish.

**Scope note.** Six trees are read here: LiteLLM, new-api, one-api, Bifrost, Kong OSS and Higress. Five overlap chapter 4's seven; **one-api** is added because it is the MIT original that new-api forked, and **Portkey OSS** and **Envoy AI Gateway** were not re-read this pass. One-api's newest commit is `8df4a26` (2025-02-21) and its newest release is v0.6.10 (2025-02-02), so its metering code is roughly **17 months older** than every other tree compared here — which makes "gateway X is worse" framing against it misleading, and matches this repo's own read: *"MIT original; maintenance slowed vs forks — new-api is the more active successor. Audit before prod."* (repo-sourced, [data/gateways_eval.json](../data/gateways_eval.json), `as_of` 2026-07-28).

---

## 1. The concept in 60 seconds

A gateway that charges anyone for anything runs the same four-step loop, and each step can be wrong on its own.

| Step | What it does | The number it uses | What goes wrong here |
|---|---|---|---|
| **1 · Scope** | Resolve a downstream credential to a tenant, a model allowlist, a budget and a set of limits | none | The term "virtual key" names two opposite objects (§2.1); the tenant hierarchy is one level deep in new-api, exclusively one-of-two in Bifrost, and five simultaneous levels in LiteLLM (§2.2) |
| **2 · Admit** | Decide whether this request may proceed | an **estimate**, computed before any token exists | Check-then-act races; estimates that are never reconciled; a bypass that skips the check for high-balance accounts (§3) |
| **3 · Count** | Turn a finished response into tokens | the provider's `usage` object, or a fallback the gateway invents | Streams that never deliver usage; reasoning and cache tokens arranged three and four ways; an estimator where a tokenizer should be (§4–§7) |
| **4 · Settle** | Turn tokens into money and make it durable | a price map keyed on the model name | Prices that depend on fields returned *in the response*; integer truncation; the write that never lands because the process died (§8) |

**The one-sentence rule this chapter argues for: step 2 and step 4 must reconcile against each other — and only three of the six trees read here even attempt it, in two cases from a goroutine that dies with the process.** LiteLLM reserves via `reserve_budget_for_request` and settles via `reconcile_budget_reservation`. new-api applies `delta := actualQuota - preConsumed` in `SettleBilling`. one-api computes `quotaDelta := quota - preConsumedQuota` inside `go postConsumeQuota(...)`, fired and never awaited. **Bifrost, Higress and Kong OSS never form a pre-call estimate at all**, so there is nothing to reconcile — their admission decision and their bill are simply different events about the same request, and nothing notices when they disagree.

---

## 2. What a virtual key actually scopes

### 2.1 The word names two opposite objects

This is the reason the feature-matrix checkbox is useless. In **LiteLLM**, **Bifrost** and **new-api**, a virtual key is a *downstream caller credential* scoped to a tenant — the thing you hand your data team. In **Portkey**, the vendor that popularized the term, a "Virtual Key" is an *upstream provider credential* — an alias for your OpenAI or Bedrock secret in a vault. Portkey's own Create Virtual Key API reference now carries the notice, verbatim: *"Deprecated. Use the Integrations API to store provider credentials and the Providers API to create AI Providers in your workspace."* (retrieved 2026-07-29). Its migration page states *"Virtual Keys have been migrated to Model Catalog"*, with virtual keys renamed to **AI Providers** at the workspace level and Model Catalog supplying *"Fine-grained budgets, rate limits, and model allow-lists."*

So a buyer asking "does it have virtual keys?" across LiteLLM and Portkey is comparing a tenant object to a secret-vault entry, and this repo's glossary line — *"per-user/team keys the gateway issues in front of your real provider keys, with their own budgets and limits"* ([README](../README.md#glossary)) — describes only the LiteLLM sense. Ask instead: **which direction does this credential point, and what does it carry?**

### 2.2 Three schemas, side by side

The LiteLLM and new-api columns are read from source at the pinned commits below. The Bifrost column is the **vendor's governance documentation**, retrieved 2026-07-29 — its virtual-key schema was not read from source this pass, and that is why it is thinner, not because it has fewer fields.

| Axis | LiteLLM (`_types.py` L1029–1135 @`c274cf3`) | new-api (`model/token.go` `type Token struct` @`c27d1ef`) | Bifrost (governance docs, retrieved 2026-07-29) |
|---|---|---|---|
| **Model allowlist** | `models`, `aliases`, `access_group_ids` | `ModelLimitsEnabled` + `ModelLimits` | `allowed_models` inside `provider_configs` |
| **Budget** | `max_budget`, `soft_budget`, `budget_duration`, `budget_id`, `budget_limits` (source comment: *"multiple concurrent budget windows"*), `model_max_budget`, `budget_fallbacks`, `throttle_on_budget_exceeded` | `RemainQuota`, `UsedQuota`, `UnlimitedQuota` — **integers** (§10.4) | `max_limit` + `reset_duration` (`1m, 1h, 1d, 1w, 1M, 1Y`) |
| **Rate limit** | `tpm_limit`, `rpm_limit`, `max_parallel_requests`, `model_rpm_limit`, `model_tpm_limit`, `mcp_rpm_limit`, `tag_rpm_limit`, plus `rpm_limit_type`/`tpm_limit_type` ∈ `guaranteed_throughput \| best_effort_throughput \| dynamic` | **no rpm/tpm field on the `Token` struct** ⚠️ see caveat below | `token_max_limit`, `request_max_limit` with their own reset durations — documented as *"(VK-level only)"* |
| **Expiry / rotation** | `duration`, `auto_rotate`, `rotation_interval` (*"e.g. '30d', '90d'"*) | `ExpiredTime` with the inline comment `// -1 means never expired` | — |
| **Tenant hierarchy** | `user_id` **and** `team_id` **and** `organization_id` **and** `project_id` **and** `agent_id`, simultaneously | `UserId` only — one level deep | *exclusive*: one team **or** one customer **or** neither |
| **Network** | — | `AllowIps` (an IP allowlist, with a `GetIpLimits()` splitter) | — |
| **Axes most comparisons omit** | `guardrails`, `policies`, `prompts`, `allowed_routes`, `allowed_passthrough_routes`, `allowed_vector_store_indexes` (per-index read/write), `enforced_params`, `blocked`, `allowed_cache_controls`, `tags`, `router_settings`, `object_permission`, and `key_type` ∈ `llm_api \| management \| read_only \| default` | `Group`, `CrossGroupRetry` (comment: *"跨分组重试，仅auto分组有效"*) | `key_ids` — restricts which *upstream* provider keys the VK may use |

Three things fall out that no comparison table in the wild states.

**(a) LiteLLM's key is the only one that can detect over-allocation.** The source comment on `rpm_limit_type` reads *"raise an error if 'guaranteed_throughput' is set and we're overallocating rpm"* — the gateway knows the sum of issued key limits against real capacity. Nobody else in this comparison models that at all.

**(b) The tenant hierarchies are not the same shape, so "multi-tenant" does not compare.** LiteLLM's key carries user, team, org, project and agent at once; Bifrost's is *exclusively* attached to one team or one customer; new-api's has a single `UserId`. A budget policy expressed in one of these often cannot be expressed in another.

**(c) Bifrost's calendar-boundary reset is a timezone seam.** Its governance docs say budgets *"reset at calendar boundaries in UTC (day/week/month/year) instead of on a rolling window"* when calendar alignment is on. A "monthly budget" is therefore a **UTC** month, which will not align with a provider invoice period or with a finance calendar in any other zone.

> ⚠️ **Caveat, stated because it was not checked.** The absence of rpm/tpm fields was verified on new-api's `Token` struct only. Whether new-api enforces per-key rate limits from a *different* table or middleware was **not** checked, so this chapter does not claim that new-api virtual keys cannot rate-limit.

---

## 3. Admission: reserve, debit, or read — and what each does under concurrency

### 3.1 Three mechanisms, and one gateway that implements none

Every gateway here runs its spend check **before** the provider call. The difference is what the check *does* to the counter, and that difference is the whole story.

| Gateway | Mechanism | Unit of atomicity | What 20 concurrent requests do against a nearly-empty budget |
|---|---|---|---|
| **LiteLLM** | **Reserve, then reconcile.** `_reserve_budget_after_common_checks` runs in auth, immediately after `common_checks`; `reserve_budget_for_request` estimates max cost, increments, and admits on the **post**-increment value: `if current_spend > counter.max_budget:` | one Redis `INCRBYFLOAT` per counter key (`redis_cache.py:872`), with the in-memory copy written only after Redis returns | Each request's increment is visible to the next. The reservation later settles to actual via `reconcile_budget_reservation` |
| **new-api** · **one-api** | **Debit an estimate, refund later.** new-api: `PreConsumeBilling` before the retry loop, `SettleBilling` applies `delta := actualQuota - preConsumed`. one-api: `CacheGetUserQuota` → reject if negative → `CacheDecreaseUserQuota` | a single-statement SQL `UPDATE ... quota - ?` per row, plus a *detached* Redis `HINCRBY`/`DECRBY` in another goroutine — the two are never atomic with each other | Bounded by the debit — **unless the trust bypass fires** (§3.3), which turns the mechanism into the read below for exactly the highest-balance accounts |
| **Bifrost** · **Higress** | **Read a counter, decrement after the response.** Bifrost: `if budget.CurrentUsage+baseline >= effectiveMaxLimit` → `DecisionBudgetExceeded` → HTTP 402. Higress `ai-quota`: a bare Redis `GET`, then `if response.Integer() <= 0` → HTTP 403 | nothing on the request path. Bifrost bumps an in-process `sync.Map` via CAS in the post-hook; Higress fires one `DecrBy` on the final stream chunk | **All 20 read the same value and all 20 pass.** A Higress consumer sitting at `quota=1` can run an unbounded number of simultaneous requests |
| **Kong OSS** | **None.** At `391ee48` the OSS tree ships six AI plugins and none of them reads a balance; the terminal metering step is `kong.log.set_serialize_value("ai.<ns>.usage", usage)`, gated on `if not conf.logging or not conf.logging.log_statistics then return true end` | — | Nothing is denied, because nothing is counted centrally. Budgets are Enterprise (`ai-rate-limiting-advanced`, `ai-proxy-advanced`) |

LiteLLM's own source states the failure of the alternative, in the warning emitted when you turn its reservation off with `disable_budget_reservation`, verbatim at `user_api_key_auth.py`:

> *"Budget enforcement is read-time only — concurrent requests can each pass the spend check before their cost is recorded, so a configured budget may be briefly exceeded under high concurrency."*

That sentence describes exactly what Bifrost and Higress do by construction. Four open LiteLLM issues demonstrate the same class in LiteLLM's own remaining read paths ([#34732](https://github.com/BerriAI/litellm/issues/34732) session-budget bypass, [#34733](https://github.com/BerriAI/litellm/issues/34733) window-reset overwrite, [#33325](https://github.com/BerriAI/litellm/issues/33325) pod-local spend across replicas, [#34101](https://github.com/BerriAI/litellm/issues/34101) project budgets missing from the reservation) — all four verified open via `gh api` on 2026-07-29.

### 3.2 "Atomic" is a per-counter word, not a per-request word

The precision that matters, and that no datasheet states: **LiteLLM's atomic unit is one counter, not the counter set.** `reserve_budget_for_request` loops over `_COUNTER_ENTITY_TYPES` — Key, Team, TeamMember, User, EndUser, Tag, Organization — reserving them one at a time. Each reservation is atomic; a multi-tier reservation as a group is not. Compensating release exists in an `except` block and in `_release_applied_entries_best_effort`, so the in-process failure path is handled.

Bifrost's serialisation point is declared in its own doc comment on `BumpBudgetUsage`, verbatim: *"This is the serialisation point for every usage increment: callers MUST funnel through this method ... rather than doing a plain Load → clone → mutate → Store, which races."* That is a correct in-process CAS — and it is process-local: the OSS tree has exactly one `GovernanceStore` implementation, `LocalGovernanceStore`.

Higress splits the difference across its two plugins. `ai-quota` fuses nothing: a `GET` to check, a fire-and-forget `DecrBy` to debit, with a `nil` completion callback so a Redis failure at that instant is neither retried nor logged. `ai-token-ratelimit` is stronger — both phases are server-side Lua, and the accumulate phase is one atomic `EVAL` over all matched rule keys — but the *check* is still a read of a counter that only moves after the response.

### 3.3 The trust bypass: protection removed from the accounts with the most at stake

Both Go forks ship the same idea and it deserves to be named. new-api's `preConsume` opens with `if s.shouldTrust(c) { s.trusted = true; effectiveQuota = 0 ... }`, and `shouldTrust` resolves for wallet funding to `return s.relayInfo.UserQuota > trustQuota`. Subscriptions are excluded from the bypass with an explicit three-point comment. one-api does the same thing in the other order: `CacheDecreaseUserQuota` fires **first**, and only then does `if userQuota > 100*preConsumedQuota { ... preConsumedQuota = 0 ... }` zero the charge, under the comment *"in this case, we do not pre-consume quota / because the user has enough quota"*. The token-level debit is correctly skipped; the Redis user-quota key has already been decremented by an amount that is then never charged.

**Read that consequence twice.** The safe mechanism is switched off precisely for the accounts with the largest balances — the ones where a concurrency overshoot or a lost settlement costs the most. The project's own tracker carries the leak case: [new-api#4429](https://github.com/QuantumNous/new-api/issues/4429), *"用户额度低于信任额度发生异常时预扣费泄漏"*, **open** (verified via `gh api` 2026-07-29). one-api's fix for the two-level version of this — a high-quota user on a low-quota token getting no pre-charge — is [one-api#925](https://github.com/songquanpeng/one-api/pull/925), opened 2024-01-11 and **closed 2026-05-25 with `merged=false`** after 2.4 years.

---

## 4. The metering pipeline, end to end

Seven things must happen between the provider's last byte and a durable row. Each is a place the number changes.

| # | Stage | What must be true | The receipt when it isn't |
|---|---|---|---|
| 1 | **Capture usage from the wire** | The usage object must arrive at all — and on OpenAI Chat Completions it arrives only if the *client* opted in (§5.1) | A caller who omits `stream_options` opts out of being metered ([litellm#22280](https://github.com/BerriAI/litellm/issues/22280), closed `not_planned` 2026-06-15) |
| 2 | **Merge partial usage** | Anthropic's `message_delta` carries *cumulative* totals but only `output_tokens` is a required field; the correct rule is seed-from-`message_start`, then let any field present in `message_delta` win | Metering from `message_start` alone under-bills a server-tool request ~**4×** (§5.1) |
| 3 | **Fall back when usage never comes** | The fallback must be labelled as an estimate, not passed off as a count | Kong OSS `chars ÷ 4`; new-api's per-family character weights; Bifrost and Higress bill **zero** (§5.2) |
| 4 | **Decompose the counts** | Reasoning is a subset on two vendors and an addend on the third; cache tokens follow four different inclusion schemas | [new-api#1103](https://github.com/QuantumNous/new-api/issues/1103) (§6.2); [new-api#5003](https://github.com/QuantumNous/new-api/issues/5003) (§7.2) |
| 5 | **Price** | The price map must key on more than the model name — `service_tier` and `inference_geo` come back **in the response** (§10.5) | [litellm#34850](https://github.com/BerriAI/litellm/pull/34850) — a PR, unmerged as of 2026-07-29; filed 2026-07-27, patching regional geo uplift onto cached tokens |
| 6 | **Attribute** | The same number must reach the client, the ledger and the dashboard | [new-api#6144](https://github.com/QuantumNous/new-api/issues/6144), open — correct usage forwarded to the client, corrupted copy used for billing (established in [chapter 4](gateway-anatomy.md) §2.1 stage 9; its *methodological* consequence is §11 step 3 here) |
| 7 | **Persist** | The row must survive the process | §8 |

Stage 6 is the one that quietly invalidates a test you may already be running. Chapter 4 and the README both tell you to diff the `usage` fields in the response to confirm a cache discount — and new-api#6144 is invisible to that test, because the response is *correct*: the reporter's client saw `prompt_tokens: 1816` with `cached_tokens: 1792` (**98.7%** cached, ours) while new-api's own console log recorded `cache_tokens` as `0` and billed on that. Their words: *"这是真实的计费错误，不是单纯的显示问题"* — a real billing error, not merely a display problem. **The response usage is necessary evidence, not sufficient evidence.**

---

## 5. Counting a stream

### 5.1 Three vendors, three streaming contracts, no common shape

| | **OpenAI Chat Completions** | **OpenAI Responses** | **Anthropic Messages** | **Gemini `generateContent`** |
|---|---|---|---|---|
| **Opt-in required?** | **Yes** — `stream_options: {"include_usage": true}` | No | No | No |
| **Where usage arrives** | one extra chunk *before* `data: [DONE]`, with `choices` as an empty array | inside the terminal `response.completed` event | `message_start` (initial) then `message_delta` (cumulative) | undocumented |
| **Cumulative or terminal?** | terminal, all-or-nothing | terminal | **cumulative** | undocumented |
| **What an abort leaves you** | *nothing* — the vendor's own hedge, verbatim: *"**NOTE:** If the stream is interrupted, you may not receive the final usage chunk which contains the total token usage for the request."* | the terminal event never fires | the **last observed cumulative value**, which is usable | undocumented |
| **Required detail fields** | none — the whole `usage` object is opt-in | `input_tokens_details`, `output_tokens_details`, `total_tokens` all **required** | only `output_tokens` is required on `message_delta`; every input and cache field is `Optional` | — |

Two structural consequences, and they are not reconcilable in one codepath. **Correct OpenAI handling is wait-for-terminal-or-lose-it. Correct Anthropic handling is last-write-wins.** And OpenAI needs *two* streaming metering paths inside one vendor: Chat Completions gates usage behind a flag that Azure's Responses endpoint actively rejects ([litellm#28553](https://github.com/BerriAI/litellm/issues/28553), open — *"Unknown parameter: stream_options.include_usage"*), while the Responses shape can drop cost on the auto-routed path ([litellm#27459](https://github.com/BerriAI/litellm/issues/27459), open).

The Anthropic merge rule is worth spelling out because no single vendor page states it. `MessageDeltaUsage` declares `output_tokens: int` required and `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens_details` and `server_tool_use` all `Optional` (anthropic-sdk-python @`f5c30d0`). Anthropic's basic streaming example shows exactly the sparse case: `message_start` carries `{"input_tokens": 25, "output_tokens": 1}` and the closing `message_delta` carries `{"output_tokens": 15}` and nothing else. **Seed from `message_start`; let any field present in `message_delta` override, because those are cumulative and authoritative.**

Skipping that merge has a measurable price, in Anthropic's own published example. On the web-search stream, `message_start` reports `input_tokens: 2679`; the closing `message_delta` reports `input_tokens: 10682` with `server_tool_use: {"web_search_requests": 1}`. **Ours: 10,682 ÷ 2,679 = 3.99×.** Server-side tools run extra internal model turns whose input tokens appear only in the cumulative delta — and a gateway reading input from `message_start` is doing what Anthropic's own prompt-caching page tells implementers to do (*"within `usage` in the response (or `message_start` event if streaming)"*). Note also that `server_tool_use.web_search_requests` is a **billable unit that is not a token at all**.

### 5.2 What six gateways do when usage never arrives

Three outcomes, and two of them bill zero.

| Behaviour | Gateways | What actually happens |
|---|---|---|
| **Re-tokenize** | **LiteLLM**, **one-api** | LiteLLM: `returned_usage.prompt_tokens = prompt_tokens or token_counter(model=model, messages=messages)` and the same idiom over the accumulated `completion_output`. one-api: real tiktoken — but `getTokenEncoder` builds encoders only for `gpt-3.5`/`gpt-4o`/`gpt-4` prefixes and falls through to `defaultTokenEncoder`, logging *"using encoder for gpt-3.5-turbo"*, so **Claude and Gemini streams are metered with an OpenAI BPE** |
| **Estimate with a heuristic** | **new-api**, **Kong OSS** | new-api calls `EstimateTokenByModel` *directly*, bypassing the tiktoken path it does own; the estimator routes by substring (`gemini` / `claude` / else) into hardcoded character-class weights (Claude: `Word 1.13, Number 1.63, CJK 1.21, Symbol 0.4, MathSymbol 4.52, Emoji 2.6, Newline 0.89, Space 0.39`). Kong OSS: `chars ÷ 4` for completion, whitespace-words × **1.8** for streamed prompts (both established in [chapter 4](gateway-anatomy.md) §3.5) |
| **Bill nothing** | **Bifrost**, **Higress** | Bifrost reads `tokensUsed` off a usage object per response shape; if every guard fails it stays 0, `computeTextCost` returns 0 on `usage == nil`, `HasUsageData` is false and `shouldUpdateBudget := !update.IsStreaming \|\| (update.IsStreaming && update.HasUsageData)` skips the bump. Higress early-returns before its `DecrBy`. **A stream with no usage object is a free request** |

LiteLLM's fallback carries a documented trap that generalizes: the `or` idiom treats `1` as truthy, and Anthropic's `message_start` ships `output_tokens: 1` as a cursor. LiteLLM's answer is `_reset_anthropic_cursor_completion_tokens`, which zeroes a lone cursor value to re-enable the fallback. Bifrost's one deliberate exception runs the other way: a **failed** request carrying `BifrostError.ExtraFields.BilledUsage` is still billed, under the comment *"Anthropic charges us for them regardless."*

### 5.3 The opt-out is a quota-evasion vector

If usage is opt-in and metering is usage-derived, a caller can decline to be metered. That is the exact motivation in [litellm#22280](https://github.com/BerriAI/litellm/issues/22280) — verbatim, *"Users might avoid token limits by only streaming outputs"* — which was auto-closed as stale on **2026-06-15** with `state_reason: not_planned` (verified via `gh api` 2026-07-29). LiteLLM does ship a related setting; read at `c274cf3`, `common_request_processing.py` L1234–1245 under the comment `### AUTO STREAM USAGE TRACKING ###`, it reads `general_settings.get("always_include_stream_usage", False)` — **off by default** — and its two branches cover `"stream_options" not in self.data` and `"include_usage" not in self.data["stream_options"]`. A client that sends `stream_options: {"include_usage": false}` **explicitly** hits neither branch, so the opt-out survives even when the setting is on.

A gateway can also break the contract that makes OpenAI usage parseable in the first place. [litellm#28735](https://github.com/BerriAI/litellm/issues/28735) (**open**, 2026-05-24) reports LiteLLM's synthetic terminal chunk carrying `choices` with one entry instead of the spec's `choices: []`; a strict downstream client keying on the empty array to find the usage chunk will not find it. The earlier report [#8450](https://github.com/BerriAI/litellm/issues/8450) is closed `not_planned` and the proposed fix [#8751](https://github.com/BerriAI/litellm/pull/8751) is closed with `merged=false` — reported twice, fixed zero times (all three verified via `gh api` 2026-07-29).

---

## 6. Reasoning tokens — three incompatible arrangements

### 6.1 The trap, stated as arithmetic

| Vendor | Where reasoning lives | Inside the output count? | Vendor's own words |
|---|---|---|---|
| **OpenAI** | `completion_tokens_details.reasoning_tokens` | **Yes — subset** | on `rejected_prediction_tokens`, verbatim: *"However, like reasoning tokens, these tokens are still counted in the total completion tokens for purposes of billing, output, and context window limits."* |
| **Anthropic** | `usage.output_tokens_details.thinking_tokens` | **Yes — subset** | *"`output_tokens` remains the inclusive, authoritative total used for billing. This object provides a read-only decomposition for observability..."* |
| **Gemini** | `usageMetadata.thoughtsTokenCount` | **No — separate addend** | `total_token_count` is *"the sum of `prompt_token_count`, `candidates_token_count`, `tool_use_prompt_token_count`, and `thoughts_token_count`."* |

**So neither naive mapping is correct on all three.** Billing `output` alone is right on OpenAI and Anthropic and **misses all thinking on Gemini**. Billing `output + reasoning` is right on Gemini and **double-counts on the other two**. Gemini carries a fourth addend as well — `tool_use_prompt_token_count`, *"the number of tokens in the results from tool executions, which are provided back to the model as input"* — input-priced content living **outside** `prompt_token_count`.

Anthropic's `thinking_tokens` is new and carries two hedges the vendor states itself, verbatim: the count is *"Computed by re-tokenizing the raw reasoning text, so it may differ from the model's exact generation count by a small number of tokens"*, and *"`output_tokens - thinking_tokens` approximates the non-reasoning output."* That matters directly, because chapter 4 documents LiteLLM pricing reasoning separately via `output_cost_per_reasoning_token`: **splitting a bill on a field its own vendor labels approximate introduces error that flat `output_tokens` billing would not have.**

And both Anthropic and Google state plainly that you pay for tokens you never see. Anthropic: *"You're charged for the full thinking tokens generated by the original request, not the summary tokens. The billed output token count does **not match** the count of tokens you see in the response."* Google: *"Pricing is based on the full thought tokens the model needs to generate, despite only the summary being output from the API"* and *"When thinking is turned on, response pricing is the sum of output tokens and thinking tokens."* (both retrieved 2026-07-29).

> 🔒 **This is the proof that the estimators cannot be fixed.** Chapter 4 called Kong OSS's `chars ÷ 4` and new-api's character-weight tables "loose". On reasoning models they are not loose, they are **structurally incapable**: any gateway metering by counting the bytes it saw on the wire under-bills reasoning by construction, because the tokens are not in the response at all. A better tokenizer does not help.

### 6.2 Who prices reasoning separately: one of six

| Gateway | Separate reasoning rate? | Detail |
|---|---|---|
| **LiteLLM** | ✅ *conditional* | `output_cost_per_reasoning_token`, applied only when `not is_text_tokens_total and reasoning_tokens > 0`. **It degrades to the ordinary completion rate when the price map lacks the key** — so "own price" is conditional on the map carrying it |
| **new-api** | ❌ | a repo-wide grep for `ReasoningTokens` at `c27d1ef` returns only pass-through and conversion sites; no ratio, no pricing branch in `service/text_quota.go` or `setting/ratio_setting/` |
| **Bifrost** | ❌ | the only occurrence in `cost.go` is a struct copy; reasoning rides inside `completionTokens` and is charged the flat `outputRate` |
| **one-api** | ❌ | the whole pricing model is `quota = ceil((promptTokens + completionTokens*completionRatio) * ratio)`; a grep for reasoning across all `.go` files returns one struct field with no consumer in the billing path |
| **Kong OSS** | ❌ *and worse* | no reasoning metric is registered, and `llm_total_tokens_count` is **derived** as prompt+completion rather than stored, so an upstream total that counted hidden reasoning tokens is discarded — [Kong/kong#14816](https://github.com/Kong/kong/issues/14816), **open** (verified via `gh api` 2026-07-29) |
| **Higress** | ❌ | quota is denominated in tokens, not money: `totalToken := int(inputToken + outputToken)`. No rate is applied at all |

Anthropic adds a wrinkle that no gateway in this comparison models: **thinking tokens change price class between turns.** Verbatim: *"**Current-turn thinking** always counts toward `max_tokens`, is billed as output tokens..."* while *"**Prior-turn thinking** ... On models that keep all prior turns, previous thinking blocks remain in context, count toward the window, and are billed as input tokens like the rest of the conversation history. On models that keep only the last turn, the API strips older thinking blocks automatically..."* The same token is billed at the output rate once, then at the input rate (or the 0.1× cache-read rate) thereafter, or not at all — decided by which model answered. **A gateway cannot predict its own next-turn input count from the conversation it holds.**

---

## 7. Cache tokens — four schemas, and a sign error

### 7.1 The inclusion flip is not binary

[Chapter 1](protocol-translation.md#2-the-field-by-field-mismatch) documents the OpenAI-includes / Anthropic-excludes flip. There are four arrangements, not two.

| Vendor | Field names | Does the input total include cache traffic? | Reconciliation identity |
|---|---|---|---|
| **OpenAI** | `prompt_tokens_details.{cached_tokens, cache_write_tokens}`; Responses uses `input_tokens_details.*`; the Usage API uses `input_cached_tokens` / `input_cache_write_tokens` / `input_uncached_tokens` | **Includes both reads and writes** | **Ours**, from OpenAI's own documented Usage API example (`input_tokens: 1000`, `input_cached_tokens: 400`, `input_cache_write_tokens: 100`, `input_uncached_tokens: 500`): 400 + 100 + 500 = **1000** exactly — a three-way partition of the total |
| **Anthropic** | `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` (+ `cache_creation.{ephemeral_5m,ephemeral_1h}_input_tokens`) | **Excludes both** — *"tokens after the last cache breakpoint"* | the vendor publishes it: `total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens` |
| **Gemini** | `cachedContentTokenCount` | **Includes** — *"When `cached_content` is set, this also includes the number of tokens in the cached content."* | not published |
| **DeepSeek** | `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens` | two **mutually exclusive** counters | ⚠️ **not documented.** Both DeepSeek pages were fetched 2026-07-29; neither states whether hit+miss sums to `prompt_tokens`. The summation is strongly implied by the wording but it is inference, not documentation |

Note that **OpenAI has three usage vocabularies inside one vendor** — Chat Completions (`prompt_tokens`/`completion_tokens`), Responses (`input_tokens`/`output_tokens`) and the Organization Usage API (`input_tokens`/`input_cached_tokens`/…). A gateway reconciling its ledger against OpenAI's own billing console must map three name sets before it can even begin comparing to Anthropic or Google. [litellm#33772](https://github.com/BerriAI/litellm/issues/33772) is a failure at exactly that seam.

### 7.2 The most vivid receipt: the flip drove input tokens negative

[new-api#5003](https://github.com/QuantumNous/new-api/issues/5003) — *"命中缓存后，输入token变成了负数，计费出现严重BUG"* — created **2026-05-21**, closed the same day as a duplicate; the repost [#5005](https://github.com/QuantumNous/new-api/issues/5005) is closed `not_planned` (both verified via `gh api` 2026-07-29). Version v1.0.0-rc.7. The reporter's real numbers: input **56,322**, cache read **72,960**, output **87**; rates ⚡1.00/1M input, ⚡5.00/1M output, ⚡0.10/1M cache read.

**Ours, reproducing the bug** — new-api computed input as 56,322 − 72,960 = **−16,638**:

```text
(−16,638 × 1.00 + 72,960 × 0.10 + 87 × 5.00) / 1e6
  = −0.016638 + 0.007296 + 0.000435 = −0.008907   ✓ matches the reported charge
```

**Ours, the correct figure:**

```text
(56,322 × 1.00 + 72,960 × 0.10 + 87 × 5.00) / 1e6
  = 0.056322 + 0.007296 + 0.000435 =  0.064053    ✓ matches the reporter's expected charge
```

The sign inverted. Instead of charging ⚡0.064053 the ledger **credited** ⚡0.008907 — a ⚡0.07296 swing per request in the customer's favour, or in the reporter's words *"站长会出现明显亏损"* (the site operator takes an obvious loss). The mechanism: the upstream had already excluded cache reads from input (Anthropic semantics) and new-api subtracted them a second time.

**The tell that identifies this bug class on sight: cache read (72,960) exceeds input (56,322), which is only possible under exclusive semantics.** If your ledger ever shows that shape alongside a positive-input assumption, you have this bug.

### 7.3 Cache-write pricing is a metering dependency, not a nicety

Separate cache rates exist in three of six trees: **LiteLLM** (`cache_read_input_token_cost`, `cache_creation_input_token_cost`, plus `cache_creation_input_token_cost_above_1hr`), **new-api** (`CacheRatio` + `CacheCreationRatio` with a 5m/1h split, and an explicit clamp against a negative base charge), **Bifrost** (read, write and a `>1hr` write rate, with counts clamped against malformed provider payloads). one-api, Kong OSS and Higress have none.

Having the rates is not the same as being able to apply them. Anthropic prices 5-minute writes at **1.25×** and 1-hour writes at **2×** base input (matching [chapter 6](caching-economics.md) exactly, no discrepancy), so a gateway **cannot price a cache write without the TTL split** — and the SDK's own type model makes the null case legal: `CacheCreation` declares both `ephemeral_1h_input_tokens` and `ephemeral_5m_input_tokens` as required ints, while the parent `Usage.cache_creation` is `Optional`. [new-api#6353](https://github.com/QuantumNous/new-api/issues/6353) (**open**, 2026-07-20) is what happens when the split is absent: two cascading bugs zero the value, so *"总费用未包含缓存写入 Token 的费用"* — a silent 100% discount on the most expensive input token class.

---

## 8. Crash-safe accounting

Money lives in three places between the provider's response and a durable row: an in-process queue or map, a Redis counter, and the database. Which of the three you lose decides who eats the error.

| Gateway | Where money sits before the durable write | Lost on `SIGKILL` | Lost on graceful stop | Who eats it |
|---|---|---|---|---|
| **LiteLLM** | spend-log rows in an in-process list; aggregate deltas in an `asyncio.Queue`; flushed by a scheduler job at `batch_writing_interval = proxy_batch_write_at + random.randint(0, 5)`, with `PROXY_BATCH_WRITE_AT` defaulting to **10** | up to **~15 s** of *ledger rows* — but **not enforcement**, because the reservation is already `INCRBYFLOAT`'d into Redis | also lost: `proxy_shutdown_event` disconnects Prisma and flushes langfuse/billing metrics but **never drains the spend queues** | **the tenant** — the reservation survives as an over-reservation until TTL |
| **Bifrost** | in-memory `sync.Map` counters, dumped every `workerInterval = 10 * time.Second` | up to **10 s** of budget deltas | **nothing** — `Cleanup()` calls `DumpBudgets` then `DumpRateLimits` first, under a comment that names the risk verbatim: *"Final flush of in-memory deltas to DB before shutdown. Without this, any deltas accumulated since the last `workerInterval` tick are lost."* | the operator |
| **new-api** | with `BATCH_UPDATE_ENABLED`, a mutex-guarded in-process `map[int]int` drained on a `BATCH_UPDATE_INTERVAL` timer, default **5** s | the batched SQL delta; and the refund, which is dispatched into a detached `gopool.Go` goroutine that dies with the process | same detached-goroutine exposure | **the tenant** — the pre-consumed estimate stays debited and is never reconciled |
| **one-api** | everything: `go postConsumeQuota(...)` is fired and never awaited, and the handler returns immediately | the delta settle, the cache resync, the `RecordConsumeLog` row **and** the used-quota/channel counters | same | **the tenant** — pre-consumed debit with no log row explaining it; on the trusted path the request is free *and invisible* |
| **Higress** | nothing — the `DecrBy` is the final statement of the stream, after `if !endOfStream { return data }` | the entire debit | same | **the operator** — tokens burned, quota untouched |
| **Kong OSS** | one log line on `ngx.ctx`, which is per-request and per-worker | the analytics record for that request | same | nobody, and that is the point: **there is no balance to be wrong, which also means Kong OSS cannot detect or reconcile the loss** |

Three refinements worth carrying into a design review.

**(a) Losing enforcement and losing the ledger are different losses.** LiteLLM loses the ledger row but keeps enforcement, because the pre-call reservation is already in Redis. new-api and one-api lose the *reconciliation*, which means the charge freezes at the estimate. Higress loses the charge entirely. Note the direction: mechanisms that debit up front fail **against the tenant**; mechanisms that decrement after the response fail **against the operator**.

**(b) LiteLLM's narrower window is off by default.** `use_redis_transaction_buffer` defaults to `False`; and when it is on, popped-then-failed data is acknowledged as lost in the log message itself: *"Data already popped from Redis may be lost. Error: %s"*. Two open issues cover the same ground from the outside ([#34805](https://github.com/BerriAI/litellm/issues/34805) buffers dropped on shutdown, [#34820](https://github.com/BerriAI/litellm/issues/34820) rows popped before the DB write is awaited).

**(c) Idempotency that does not survive a restart is not idempotency.** Bifrost dedupes billing per physical call via `tryClaimBilling` keyed on `RequestID:AttemptNumber` — genuinely good, and the only such mechanism in this comparison — but the map is in-memory with `billedEntryTTL = 5 * time.Minute`, so it does not survive a restart either.

---

## 9. Multi-tenancy isolation, and why some gateways require Postgres

Chapter 4 established the rule: **stages 1, 2 and 9 are what force a database** — auth needs key lookup, budgets need a durable counter, metering needs a ledger. This chapter supplies the reason the counter cannot simply live in memory, and it is §3.1 plus §8 together.

A budget counter must be **shared** (or every replica enforces its own private cap — exactly [litellm#33325](https://github.com/BerriAI/litellm/issues/33325), pod-local spend across replicas), **atomic** under concurrency (§3.1), and **durable** across a restart (§8). Redis gives you the first two and not the third; a relational store gives you the third and, through row locks and transactions, a workable version of the second. That is why the gateways with real virtual keys run **both**: Redis for the hot counter, Postgres or MySQL for the ledger and the key table. LiteLLM's writeback is one Prisma transaction per entity table with IDs sorted for lock ordering; Bifrost's periodic dump is one GORM transaction with IDs sorted and a monotonic `last_reset` guard; new-api and one-api use single-statement `UPDATE ... quota - ?` row writes with **no** enclosing transaction and, in new-api's case, no `WHERE quota >= ?` guard — so the balance can go negative.

Three isolation seams a tenant model has to name:

- **Counter scope.** LiteLLM reserves across seven entity types at once (Key, Team, TeamMember, User, EndUser, Tag, Organization); Bifrost attaches a VK to one team **or** one customer, exclusively; new-api and one-api have a single user level. A budget you can express in one is often inexpressible in another.
- **Cross-node agreement.** Bifrost's `CheckBudget` compares `budget.CurrentUsage + baseline` and folds `baselines` into the persisted value at dump time, which implies a cluster layer feeding peer usage — but the OSS tree has exactly one `GovernanceStore` implementation and this pass did **not** locate the producer of a non-empty `baselines` map. Local mechanism confirmed; multi-node semantics **INCONCLUSIVE** from this repository alone.
- **Reset boundary.** Bifrost's calendar-aligned budgets reset on **UTC** boundaries (§2.2). If your finance month is not UTC, your "monthly budget" and your invoice month are different windows.

The buyer's read is unchanged from chapter 4 and this chapter sharpens it: **the moment you want the feature that most justifies a gateway — virtual keys with enforced budgets — you have signed up for two datastores, a migration story and an on-call rotation.** A gateway that offers budgets without both is offering you §3.1's read-then-decrement, whether or not it says so.

---

## 10. Failure modes, with receipts and reproduced arithmetic

Every issue below was fetched via `gh api` on **2026-07-29** and confirmed to exist, to carry the state given, and to say what it is cited for. Arithmetic labelled **ours** is computed from the figures in the issue body and printed so you can re-run it.

### 10.1 Streaming metering fails at production scale — 80.7% of rows at $0

[litellm#34875](https://github.com/BerriAI/litellm/issues/34875), **open**, created **2026-07-28**. The reporter, verbatim: *"In our proxy deployment (`litellm[proxy]==1.83.14`, Python 3.13), **80.7% of streaming success rows (245,562 of 304,148)** recorded a zero cost with real token counts. The rate was load-independent but strongly model-correlated (~93–97% for gpt-5.x streams, ~0% for Claude streams), consistent with a scheduling race rather than a data problem."* **Ours: 245,562 ÷ 304,148 = 80.74%** ✓. Their root cause: the streaming handler schedules `async_success_handler` as an asyncio task *and* submits `success_handler` to the thread-pool executor simultaneously; both mutate the same uncopied `model_call_details` dict; the sync handler unconditionally sets `response_cost = None` while the async handler writes the real cost, with *"no lock or ordering between the asyncio task and the executor thread."* This is a **concurrency bug in the metering pipeline** — a different axis from §3's budget races and §8's crash losses, and the strongest available evidence that streaming metering fails at scale.

### 10.2 Both directions in one cost engine — three receipts, January to June

| Receipt | Direction | **Our** reproduction |
|---|---|---|
| [litellm#26807](https://github.com/BerriAI/litellm/issues/26807), **open**, 2026-04-29 — cached tokens billed at the full input rate in the custom-pricing path | **1.67× over** | Reported: `prompt_tokens=6074`, `cached_tokens=3456`, `completion_tokens=285`; rates 2.5e-6 in / 1.5e-5 out / 2.5e-7 cache-read; returned cost **0.01946**. Buggy: 6074×2.5e-6 + 285×1.5e-5 = 0.015185 + 0.004275 = **0.01946** ✓ (every prompt token at the plain input rate). Correct: (6074−3456)×2.5e-6 + 3456×2.5e-7 + 0.004275 = 0.006545 + 0.000864 + 0.004275 = **0.011684**. Overcharge **0.01946 ÷ 0.011684 = 1.67×** |
| [litellm#18599](https://github.com/BerriAI/litellm/issues/18599), closed 2026-01-03; fix [PR #18607](https://github.com/BerriAI/litellm/pull/18607) **verified merged** `2026-01-03T18:39:01Z` — reasoning tokens priced *instead of* total completion tokens | **7.02% under** | gpt-5-nano, `prompt_tokens=17`, `completion_tokens=482`, `reasoning_tokens=448`. Correct: 17×0.05/1e6 + 482×0.40/1e6 = **0.00019365** ✓. Buggy: 17×0.05/1e6 + 448×0.40/1e6 = **0.00018005** ✓ — only the 448 reasoning tokens priced, the 34 non-reasoning completion tokens dropped. Under-report **7.02%**. *(This issue is already cited in [chapter 4](gateway-anatomy.md); new here is the reproduced arithmetic and the sibling below)* |
| [litellm#30488](https://github.com/BerriAI/litellm/pull/30488), a PR, **verified merged** `2026-06-17T11:47:31Z` — reasoning tokens **double-billed** in the Perplexity manual cost fallback | **2.17× over** | Author's before/after for `perplexity/sonar-deep-research` with `prompt_tokens=9, completion_tokens=20, reasoning_tokens=15`: **$0.000223 → $0.000103**. The PR describes itself as a *"Sibling fix to #18607 which addressed the same convention mismatch in the central cost path"* |

**The reusable lesson is the pair, not either one.** The subset-versus-addend convention (§6.1) is not decided once in a cost engine — it is re-decided in **every provider adapter, forever**. That is why the same class of bug landed in the central path in January (under-bill) and in the Perplexity adapter in June (over-bill).

### 10.3 A reasoning bug that has been open for 14 months, self-evident in its own payload

[new-api#1103](https://github.com/QuantumNous/new-api/issues/1103), *"gemini reasoning未计费"*, opened **2025-05-25**, **verified still open** on 2026-07-29. The reporter's returned payload: `prompt_tokens: 7`, `completion_tokens: 124`, `total_tokens: 1228`, `completion_tokens_details.reasoning_tokens: 1097`.

**Ours:** 7 + 124 = 131, but `total_tokens` says 1228 — and 1228 − 7 = 1221 = 124 + 1097 exactly. So the gateway's own `total_tokens` is computed correctly while its `completion_tokens` omits the 1,097 reasoning tokens; **the payload contradicts itself**. Billed output is 124 of 1,221 = **10.16%**, meaning **89.84% of output tokens go unbilled**. This is precisely the failure §6.1 predicts from Gemini's separate-addend arrangement, sitting open for over a year.

### 10.4 The ledger cannot represent the price

Orthogonal to every token-semantics bug above: new-api's `Token` struct declares `RemainQuota int` and `UsedQuota int` — Go **ints** (read at `c27d1ef`), so every request's cost is rounded to a whole quota unit. [new-api#2608](https://github.com/QuantumNous/new-api/issues/2608), *"quota 精度导致的计费问题"*, **open** since 2026-01-08, quotes the code: `if modelRatio != 0 && calculateQuota <= 0 { calculateQuota = 1 }` followed by `quota := int(calculateQuota)`. Two defects in three lines — any nonzero sub-unit cost is forced **up** to 1 (overcharge), and `int(...)` **truncates** toward zero everywhere else (undercharge). The reporter's question is the right one to put to any vendor: *"quota 设置成整数是有什么考量吗？"* — was there a reason quota is an integer? **Even a gateway that reads every usage field perfectly still cannot bill correctly if its ledger type cannot hold the number.**

### 10.5 The price depends on fields that arrive *in the response*

`Usage` in anthropic-sdk-python @`f5c30d0` declares `inference_geo: Optional[str]` — *"The geographic region where inference was performed for this request"* — and `service_tier: Optional[Literal["standard", "priority", "batch"]]` — *"If the request used the priority, standard, or batch tier."* Google has the parallel: `traffic_type` on usage metadata, *"Output only. The traffic type for this request."* **Both change the price, and both are returned rather than requested, so the price of a request is not knowable from the request.** [litellm#34850](https://github.com/BerriAI/litellm/pull/34850) (a **PR**, open and unmerged as of 2026-07-29; filed 2026-07-27) is a gateway actively patching for this: *"fix(anthropic cost): apply regional geo uplift to cached tokens"*. The rule: **any gateway pricing from a static model→price map keyed on model name alone will mis-price geo-uplifted and priority-tier traffic — and the error is invisible, because the model name matched.**

### 10.6 A fee-evasion fix that has sat open and unmerged since 2023

[one-api#412](https://github.com/songquanpeng/one-api/pull/412), *"为函数调用加上计费避免逃费问题"* (add billing for function calls to avoid fee evasion), a **pull request**, created **2023-08-13**, **state open, `merged=false`** (verified via `gh api` 2026-07-29). The author's own note concedes the estimate differs from OpenAI by a token or two but is *"比不计费好"* — better than not billing at all. Paired with #925 (§3.3), the honest framing is **not** active regression: it is two unmerged fixes in a project this repo already records as slowing.

---

## 11. Verify this yourself

Ordered by payoff per minute. Steps 1–3 need one API key and no gateway source.

1. **Diff a stream with and without `stream_options` — five minutes, and the highest-value measurement in this chapter.** Send the same streamed prompt twice through your gateway, once with `stream_options: {"include_usage": true}` and once with the field absent, then read both spend rows. This settles a conflict this chapter could not: [litellm#22280](https://github.com/BerriAI/litellm/issues/22280)'s reporter asserts *"Without that attribute, token count is zero"*, while chapter 4 establishes that LiteLLM falls back to a local `token_counter` over the messages — which would bill an *estimate*, not zero. Then repeat with `{"include_usage": false}` explicitly; §5.3 predicts the opt-out survives even with `always_include_stream_usage` enabled.
2. **Break the budget on purpose.** Set a small cap on one virtual key and fire 20 concurrent requests. §3.1 predicts the outcome by mechanism: reserve-then-reconcile stops at the cap; read-then-decrement overshoots by roughly your concurrency. Then repeat with the account balance raised above the trust threshold — on new-api and one-api that flips the mechanism (§3.3).
3. **Reconcile three numbers, not two.** For one hour of traffic, compare (a) the `usage` object your client received, (b) your gateway's own spend log and (c) the provider console, per token category **including cache-write**. Chapter 4 and the README both stop at (a) versus (c); [new-api#6144](https://github.com/QuantumNous/new-api/issues/6144) is invisible to that test because (a) is correct and (b) is not (§4).
4. **Kill the pod mid-stream, then read the ledger.** Start a long stream, `SIGKILL` the gateway, and check whether the spend row exists and whether the budget moved. §8 predicts *which* of the two you lose, and therefore who eats the error. Repeat with `SIGTERM`: on Bifrost the graceful path flushes, on LiteLLM it does not.
5. **Grep for the estimator before you trust the count.** No keys needed:
   ```bash
   # Kong OSS — the chars÷4 and ×1.8 estimators
   grep -n "strip(response) / 4" kong/llm/plugin/shared-filters/normalize-sse-chunk.lua
   grep -n "stream_mode\") and 1.8" kong/llm/plugin/shared-filters/normalize-request.lua
   # new-api — the per-family character weight table and the bypass around its own tokenizer
   grep -n "EstimateTokenByModel" service/usage_helpr.go service/token_estimator.go
   # one-api — which models get a real encoder, and what the rest fall back to
   grep -n "defaultTokenEncoder\|using encoder for" relay/adaptor/openai/token.go
   ```
6. **Look for the negative-input tell.** Query your spend log for any row where cache-read tokens exceed input tokens. Under Anthropic's exclusive semantics that shape is normal; under an inclusive assumption it is §7.2's sign error waiting to happen.
7. **Ask for the reconciliation, not the check.** The one vendor question that separates the mechanisms in §3.1: *"Show me the code path where the pre-call estimate is compared against the settled actual."* Five of the six trees read here have none.
8. **Confirm the pins yourself** — every commit in the appendix was re-confirmed this way on 2026-07-29:
   ```bash
   gh api repos/BerriAI/litellm/commits/c274cf321c5c35c629220a89bb497d15b56f870f --jq '.commit.committer.date'
   gh api repos/QuantumNous/new-api/issues/1103 --jq '{state,created_at,title}'
   ```

---

## 12. Where to go next

If you are choosing a gateway, start at [the requirements map](../README.md#the-requirements-map) and treat any vendor's "virtual keys ✅" — and the README glossary's own *Virtual keys* entry — as a question about §2.2's axis table rather than an answer — then ask §11 step 7. If you already run one, §11 steps 1 and 2 cost ten minutes between them and answer more than any datasheet.

In this handbook (the map is in [HANDBOOK.md](../HANDBOOK.md)): [chapter 1 — The Compatibility Surface](protocol-translation.md) owns the field-by-field usage mismatch this chapter prices; [chapter 4 — Anatomy of an AI Gateway](gateway-anatomy.md) is where stages 2 and 9 sit in the request path, and this chapter is those two stages at depth; [chapter 5 — Failover & reliability](failover-reliability.md) owns the mid-stream abort and the retry-billing question that §8 touches only at the edge; [chapter 6 — Caching economics](caching-economics.md) supplies the 1.25×/2×/0.1× multipliers that §7.3 depends on, and gains a failure mode from this pass — **changing a thinking configuration silently invalidates the prompt cache.** Anthropic, verbatim: *"The thinking configuration and the resolved `effort` level are rendered into the prompt itself, so changing any of them starts a new cache prefix. ... Treat any thinking or effort change as starting the cache over."* Per chapter 6's own arithmetic, a cache that writes and never hits is worse than no caching at all (below the 21.74% break-even), so **any router that varies effort per request is a cache-destruction mechanism** — a connection between the routing and caching chapters that neither currently names.

**Explicitly not established here, so nobody cites this chapter for it.** (a) Whether LiteLLM's multi-tier reservation can leave a *partial* reservation applied under a mid-loop process kill: by inspection the loop reserves counters one at a time with compensating release in an `except` block, and the cancel-path docstring describes the orphan class (*"Left alone it pins the spend counter above real spend and 429s subsequent requests until the counter's TTL expires"*) — but this was not run, and the effective runtime TTL on the spend-counter keys was not confirmed. **INCONCLUSIVE**, not an orphan window of any stated duration. (b) Bifrost's cross-node `baselines` semantics (§9). (c) Whether Gemini streams `usageMetadata` on every chunk cumulatively — widely repeated, but Google's primary reference defines the field only as *"Output only. Metadata on the generation requests' token usage"* and says nothing about streaming; every supporting source found was secondary, several of them relay-vendor doc mirrors this repo's own watch-list treats as unverified. **Any gateway's Gemini streaming metering rests on observed behaviour, not a contract, and is therefore free to change without notice.** (d) Whether DeepSeek's hit+miss counters sum to `prompt_tokens` (§7.1). (e) Whether omitting `include_usage` bills zero or bills an estimate (§11 step 1). (f) Anthropic's streaming docs page omits `usage` from both `message_start` and `message_delta` in its *thinking* example while including it in every other example on the page — recorded as a **documentation inconsistency**, most likely elision for brevity, and explicitly **not** a claim about runtime behaviour, since the SDK type requires `output_tokens` on `MessageDeltaUsage`.

---

## Appendix — every source this chapter relies on

**Source trees, read at pinned commits** (each SHA re-confirmed via `gh api repos/OWNER/REPO/commits/SHA` on 2026-07-29; committer dates as returned):

| Project | Commit (committer date) | Files read |
|---|---|---|
| BerriAI/litellm | [`c274cf321c5c35c629220a89bb497d15b56f870f`](https://github.com/BerriAI/litellm/tree/c274cf321c5c35c629220a89bb497d15b56f870f) (2026-07-29) | [`proxy/_types.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/_types.py) · [`proxy/auth/user_api_key_auth.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/auth/user_api_key_auth.py) · [`proxy/spend_tracking/budget_reservation.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/spend_tracking/budget_reservation.py) · [`proxy/proxy_server.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/proxy_server.py) · [`proxy/common_request_processing.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/common_request_processing.py) · [`proxy/db/db_spend_update_writer.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/db/db_spend_update_writer.py) · [`proxy/db/db_transaction_queue/redis_update_buffer.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/db/db_transaction_queue/redis_update_buffer.py) · [`caching/redis_cache.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/caching/redis_cache.py) · [`constants.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/constants.py) · [`litellm_core_utils/streaming_chunk_builder_utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/streaming_chunk_builder_utils.py) · [`litellm_core_utils/llm_cost_calc/utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/llm_cost_calc/utils.py) |
| QuantumNous/new-api | [`c27d1ef651c608dd8b9e60848a7e0f13a8619d9b`](https://github.com/QuantumNous/new-api/tree/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b) (2026-07-29) | [`model/token.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/token.go) · [`model/user.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/user.go) · [`model/utils.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/utils.go) · [`service/billing_session.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/billing_session.go) · [`service/billing.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/billing.go) · [`service/text_quota.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/text_quota.go) · [`service/token_estimator.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/token_estimator.go) · [`service/usage_helpr.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/usage_helpr.go) · [`controller/relay.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/controller/relay.go) · [`common/init.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/common/init.go) |
| songquanpeng/one-api | [`8df4a2670b98266bd287c698243fff327d9748cf`](https://github.com/songquanpeng/one-api/tree/8df4a2670b98266bd287c698243fff327d9748cf) (2025-02-21 — the newest commit on the repo) | [`relay/controller/helper.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/controller/helper.go) · [`relay/controller/text.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/controller/text.go) · [`model/user.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/user.go) · [`model/token.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/token.go) · [`model/cache.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/cache.go) · [`common/redis.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/common/redis.go) · [`relay/adaptor/openai/token.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/adaptor/openai/token.go) · [`relay/adaptor/openai/adaptor.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/adaptor/openai/adaptor.go) |
| maximhq/bifrost | [`39ba57350ce943160feef437eaf5cba52b0aedd5`](https://github.com/maximhq/bifrost/tree/39ba57350ce943160feef437eaf5cba52b0aedd5) (2026-07-29) | [`plugins/governance/store.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/store.go) · [`plugins/governance/tracker.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/tracker.go) · [`plugins/governance/main.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/main.go) · [`framework/modelcatalog/datasheet/cost.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/framework/modelcatalog/datasheet/cost.go) |
| Kong/kong | [`391ee48d3a68e8d0bbd0405ec1d02d75f768aa92`](https://github.com/Kong/kong/tree/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92) (2026-07-22; `kong/meta.lua` reports 3.10.0) | [`kong/llm/plugin/observability.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/observability.lua) · [`shared-filters/serialize-analytics.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/serialize-analytics.lua) · [`shared-filters/normalize-sse-chunk.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-sse-chunk.lua) · [`shared-filters/normalize-request.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-request.lua) · [`shared-filters/normalize-json-response.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-json-response.lua) · [`kong/llm/drivers/shared.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/drivers/shared.lua) |
| alibaba/higress | [`c8b82797c51a97faca46e2ae12990453f5026802`](https://github.com/alibaba/higress/tree/c8b82797c51a97faca46e2ae12990453f5026802) (2026-07-23) | [`extensions/ai-quota/main.go`](https://github.com/alibaba/higress/blob/c8b82797c51a97faca46e2ae12990453f5026802/plugins/wasm-go/extensions/ai-quota/main.go) · [`extensions/ai-token-ratelimit/main.go`](https://github.com/alibaba/higress/blob/c8b82797c51a97faca46e2ae12990453f5026802/plugins/wasm-go/extensions/ai-token-ratelimit/main.go) |
| higress-group/wasm-go | [`41d65dbb2f9e37e571cb2fdcfec38833b878623b`](https://github.com/higress-group/wasm-go/blob/41d65dbb2f9e37e571cb2fdcfec38833b878623b/pkg/tokenusage/tokenusage.go) (2025-11-03) **and** [`b573359becf82b5fd79fad6b323313f21917e84a`](https://github.com/higress-group/wasm-go/tree/b573359becf82b5fd79fad6b323313f21917e84a) (2025-08-21) | `pkg/tokenusage/tokenusage.go`. ⚠️ **Higress's token counting lives in a different repository from its plugins, and the two plugins pin different versions of it**: `ai-token-ratelimit/go.mod` → `41d65db`, `ai-quota/go.mod` → `b573359` |

**Vendor specifications, SDK types and docs:**

| Source | What it establishes here |
|---|---|
| [openai/openai-openapi @`db14b6e`](https://github.com/openai/openai-openapi/blob/db14b6e1712aaf5265cf5a6871adff7a9c61d31c/openapi.yaml) (2026-07-28) | `ChatCompletionStreamOptions.include_usage` and its interruption hedge, verbatim; `CompletionUsage` incl. `prompt_tokens_details.cache_write_tokens` and the `rejected_prediction_tokens` sentence; `ResponseUsage` required fields; the Organization Usage API example whose 400+100+500=1000 partition §7.1 derives |
| [anthropics/anthropic-sdk-python @`f5c30d0`](https://github.com/anthropics/anthropic-sdk-python/tree/f5c30d0490fb7bcd8e0b65d8d8e63c0e7d1bfe59/src/anthropic/types) (2026-07-28) | `usage.py` (`inference_geo`, `service_tier`, `output_tokens_details`) · `message_delta_usage.py` (only `output_tokens` required) · `output_tokens_details.py` (`thinking_tokens` and its two hedges) · `cache_creation.py` (required 5m/1h ints under an Optional parent) · `server_tool_usage.py` |
| [Anthropic — streaming](https://platform.claude.com/docs/en/build-with-claude/streaming) · [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) (all retrieved 2026-07-29) | the cumulative-usage Warning; the basic and web-search SSE examples behind §5.1's 3.99×; the `total_input_tokens` identity and the 1.25×/2×/0.1× multipliers; billing for unseen thinking; current-turn vs prior-turn price class; thinking-config cache invalidation |
| [googleapis/python-genai @`fc282b3`](https://github.com/googleapis/python-genai/blob/fc282b359a7e9e16219587266c94d2bdc506164a/google/genai/types.py) (2026-07-28) · [Gemini generateContent reference](https://ai.google.dev/api/generate-content) · [Gemini thinking](https://ai.google.dev/gemini-api/docs/thinking) (retrieved 2026-07-29) | the four-addend `total_token_count`; `prompt_token_count` including cached content; `tool_use_prompt_token_count`; `traffic_type`; *"response pricing is the sum of output tokens and thinking tokens"*; **and the documented silence on streaming usage semantics** |
| [DeepSeek — KV cache](https://api-docs.deepseek.com/guides/kv_cache) · [token usage](https://api-docs.deepseek.com/quick_start/token_usage) (retrieved 2026-07-29) | `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`, and the absence of any stated summation identity |
| [Portkey — create virtual key](https://portkey.ai/docs/api-reference/admin-api/control-plane/virtual-keys/create-virtual-key) · [upgrade to Model Catalog](https://portkey.ai/docs/support/upgrade-to-model-catalog) · [virtual keys](https://portkey.ai/docs/product/ai-gateway/virtual-keys) (retrieved 2026-07-29) | the verbatim "Deprecated" notice, the upstream-credential request body, and the Virtual Keys → AI Providers / Model Catalog migration |
| [Bifrost — governance](https://docs.getbifrost.ai/features/governance) (retrieved 2026-07-29) | VK budgets and reset durations; *"(VK-level only)"* rate limits; exclusive team-or-customer attachment; UTC calendar-boundary resets |

**GitHub issues and PRs** (each fetched via `gh api` on 2026-07-29 and confirmed to exist, to carry the state shown, and to say what it is cited for):

| Item | State · created | Cited for |
|---|---|---|
| [litellm#34875](https://github.com/BerriAI/litellm/issues/34875) | **open** · 2026-07-28 | 80.7% of 304,148 streaming rows at $0 — the success-handler race (§10.1) |
| [litellm#33772](https://github.com/BerriAI/litellm/issues/33772) | **open** · 2026-07-17 | OpenAI `cache_write_tokens` dropped from cost calculation; reporter: spend *"well below"* the provider invoice (§7.1) |
| [litellm#26807](https://github.com/BerriAI/litellm/issues/26807) | **open** · 2026-04-29 | Cached tokens at full input rate in the custom-pricing path — 1.67× over (§10.2) |
| [litellm#18599](https://github.com/BerriAI/litellm/issues/18599) · [PR #18607](https://github.com/BerriAI/litellm/pull/18607) | closed · 2026-01-03 · **merged** 2026-01-03 | Reasoning priced instead of total completion — 7.02% under (§10.2) |
| [litellm#30488](https://github.com/BerriAI/litellm/pull/30488) | **merged** 2026-06-17 | Perplexity reasoning double-billing — 2.17× over; self-described sibling of #18607 (§10.2) |
| [litellm#28735](https://github.com/BerriAI/litellm/issues/28735) · [#8450](https://github.com/BerriAI/litellm/issues/8450) · [PR #8751](https://github.com/BerriAI/litellm/pull/8751) | **open** · closed `not_planned` · closed `merged=false` | Synthetic usage chunk violates `choices: []` — reported twice, fixed zero times (§5.3) |
| [litellm#22280](https://github.com/BerriAI/litellm/issues/22280) | closed `not_planned` 2026-06-15 · 2026-02-27 | The enforce-streamed-usage request, auto-closed as stale (§5.3, §11 step 1) |
| [litellm#34850](https://github.com/BerriAI/litellm/pull/34850) · [#27459](https://github.com/BerriAI/litellm/issues/27459) · [#28553](https://github.com/BerriAI/litellm/issues/28553) | all **open** | Regional geo uplift on cached tokens (§10.5); Chat→Responses usage cost dropped; Azure Responses rejecting `stream_options.include_usage` (§5.1) |
| [litellm#34732](https://github.com/BerriAI/litellm/issues/34732) · [#34733](https://github.com/BerriAI/litellm/issues/34733) · [#33325](https://github.com/BerriAI/litellm/issues/33325) · [#34101](https://github.com/BerriAI/litellm/issues/34101) | all **open** | Budget races: session bypass, window-reset overwrite, pod-local spend across replicas, project budgets missing from the reservation (§3.1, §9) |
| [litellm#34805](https://github.com/BerriAI/litellm/issues/34805) · [#34820](https://github.com/BerriAI/litellm/issues/34820) | both **open** | Spend buffers dropped on shutdown; rows popped before the DB write is awaited (§8) |
| [new-api#1103](https://github.com/QuantumNous/new-api/issues/1103) | **open** · 2025-05-25 | Gemini reasoning unbilled — 89.84% of output tokens (§10.3) |
| [new-api#5003](https://github.com/QuantumNous/new-api/issues/5003) · [#5005](https://github.com/QuantumNous/new-api/issues/5005) | closed `duplicate` · closed `not_planned` · both 2026-05-21 | Negative input tokens from double-subtracting cache reads (§7.2) |
| [new-api#6353](https://github.com/QuantumNous/new-api/issues/6353) | **open** · 2026-07-20 | Claude cache-write tokens unbilled when the 5m/1h split is absent (§7.3) |
| [new-api#2608](https://github.com/QuantumNous/new-api/issues/2608) | **open** · 2026-01-08 | Integer quota truncation and force-to-1 rounding (§10.4) |
| [new-api#4429](https://github.com/QuantumNous/new-api/issues/4429) · [#6144](https://github.com/QuantumNous/new-api/issues/6144) | both **open** | Pre-deduct leak under the trust bypass (§3.3); billing on a corrupted usage copy (§4) |
| [one-api#412](https://github.com/songquanpeng/one-api/pull/412) · [#925](https://github.com/songquanpeng/one-api/pull/925) | **open** `merged=false` · closed 2026-05-25 `merged=false` | Function-call fee evasion, unmerged since 2023-08-13 (§10.6); the two-level pre-charge fix closed after 2.4 years (§3.3) |
| [Kong/kong#14816](https://github.com/Kong/kong/issues/14816) | **open** · 2026-01-15 | `llm_total_tokens_count` derived rather than stored, discarding hidden reasoning tokens (§6.2) |

**Our arithmetic** (all reproducible from the figures printed beside each): the 3.99× server-tool ratio (§5.1); the 400+100+500=1000 OpenAI partition (§7.1); the −0.008907 vs 0.064053 reproduction (§7.2); 80.74% (§10.1); 1.67×, 7.02% (§10.2); 10.16% billed / 89.84% unbilled (§10.3); 98.7% cached (§4). Written and checked 2026-07-29.

**Repo files:** [README.md](../README.md) glossary rows for *Virtual keys* and *Thinking / reasoning tokens* · [HANDBOOK.md](../HANDBOOK.md) chapter map · [BENCHMARKS.md](../BENCHMARKS.md) Part 6 token-type criterion · [data/gateways_eval.json](../data/gateways_eval.json) (`as_of` 2026-07-28, the one-api entry) · [chapter 1](protocol-translation.md) §2 · [chapter 4](gateway-anatomy.md) §2.1 stages 2, 9 and 10, §3.3, §3.5 and §4 · [chapter 6](caching-economics.md) §2.1 and §3.1.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every claim above is dated and linked to a spec, a commit, an issue or a re-runnable command, so you can re-check it. If you settle one of the six open questions in §12, that's a PR we want.*
