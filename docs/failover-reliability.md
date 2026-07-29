# Failover & Reliability — what actually happens when a provider fails mid-request

*Last updated 2026-07-29 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

**Languages:** English · [简体中文](failover-reliability.zh-CN.md)


> 📊 **Key numbers** · Six open-source gateways, read at pinned commits on **2026-07-29**: **exactly one of the six re-issues a failed LLM request **at the LLM layer** by default.** Bifrost ships `DefaultMaxRetries = 0`, Portkey OSS `attempts: retry?.attempts ?? 0`, new-api `RetryTimes = 0`; Envoy AI Gateway writes no retry *count or trigger* of its own (only `PerTryIdleTimeout`); Kong OSS has no AI-level retry at all. Only **LiteLLM** defaults non-zero — `num_retries` falls through to `openai.DEFAULT_MAX_RETRIES` = **2**. **Exactly one of the six can fail over *after* the first token is on the wire** — also LiteLLM, on by default, by re-prompting a fallback model with the partial text as a continuation. For four of the other five, the honest answer to "what does the client see when the upstream dies mid-stream?" is *a truncated stream that looks successful*: Portkey OSS writes the error to `console.error` and closes the writer; new-api's stream handler returns `usage, nil` unconditionally. Cooldowns are shorter and rarer than the word "circuit breaker" implies: **only two of the six remember a failure after the request ends**, LiteLLM's default window is **5 seconds**, and new-api's is permanent but ships **disabled**. And none of it is idempotent: **no provider documents an idempotency key for inference**, and neither the OpenAI nor the Anthropic Python SDK ever puts one on the wire — so every retry, at every layer, is a fresh billable generation.

[Chapter 4](gateway-anatomy.md) mapped the whole request path and marked stage 7 — provider call, retry, failover — as the stage it could only partially answer, leaving "does any gateway double-bill a retried request?" as an explicit open hypothesis. This chapter is stage 7 and the streaming half of stage 8 at full depth: what triggers a retry versus a failover, what bytes actually go back on the wire, what (if anything) remembers a failure after the request ends, what a client sees when the upstream dies after the first token, whether a retry can be billed twice, what the three providers' 429 contracts actually say, why health checks lie, and — last, because it's the part vendors skip — the arithmetic of putting one more hop in front of every request you make.

Sourcing convention, same as chapters 1 and 4: source reads are pinned to a commit and cited by file and line, vendor documentation is attributed and dated, GitHub issues were verified to exist via the API, arithmetic and inference are marked as ours, and figures taken from this repo's own files are marked *repo-sourced*. Where a claim is not independently confirmed, it says so in place. Six of the seven gateways from chapter 4 are covered here — **Higress was not read this pass** and is absent from every table below rather than guessed at.

---

## 1. The concept in 60 seconds

Two words get used interchangeably and mean different things:

- **Retry** — send it again. Same intent, possibly the same upstream.
- **Failover** — send it *somewhere else*. Different deployment, different provider, possibly a different wire protocol.

In an ordinary API gateway these are separate layers. In an LLM gateway they collapse, because the thing you retry is not a byte-identical upstream request — it's a client request that has to be *re-routed and re-translated* before it can be sent anywhere. That single implementation choice decides whether cross-provider failover is even possible, and it's the reason the six gateways below give six different answers.

Four questions determine everything else, and none of them appears in a feature matrix:

1. **What triggers a retry, and what triggers a failover?** (§2)
2. **What actually goes back on the wire — the original client request, or the already-translated upstream request?** (§3)
3. **Does anything remember the failure after the request ends?** (§4)
4. **What happens after the first token?** (§5)

Question 4 is the one that matters most and is documented least, because its failure mode is the only one the client cannot detect: a stream that stops early looks, on the wire, exactly like a stream that finished.

---

## 2. Retry within a group vs failover across groups

### 2.1 Six gateways, six answers — and five of them do zero LLM-level retrying out of the box

| Gateway | What triggers a retry | What triggers a failover | Default retry attempts | Where the two layers live |
|---|---|---|---|---|
| **LiteLLM** `c274cf3` | 408 / 409 / 429 / ≥500 (`litellm._should_retry`, `utils.py:6339`) plus connection errors; a configured `retry_policy` sets `_retry_policy_applies` and bypasses the trigger test entirely | `num_retries` exhausted → the `fallbacks` list; **or immediately**, for `ContextWindowExceededError` / `ContentPolicyViolationError` when the matching fallback list is configured | **2** — `num_retries` falls through to `openai.DEFAULT_MAX_RETRIES` (`router.py:601-606`); `max_fallbacks` = 5 (`ROUTER_MAX_FALLBACKS`) | `async_function_with_fallbacks` (`router.py:6398`) wraps `async_function_with_retries` (`:6493`) |
| **Portkey OSS** `669825c` | HTTP status only: `RETRY_STATUS_CODES = [429, 500, 502, 503, 504]`, or exactly the operator's `retry.onStatusCodes` | `strategy.mode: fallback` advances to the next target on any non-ok status (or on exactly `strategy.onStatusCodes` when set) | **0** — `attempts: retry?.attempts ?? 0` (`requestContext.ts:148`) | **three** nested layers: `tryTargetsRecursively` (`:476`) → `tryPost` (`:288`) → `recursiveAfterRequestHookHandler` (`:1182`) → `retryRequest` |
| **Bifrost** `e6952b6` | 500/502/503/504 + network errors → same credential; 401/402/403/429 → **rotate credential** | retry budget spent → walk the configured `Fallbacks`; each hop gets its own full retry budget | **0** — `DefaultMaxRetries = 0` (`core/schemas/provider.go:13`) | `executeRequestWithRetries` (`bifrost.go:5818`) inside `handleRequest` (`:5000`) |
| **new-api** `c27d1ef` | very broad: 1xx, 3xx, 401–407, 409–499, 500–503, 505–523, 525–599. Only **504 and 524** are hard-excluded (the ranges are operator-editable; 400, 408 and 2xx simply fall outside the shipped defaults) | none separately — the loop re-picks the channel per attempt, so **every retry *is* a failover** | **0** — `RetryTimes = 0` (`common/constants.go:133`); loop bound is `<=`, so N means N+1 total attempts | one loop, `controller/relay.go:194` |
| **Envoy AI Gateway** `6722cca` | whatever the operator's Envoy Gateway `BackendTrafficPolicy` says | `priority: 0 / priority: 1` on `backendRefs`, arbitrated by that same policy | **none of its own** — the only `RetryPolicy` field the control plane writes is `PerTryIdleTimeout` | delegated entirely to Envoy Gateway |
| **Kong OSS** `391ee48` | no AI-level retry exists in the OSS tree | none — `ai-proxy-advanced`, which owns `config.balancer` / `failover_criteria` / `max_fails`, is `tier: ai_gateway_enterprise` and absent from the tree | transport only: `service.retries` = 5, under nginx's default `proxy_next_upstream error timeout` | the nginx balancer, not a plugin |

