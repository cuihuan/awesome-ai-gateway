# MCP & Agent Gateways — why agent traffic is not completion traffic

*Last updated 2026-07-29 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

**Languages:** English · [简体中文](mcp-agent-gateways.zh-CN.md)

> 📊 **Key numbers** · The Model Context Protocol was rewritten on **2026-07-28**, the day before this chapter. Revision **2026-07-28** was published **2026-07-28T16:47:49Z** (tag → commit `5f5440bb26a62e2cf3440b92da5a667efa03b267`, confirmed via `gh api` on 2026-07-29) and is the **only** spec revision published in calendar 2026 — the `schema/` directory at that tag holds exactly six entries: `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`, `2026-07-28`, `draft`. It **deletes sessions**: the `Mcp-Session-Id` header, the `initialize` handshake, the Streamable HTTP GET stream and `Last-Event-ID` resumability are all gone, and a conforming server is told to answer a GET with **`405 Method Not Allowed`**. Of the **six** client↔server era combinations the spec's own compatibility matrix enumerates, **two fail outright** — so a gateway is the compatibility shim for at least the **twelve-month** minimum deprecation window the new lifecycle policy defines. An MCP gateway carries **six duties an LLM gateway does not** (§1); **two** are anchored in MUST-level spec text, the rest in SHOULD-level or vendor practice, one follows from the transport pages, and one — **audit of tool invocations — has no protocol primitive at all**, only a client-side SHOULD ("*Log tool usage for audit purposes*"). Secret brokering is not a feature, it is mandated: "*MCP servers **MUST NOT** accept or transit any other tokens*". And the dominant 2026 vulnerability class is **not** tool-RBAC failure — of the **41** CVEs published in 2026 matching "Model Context Protocol" (our own NVD keyword query, 2026-07-29, method caveats in §8.1), the recurring root cause is **DNS rebinding / missing `Origin` and `Host` validation**, which hit the Rust SDK, the Go SDK and Google's MCP Toolbox independently. This repo lists **26** MCP & agent gateways (the [MCP & agent gateways](../README.md#-mcp--agent-gateways) section, counted 2026-07-29) and, until this chapter, carried **zero** MCP protocol coverage and **no data file** for the category.

Chapters 1 and 4–6 all assume the same client: something that sends a prompt and reads a completion. This chapter is about the other client. When the caller is an agent, the gateway stops mediating *text* and starts mediating *verbs* — `tools/call name=delete_repo` is a request to do something, on someone's behalf, using someone's credential, chosen by a model that just read attacker-controllable input. Every governance primitive an LLM gateway ships — model allow-lists, token budgets, rate limits — is aimed at the wrong noun.

Sourcing convention, same as the rest of the handbook: spec text is quoted verbatim from the revision-`2026-07-28` pages with a retrieval date of 2026-07-29, including the vendor's own hedges; gateway behaviour is read from source at pinned commits listed in the appendix; CVEs are fetched from CVE.org's or NVD's API and quoted; GitHub PR merge status is confirmed via `gh api`; arithmetic and inference are marked **ours**; figures from this repo's files are marked *repo-sourced* with their `as_of`. Where something is not established, it says so in place.

---

## 1. The concept in 60 seconds

The difference is not "agents send more requests." It is that **six separate properties of a request change at once**, and each one breaks a different piece of gateway machinery.

| Axis | Completion traffic | Agent / MCP traffic | What breaks |
|---|---|---|---|
| **Unit of authorization** | a *model* + a budget | a **verb** — `tools/call` with `params.name` | Model allow-lists cannot express "may read Jira, may not delete Jira" |
| **Who chose to send it** | a human, in the loop | the **model**, autonomously — tools are "**model-controlled**" per spec | Consent has to be brokered, not assumed |
| **Whose credential is used** | the gateway's provider key | a **third party's** OAuth token, per end user | Key injection is no longer sufficient; you need delegation |
| **What is attacker-controlled** | the user prompt | the user prompt **plus every tool description and every tool result** | Input filtering at the front door misses the whole rear channel |
| **What a failure looks like** | HTTP 4xx/5xx | frequently **HTTP 200** with `isError: true` inside the body | Status-code metering scores a broken tool at 100% success |
| **What state exists** | conversation, client-side | **none, as of 2026-07-28** — sessions were removed from the protocol | Session-affinity routing is no longer a protocol requirement |

The framing that stays useful: **an LLM gateway decides what a model may say; an MCP gateway decides what an agent may do.** The spec is explicit that it cannot enforce the second itself — "*While MCP itself cannot enforce these security principles at the protocol level, implementors **SHOULD**: 1. Build robust consent and authorization flows into their applications …*" That sentence is the entire product category's reason to exist.

### The six duties, and how well each is anchored

**Ours**, synthesised from the spec text quoted throughout this chapter — the point of the right-hand column is that two of six rest on strict MUST-level spec text, two more on MUST/MAY-adjacent wording you can still hold a vendor to, and one is a hole.

| # | Duty | Anchor strength | Where |
|---|---|---|---|
| 1 | **Per-tool authorization** — authorize a *verb*, not a model | **MUST/MAY-level**: lists "*MAY vary by the authorization presented on the request*"; shortfalls signalled per-operation via `WWW-Authenticate` `insufficient_scope` | §4 |
| 2 | **Consent brokering** — per-client consent before forwarding to a third-party AS | **MUST**, and it names proxies explicitly | §5.2 |
| 3 | **Secret brokering** — never pass the client's token upstream | **MUST NOT**, twice, in two different pages | §5.1 |
| 4 | **Audit of invocations** | ⚠️ **client-side SHOULD only** — no protocol primitive, no conversation id since sessions were removed | §8.4 |
| 5 | **Transport bridging** — stdio ↔ Streamable HTTP | derived from the transport pages: stdio "*SHOULD NOT*" use the auth spec at all | §5.4 |
| 6 | **Dual-era translation** | **MUST**-adjacent: two of six era combinations fail, under a 12-month deprecation floor | §2.3 |

---

## 2. The protocol surface a gateway must govern

### 2.1 What revision 2026-07-28 changed

Every row below is from the [official changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), with the SEP's merge status confirmed via `gh api` (all `merged=true`).

| Change | Verbatim spec text | SEP · merged | Gateway consequence |
|---|---|---|---|
| **Sessions removed** | "*Remove protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP transport. List endpoints (`tools/list`, `resources/list`, `prompts/list`) no longer vary per-connection.*" | [#2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567) · 2026-05-07 | Sticky routing is no longer a protocol obligation (§7) |
| **Handshake removed** | "*Make MCP stateless: remove the `initialize`/`notifications/initialized` handshake. Every request now carries its protocol version and client capabilities in `_meta`*" | [#2575](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575) · 2026-05-11 | Per-request `_meta` validation; missing required fields → `-32602` + **HTTP 400** |
| **`server/discover` added** | "*Add `server/discover`: servers MUST implement this RPC to advertise their supported protocol versions, capabilities, and identity.*" | #2575 | The new capability-advertisement point a federating gateway must synthesise |
| **Server-initiated requests abolished** | "*Multi Round-Trip Requests (MRTR) pattern introduced which replaces the previous approach of sending server-initiated requests, such as `roots/list`, `sampling/createMessage`, or `elicitation/create`.*" | [#2322](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2322) · 2026-05-06 | "*No other message direction exists*" — a proxy only ever forwards client→server requests |
| **Resumability removed** | "*A broken response stream loses the in-flight request; clients **MUST** re-issue it as a new request with a new request ID*" | #2575 | `Last-Event-ID` must be ignored; GET/DELETE → `405` |
| **Roots, Sampling, Logging deprecated** | "*These features remain fully functional during the deprecation window but new implementations should not add support for them.*" | [#2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577) · 2026-05-15 | Suggested migrations name **OpenTelemetry** in place of MCP Logging |
| **12-month lifecycle policy** | "*a minimum twelve-month deprecation window, and a registry of deprecated features*" | [#2596](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2596) · 2026-05-18 | Dual-era translation is a durable duty, not a transition |
| **DCR deprecated** | "*Deprecate the OAuth 2.0 Dynamic Client Registration Protocol (RFC7591) as a client registration mechanism in favor of Client ID Metadata Documents*" | landed inside PR #2858 — see caveat below | Client identity becomes an `https` URL that must match its document exactly |
| **Tasks moved out of core** | "*Move experimental tasks out of the core protocol and into an official extension (`io.modelcontextprotocol/tasks`)*" | [#2663](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2663) · 2026-05-15 | Extensions are capability-negotiated; a gateway must negotiate or degrade, never blindly pass through |

> ⚠️ **Citation caveat, stated so nobody propagates it wrong.** The changelog attributes the DCR deprecation to PR **#2858**, but `gh api repos/modelcontextprotocol/modelcontextprotocol/pulls/2858` (2026-07-29) returns `title="Authorization spec split"`, `merged=true`, `merged_at=2026-06-04T19:16:55Z`. The deprecation is real and normative — the client-registration page carries a Warning box reading "*Dynamic Client Registration is deprecated. New implementations should use Client ID Metadata Documents instead.*" — but **do not describe #2858 as a dedicated DCR-deprecation PR**; it landed as part of the authorization spec split.

Release timing, because it will be checked: the RC blog post says the candidate "*is locked as of*" **May 21, 2026** and calls the validation period a "**ten-week window**" — that is the vendor's phrasing, and May 21 → Jul 28 is 68 days (9.7 weeks). The machine-checkable figures are the GitHub tags: `2026-07-28-RC` published **2026-05-29T12:51:22Z**, `2026-07-28` published **2026-07-28T16:47:49Z**. Cite the tags as fact and "ten-week" as attributed prose.

### 2.2 Three primitives, three different owners — three different policy classes

A gateway that applies one policy engine uniformly across MCP has already made a mistake, because the spec assigns each primitive a different controller:

| Primitive | Verbatim | Methods | The policy class it needs |
|---|---|---|---|
| **Tools** | "*Tools in MCP are designed to be **model-controlled**, meaning that the language model can discover and invoke tools automatically*" | `tools/list`, `tools/call` | Per-verb authorization + consent + audit. This is the dangerous one |
| **Prompts** | "*Prompts are designed to be **user-controlled** … This refers to who decides when the prompt is used, not who authors its content. Prompt content is defined by the server.*" | `prompts/list`, `prompts/get` | Content provenance — the *server* writes the text the user selects |
| **Resources** | "*Resources in MCP are designed to be **application-driven**, with host applications determining how to incorporate context based on their needs.*" | `resources/list`, `resources/read`, `resources/templates/list` | Data-access control and residency |

All three carry the same hedge — "*implementations are free to expose [them] through any interface pattern that suits their needs—the protocol itself does not mandate any specific user interaction model*" — which is precisely the freedom a gateway is bought to constrain.

### 2.3 The era matrix — where a gateway is load-bearing

The spec defines "**Modern**" (2026-07-28+, per-request metadata), "**Legacy**" (2025-11-25 and earlier, `initialize` handshake) and "**Dual-era**". Its compatibility matrix enumerates six combinations:

| Client era | Server era | Outcome |
|---|---|---|
| Modern | Modern | ✅ works |
| Modern | Legacy | ❌ **fails** — "*The server may reject the request with an implementation-defined error, stay silent, or even process an era-ambiguous method under legacy semantics*" |
| Legacy | Modern | ❌ **fails** — "*Legacy clients have no fall-forward mechanism*" |
| Dual-era | Modern | ✅ works |
| Dual-era | Legacy | ✅ works |
| Legacy | Dual-era | ✅ works |

**Two of the six fail, and both failures are silent-capable.** Era detection is transport-specific — on stdio, probe `server/discover`, and "*The fallback **MUST NOT** be keyed to one specific error code*"; on HTTP, attempt a modern request and inspect the body of a `400`. "*The era determination is a property of the server, not of an individual request. Clients **SHOULD** cache the result for the lifetime of the server process (stdio) or origin (HTTP).*" Combined with the 12-month floor on deprecation, **dual-era translation is a gateway duty through at least mid-2027.**

---

## 3. Traffic shape — what a `tools/call` puts on the wire

### 3.1 The 2026 transport was redesigned *for* intermediaries

This is the single most gateway-relevant thing in the revision, and it is stated as intent, not inferred: "*The Streamable HTTP transport mirrors selected JSON-RPC body fields into HTTP headers so that intermediaries (load balancers, gateways, observability tooling) can route and inspect requests without parsing the body.*"

| Header | Source field | Required on |
|---|---|---|
| `Mcp-Method` | `method` | all requests — "*These headers are **REQUIRED** for compliance*" |
| `Mcp-Name` | `params.name` or `params.uri` | `tools/call`, `resources/read`, `prompts/get` |
| `MCP-Protocol-Version` | — | every POST |
| `Mcp-Param-{Name}` | a tool argument annotated `x-mcp-header` | opt-in per server; "*clients **MUST** support this feature*" |

And the spec pre-empts the split-brain bug that mirrored headers invite: "*Servers that process the request body **MUST** reject requests where the values specified in the headers do not match the corresponding values in the request body. This prevents potential security vulnerabilities when different components in the network rely on different sources of truth (e.g., a load balancer routing on the header value while the MCP server executes based on the body value).*" Rejection is `400` + JSON-RPC **`-32020` (`HeaderMismatch`)**. Two clauses bind intermediaries directly: they "***MUST** return an appropriate HTTP error status … but are not required to return a JSON-RPC error response*", and — the one to put in your config review — intermediaries enforcing policy on mirrored headers "***SHOULD** verify that the `MCP-Protocol-Version` header indicates a version that requires header–body validation. If the version is older or the header is absent, the intermediary **SHOULD** reject the request rather than trusting unvalidated header values.*"

Compare that to the LLM-gateway auth-bypass CVE cluster this repo tracks in its [supply-chain matrix](../README.md#-supply-chain-security--who-signs-their-releases-and-what-actually-got-hacked): same forgeable-header shape, opposite outcome — here the standard writes the mitigation down first.

`x-mcp-header` deserves its own line because it is a data-residency routing key in disguise (the spec's own worked example promotes a Spanner `execute_sql` tool's `region` argument). It is heavily constrained — primitive types only, "*Parameters with type `number` are not permitted*", statically reachable from the schema root only (not through `items`, `oneOf`/`anyOf`/`allOf`/`not`, `if`/`then`/`else` or `$ref`), case-insensitively unique, no CR/LF — and clients "***MUST** reject tool definitions where any `x-mcp-header` value violates these constraints*" by dropping that tool from `tools/list`. The security hedge is verbatim: "*Server developers **SHOULD NOT** mark sensitive parameters (passwords, API keys, tokens, PII) with `x-mcp-header`, as header values are visible to network intermediaries.*"

### 3.2 The metering trap: a failed tool call is usually a 200

MCP deliberately bifurcates errors. **Protocol errors** ("*Unknown tool; Malformed requests …; Server errors*") come back as JSON-RPC errors. **Tool execution errors** ("*API failures; Input validation errors …; Business logic errors*") are "*reported in tool results with `isError: true`*", because "*Clients **SHOULD** provide tool execution errors to language models to enable self-correction.*"

**Consequence, ours:** a gateway that meters, alerts or SLOs on HTTP status alone will report a **100% success rate on a completely broken tool**. Every failed `tools/call` in the execution-error class is an HTTP 200 with a `result` body. This is the MCP analogue of chapter 5's finding that four of six gateways return a truncated stream that *looks* successful — same class of blindness, different layer. Also renumbered in this revision: resource-not-found moved from `-32002` to `-32602`, with clients SHOULD still accepting `-32002` from older servers, and the server-error range is now carved in two — `-32000..-32019` legacy ("*receivers **MUST NOT** assume any specific meaning for these codes*") and `-32020..-32099` reserved for the spec (`-32020` HeaderMismatch, `-32021` MissingRequiredClientCapability, `-32022` UnsupportedProtocolVersion).

### 3.3 Cacheable lists — and `cacheScope`, defined in terms of shared gateways by name

New in 2026: `tools/list`, `prompts/list`, `resources/list`, `resources/read` and `resources/templates/list` results carry required `ttlMs` and `cacheScope` fields ([SEP #2549](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2549), merged 2026-05-15). The scope definitions name us explicitly:

| `cacheScope` | Verbatim |
|---|---|
| `"public"` | "*The response does not contain user-specific data. Any client, shared gateway, or caching proxy **MAY** store and serve the cached response to any user.*" |
| `"private"` | "*The response contains private data that is not meant to be shared between callers. Cached responses **MAY** be reused for the same authorization context. Caches **MUST NOT** be shared across authorization contexts (e.g. a different access token requires a different cache).*" |

The trap is stated by the spec itself: "*Servers MUST be aware that responses with a `"public"` `cacheScope` may be shared between callers even if the Result is coming from an authenticated endpoint*", and implementors "*MUST apply appropriate per-primitive access controls, and MUST NOT rely on `cacheScope` alone*". MRTR retry results carrying `inputResponses` or `requestState` "***MUST NOT** be cached*". This is [chapter 6 §4](caching-economics.md)'s cache-key problem with the answer written down in advance — the difference being that in the LLM world most gateway caches put no tenant in the key at all — see the cache-key table in [chapter 6](caching-economics.md).

---

## 4. Tool-level authorization — the verb, not the model

The spec sanctions per-tool authorization at both ends. **Discovery** may be filtered: "*Servers that declare the `tools` capability **MUST** respond to `tools/list` requests with the set of tools currently available to the requesting client. This set **MAY** be empty and **MAY** change over time …, but **MUST NOT** vary per-connection or as a side effect of other requests on the connection. The set **MAY** vary by the authorization presented on the request — for example, returning only the tools the caller's granted scopes permit — since credentials are per-request input, not connection state.*" **Runtime** shortfalls get a step-up challenge: `HTTP 403` plus `WWW-Authenticate: Bearer error="insufficient_scope", scope="…", resource_metadata=…`, with clients required to "*treat the scopes provided in the challenge as authoritative*" and to request the **union** of prior and challenged scopes; servers "***MUST** account for scope hierarchies*".

What the listed gateways actually implement, read from source at the pinned commits in the appendix:

| Gateway | Mechanism | Default posture | Where it lives |
|---|---|---|---|
| **agentgateway** | CEL rule sets over `ResourceType::{Tool, Prompt, Resource}` (`McpAuthorization`) | **allow-all** — `McpAuthorizationSet::validate` short-circuits to `true` when `!self.0.has_rules()` | Apache-2.0 OSS (`crates/agentgateway/src/mcp/rbac.rs`) |
| **Envoy AI Gateway** | `MCPRoute` CRD: rules match tools against JWT scopes/claims ("*Scopes and claims are AND-ed*"), plus experimental CEL over `request.mcp.tool`/`.method`/`.backend`/`.params`; first-match-wins, max 32 | **`Deny`** (`+kubebuilder:default:=Deny`) | Apache-2.0 OSS, but **`api/v1beta1`** — not v1 |
| **Pomerium** | `mcp_tool` policy criterion — "*matches tool names by exact name, prefix, suffix, or list — enabling deny-based block lists and allowlists*" | policy-defined | Apache-2.0 OSS (`pkg/policy/criteria/mcp_tool.go`) |
| **ToolHive (Virtual MCP)** | Cedar policy + OIDC; per-tool **per-user** rate limiting, gated by a CEL rule requiring `incomingAuth.type: oidc` | policy-defined; "*vMCP runtime authz middleware is Cedar-only*" | Apache-2.0 OSS (`virtualmcpserver_types.go`) |
| **Kong AI Gateway** | MCP Tool ACLs on Consumers/Consumer Groups — "*Kong intercepts the response from your upstream API and filters the tool list based on the authenticated user's permissions*" | default-deny posture supported | **Enterprise only** — `tier: ai_gateway_enterprise`; Kong OSS at `391ee48` has **zero** paths matching "mcp" |
| **Lunar MCPX** | Tool-group ACL resolved across `consumers` / `clientNames` / `defaultConsumer`; `Permission = "allow" \| "block"`, per-consumer `default-allow` (block-list) or default-block (allow-list) | per-consumer config | MIT (`mcpx/LICENSE.MD`) — but see the tier caveat in §9 |
| **Docker MCP Gateway** | Static `--tools` enable-list + `--interceptor` + `--block-secrets` (default `true`) + `--verify-signatures` (default `true`) | enable-list, **identity-free** | MIT. `docker mcp policy` is "*Manage secret policies*", **not** tool authorization |

**Two of these differ on the axis that matters most and it is not a feature-matrix column.** agentgateway's empty rule set means *allow everything*; Envoy AI Gateway's `MCPRoute` defaults to *Deny*. Same category, same open-source licence, opposite failure direction when someone ships an incomplete config.

**And Docker MCP Gateway is the entry this repo currently describes wrong.** Per-tool *enablement* is a deployment-time list; per-tool *authorization* answers "which caller". Only the first is what `--tools` provides.

---

## 5. Secret brokering and OAuth on-behalf-of

### 5.1 The spec makes brokering mandatory, not optional

An MCP server "*acts as an OAuth 2.1 resource server*", "***MUST** implement OAuth 2.0 Protected Resource Metadata (RFC9728)*", and clients "***MUST** use OAuth 2.0 Protected Resource Metadata for authorization server discovery*". The basis documents are IETF drafts — `draft-ietf-oauth-v2-1-13` and `draft-ietf-oauth-client-id-metadata-document-00` — which is worth knowing before anyone calls this "the OAuth 2.1 standard".

Then the boundary clause, which is the whole reason secret brokering is a gateway product:

> "*MCP clients **MUST NOT** send tokens to the MCP server other than ones issued by the MCP server's authorization server. MCP servers **MUST** only accept tokens that are valid for use with their own resources. MCP servers **MUST NOT** accept or transit any other tokens.*"

and

> "*If the MCP server makes requests to upstream APIs, it may act as an OAuth client to them. The access token used at the upstream API is a separate token, issued by the upstream authorization server. The MCP server **MUST NOT** pass through the token it received from the MCP client.*"

**The agent therefore structurally never holds the downstream credential.** The stated risks of getting this wrong are Security Control Circumvention, Accountability and Audit Trail Issues, Trust Boundary Issues and Future Compatibility Risk — including, verbatim: "*If the MCP Server passes tokens without validating their claims (e.g., roles, privileges, or audience) or other metadata, a malicious actor in possession of a stolen token can use the server as a proxy for data exfiltration.*"

RFC 8707 resource indicators are the audience-binding half, and the MUST is unusually strong: the `resource` parameter "***MUST** be included in both authorization requests and token requests*", "***MUST** identify the MCP server that the client intends to use the token with*", "***MUST** use the canonical URI*" — and clients "***MUST** send this parameter regardless of whether authorization servers support it.*" Note the security page's own hedge, which the marketing never carries: resource indicators "*provide critical security benefits by binding tokens to their intended audiences **when the Authorization Server supports the capability**.*"

### 5.2 The confused-deputy MUST that names gateways directly

This is the strongest gateway-specific normative text in the whole specification, and it is a MUST:

> "*MCP proxy servers using static client IDs **MUST** obtain user consent for each dynamically registered client before forwarding to third-party authorization servers (which may require additional consent).*"

"MCP Proxy Server" is a defined term — "*An MCP server that connects MCP clients to third-party APIs, offering MCP features while delegating operations and acting as a single OAuth client to the third-party API server*" — i.e. exactly what almost every entry in this repo's MCP section is. The Required Protections are prescriptive enough to be a checklist: a per-user registry of approved `client_id` values checked "***before** initiating the third-party authorization flow*"; a consent UI that identifies "*the requesting MCP client by name*" and shows "*the registered `redirect_uri` where tokens will be sent*", with CSRF protection and "*Prevent iframing via `frame-ancestors` CSP directive or `X-Frame-Options: DENY`*"; consent cookies using the "*`__Host-` prefix*" with "*`Secure`, `HttpOnly`, and `SameSite=Lax`*", bound to the specific `client_id` "*(not just "user has consented")*"; exact-string `redirect_uri` matching; and single-use `state` whose cookie "***MUST NOT** be set until **after** the user has approved the consent screen.*"

### 5.3 Who actually brokers, and at what price

| Gateway | Client-facing auth | Upstream credential | RFC 8693 token exchange / OBO | Licence reality |
|---|---|---|---|---|
| **agentgateway** | JWT validation (Strict/Optional/Permissive) with `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server`; IdPs Auth0, Okta, Descope, Keycloak, Authentik, Entra | `BackendAuthKind::{Passthrough, Key, Gcp, Aws, Azure, Copilot}`, key redacted on serialize | ✅ `"urn:ietf:params:oauth:grant-type:token-exchange"` in `src/http/oauth.rs`, `apply_token_exchange(...)`, plus an e2e test titled "*End-to-end on-behalf-of (OBO) token exchange over a CONNECT tunnel*" with a mock STS | **Apache-2.0, in-tree** |
| **Archestra** | OIDC + SAML SSO | secrets vault | ✅ `entra-obo-strategy.ts` and `rfc8693-token-exchange.ts` | ⚠️ **Enterprise-licensed.** Both files begin `// SPDX-License-Identifier: LicenseRef-Archestra-Enterprise`; 59 paths are enterprise-marked. The dual-LLM guardrail (`dual-llm.ts`) has no SPDX header and **is** AGPL-3.0-only |
| **Kong AI Gateway** | `ai-mcp-oauth2` plugin | — | ✅ documented, token exchange from **v3.14+**, min Gateway 3.12 | **Enterprise only** (`tier: ai_gateway_enterprise`) |
| **Pomerium** | identity-aware proxy | "*MCP-aware bridge that manages upstream OAuth on behalf of your users*" (vendor docs) | not verified in this pass | Apache-2.0 tree contains the MCP code |
| **Envoy AI Gateway** | `MCPBackendSecurityPolicy.APIKey` from a k8s `secretRef` or `inline`, injected into a header (default `Authorization`, `Bearer` prefix) or a query param | key injection only | ❌ not found in this pass | Apache-2.0. Its own API doc warns: "*Embedding credentials in URLs (including query parameters) is generally not recommended because URLs can be exposed in logs and intermediary systems; prefer header-based injection when possible.*" |
| **Lunar MCPX** | **static API key** — `x-lunar-api-key`, 401 absent / 403 wrong, and a **no-op guard** when `auth.enabled` is false or no key is set | outbound OAuth authorization-code flow (`/oauth/callback` → `completeOAuthByState`) + `staticOauth` literals | ❌ — grep for `on-behalf-of\|obo\|token_exchange\|urn:ietf:params:oauth:grant-type:token-exchange` over `mcpx-server/src` returns **zero** matches | MIT code (§9 caveat) |
| **Docker MCP Gateway** | — | credstore under `cmd/docker-mcp/secret-management/`, `--block-secrets` default `true` | ❌ | MIT |

Lunar MCPX also ships the cleanest *scoping* design read this pass, worth quoting because it is a design property rather than a feature: three purpose-separated buckets in `env-var-manager.ts` — `profileSecrets`, `oauthCredentials`, `prefilledLiterals` — with the file's own comment stating "*The three scopes don't share a primary map, so a user-controlled profile secret cannot be reached by OAuth-name lookups and vice versa.*"

### 5.4 stdio has no auth layer at all — which is the whole argument for a gateway

"*Implementations using an HTTP-based transport **SHOULD** conform to this specification. Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment.*" A gateway bridging stdio↔Streamable HTTP is therefore not doing a cosmetic transport conversion: it must **originate the entire OAuth story**, synthesise the `_meta` block and the `Mcp-Method`/`Mcp-Name` headers, and translate cancellation semantics — on stdio the client "***MUST** send a `notifications/cancelled` notification*", while on Streamable HTTP "*Closing the SSE response stream **MUST** be treated by the server as cancellation of that request.*"

And the proxy architecture gets its own attack section, opening with a hedge worth reproducing exactly: "*The `stdio` transport itself is not inherently vulnerable. However, in proxy architectures where a separate proxy service manages `stdio` connections and can spawn MCP servers as child processes, it can provide a critical escalation path from web-based attacks to full system compromise.*" Followed by: "***Important**: This attack vector only applies to MCP implementations that use a proxy architecture, not to direct `stdio` transport usage.*" The mitigations are SHOULDs and read as a spec for ToolHive/Docker-style container isolation: "*Implement sandboxing or containerization for spawned processes; Restrict file system access for spawned MCP servers; Log all `stdio` transport usage for security monitoring; Require additional authorization for potentially dangerous commands.*"

---

## 6. Prompt injection through tools — the exposure no gateway closes

### 6.1 The framing, and its author's own hedge

Simon Willison's "**The lethal trifecta for AI agents: private data, untrusted content, and external communication**" (16th June 2025) names the three legs verbatim: "*Access to your private data—one of the most common purposes of tools in the first place! Exposure to untrusted content—any mechanism by which text (or images) controlled by a malicious attacker could become available to your LLM. The ability to externally communicate in a way that could be used to steal your data*". **An MCP gateway is, definitionally, a machine for assembling all three in one place.**

The honest part is his, not ours: "*we still don't know how to 100% reliably prevent this from happening.*" And on the vendors selling into this gap, with his own emphasis preserved: "*I am _deeply suspicious_ of these: If you look closely they'll almost always carry confident claims that they capture '95% of attacks' or similar... but in web application security 95% is very much a failing grade.*"

### 6.2 Two injection channels, both with CVEs

**Tool descriptions.** Willison, "Model Context Protocol has prompt injection security problems" (9th April 2025): "*MCP tools can mutate their own definitions after installation. You approve a safe-looking tool on Day 1, and by Day 7 it's quietly rerouted your API keys to an attacker*" and "*Malicious instructions are tucked away in the tool descriptions themselves—visible to the LLM, not normally displayed to users.*" The spec agrees and makes it a client MUST: "*clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers*", and, in the top-level principles, "*Tools represent arbitrary code execution and must be treated with appropriate caution.*"

**Tool results.** The cleanest primary source is a vendor's own CVE against its own MCP server. **CVE-2026-13341**, assigned by Kong, published 2026-07-03, CVSS **7.4 HIGH**: "*A vulnerability exists in the Kong Konnect Model Context Protocol (MCP) server prior to version 1.0.0, which could allow a remote attacker to perform an indirect prompt injection attack and execute unintended API requests.*" The injected content arrives **inside analytics data the tool returns** — not in the user prompt. A second instance: **CVE-2026-44192** (2026-07-22, CVSS 6.6) against the Ansible Lightspeed MCP server.

**Exfiltration.** **CVE-2025-34072** (VulnCheck, 2025-07-02, CVSS 4.0 base **9.3 CRITICAL**) against Anthropic's deprecated Slack MCP Server: "*When an AI agent using the Slack MCP Server processes untrusted data, it can be manipulated to generate messages containing attacker-crafted hyperlinks embedding sensitive data. Slack's link preview bots (e.g., Slack-LinkExpanding, Slackbot, Slack-ImgProxy) will then issue outbound requests to the attacker-controlled URL, resulting in zero-click exfiltration of private data.*" **Read the exfiltration channel carefully: it is a third-party unfurl bot, not the agent.** A gateway egress allow-list on the agent's own connections does not stop it. That is the most important architectural fact in this section.

### 6.3 The spec concedes it cannot enforce consent — and that is the product gap

Key principles, verbatim: "*Users must explicitly consent to and understand all data access and operations*"; "*Hosts must obtain explicit user consent before invoking any tool*". Tools page Warning: "*For trust & safety and security, there **SHOULD** always be a human in the loop with the ability to deny tool invocations.*" And then the concession quoted in §1: MCP "*cannot enforce these security principles at the protocol level*".

What the listed gateways ship against this, stated as capability presence rather than efficacy — **nobody in this section has published a methodology we would accept as a detection-rate measurement, and per §6.1 you should be suspicious of any that appears**:

| Project | Mechanism | Licence note |
|---|---|---|
| **Archestra** | deterministic dual-LLM / "lethal trifecta" guardrail (`platform/backend/src/agents/subagents/dual-llm.ts`) | **AGPL-3.0-only** — no SPDX header, so the default route applies. Unlike its OBO code (§5.3) |
| **agentgateway** | `mcpGuardrails` external policy hooks: `Outcome<T>::{Pass, Mutated(T), Reject(ErrorData)}`, request/response phases, "*the first to reject a request short-circuits the chain*" | Apache-2.0 |
| **fak**, **Armorer Guard**, **Lasso MCP Gateway** | default-deny capability allow-list with result quarantine; stdio-wrapping argument inspection; plugin guardrails + secret masking | repo-sourced from the [list](../README.md#-mcp--agent-gateways), not source-read this pass |
| **toolport**, **mcpproxy-go** | tool integrity checks + quarantine of newly-seen servers — the direct answer to the Day-1/Day-7 rug pull | repo-sourced, not source-read this pass |

---

## 7. Session and state handling — the differentiator the spec just deleted

Through 2025-11-25, session affinity was a genuine MCP gateway problem: `Mcp-Session-Id` needed sticky routing, DELETE terminated a session, and `Last-Event-ID` resumability meant a load balancer had to return a client to the same replica. As of 2026-07-28: "*The Model Context Protocol (MCP) is a **stateless protocol**: all the information needed to process a request is contained in the request itself. A server processes each request independently; no state should be inferred from previous requests, even those on the same connection or stream.*" And: "*Servers **MUST NOT** rely on prior requests over the same connection to establish context.*" Legacy traffic is to be handled by ignoring it — "*An `Mcp-Session-Id` header on a request: ignore it, and do not mint or echo session IDs. A `Last-Event-ID` header: ignore it; streams are not resumable.*"

State that must span calls is now explicit: servers mint a handle and receive it back "*as an ordinary tool argument on each request*" ([SEP #2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567), merged 2026-05-07). The named attack changed with it. "Session Hijacking" is **gone** from the current best-practices page, replaced by **State Handle Hijacking**, whose mitigation is a two-line gateway requirement:

> "*MCP servers that implement authorization **MUST** verify all inbound requests. MCP servers **MUST NOT** treat possession of a state handle as authentication.*"

Plus SHOULDs: non-deterministic handles from a secure RNG, expiry, and binding "*handles server-side to the authenticated user, for example by keying stored state as `<user_id>:<handle>` where the user ID is derived from the verified token rather than supplied by the client.*" The tools page says the same in design language: "*For authenticated servers, a handle is a name, not a capability.*" The old guidance is not deleted, just relocated — the page explicitly redirects readers to "*Session Hijacking in the 2025-11-25 version of this page*".

> 🔶 **Demoted — ours, an inference, not spec text.** The spec says what changed; the claim that this **erodes the value proposition of session-routing MCP gateways** is our analysis. The reasoning: a conforming 2026-07-28 endpoint is an ordinary stateless HTTP POST endpoint that any commodity load balancer can round-robin, and list results "***MUST NOT** vary per-connection*". The vendor concedes the migration cost in its own words — "*there will be some migration cost, especially for developers that did depend on session identifiers*" — but says nothing about product categories. This is directly testable against the two entries in this repo that sell sessions as a headline (§10, step 5), and **we have not tested it**.

---

## 8. Failure modes, with receipts

### 8.1 The dominant 2026 class is DNS rebinding, not authorization

The same root cause landed independently in five codebases, each with its own CVE:

| CVE | Target | Published · CVSS | Verbatim |
|---|---|---|---|
| **CVE-2026-42559** | Rust `rmcp` < 1.4.0 | 2026-05-14 · 8.8 | "*did not validate the incoming Host header. This allowed a malicious public website, via a DNS rebinding attack, to send authenticated requests to an MCP server running on the victim's loopback or private-network interface*" |
| **CVE-2026-34742** | MCP Go SDK < 1.4.0 | 2026-04-02 · 7.6 | "*does not enable DNS rebinding protection by default for HTTP-based servers*" |
| **CVE-2026-11624** | Google MCP Toolbox for Databases < v0.25.0 | 2026-06-13 · 9.4 | "*users had no way to validate the origin's host*" |
| **CVE-2026-23744** | MCPJam inspector ≤ 1.4.2 | 2026-01-16 · 9.8 | "*MCPJam inspector by default listens on 0.0.0.0 instead of 127.0.0.1, an attacker can trigger the RCE remotely via a simple HTTP request*" (fixed 1.4.3) |
| **CVE-2026-33032** | Nginx UI ≤ 2.3.5 | 2026-03-30 · 9.8 | "*/mcp requires both IP whitelisting and authentication (AuthRequired() middleware), the /mcp_message endpoint only applies IP whitelisting - and the default IP whitelist is empty, which the middleware treats as 'allow all'*" |

**The recurring assumption is that loopback equals trusted, and no amount of tool-level RBAC in a gateway fixes it** — it must be fixed at the MCP server, or by never exposing servers directly. Which is, in fairness, the strongest architectural argument the gateway vendors have. The spec's own Streamable HTTP security section is three lines and all three are a gateway's job: "*Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding attacks*" (invalid → 403); "*When running locally, servers **SHOULD** bind only to localhost (127.0.0.1)*"; "*Servers **SHOULD** implement proper authentication for all connections.*"

**On the 41 figure.** NVD keyword search for "Model Context Protocol", queried 2026-07-29, split into two windows because NVD caps a range at 120 days: 2026-01-01→2026-04-25 returned **23**, 2026-04-25→2026-07-29 returned **18**. Highest severities include CVE-2026-49257 (mcp-pinot, 10.0), CVE-2026-22792/22793 (5ire, 9.6), CVE-2026-32625 (LibreChat, 9.6), CVE-2026-15643 (AWS HealthLake MCP Server, 9.2). **Method caveat, ours:** keyword matching over-counts (products merely mentioning MCP) and under-counts (MCP flaws not using the phrase), and the boundary date appears in both windows so a same-day publication could double-count. Treat 41 as "**approximately 40, by this method on this date**", not a census.

### 8.2 SSRF — and the spec's recommended mitigation is literally a gateway

During OAuth metadata discovery a client fetches URLs from three **server-controlled** sources: the `resource_metadata` URL in `WWW-Authenticate`, `authorization_servers` in PRM, and the endpoints in AS metadata. "*MCP clients deployed to a server **MUST** consider SSRF risks and implement appropriate mitigations when fetching OAuth-related URLs. Which protections are appropriate depend on your network environment.*" The SHOULD list blocks `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `::1`, `169.254.0.0/16` "*(including cloud metadata endpoints)*", `fc00::/7`, `fe80::/10` — and then: "*For server-side MCP client deployments, operators **SHOULD** consider using an egress proxy that enforces network policies*", naming Stripe's Smokescreen. With a warning we would put in bold anyway: "*Avoid implementing IP validation manually. Attackers exploit encoding tricks (octal, hex, IPv4-mapped IPv6) that custom parsers often miss.*" Related: `$ref` in tool schemas — "*Implementations **MUST NOT** automatically dereference `$ref` values that resolve to a network URI*", opt-in fetching "***MUST** be disabled by default*".

### 8.3 Aggregation namespaces are the gateway's invention, not the protocol's

Every federating gateway in this repo's list — ContextForge, MetaMCP, 1MCP, mcpproxy-go, Nexus, ToolHive's virtual MCP — has to solve this, and the spec hands it to them without a mechanism: "*Tool name uniqueness is scoped to a single server. Clients or proxies that aggregate tools from multiple servers **MAY** encounter naming collisions (for example, two servers each exposing a `search` tool) and **SHOULD** implement a disambiguation strategy such as prefixing tool names with a server identifier. The server `name` (from `serverInfo`) is not guaranteed to be unique across servers and **SHOULD NOT** be relied upon for disambiguation.*" Reinforced elsewhere: `clientInfo` and `serverInfo` "*are self-reported by the sender and are not verified by the protocol*", and implementations "***SHOULD NOT** rely on them for security decisions.*"

### 8.4 Audit has no protocol primitive — the gap that lands on the gateway

The entire audit requirement in the tools spec is one client-side bullet: "*Log tool usage for audit purposes.*" Servers get "*Validate all tool inputs; Implement proper access controls; Rate limit tool invocations; Sanitize tool outputs.*" There is **no `notifications/audit`**, no required correlation identifier beyond the JSON-RPC `id`, and — because sessions were removed — **no protocol-level conversation identifier to group calls by**. The nearest thing the revision adds is W3C trace context: `traceparent`, `tracestate` and `baggage` are reserved `_meta` keys ("*As an exception to the prefix requirement*") whose values "***MUST** follow W3C Trace Context and W3C Baggage formats*" ([SEP #414](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/414)). **Trace context is standardised; audit content is not.** Per-call attribution is the gateway's to invent — which is why Lunar MCPX's `src/services/audit-log/` and Kong's "*All access attempts (allowed or denied) are written to the plugin's audit log*" are differentiators rather than table stakes.

### 8.5 Supply chain — including a checked negative

- **`postmark-mcp` was backdoored.** Cite **MAL-2025-47604** ("*Malicious code in postmark-mcp (npm)*", published 2025-09-26, OpenSSF malicious-packages feed via `api.osv.dev`), not the widely-reposted vendor blog. There is no CVE ID; the OSV record is the correct primary-source class for a trojaned package.
- **A gateway on this list has its own CVE.** **CVE-2025-47274** against ToolHive, published 2025-05-12, CVSS 4.0 base **2.4 LOW**: "*Due to the ordering of code used to start an MCP server container, versions of ToolHive prior to 0.0.33 inadvertently store secrets in the run config files … an attacker who has access to the home folder of the user who starts the MCP server can read secrets without needing access to the secrets store itself.*" Fixed in 0.0.33.
- **Foundational 2025 cluster**, each verified individually at CVE.org: **CVE-2025-49596** (MCP Inspector < 0.14.1, 9.4 CRITICAL — "*unauthenticated requests to launch MCP commands over stdio*"), **CVE-2025-6514** (`mcp-remote`, 9.6 — "*OS command injection … when connecting to untrusted MCP servers due to crafted input from the authorization_endpoint response URL*"), **CVE-2025-53109/53110** (filesystem server path-validation bypass, 7.3 each), **CVE-2025-52882** (Claude Code IDE extensions accepting "*unauthorized websocket connections*", 8.8).
- ✅ **A checked negative, published so nobody re-files it.** agentgateway's `Cargo.lock` contains **rmcp 0.10.0**, which matches GHSA-89vp-x53w-74fx / RUSTSEC-2026-0189 (the CVE-2026-42559 rebinding flaw, fixed 1.4.0). It is **not exposed**: `crates/agentgateway/Cargo.toml` line 112 pins the production dependency to `rmcp = { version = "3.0.0-beta.5", … }` under `[dependencies]`, while the 0.10.0 copy is `legacy-rmcp` at line 212, inside `[dev-dependencies]` (lines 191–226), with the in-file comment "*We need SSE client for testing but they removed it for some reason*". Dev-dependencies are not linked into the shipped binary, and OSV reports no advisories for rmcp 3.0.0-beta.5. **The naive lockfile grep produces a false positive here.**

### 8.6 What this chapter does *not* establish

- ❌ **Which MCP revision any listed gateway implements.** No product was source-read for revision support in this pass. Every claim of the form "gateway X supports 2026-07-28" is **INCONCLUSIVE** and needs a source-read at a pinned commit before publication. Two data points that are facts but are **not** answers: Envoy AI Gateway hard-codes `attribute.String("mcp.protocol.version", "2025-06-18")` in `internal/tracing/mcp.go` at `6722cca` (a tracing attribute, not proof of the data path's revision), and Lunar MCPX resolves `@modelcontextprotocol/sdk` **1.29.0** for `mcpx-server` in `package-lock.json` (the announcement's Tier-1 TypeScript SDK release is `2.0.0`, published 2026-07-27T23:55:41Z).
- ❌ **Whether the Tier-1 SDKs actually implement the 2026-07-28 wire format.** The announcement states "*All four Tier 1 SDKs speak `2026-07-28` as of today: TypeScript, Python, Go, and C#*" and that the Rust SDK "*supports the new spec in beta*". Release timing corroborates it (Python v2.0.0 2026-07-28T13:41:36Z, Go v1.7.0 13:09:53Z, C# v2.0.0 21:27:41Z, and `rmcp-v3.0.0` stable at 22:52:41Z — ~6h after the spec tag and after the blog's "beta" wording was written). **Release tags and timestamps were verified; SDK source was not.** Treat it as a vendor claim corroborated by timing.
- ❌ **Extension internals.** Tasks, MCP Apps and Skills-over-MCP were read only via the spec index blurb and changelog line. `subscriptions/listen` and the MRTR pattern pages were not read in full, and **`schema.ts` was not read** — the spec itself says the TypeScript schema is "*the source of truth for all protocol messages and structures*", so every shape claim here is from subordinate prose pages.
- ❌ **The circulating blogspam figures.** "150 million combined downloads", "9 of 11 MCP marketplaces", "30 CVEs in 60 days" appear across dev.to / practical-devsecops / agent-wars-class aggregators with **no primary source located** — no vendor advisory, no CVE record, no paper. **Do not repeat them.** The defensible figure is the one you can reproduce against NVD (§8.1).

---

## 9. How the listed gateways actually differ

Transport support is the first thing an evaluator needs and no entry in this repo currently states it. Read from source or vendor docs at the pinned commits in the appendix:

| Gateway | Downstream (client-facing) | Upstream (server-facing) | Tool authz | Licence / tier reality |
|---|---|---|---|---|
| **IBM ContextForge** | HTTP, JSON-RPC, WebSocket, SSE, stdio, streamable-HTTP (vendor README) | same, plus a `mcpgateway.translate --stdio … --expose-sse --expose-streamable-http` bridge | RBAC + "*user-scoped OAuth tokens and unconditional X-Upstream-Authorization header support*" | Apache-2.0 — **widest transport set read this pass** |
| **agentgateway** | SSE, Streamable HTTP | stdio, SSE, Streamable HTTP, **plus OpenAPI upstreams** | CEL, **allow-all when empty** | Apache-2.0. **Linux Foundation, not CNCF** (see the note under this table) |
| **Lunar MCPX** | Streamable HTTP, SSE | stdio, SSE, Streamable HTTP | tool-group ACL per consumer / client name | MIT files, **but** the repo README says "*It remains open-source at its core and free for non-production/personal use. For production environments, we offer advanced features through guided onboarding and platform tiers*" — in tension with MIT, which restricts nothing. No separate licence file gates the paid features, so **which capabilities are gated is unresolved from the repo alone** |
| **Envoy AI Gateway** | **Streamable HTTP only** on the data path (`MCPRoute.Path`, default `/mcp`; SSE is a response streaming mode, not a transport) | stdio only via the `aigw` CLI, which "*run[s] local Streamable HTTP proxies for each command*" | JWT scopes/claims + experimental CEL, **default `Deny`** | Apache-2.0; **v1.0.0 released 2026-06-23** but the MCP CRD is still `v1beta1` at `6722cca` (2026-07-23) |
| **ToolHive** | — | containerised MCP servers | Cedar + OIDC, per-tool per-user rate limits | Apache-2.0 |
| **Docker MCP Gateway** | — | containers | `--tools` enable-list (identity-free) | MIT |
| **Pomerium** | HTTP | — | `mcp_tool` criterion | Apache-2.0 tree carries the MCP code |
| **Kong AI Gateway** | — | — | MCP Tool ACLs, `tools/list` filtering by consumer | **Enterprise only**; Kong OSS `391ee48` has **zero** MCP paths in a full recursive tree, and 45 plugins of which 6 are `ai-*`, none MCP |
| **Tetrate Agent Router Service** | managed Envoy AI Gateway | — | inherits | SaaS. Vendor materials describe **model cost plus a 5% fee**; `router.tetrate.ai/pricing` returned **HTTP 404**, so the figure is blog/product-page sourced — re-check before printing it as hard |
| **Archestra** | — | — | RBAC/custom roles **Enterprise** | AGPL-3.0-only by default per `LICENSE.md`'s SPDX-header routing; **59 enterprise-marked paths** |

**Two rows above are not in this repo's MCP section, and both should be.** **Kong AI Gateway** (listed under [Enterprise & compliance](../README.md#-enterprise--compliance)) is described with no MCP mention at all, despite `ai-mcp-proxy`, `ai-mcp-oauth2` and `tools/list` filtering by consumer — the tier answer this repo prides itself on is missing too. **Envoy AI Gateway** (listed under [Kubernetes-native & inference infra](../README.md#-kubernetes-native--inference-infra)) is described only as "CNCF-aligned GenAI access on Envoy Gateway", with MCP appearing only in the news rows at :633 and :667 — while **Tetrate Agent Router Service**, the managed *resale* of that same engine, sits in the MCP section. The open-source original, carrying a default-`Deny` per-tool authorization CRD, is the more useful entry for a reader.

**One attribution correction the list needs.** agentgateway's own `CHARTER.md` at `7cd5647` opens "*Technical Charter (the "Charter") for agentgateway a Series of LF Projects, LLC*" and its README footer reads "*Agentgateway is a Linux Foundation project.*" The Linux Foundation press release is dated 2025-08-25; its only CNCF reference is an attributed quote from a CNCF Ambassador. Solo.io's separate project **kagent** is the CNCF Sandbox one. the [MCP & agent gateways](../README.md#-mcp--agent-gateways) section calls agentgateway a "CNCF proxy for agentic traffic" — that is wrong and should read "Linux Foundation". (README:286 "CNCF-aligned" for Envoy AI Gateway and :287 for kgateway are fine.)

**And one non-entry worth stating.** `katanemo/plano` at `6d315cc` is an MCP **client**, not a gateway: MCP appears as an outbound filter transport (`type: mcp`, `transport: streamable-http`, "*MCP filters call a specific tool on a remote MCP server*") and as Anthropic Messages passthrough types. There is no MCP tool RBAC, no MCP authorization module and no MCP server-side transport. Its placement outside this section is **correct** — recorded here so nobody "fixes" it.

---

## 10. Verify this yourself

Ordered by how fast they pay off. Nothing here needs a paid account.

1. **Confirm the spec revision and that it is the only 2026 one — 30 seconds.**
   ```bash
   gh api repos/modelcontextprotocol/modelcontextprotocol/git/ref/tags/2026-07-28 --jq '.object.sha'
   gh api "repos/modelcontextprotocol/modelcontextprotocol/contents/schema?ref=2026-07-28" --jq '.[].name'
   ```
   Expect `5f5440bb26a62e2cf3440b92da5a667efa03b267` and exactly six directory entries.
2. **Check merge status before believing any changelog SEP reference.** `gh api repos/modelcontextprotocol/modelcontextprotocol/pulls/2858 --jq '{title,merged,merged_at}'` returns `"Authorization spec split"` — the DCR-deprecation citation in §2.1's caveat, reproduced in one call.
3. **Prove your gateway is header/body consistent.** Send a `tools/call` whose `Mcp-Name` header disagrees with `params.name`. A conforming server returns **400** with JSON-RPC **`-32020`**. If your gateway routes on the header and the server executes the body, you have the split-brain the spec forbids.
4. **Prove tool errors are invisible to status-code metering.** Invoke a tool with arguments guaranteed to fail its own validation. Expect **HTTP 200**, `result.isError: true` — then check whether your dashboard counted it as a success.
5. **Test the statelessness claim in §7 against the products.** Point a 2026-07-28-era client at a gateway advertising session-aware routing and watch whether it mints or echoes `Mcp-Session-Id`; a 2026-07-28-conforming path has no reason to echo it, and GET/DELETE to the MCP endpoint should no longer be served (the spec removed the GET stream; **405** is what the reference implementations return, not a spec-mandated code). This is the test that would settle the demoted inference in §7 — we have not run it.
6. **Prove Kong ships no OSS MCP, in one call.**
   ```bash
   gh api "repos/Kong/kong/git/trees/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92?recursive=1" --jq '.tree[].path' | grep -i mcp
   ```
   Empty output. Then read `tier: ai_gateway_enterprise` on the `ai-mcp-proxy` and `ai-mcp-oauth2` plugin pages.
7. **Check the authorization default before you trust the feature checkbox.** In agentgateway, `crates/agentgateway/src/mcp/rbac.rs` — `McpAuthorizationSet::validate` returns `true` when there are no rules. In Envoy AI Gateway, `api/v1beta1/mcp_route.go` — `MCPRouteAuthorization.DefaultAction` carries `+kubebuilder:default:=Deny`. Same category, opposite fail direction.
8. **Verify token non-passthrough empirically.** Present the gateway a token minted by an upstream third-party AS rather than by the gateway's own AS. Per spec it must be refused: "*MCP servers **MUST NOT** accept or transit any other tokens.*"
9. **Reproduce the CVE count rather than quoting ours.**
   ```bash
   curl -s "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=Model+Context+Protocol&pubStartDate=2026-01-01T00:00:00.000&pubEndDate=2026-04-25T00:00:00.000" | jq .totalResults
   ```
   Then the second window. NVD caps a range at 120 days, which is why it is two calls.
10. **Re-check the agentgateway rmcp false positive** before filing it: `grep -n "rmcp" crates/agentgateway/Cargo.toml` and confirm 0.10.0 sits under `[dev-dependencies]`, not `[dependencies]`.

---

## 11. Where to go next

If you're picking one, start at [the requirements map](../README.md#the-requirements-map) and the [MCP & agent gateways section](../README.md#-mcp--agent-gateways) — then treat every "per-tool access control" phrase there as the question in §4, not the answer: *per-tool enablement* and *per-consumer authorization* are different products. The chapter map is [HANDBOOK.md](../HANDBOOK.md).

Sibling chapters, and specifically what each one becomes when the client is an agent:

- [**Chapter 1 — The Compatibility Surface**](protocol-translation.md): translation between three LLM wire formats. MCP adds a **fourth** translation axis that is not about fields at all — the modern/legacy era split (§2.3), where two of six combinations fail outright rather than degrading.
- [**Chapter 4 — Anatomy of an AI gateway**](gateway-anatomy.md): the eleven-stage request path. An MCP gateway's stages are different nouns — discovery, consent, per-verb authorization, credential exchange, invocation, audit — and its stage-0 supply-chain risk is materially larger, because a tool definition can change after you approved it (§6.2).
- [**Chapter 5 — Failover & reliability**](failover-reliability.md): its central finding, that a truncated stream can look successful, has an exact MCP analogue in §3.2 — an `isError: true` body inside an HTTP 200. Retry semantics also change: with resumability removed, "*A broken response stream loses the in-flight request*", and re-issuing a `tools/call` re-executes a **side effect**, not a re-generation.
- [**Chapter 6 — Caching economics**](caching-economics.md): §4 there found gateways caching without a tenant in the key. MCP's `cacheScope` (§3.3) writes that rule into the protocol first — and then warns that the field alone is not access control.

**Three things this chapter deliberately leaves open**, so nobody cites it for them: which MCP revision each listed gateway implements (§8.6 — the single highest-value open question in this category right now); whether the Tier-1 SDKs' wire behaviour matches their release claims; and the extension surfaces (Tasks, MCP Apps, Skills over MCP) that a gateway must negotiate or degrade rather than pass through blindly.

---

## Appendix — every source this chapter relies on

**MCP specification, revision 2026-07-28** (all pages retrieved 2026-07-29):

| Page | What it establishes here |
|---|---|
| [specification/latest](https://modelcontextprotocol.io/specification/latest) → 2026-07-28 | Current revision; key security principles; consent MUSTs; the "cannot enforce at the protocol level" concession |
| [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | Every row of §2.1; DCR deprecation and the #2858 citation oddity; error-code renumbering; `cacheScope`; OTel `_meta` keys |
| [basic](https://modelcontextprotocol.io/specification/2026-07-28/basic) | Statelessness; required `_meta` fields and the `-32602`/400 rejection; error-code allocation policy; `clientInfo`/`serverInfo` are unverified and must not drive security decisions |
| [basic/versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) | Modern/Legacy/Dual-era terminology; the six-combination matrix; `server/discover` MUST; extension negotiation and fallback |
| [basic/transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports) · [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) · [streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) | One message direction only; `Mcp-Method`/`Mcp-Name` REQUIRED and the intermediary-routing rationale; header/body mismatch → `-32020`; legacy-header handling and 405; Origin/localhost/auth security trio; stdio framing and cancellation; `X-Accel-Buffering: no` |
| [basic/authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) · [security-considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations) · [client-registration](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration) | OAuth 2.1 resource-server role; RFC 9728 MUST; RFC 8707 MUSTs and the AS-support hedge; token non-passthrough; confused-deputy per-client consent MUST; CIMD selection priority and `https`+path requirement; stdio "SHOULD NOT follow this specification" |
| [server/tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts) | Model-/user-/application-controlled split; list-varies-by-authorization; `x-mcp-header` constraints; error bifurcation; tool-name collision guidance; "a handle is a name, not a capability"; the single audit SHOULD |
| [server/utilities/caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) | `ttlMs` / `cacheScope` definitions verbatim, the shared-gateway clause, and the MUST-NOT-rely-on-cacheScope warning |
| [security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | "MCP Proxy Server" definition; State Handle Hijacking; stdio-proxy escalation path and its hedge; local-server one-click consent MUST; SSRF mitigations and Smokescreen |
| [release blog](https://blog.modelcontextprotocol.io/posts/2026-07-28/) · [RC blog](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) | Tier-1 SDK claim; migration-cost concession; "locked as of May 21, 2026" and the "ten-week window" phrasing |

**IETF/RFC documents named normatively by the spec:** `draft-ietf-oauth-v2-1-13` (OAuth 2.1), RFC 6750, RFC 8414, RFC 7591, RFC 8707, RFC 9728, RFC 9207, RFC 9110, `draft-ietf-oauth-client-id-metadata-document-00`.

**`gh api` verifications, all run 2026-07-29:** tag `2026-07-28` → published 2026-07-28T16:47:49Z, commit `5f5440bb26a62e2cf3440b92da5a667efa03b267`; tag `2026-07-28-RC` → 2026-05-29T12:51:22Z; `schema/` at that tag → six entries (`schema.ts` 98,426 bytes, `schema.json` 181,474 bytes); PRs **2243** (2026-04-15), **2322** (2026-05-06), **2567** (2026-05-07), **2575** (2026-05-11), **2549** (2026-05-15), **2577** (2026-05-15), **2663** (2026-05-15), **2596** (2026-05-18), **2858** (2026-06-04) — **all `merged=true`**; SDK releases across `modelcontextprotocol/{typescript,python,go,csharp,rust}-sdk`.

**Source trees, read at pinned commits:**

| Project | Commit (date) | Files read |
|---|---|---|
| agentgateway/agentgateway | `7cd564709f4834962d411e7a6219b30febdbd02f` (2026-07-28) | `crates/agentgateway/src/mcp/{rbac.rs,auth.rs,guardrails/mod.rs,upstream/{stdio,sse,streamablehttp}.rs}` · `src/http/{oauth.rs,auth/mod.rs,auth/oauth/transport.rs}` · `src/types/agent.rs` · `tests/tests/connect.rs` · `Cargo.toml` · `Cargo.lock` · `CHARTER.md` · `LICENSE` · `README.md` |
| envoyproxy/ai-gateway | `6722cca8d33896c4464c12f2de5aaf1238a569b6` (2026-07-23) | `api/v1beta1/mcp_route.go` · `internal/mcpproxy/mcpproxy.go` · `internal/tracing/mcp.go` · `internal/autoconfig/mcp.go` |
| TheLunarCompany/lunar | `c825cce7de2192b1e36c5ac7d6f333bde02a4579` (2026-07-28) | `mcpx/packages/mcpx-server/src/model/config/{config,permissions}.ts` · `src/services/{permissions,env-var-manager,target-server-connection-factory}.ts` · `src/server/{auth,oauth-router,downstream-transports}.ts` · `src/services/audit-log/` · `mcpx/LICENSE.MD` · `README.md` · `mcpx/package-lock.json` |
| pomerium/pomerium | `abbc8bf07c5b02c78a58385cf9ab36710b58fce0` (2026-07-28) | `pkg/policy/criteria/mcp_tool.go` · `authorize/evaluator/mcp.go` · `internal/mcp/` |
| stacklok/toolhive | `0a0cbd94929c050fa56e46b7f7da01c9b69f2dec` | `cmd/thv-operator/api/v1beta1/{virtualmcpserver_types.go,virtualmcpcompositetooldefinition_types.go}` |
| docker/mcp-gateway | `2bd20fe83dd04870e8d87dc1ed059d4d19fc7c68` (2026-07-23) | `docs/generator/reference/{mcp_gateway_run.md,mcp_policy.md}` · `cmd/docker-mcp/secret-management/` |
| archestra-ai/archestra | `d45667b329fa9bf8d83ddf05b7d09c57d27e52b9` (2026-07-29) | `LICENSE.md` · `platform/backend/src/services/identity-providers/enterprise-managed/exchange-strategies/{entra-obo-strategy,rfc8693-token-exchange}.ts` · `platform/backend/src/agents/subagents/dual-llm.ts` |
| IBM/mcp-context-forge | `eb1e212bbab90bbcdb410d5b577eac27bf677b03` (2026-07-28) | `README.md` |
| Kong/kong | `391ee48d3a68e8d0bbd0405ec1d02d75f768aa92` (2026-07-22) | full recursive tree (zero "mcp" paths) + `kong/plugins/` listing (45 plugins) |
| katanemo/plano | `6d315cc13820a037280d1b763afbe1ebd41c944d` (2026-07-27) | `skills/rules/filter-mcp.md` · `crates/brightstaff/src/handlers/agents/pipeline.rs` · `crates/hermesllm/src/apis/anthropic.rs` |

**Vendor documentation:** [Kong `ai-mcp-proxy`](https://developer.konghq.com/plugins/ai-mcp-proxy/) · [Kong `ai-mcp-oauth2`](https://developer.konghq.com/plugins/ai-mcp-oauth2/) · [Kong MCP Tool ACLs blog](https://konghq.com/blog/product-releases/mcp-tool-acls-ai-gateway) (2026-01-14) · [Pomerium MCP capabilities](https://www.pomerium.com/docs/capabilities/mcp) · [Archestra pricing model](https://archestra.ai/docs/platform-pricing-model) · [Tetrate Agent Router Service](https://tetrate.io/products/tetrate-agent-router-service) · [Linux Foundation agentgateway press release](https://www.linuxfoundation.org/press/linux-foundation-welcomes-agentgateway-project-to-accelerate-ai-agent-adoption-while-maintaining-security-observability-and-governance) (2025-08-25).

**Security writing:** [Simon Willison — the lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) (2025-06-16) · [Simon Willison — MCP prompt injection](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/) (2025-04-09).

**CVEs and advisories,** each fetched from `cveawg.mitre.org/api/cve/` or the NVD API on 2026-07-29: CVE-2026-13341 · CVE-2026-44192 · CVE-2025-34072 (+ [VulnCheck advisory](https://vulncheck.com/advisories/anthropic-slack-mcp-server-data-exfiltration), [researcher writeup](https://embracethered.com/blog/posts/2025/security-advisory-anthropic-slack-mcp-server-data-leakage/)) · CVE-2025-49596 · CVE-2025-6514 · CVE-2025-53109 · CVE-2025-53110 · CVE-2025-52882 · CVE-2025-47274 (ToolHive) · CVE-2026-42559 · CVE-2026-34742 · CVE-2026-11624 · CVE-2026-23744 · CVE-2026-33032 · CVE-2026-49257 · CVE-2026-22792/22793 · CVE-2026-32625 · CVE-2026-15643. OSV: **MAL-2025-47604** (`postmark-mcp`, npm, 2025-09-26) · GHSA-89vp-x53w-74fx / RUSTSEC-2026-0189 (rmcp < 1.4.0) · no advisories for rmcp 3.0.0-beta.5.

**Repo files** (*repo-sourced*, as_of 2026-07-29): [README.md](../README.md) §*MCP & agent gateways* (the MCP & agent gateways section, **26** entries as of 2026-07-29), plus the Enterprise, Kubernetes-native, glossary and What's-new sections· [HANDBOOK.md](../HANDBOOK.md) chapter 8 · [chapter 1](protocol-translation.md) · [chapter 4](gateway-anatomy.md) · [chapter 5](failover-reliability.md) · [chapter 6](caching-economics.md). **No `data/` file carries MCP-specific fields** — the four MUST-level, machine-checkable claims this chapter identifies (revision spoken, token-audience validation, per-tool authorization, per-client consent for proxied OAuth) have no column anywhere in this repo today.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) — every claim above is dated and linked to a spec page, a commit, a CVE record or a `gh api` call, so you can re-check it. The one we most want back: a source-read, at a pinned commit, of which MCP revision each listed gateway actually speaks (§8.6).*
