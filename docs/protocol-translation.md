# The Compatibility Surface — Why Gateways Break Claude Code (and How to Tell Before It Bites You)

*Last updated 2026-07-29 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

**Languages:** English · [简体中文](protocol-translation.zh-CN.md)

> 📊 **Key numbers** · The three major LLM wire protocols share **zero field names in their usage objects** (`prompt_tokens` vs `input_tokens` vs `promptTokenCount` — verified against the official references below, 2026-07-29), so every cross-format request is a live, lossy translation. On the hardest path — an Anthropic-format client like Claude Code routed to an OpenAI-format upstream — the independent measurement is **LiteLLM 3/3 · Bifrost 3/3 · Portkey OSS: path not offered** ([xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json), neutral CI, 2026-07-10). The phrase "claude code" appears in **465 LiteLLM issues** and **138 new-api issues** (`repo:<owner>/<repo> "claude code" is:issue`, 2026-07-29 — without `is:issue` the LiteLLM figure is ~2,000 because pull requests are counted too). And one silent failure has a price tag: a stripped `cache_control` breakpoint re-bills cached input at **10×** — cache reads cost 0.1× base input on [Anthropic's official price sheet](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

Every gateway on the [list](../README.md) advertises some version of "OpenAI-compatible, works with Claude, supports Gemini." What that sentence hides is *where* the compatibility lives. A gateway that accepts Anthropic's Messages format from your agent and forwards it to an Anthropic upstream is doing passthrough — cheap and hard to get wrong. A gateway that accepts Messages format and serves it from an OpenAI-format upstream (or vice versa) is doing **structural translation of every request and every streamed byte of every response**. That translation layer is the single largest source of "the gateway broke my agent" bug reports, and this chapter maps it: what the three protocols actually disagree on, the five ways translation fails (each anchored to a real, verified GitHub issue), what independent measurement shows, and how to test your own gateway in ten minutes.

---

## 1. The concept in 60 seconds

There are three wire-protocol families that matter in 2026:

| Family | Endpoint | Spoken natively by | Reference (verified 2026-07-29) |
|---|---|---|---|
| **OpenAI Chat Completions** | `POST /v1/chat/completions` | OpenAI + the entire "OpenAI-compatible" ecosystem | [developers.openai.com](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions) |
| **Anthropic Messages** | `POST /v1/messages` | Anthropic; the format Claude Code emits | [platform.claude.com](https://platform.claude.com/docs/en/api/messages) |
| **Gemini generateContent** | `POST …:generateContent` / `:streamGenerateContent` | Google Gemini | [ai.google.dev](https://ai.google.dev/api/generate-content) |

A gateway that "speaks all three" sits in the middle doing live translation: request body down to the upstream's schema, then the response — including the SSE stream, event by event — back up to the client's schema. Translation must preserve tool-call identity across turns, re-shape streaming envelopes on the fly, and re-derive token accounting between schemas that don't share a single field name. Passthrough fidelity is a solved problem; **translation fidelity is where agents die**, because coding agents exercise exactly the corners the schemas disagree on: parallel tool calls, long system prompts, incremental tool-argument streaming, and cache breakpoints.

### The same tool call, three ways

Here is one model response — "call `get_weather` for San Francisco" — as each protocol actually puts it on the wire (shapes from the official references above; the Gemini function shapes also per [Google's function-calling guide](https://ai.google.dev/gemini-api/docs/function-calling), retrieved 2026-07-29):

```jsonc
// OpenAI chat.completions — arguments is a JSON-encoded STRING; finish_reason: "tool_calls"
{ "role": "assistant",
  "tool_calls": [{
    "id": "call_abc123",
    "type": "function",
    "function": { "name": "get_weather",
                  "arguments": "{\"location\": \"San Francisco, CA\"}" } }] }
```

```jsonc
// Anthropic messages — input is a parsed OBJECT; stop_reason: "tool_use"
{ "role": "assistant",
  "content": [{
    "type": "tool_use",
    "id": "toolu_01T1x1fJ34qAmk2tNTrN7Up6",
    "name": "get_weather",
    "input": { "location": "San Francisco, CA" } }] }
```

```jsonc
// Gemini generateContent — a functionCall PART inside a "model" content
{ "role": "model",
  "parts": [{
    "functionCall": { "name": "get_weather",
                      "args": { "location": "San Francisco, CA" } } }] }
```

Three different container shapes, two different argument encodings (string vs object), and three different pairing mechanisms for the tool *result* coming back: OpenAI pairs by `tool_call_id` in a dedicated `tool`-role message, Anthropic by `tool_use_id` in a `tool_result` block inside a `user` message, and Gemini's documented `functionResponse` shape pairs by function *name*, not id. A translating gateway carries ids like `toolu_01N9FRKhMkWtQ77NLCKGy4An` across schemas that never minted them — the verbatim payload in [Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980) shows exactly such Anthropic-minted `toolu_…` ids riding inside OpenAI-shaped `tool_calls` messages at the moment the pairing broke.

---

## 2. The field-by-field mismatch

Everything below is taken from the current official references — [OpenAI Chat Completions](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions) (+ [streaming events](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)), [Anthropic Messages](https://platform.claude.com/docs/en/api/messages) (+ [streaming](https://platform.claude.com/docs/en/build-with-claude/streaming), [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)), and [Gemini generateContent](https://ai.google.dev/api/generate-content) — all retrieved 2026-07-29.

| Concern | OpenAI `chat.completions` | Anthropic `messages` | Gemini `generateContent` | What the translator must not fumble |
|---|---|---|---|---|
| **System prompt** | A message: `role: "system"` (or `"developer"`) inside `messages[]`; multiple allowed | Top-level `system` parameter (string or text-block array); `messages[]` alternates `user`/`assistant` | Top-level `systemInstruction` object with `parts` | Hoist N system messages into 1 top-level field — without dropping any (see [failure mode 4](#failure-4)) |
| **Roles** | `developer` · `system` · `user` · `assistant` · `tool` | `user` · `assistant` | `user` · `model` | `tool`-role messages have no direct Anthropic/Gemini equivalent — they must become content blocks/parts inside a `user` turn |
| **Tool call (model → you)** | `assistant` message with `tool_calls[]`: `{id, type: "function", function: {name, arguments}}` — `arguments` is a **JSON-encoded string** | `tool_use` content block: `{type, id, name, input}` — `input` is a **parsed object** | `functionCall` part inside a `model` content | String↔object conversion of the arguments, both directions; a classic bug is relaying `input` as a raw string |
| **Tool result (you → model)** | Separate message: `role: "tool"`, `tool_call_id` | `tool_result` content block inside a `user` message: `{tool_use_id, content, is_error}` | `functionResponse` part | Id pairing: every `tool_use.id` must match a `tool_result.tool_use_id` — Anthropic 400s if any is orphaned (see [failure mode 1](#failure-1)) |
| **Stream envelope** | Unnamed SSE `data:` lines, each a `chat.completion.chunk` with `choices[].delta`; terminates with `data: [DONE]` | **Named SSE events**: `message_start` → `content_block_start`/`content_block_delta`/`content_block_stop` (per block, with `index`) → `message_delta` → `message_stop`, plus `ping`/`error` | SSE via `?alt=sse`; each chunk a full `GenerateContentResponse` JSON | The shapes are structurally alien: flat delta stream ↔ indexed block state machine. The translator must *synthesize* events that never existed upstream |
| **Streaming text** | `delta.content` string fragments | `content_block_delta` with `delta.type: "text_delta"` | `candidates[].content.parts[].text` | Losing granularity here = buffered "fake" streaming (see [failure mode 2](#failure-2)) |
| **Streaming tool args** | `delta.tool_calls[]` fragments keyed by `index`; `function.arguments` accretes as string pieces | `input_json_delta` with `partial_json` string pieces; final `tool_use.input` must be a parsed object | (no equivalent incremental-JSON contract documented) | Accumulate partial JSON, then parse — mismatched block `index` bookkeeping breaks clients mid-stream |
| **Finish/stop** | `finish_reason`: `stop` · `length` · `tool_calls` · `content_filter` · `function_call` | `stop_reason`: `end_turn` · `max_tokens` · `stop_sequence` · `tool_use` · `pause_turn` · `refusal` · `model_context_window_exceeded`; arrives in `message_delta` | `finishReason` (own enum) | `tool_calls`↔`tool_use` must map exactly, or the agent doesn't know it's supposed to run a tool |
| **Thinking / reasoning** | Reasoning is exposed only as a count: `completion_tokens_details.reasoning_tokens` | First-class `thinking` content blocks, streamed via `thinking_delta` + a `signature_delta` (integrity signature) before `content_block_stop` | `thoughtsTokenCount` in `usageMetadata` | Anthropic thinking blocks (and their signatures) simply have nowhere to go in an OpenAI-format hop — round-tripping loses them |
| **Usage naming** | `usage`: `prompt_tokens` · `completion_tokens` · `total_tokens`; stream: **only the final chunk** carries usage, and only if `stream_options: {"include_usage": true}` | `usage`: `input_tokens` · `output_tokens` (+ cache fields); stream: `message_start` carries initial usage, `message_delta` carries **cumulative** totals | `usageMetadata`: `promptTokenCount` · `candidatesTokenCount` · `totalTokenCount` | Zero shared names. If the translator forgets `include_usage` downstream or drops `message_delta.usage` upstream, billing can't be reconciled |
| **Cache accounting** | `prompt_tokens` **includes** cached tokens; `prompt_tokens_details.cached_tokens` is a subset breakdown | `input_tokens` **excludes** cache traffic: total input = `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` | `cachedContentTokenCount` in `usageMetadata` | The inclusion-semantics flip is a built-in double-count trap (see [failure mode 3](#failure-3)) |
| **Cache breakpoints** | None — server-side automatic caching | Explicit `cache_control: {"type": "ephemeral"}` (optional `ttl`: `"5m"`/`"1h"`) on content blocks, ≤4 per request | Separate cached-content mechanism | `cache_control` exists **only** in Anthropic's schema — a naive translator strips it, silently (see [failure mode 5](#failure-5)) |

### The same two-word reply, streamed, both ways

The row that is hardest to picture from a table is the stream envelope, so here it is concretely. An OpenAI-format upstream streams "Hello!" as unnamed `data:` chunks (shape per the [streaming-events reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)):

```text
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

An Anthropic-format client expects the same two words as a *named-event state machine* (this sequence is the [official docs' own example](https://platform.claude.com/docs/en/build-with-claude/streaming), abbreviated):

```text
event: message_start
data: {"type":"message_start","message":{"id":"msg_…","role":"assistant","content":[],"usage":{"input_tokens":25,"output_tokens":1},…}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":15}}

event: message_stop
data: {"type":"message_stop"}
```

A translating gateway must *manufacture* the right-hand side from the left in real time: invent `message_start` before the first upstream chunk arrives, open and close numbered content blocks it was never told about, convert `finish_reason: "stop"` into a `message_delta` carrying `stop_reason: "end_turn"` *plus* usage the upstream only sends on its final chunk (and only if the gateway remembered to request `stream_options: {"include_usage": true}` downstream). Add a tool call mid-stream and it must interleave a second block with `input_json_delta` fragments at the correct `index`. Get any of the bookkeeping wrong and the client's stream parser throws — which is precisely the `Content block not found` error in [failure mode 2](#failure-2).

Two rows in the mismatch table do the most damage in practice. The **usage-semantics flip** (OpenAI counts cached tokens inside `prompt_tokens`; Anthropic counts them *outside* `input_tokens`) means a translator that maps fields 1:1 either double-counts or under-counts cached input — that's not a bug in any one gateway, it's a trap in the schema pair. And **`cache_control` having no OpenAI equivalent** means any "normalize to OpenAI format internally" architecture destroys it by default unless someone writes explicit preservation code — per provider adapter, forever.

---

## 3. The five failure modes

Each failure mode below is anchored to a real, public GitHub issue, verified to exist and to say what we cite it for (via GitHub API, 2026-07-29). Dates are issue-creation dates; closed issues are fixed in current releases — they're cited as evidence of the *class*, which recurs.

<a name="failure-1"></a>
### 3.1 Tool-call rewriting or dropping

The translator loses tool-call identity or structure across the format boundary. The canonical shape: a client sends parallel tool calls and their results back through the gateway, and the id pairing breaks in translation — the upstream rejects the conversation with `400 … the following tool_use ids were not found in tool_result blocks` ([Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980), 2025-03-09, closed — OpenAI-format client with multiple `tool_calls` relayed to Anthropic). The subtler variant is dropping or string-ifying arguments: the [cross-format probe](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs) explicitly checks that `tool_use.input` arrives as a *parsed object*, "the classic mistranslation" being a raw JSON string. For an agent, either variant is fatal: it can't execute the tool or can't continue the conversation.

<a name="failure-2"></a>
### 3.2 Fake or reshaped streaming

Translating a flat OpenAI delta stream into Anthropic's indexed block state machine (or vice versa) in real time is genuinely hard, and two distinct failures come out of it. **Reshaped-broken**: the synthesized event stream violates the client's state expectations — Claude Code driving an OpenAI model through LiteLLM's `/v1/messages` logged `Error streaming, falling back to non-streaming mode: Content block not found` on every tool call ([BerriAI/litellm#13373](https://github.com/BerriAI/litellm/issues/13373), 2025-08-07, closed). **Fake streaming**: the gateway buffers the whole upstream response and emits it as one blob — you lose time-to-first-token and any ability to see queue latency. The measured signature is a stream that arrives as 0–1 delta events instead of many: exactly what [fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json) recorded for Portkey OSS v1.15.2 on a clean CI runner ("only 0 chunk(s) — collapsed/buffered", 2026-07-10; non-streaming worked, hosted product untested).

<a name="failure-3"></a>
### 3.3 Usage misreporting and inflation

Because the three usage schemas disagree on both names and *semantics*, translated usage is where billing quietly goes wrong. Two verified instances on opposite sides of the same trap: LiteLLM's cost calculation once charged `cache_creation_input_tokens` twice — "once as prompt tokens and then again as cache creation tokens" — reporting $0.091311 against an Anthropic-console-verified $0.05439, ~1.7× the real cost ([BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812), 2025-04-08, closed). And new-api's `/v1/messages` → OpenAI-compatible-upstream conversion returned `input_tokens` that still *included* cached tokens — inflated usage on the Anthropic-format side, precisely the inclusion-semantics flip from the table above ([QuantumNous/new-api#4395](https://github.com/QuantumNous/new-api/issues/4395), 2026-04-22, open, zh). If you pay per token through a gateway, this failure mode is invisible until you reconcile against the provider's own console.

<a name="failure-4"></a>
### 3.4 Context and system-prompt truncation

Translation between "system prompts are messages, plural" (OpenAI) and "system prompt is one top-level field" (Anthropic) invites silent content loss. Verified instance: Portkey's Anthropic adapter overwrote the `system` parameter on each iteration, so when a client sent multiple system messages **only the last one was forwarded** — every earlier instruction silently vanished ([Portkey-AI/gateway#457](https://github.com/Portkey-AI/gateway/issues/457), 2024-07-11, closed). The mirror image is *mangling* rather than truncation: new-api's message re-serialization produced empty text content blocks that Anthropic rejects (`400 … text content blocks must be non-empty`), making Claude Code entirely unusable through the gateway against Anthropic's own models ([QuantumNous/new-api#1854](https://github.com/QuantumNous/new-api/issues/1854), 2025-09-20, closed, zh). Truncation is the nastier of the two: a 400 you notice; a dropped system prompt just makes your agent quietly worse.

<a name="failure-5"></a>
### 3.5 `cache_control` stripping — the silent 10× bill

`cache_control` breakpoints exist only in Anthropic's schema, so any internal normalization step that doesn't explicitly carry them drops them — and *nothing fails*. Requests succeed, responses look identical; the only symptom is `cache_read_input_tokens: 0` and a bigger bill. Verified instances: Portkey stripping `cache_control` en route to Vertex AI Anthropic models, with the reporter's own before/after usage showing zero cache tokens ([Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579), 2026-03-25, open), and LiteLLM's SDK→proxy path silently no-opping cache-control injection ([BerriAI/litellm#30319](https://github.com/BerriAI/litellm/issues/30319), 2026-06-12, closed). The class keeps recurring per adapter — e.g. [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797) (2026-07-27, open) reports the same stripping in a newer provider path. The arithmetic: Anthropic bills cache reads at **0.1× base input** ([pricing, retrieved 2026-07-29](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)), so input that should have been cache-read now bills at full price — **10× on those tokens**. For a Claude Code session, where the system prompt and tool definitions dominate input and repeat on every request, "those tokens" is most of your bill (production telemetry cited on the [list](../README.md#-latest-evaluations) has system prompts at 69% of input tokens — Datadog, 2026-04).

---

## 4. Why the measured results look the way they do

The [llm-gateway-bench](https://github.com/cuihuan/llm-gateway-bench) project measures exactly this chapter's subject, black-box, against a spec-correct mock upstream on a neutral CI runner (no API keys, no vendor involvement). Two datasets, both from 2026-07-10:

**Same-format passthrough** ([fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json)) — OpenAI client → gateway → OpenAI-format upstream. Does a spec-correct response survive the relay?

| Gateway (version) | tool_calls | streaming | stream usage | Score |
|---|---|---|---|---|
| LiteLLM 1.91.1 | ✅ intact | ✅ 7 chunks, content intact | ✅ `total_tokens=14` relayed | **3/3** |
| Bifrost (docker `95caedb1c368`) | ✅ intact | ✅ 5 chunks, content intact | ✅ relayed | **3/3** |
| Portkey OSS 1.15.2 | ✅ intact | ❌ 0 chunks — collapsed/buffered | ❌ no usage in stream | **1/3** |

**Cross-format translation** ([xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json)) — Anthropic-format client (the Claude Code path) → gateway `/v1/messages` → OpenAI-format upstream. The hardest path, and the one this chapter is about:

| Gateway (version) | tool_use | streaming | stream usage | Score |
|---|---|---|---|---|
| LiteLLM 1.91.1 | ✅ name + parsed `input` | ✅ 3 `text_delta` events, intact | ✅ `output_tokens` in `message_delta` | **3/3** |
| Bifrost (docker `95caedb1c368`) | ✅ | ✅ 4 `text_delta` events | ✅ | **3/3** |
| Portkey OSS 1.15.2 | — | — | — | **not offered** — its `/v1/messages` is Anthropic-provider-only in the header-config self-host; targeting an OpenAI upstream returns 500 `"messages is not supported by openai"` |

Three readings, grounded in the raw data:

1. **LiteLLM and Bifrost genuinely translate, and translate cleanly** — on this probe's three checks, both synthesize a well-formed Anthropic event stream (`message_start` → `content_block_delta` … — visible verbatim in the recorded `stream_snippet`s), deliver `tool_use.input` as a parsed object, and land `output_tokens` in the final `message_delta`. That's all five failure-mode surfaces from §3 exercised at their choke points, passing.
2. **Portkey OSS's cross-format "failure" is honest scoping, not breakage** — the data records `unsupported: true`, not a lying 3/3 or a crash. Its `/v1/messages` endpoint translates only *toward Anthropic-family providers* in this deployment mode. If your agent speaks Anthropic format and your upstream speaks OpenAI format, this gateway (in OSS header-config mode) is not on the menu — its 1/3 on the *same-format* streaming probe is the separate, real finding.
3. **The path under your feet changes between versions — pin them.** The [probe's own header](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs) documents (measured 2026-07-09) that LiteLLM ≤1.57.x served `/v1/messages` by translating to the upstream's **Chat Completions** endpoint, while ≥~1.9x rewrote the path to the OpenAI **Responses API** (`/v1/responses`, `input`/`max_output_tokens`) — and the new transformer raises `KeyError('created_at')` if the upstream answers with a `chat.completion` body. Same gateway, same config, different minor version: a chat-completions-only upstream went from working to a Python traceback. The bench handles this by mocking both endpoints and flagging the mismatch inconclusive rather than 0/3; your production stack won't be so forgiving.

---

## 5. How to verify *your* gateway in 10 minutes

Don't trust this chapter — or any vendor README. The whole point of the failure catalog is that every signature is cheap to check:

1. **Pin and record versions first** — gateway version/image digest and agent version. §4's `KeyError('created_at')` story is what "it worked last month" looks like across a minor bump.
2. **Run the black-box probes (no API keys needed):**
   ```bash
   git clone https://github.com/cuihuan/llm-gateway-bench && cd llm-gateway-bench
   node probe/fidelity.mjs   # same-format passthrough: tool_calls / streaming / usage
   node probe/xformat.mjs    # the Claude Code path: Anthropic client → OpenAI upstream
   ```
   Point them at your gateway; they run a spec-correct mock upstream locally and score the same 3 checks as §4.
3. **Run your real agent through it** — a trivial Claude Code task in a scratch repo (`claude -p "list the files here and read one"`) exercises parallel tools, streaming, system prompt, and caching in one shot. Run it twice back-to-back (the second run is the cache check).
4. **Reconcile one request's usage** against the provider's own console — the only way to catch [failure mode 3](#failure-3).

Then read the output against the five signatures:

| Signature you see | Failure mode | Anchor issue |
|---|---|---|
| `400 … tool_use ids were not found in tool_result blocks`; tools fire but the next turn 400s | Tool-call rewriting/dropping | [Portkey#980](https://github.com/Portkey-AI/gateway/issues/980) |
| `Error: Streaming fallback triggered` / long pause then the whole answer at once / probe reports "collapsed/buffered" | Fake or reshaped streaming | [litellm#13373](https://github.com/BerriAI/litellm/issues/13373) |
| Gateway-billed tokens ≠ provider console; `input_tokens` moves with cache activity | Usage misreporting | [litellm#9812](https://github.com/BerriAI/litellm/issues/9812), [new-api#4395](https://github.com/QuantumNous/new-api/issues/4395) |
| Agent "forgets" standing instructions; `400 … text content blocks must be non-empty` | Context/system-prompt truncation or mangling | [Portkey#457](https://github.com/Portkey-AI/gateway/issues/457), [new-api#1854](https://github.com/QuantumNous/new-api/issues/1854) |
| `cache_read_input_tokens: 0` on the *second* identical request | `cache_control` stripping (silent 10×) | [Portkey#1579](https://github.com/Portkey-AI/gateway/issues/1579), [litellm#30319](https://github.com/BerriAI/litellm/issues/30319) |

Ten minutes. The alternative is finding out from your invoice.

---

## 6. Per-gateway implementation notes

Only gateways whose behavior we can source — from their own docs or from the measured data — get a row with claims; everything else on the [list](../README.md) is honestly **not measured**. Vendor docs describe intent; the *measured* column is what actually happened on a neutral runner (2026-07-10).

| Gateway | Anthropic-format inbound (`/v1/messages`) | Cross-format translation | Source (retrieved 2026-07-29) | Measured (xformat · fidelity) |
|---|---|---|---|---|
| **LiteLLM** | ✅ documented | ✅ to "all LiteLLM supported providers" (openai, bedrock, vertex, gemini, azure…) | [docs.litellm.ai — `/v1/messages`](https://docs.litellm.ai/docs/anthropic_unified) | **3/3 · 3/3** (v1.91.1) — note the §4 transport change; pin your version |
| **Bifrost** | ✅ drop-in Anthropic SDK endpoint (`/anthropic`) | ✅ unified across 23+ providers behind an OpenAI-compatible core | [README](https://github.com/maximhq/bifrost) · [Anthropic SDK integration docs](https://docs.getbifrost.ai/integrations/anthropic-sdk/overview) | **3/3 · 3/3** (docker `95caedb1c368`) |
| **Portkey OSS** | Endpoint exists, but Anthropic-provider-only in header-config self-host | ❌ not offered on the Anthropic→OpenAI path in that mode (`"messages is not supported by openai"`) | measured behavior, [xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json) | **not offered · 1/3** (v1.15.2; hosted product untested) |
| **new-api** | ✅ "Native Claude Format" documented | ✅ converts `/v1/messages` ↔ OpenAI-compatible upstreams (usage-conversion caveat: [#4395](https://github.com/QuantumNous/new-api/issues/4395)) | [docs.newapi.pro — Native Claude Format](https://docs.newapi.pro/en/docs/api/ai-model/chat/createmessage) | not measured |
| **one-api** | ❌ — inbound is OpenAI format only ("access all models via the standard OpenAI API format") | Outbound only: rewrites request/response bodies toward non-OpenAI downstream channels (incl. Claude) | [README](https://github.com/songquanpeng/one-api) (zh; incl. architecture diagram) | not measured |
| Everything else on the [list](../README.md) | — | — | — | **not measured** — treat all compatibility claims as vendor claims until probed |

---

## 7. What this means for choosing

If your agent speaks Anthropic format and your upstream doesn't (or might not, once [routing](../README.md#-smart-routing--model-selection) kicks in), the translation layer *is* the product — shortlist from gateways with measured cross-format fidelity in [Self-hosted open source](../README.md#-self-hosted-open-source), currently LiteLLM and Bifrost at 3/3, and pin the exact version you validated. Before any gateway touches production traffic, spend the ten minutes in §5, because four of the five failure modes are silent and one of them costs 10× on your biggest token bucket — the caching economics are laid out in [Prompt caching through a gateway — the money question](../README.md#-prompt-caching-through-a-gateway--the-money-question). And keep reconciling usage against the provider console on a schedule, per [How to choose safely](../README.md#how-to-choose-safely) — a gateway that was faithful at version *N* is one refactor away from failure mode 3 at version *N+1*.

---

## Appendix — every source this chapter relies on

**Primary protocol references** (all retrieved and field-checked 2026-07-29):

- OpenAI Chat Completions — [create / parameters & usage schema](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions) · [streaming events](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)
- Anthropic Messages — [API reference](https://platform.claude.com/docs/en/api/messages) · [streaming](https://platform.claude.com/docs/en/build-with-claude/streaming) · [prompt caching & pricing multipliers](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Gemini — [generateContent / streamGenerateContent reference](https://ai.google.dev/api/generate-content) · [function calling shapes](https://ai.google.dev/gemini-api/docs/function-calling)

**GitHub issues** (each verified to exist and to say what it's cited for, via GitHub API, 2026-07-29):

| Issue | Title (abridged) | Created | State | Cited in |
|---|---|---|---|---|
| [Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980) | 400 anthropic error: `tool_use` ids not found in `tool_result` blocks | 2025-03-09 | closed | §3.1 |
| [BerriAI/litellm#13373](https://github.com/BerriAI/litellm/issues/13373) | Claude Code with an OpenAI model throws "Streaming fallback triggered" | 2025-08-07 | closed | §3.2 |
| [BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812) | Anthropic cost calculations incorrect with prompt caching | 2025-04-08 | closed | §3.3 |
| [QuantumNous/new-api#4395](https://github.com/QuantumNous/new-api/issues/4395) | `/v1/messages` → OpenAI-compatible upstream usage conversion (zh) | 2026-04-22 | open | §3.3 |
| [Portkey-AI/gateway#457](https://github.com/Portkey-AI/gateway/issues/457) | Anthropic only uses last system message | 2024-07-11 | closed | §3.4 |
| [QuantumNous/new-api#1854](https://github.com/QuantumNous/new-api/issues/1854) | Claude Code via new-api → "text content blocks must be non-empty" (zh) | 2025-09-20 | closed | §3.4 |
| [Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579) | `cache_control` stripped when routing to Vertex AI Anthropic | 2026-03-25 | open | §3.5 |
| [BerriAI/litellm#30319](https://github.com/BerriAI/litellm/issues/30319) | Prompt caching silently stripped through proxy path | 2026-06-12 | closed | §3.5 |
| [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797) | `cache_control` stripped in SAP provider path | 2026-07-27 | open | §3.5 |

**Measured data & vendor docs**:

- [xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json) · [fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json) — neutral-CI probe results, measured 2026-07-10 (LiteLLM 1.91.1, Bifrost docker `95caedb1c368`, Portkey OSS 1.15.2)
- [probe/xformat.mjs](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs) — probe source; the LiteLLM `/v1/messages` transport-change and `KeyError('created_at')` note (measured 2026-07-09)
- [LiteLLM `/v1/messages` docs](https://docs.litellm.ai/docs/anthropic_unified) · [Bifrost README](https://github.com/maximhq/bifrost) + [Anthropic SDK integration](https://docs.getbifrost.ai/integrations/anthropic-sdk/overview) · [new-api Native Claude Format](https://docs.newapi.pro/en/docs/api/ai-model/chat/createmessage) · [one-api README](https://github.com/songquanpeng/one-api) (all retrieved 2026-07-29)
- Issue-count figures ("claude code" in tracker: LiteLLM 465 · new-api 138 · Portkey 6) — GitHub issue search API, queried 2026-07-29

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every claim above is dated and linked so you can re-check it; if a linked issue is fixed or a probe result changes, that's a PR we want.*