**Footnote on Kong, so the heading and the table agree:** Kong OSS *does* carry a non-zero retry default — `services.lua:33-34`, `retries = 5` — but it is a transport-level balancer retry, not an LLM-level one, and §3 shows why it almost never fires for a chat completion. "Five of six do zero LLM-level retrying" is exact.

### 2.2 The nesting, gateway by gateway

**LiteLLM** — the chain at `c274cf3` is `function_with_fallbacks` (`router.py:6775`, a three-line sync shim over `run_async_function`) → `async_function_with_fallbacks` (`:6398`) → `async_function_with_retries` (`:6493`) → `make_call` (`:6672`) → `_acompletion`. The decision of *whether* to retry lives in `should_retry_this_error` (`:6711`), which **raises** — i.e. blocks the retry and hands the error up to the fallback layer — on seven distinct conditions, including `_num_healthy_deployments <= 0`, a `RateLimitError` with no healthy deployments left, and an `AuthenticationError` when the group has one deployment. That is the mechanism by which "retry" gracefully becomes "fail over" without anyone configuring it.

> 📌 **Naming, so the greps line up.** The retry driver is `async_function_with_retries`; there is no sync twin (the sync `function_with_fallbacks` wrapper does exist). Verified two ways on 2026-07-29: GitHub code search for `"def function_with_retries" repo:BerriAI/litellm` returns `total_count: 0`, and `grep -n "def .*function_with_retries" router.py` on the raw file at `c274cf3` returns exactly one line, `6493: async def async_function_with_retries`. [Chapter 4](gateway-anatomy.md) originally printed the sync names and was corrected in `515b1b8` while this chapter was being drafted.

**Portkey OSS** — chapter 4 describes two nested layers. There are **three**. `tryTargetsRecursively` (`handlerUtils.ts:476`) switches on `strategy.mode` over `{loadbalance, fallback, single, conditional}` and is the *only* layer that can change provider; inside it `tryPost` (`:288`) does translation and cache; inside that `recursiveAfterRequestHookHandler` (`:1182`) owns `retryRequest`. Note what `loadbalance` does **not** do: it picks one target by weight and does not iterate on failure. Weighted load balancing in Portkey OSS is not failover.

**Bifrost** — two clean loops. `executeRequestWithRetries` runs inside one provider; `handleRequest` walks `Fallbacks` only after that budget is spent. Two behaviours worth writing down: a fallback is **skipped entirely** when the error carries `AllowFallbacks: false` or is a `RequestCancelled` (`shouldTryFallbacks`, `bifrost.go:4854`), and when every fallback has failed the caller gets back **the primary provider's error**, not the last one (`:5133`). Debugging a fallback chain from the error you received is therefore misleading by design.

**new-api** — one loop, no separate failover layer, and one important exception: if the request pinned a channel (`specific_channel_id` in context), `shouldRetry` returns false. Pinned traffic gets no failover at all.

### 2.3 Two traps in the retry layer that are in nobody's documentation

**Portkey OSS: a guardrail verdict can burn your upstream retry budget.** In `recursiveAfterRequestHookHandler` (`handlerUtils.ts:1249-1281`), `retryRequest` returns, `responseHandler` back-translates, `afterRequestHookHandler` runs the **output guardrails and can change the status** — and only *then* is `isRetriableStatusCode` computed, against that post-hook response. If it matches and budget remains, the handler recurses into a fresh `retryRequest`. So a guardrail that rejects a perfectly healthy provider response can send the gateway back to the provider to generate another one, at full price. Separately, the `Retry-After` path is bounded globally: `MAX_RETRY_LIMIT_MS = 60 * 1000`, decremented per honoured wait, with headers probed in the order `retry-after-ms`, `x-ms-retry-after-ms`, `retry-after` — and if a provider asks for longer than the remaining budget, Portkey sets `retrySkipped = true` and gives up rather than waiting.

**Envoy AI Gateway: with no `BackendTrafficPolicy` attached, there is no failover at all.** The AI Gateway control plane never writes `numRetries`, `retryOn` or retriable status codes; the shipped example (`examples/provider_fallback/fallback.yaml`) asks the *operator* for `numAttemptsPerPriority: 1`, `numRetries: 5`, `perRetry.backOff` 100 ms→10 s, `perRetry.timeout 30s`, `retryOn.httpStatusCodes: [500]`, `retryOn.triggers: [connect-failure, retriable-status-codes]`. Note what the project's own comment says `numAttemptsPerPriority: 1` is for: *"This ensures that only one attempt is made per priority. For example, if the primary backend fails, it will not retry on the same backend."* That is a good default — and it means the failover behaviour you get is entirely a property of a YAML file the gateway does not ship.

---

## 3. What actually goes back on the wire

This is the question that decides whether cross-format failover is possible, and it splits the six cleanly.

| Gateway | What is sent on attempt 2 | Cross-wire-format failover? |
|---|---|---|
| **LiteLLM** | The **original client request**, fully re-routed: `make_call` → `_acompletion` → `async_get_available_deployment` runs again per attempt, with cooled-down deployments filtered out by `_filter_cooldown_deployments` | ✅ — and note the consequence: intra-group "retry" already lands on a different deployment, so LiteLLM achieves cross-deployment failover before `fallbacks` is ever consulted |
| **new-api** | The **original client body**, replayed from `common.GetBodyStorage(c)` and re-converted for the newly selected channel's format | ✅ |
| **Envoy AI Gateway** | The **original body**, re-translated per attempt: `forceBodyMutation := u.onRetry() \|\| u.parent.forceBodyMutation`, against `originalRequestBodyRaw`; upstream auth re-runs too | ✅ — this is precisely what makes it native |
| **Bifrost** | The **same logical request** through the same provider adapter, with a rotated credential on per-key failures | ⚠️ only at the fallback layer (`prepareFallbackRequest` clones onto a new provider/model), never at the retry layer |
| **Kong OSS** | `MetaPlugin:retry` re-runs `STAGES.REQ_TRANSFORMATION` on a balancer try | ❌ — each driver calls `kong.service.set_target(host, port)` against one DNS-resolved host, so there is no second provider to reach |
| **Portkey OSS** (retry layer) | The **already-translated**, provider-specific `fetchOptions` replayed byte-for-byte to the same URL — the body was built by `transformToProviderRequestAndSave` *before* the retry handler ever ran | ❌ at the retry layer. ✅ only when `tryTargetsRecursively` moves to a different target, which re-enters `tryPost` and re-translates |

