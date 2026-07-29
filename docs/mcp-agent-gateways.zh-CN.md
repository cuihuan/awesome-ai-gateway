# MCP 与 Agent 网关——为什么 Agent 流量不是补全流量

**语言：** [English](mcp-agent-gateways.md) · 简体中文

*最近更新 2026-07-29 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)与[诚实安全记分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · Model Context Protocol 在 **2026-07-28** 被重写了一遍,也就是本章写作的前一天。修订版 **2026-07-28** 发布于 **2026-07-28T16:47:49Z**(tag → commit `5f5440bb26a62e2cf3440b92da5a667efa03b267`,于 2026-07-29 经 `gh api` 确认),而且是 2026 自然年里**唯一**发布过的规范修订版——该 tag 下的 `schema/` 目录恰好只有六个条目:`2024-11-05`、`2025-03-26`、`2025-06-18`、`2025-11-25`、`2026-07-28`、`draft`。它**删掉了 session**:`Mcp-Session-Id` 头、`initialize` 握手、Streamable HTTP 的 GET 流以及 `Last-Event-ID` 续传全部消失,一个合规服务端被要求用 **`405 Method Not Allowed`** 回应 GET。在规范自己那张兼容矩阵列举的**六**种客户端↔服务端时代组合里,**有两种直接失败**——所以在新生命周期政策定下的至少 **十二个月**最短弃用窗口里,网关就是那层兼容垫片。一个 MCP 网关要担**六项 LLM 网关不担的职责**(§1);其中**两项**锚定在 MUST 级规范文本上,其余的锚在 SHOULD 级或厂商实践里,一项由传输页推导而来,还有一项——**工具调用的审计——根本没有任何协议原语**,只有一条客户端侧的 SHOULD("*Log tool usage for audit purposes*")。密钥代持不是一个功能,而是被强制的:"*MCP servers **MUST NOT** accept or transit any other tokens*"。而 2026 年的主导漏洞类别**不是**工具 RBAC 失效——在 2026 年发布、匹配 "Model Context Protocol" 的 **41** 条 CVE 里(我们自己的 NVD 关键词查询,2026-07-29,方法学告诫见 §8.1),反复出现的根因是 **DNS rebinding / 缺少 `Origin` 与 `Host` 校验**,它独立地打中了 Rust SDK、Go SDK 和 Google 的 MCP Toolbox。本仓收录了 **26** 个 MCP 与 Agent 网关([MCP 与 Agent 网关](../README.zh-CN.md#-mcp-与-agent-网关)一节,计数于 2026-07-29),而在本章之前,它对 MCP 协议的覆盖为**零**,这个品类也**没有任何数据文件**。

第一章和第四到六章都假设了同一种客户端:一个发 prompt、读补全的东西。本章讲的是另一种客户端。当调用方是一个 agent 时,网关就不再中介*文本*,而开始中介*动词*——`tools/call name=delete_repo` 是一个「去做某件事」的请求,代表某个人,用某个人的凭据,而下这个决定的模型刚刚读过攻击者可控的输入。LLM 网关出货的每一个治理原语——模型白名单、token 预算、限流——瞄准的都是错的那个名词。

来源约定与手册其余部分相同:规范文本逐字引自 `2026-07-28` 修订版页面,检索日期 2026-07-29,包括厂商自己的免责表述;网关行为按附录里列出的锁定 commit 读自源码;CVE 从 CVE.org 或 NVD 的 API 抓取并引用;GitHub PR 的合并状态经 `gh api` 确认;算术与推断标明**出自我们**;取自本仓文件的数字标为*仓内来源*并附其 `as_of`。凡是没有确立的,都在出现处就地说明。

---

## 1. 60 秒讲清概念

区别不是「agent 发的请求更多」。而是**一个请求有六个不同的属性同时改变**,而每一个都打坏网关机器里不同的一块。

| 维度 | 补全流量 | Agent / MCP 流量 | 什么被打坏 |
|---|---|---|---|
| **授权的单位** | 一个*模型* + 一份预算 | 一个**动词** —— 带 `params.name` 的 `tools/call` | 模型白名单表达不了「可以读 Jira,不可以删 Jira」 |
| **谁决定发这个请求** | 一个人,在回路里 | **模型**,自主决定——按规范,工具是「**model-controlled**」 | 同意必须被代持,而不是被默认 |
| **用的是谁的凭据** | 网关的厂商 key | 一个**第三方**的 OAuth token,按最终用户区分 | 注入 key 已经不够了;你需要的是委派 |
| **什么是攻击者可控的** | 用户 prompt | 用户 prompt **加上每一份工具描述和每一个工具返回结果** | 只在前门做输入过滤,会漏掉整条后门通道 |
| **一次失败长什么样** | HTTP 4xx/5xx | 经常是 **HTTP 200**,body 里带 `isError: true` | 按状态码计量会给一个彻底坏掉的工具打 100% 成功率 |
| **存在什么状态** | 会话,在客户端侧 | **无,自 2026-07-28 起** —— session 已从协议里移除 | 会话亲和路由不再是协议要求 |

那个一直好用的说法:**LLM 网关决定一个模型可以说什么;MCP 网关决定一个 agent 可以做什么。** 规范明说了它自己没法强制后者——"*While MCP itself cannot enforce these security principles at the protocol level, implementors **SHOULD**: 1. Build robust consent and authorization flows into their applications …*" 这一句话就是整个产品品类存在的理由。

### 六项职责,以及各自锚得有多牢

**出自我们**,由本章各处引用的规范文本综合而来——右边那一列的意义在于:六项里有四项是你可以拿去要求厂商兑现的义务,而有一项是个窟窿。

| # | 职责 | 锚定强度 | 在哪 |
|---|---|---|---|
| 1 | **按工具授权** —— 授权一个*动词*,而不是一个模型 | **MUST/MAY 级**:规范写着 "*MAY vary by the authorization presented on the request*";不足之处按操作用 `WWW-Authenticate` `insufficient_scope` 发信号 | §4 |
| 2 | **同意代持** —— 转发到第三方 AS 之前先取得按客户端的同意 | **MUST**,而且明确点名了代理 | §5.2 |
| 3 | **密钥代持** —— 绝不把客户端的 token 往上游传 | **MUST NOT**,两次,写在两个不同的页面上 | §5.1 |
| 4 | **调用审计** | ⚠️ **只有客户端侧的 SHOULD** —— 没有协议原语,而且 session 移除之后连会话 id 都没了 | §8.4 |
| 5 | **传输桥接** —— stdio ↔ Streamable HTTP | 由传输页推导:stdio "*SHOULD NOT*" 使用授权规范 | §5.4 |
| 6 | **双时代翻译** | **MUST** 相邻:六种时代组合里有两种失败,而且下面还压着 12 个月的弃用底线 | §2.3 |

---

## 2. 网关必须治理的那片协议面

### 2.1 修订版 2026-07-28 改了什么

下面每一行都出自[官方 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog),SEP 的合并状态经 `gh api` 确认(全部 `merged=true`)。

| 变更 | 规范原文 | SEP · 合并 | 对网关的后果 |
|---|---|---|---|
| **session 被移除** | "*Remove protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP transport. List endpoints (`tools/list`, `resources/list`, `prompts/list`) no longer vary per-connection.*" | [#2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567) · 2026-05-07 | 粘性路由不再是协议义务(§7) |
| **握手被移除** | "*Make MCP stateless: remove the `initialize`/`notifications/initialized` handshake. Every request now carries its protocol version and client capabilities in `_meta`*" | [#2575](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575) · 2026-05-11 | 按请求校验 `_meta`;缺必填字段 → `-32602` + **HTTP 400** |
| **新增 `server/discover`** | "*Add `server/discover`: servers MUST implement this RPC to advertise their supported protocol versions, capabilities, and identity.*" | #2575 | 一个做联邦的网关必须合成的那个新能力广告点 |
| **服务端发起的请求被废除** | "*Multi Round-Trip Requests (MRTR) pattern introduced which replaces the previous approach of sending server-initiated requests, such as `roots/list`, `sampling/createMessage`, or `elicitation/create`.*" | [#2322](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2322) · 2026-05-06 | "*No other message direction exists*" —— 一个代理永远只转发 客户端→服务端 的请求 |
| **续传被移除** | "*A broken response stream loses the in-flight request; clients **MUST** re-issue it as a new request with a new request ID*" | #2575 | `Last-Event-ID` 必须被忽略;GET/DELETE → `405` |
| **Roots、Sampling、Logging 被弃用** | "*These features remain fully functional during the deprecation window but new implementations should not add support for them.*" | [#2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577) · 2026-05-15 | 建议的迁移路径点名用 **OpenTelemetry** 取代 MCP Logging |
| **12 个月生命周期政策** | "*a minimum twelve-month deprecation window, and a registry of deprecated features*" | [#2596](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2596) · 2026-05-18 | 双时代翻译是一项长期职责,不是一次过渡 |
| **DCR 被弃用** | "*Deprecate the OAuth 2.0 Dynamic Client Registration Protocol (RFC7591) as a client registration mechanism in favor of Client ID Metadata Documents*" | 落在 PR #2858 里面——见下面的告诫 | 客户端身份变成一个 `https` URL,而且必须与它的文档精确一致 |
| **Tasks 移出核心** | "*Move experimental tasks out of the core protocol and into an official extension (`io.modelcontextprotocol/tasks`)*" | [#2663](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2663) · 2026-05-15 | 扩展是要协商能力的;网关必须协商或降级,绝不能盲目透传 |

> ⚠️ **一条引用告诫,写出来免得有人把它传错。** changelog 把 DCR 弃用归到 PR **#2858** 上,但 `gh api repos/modelcontextprotocol/modelcontextprotocol/pulls/2858`(2026-07-29)返回的是 `title="Authorization spec split"`、`merged=true`、`merged_at=2026-06-04T19:16:55Z`。这次弃用是真实且规范性的——客户端注册页挂着一个 Warning 框写着 "*Dynamic Client Registration is deprecated. New implementations should use Client ID Metadata Documents instead.*" ——但**不要把 #2858 描述成一个专门做 DCR 弃用的 PR**;它是作为授权规范拆分的一部分落地的。

发布时间线,因为总会有人去核:RC 博文说候选版 "*is locked as of*" **May 21, 2026**,并把验证期称为一个「**ten-week window**」——那是厂商的措辞,而 5 月 21 → 7 月 28 是 68 天(9.7 周)。机器可核的数字是 GitHub 上的 tag:`2026-07-28-RC` 发布于 **2026-05-29T12:51:22Z**,`2026-07-28` 发布于 **2026-07-28T16:47:49Z**。把 tag 当事实引用,把「ten-week」当有出处的散文引用。

### 2.2 三种原语,三个不同的所有者——三类不同的策略

一个在 MCP 上统一套用一个策略引擎的网关,已经犯了错,因为规范给每一种原语指派了不同的控制者:

| 原语 | 原文 | 方法 | 它需要的策略类别 |
|---|---|---|---|
| **Tools** | "*Tools in MCP are designed to be **model-controlled**, meaning that the language model can discover and invoke tools automatically*" | `tools/list`、`tools/call` | 按动词授权 + 同意 + 审计。这就是危险的那一个 |
| **Prompts** | "*Prompts are designed to be **user-controlled** … This refers to who decides when the prompt is used, not who authors its content. Prompt content is defined by the server.*" | `prompts/list`、`prompts/get` | 内容溯源——用户选的那段文字是*服务端*写的 |
| **Resources** | "*Resources in MCP are designed to be **application-driven**, with host applications determining how to incorporate context based on their needs.*" | `resources/list`、`resources/read`、`resources/templates/list` | 数据访问控制与数据驻留 |

三者都带着同一句免责——"*implementations are free to expose [them] through any interface pattern that suits their needs—the protocol itself does not mandate any specific user interaction model*" ——而这份自由,恰恰就是一个网关被买来去约束的东西。

### 2.3 时代矩阵——网关承重的地方

规范定义了「**Modern**」(2026-07-28 及之后,按请求带元数据)、「**Legacy**」(2025-11-25 及更早,`initialize` 握手)和「**Dual-era**」。它的兼容矩阵列举了六种组合:

| 客户端时代 | 服务端时代 | 结果 |
|---|---|---|
| Modern | Modern | ✅ 可用 |
| Modern | Legacy | ❌ **失败** —— "*The server may reject the request with an implementation-defined error, stay silent, or even process an era-ambiguous method under legacy semantics*" |
| Legacy | Modern | ❌ **失败** —— "*Legacy clients have no fall-forward mechanism*" |
| Dual-era | Modern | ✅ 可用 |
| Dual-era | Legacy | ✅ 可用 |
| Legacy | Dual-era | ✅ 可用 |

**六种里有两种失败,而且两种都可能是静默的。** 时代探测是分传输的——在 stdio 上探 `server/discover`,而且 "*The fallback **MUST NOT** be keyed to one specific error code*";在 HTTP 上则是发一个 modern 请求,再检查 `400` 的 body。"*The era determination is a property of the server, not of an individual request. Clients **SHOULD** cache the result for the lifetime of the server process (stdio) or origin (HTTP).*" 加上那条 12 个月的弃用底线,**双时代翻译至少到 2027 年年中都是网关的职责。**

---

## 3. 流量形状——一次 `tools/call` 到底在线上放了什么

### 3.1 2026 年的传输是*为*中间件重新设计的

这是这次修订版里与网关最相关的一件事,而且它是被当作意图明说出来的,不是推断出来的:"*The Streamable HTTP transport mirrors selected JSON-RPC body fields into HTTP headers so that intermediaries (load balancers, gateways, observability tooling) can route and inspect requests without parsing the body.*"

| 头 | 源字段 | 在哪些请求上必填 |
|---|---|---|
| `Mcp-Method` | `method` | 所有请求 —— "*These headers are **REQUIRED** for compliance*" |
| `Mcp-Name` | `params.name` 或 `params.uri` | `tools/call`、`resources/read`、`prompts/get` |
| `MCP-Protocol-Version` | —— | 每一个 POST |
| `Mcp-Param-{Name}` | 一个被标注了 `x-mcp-header` 的工具参数 | 按服务端选开;"*clients **MUST** support this feature*" |

而规范提前堵掉了镜像头必然招来的那个脑裂 bug:"*Servers that process the request body **MUST** reject requests where the values specified in the headers do not match the corresponding values in the request body. This prevents potential security vulnerabilities when different components in the network rely on different sources of truth (e.g., a load balancer routing on the header value while the MCP server executes based on the body value).*" 拒绝的方式是 `400` + JSON-RPC **`-32020`(`HeaderMismatch`)**。有两条子句直接约束中间件:它们 "***MUST** return an appropriate HTTP error status … but are not required to return a JSON-RPC error response*",以及——这条该写进你的配置评审——在镜像头上执行策略的中间件 "***SHOULD** verify that the `MCP-Protocol-Version` header indicates a version that requires header–body validation. If the version is older or the header is absent, the intermediary **SHOULD** reject the request rather than trusting unvalidated header values.*"

拿它对比一下本仓在[供应链矩阵](../README.zh-CN.md#-供应链安全谁给发布签名谁真被打穿过)里追踪的那簇 LLM 网关鉴权绕过 CVE:同样是可伪造头的形状,结果却相反——这里标准先把缓解措施写下来了。

`x-mcp-header` 值得单独一行,因为它是一把伪装起来的数据驻留路由 key(规范自己的示例就把一个 Spanner `execute_sql` 工具的 `region` 参数提升成了头)。它被严格约束——只允许原始类型,"*Parameters with type `number` are not permitted*",必须从 schema 根静态可达(不能穿过 `items`、`oneOf`/`anyOf`/`allOf`/`not`、`if`/`then`/`else` 或 `$ref`),大小写不敏感地唯一,不含 CR/LF——而且客户端 "***MUST** reject tool definitions where any `x-mcp-header` value violates these constraints*",做法是把那个工具从 `tools/list` 里丢掉。安全免责原文:"*Server developers **SHOULD NOT** mark sensitive parameters (passwords, API keys, tokens, PII) with `x-mcp-header`, as header values are visible to network intermediaries.*"

### 3.2 计量陷阱:一次失败的工具调用通常是 200

MCP 刻意把错误分成两叉。**协议错误**("*Unknown tool; Malformed requests …; Server errors*")以 JSON-RPC 错误返回。**工具执行错误**("*API failures; Input validation errors …; Business logic errors*")则 "*reported in tool results with `isError: true`*",因为 "*Clients **SHOULD** provide tool execution errors to language models to enable self-correction.*"

**后果,出自我们:**一个只按 HTTP 状态码计量、告警或算 SLO 的网关,会给一个彻底坏掉的工具报出 **100% 成功率**。执行错误那一类里的每一次失败 `tools/call` 都是一个带 `result` body 的 HTTP 200。这是第五章那个「六家里有四家会返回一条*看起来*成功的截断流」的发现在 MCP 上的对应物——同一类失明,不同的层。这次修订版还重新编了号:资源未找到从 `-32002` 挪到了 `-32602`,客户端 SHOULD 仍然接受老服务端发来的 `-32002`,而服务端错误段被劈成两半——`-32000..-32019` 是遗留段("*receivers **MUST NOT** assume any specific meaning for these codes*"),`-32020..-32099` 保留给规范(`-32020` HeaderMismatch、`-32021` MissingRequiredClientCapability、`-32022` UnsupportedProtocolVersion)。

### 3.3 可缓存的列表——以及点名以共享网关来定义的 `cacheScope`

2026 年新增:`tools/list`、`prompts/list`、`resources/list`、`resources/read` 和 `resources/templates/list` 的结果带上了必填的 `ttlMs` 和 `cacheScope` 字段([SEP #2549](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2549),2026-05-15 合并)。这两个作用域的定义明确点了我们的名:

| `cacheScope` | 原文 |
|---|---|
| `"public"` | "*The response does not contain user-specific data. Any client, shared gateway, or caching proxy **MAY** store and serve the cached response to any user.*" |
| `"private"` | "*The response contains private data that is not meant to be shared between callers. Cached responses **MAY** be reused for the same authorization context. Caches **MUST NOT** be shared across authorization contexts (e.g. a different access token requires a different cache).*" |

陷阱是规范自己说出来的:"*Servers MUST be aware that responses with a `"public"` `cacheScope` may be shared between callers even if the Result is coming from an authenticated endpoint*",而且实现者 "*MUST apply appropriate per-primitive access controls, and MUST NOT rely on `cacheScope` alone*"。带 `inputResponses` 或 `requestState` 的 MRTR 重试结果 "***MUST NOT** be cached*"。这就是[第六章 §4](caching-economics.zh-CN.md) 那个缓存 key 问题,只不过答案被提前写下来了——区别在于,在 LLM 世界里多数网关缓存的 key 里根本没有租户——见[第六章](caching-economics.zh-CN.md)里那张缓存 key 表。

---

## 4. 工具级授权——动词,而不是模型

规范在两端都为按工具授权背书。**发现**这一端可以被过滤:"*Servers that declare the `tools` capability **MUST** respond to `tools/list` requests with the set of tools currently available to the requesting client. This set **MAY** be empty and **MAY** change over time …, but **MUST NOT** vary per-connection or as a side effect of other requests on the connection. The set **MAY** vary by the authorization presented on the request — for example, returning only the tools the caller's granted scopes permit — since credentials are per-request input, not connection state.*" **运行时**的权限不足则会拿到一次升权挑战:`HTTP 403` 加上 `WWW-Authenticate: Bearer error="insufficient_scope", scope="…", resource_metadata=…`,客户端被要求 "*treat the scopes provided in the challenge as authoritative*" 并请求先前 scope 与被挑战 scope 的**并集**;服务端 "***MUST** account for scope hierarchies*"。

那些被收录的网关实际实现了什么,按附录里的锁定 commit 读自源码:

| 网关 | 机制 | 默认姿态 | 它住在哪 |
|---|---|---|---|
| **agentgateway** | 在 `ResourceType::{Tool, Prompt, Resource}` 上的 CEL 规则集(`McpAuthorization`) | **全放行** —— `McpAuthorizationSet::validate` 在 `!self.0.has_rules()` 时短路返回 `true` | Apache-2.0 OSS(`crates/agentgateway/src/mcp/rbac.rs`) |
| **Envoy AI Gateway** | `MCPRoute` CRD:规则把工具与 JWT scope/claim 匹配("*Scopes and claims are AND-ed*"),外加在 `request.mcp.tool`/`.method`/`.backend`/`.params` 上的实验性 CEL;首个匹配胜出,最多 32 条 | **`Deny`**(`+kubebuilder:default:=Deny`) | Apache-2.0 OSS,但是 **`api/v1beta1`** —— 不是 v1 |
| **Pomerium** | `mcp_tool` 策略判据 —— "*matches tool names by exact name, prefix, suffix, or list — enabling deny-based block lists and allowlists*" | 由策略决定 | Apache-2.0 OSS(`pkg/policy/criteria/mcp_tool.go`) |
| **ToolHive(Virtual MCP)** | Cedar 策略 + OIDC;按工具**按用户**限流,由一条要求 `incomingAuth.type: oidc` 的 CEL 规则把关 | 由策略决定;"*vMCP runtime authz middleware is Cedar-only*" | Apache-2.0 OSS(`virtualmcpserver_types.go`) |
| **Kong AI Gateway** | 在 Consumer/Consumer Group 上的 MCP Tool ACL —— "*Kong intercepts the response from your upstream API and filters the tool list based on the authenticated user's permissions*" | 支持默认拒绝的姿态 | **仅企业版** —— `tier: ai_gateway_enterprise`;Kong OSS 在 `391ee48` 上匹配 "mcp" 的路径**为零** |
| **Lunar MCPX** | 跨 `consumers` / `clientNames` / `defaultConsumer` 解析出来的工具组 ACL;`Permission = "allow" \| "block"`,按 consumer 可选 `default-allow`(黑名单)或默认阻断(白名单) | 按 consumer 配置 | MIT(`mcpx/LICENSE.MD`)—— 但见 §9 里的层级告诫 |
| **Docker MCP Gateway** | 静态的 `--tools` 启用列表 + `--interceptor` + `--block-secrets`(默认 `true`)+ `--verify-signatures`(默认 `true`) | 启用列表,**无身份概念** | MIT。`docker mcp policy` 是 "*Manage secret policies*",**不是**工具授权 |

**其中两家在最要紧的那个维度上截然相反,而那个维度不是功能对照表里的一列。** agentgateway 的空规则集意味着*全部放行*;Envoy AI Gateway 的 `MCPRoute` 默认是 *Deny*。同一个品类,同一种开源许可,而当有人上了一份不完整的配置时,失败方向正好相反。

**而 Docker MCP Gateway 是本仓目前描述错了的那一条。** 按工具*启用*是一份部署期的列表;按工具*授权*回答的是「哪个调用方」。`--tools` 提供的只有前者。

---

## 5. 密钥代持与 OAuth on-behalf-of

### 5.1 规范把代持定成了强制,而不是可选

一个 MCP 服务端 "*acts as an OAuth 2.1 resource server*"、"***MUST** implement OAuth 2.0 Protected Resource Metadata (RFC9728)*",而客户端 "***MUST** use OAuth 2.0 Protected Resource Metadata for authorization server discovery*"。它依据的文档是 IETF 草案——`draft-ietf-oauth-v2-1-13` 和 `draft-ietf-oauth-client-id-metadata-document-00` ——在有人把这个称作「OAuth 2.1 标准」之前,值得先知道这一点。

然后是那条边界条款,也就是密钥代持之所以能成为一个网关产品的全部原因:

> "*MCP clients **MUST NOT** send tokens to the MCP server other than ones issued by the MCP server's authorization server. MCP servers **MUST** only accept tokens that are valid for use with their own resources. MCP servers **MUST NOT** accept or transit any other tokens.*"

以及

> "*If the MCP server makes requests to upstream APIs, it may act as an OAuth client to them. The access token used at the upstream API is a separate token, issued by the upstream authorization server. The MCP server **MUST NOT** pass through the token it received from the MCP client.*"

**因此这个 agent 在结构上永远拿不到下游凭据。** 做错这件事的风险被写明为:Security Control Circumvention、Accountability and Audit Trail Issues、Trust Boundary Issues 和 Future Compatibility Risk ——包括这句原文:"*If the MCP Server passes tokens without validating their claims (e.g., roles, privileges, or audience) or other metadata, a malicious actor in possession of a stolen token can use the server as a proxy for data exfiltration.*"

RFC 8707 的 resource indicator 是受众绑定的另一半,而这里的 MUST 强得不寻常:`resource` 参数 "***MUST** be included in both authorization requests and token requests*"、"***MUST** identify the MCP server that the client intends to use the token with*"、"***MUST** use the canonical URI*" ——而且客户端 "***MUST** send this parameter regardless of whether authorization servers support it.*" 注意安全页自己那条营销从不带上的免责:resource indicator "*provide critical security benefits by binding tokens to their intended audiences **when the Authorization Server supports the capability**.*"

### 5.2 那条直接点名网关的「混淆代理」MUST

这是整份规范里最强的、专门针对网关的规范性文本,而且它是一条 MUST:

> "*MCP proxy servers using static client IDs **MUST** obtain user consent for each dynamically registered client before forwarding to third-party authorization servers (which may require additional consent).*"

「MCP Proxy Server」是一个被定义的术语——"*An MCP server that connects MCP clients to third-party APIs, offering MCP features while delegating operations and acting as a single OAuth client to the third-party API server*" ——也就是本仓 MCP 一节里几乎每一条目正是的东西。它要求的保护措施细到可以当清单用:一份按用户的已批准 `client_id` 名册,要 "***before** initiating the third-party authorization flow*" 检查;一个同意界面,要标明 "*the requesting MCP client by name*",并显示 "*the registered `redirect_uri` where tokens will be sent*",带 CSRF 保护并 "*Prevent iframing via `frame-ancestors` CSP directive or `X-Frame-Options: DENY`*";同意 cookie 要用 "*`__Host-` prefix*" 并带 "*`Secure`, `HttpOnly`, and `SameSite=Lax`*",绑定到具体的 `client_id` "*(not just "user has consented")*";`redirect_uri` 精确字符串匹配;以及一次性的 `state`,它的 cookie "***MUST NOT** be set until **after** the user has approved the consent screen.*"

### 5.3 到底谁在代持,以及代价是什么

| 网关 | 面向客户端的鉴权 | 上游凭据 | RFC 8693 token exchange / OBO | 许可证的真实情况 |
|---|---|---|---|---|
| **agentgateway** | JWT 校验(Strict/Optional/Permissive),带 `/.well-known/oauth-protected-resource` 与 `/.well-known/oauth-authorization-server`;IdP 支持 Auth0、Okta、Descope、Keycloak、Authentik、Entra | `BackendAuthKind::{Passthrough, Key, Gcp, Aws, Azure, Copilot}`,序列化时 key 被脱敏 | ✅ `src/http/oauth.rs` 里的 `"urn:ietf:params:oauth:grant-type:token-exchange"`、`apply_token_exchange(...)`,外加一个标题为 "*End-to-end on-behalf-of (OBO) token exchange over a CONNECT tunnel*" 的 e2e 测试,带一个 mock STS | **Apache-2.0,在主干树里** |
| **Archestra** | OIDC + SAML SSO | 密钥保险库 | ✅ `entra-obo-strategy.ts` 与 `rfc8693-token-exchange.ts` | ⚠️ **企业版许可。** 两个文件都以 `// SPDX-License-Identifier: LicenseRef-Archestra-Enterprise` 开头;有 59 条路径被标为企业版。那个双 LLM 护栏(`dual-llm.ts`)没有 SPDX 头,**因此是** AGPL-3.0-only |
| **Kong AI Gateway** | `ai-mcp-oauth2` 插件 | —— | ✅ 有文档,token exchange 自 **v3.14+** 起,最低 Gateway 3.12 | **仅企业版**(`tier: ai_gateway_enterprise`) |
| **Pomerium** | 身份感知代理 | "*MCP-aware bridge that manages upstream OAuth on behalf of your users*"(厂商文档) | 这一轮未核实 | Apache-2.0 树里含 MCP 代码 |
| **Envoy AI Gateway** | `MCPBackendSecurityPolicy.APIKey`,来自一个 k8s `secretRef` 或 `inline`,注入到某个头(默认 `Authorization`,`Bearer` 前缀)或一个 query 参数 | 只有 key 注入 | ❌ 这一轮没找到 | Apache-2.0。它自己的 API 文档警告:"*Embedding credentials in URLs (including query parameters) is generally not recommended because URLs can be exposed in logs and intermediary systems; prefer header-based injection when possible.*" |
| **Lunar MCPX** | **静态 API key** —— `x-lunar-api-key`,缺失 401 / 错误 403,而且在 `auth.enabled` 为 false 或没设 key 时是一个**空操作守卫** | 出站 OAuth 授权码流(`/oauth/callback` → `completeOAuthByState`)+ `staticOauth` 字面量 | ❌ —— 在 `mcpx-server/src` 上 grep `on-behalf-of\|obo\|token_exchange\|urn:ietf:params:oauth:grant-type:token-exchange` 返回**零**命中 | MIT 代码(§9 告诫) |
| **Docker MCP Gateway** | —— | `cmd/docker-mcp/secret-management/` 下的 credstore,`--block-secrets` 默认 `true` | ❌ | MIT |

Lunar MCPX 还出货了这一轮读到的最干净的*作用域*设计,值得引用,因为它是一种设计属性而不是一个功能:`env-var-manager.ts` 里三个用途分离的桶—— `profileSecrets`、`oauthCredentials`、`prefilledLiterals` ——而文件自己的注释写着 "*The three scopes don't share a primary map, so a user-controlled profile secret cannot be reached by OAuth-name lookups and vice versa.*"

### 5.4 stdio 根本没有鉴权层——而这正是网关存在的全部理由

"*Implementations using an HTTP-based transport **SHOULD** conform to this specification. Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment.*" 所以一个桥接 stdio↔Streamable HTTP 的网关做的不是一次表面的传输转换:它必须**从零缔造整套 OAuth 故事**,合成 `_meta` 块以及 `Mcp-Method`/`Mcp-Name` 头,并翻译取消语义——在 stdio 上客户端 "***MUST** send a `notifications/cancelled` notification*",而在 Streamable HTTP 上 "*Closing the SSE response stream **MUST** be treated by the server as cancellation of that request.*"

而代理架构有它自己的攻击章节,开头那句免责值得原样复述:"*The `stdio` transport itself is not inherently vulnerable. However, in proxy architectures where a separate proxy service manages `stdio` connections and can spawn MCP servers as child processes, it can provide a critical escalation path from web-based attacks to full system compromise.*" 紧接着是:"***Important**: This attack vector only applies to MCP implementations that use a proxy architecture, not to direct `stdio` transport usage.*" 缓解措施都是 SHOULD,读起来就像是给 ToolHive/Docker 那种容器隔离写的规格书:"*Implement sandboxing or containerization for spawned processes; Restrict file system access for spawned MCP servers; Log all `stdio` transport usage for security monitoring; Require additional authorization for potentially dangerous commands.*"

---

## 6. 经由工具的 prompt 注入——没有任何网关能关上的敞口

### 6.1 这个说法,以及它作者自己的免责

Simon Willison 的「**The lethal trifecta for AI agents: private data, untrusted content, and external communication**」(2025 年 6 月 16 日)逐字点名了这三条腿:"*Access to your private data—one of the most common purposes of tools in the first place! Exposure to untrusted content—any mechanism by which text (or images) controlled by a malicious attacker could become available to your LLM. The ability to externally communicate in a way that could be used to steal your data*"。**一个 MCP 网关,按定义就是一台把这三样凑到同一个地方的机器。**

诚实的那部分是他的,不是我们的:"*we still don't know how to 100% reliably prevent this from happening.*" 而对那些冲着这个缺口卖东西的厂商,保留他自己的强调:"*I am _deeply suspicious_ of these: If you look closely they'll almost always carry confident claims that they capture '95% of attacks' or similar... but in web application security 95% is very much a failing grade.*"

### 6.2 两条注入通道,都带着 CVE

**工具描述。** Willison,「Model Context Protocol has prompt injection security problems」(2025 年 4 月 9 日):"*MCP tools can mutate their own definitions after installation. You approve a safe-looking tool on Day 1, and by Day 7 it's quietly rerouted your API keys to an attacker*",以及 "*Malicious instructions are tucked away in the tool descriptions themselves—visible to the LLM, not normally displayed to users.*" 规范同意这一点,并把它写成了一条客户端 MUST:"*clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers*",而在顶层原则里则是 "*Tools represent arbitrary code execution and must be treated with appropriate caution.*"

**工具返回结果。** 最干净的一手来源,是一家厂商针对自家 MCP 服务端提的 CVE。**CVE-2026-13341**,由 Kong 指派,发布于 2026-07-03,CVSS **7.4 HIGH**:"*A vulnerability exists in the Kong Konnect Model Context Protocol (MCP) server prior to version 1.0.0, which could allow a remote attacker to perform an indirect prompt injection attack and execute unintended API requests.*" 被注入的内容是**在工具返回的分析数据里**到达的——而不是在用户 prompt 里。第二个实例:**CVE-2026-44192**(2026-07-22,CVSS 6.6),针对 Ansible Lightspeed 的 MCP 服务端。

**数据外泄。** **CVE-2025-34072**(VulnCheck,2025-07-02,CVSS 4.0 基础分 **9.3 CRITICAL**),针对 Anthropic 已弃用的 Slack MCP Server:"*When an AI agent using the Slack MCP Server processes untrusted data, it can be manipulated to generate messages containing attacker-crafted hyperlinks embedding sensitive data. Slack's link preview bots (e.g., Slack-LinkExpanding, Slackbot, Slack-ImgProxy) will then issue outbound requests to the attacker-controlled URL, resulting in zero-click exfiltration of private data.*" **把这条外泄通道看仔细:它是一个第三方的链接展开机器人,不是那个 agent。** 一份只针对 agent 自己连接的网关出站白名单拦不住它。这是本节里最重要的一条架构事实。

### 6.3 规范承认它无法强制同意——而那就是产品缺口

关键原则,原文:"*Users must explicitly consent to and understand all data access and operations*";"*Hosts must obtain explicit user consent before invoking any tool*"。工具页的 Warning:"*For trust & safety and security, there **SHOULD** always be a human in the loop with the ability to deny tool invocations.*" 然后是 §1 里引过的那句让步:MCP "*cannot enforce these security principles at the protocol level*"。

被收录的网关对此出货了什么,只按能力是否存在陈述、不谈效果——**本节里没有任何一家公布过我们愿意认可为检出率测量的方法学,而且按 §6.1,你应该对任何看起来像的东西保持怀疑**:

| 项目 | 机制 | 许可证注记 |
|---|---|---|
| **Archestra** | 确定性的双 LLM /「致命三要素」护栏(`platform/backend/src/agents/subagents/dual-llm.ts`) | **AGPL-3.0-only** —— 没有 SPDX 头,所以走默认路径。与它的 OBO 代码(§5.3)不同 |
| **agentgateway** | `mcpGuardrails` 外部策略钩子:`Outcome<T>::{Pass, Mutated(T), Reject(ErrorData)}`,请求/响应两个阶段,"*the first to reject a request short-circuits the chain*" | Apache-2.0 |
| **fak**、**Armorer Guard**、**Lasso MCP Gateway** | 默认拒绝的能力白名单 + 结果隔离;包装 stdio 的参数检查;插件护栏 + 密钥打码 | 来自[榜单](../README.zh-CN.md#-mcp-与-agent-网关)的仓内来源,这一轮没有读源码 |
| **toolport**、**mcpproxy-go** | 工具完整性校验 + 对新出现服务端的隔离——正是对 Day-1/Day-7 抽地毯的直接回应 | 仓内来源,这一轮没有读源码 |

---

## 7. Session 与状态处理——规范刚刚删掉的那个差异点

在 2025-11-25 之前,会话亲和确实是一个真实的 MCP 网关问题:`Mcp-Session-Id` 需要粘性路由,DELETE 会终止一个会话,而 `Last-Event-ID` 续传意味着负载均衡器必须把客户端送回同一个副本。到 2026-07-28:"*The Model Context Protocol (MCP) is a **stateless protocol**: all the information needed to process a request is contained in the request itself. A server processes each request independently; no state should be inferred from previous requests, even those on the same connection or stream.*" 以及:"*Servers **MUST NOT** rely on prior requests over the same connection to establish context.*" 遗留流量的处理方式是无视它——"*An `Mcp-Session-Id` header on a request: ignore it, and do not mint or echo session IDs. A `Last-Event-ID` header: ignore it; streams are not resumable.*"

必须跨调用存在的状态现在是显式的:服务端铸造一个句柄,并 "*as an ordinary tool argument on each request*" 收回它([SEP #2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567),2026-05-07 合并)。被点名的攻击也随之改变。「Session Hijacking」已经从当前的最佳实践页**消失**,取而代之的是 **State Handle Hijacking**,它的缓解措施是两行网关要求:

> "*MCP servers that implement authorization **MUST** verify all inbound requests. MCP servers **MUST NOT** treat possession of a state handle as authentication.*"

外加几条 SHOULD:句柄要来自安全 RNG 且不可预测、要有过期,以及绑定 "*handles server-side to the authenticated user, for example by keying stored state as `<user_id>:<handle>` where the user ID is derived from the verified token rather than supplied by the client.*" 工具页用设计语言说了同一件事:"*For authenticated servers, a handle is a name, not a capability.*" 旧的指引没有被删掉,只是被挪走了——那一页明确把读者引向 "*Session Hijacking in the 2025-11-25 version of this page*"。

> 🔶 **降级处理——出自我们,是推断,不是规范文本。** 规范说的是什么变了;而「这**侵蚀了做会话路由的 MCP 网关的价值主张**」这个论断是我们的分析。理由是:一个合规的 2026-07-28 端点就是一个普通的无状态 HTTP POST 端点,任何一台商品负载均衡器都能对它轮询,而列表结果 "***MUST NOT** vary per-connection*"。厂商用自己的话承认了迁移代价——"*there will be some migration cost, especially for developers that did depend on session identifiers*" ——但对产品品类只字未提。这一条可以直接拿本仓那两个把 session 当卖点的条目来测(§10 第 5 步),而**我们还没测过**。

---

## 8. 失败模式,附凭据

### 8.1 2026 年的主导类别是 DNS rebinding,不是授权

同一个根因独立地落在五个代码库里,各自带着自己的 CVE:

| CVE | 目标 | 发布 · CVSS | 原文 |
|---|---|---|---|
| **CVE-2026-42559** | Rust `rmcp` < 1.4.0 | 2026-05-14 · 8.8 | "*did not validate the incoming Host header. This allowed a malicious public website, via a DNS rebinding attack, to send authenticated requests to an MCP server running on the victim's loopback or private-network interface*" |
| **CVE-2026-34742** | MCP Go SDK < 1.4.0 | 2026-04-02 · 7.6 | "*does not enable DNS rebinding protection by default for HTTP-based servers*" |
| **CVE-2026-11624** | Google MCP Toolbox for Databases < v0.25.0 | 2026-06-13 · 9.4 | "*users had no way to validate the origin's host*" |
| **CVE-2026-23744** | MCPJam inspector ≤ 1.4.2 | 2026-01-16 · 9.8 | "*MCPJam inspector by default listens on 0.0.0.0 instead of 127.0.0.1, an attacker can trigger the RCE remotely via a simple HTTP request*"(1.4.3 修复) |
| **CVE-2026-33032** | Nginx UI ≤ 2.3.5 | 2026-03-30 · 9.8 | "*/mcp requires both IP whitelisting and authentication (AuthRequired() middleware), the /mcp_message endpoint only applies IP whitelisting - and the default IP whitelist is empty, which the middleware treats as 'allow all'*" |

**反复出现的那个假设是「回环即可信」,而网关里再多的工具级 RBAC 也修不好它** —— 它必须在 MCP 服务端上修,或者干脆别把服务端直接暴露出去。而这一点,平心而论,正是网关厂商手里最强的架构论据。规范自己的 Streamable HTTP 安全一节只有三行,而这三行都是网关的活:"*Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding attacks*"(非法 → 403);"*When running locally, servers **SHOULD** bind only to localhost (127.0.0.1)*";"*Servers **SHOULD** implement proper authentication for all connections.*"

**关于那个 41。** 对 "Model Context Protocol" 的 NVD 关键词搜索,查询于 2026-07-29,因为 NVD 把区间上限卡在 120 天,所以拆成两个窗口:2026-01-01→2026-04-25 返回 **23**,2026-04-25→2026-07-29 返回 **18**。严重度最高的包括 CVE-2026-49257(mcp-pinot,10.0)、CVE-2026-22792/22793(5ire,9.6)、CVE-2026-32625(LibreChat,9.6)、CVE-2026-15643(AWS HealthLake MCP Server,9.2)。**方法学告诫,出自我们:**关键词匹配会多算(只是提到了 MCP 的产品)也会漏算(不用这个短语的 MCP 缺陷),而且边界日期同时出现在两个窗口里,所以同一天发布的条目可能被重复计数。把 41 当成「**按这个方法、在这个日期上,大约 40**」,而不是一次普查。

### 8.2 SSRF —— 而规范推荐的缓解措施,字面意义上就是一个网关

在 OAuth 元数据发现期间,客户端会从三个**服务端可控**的来源取 URL:`WWW-Authenticate` 里的 `resource_metadata` URL、PRM 里的 `authorization_servers`,以及 AS 元数据里的各个端点。"*MCP clients deployed to a server **MUST** consider SSRF risks and implement appropriate mitigations when fetching OAuth-related URLs. Which protections are appropriate depend on your network environment.*" 那份 SHOULD 清单要拦 `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`127.0.0.0/8`、`::1`、`169.254.0.0/16` "*(including cloud metadata endpoints)*"、`fc00::/7`、`fe80::/10` ——然后是:"*For server-side MCP client deployments, operators **SHOULD** consider using an egress proxy that enforces network policies*",并点名了 Stripe 的 Smokescreen。还带一句我们本来也会加粗的警告:"*Avoid implementing IP validation manually. Attackers exploit encoding tricks (octal, hex, IPv4-mapped IPv6) that custom parsers often miss.*" 相关的还有工具 schema 里的 `$ref` —— "*Implementations **MUST NOT** automatically dereference `$ref` values that resolve to a network URI*",选开的抓取 "***MUST** be disabled by default*"。

### 8.3 聚合命名空间是网关的发明,不是协议的

本仓榜单里每一个做联邦的网关—— ContextForge、MetaMCP、1MCP、mcpproxy-go、Nexus、ToolHive 的 virtual MCP ——都必须解决它,而规范把它扔给了它们,却不给机制:"*Tool name uniqueness is scoped to a single server. Clients or proxies that aggregate tools from multiple servers **MAY** encounter naming collisions (for example, two servers each exposing a `search` tool) and **SHOULD** implement a disambiguation strategy such as prefixing tool names with a server identifier. The server `name` (from `serverInfo`) is not guaranteed to be unique across servers and **SHOULD NOT** be relied upon for disambiguation.*" 别处还有强化:`clientInfo` 与 `serverInfo` "*are self-reported by the sender and are not verified by the protocol*",而且实现 "***SHOULD NOT** rely on them for security decisions.*"

### 8.4 审计没有协议原语——这个窟窿落到了网关头上

工具规范里全部的审计要求,就是一条客户端侧的条目:"*Log tool usage for audit purposes.*" 服务端拿到的是 "*Validate all tool inputs; Implement proper access controls; Rate limit tool invocations; Sanitize tool outputs.*" **没有 `notifications/audit`**,除了 JSON-RPC 的 `id` 之外没有任何必需的关联标识符,而且——因为 session 被移除了——**没有协议级的会话标识符可以用来把调用归组**。这次修订版加进来最接近的东西是 W3C trace context:`traceparent`、`tracestate` 和 `baggage` 是保留的 `_meta` key("*As an exception to the prefix requirement*"),其值 "***MUST** follow W3C Trace Context and W3C Baggage formats*"([SEP #414](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/414))。**trace context 被标准化了;审计内容没有。** 按调用的归属是网关自己要发明的东西——这就是为什么 Lunar MCPX 的 `src/services/audit-log/` 和 Kong 的 "*All access attempts (allowed or denied) are written to the plugin's audit log*" 是差异点,而不是标配。

### 8.5 供应链——包括一个被核实为否的项

- **`postmark-mcp` 被植入过后门。** 引用 **MAL-2025-47604**("*Malicious code in postmark-mcp (npm)*",发布于 2025-09-26,OpenSSF 恶意包源,经 `api.osv.dev`),而不是那篇被到处转载的厂商博客。它没有 CVE ID;OSV 记录才是被木马化的软件包正确的一手来源类别。
- **这份榜单上的一个网关有自己的 CVE。** **CVE-2025-47274**,针对 ToolHive,发布于 2025-05-12,CVSS 4.0 基础分 **2.4 LOW**:"*Due to the ordering of code used to start an MCP server container, versions of ToolHive prior to 0.0.33 inadvertently store secrets in the run config files … an attacker who has access to the home folder of the user who starts the MCP server can read secrets without needing access to the secrets store itself.*" 已在 0.0.33 修复。
- **2025 年的基础簇**,每一条都在 CVE.org 上单独核实过:**CVE-2025-49596**(MCP Inspector < 0.14.1,9.4 CRITICAL —— "*unauthenticated requests to launch MCP commands over stdio*")、**CVE-2025-6514**(`mcp-remote`,9.6 —— "*OS command injection … when connecting to untrusted MCP servers due to crafted input from the authorization_endpoint response URL*")、**CVE-2025-53109/53110**(filesystem server 路径校验绕过,各 7.3)、**CVE-2025-52882**(Claude Code IDE 扩展接受 "*unauthorized websocket connections*",8.8)。
- ✅ **一个被核实为否的项,公布出来免得有人再报一遍。** agentgateway 的 `Cargo.lock` 里含 **rmcp 0.10.0**,它匹配 GHSA-89vp-x53w-74fx / RUSTSEC-2026-0189(也就是 CVE-2026-42559 那个 rebinding 缺陷,1.4.0 修复)。但它**没有被暴露**:`crates/agentgateway/Cargo.toml` 第 112 行把生产依赖钉在 `[dependencies]` 下的 `rmcp = { version = "3.0.0-beta.5", … }`,而那份 0.10.0 副本是第 212 行的 `legacy-rmcp`,在 `[dev-dependencies]`(第 191–226 行)里面,文件里还有注释 "*We need SSE client for testing but they removed it for some reason*"。dev 依赖不会被链进出货的二进制,而且 OSV 对 rmcp 3.0.0-beta.5 没有任何公告。**朴素地 grep 锁文件在这里会产出一个假阳性。**

### 8.6 本章*没有*确立什么

- ❌ **每个被收录的网关到底实现了哪个 MCP 修订版。** 这一轮没有为修订版支持情况读过任何产品的源码。任何形如「网关 X 支持 2026-07-28」的论断都是 **INCONCLUSIVE**,发表之前需要一次按锁定 commit 的源码阅读。两个是事实但**不是**答案的数据点:Envoy AI Gateway 在 `6722cca` 的 `internal/tracing/mcp.go` 里写死了 `attribute.String("mcp.protocol.version", "2025-06-18")`(那是一个 tracing 属性,不能证明数据路径的修订版),以及 Lunar MCPX 在 `package-lock.json` 里为 `mcpx-server` 解析出 `@modelcontextprotocol/sdk` **1.29.0**(而公告里 Tier-1 TypeScript SDK 的发布版是 `2.0.0`,发布于 2026-07-27T23:55:41Z)。
- ❌ **Tier-1 SDK 是否真的实现了 2026-07-28 的线上格式。** 公告称 "*All four Tier 1 SDKs speak `2026-07-28` as of today: TypeScript, Python, Go, and C#*",并称 Rust SDK "*supports the new spec in beta*"。发布时间线佐证了这一点(Python v2.0.0 2026-07-28T13:41:36Z、Go v1.7.0 13:09:53Z、C# v2.0.0 21:27:41Z,而 `rmcp-v3.0.0` 稳定版在 22:52:41Z —— 比规范 tag 晚约 6 小时,也晚于博客写下「beta」措辞的时点)。**发布 tag 与时间戳已核实;SDK 源码没有。** 把它当作一个被时间线佐证的厂商声明。
- ❌ **扩展的内部细节。** Tasks、MCP Apps 和 Skills-over-MCP 只通过规范索引的简介和 changelog 那一行读过。`subscriptions/listen` 与 MRTR 模式页没有完整读过,而且 **`schema.ts` 没有读** —— 规范自己说 TypeScript schema 是 "*the source of truth for all protocol messages and structures*",所以这里每一条关于结构的论断都来自从属的散文页面。
- ❌ **那些到处流传的博客垃圾数字。** 「150 million combined downloads」「9 of 11 MCP marketplaces」「30 CVEs in 60 days」散见于 dev.to / practical-devsecops / agent-wars-class 之类的聚合站,**没有找到任何一手来源** —— 没有厂商公告,没有 CVE 记录,没有论文。**不要复读它们。** 站得住的那个数字,是你能对着 NVD 复现的那个(§8.1)。

---

## 9. 被收录的网关到底差在哪

传输支持是评估者最先需要的东西,而本仓目前没有一条目写出它。按附录里的锁定 commit 读自源码或厂商文档:

| 网关 | 下游(面向客户端) | 上游(面向服务端) | 工具授权 | 许可证 / 层级的真实情况 |
|---|---|---|---|---|
| **IBM ContextForge** | HTTP、JSON-RPC、WebSocket、SSE、stdio、streamable-HTTP(厂商 README) | 同上,外加一个 `mcpgateway.translate --stdio … --expose-sse --expose-streamable-http` 桥 | RBAC + "*user-scoped OAuth tokens and unconditional X-Upstream-Authorization header support*" | Apache-2.0 —— **这一轮读到的最宽传输集** |
| **agentgateway** | SSE、Streamable HTTP | stdio、SSE、Streamable HTTP,**外加 OpenAPI 上游** | CEL,**空规则时全放行** | Apache-2.0。**Linux Foundation,不是 CNCF**(见本表下面的注记) |
| **Lunar MCPX** | Streamable HTTP、SSE | stdio、SSE、Streamable HTTP | 按 consumer / client name 的工具组 ACL | MIT 文件,**但是**仓库 README 写着 "*It remains open-source at its core and free for non-production/personal use. For production environments, we offer advanced features through guided onboarding and platform tiers*" —— 这与什么都不限制的 MIT 相冲突。没有单独的许可证文件为付费功能设卡,所以**哪些能力被设卡,仅凭这个仓库无法确定** |
| **Envoy AI Gateway** | 数据路径上**只有 Streamable HTTP**(`MCPRoute.Path`,默认 `/mcp`;SSE 是一种响应流式模式,不是一种传输) | 只能通过 `aigw` CLI 走 stdio,它会 "*run[s] local Streamable HTTP proxies for each command*" | JWT scope/claim + 实验性 CEL,**默认 `Deny`** | Apache-2.0;**v1.0.0 于 2026-06-23 发布**,但 MCP 的 CRD 在 `6722cca`(2026-07-23)上仍然是 `v1beta1` |
| **ToolHive** | —— | 容器化的 MCP 服务端 | Cedar + OIDC,按工具按用户限流 | Apache-2.0 |
| **Docker MCP Gateway** | —— | 容器 | `--tools` 启用列表(无身份概念) | MIT |
| **Pomerium** | HTTP | —— | `mcp_tool` 判据 | Apache-2.0 树里带着 MCP 代码 |
| **Kong AI Gateway** | —— | —— | MCP Tool ACL,按 consumer 过滤 `tools/list` | **仅企业版**;Kong OSS `391ee48` 的完整递归目录树里 MCP 路径**为零**,45 个插件里有 6 个是 `ai-*`,没有一个是 MCP |
| **Tetrate Agent Router Service** | 托管的 Envoy AI Gateway | —— | 继承 | SaaS。厂商材料描述为**模型成本外加 5% 费用**;`router.tetrate.ai/pricing` 返回 **HTTP 404**,所以这个数字来自博客/产品页,当成硬数据印出来之前请重新核实 |
| **Archestra** | —— | —— | RBAC/自定义角色属**企业版** | 按 `LICENSE.md` 的 SPDX 头路由规则,默认是 AGPL-3.0-only;**59 条被标为企业版的路径** |

**上表里有两行不在本仓的 MCP 一节里,而它们都该在。** **Kong AI Gateway**(（列在[企业合规](../README.zh-CN.md#-企业合规)一节）)的描述里完全没提 MCP,尽管它有 `ai-mcp-proxy`、`ai-mcp-oauth2` 以及按 consumer 过滤 `tools/list` ——本仓引以为傲的那个「层级」答案也是缺的。**Envoy AI Gateway**(（列在 [Kubernetes 原生与推理基础设施](../README.zh-CN.md#-kubernetes-原生与推理基础设施)一节）)只被描述为「CNCF-aligned GenAI access on Envoy Gateway」,MCP 只出现在 :633 和 :667 的动态行里——而 **Tetrate Agent Router Service**,也就是同一个引擎的托管*转售*版,却坐在 MCP 一节里。那个带着默认 `Deny` 的按工具授权 CRD 的开源原版,对读者来说才是更有用的条目。

**榜单需要的一处归属更正。** agentgateway 自己在 `7cd5647` 的 `CHARTER.md` 开头写着 "*Technical Charter (the "Charter") for agentgateway a Series of LF Projects, LLC*",而它的 README 页脚写着 "*Agentgateway is a Linux Foundation project.*" Linux Foundation 的新闻稿日期是 2025-08-25;其中唯一提到 CNCF 的地方是一位 CNCF Ambassador 的具名引语。Solo.io 另一个项目 **kagent** 才是 CNCF Sandbox 的那个。[MCP 与 Agent 网关](../README.zh-CN.md#-mcp-与-agent-网关) 一节 把 agentgateway 称作「CNCF proxy for agentic traffic」——那是错的,应该写成「Linux Foundation」。(README:286 对 Envoy AI Gateway 的「CNCF-aligned」和 :287 对 kgateway 的说法都没问题。)

**还有一条值得说明的非条目。** `katanemo/plano` 在 `6d315cc` 上是一个 MCP **客户端**,不是网关:MCP 在它这里以出站过滤器传输的形式出现(`type: mcp`、`transport: streamable-http`,"*MCP filters call a specific tool on a remote MCP server*"),以及作为 Anthropic Messages 的透传类型出现。它没有 MCP 工具 RBAC,没有 MCP 授权模块,也没有 MCP 服务端侧传输。它被放在 本节之外、也就是本节之外的位置,是**正确的** —— 记在这里,免得有人去「修」它。

---

## 10. 自己动手验证

按见效快慢排序。这里没有一项需要付费账号。

1. **确认规范修订版,以及它是 2026 年唯一的那一个 —— 30 秒。**
   ```bash
   gh api repos/modelcontextprotocol/modelcontextprotocol/git/ref/tags/2026-07-28 --jq '.object.sha'
   gh api "repos/modelcontextprotocol/modelcontextprotocol/contents/schema?ref=2026-07-28" --jq '.[].name'
   ```
   预期得到 `5f5440bb26a62e2cf3440b92da5a667efa03b267`,以及恰好六个目录条目。
2. **在相信任何 changelog 里的 SEP 引用之前,先查合并状态。** `gh api repos/modelcontextprotocol/modelcontextprotocol/pulls/2858 --jq '{title,merged,merged_at}'` 返回 `"Authorization spec split"` —— §2.1 那条告诫里的 DCR 弃用引用问题,一次调用就复现了。
3. **证明你的网关做到了 header/body 一致。** 发一个 `Mcp-Name` 头与 `params.name` 不一致的 `tools/call`。一个合规服务端会返回 **400** 加 JSON-RPC **`-32020`**。如果你的网关按头路由而服务端按 body 执行,那你就有了规范明令禁止的那种脑裂。
4. **证明工具错误对按状态码计量是隐形的。** 用一定过不了它自己校验的参数去调一个工具。预期得到 **HTTP 200**、`result.isError: true` —— 然后去看你的看板是不是把它算成了成功。
5. **拿产品去测 §7 里那个无状态论断。** 把一个 2026-07-28 时代的客户端指向一个宣称做会话感知路由的网关,看它会不会铸造或回显 `Mcp-Session-Id`;一条 2026-07-28 合规路径没有任何理由回显它,而且对 MCP 端点的 GET/DELETE 也不该再被服务(规范移除了 GET 流;**405** 是参考实现返回的东西,不是规范规定的状态码)。这就是那个能给 §7 里被降级的推断下结论的测试——而我们没有跑过。
6. **一次调用证明 Kong 没有出货任何 OSS MCP。**
   ```bash
   gh api "repos/Kong/kong/git/trees/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92?recursive=1" --jq '.tree[].path' | grep -i mcp
   ```
   输出为空。然后去 `ai-mcp-proxy` 和 `ai-mcp-oauth2` 插件页上读那行 `tier: ai_gateway_enterprise`。
7. **在你相信那个功能勾选框之前,先查授权默认值。** 在 agentgateway 里是 `crates/agentgateway/src/mcp/rbac.rs` —— `McpAuthorizationSet::validate` 在没有规则时返回 `true`。在 Envoy AI Gateway 里是 `api/v1beta1/mcp_route.go` —— `MCPRouteAuthorization.DefaultAction` 带着 `+kubebuilder:default:=Deny`。同一个品类,相反的失败方向。
8. **用实验证明 token 没有被透传。** 给网关递一个由上游第三方 AS 而不是网关自己的 AS 签发的 token。按规范它必须被拒:"*MCP servers **MUST NOT** accept or transit any other tokens.*"
9. **自己复现那个 CVE 计数,别引用我们的。**
   ```bash
   curl -s "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=Model+Context+Protocol&pubStartDate=2026-01-01T00:00:00.000&pubEndDate=2026-04-25T00:00:00.000" | jq .totalResults
   ```
   然后是第二个窗口。NVD 把区间上限卡在 120 天,这就是它要两次调用的原因。
10. **在把 agentgateway 那个 rmcp 假阳性报出去之前先复核一遍**:`grep -n "rmcp" crates/agentgateway/Cargo.toml`,确认 0.10.0 坐在 `[dev-dependencies]` 下面,而不是 `[dependencies]`。

---

## 11. 接下来去哪

如果你要挑一个,从[诉求速查表](../README.zh-CN.md#诉求速查表)和 [MCP 与 Agent 网关一节](../README.zh-CN.md#-mcp-与-agent-网关)开始——然后把那里每一句「按工具访问控制」都当成 §4 里的那个问题,而不是答案:*按工具启用*和*按 consumer 授权*是两种不同的产品。章节地图是 [HANDBOOK.md](../HANDBOOK.md)。

各兄弟章节,以及当客户端变成 agent 之后它们各自会变成什么:

- [**第一章——兼容面**](protocol-translation.zh-CN.md):三种 LLM 线协议格式之间的翻译。MCP 加上了**第四条**根本不关字段的翻译轴——modern/legacy 的时代分裂(§2.3),那里六种组合有两种是直接失败,而不是降级。
- [**第四章——AI 网关解剖**](gateway-anatomy.zh-CN.md):十一环的请求路径。一个 MCP 网关的各环是不同的名词——发现、同意、按动词授权、凭据交换、调用、审计——而它第 0 环的供应链风险实质上更大,因为一份工具定义可以在你批准之后再改(§6.2)。
- [**第五章——故障切换与可靠性**](failover-reliability.zh-CN.md):它的核心发现——一条被截断的流可以看起来很成功——在 §3.2 里有一个精确的 MCP 对应物:HTTP 200 里面一个 `isError: true` 的 body。重试语义也变了:续传被移除之后,"*A broken response stream loses the in-flight request*",而重发一个 `tools/call` 是在重新执行一次**副作用**,不是重新生成一次。
- [**第六章——缓存经济学**](caching-economics.zh-CN.md):那里的 §4 发现网关做缓存时 key 里没有租户。MCP 的 `cacheScope`(§3.3)把这条规则先一步写进了协议——然后又警告说光靠这个字段不是访问控制。

**本章刻意留作开放的三件事**,免得有人拿本章去引用它们:每个被收录的网关到底实现了哪个 MCP 修订版(§8.6 —— 目前这个品类里价值最高的那个开放问题);Tier-1 SDK 的线上行为是否与它们的发布声明一致;以及那些网关必须协商或降级、而不是盲目透传的扩展面(Tasks、MCP Apps、Skills over MCP)。

---

## 附录——本章依赖的全部来源

**MCP 规范,修订版 2026-07-28**(所有页面均检索于 2026-07-29):

| 页面 | 它在这里确立了什么 |
|---|---|
| [specification/latest](https://modelcontextprotocol.io/specification/latest) → 2026-07-28 | 当前修订版;关键安全原则;同意的那些 MUST;那句「cannot enforce at the protocol level」的让步 |
| [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | §2.1 的每一行;DCR 弃用与 #2858 那处引用怪象;错误码重新编号;`cacheScope`;OTel `_meta` key |
| [basic](https://modelcontextprotocol.io/specification/2026-07-28/basic) | 无状态;必填的 `_meta` 字段与 `-32602`/400 拒绝;错误码分配政策;`clientInfo`/`serverInfo` 未经验证、不得驱动安全决策 |
| [basic/versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) | Modern/Legacy/Dual-era 术语;那张六组合矩阵;`server/discover` MUST;扩展协商与回退 |
| [basic/transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports) · [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) · [streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) | 只有一个消息方向;`Mcp-Method`/`Mcp-Name` REQUIRED 及其面向中间件路由的理由;header/body 不匹配 → `-32020`;遗留头的处理与 405;Origin/localhost/鉴权三件套;stdio 分帧与取消;`X-Accel-Buffering: no` |
| [basic/authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) · [security-considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations) · [client-registration](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration) | OAuth 2.1 资源服务器角色;RFC 9728 MUST;RFC 8707 的那些 MUST 与 AS 支持的免责;token 不透传;混淆代理的按客户端同意 MUST;CIMD 选择优先级与 `https`+路径要求;stdio "SHOULD NOT follow this specification" |
| [server/tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts) | model-/user-/application-controlled 的划分;列表按授权而变;`x-mcp-header` 约束;错误分叉;工具名冲突指引;"a handle is a name, not a capability";那唯一一条审计 SHOULD |
| [server/utilities/caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) | `ttlMs` / `cacheScope` 的逐字定义、那条共享网关子句,以及不得只依赖 `cacheScope` 的警告 |
| [security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | 「MCP Proxy Server」定义;State Handle Hijacking;stdio 代理的提权路径及其免责;本地服务端一键同意 MUST;SSRF 缓解与 Smokescreen |
| [发布博文](https://blog.modelcontextprotocol.io/posts/2026-07-28/) · [RC 博文](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) | Tier-1 SDK 声明;迁移代价的让步;"locked as of May 21, 2026" 与「ten-week window」的措辞 |

**规范以规范性方式点名的 IETF/RFC 文档:**`draft-ietf-oauth-v2-1-13`(OAuth 2.1)、RFC 6750、RFC 8414、RFC 7591、RFC 8707、RFC 9728、RFC 9207、RFC 9110、`draft-ietf-oauth-client-id-metadata-document-00`。

**`gh api` 核实,全部跑于 2026-07-29:**tag `2026-07-28` → 发布于 2026-07-28T16:47:49Z,commit `5f5440bb26a62e2cf3440b92da5a667efa03b267`;tag `2026-07-28-RC` → 2026-05-29T12:51:22Z;该 tag 下的 `schema/` → 六个条目(`schema.ts` 98,426 字节,`schema.json` 181,474 字节);PR **2243**(2026-04-15)、**2322**(2026-05-06)、**2567**(2026-05-07)、**2575**(2026-05-11)、**2549**(2026-05-15)、**2577**(2026-05-15)、**2663**(2026-05-15)、**2596**(2026-05-18)、**2858**(2026-06-04)—— **全部 `merged=true`**;以及 `modelcontextprotocol/{typescript,python,go,csharp,rust}-sdk` 各仓的 SDK 发布。

**源码树,按锁定 commit 读取:**

| 项目 | Commit(日期) | 读了哪些文件 |
|---|---|---|
| agentgateway/agentgateway | `7cd564709f4834962d411e7a6219b30febdbd02f`(2026-07-28) | `crates/agentgateway/src/mcp/{rbac.rs,auth.rs,guardrails/mod.rs,upstream/{stdio,sse,streamablehttp}.rs}` · `src/http/{oauth.rs,auth/mod.rs,auth/oauth/transport.rs}` · `src/types/agent.rs` · `tests/tests/connect.rs` · `Cargo.toml` · `Cargo.lock` · `CHARTER.md` · `LICENSE` · `README.md` |
| envoyproxy/ai-gateway | `6722cca8d33896c4464c12f2de5aaf1238a569b6`(2026-07-23) | `api/v1beta1/mcp_route.go` · `internal/mcpproxy/mcpproxy.go` · `internal/tracing/mcp.go` · `internal/autoconfig/mcp.go` |
| TheLunarCompany/lunar | `c825cce7de2192b1e36c5ac7d6f333bde02a4579`(2026-07-28) | `mcpx/packages/mcpx-server/src/model/config/{config,permissions}.ts` · `src/services/{permissions,env-var-manager,target-server-connection-factory}.ts` · `src/server/{auth,oauth-router,downstream-transports}.ts` · `src/services/audit-log/` · `mcpx/LICENSE.MD` · `README.md` · `mcpx/package-lock.json` |
| pomerium/pomerium | `abbc8bf07c5b02c78a58385cf9ab36710b58fce0`(2026-07-28) | `pkg/policy/criteria/mcp_tool.go` · `authorize/evaluator/mcp.go` · `internal/mcp/` |
| stacklok/toolhive | `0a0cbd94929c050fa56e46b7f7da01c9b69f2dec` | `cmd/thv-operator/api/v1beta1/{virtualmcpserver_types.go,virtualmcpcompositetooldefinition_types.go}` |
| docker/mcp-gateway | `2bd20fe83dd04870e8d87dc1ed059d4d19fc7c68`(2026-07-23) | `docs/generator/reference/{mcp_gateway_run.md,mcp_policy.md}` · `cmd/docker-mcp/secret-management/` |
| archestra-ai/archestra | `d45667b329fa9bf8d83ddf05b7d09c57d27e52b9`(2026-07-29) | `LICENSE.md` · `platform/backend/src/services/identity-providers/enterprise-managed/exchange-strategies/{entra-obo-strategy,rfc8693-token-exchange}.ts` · `platform/backend/src/agents/subagents/dual-llm.ts` |
| IBM/mcp-context-forge | `eb1e212bbab90bbcdb410d5b577eac27bf677b03`(2026-07-28) | `README.md` |
| Kong/kong | `391ee48d3a68e8d0bbd0405ec1d02d75f768aa92`(2026-07-22) | 完整递归目录树(零个 "mcp" 路径)+ `kong/plugins/` 列表(45 个插件) |
| katanemo/plano | `6d315cc13820a037280d1b763afbe1ebd41c944d`(2026-07-27) | `skills/rules/filter-mcp.md` · `crates/brightstaff/src/handlers/agents/pipeline.rs` · `crates/hermesllm/src/apis/anthropic.rs` |

**厂商文档:**[Kong `ai-mcp-proxy`](https://developer.konghq.com/plugins/ai-mcp-proxy/) · [Kong `ai-mcp-oauth2`](https://developer.konghq.com/plugins/ai-mcp-oauth2/) · [Kong MCP Tool ACL 博客](https://konghq.com/blog/product-releases/mcp-tool-acls-ai-gateway)(2026-01-14)· [Pomerium MCP 能力](https://www.pomerium.com/docs/capabilities/mcp) · [Archestra 定价模型](https://archestra.ai/docs/platform-pricing-model) · [Tetrate Agent Router Service](https://tetrate.io/products/tetrate-agent-router-service) · [Linux Foundation agentgateway 新闻稿](https://www.linuxfoundation.org/press/linux-foundation-welcomes-agentgateway-project-to-accelerate-ai-agent-adoption-while-maintaining-security-observability-and-governance)(2025-08-25)。

**安全写作:**[Simon Willison —— 致命三要素](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)(2025-06-16)· [Simon Willison —— MCP prompt 注入](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/)(2025-04-09)。

**CVE 与安全公告,**每一条都在 2026-07-29 从 `cveawg.mitre.org/api/cve/` 或 NVD API 抓取:CVE-2026-13341 · CVE-2026-44192 · CVE-2025-34072(+ [VulnCheck 公告](https://vulncheck.com/advisories/anthropic-slack-mcp-server-data-exfiltration)、[研究者复盘](https://embracethered.com/blog/posts/2025/security-advisory-anthropic-slack-mcp-server-data-leakage/))· CVE-2025-49596 · CVE-2025-6514 · CVE-2025-53109 · CVE-2025-53110 · CVE-2025-52882 · CVE-2025-47274(ToolHive)· CVE-2026-42559 · CVE-2026-34742 · CVE-2026-11624 · CVE-2026-23744 · CVE-2026-33032 · CVE-2026-49257 · CVE-2026-22792/22793 · CVE-2026-32625 · CVE-2026-15643。OSV:**MAL-2025-47604**(`postmark-mcp`,npm,2025-09-26)· GHSA-89vp-x53w-74fx / RUSTSEC-2026-0189(rmcp < 1.4.0)· rmcp 3.0.0-beta.5 没有任何公告。

**仓内文件**(*仓内来源*,as_of 2026-07-29):[README.md](../README.md) 的 §*MCP & agent gateways*(MCP 与 Agent 网关一节,**26** 条)、第 258、284、286–287、297、735、799 行,以及第 633、667、676 行的动态条目 · [HANDBOOK.md](../HANDBOOK.md) 第八章 · [第一章](protocol-translation.zh-CN.md) · [第四章](gateway-anatomy.zh-CN.md) · [第五章](failover-reliability.zh-CN.md) · [第六章](caching-economics.zh-CN.md)。**没有任何 `data/` 文件带 MCP 相关字段** —— 本章识别出的那四条 MUST 级、机器可核的论断(所说的修订版、token 受众校验、按工具授权、代理 OAuth 的按客户端同意)在本仓今天没有任何一列对应。

---

*觉得有用?[⭐ 给榜单点个 Star](https://github.com/cuihuan/awesome-ai-gateway) — 下一个选网关的工程师就是这样找到它的。欢迎经 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充 — 上面每条论断都标了日期,并锚定到一个规范页面、一个 commit、一条 CVE 记录或一次 `gh api` 调用,方便你自己复核。我们最想收回来的那一条:按锁定 commit 读源码,查明每个被收录的网关实际说的是哪个 MCP 修订版(§8.6)。*