Two consequences worth stating plainly. First, a gateway whose retry replays translated bytes cannot fail a request over to a differently-shaped provider without climbing to an outer layer — which is why Portkey OSS's `retry` and `strategy` settings are not substitutes for each other. Second, re-translating per attempt means every attempt re-runs the [five translation failure modes](protocol-translation.md#3-the-five-failure-modes) from chapter 1: a `cache_control` breakpoint that survives attempt 1 has to survive attempt 2 as well, on a possibly different adapter.

> ⚠️ **A Kong code fact whose runtime consequence is unconfirmed.** `kong/llm/plugin/base.lua:154-161` initialises every plugin with `balancer_retry_enabled = false` and `:218` defines a method `enable_balancer_retry()` to flip it. But `MetaPlugin:access` (`:78`) tests `if sub_plugin.enable_balancer_retry then` — the **method**, not the flag. Because `sub_plugin` inherits `__index = _M` and the method is a function, that expression is truthy for every plugin built on this base. Read literally, the retry callback is registered unconditionally and `balancer_retry_enabled` is written but never read. **We did not observe this at runtime; treat the code shape as verified and the impact as inferred.** It is a good candidate for a five-minute reproduction by someone with a Kong test rig.

---

## 4. Cooldowns and circuit breakers

### 4.1 Only two of the six remember a failure after the request ends — and one of those ships disabled

| Gateway | Does a failure outlive the request? | Trigger | Window |
|---|---|---|---|
| **LiteLLM** | ✅ a cooldown cache the router filters deployments against | any 429 in a **multi**-deployment group; >50% failures over ≥5 requests in the current minute; 100% failures over ≥1000 requests; any status `_should_retry()` rejects | **5 seconds** — `DEFAULT_COOLDOWN_TIME_SECONDS = 5`, assigned at `router.py:589` |
| **new-api** | ✅ and it never expires — a DB status flip to `ChannelStatusAutoDisabled` | HTTP **401** (`AutomaticDisableStatusCodeRanges = [{401,401}]`) or an Aho-Corasick keyword match on the error body | **no TTL.** Re-enable needs `AutomaticEnableChannelEnabled` *plus* a passing channel test — and `AutomaticDisableChannelEnabled` defaults to **`false`**, so out of the box this never fires |
| **Bifrost** | ❌ `deadKeyIDs` / `usedKeyIDs` live for the duration of one request only | 401/402/403 → dead key (never retried in this request); 429 → used key (reset once the pool is exhausted) | n/a — the real circuit breaker is **Enterprise**; `plugins/` at `e6952b6` contains no `circuitbreaker` |
| **Portkey OSS** | ❌ the hook exists, the implementation doesn't | `handleCircuitBreakerResponse` is invoked through optional chaining and **nothing in the OSS tree ever sets it**; nothing ever sets `target.isOpen`, which the target filter reads | n/a |
| **Kong OSS** | ❌ | `max_fails` / `fail_timeout` live in `ai-proxy-advanced` (Enterprise). Kong's own reference documents the default as `max_fails: 0` — *"The zero value disables the circuit breaker"* | n/a |
| **Envoy AI Gateway** | ❌ none of its own | Envoy outlier detection, **if** the operator configures it in Envoy Gateway | n/a |

### 4.2 Three things this table is really saying

**(a) "Circuit breaker" in this category usually means something much weaker than in the Hystrix sense.** Three of six ship nothing. One ships a call site with no implementation — the same shape as the `preRequestValidator` gap chapter 4 documented for Portkey's budget layer: **the OSS data plane has the hook, the hosted product has the state.** One ships an on-by-default 5-second window. One ships a permanent kill switch that is off by default.

**(b) LiteLLM's defaults contain a deliberate exemption that surprises people.** Single-deployment model groups are explicitly excluded from *both* the 429 rule and the error-rate rule (`is_single_deployment_model_group`). The reasoning is sound — cooling down your only deployment just fails the next request faster — but the exemption is narrower than it looks. `_should_cooldown_deployment` has four default-path branches at `c274cf3` and only two carry the guard (the 429 rule, line 225, and the >50%-error-rate rule, line 233). The other two still fire on a single deployment: a **100% failure rate over ≥1,000 requests in the minute** (line 227 — the constant is literally named `SINGLE_DEPLOYMENT_TRAFFIC_FAILURE_THRESHOLD`), and **any status `litellm._should_retry()` rejects**, in practice 401 and 404 (line 238). So the two rules that would catch a *degrading* provider are off; only an auth/not-found error or a thousand-request wipeout still registers.

**(c) `allowed_fails` is effectively dead code at default settings.** `should_cooldown_based_on_allowed_fails_policy` only runs when an `allowed_fails_policy` is set, or when `Router.allowed_fails` differs from the module default `litellm.allowed_fails = 3`. Out of the box the percentage rule governs. If you have been tuning `allowed_fails` and seeing nothing change, that is why.

---

## 5. Mid-stream — what the client sees after the first token

### 5.1 One gateway of the six can fail over after the first chunk; one can retry only on the first chunk; four cannot act at all

| Gateway | Upstream dies after chunk N | What the client observes | Retried or failed over? |
|---|---|---|---|
| **LiteLLM** | `_handle_stream_fallback_error` raises `MidStreamFallbackError(generated_content=self.response_uptil_now, is_pre_first_chunk=not self.sent_first_chunk)` | the stream **continues**, produced by a different model | ✅ **on by default** — every `CustomStreamWrapper` is wrapped in `_acompletion_streaming_iterator`. Exception: any mapped 4xx **except 429** re-raises instead of falling back |
| **Bifrost** | terminal once `tryStreamRequest` has handed back its channel | truncated | ⚠️ **first chunk only** — an error embedded in the first SSE frame retries and falls over; anything later does not |
| **Portkey OSS** | `catch (error) { console.error('Error during stream processing:', …) } finally { await writer.close() }` | a **truncated SSE stream that looks successful** — no error chunk, no status change | ❌ the retry/fallback machinery cannot see it: the response object was returned when the fetch resolved on headers |
| **new-api** | `StreamScannerHandler` has no error return; scanner failures are logged and swallowed; `OaiStreamHandler` ends `return usage, nil` | truncated; the request settles through the normal `PostTextConsumeQuota` path on whatever partial usage accumulated | ❌ — with no error to propagate, the retry loop is never re-entered |
| **Kong OSS** | nginx, verbatim: *"if an error or timeout occurs in the middle of the transferring of a response, fixing this is impossible"* | truncated | ❌ by construction |
| **Envoy AI Gateway** | Envoy router docs, verbatim: *"This timeout only applies before any part of the response is sent to the downstream, which normally happens after the upstream has sent response headers."* | truncated | ❌ by construction. Its one streaming control, `streamIdleTimeout` → `RetryPolicy.PerTryIdleTimeout`, **bounds** an idle stream; it does not resume one |

LiteLLM's continuation path deserves the detail, because it is the only place in this category where someone actually solved the problem rather than documenting it away. On a mid-stream failure the router rebuilds the partial response with `stream_chunk_builder`, then — when content was already generated — rewrites `messages` to the original turns *plus* a system message ending `"Your response should be in continuation of this text: "` and an assistant message carrying the partial with `prefix: True`, and re-enters the fallback path. If nothing had been generated yet it replays the original messages verbatim. Fallback usage is merged into the resumed stream, and a `finally` block with `anyio.CancelScope(shield=True)` closes the dead upstream. **This is a re-prompt, not a resume** — you pay input tokens again on the fallback model, and the continuation is a different model's text glued to the first model's prefix.

### 5.2 Why nobody else can do it: the protocol says the partial is gone

- **The SSE spec discards it.** WHATWG HTML, verbatim: *"Once the end of the file is reached, any pending data must be discarded. (If the file ends in the middle of an event, before the final empty line, the incomplete event is not dispatched.)"*
- **The spec's own resume mechanism exists and is dead code in practice.** SSE defines `Last-Event-ID` plus the `id:` and `retry:` fields. Both the OpenAI and Anthropic Python SDKs *parse* `id:` into `_last_event_id` and expose `ServerSentEvent.retry` — and neither ever emits a `Last-Event-ID` request header (0 code-search hits for the literal string in either repo, 2026-07-29). The reconnection half of the contract is parsed and thrown away.
- **A status-code-keyed retry layer is structurally blind to Anthropic's mid-stream errors.** Anthropic's errors page, verbatim: *"When receiving a streaming response over server-sent events (SSE), an error can occur after the API returns a 200 response. In that case, error handling doesn't follow these standard mechanisms."* The wire shape is `event: error` / `data: {"type":"error","error":{"type":"overloaded_error",…}}` — an `overloaded_error` that would be an HTTP 529 outside a stream. Every gateway in §2 whose retry trigger is an HTTP status will see a 200.
- **Real server-side resume exists on exactly one provider, on exactly one API surface.** OpenAI's Responses API in background mode: track the `sequence_number` cursor and resume with `GET /v1/responses/{id}?stream=true&starting_after=42`. OpenAI's own TypeScript sample carries the comment *"SDK support coming soon"*, and the guide notes time-to-first-token is higher for background responses.
- **Anthropic documents a manual recovery — and changed it at Claude 4.6.** For 4.5 and earlier you construct a continuation request placing the partial in an **assistant** message; for 4.6 and later you *"add a user message that instructs the model to continue from where it left off"*, because those models reject assistant prefill (`"This model does not support assistant message prefill"`). Tool-use and extended-thinking blocks *"cannot be partially recovered."* **A gateway that hard-codes the pre-4.6 prefill recovery now generates a 400 on 4.6+ models** — and LiteLLM's continuation path in §5.1 is exactly the pre-4.6 shape, `{'role':'assistant', 'content': e.generated_content, 'prefix': True}`. Whether LiteLLM's adapters rewrite that for 4.6+ targets was not read this pass; if you rely on mid-stream fallback against a 4.6-class model, test it before trusting it.

### 5.3 The metering hole underneath all of this

A mid-stream failure doesn't only lose text — it usually loses the numbers, which is why §6 and this section are the same problem:

- **Anthropic's streaming usage is cumulative and arrives late.** The docs warn that *"the token counts shown in the `usage` field of the `message_delta` event are cumulative"*, and `message_delta` is step 3 of 4 — after every content block. A client (or gateway) that dies during `content_block_delta`, which is the long part, has never seen a usage frame.
- **`message_start` carries a usage object, but a tiny one.** Anthropic's three worked examples show `"output_tokens"` of `1`, `2` and `3` respectively. Chapter 4 §3.5 quotes LiteLLM's source describing this as a fixed placeholder of `1` that a truthiness-checked fallback then fails to override. Anthropic's own docs show the value **varies** — so a gateway special-casing the literal `1` is fragile in both directions.
- **OpenAI gives a naive client no usage at all.** Chat Completions streaming emits none unless the caller sets `stream_options: {"include_usage": true}` — the documented reason a gateway proxying an unmodified client has nothing to meter and falls back to an estimator (Kong OSS's `chars ÷ 4`, new-api's character-class weight table — both catalogued in chapter 4 §3.5).

Combine that with Anthropic's disconnect-billing clause in §6.2 and the shape is stark: **on a mid-stream abort the provider bills you and the gateway usually can't tell you how much.**

---

## 6. Retry idempotency and double-billing

### 6.1 The protocol layer offers no protection at all

| Layer | Idempotency guarantee for inference | Evidence |
|---|---|---|
| **OpenAI API** | ❌ none | The only OpenAI-documented `Idempotency-Key` is in the **Agentic Commerce Protocol** (merchant endpoints, `idempotency_conflict` / HTTP 409). Nothing on `/v1/responses` or `/v1/chat/completions` |
| **Anthropic API** | ❌ none | Messages offers no key; the 409 `conflict_error` is about resource state; the Batches API dedupes only via `custom_id` **within one batch** |
| **Google Gemini** | ❌ none | no `Idempotency-Key` / `idempotency_key` request-header plumbing in `google/genai/_api_client.py` @`fc282b3` — the repo's single `idempotency` hit is a usage-header unit test, unrelated to request replay |
| **openai-python / anthropic-sdk-python** | ❌ generated, never sent | Each `_base_client.py` declares `_idempotency_header: str \| None`, sets it to `None` in `__init__`, and generates `stainless-python-retry-<uuid4>` per non-GET request. The write is gated on `if idempotency_header and options.idempotency_key and …` — which can never fire, because the attribute is never reassigned. Same dead pattern in openai-node and anthropic-sdk-typescript |

**So every retry — SDK, gateway or human — is a fresh billable generation.** Chapter 4 filed "whether any gateway double-bills a retried request" as an open hypothesis. Half of it now has an answer: at the protocol layer, double *generation* on retry is not preventable, by anyone, today.

### 6.2 What the providers say about paying for work you didn't receive

- **Anthropic, and this is the strongest receipt in this chapter** — billing FAQ, verbatim: *"In general, failed requests are not charged, and you will only be billed for successful API calls and completed tasks. However you will be charged if your client disconnects or times out in the middle of an API call that was on track to be successful."* Sourcing tier matters: this is a **support-centre article**, not the API reference, which is silent. It settles the mid-stream-abort question chapter 4 §3.3 could only argue from gateway-side issues: [litellm#14457](https://github.com/BerriAI/litellm/issues/14457) (usage lost on client disconnect) is eating real cost, and [new-api#4463](https://github.com/QuantumNous/new-api/issues/4463)'s deliberate kill-the-upstream choice is buying real cost back.
- **OpenAI documents the observability consequence, not the billing one** — the `chat.completion.chunk.usage` docstring warns *"If the stream is interrupted or cancelled, you may not receive the final usage chunk"*, and usage is absent entirely unless the caller sets `stream_options: {"include_usage": true}`. Whether OpenAI bills the partial is **NOT DOCUMENTED** anywhere we could find. Treat community claims either way as folklore.
- **Google documents only the 400/500 case** — *"If your request fails with a 400 or 500 error, you won't be charged for the tokens used. However, the request will still count against your quota."* Mid-stream client disconnect: **NOT DOCUMENTED**.

### 6.3 The one gateway with an explicit position, quoted in full

> ⚠️ **This corrects chapter 4.** [gateway-anatomy.md](gateway-anatomy.md) §2.1 cites Bifrost's `RequestID`+`AttemptNumber` dedup as the fix for "double-billing on attempts", which reads as protection from paying for retries. The full source comment at `plugins/governance/tracker.go` @`e6952b6` says the opposite: *"Billing is deduped on RequestID+AttemptNumber so each token-consuming attempt bills at most once **while distinct attempts each bill**."* Bifrost deliberately bills every attempt. The dedup prevents double-billing **one physical provider call** — which is the correct design, since the provider charged for each attempt too, and is exactly why it belongs in a reliability chapter: *your retry budget is a spend multiplier.*

**Still INCONCLUSIVE, and stated as such:** whether LiteLLM, Kong OSS or new-api bills a *client* twice for a single physical provider call on retry. That needs a black-box spend-delta measurement against a fault-injecting upstream, not a source read. Nobody should cite this chapter for it.

---

## 7. The 429 math — three providers, three incompatible contracts

Rate limits are not a corner case. Repo-sourced (README, Datadog production telemetry across 1,000+ orgs, March 2026): rate-limit errors were **~⅓ of all LLM errors — nearly 8.4 million** in a single month. *Re-verifiability caveat we owe the reader:* that report is a live marketing page with no version or dated snapshot, and it carries a second, different figure for February 2026 (*"60% of those errors were caused by exceeded rate limits"*) — so a reader checking later may find a different headline than the March number this repo carries.

| | **Anthropic** | **OpenAI** | **Google Gemini** |
|---|---|---|---|
| `Retry-After` on a 429 | ✅ documented on **every** 429 | ❌ not documented (0 hits on the rate-limits guide) | ❌ not documented |
| Rate-limit headers | `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` + 6 `anthropic-priority-*` | 9 × `x-ratelimit-*` | none documented |
| Reset encoding | **RFC 3339 timestamp** | **duration string** (`1s`, `6m0s`) | — |
| Output-token axis | OTPM, *"evaluated in real time as output tokens are produced"* | folded into one TPM axis | **none** — TPM is input-only |
| `max_tokens` vs the limit | *"does not factor into OTPM rate limit calculations, so there is no rate limit downside to setting a higher max_tokens"* | *"calculated as the maximum of `max_tokens` and the estimated number of tokens"* — a **reservation** | n/a |
| Cache reads count toward the token limit? | ✗ for most models — *"only uncached input tokens count toward your ITPM"* († Haiku 3.5 **does** count `cache_read_input_tokens`) | not documented | not documented |
| Do failed requests count? | **not documented** | ✅ *"unsuccessful requests contribute to your per-minute limit"* | ✅ not charged on 400/500, but *"the request will still count against your quota"* |
| Replenishment | continuous token bucket — *"capacity is continuously replenished … rather than being reset at fixed intervals"* | not stated; the duration-style resets imply fixed windows (**our inference**) | RPM / TPM(input) / RPD, plus a spend limit on a **rolling 10-minute window** |

**The gateway-relevant reading.** A gateway that normalises "rate limit" across these three cannot pass through a uniform reset semantic — it must convert RFC 3339 ↔ duration ↔ nothing. Worse for anyone doing pre-flight admission: **the same `max_tokens: 64000` is a reservation against your OpenAI TPM and a no-op against your Anthropic OTPM.** A single admission formula is wrong for at least one provider by construction. And "Anthropic 429s are free retries" is folklore — Anthropic's rate-limits page contains zero mentions of `unsuccessful` or `failed request`.

> ⚠️ **This corrects chapter 4.** §6 of [gateway-anatomy.md](gateway-anatomy.md) states unconditionally that *"the entire default retry budget is ≈1.1–1.5 seconds"* for the OpenAI and Anthropic SDKs. `_calculate_retry_timeout()` in **both** SDKs short-circuits before the exponential backoff: `retry_after = self._parse_retry_after_header(...)`, and `if retry_after is not None and 0 < retry_after <= 60: return retry_after`. Anthropic documents sending `retry-after` on every 429 and its errors page says the SDKs retry *"twice by default, honoring the `retry-after` header when present."* **Against Anthropic, the worst-case default 429 budget is 2 × 60 s = ~120 seconds, not 1.5.** The 1.1–1.5 s figure is correct for connection errors and for 429s with no header — which is to say, for OpenAI. Since that number is the decision boundary of chapter 4's entire "case against a gateway", the qualifier is load-bearing.

And the SDK baseline is not uniform anyway. `googleapis/python-genai` @`fc282b3`: `_RETRY_ATTEMPTS = 5` (including the initial call), `_RETRY_INITIAL_DELAY = 1.0`, `_RETRY_MAX_DELAY = 60.0`, `_RETRY_HTTP_STATUS_CODES = (408, 429, 500, 502, 503, 504)`, implemented with `tenacity.wait_exponential_jitter` — which is **header-blind**, so `Retry-After` is never honoured. **Our arithmetic:** ≈1+2+4+8 = 15 s of sleep plus up to 4 s jitter, roughly **10×** the headerless OpenAI/Anthropic budget. Also note 409 is retried by OpenAI and Anthropic and **not** by Google. Anyone telling you "the SDK already retries for you" as a uniform baseline is wrong by an order of magnitude, in the direction that matters for capacity planning.

---

## 8. Health checks and why they lie

A health check is a claim about the future made from a synthetic probe. Six specific reasons that claim is weaker than it looks, each grounded in something above:

1. **A health signal that needs traffic doesn't exist at low traffic.** LiteLLM's percentage rule needs ≥5 requests in the current minute before it can fire. A group serving 3 RPM is never unhealthy by that rule, no matter how badly it is failing.
2. **A one-deployment group loses the two rules that detect degradation** — the `is_single_deployment_model_group` exemption in §4.2(b) disables the 429 rule and the error-rate rule; only a 401/404 or a 100%-failure minute over ≥1,000 requests still trips a cooldown. The configuration where you most want a health signal keeps only its bluntest one.
3. **The most obvious "provider is down" signal is explicitly excluded.** LiteLLM's `_is_cooldown_required` returns `False` when the exception string contains `APIConnectionError`, and for any 4xx other than 429/401/408/404. Connection failures do not cool a deployment down.
4. **The state is per-request or nonexistent in four of six gateways** (§4.1). Bifrost's dead-key set is discarded when the request ends; Portkey OSS's `isOpen` is never set; Kong OSS and Envoy AI Gateway have no AI-level notion of upstream health at all.
5. **A probe on a different key tells you nothing about your key.** Rate limits are per-organisation and per-key, and 429s are ~⅓ of production LLM errors. Anthropic's ITPM/OTPM are continuously-replenished buckets — a 16-token probe succeeding is not evidence that a 64k-token request will be admitted one second later.
6. **The outage most likely to take you down is inside the gateway, where no upstream health check points.** OpenRouter's own February 2026 postmortem: **38 minutes from 05:27 UTC on Feb 17** (80–90% failure rates at peak) and **35 minutes from 07:36 UTC on Feb 19** — root cause, a third-party caching layer used for **API-key lookups**, which then overwhelmed the database on recovery. Users got 500s, then 401 `"User not found"`. OpenRouter's words: *"Returning an authentication error for what was actually an infrastructure problem caused real confusion: some customers spent time debugging their own API key configurations when nothing on their side was wrong."* Their remediation was circuit breakers plus **changing that response from 401 to 503**. No upstream provider was involved at any point.

The practical rule: **treat health state as a hint for load-shedding, never as evidence for a status page.** If your dashboard says a provider is healthy, what it actually says is "our last synthetic probe on our probe key succeeded, and fewer than five requests have failed in the current minute."

---

## 9. The honest reliability arithmetic of a gateway in the path

**Our synthesis, standard reliability math.** A gateway is a series dependency: `A_total = A_gateway × A_provider`. Failover earns its keep only by masking *provider* outages, so the net is `gain = P(provider outage masked) − P(gateway-caused outage)`. Three corrections this chapter forces onto that expression:

**(1) The first term is smaller than the incident count suggests, because failover only works before the first byte.** §5.1: four of six gateways cannot act on a mid-stream failure at all, one acts only on a first-chunk error, one re-prompts. Long streaming responses — agentic coding turns, long-form generation — are simultaneously the most valuable requests and the least protectable. Any estimate of "outages masked" computed from incident counts silently assumes every failure arrives before the response body starts.

**(2) With one provider configured, the first term is identically zero, so the expression is strictly negative.** Unchanged from chapter 4, and worth repeating because installing a gateway in front of a single provider adds a hop, a stateful service and a supply chain without buying anything on this axis.

**(3) The base rates everyone quotes have a date on them, and it is not recent.** The standing citation — repo-sourced, README, from Chu et al., ICPE 2025 ([arXiv 2501.12469](https://arxiv.org/abs/2501.12469)) — is verified exactly as published: median MTBF **1.99 days** (OpenAI API) and **2.09 days** (Anthropic API); *"Most failures are resolved between 0.5 and 3 hours, with the median values around 1 hour"*, OpenAI API 1.23 h vs Anthropic API 0.77 h; and *"only 6.15% of incident reports disclose a postmortem."* **Two caveats the repo does not currently state.** The datasets **end 2024-08-30** (OpenAI 2021-02-09→2024-08-28, n=365; Anthropic 2023-03-25→2024-08-30, n=141) — that is a 2021–2024 base rate being quoted in the present tense in July 2026. And MTTR there is defined as status-page **S1→S4**, i.e. the duration of the vendor's own incident report, not measured user-visible unavailability.

**Calibration for the second term, dated and primary:** the OpenRouter pair in §8 — **73 minutes of downtime across three days**, entirely gateway-caused. That is a failure mode that cannot exist without the gateway, and it presented as a stage-1/2 symptom (401s) from a stage-11 cause (the control plane's cache), which a buyer testing only upstream failover would never catch.

**Two more terms nobody writes down.** *Correlation:* multi-provider failover implicitly assumes independent failures. Provider outages largely are independent; a rate-limit event on your own account is independent; **a bad deploy of your gateway is 100% correlated across every provider you configured.** Adding providers does not reduce that term at all. *Retry cost:* §6.3 — because no layer is idempotent, your retry budget is a spend multiplier. Bifrost's source says it plainly: distinct attempts each bill. A generous `num_retries` across an incident is a bill, not just a latency.

**The decision, stated as a question rather than a recommendation:** *is my worst acceptable outage shorter than about an hour, and does more than a trivial fraction of my traffic fail before the first token?* If both are yes, a gateway's failover is buying something real. If your traffic is long streams, understand that you are buying protection for the connect phase and roughly nothing after it — unless you are on the one implementation in §5.1 that re-prompts, and unless you are willing to pay input tokens twice and accept a seam in the output.

### 9.1 Eight questions to put to a vendor

Each one has a right answer somewhere above, and none of them is in a feature matrix.

1. What are your **shipped defaults** for retry count, backoff and cooldown — not the maximum, the default? (§2.1, §4.1)
2. Is a retry a **re-route** or a **replay**? Can attempt 2 land on a different provider with a different wire format? (§3)
3. Does a failure **outlive the request**? Show me where that state lives and what its TTL is. (§4.1)
4. What does the client see when the upstream dies **after** the first token — an error frame, a truncation, or a resumed stream? (§5.1)
5. If you resume mid-stream, is it a **reconnect or a re-prompt**, and who pays for the second set of input tokens? (§5.1)
6. What's the **idempotency key for billing** across attempts, and does a retried request produce one spend row or two? (§6)
7. Whose `Retry-After` do you honour, and how do you normalise **three incompatible rate-limit contracts** into one admission decision? (§7)
8. When *you* fail — not the provider — what status code do I get, and how would my health check tell the difference? (§8)

---

## 10. Verify this yourself

Nothing above needs to be taken on faith. Ordered by how fast they pay off.

1. **Read the retry defaults off the source, at your version** — 5 minutes, no keys.
   ```bash
   # LiteLLM: the only non-zero default, and the function chapter 4 got wrong
   curl -s https://raw.githubusercontent.com/BerriAI/litellm/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router.py \
     | grep -n "def function_with_fallbacks\|def async_function_with_retries\|def function_with_retries"
   # Bifrost / new-api / Portkey: all zero
   grep -n "DefaultMaxRetries" core/schemas/provider.go        # = 0
   grep -n "var RetryTimes"     common/constants.go            # = 0
   grep -n "attempts: retry"    src/handlers/services/requestContext.ts   # ?? 0
   ```
2. **Prove no idempotency key leaves your machine** — 30 seconds.
   ```bash
   python -c "import openai, anthropic; print(openai.OpenAI(api_key='x')._idempotency_header, anthropic.Anthropic(api_key='x')._idempotency_header)"   # -> None None
   OPENAI_LOG=debug  python your_script.py   # inspect the outgoing headers
   ```
3. **Prove the SDK retry budget is not 1.5 s under `retry-after`** — read `_calculate_retry_timeout` in your installed `_base_client.py` and confirm the `if retry_after is not None and 0 < retry_after <= 60: return retry_after` early return sits *above* the exponential backoff. Then read your own numbers:
   ```bash
   python -c "from openai._constants import *; print(DEFAULT_MAX_RETRIES, INITIAL_RETRY_DELAY, MAX_RETRY_DELAY, DEFAULT_TIMEOUT)"
   python -c "from google.genai._api_client import _RETRY_ATTEMPTS,_RETRY_INITIAL_DELAY,_RETRY_MAX_DELAY,_RETRY_HTTP_STATUS_CODES as C; print(_RETRY_ATTEMPTS,_RETRY_INITIAL_DELAY,_RETRY_MAX_DELAY,C)"
   ```
4. **Kill a stream mid-flight and watch what your gateway does.** Start a long streaming completion through the gateway, then `iptables -A OUTPUT -d <provider-ip> -j REJECT` (or kill the upstream in a mock). §5.1 predicts your answer: continuation text (LiteLLM), or a clean truncation with a 200 and no error (four of the six). Then check whether a spend row exists for the partial.
5. **Check whether a retry is billed once or twice.** Point the gateway at a mock upstream that returns 503 on attempt 1 and 200 on attempt 2, with a known usage object. Read the spend rows. **This is the measurement that would settle §6.3's INCONCLUSIVE, and we have not run it.**
6. **Measure your actual cooldown window**, don't read it. Fail one deployment deliberately, then poll: LiteLLM's default returns it to the rotation after ~5 s. If you expected minutes, you have a config change to make.
7. **Confirm the 429 contracts against live headers** — one call each, keys required.
   ```bash
   curl -sD - -o /dev/null https://api.anthropic.com/v1/messages \
     -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' -H 'content-type: application/json' \
     -d '{"model":"claude-sonnet-5","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}' \
     | grep -i 'ratelimit\|retry-after'
   curl -s https://developers.openai.com/api/docs/guides/rate-limits.md | grep -n 'unsuccessful\|maximum of `max_tokens`'
   ```
8. **Re-verify every commit this chapter pins**, in one loop:
   ```bash
   for x in BerriAI/litellm:c274cf321c5c35c629220a89bb497d15b56f870f \
            Portkey-AI/gateway:669825cbe89ee51569918b8f78a9db486fd69dd4 \
            maximhq/bifrost:e6952b6a7172658b2594208a59e064cd2b60b9cc \
            Kong/kong:391ee48d3a68e8d0bbd0405ec1d02d75f768aa92 \
            envoyproxy/ai-gateway:6722cca8d33896c4464c12f2de5aaf1238a569b6 \
            QuantumNous/new-api:c27d1ef651c608dd8b9e60848a7e0f13a8619d9b; do
     gh api repos/${x%%:*}/git/commits/${x##*:} --jq '.sha[0:8] + "  " + .committer.date'
   done
   ```
9. **Confirm Kong OSS really ships no failover plugin:**
   ```bash
   gh api "repos/Kong/kong/contents/kong/plugins?ref=391ee48d3a68e8d0bbd0405ec1d02d75f768aa92" --jq '.[].name' | grep '^ai-'
   # -> exactly 6 names, none of them ai-proxy-advanced
   ```

---

## 11. Where to go next

If you're choosing a gateway, start at [the requirements map](../README.md#the-requirements-map) and [How to choose safely](../README.md#how-to-choose-safely); the reliability-relevant evidence lives in the [Quick comparison](../README.md#quick-comparison) and [BENCHMARKS Part 5](../BENCHMARKS.md#part-5--real-world-reviews-what-production-users-report).

In this handbook — the full map is in the [chapter index](../HANDBOOK.md). [Chapter 1 — The Compatibility Surface](protocol-translation.md) is the translation layer this chapter's §3 keeps re-entering per attempt; read it if any of your failover targets speak a different wire format. [Chapter 4 — Anatomy of an AI gateway](gateway-anatomy.md) is the whole request path, and this chapter closes the stage-7 gap it left open — with four corrections to chapter 4 flagged inline above (`async_function_with_retries`, Portkey's third layer, the full Bifrost billing quote, and the `retry-after` qualifier on the SDK budget), which is what "falsifiable by design" is supposed to look like in practice.

**Explicitly not established here**, so nobody cites this chapter for them: whether LiteLLM, Kong OSS or new-api bills a client twice for one physical provider call on retry (§6.3, needs a spend-delta measurement); the runtime consequence of Kong's `enable_balancer_retry` naming mismatch (§3, code shape verified, behaviour inferred); Higress's retry, cooldown and mid-stream semantics, which were not read this pass; and any claim about Kong Enterprise's or Bifrost Enterprise's circuit breakers beyond what their own docs state.

---

## Appendix — every source this chapter relies on

**Source trees, read at pinned commits, each re-verified via `gh api repos/<owner>/<repo>/git/commits/<sha>` on 2026-07-29** (dates below are the committer dates that call returned):

| Gateway | Commit | Committed | Files read |
|---|---|---|---|
| BerriAI/litellm | [`c274cf3`](https://github.com/BerriAI/litellm/commit/c274cf321c5c35c629220a89bb497d15b56f870f) | 2026-07-29 | [`litellm/router.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router.py) · [`router_utils/cooldown_handlers.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router_utils/cooldown_handlers.py) · [`constants.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/constants.py) · [`utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/utils.py) · [`litellm_core_utils/streaming_handler.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/streaming_handler.py) |
| Portkey-AI/gateway | [`669825c`](https://github.com/Portkey-AI/gateway/commit/669825cbe89ee51569918b8f78a9db486fd69dd4) | 2026-05-25 | [`src/handlers/handlerUtils.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/handlerUtils.ts) · [`retryHandler.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/retryHandler.ts) · [`streamHandler.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/streamHandler.ts) · [`services/requestContext.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/services/requestContext.ts) · [`src/globals.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/globals.ts) · `src/types/requestBody.ts` |
| maximhq/bifrost | [`e6952b6`](https://github.com/maximhq/bifrost/commit/e6952b6a7172658b2594208a59e064cd2b60b9cc) | 2026-07-28 | [`core/bifrost.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/bifrost.go) · [`core/utils.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/utils.go) · [`core/schemas/provider.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/schemas/provider.go) · [`core/streamfallback_test.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/streamfallback_test.go) · [`plugins/governance/tracker.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/plugins/governance/tracker.go) · `docs/enterprise/circuit-breaker.mdx` · `plugins/` tree listing |
| Kong/kong | [`391ee48`](https://github.com/Kong/kong/commit/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92) | 2026-07-22 | [`kong/llm/plugin/base.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/base.lua) · [`kong/db/schema/entities/services.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/db/schema/entities/services.lua) · [`kong/llm/drivers/openai.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/drivers/openai.lua) · `kong/runloop/handler.lua` · `kong/runloop/upstream_retry.lua` · `kong/init.lua` · `kong/templates/nginx_kong.lua` · `kong/plugins/` tree listing (6 `ai-*` plugins) |
| envoyproxy/ai-gateway | [`6722cca`](https://github.com/envoyproxy/ai-gateway/commit/6722cca8d33896c4464c12f2de5aaf1238a569b6) | 2026-07-23 | [`internal/extensionserver/post_translate_modify.go`](https://github.com/envoyproxy/ai-gateway/blob/6722cca8d33896c4464c12f2de5aaf1238a569b6/internal/extensionserver/post_translate_modify.go) · [`internal/extproc/processor_impl.go`](https://github.com/envoyproxy/ai-gateway/blob/6722cca8d33896c4464c12f2de5aaf1238a569b6/internal/extproc/processor_impl.go) · `examples/provider_fallback/fallback.yaml` · `site/docs/capabilities/traffic/provider-fallback.md` |
| QuantumNous/new-api | [`c27d1ef`](https://github.com/QuantumNous/new-api/commit/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b) | 2026-07-29 | [`controller/relay.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/controller/relay.go) · [`setting/operation_setting/status_code_ranges.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/setting/operation_setting/status_code_ranges.go) · [`common/constants.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/common/constants.go) · `service/channel.go` · `model/option.go` · `relay/compatible_handler.go` · `relay/helper/stream_scanner.go` · `relay/channel/openai/relay-openai.go` |

**SDK sources, read at pinned commits on 2026-07-29:** openai/openai-python [`4f40426`](https://github.com/openai/openai-python/commit/4f404262955cb711c56c07cce52076b6107303e5) (2026-07-28) — `_constants.py`, `_base_client.py`, `_streaming.py` · anthropics/anthropic-sdk-python [`f5c30d0`](https://github.com/anthropics/anthropic-sdk-python/commit/f5c30d0490fb7bcd8e0b65d8d8e63c0e7d1bfe59) (2026-07-28) — same three files · googleapis/python-genai [`fc282b3`](https://github.com/googleapis/python-genai/commit/fc282b359a7e9e16219587266c94d2bdc506164a) (2026-07-28) — `google/genai/_api_client.py` · openai/openai-node `83e6b4a` and anthropics/anthropic-sdk-typescript `3b45cd3` — `src/client.ts` (the same declared-never-assigned `idempotencyHeader` pattern).

**Vendor & standards documentation, all fetched 2026-07-29:** [Anthropic rate limits](https://platform.claude.com/docs/en/api/rate-limits) · [Anthropic errors](https://platform.claude.com/docs/en/api/errors) · [Anthropic streaming, incl. Error recovery](https://platform.claude.com/docs/en/build-with-claude/streaming) · [Anthropic Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python) · [Anthropic billing FAQ](https://support.claude.com/en/articles/8114526-how-will-i-be-billed) (support-centre tier, not the API reference) · [OpenAI rate limits](https://developers.openai.com/api/docs/guides/rate-limits) · [OpenAI streaming events reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events.md) · [OpenAI background mode](https://developers.openai.com/api/docs/guides/background) · [OpenAI Agentic Commerce production guide](https://developers.openai.com/commerce/guides/production) (the only OpenAI-documented `Idempotency-Key`) · [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Gemini billing FAQ](https://ai.google.dev/gemini-api/docs/billing) · [Gemini troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting) · [WHATWG SSE spec](https://html.spec.whatwg.org/multipage/server-sent-events.html) · [nginx `ngx_http_proxy_module`](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) · [Envoy router filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/router_filter) · [Kong `ai-proxy-advanced` reference](https://developer.konghq.com/plugins/ai-proxy-advanced/reference/) (`tier: ai_gateway_enterprise`; `max_fails: 0` = *"disables the circuit breaker"*).

**GitHub issues cited** (each verified to exist via `gh api` on 2026-07-29):

| Issue | State | Cited for |
|---|---|---|
| [maximhq/bifrost#4788](https://github.com/maximhq/bifrost/issues/4788) | closed, created 2026-06-29 | The first-chunk streaming regression whose fix ships `core/streamfallback_test.go` (`TestStreamFallbackAfterFirstChunkError`, `TestStreamRetryAfterFirstChunkError`) |
| [litellm#14457](https://github.com/BerriAI/litellm/issues/14457) | open | Usage lost on client disconnect mid-stream — the gateway-side cost of Anthropic's disconnect-billing clause |
| [new-api#4463](https://github.com/QuantumNous/new-api/issues/4463) | closed | The deliberate opposite choice: kill the upstream on client disconnect |

**Repo-sourced figures & prior chapters:** [README](../README.md) (Datadog production telemetry, March 2026: rate limits ≈⅓ of LLM errors, ~8.4M; Chu et al. ICPE 2025 MTBF/MTTR base rates — see §9 for the dataset-window caveat this chapter adds) · [BENCHMARKS Part 5](../BENCHMARKS.md#part-5--real-world-reviews-what-production-users-report) and [data/gateway_reality.json](../data/gateway_reality.json) — note that this data file currently carries **no `as_of` key**, unlike the repo's other curated datasets, so its rows cannot be dated by a consumer; every OpenRouter figure in this chapter is therefore taken from the vendor postmortem directly, not from that file · [OpenRouter Feb 2026 postmortem](https://openrouter.ai/blog/announcements/openrouter-outages-on-february-17-and-19-2026/) · [chapter 1](protocol-translation.md) · [chapter 4](gateway-anatomy.md) · [chapter map](../HANDBOOK.md).

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every claim above is dated and linked to a commit, an issue, a vendor doc or a measurement, so you can re-check it. If a pinned commit has moved on, that's a PR we want.*
