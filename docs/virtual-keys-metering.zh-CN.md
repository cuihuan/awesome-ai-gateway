# 虚拟 key、预算与计量——网关怎么数你的钱,以及这笔账在哪儿数错

**语言：** [English](virtual-keys-metering.md) · 简体中文

*最近更新 2026-07-29 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)与[诚实安全记分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · 六个开源网关,在 **2026-07-29** 按锁定 commit 读源码,对「这个 key 付得起这次请求吗?」给出了三种互不兼容的答法——而只有 **LiteLLM** 把检查和计数器变更做成了*同一个操作*(一次 Redis `INCRBYFLOAT`,然后比较**自增之后**的值)。**new-api** 和 **one-api** 先按估算预扣,再通过一条「信任」旁路,恰好对余额最多的那批账号关掉这层保护。**Bifrost** 和 **Higress** 比较的是一个只在响应*之后*才动的计数器,所以对着一个只剩一分钱的预算并发 N 个请求,全都会放行。**Kong OSS** 在开源数据面里根本不做任何消费检查。而在准入的下游,计数本身才是更大的问题:一个生产 LiteLLM 部署报告 **80.7% 的流式成功行(304,148 行里的 245,562 行)**带着真实 token 数却写着 **$0 成本**([litellm#34875](https://github.com/BerriAI/litellm/issues/34875),开放,提交于 2026-07-28)。推理 token 被三家厂商摆成**三种互不兼容的排法**——在 OpenAI 和 Anthropic 上是输出计数的一个*子集*,在 Gemini 上是一个**独立加数**——所以只按 `output` 计费会在 Gemini 上漏掉每一个思考 token,而 `output + reasoning` 又会在另外两家上重复计数。new-api 出货其中第一种错误已经 **14 个月**,在报告者那次 Gemini 请求上留下 **89.84%** 的输出 token 未计费([new-api#1103](https://github.com/QuantumNous/new-api/issues/1103),自 2025-05-25 起开放)。独立的推理*价格*在六棵树里恰好存在于**一棵**;独立的缓存价格是**六分之三**。而崩溃窗口是秒级,不是毫秒级:LiteLLM 最多 **~15 秒**的消费行,Bifrost **10 秒**的预算增量,new-api 开了批处理是 **5 秒**——而在 Higress 里扣费是整条流的最后一条语句,所以一次被中止的请求干脆是免费的。

[第四章](gateway-anatomy.zh-CN.md)走完了请求生命周期,并标出了两个必然要拖进数据库的环节:**第 2 环,虚拟 key 与预算**,以及**第 9 环,计量**。本章就是这两环的完整深度。它回答四个功能对照表答不了的问题:一个「虚拟 key」到底圈定了什么(这个词指的是两个相反的对象),你的预算在并发下是否还站得住,你被计费的那个 token 数是不是厂商真正产出的那个 token 数,以及进程死掉时这两者会怎样。

一句话版本,也是本章存在的理由:**准入控制与计量是同一笔钱,被量了两次,而这两套机制几乎从不一致。** 准入在调用前按估算跑;计量在调用后按一个被三家厂商摆成三种形状的 usage 对象跑。本章里的每一种失败,都住在这两个数字之间的缝里。

来源就地说明。网关行为按锁定 commit 读自源码并引用原文;厂商语义逐字引自官方规范、SDK 类型或文档页并附检索日期;算术标明**出自我们**,且可以按旁边印出的数字复算;取自本仓数据文件的数字标为*仓内来源*并附其 `as_of`。凡是无法核实的,都在出现处就地标注,而不是抹平过去——§12 列出了本章刻意不予确立的内容。

**范围说明。** 这里读了六棵树:LiteLLM、new-api、one-api、Bifrost、Kong OSS 和 Higress。其中五个与第四章那七个重叠;**one-api** 是新加的,因为它是 new-api fork 出去的那个 MIT 原版,而 **Portkey OSS** 与 **Envoy AI Gateway** 这一轮没有重读。one-api 最新的 commit 是 `8df4a26`(2025-02-21),最新的 release 是 v0.6.10(2025-02-02),所以它的计量代码比这里对比的其他每一棵树都老大约 **17 个月**——这让「网关 X 更差」这种对着它的说法变得有误导性,也与本仓自己的判断一致:*"MIT original; maintenance slowed vs forks — new-api is the more active successor. Audit before prod."*(仓内来源,[data/gateways_eval.json](../data/gateways_eval.json),`as_of` 2026-07-28)。

---

## 1. 60 秒讲清概念

一个要向谁收谁的钱的网关,跑的都是同一个四步循环,而每一步都能自己出错。

| 步骤 | 它做什么 | 它用的那个数 | 这里会出什么错 |
|---|---|---|---|
| **1 · 圈定** | 把一个下游凭据解析成租户、模型白名单、预算和一组限额 | 无 | 「虚拟 key」这个词指的是两个相反的对象(§2.1);租户层级在 new-api 里只有一层,在 Bifrost 里是二选一互斥,在 LiteLLM 里是同时五层(§2.2) |
| **2 · 准入** | 决定这次请求能不能往下走 | 一个**估算**,在任何 token 存在之前就算出来 | 先查后改的竞态;从不对账的估算;一条对高余额账号跳过检查的旁路(§3) |
| **3 · 计数** | 把一个完成的响应变成 token | 厂商的 `usage` 对象,或者网关自己发明的一个兜底 | 永远不给 usage 的流;被摆成三种和四种排法的推理与缓存 token;本该放分词器的地方放了个估算器(§4–§7) |
| **4 · 结算** | 把 token 变成钱,并让它落地 | 一张以模型名为 key 的价格表 | 价格取决于*在响应里*才回来的字段;整数截断;因为进程死了而永远没落盘的那次写入(§8) |

**本章要论证的那条一句话规则:第 2 步和第 4 步必须互相对账——而这里读的六棵树里只有三棵试过,其中两棵还是从一个随进程一起死掉的 goroutine 里做的。** LiteLLM 用 `reserve_budget_for_request` 预留、用 `reconcile_budget_reservation` 结算。new-api 在 `SettleBilling` 里应用 `delta := actualQuota - preConsumed`。one-api 在 `go postConsumeQuota(...)` 里算 `quotaDelta := quota - preConsumedQuota`,发出去就不再等待。**Bifrost、Higress 和 Kong OSS 根本不形成调用前估算**,所以也就没有什么可对账的——它们的准入决策和它们的账单,只是关于同一次请求的两个不同事件,而当两者不一致时,没有任何东西会察觉。

---

## 2. 一个虚拟 key 到底圈定了什么

### 2.1 这个词指的是两个相反的对象

这就是那个功能对照表勾选框毫无用处的原因。在 **LiteLLM**、**Bifrost** 和 **new-api** 里,虚拟 key 是一个圈定到租户的*下游调用方凭据*——就是你发给数据团队的那个东西。在把这个词捧红的厂商 **Portkey** 那里,「Virtual Key」是一个*上游厂商凭据*——你放在保险库里的 OpenAI 或 Bedrock 密钥的别名。Portkey 自家的 Create Virtual Key API 参考页现在挂着这句原文告示:*"Deprecated. Use the Integrations API to store provider credentials and the Providers API to create AI Providers in your workspace."*(检索于 2026-07-29)。它的迁移页写着 *"Virtual Keys have been migrated to Model Catalog"*,虚拟 key 在 workspace 层被更名为 **AI Providers**,由 Model Catalog 提供 *"Fine-grained budgets, rate limits, and model allow-lists."*

所以一个买方拿「它有没有虚拟 key?」去横跨 LiteLLM 和 Portkey 提问,是在拿一个租户对象和一条保险库条目做比较;而本仓术语表里那一行——*"per-user/team keys the gateway issues in front of your real provider keys, with their own budgets and limits"*([README](../README.zh-CN.md#术语表))——描述的只是 LiteLLM 那一层意思。该问的是:**这个凭据指向哪个方向,它又携带了什么?**

### 2.2 三套 schema,并排看

LiteLLM 与 new-api 两列按下面的锁定 commit 读自源码。Bifrost 那一列是**厂商的治理文档**,检索于 2026-07-29——它的虚拟 key schema 这一轮没有读源码,这才是它那列更薄的原因,而不是因为它字段更少。

| 维度 | LiteLLM(`_types.py` L1029–1135 @`c274cf3`) | new-api(`model/token.go` `type Token struct` @`c27d1ef`) | Bifrost(治理文档,检索于 2026-07-29) |
|---|---|---|---|
| **模型白名单** | `models`、`aliases`、`access_group_ids` | `ModelLimitsEnabled` + `ModelLimits` | `provider_configs` 里的 `allowed_models` |
| **预算** | `max_budget`、`soft_budget`、`budget_duration`、`budget_id`、`budget_limits`(源码注释:*"multiple concurrent budget windows"*)、`model_max_budget`、`budget_fallbacks`、`throttle_on_budget_exceeded` | `RemainQuota`、`UsedQuota`、`UnlimitedQuota` —— **整数**(§10.4) | `max_limit` + `reset_duration`(`1m, 1h, 1d, 1w, 1M, 1Y`) |
| **限流** | `tpm_limit`、`rpm_limit`、`max_parallel_requests`、`model_rpm_limit`、`model_tpm_limit`、`mcp_rpm_limit`、`tag_rpm_limit`,外加 `rpm_limit_type`/`tpm_limit_type` ∈ `guaranteed_throughput \| best_effort_throughput \| dynamic` | **`Token` 结构体上没有 rpm/tpm 字段** ⚠️ 见下面的告诫 | `token_max_limit`、`request_max_limit`,各带自己的重置周期——文档写明 *"(VK-level only)"* |
| **过期 / 轮换** | `duration`、`auto_rotate`、`rotation_interval`(*"e.g. '30d', '90d'"*) | `ExpiredTime`,带行内注释 `// -1 means never expired` | —— |
| **租户层级** | `user_id` **和** `team_id` **和** `organization_id` **和** `project_id` **和** `agent_id`,同时存在 | 只有 `UserId` —— 一层深 | *互斥*:一个 team **或**一个 customer **或**都不挂 |
| **网络** | —— | `AllowIps`(一个 IP 白名单,带 `GetIpLimits()` 切分器) | —— |
| **多数对比都会漏掉的维度** | `guardrails`、`policies`、`prompts`、`allowed_routes`、`allowed_passthrough_routes`、`allowed_vector_store_indexes`(按 index 分读/写)、`enforced_params`、`blocked`、`allowed_cache_controls`、`tags`、`router_settings`、`object_permission`,以及 `key_type` ∈ `llm_api \| management \| read_only \| default` | `Group`、`CrossGroupRetry`(注释:*"跨分组重试，仅auto分组有效"*) | `key_ids` —— 限制这个 VK 能用哪些*上游*厂商 key |

由此掉出三件外面任何对比表都没写的事。

**(a) LiteLLM 的 key 是唯一一个能发现超额分配的。** `rpm_limit_type` 上的源码注释写着 *"raise an error if 'guaranteed_throughput' is set and we're overallocating rpm"* —— 这个网关知道已签发 key 的限额总和相对于真实容量是多少。这份对比里没有第二家建模了这件事。

**(b) 租户层级的形状根本不一样,所以「多租户」没法比。** LiteLLM 的 key 同时携带 user、team、org、project 和 agent;Bifrost 的是*互斥地*挂在一个 team 或一个 customer 上;new-api 的只有一个 `UserId`。一条在某一家能表达出来的预算策略,在另一家往往表达不了。

**(c) Bifrost 的日历边界重置是一道时区接缝。** 它的治理文档说,开启日历对齐时预算 *"reset at calendar boundaries in UTC (day/week/month/year) instead of on a rolling window"*。于是「月度预算」是一个 **UTC** 月,这既对不上厂商的账期,也对不上任何其他时区的财务月历。

> ⚠️ **一条告诫,因为它没被核实过所以写在这里。** rpm/tpm 字段的缺席只在 new-api 的 `Token` 结构体上核实过。new-api 是否从*另一张*表或中间件里执行按 key 的限流,**没有**检查过,所以本章并不主张 new-api 的虚拟 key 无法限流。

---

## 3. 准入:预留、预扣,还是读一下——以及三者在并发下各自会怎样

### 3.1 三种机制,以及一个一种都没实现的网关

这里的每一个网关都在厂商调用**之前**跑消费检查。区别在于这次检查对计数器*做了什么*,而这个区别就是全部故事。

| 网关 | 机制 | 原子性的单位 | 20 个并发请求对着一个快空的预算会怎样 |
|---|---|---|---|
| **LiteLLM** | **先预留,再对账。** `_reserve_budget_after_common_checks` 在鉴权里跑,紧跟在 `common_checks` 之后;`reserve_budget_for_request` 估算最大成本、自增,并按**自增之后**的值放行:`if current_spend > counter.max_budget:` | 每个计数器 key 一次 Redis `INCRBYFLOAT`(`redis_cache.py:872`),内存副本只在 Redis 返回之后才写 | 每个请求的自增对下一个都可见。这次预留随后由 `reconcile_budget_reservation` 结算成实际值 |
| **new-api** · **one-api** | **先按估算预扣,之后退款。** new-api:重试循环之前跑 `PreConsumeBilling`,`SettleBilling` 应用 `delta := actualQuota - preConsumed`。one-api:`CacheGetUserQuota` → 为负则拒绝 → `CacheDecreaseUserQuota` | 每行一条单语句 SQL `UPDATE ... quota - ?`,外加另一个 goroutine 里一次*脱钩的* Redis `HINCRBY`/`DECRBY` —— 两者彼此从不原子 | 被预扣限住——**除非信任旁路触发**(§3.3),那会恰好对余额最高的那批账号把机制变成下面那种「读一下」 |
| **Bifrost** · **Higress** | **读一个计数器,响应之后再减。** Bifrost:`if budget.CurrentUsage+baseline >= effectiveMaxLimit` → `DecisionBudgetExceeded` → HTTP 402。Higress `ai-quota`:一次裸的 Redis `GET`,然后 `if response.Integer() <= 0` → HTTP 403 | 请求路径上什么都没有。Bifrost 在 post-hook 里用 CAS 顶一个进程内 `sync.Map`;Higress 在流的最后一个 chunk 上发一次 `DecrBy` | **20 个全读到同一个值,20 个全放行。** 一个停在 `quota=1` 的 Higress 消费者可以同时跑无限多个请求 |
| **Kong OSS** | **没有。** 在 `391ee48`,OSS 树出货六个 AI 插件,没有一个读余额;末端的计量动作是 `kong.log.set_serialize_value("ai.<ns>.usage", usage)`,还被 `if not conf.logging or not conf.logging.log_statistics then return true end` 挡着 | —— | 什么都不会被拒,因为什么都没被集中计数。预算是企业版功能(`ai-rate-limiting-advanced`、`ai-proxy-advanced`) |

LiteLLM 自家源码就写明了另一种做法的失败之处——就在你用 `disable_budget_reservation` 关掉预留时它发出的那句警告里,`user_api_key_auth.py` 原文:

> *"Budget enforcement is read-time only — concurrent requests can each pass the spend check before their cost is recorded, so a configured budget may be briefly exceeded under high concurrency."*

这句话描述的,正是 Bifrost 和 Higress 在构造上就在做的事。四条开放的 LiteLLM issue 证明同一类问题也存在于 LiteLLM 自己剩下的那些读路径里([#34732](https://github.com/BerriAI/litellm/issues/34732) session 预算被绕过、[#34733](https://github.com/BerriAI/litellm/issues/34733) 窗口重置被覆盖、[#33325](https://github.com/BerriAI/litellm/issues/33325) 跨副本的 pod 本地消费、[#34101](https://github.com/BerriAI/litellm/issues/34101) project 预算没进预留)——四条都在 2026-07-29 经 `gh api` 核实为开放。

### 3.2 「原子」是一个按计数器算的词,不是按请求算的词

真正要紧、而且没有任何一份产品说明书写出来的精度问题:**LiteLLM 的原子单位是一个计数器,不是那组计数器。** `reserve_budget_for_request` 在 `_COUNTER_ENTITY_TYPES` 上循环——Key、Team、TeamMember、User、EndUser、Tag、Organization——一个一个地预留。每一次预留是原子的;把多层预留当作一个整体则不是。补偿性释放存在于一个 `except` 块和 `_release_applied_entries_best_effort` 里,所以进程内的失败路径是有处理的。

Bifrost 的序列化点写在它自己 `BumpBudgetUsage` 的文档注释里,原文:*"This is the serialisation point for every usage increment: callers MUST funnel through this method ... rather than doing a plain Load → clone → mutate → Store, which races."* 那是一次正确的进程内 CAS——而且它是进程本地的:OSS 树里恰好只有一个 `GovernanceStore` 实现,`LocalGovernanceStore`。

Higress 把这件事在两个插件之间劈开了。`ai-quota` 什么都没融合:一次 `GET` 用来查,一次发完不管的 `DecrBy` 用来扣,完成回调是 `nil`,所以那一刻的 Redis 失败既不重试也不记日志。`ai-token-ratelimit` 更强一些——两个阶段都是服务端 Lua,累加阶段是对所有命中规则 key 的一次原子 `EVAL`——但那次*检查*读的仍然是一个只在响应之后才动的计数器。

### 3.3 信任旁路:保护恰好从最输不起的那批账号身上被撤掉

两个 Go fork 都出货了同一个想法,而它值得被点名。new-api 的 `preConsume` 开头就是 `if s.shouldTrust(c) { s.trusted = true; effectiveQuota = 0 ... }`,而 `shouldTrust` 对钱包充值这一路解析为 `return s.relayInfo.UserQuota > trustQuota`。订阅被一条明确的三点注释排除在旁路之外。one-api 做的是同一件事,只是顺序反过来:`CacheDecreaseUserQuota` **先**执行,然后才由 `if userQuota > 100*preConsumedQuota { ... preConsumedQuota = 0 ... }` 把这笔扣款清零,注释写着 *"in this case, we do not pre-consume quota / because the user has enough quota"*。token 级的预扣被正确地跳过了;而 Redis 里的用户额度 key 已经被减掉了一个之后再也不会被收取的数额。

**这个后果值得读两遍。** 安全机制恰好对余额最大的那批账号被关掉——而那正是并发超发或一次丢失的结算代价最大的地方。项目自己的 tracker 里就挂着这个泄漏案例:[new-api#4429](https://github.com/QuantumNous/new-api/issues/4429),*"用户额度低于信任额度发生异常时预扣费泄漏"*,**开放**(经 `gh api` 于 2026-07-29 核实)。one-api 对这件事两层版本的修复——一个高额度用户用低额度 token 时拿不到预扣——是 [one-api#925](https://github.com/songquanpeng/one-api/pull/925),开于 2024-01-11,**在 2.4 年后于 2026-05-25 以 `merged=false` 关闭**。

---

## 4. 计量流水线,端到端

从厂商的最后一个字节到一行落地的记录之间,有七件事必须发生。每一件都是这个数字会变的地方。

| # | 环节 | 必须成立的事 | 不成立时的凭据 |
|---|---|---|---|
| 1 | **从线上抓取 usage** | usage 对象必须真的到达——而在 OpenAI Chat Completions 上,它只有在*客户端*主动选了才会到(§5.1) | 一个不带 `stream_options` 的调用方,就是选择了不被计量([litellm#22280](https://github.com/BerriAI/litellm/issues/22280),于 2026-06-15 以 `not_planned` 关闭) |
| 2 | **合并部分 usage** | Anthropic 的 `message_delta` 带的是*累计*总数,但只有 `output_tokens` 是必填字段;正确的规则是先用 `message_start` 播种,然后让 `message_delta` 里出现的任何字段胜出 | 只按 `message_start` 计量,会把一次服务端工具请求少收约 **4×**(§5.1) |
| 3 | **usage 永远不来时的兜底** | 兜底必须被标为估算,而不是冒充成计数 | Kong OSS 的 `chars ÷ 4`;new-api 的按模型族字符权重;Bifrost 与 Higress 计费**为零**(§5.2) |
| 4 | **拆解各项计数** | 推理在两家厂商是子集,在第三家是加数;缓存 token 遵循四种不同的包含 schema | [new-api#1103](https://github.com/QuantumNous/new-api/issues/1103)(§6.2);[new-api#5003](https://github.com/QuantumNous/new-api/issues/5003)(§7.2) |
| 5 | **定价** | 价格表的 key 必须不止是模型名——`service_tier` 与 `inference_geo` 是**在响应里**回来的(§10.5) | [litellm#34850](https://github.com/BerriAI/litellm/pull/34850) —— 一个 PR,截至 2026-07-29 未合并;提交于 2026-07-27,给缓存 token 打上区域地理溢价的补丁 |
| 6 | **归属** | 同一个数字必须同时到达客户端、账本和看板 | [new-api#6144](https://github.com/QuantumNous/new-api/issues/6144),开放——转发给客户端的 usage 是对的,用来计费的那份副本是坏的(在[第四章](gateway-anatomy.zh-CN.md) §2.1 第 9 环里确立;它的*方法论*后果是这里的 §11 第 3 步) |
| 7 | **持久化** | 这行记录必须活过进程 | §8 |

第 6 环是那个悄悄让你可能已经在跑的某个测试失效的环节。第四章和 README 都告诉你去 diff 响应里的 `usage` 字段来确认缓存折扣——而 new-api#6144 对那个测试完全隐形,因为响应是*对的*:报告者的客户端看到 `prompt_tokens: 1816` 带 `cached_tokens: 1792`(**98.7%** 命中,出自我们),而 new-api 自己的控制台日志把 `cache_tokens` 记成 `0` 并照此计费。他们的原话:*"这是真实的计费错误，不是单纯的显示问题"*。**响应里的 usage 是必要证据,不是充分证据。**

---

## 5. 数一条流

### 5.1 三家厂商,三份流式契约,没有共同形状

| | **OpenAI Chat Completions** | **OpenAI Responses** | **Anthropic Messages** | **Gemini `generateContent`** |
|---|---|---|---|---|
| **需要主动开启吗?** | **要** —— `stream_options: {"include_usage": true}` | 不要 | 不要 | 不要 |
| **usage 在哪里到达** | `data: [DONE]` *之前*的一个额外 chunk,`choices` 是空数组 | 在末尾的 `response.completed` 事件里 | `message_start`(初始)然后 `message_delta`(累计) | 未见文档 |
| **累计还是末端?** | 末端,全有或全无 | 末端 | **累计** | 未见文档 |
| **中止后你还剩什么** | *什么都没有* —— 厂商自己的免责原文:*"**NOTE:** If the stream is interrupted, you may not receive the final usage chunk which contains the total token usage for the request."* | 末端事件永远不会触发 | **最后一次观察到的累计值**,是可用的 | 未见文档 |
| **必填的明细字段** | 没有——整个 `usage` 对象都是选开的 | `input_tokens_details`、`output_tokens_details`、`total_tokens` 全部**必填** | `message_delta` 上只有 `output_tokens` 必填;每一个输入与缓存字段都是 `Optional` | —— |

两条结构性后果,而且它们在一条代码路径里无法调和。**正确的 OpenAI 处理是等末端否则就丢。正确的 Anthropic 处理是最后写入者胜。** 而 OpenAI 在同一家厂商内部就需要*两条*流式计量路径:Chat Completions 把 usage 挡在一个开关后面,而 Azure 的 Responses 端点会主动拒绝这个开关([litellm#28553](https://github.com/BerriAI/litellm/issues/28553),开放——*"Unknown parameter: stream_options.include_usage"*),而 Responses 那种形状又会在自动路由的路径上把成本丢掉([litellm#27459](https://github.com/BerriAI/litellm/issues/27459),开放)。

Anthropic 的合并规则值得写清楚,因为没有任何单独一页厂商文档写过它。`MessageDeltaUsage` 声明 `output_tokens: int` 必填,而 `input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`、`output_tokens_details` 和 `server_tool_use` 全是 `Optional`(anthropic-sdk-python @`f5c30d0`)。Anthropic 的基础流式示例展示的正是这种稀疏情形:`message_start` 带 `{"input_tokens": 25, "output_tokens": 1}`,而收尾的 `message_delta` 带 `{"output_tokens": 15}`,别的什么都没有。**用 `message_start` 播种;让 `message_delta` 里出现的任何字段覆盖它,因为那些是累计的、也是权威的。**

跳过这次合并有一个可测量的代价,就在 Anthropic 自己公布的示例里。在那条网页搜索的流上,`message_start` 报的是 `input_tokens: 2679`;收尾的 `message_delta` 报的是 `input_tokens: 10682`,带 `server_tool_use: {"web_search_requests": 1}`。**出自我们:10,682 ÷ 2,679 = 3.99×。** 服务端工具会跑额外的内部模型轮次,它们的输入 token 只出现在那个累计的 delta 里——而一个从 `message_start` 读输入的网关,做的恰恰是 Anthropic 自家 prompt 缓存页告诉实现者去做的事(*"within `usage` in the response (or `message_start` event if streaming)"*)。另外注意 `server_tool_use.web_search_requests` 是一个**根本不是 token 的计费单位**。

### 5.2 usage 永远不来时,六个网关各自会怎样

三种结果,其中两种计费为零。

| 行为 | 网关 | 实际发生了什么 |
|---|---|---|
| **重新分词** | **LiteLLM**、**one-api** | LiteLLM:`returned_usage.prompt_tokens = prompt_tokens or token_counter(model=model, messages=messages)`,并在累积的 `completion_output` 上用同一套写法。one-api:用的是真 tiktoken——但 `getTokenEncoder` 只为 `gpt-3.5`/`gpt-4o`/`gpt-4` 前缀构建编码器,其余落到 `defaultTokenEncoder` 并打日志 *"using encoder for gpt-3.5-turbo"*,所以 **Claude 和 Gemini 的流是用一个 OpenAI BPE 计量的** |
| **用启发式估算** | **new-api**、**Kong OSS** | new-api *直接*调用 `EstimateTokenByModel`,绕过了它自己确实拥有的 tiktoken 路径;这个估算器按子串(`gemini` / `claude` / 其余)路由进写死的字符类权重(Claude:`Word 1.13, Number 1.63, CJK 1.21, Symbol 0.4, MathSymbol 4.52, Emoji 2.6, Newline 0.89, Space 0.39`)。Kong OSS:补全按 `chars ÷ 4`,流式 prompt 按空白分词数 × **1.8**(两者都在[第四章](gateway-anatomy.zh-CN.md) §3.5 里确立) |
| **一分不收** | **Bifrost**、**Higress** | Bifrost 按响应形状从一个 usage 对象上读 `tokensUsed`;如果每个保护分支都不成立,它就停在 0,`computeTextCost` 在 `usage == nil` 时返回 0,`HasUsageData` 为 false,而 `shouldUpdateBudget := !update.IsStreaming \|\| (update.IsStreaming && update.HasUsageData)` 会跳过那次累加。Higress 在它的 `DecrBy` 之前就提前返回。**一条没有 usage 对象的流,就是一次免费请求** |

LiteLLM 的兜底带着一个有文档记录、而且可以推广的陷阱:`or` 这种写法把 `1` 当真值,而 Anthropic 的 `message_start` 出货的 `output_tokens: 1` 是一个游标。LiteLLM 的答案是 `_reset_anthropic_cursor_completion_tokens`,它把一个孤零零的游标值清零,好重新启用兜底。Bifrost 唯一一个刻意的例外走的是反方向:一次**失败**的请求只要带着 `BifrostError.ExtraFields.BilledUsage`,照样计费,注释写着 *"Anthropic charges us for them regardless."*

### 5.3 这个「不选开」是一条逃额度的路子

如果 usage 是选开的,而计量又是从 usage 推出来的,那么调用方就可以拒绝被计量。这正是 [litellm#22280](https://github.com/BerriAI/litellm/issues/22280) 的动机所在——原文,*"Users might avoid token limits by only streaming outputs"* ——它在 **2026-06-15** 因过期被自动关闭,`state_reason: not_planned`(经 `gh api` 于 2026-07-29 核实)。LiteLLM 确实出货了一个相关设置;读于 `c274cf3`,`common_request_processing.py` L1234–1245,在注释 `### AUTO STREAM USAGE TRACKING ###` 之下,它读的是 `general_settings.get("always_include_stream_usage", False)` ——**默认关闭**——而它的两个分支覆盖的是 `"stream_options" not in self.data` 和 `"include_usage" not in self.data["stream_options"]`。一个**显式**发送 `stream_options: {"include_usage": false}` 的客户端两个分支都不命中,所以就算这个设置打开了,这条「不选开」的路子依然活着。

一个网关还能把「让 OpenAI 的 usage 本来可解析」的那个契约本身也打破。[litellm#28735](https://github.com/BerriAI/litellm/issues/28735)(**开放**,2026-05-24)报告 LiteLLM 合成的末端 chunk 带的 `choices` 里有一个元素,而不是规范要求的 `choices: []`;一个严格按空数组去找 usage chunk 的下游客户端就找不到它。更早的那份报告 [#8450](https://github.com/BerriAI/litellm/issues/8450) 以 `not_planned` 关闭,提出的修复 [#8751](https://github.com/BerriAI/litellm/pull/8751) 以 `merged=false` 关闭——报了两次,修了零次(三者均于 2026-07-29 经 `gh api` 核实)。

---

## 6. 推理 token —— 三种互不兼容的排法

### 6.1 这个陷阱,用算术说清楚

| 厂商 | 推理住在哪里 | 在输出计数里面吗? | 厂商自己的原话 |
|---|---|---|---|
| **OpenAI** | `completion_tokens_details.reasoning_tokens` | **在——子集** | 关于 `rejected_prediction_tokens`,原文:*"However, like reasoning tokens, these tokens are still counted in the total completion tokens for purposes of billing, output, and context window limits."* |
| **Anthropic** | `usage.output_tokens_details.thinking_tokens` | **在——子集** | *"`output_tokens` remains the inclusive, authoritative total used for billing. This object provides a read-only decomposition for observability..."* |
| **Gemini** | `usageMetadata.thoughtsTokenCount` | **不在——独立加数** | `total_token_count` 是 *"the sum of `prompt_token_count`, `candidates_token_count`, `tool_use_prompt_token_count`, and `thoughts_token_count`."* |

**所以两种朴素映射没有一种在三家上都对。** 只按 `output` 计费在 OpenAI 和 Anthropic 上是对的,却**在 Gemini 上漏掉全部思考**。按 `output + reasoning` 计费在 Gemini 上是对的,却**在另外两家上重复计数**。Gemini 还带着第四个加数——`tool_use_prompt_token_count`,*"the number of tokens in the results from tool executions, which are provided back to the model as input"* ——一份按输入定价、却住在 `prompt_token_count` **之外**的内容。

Anthropic 的 `thinking_tokens` 是新的,而且带着厂商自己写明的两条免责,原文:这个计数是 *"Computed by re-tokenizing the raw reasoning text, so it may differ from the model's exact generation count by a small number of tokens"*,以及 *"`output_tokens - thinking_tokens` approximates the non-reasoning output."* 这直接要紧,因为第四章记录了 LiteLLM 通过 `output_cost_per_reasoning_token` 给推理单独定价:**在一个连厂商自己都标为近似的字段上劈开账单,会引入一个按 `output_tokens` 平铺计费本来不会有的误差。**

而 Anthropic 和 Google 都明说了:你要为自己根本看不到的 token 付钱。Anthropic:*"You're charged for the full thinking tokens generated by the original request, not the summary tokens. The billed output token count does **not match** the count of tokens you see in the response."* Google:*"Pricing is based on the full thought tokens the model needs to generate, despite only the summary being output from the API"*,以及 *"When thinking is turned on, response pricing is the sum of output tokens and thinking tokens."*(两者均检索于 2026-07-29)。

> 🔒 **这就是那些估算器无法被修好的证据。** 第四章把 Kong OSS 的 `chars ÷ 4` 和 new-api 的字符权重表称为「粗糙」。在推理模型上它们不是粗糙,是**结构性地做不到**:任何靠数它在线上看见的字节来计量的网关,在构造上就会少算推理,因为那些 token 根本不在响应里。换一个更好的分词器也没用。

### 6.2 谁给推理单独定价:六分之一

| 网关 | 有独立推理费率吗? | 细节 |
|---|---|---|
| **LiteLLM** | ✅ *有条件* | `output_cost_per_reasoning_token`,只在 `not is_text_tokens_total and reasoning_tokens > 0` 时应用。**价格表里没有这个 key 时它会退化成普通补全费率** —— 所以「有自己的价」是以价格表带着它为条件的 |
| **new-api** | ❌ | 在 `c27d1ef` 上全仓 grep `ReasoningTokens` 只返回透传和转换点;`service/text_quota.go` 或 `setting/ratio_setting/` 里没有比例、没有定价分支 |
| **Bifrost** | ❌ | `cost.go` 里唯一一处出现是一次结构体拷贝;推理搭在 `completionTokens` 里,按平铺的 `outputRate` 收费 |
| **one-api** | ❌ | 整个定价模型就是 `quota = ceil((promptTokens + completionTokens*completionRatio) * ratio)`;在所有 `.go` 文件里 grep reasoning 只返回一个结构体字段,计费路径里没有任何消费方 |
| **Kong OSS** | ❌ *而且更糟* | 没有注册任何推理指标,而且 `llm_total_tokens_count` 是**推导出来的**(prompt+completion)而不是存下来的,所以一个把隐藏推理 token 也算进去的上游总数会被丢掉—— [Kong/kong#14816](https://github.com/Kong/kong/issues/14816),**开放**(经 `gh api` 于 2026-07-29 核实) |
| **Higress** | ❌ | 额度以 token 计价,不是以钱计价:`totalToken := int(inputToken + outputToken)`。根本没有应用任何费率 |

Anthropic 还加了一层这份对比里没有任何网关建模过的褶皱:**思考 token 在不同轮次之间会换价格档。** 原文:*"**Current-turn thinking** always counts toward `max_tokens`, is billed as output tokens..."*,而 *"**Prior-turn thinking** ... On models that keep all prior turns, previous thinking blocks remain in context, count toward the window, and are billed as input tokens like the rest of the conversation history. On models that keep only the last turn, the API strips older thinking blocks automatically..."* 同一个 token 先按输出价收一次,之后再按输入价(或 0.1× 的缓存读取价)收,或者干脆不收——由哪个模型来答决定。**一个网关无法从它手里那段对话预测出自己下一轮的输入计数。**

---

## 7. 缓存 token —— 四种 schema,外加一个符号错误

### 7.1 这个「包含与否」的翻转不是二选一

[第一章](protocol-translation.zh-CN.md#2-逐字段的分歧对照)记录了 OpenAI 包含 / Anthropic 排除的那次翻转。实际上有四种排法,不是两种。

| 厂商 | 字段名 | 输入总数包含缓存流量吗? | 对账恒等式 |
|---|---|---|---|
| **OpenAI** | `prompt_tokens_details.{cached_tokens, cache_write_tokens}`;Responses 用 `input_tokens_details.*`;Usage API 用 `input_cached_tokens` / `input_cache_write_tokens` / `input_uncached_tokens` | **读和写都包含** | **出自我们**,基于 OpenAI 自己文档里的 Usage API 示例(`input_tokens: 1000`、`input_cached_tokens: 400`、`input_cache_write_tokens: 100`、`input_uncached_tokens: 500`):400 + 100 + 500 = **1000**,精确——一个对总数的三路划分 |
| **Anthropic** | `input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`(+ `cache_creation.{ephemeral_5m,ephemeral_1h}_input_tokens`) | **两者都排除** —— *"tokens after the last cache breakpoint"* | 厂商自己公布了:`total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens` |
| **Gemini** | `cachedContentTokenCount` | **包含** —— *"When `cached_content` is set, this also includes the number of tokens in the cached content."* | 未公布 |
| **DeepSeek** | `prompt_cache_hit_tokens`、`prompt_cache_miss_tokens` | 两个**互斥**的计数器 | ⚠️ **没有文档。** DeepSeek 两个页面都在 2026-07-29 抓取过;都没说 hit+miss 是否等于 `prompt_tokens`。措辞强烈暗示这个求和关系,但那是推断,不是文档 |

注意 **OpenAI 在同一家厂商内部有三套 usage 词汇表** —— Chat Completions(`prompt_tokens`/`completion_tokens`)、Responses(`input_tokens`/`output_tokens`)和 Organization Usage API(`input_tokens`/`input_cached_tokens`/……)。一个要把自己的账本和 OpenAI 自家账单控制台对齐的网关,得先映射三套名字,才谈得上开始跟 Anthropic 或 Google 比。[litellm#33772](https://github.com/BerriAI/litellm/issues/33772) 就是恰好发生在这道接缝上的一次失败。

### 7.2 最鲜活的那份凭据:这次翻转把输入 token 推成了负数

[new-api#5003](https://github.com/QuantumNous/new-api/issues/5003) —— *"命中缓存后，输入token变成了负数，计费出现严重BUG"* —— 创建于 **2026-05-21**,当天以重复关闭;重发的那条 [#5005](https://github.com/QuantumNous/new-api/issues/5005) 以 `not_planned` 关闭(两者均于 2026-07-29 经 `gh api` 核实)。版本 v1.0.0-rc.7。报告者的真实数字:输入 **56,322**,缓存读取 **72,960**,输出 **87**;费率 ⚡1.00/1M 输入、⚡5.00/1M 输出、⚡0.10/1M 缓存读取。

**出自我们,复现这个 bug** —— new-api 把输入算成了 56,322 − 72,960 = **−16,638**:

```text
(−16,638 × 1.00 + 72,960 × 0.10 + 87 × 5.00) / 1e6
  = −0.016638 + 0.007296 + 0.000435 = −0.008907   ✓ matches the reported charge
```

**出自我们,正确的数字:**

```text
(56,322 × 1.00 + 72,960 × 0.10 + 87 × 5.00) / 1e6
  = 0.056322 + 0.007296 + 0.000435 =  0.064053    ✓ matches the reporter's expected charge
```

符号反了。账本非但没收 ⚡0.064053,反而**贷记**了 ⚡0.008907 —— 每次请求朝着客户方向摆动 ⚡0.07296,用报告者的话说就是 *"站长会出现明显亏损"*。机制是:上游已经把缓存读取从输入里排除掉了(Anthropic 语义),而 new-api 又减了第二遍。

**一眼认出这类 bug 的标志:缓存读取(72,960)大于输入(56,322),这只有在排除语义下才可能出现。** 如果你的账本上出现过这种形状,同时你还假设输入为正,那你就中了这个 bug。

### 7.3 缓存写入定价是一项计量依赖,不是锦上添花

独立的缓存费率在六棵树里存在于三棵:**LiteLLM**(`cache_read_input_token_cost`、`cache_creation_input_token_cost`,外加 `cache_creation_input_token_cost_above_1hr`)、**new-api**(`CacheRatio` + `CacheCreationRatio`,带 5m/1h 拆分,并对基础扣费为负显式做了钳制)、**Bifrost**(读取、写入,以及一个 `>1hr` 写入费率,并对畸形的厂商载荷做了计数钳制)。one-api、Kong OSS 和 Higress 一个都没有。

有费率不等于用得上。Anthropic 对 5 分钟写入按基础输入的 **1.25×** 定价、1 小时写入按 **2×**(与[第六章](caching-economics.zh-CN.md)完全一致,没有出入),所以一个网关**没有 TTL 拆分就没法给缓存写入定价** ——而 SDK 自己的类型模型让空的情况合法:`CacheCreation` 把 `ephemeral_1h_input_tokens` 和 `ephemeral_5m_input_tokens` 都声明为必填 int,而父级 `Usage.cache_creation` 是 `Optional`。[new-api#6353](https://github.com/QuantumNous/new-api/issues/6353)(**开放**,2026-07-20)就是这个拆分缺席时会发生的事:两个级联 bug 把值清零,于是 *"总费用未包含缓存写入 Token 的费用"* ——对最贵的那一类输入 token 悄无声息地打了 100% 折。

---

## 8. 崩溃安全的记账

在厂商响应和一行落地记录之间,钱住在三个地方:一个进程内的队列或 map、一个 Redis 计数器,以及数据库。你丢的是哪一个,决定了这笔错由谁来吃。

| 网关 | 落地写入之前钱待在哪 | `SIGKILL` 时丢什么 | 优雅停止时丢什么 | 谁来吃 |
|---|---|---|---|---|
| **LiteLLM** | 消费日志行在一个进程内 list 里;聚合增量在一个 `asyncio.Queue` 里;由调度任务按 `batch_writing_interval = proxy_batch_write_at + random.randint(0, 5)` 刷出,`PROXY_BATCH_WRITE_AT` 默认 **10** | 最多 **~15 秒**的*账本行* —— 但**不丢强制**,因为预留已经被 `INCRBYFLOAT` 进了 Redis | 同样会丢:`proxy_shutdown_event` 会断开 Prisma 并刷出 langfuse/billing 指标,但**从不排空消费队列** | **租户** —— 那次预留会以超额预留的形式一直留到 TTL |
| **Bifrost** | 内存 `sync.Map` 计数器,每 `workerInterval = 10 * time.Second` 落一次 | 最多 **10 秒**的预算增量 | **什么都不丢** —— `Cleanup()` 先调用 `DumpBudgets` 再调用 `DumpRateLimits`,注释原文点明了这个风险:*"Final flush of in-memory deltas to DB before shutdown. Without this, any deltas accumulated since the last `workerInterval` tick are lost."* | 运营方 |
| **new-api** | 开了 `BATCH_UPDATE_ENABLED` 时,是一个互斥锁保护的进程内 `map[int]int`,由 `BATCH_UPDATE_INTERVAL` 定时器排空,默认 **5** 秒 | 那批 SQL 增量;以及退款,它被派进一个随进程一起死掉的脱钩 `gopool.Go` goroutine | 同样的脱钩 goroutine 暴露面 | **租户** —— 预扣的估算就那么扣着,永远不对账 |
| **one-api** | 全部:`go postConsumeQuota(...)` 发出去就不等待,handler 立刻返回 | 那次差值结算、缓存重新同步、`RecordConsumeLog` 那行记录,**以及**已用额度/渠道计数器 | 同上 | **租户** —— 预扣了却没有任何日志行解释它;在信任路径上,这次请求是免费的*而且隐形* |
| **Higress** | 什么都没有 —— `DecrBy` 是整条流的最后一条语句,在 `if !endOfStream { return data }` 之后 | 整笔扣费 | 同上 | **运营方** —— token 烧掉了,额度纹丝不动 |
| **Kong OSS** | `ngx.ctx` 上的一行日志,按请求、按 worker | 那次请求的分析记录 | 同上 | 没人,而这正是重点:**没有余额可以被算错,这同时也意味着 Kong OSS 无法发现或对账这次丢失** |

三条值得带进设计评审的细化。

**(a) 丢掉强制和丢掉账本是两种不同的丢失。** LiteLLM 丢的是账本行,但保住了强制,因为调用前的预留已经在 Redis 里。new-api 和 one-api 丢的是*对账*,也就是说这笔费用冻结在估算上。Higress 丢的是整笔费用。注意方向:先扣款的机制失败时**对租户不利**;响应后再减的机制失败时**对运营方不利**。

**(b) LiteLLM 更窄的那个窗口默认是关的。** `use_redis_transaction_buffer` 默认 `False`;而当它打开时,已弹出却失败的数据在日志文字里就被承认丢了:*"Data already popped from Redis may be lost. Error: %s"*。两条开放 issue 从外部覆盖了同一块地面([#34805](https://github.com/BerriAI/litellm/issues/34805) 停机时缓冲被丢弃、[#34820](https://github.com/BerriAI/litellm/issues/34820) 行在 DB 写入被 await 之前就被弹出)。

**(c) 活不过重启的幂等性不叫幂等性。** Bifrost 用 `tryClaimBilling` 按 `RequestID:AttemptNumber` 做物理调用级的计费去重——确实做得好,而且是这份对比里唯一这么做的机制——但那个 map 在内存里,`billedEntryTTL = 5 * time.Minute`,所以它同样活不过一次重启。

---

## 9. 多租户隔离,以及为什么有些网关必须要 Postgres

第四章确立了这条规则:**第 1、2、9 环是那些逼你上数据库的环节** —— 鉴权需要 key 查询,预算需要一个可持久的计数器,计量需要一个账本。本章补上了这个计数器为什么不能干脆住在内存里的理由,而这个理由就是 §3.1 加上 §8。

一个预算计数器必须是**共享的**(否则每个副本都在强制自己那份私有上限——这正是 [litellm#33325](https://github.com/BerriAI/litellm/issues/33325),跨副本的 pod 本地消费),在并发下是**原子的**(§3.1),并且**跨重启可持久**(§8)。Redis 给你前两样,不给第三样;关系型存储给你第三样,并通过行锁和事务给你第二样的一个可用版本。这就是那些拥有真正虚拟 key 的网关**两个都跑**的原因:Redis 做热计数器,Postgres 或 MySQL 做账本和 key 表。LiteLLM 的回写是每个实体表一个 Prisma 事务,ID 排序以固定加锁顺序;Bifrost 的周期性落盘是一个 GORM 事务,ID 排序,外加一个单调的 `last_reset` 守卫;new-api 和 one-api 用的是单语句 `UPDATE ... quota - ?` 行写入,**没有**外层事务,而且在 new-api 的情况下连 `WHERE quota >= ?` 守卫都没有——所以余额可以变成负数。

一个租户模型必须点名的三道隔离接缝:

- **计数器作用域。** LiteLLM 一次性对七种实体类型预留(Key、Team、TeamMember、User、EndUser、Tag、Organization);Bifrost 把一个 VK 互斥地挂在一个 team **或**一个 customer 上;new-api 和 one-api 只有单一的用户层。一条在某一家能表达的预算,在另一家往往表达不了。
- **跨节点一致。** Bifrost 的 `CheckBudget` 比较的是 `budget.CurrentUsage + baseline`,并在落盘时把 `baselines` 折进持久化的值里,这暗示存在一个把对端用量喂进来的集群层——但 OSS 树里恰好只有一个 `GovernanceStore` 实现,而这一轮**没有**定位到那个非空 `baselines` map 的生产者。本地机制已确认;仅凭这个仓库,多节点语义 **INCONCLUSIVE**。
- **重置边界。** Bifrost 的日历对齐预算按 **UTC** 边界重置(§2.2)。如果你的财务月不是 UTC 的,那你的「月度预算」和你的账期就是两个不同的窗口。

买方的解读和第四章一样,而本章把它磨得更锋利:**一旦你想要那个最能证明网关价值的功能——带强制预算的虚拟 key——你就已经签下了两个数据存储、一套迁移方案和一份 on-call 排班。** 一个不带这两样却提供预算的网关,给你的就是 §3.1 里那种先读后减,不管它有没有这么说。

---

## 10. 失败模式,附凭据与复算的算术

下面每一条 issue 都在 **2026-07-29** 经 `gh api` 抓取过,并确认存在、确认带着这里给出的状态、确认确实说了它被引用的那件事。标注**出自我们**的算术是按 issue 正文里的数字算出来的,并且印出来供你重跑。

### 10.1 流式计量在生产规模上失效 —— 80.7% 的行是 $0

[litellm#34875](https://github.com/BerriAI/litellm/issues/34875),**开放**,创建于 **2026-07-28**。报告者原文:*"In our proxy deployment (`litellm[proxy]==1.83.14`, Python 3.13), **80.7% of streaming success rows (245,562 of 304,148)** recorded a zero cost with real token counts. The rate was load-independent but strongly model-correlated (~93–97% for gpt-5.x streams, ~0% for Claude streams), consistent with a scheduling race rather than a data problem."* **出自我们:245,562 ÷ 304,148 = 80.74%** ✓。他们的根因:流式处理器把 `async_success_handler` 排成一个 asyncio task,*同时*又把 `success_handler` 提交给线程池执行器;两者变更的是同一个未拷贝的 `model_call_details` dict;同步 handler 无条件把 `response_cost` 设成 `None`,而异步 handler 写的是真实成本,并且 *"no lock or ordering between the asyncio task and the executor thread."* 这是**计量流水线里的一个并发 bug** —— 与 §3 的预算竞态和 §8 的崩溃丢失是不同的轴,也是「流式计量在规模上会失效」这件事目前最强的证据。

### 10.2 同一个成本引擎里的两个方向 —— 三份凭据,从一月到六月

| 凭据 | 方向 | **我们的**复现 |
|---|---|---|
| [litellm#26807](https://github.com/BerriAI/litellm/issues/26807),**开放**,2026-04-29 —— 自定义定价路径里缓存 token 按全额输入价计费 | **多收 1.67×** | 报告值:`prompt_tokens=6074`、`cached_tokens=3456`、`completion_tokens=285`;费率 2.5e-6 输入 / 1.5e-5 输出 / 2.5e-7 缓存读取;返回成本 **0.01946**。有 bug 时:6074×2.5e-6 + 285×1.5e-5 = 0.015185 + 0.004275 = **0.01946** ✓(每一个 prompt token 都按裸输入价)。正确时:(6074−3456)×2.5e-6 + 3456×2.5e-7 + 0.004275 = 0.006545 + 0.000864 + 0.004275 = **0.011684**。多收 **0.01946 ÷ 0.011684 = 1.67×** |
| [litellm#18599](https://github.com/BerriAI/litellm/issues/18599),关闭于 2026-01-03;修复 [PR #18607](https://github.com/BerriAI/litellm/pull/18607) **已核实合并**于 `2026-01-03T18:39:01Z` —— 推理 token 被拿来*代替*总补全 token 定价 | **少收 7.02%** | gpt-5-nano,`prompt_tokens=17`、`completion_tokens=482`、`reasoning_tokens=448`。正确:17×0.05/1e6 + 482×0.40/1e6 = **0.00019365** ✓。有 bug:17×0.05/1e6 + 448×0.40/1e6 = **0.00018005** ✓ —— 只给那 448 个推理 token 定了价,34 个非推理补全 token 被丢掉。少报 **7.02%**。*(这条 issue 已在[第四章](gateway-anatomy.zh-CN.md)里被引用过;这里新增的是复算的算术和下面那条兄弟凭据)* |
| [litellm#30488](https://github.com/BerriAI/litellm/pull/30488),一个 PR,**已核实合并**于 `2026-06-17T11:47:31Z` —— Perplexity 手动成本兜底里推理 token 被**重复计费** | **多收 2.17×** | 作者给出的 `perplexity/sonar-deep-research` 修复前后,`prompt_tokens=9, completion_tokens=20, reasoning_tokens=15`:**$0.000223 → $0.000103**。这个 PR 自称是 *"Sibling fix to #18607 which addressed the same convention mismatch in the central cost path"* |

**可复用的教训在这一对上,而不在其中任何一条上。** 子集 vs 加数这个约定(§6.1)在一个成本引擎里不是决定一次就完事的——它在**每一个厂商适配器里、永远地**被重新决定一次。这就是为什么同一类 bug 一月落在中心路径上(少收),六月又落在 Perplexity 适配器上(多收)。

### 10.3 一个开放了 14 个月的推理 bug,自己的载荷就自证了

[new-api#1103](https://github.com/QuantumNous/new-api/issues/1103),*"gemini reasoning未计费"*,开于 **2025-05-25**,在 2026-07-29 **核实仍然开放**。报告者返回的载荷:`prompt_tokens: 7`、`completion_tokens: 124`、`total_tokens: 1228`、`completion_tokens_details.reasoning_tokens: 1097`。

**出自我们:**7 + 124 = 131,但 `total_tokens` 写的是 1228 —— 而 1228 − 7 = 1221 = 124 + 1097,分毫不差。所以这个网关自己的 `total_tokens` 算得是对的,而它的 `completion_tokens` 漏掉了那 1,097 个推理 token;**这个载荷自相矛盾**。计费的输出是 1,221 里的 124 = **10.16%**,也就是说 **89.84% 的输出 token 没被计费**。这正是 §6.1 从 Gemini 那种独立加数排法里预测出来的失败,已经开放了一年多。

### 10.4 账本装不下这个价格

与上面每一个 token 语义 bug 都正交:new-api 的 `Token` 结构体声明 `RemainQuota int` 和 `UsedQuota int` —— Go 的 **int**(读于 `c27d1ef`),所以每一次请求的成本都被四舍五入到一个整数额度单位。[new-api#2608](https://github.com/QuantumNous/new-api/issues/2608),*"quota 精度导致的计费问题"*,自 2026-01-08 起**开放**,引用了那段代码:`if modelRatio != 0 && calculateQuota <= 0 { calculateQuota = 1 }`,紧接着是 `quota := int(calculateQuota)`。三行里两个缺陷——任何非零的亚单位成本都被强行**向上**拗到 1(多收),而 `int(...)` 在其他所有地方**朝零截断**(少收)。报告者的问题是该拿去问任何厂商的那个问题:*"quota 设置成整数是有什么考量吗？"* **就算一个网关把每一个 usage 字段都读得完美无缺,只要它账本的类型装不下这个数,它照样算不对账。**

### 10.5 价格取决于*在响应里*才到的字段

anthropic-sdk-python @`f5c30d0` 里的 `Usage` 声明了 `inference_geo: Optional[str]` —— *"The geographic region where inference was performed for this request"* —— 和 `service_tier: Optional[Literal["standard", "priority", "batch"]]` —— *"If the request used the priority, standard, or batch tier."* Google 有对应物:usage 元数据上的 `traffic_type`,*"Output only. The traffic type for this request."* **两者都会改变价格,而且两者都是被返回的而不是被请求的,所以一次请求的价格无法从这次请求本身知道。** [litellm#34850](https://github.com/BerriAI/litellm/pull/34850)(一个 **PR**,截至 2026-07-29 开放且未合并;提交于 2026-07-27)就是一个网关正在为这件事打补丁:*"fix(anthropic cost): apply regional geo uplift to cached tokens"*。规则是:**任何只按模型名做 key、从静态 模型→价格 表定价的网关,都会给地理溢价和优先档流量定错价——而且这个错误是隐形的,因为模型名匹配上了。**

### 10.6 一个自 2023 年起就开放且未合并的逃费修复

[one-api#412](https://github.com/songquanpeng/one-api/pull/412),*"为函数调用加上计费避免逃费问题"*,一个 **pull request**,创建于 **2023-08-13**,**状态开放,`merged=false`**(经 `gh api` 于 2026-07-29 核实)。作者自己的说明承认这个估算和 OpenAI 差一两个 token,但 *"比不计费好"*。和 #925(§3.3)放在一起,诚实的说法**不是**主动的倒退:而是一个本仓早已记录为放缓的项目里,躺着两个未合并的修复。

---

## 11. 自己动手验证

按每分钟的回报排序。第 1–3 步只要一个 API key,不需要网关源码。

1. **带与不带 `stream_options` 各跑一条流做 diff —— 五分钟,而且是本章里价值最高的一次测量。** 把同一个流式 prompt 经你的网关发两次,一次带 `stream_options: {"include_usage": true}`,一次不带这个字段,然后读两条消费记录。这会解掉本章没能解掉的一处冲突:[litellm#22280](https://github.com/BerriAI/litellm/issues/22280) 的报告者断言 *"Without that attribute, token count is zero"*,而第四章确立的是 LiteLLM 会退回到在 messages 上跑本地 `token_counter` —— 那会按*估算*计费,而不是零。然后再用显式的 `{"include_usage": false}` 重复一遍;§5.3 预测就算 `always_include_stream_usage` 开着,这条不选开的路子依然活着。
2. **故意把预算打爆。** 给一个虚拟 key 设一个很小的上限,然后打 20 个并发请求。§3.1 按机制预测结果:先预留再对账会停在上限上;先读后减会按你的并发量大致超发。然后把账户余额提到信任阈值以上再来一遍——在 new-api 和 one-api 上,这会切换机制(§3.3)。
3. **对三个数字,不是两个。** 取一小时的流量,按 token 类别(**包括缓存写入**)比较 (a) 你客户端收到的 `usage` 对象、(b) 你网关自己的消费日志、(c) 厂商控制台。第四章和 README 都只停在 (a) 对 (c);[new-api#6144](https://github.com/QuantumNous/new-api/issues/6144) 对那个测试是隐形的,因为 (a) 是对的而 (b) 不是(§4)。
4. **在流中途杀掉 pod,然后去读账本。** 起一条长流,`SIGKILL` 掉网关,检查消费记录在不在、预算有没有动。§8 预测你会丢的是两者里的*哪一个*,因而也就预测了这笔错由谁来吃。用 `SIGTERM` 再来一遍:Bifrost 的优雅路径会刷出,LiteLLM 不会。
5. **在你信任那个计数之前,先 grep 出估算器。** 不需要 key:
   ```bash
   # Kong OSS — the chars÷4 and ×1.8 estimators
   grep -n "strip(response) / 4" kong/llm/plugin/shared-filters/normalize-sse-chunk.lua
   grep -n "stream_mode\") and 1.8" kong/llm/plugin/shared-filters/normalize-request.lua
   # new-api — the per-family character weight table and the bypass around its own tokenizer
   grep -n "EstimateTokenByModel" service/usage_helpr.go service/token_estimator.go
   # one-api — which models get a real encoder, and what the rest fall back to
   grep -n "defaultTokenEncoder\|using encoder for" relay/adaptor/openai/token.go
   ```
6. **去找那个负输入的标志。** 在你的消费日志里查任何一行缓存读取 token 大于输入 token 的记录。在 Anthropic 的排除语义下这种形状是正常的;在包含假设之下,它就是 §7.2 那个符号错误在等着发生。
7. **要的是对账,不是那次检查。** 那个能把 §3.1 里各种机制区分开的厂商问题只有一个:*"把调用前估算和结算后实际值做比较的那条代码路径给我看一下。"* 这里读的六棵树里有五棵根本没有。
8. **自己确认这些锁定 commit** —— 附录里的每一个 commit 都在 2026-07-29 用这种方式重新确认过:
   ```bash
   gh api repos/BerriAI/litellm/commits/c274cf321c5c35c629220a89bb497d15b56f870f --jq '.commit.committer.date'
   gh api repos/QuantumNous/new-api/issues/1103 --jq '{state,created_at,title}'
   ```

---

## 12. 接下来去哪

如果你正在选网关,从[诉求速查表](../README.zh-CN.md#诉求速查表)开始,并且把任何厂商的「虚拟 key ✅」——以及 README 术语表里那条 *Virtual keys* 条目——当成一个关于 §2.2 那张维度表的问题,而不是一个答案——然后去问 §11 的第 7 步。如果你已经在跑一个了,§11 的第 1 步和第 2 步加起来只花你十分钟,回答的却比任何产品说明书都多。

在本手册里(地图在 [HANDBOOK.md](../HANDBOOK.md)):[第一章——兼容面](protocol-translation.zh-CN.md)负责本章给出定价的那份逐字段 usage 分歧;[第四章——AI 网关解剖](gateway-anatomy.zh-CN.md)是第 2 环和第 9 环在请求路径里的位置,而本章就是那两环的深水区;[第五章——故障切换与可靠性](failover-reliability.zh-CN.md)负责流中途中止,以及 §8 只擦到边的那个重试计费问题;[第六章——缓存经济学](caching-economics.zh-CN.md)提供了 §7.3 所依赖的 1.25×/2×/0.1× 倍率,而且从这一轮里得到了一个新的失败模式——**改动思考配置会无声地让 prompt 缓存失效。** Anthropic 原文:*"The thinking configuration and the resolved `effort` level are rendered into the prompt itself, so changing any of them starts a new cache prefix. ... Treat any thinking or effort change as starting the cache over."* 按第六章自己的算术,一个只写不命中的缓存比完全不缓存还糟(在 21.74% 的盈亏平衡点之下),所以**任何按请求变动 effort 的路由器都是一台缓存毁灭机** —— 这是路由与缓存两章目前都没点名的一条连接。

**本章明确没有确立的内容,免得有人拿本章去引用它们。**(a) LiteLLM 的多层预留在循环中途被杀进程时,会不会留下*部分*已应用的预留:按代码检视,这个循环一次预留一个计数器,并在 `except` 块里带补偿性释放,取消路径的 docstring 也描述了那种孤儿类别(*"Left alone it pins the spend counter above real spend and 429s subsequent requests until the counter's TTL expires"*)——但这没有实跑,消费计数器 key 的实际运行时 TTL 也没有确认。**INCONCLUSIVE**,而不是一个有确定时长的孤儿窗口。(b) Bifrost 的跨节点 `baselines` 语义(§9)。(c) Gemini 是不是在每个 chunk 上都累计地流式给出 `usageMetadata` —— 这个说法被广泛复读,但 Google 的一手参考只把这个字段定义为 *"Output only. Metadata on the generation requests' token usage"*,对流式只字未提;找到的每一个支持性来源都是二手的,其中好几个还是本仓自己的观察名单视为未核实的中转商文档镜像。**任何网关的 Gemini 流式计量都建立在观察到的行为上,而不是一份契约上,因此它可以随时改变而不作通知。**(d) DeepSeek 的 hit+miss 计数器是否等于 `prompt_tokens`(§7.1)。(e) 省略 `include_usage` 到底是计费为零还是计费一个估算(§11 第 1 步)。(f) Anthropic 的流式文档页在它的*thinking* 示例里同时从 `message_start` 和 `message_delta` 中省掉了 `usage`,而同一页的其他每一个示例都带着它——这被记为一处**文档不一致**,最可能是为简洁而省略,并且明确**不是**关于运行时行为的论断,因为 SDK 类型要求 `MessageDeltaUsage` 上必须有 `output_tokens`。

---

## 附录——本章依赖的全部来源

**源码树,按锁定 commit 读取**(每个 SHA 均于 2026-07-29 经 `gh api repos/OWNER/REPO/commits/SHA` 重新确认;committer date 按返回值):

| 项目 | Commit(committer date) | 读了哪些文件 |
|---|---|---|
| BerriAI/litellm | [`c274cf321c5c35c629220a89bb497d15b56f870f`](https://github.com/BerriAI/litellm/tree/c274cf321c5c35c629220a89bb497d15b56f870f)(2026-07-29) | [`proxy/_types.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/_types.py) · [`proxy/auth/user_api_key_auth.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/auth/user_api_key_auth.py) · [`proxy/spend_tracking/budget_reservation.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/spend_tracking/budget_reservation.py) · [`proxy/proxy_server.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/proxy_server.py) · [`proxy/common_request_processing.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/common_request_processing.py) · [`proxy/db/db_spend_update_writer.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/db/db_spend_update_writer.py) · [`proxy/db/db_transaction_queue/redis_update_buffer.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/proxy/db/db_transaction_queue/redis_update_buffer.py) · [`caching/redis_cache.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/caching/redis_cache.py) · [`constants.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/constants.py) · [`litellm_core_utils/streaming_chunk_builder_utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/streaming_chunk_builder_utils.py) · [`litellm_core_utils/llm_cost_calc/utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/llm_cost_calc/utils.py) |
| QuantumNous/new-api | [`c27d1ef651c608dd8b9e60848a7e0f13a8619d9b`](https://github.com/QuantumNous/new-api/tree/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b)(2026-07-29) | [`model/token.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/token.go) · [`model/user.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/user.go) · [`model/utils.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/model/utils.go) · [`service/billing_session.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/billing_session.go) · [`service/billing.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/billing.go) · [`service/text_quota.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/text_quota.go) · [`service/token_estimator.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/token_estimator.go) · [`service/usage_helpr.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/service/usage_helpr.go) · [`controller/relay.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/controller/relay.go) · [`common/init.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/common/init.go) |
| songquanpeng/one-api | [`8df4a2670b98266bd287c698243fff327d9748cf`](https://github.com/songquanpeng/one-api/tree/8df4a2670b98266bd287c698243fff327d9748cf)(2025-02-21 —— 该仓最新的一个 commit) | [`relay/controller/helper.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/controller/helper.go) · [`relay/controller/text.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/controller/text.go) · [`model/user.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/user.go) · [`model/token.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/token.go) · [`model/cache.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/model/cache.go) · [`common/redis.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/common/redis.go) · [`relay/adaptor/openai/token.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/adaptor/openai/token.go) · [`relay/adaptor/openai/adaptor.go`](https://github.com/songquanpeng/one-api/blob/8df4a2670b98266bd287c698243fff327d9748cf/relay/adaptor/openai/adaptor.go) |
| maximhq/bifrost | [`39ba57350ce943160feef437eaf5cba52b0aedd5`](https://github.com/maximhq/bifrost/tree/39ba57350ce943160feef437eaf5cba52b0aedd5)(2026-07-29) | [`plugins/governance/store.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/store.go) · [`plugins/governance/tracker.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/tracker.go) · [`plugins/governance/main.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/plugins/governance/main.go) · [`framework/modelcatalog/datasheet/cost.go`](https://github.com/maximhq/bifrost/blob/39ba57350ce943160feef437eaf5cba52b0aedd5/framework/modelcatalog/datasheet/cost.go) |
| Kong/kong | [`391ee48d3a68e8d0bbd0405ec1d02d75f768aa92`](https://github.com/Kong/kong/tree/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92)(2026-07-22;`kong/meta.lua` 报告 3.10.0) | [`kong/llm/plugin/observability.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/observability.lua) · [`shared-filters/serialize-analytics.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/serialize-analytics.lua) · [`shared-filters/normalize-sse-chunk.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-sse-chunk.lua) · [`shared-filters/normalize-request.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-request.lua) · [`shared-filters/normalize-json-response.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/shared-filters/normalize-json-response.lua) · [`kong/llm/drivers/shared.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/drivers/shared.lua) |
| alibaba/higress | [`c8b82797c51a97faca46e2ae12990453f5026802`](https://github.com/alibaba/higress/tree/c8b82797c51a97faca46e2ae12990453f5026802)(2026-07-23) | [`extensions/ai-quota/main.go`](https://github.com/alibaba/higress/blob/c8b82797c51a97faca46e2ae12990453f5026802/plugins/wasm-go/extensions/ai-quota/main.go) · [`extensions/ai-token-ratelimit/main.go`](https://github.com/alibaba/higress/blob/c8b82797c51a97faca46e2ae12990453f5026802/plugins/wasm-go/extensions/ai-token-ratelimit/main.go) |
| higress-group/wasm-go | [`41d65dbb2f9e37e571cb2fdcfec38833b878623b`](https://github.com/higress-group/wasm-go/blob/41d65dbb2f9e37e571cb2fdcfec38833b878623b/pkg/tokenusage/tokenusage.go)(2025-11-03)**以及** [`b573359becf82b5fd79fad6b323313f21917e84a`](https://github.com/higress-group/wasm-go/tree/b573359becf82b5fd79fad6b323313f21917e84a)(2025-08-21) | `pkg/tokenusage/tokenusage.go`。⚠️ **Higress 的 token 计数住在和它插件不同的另一个仓库里,而这两个插件锁的还是它的不同版本**:`ai-token-ratelimit/go.mod` → `41d65db`,`ai-quota/go.mod` → `b573359` |

**厂商规范、SDK 类型与文档:**

| 来源 | 它在这里确立了什么 |
|---|---|
| [openai/openai-openapi @`db14b6e`](https://github.com/openai/openai-openapi/blob/db14b6e1712aaf5265cf5a6871adff7a9c61d31c/openapi.yaml)(2026-07-28) | `ChatCompletionStreamOptions.include_usage` 及其关于中断的免责原文;`CompletionUsage`,含 `prompt_tokens_details.cache_write_tokens` 与那句 `rejected_prediction_tokens`;`ResponseUsage` 的必填字段;§7.1 推导所用的那个 400+100+500=1000 划分的 Organization Usage API 示例 |
| [anthropics/anthropic-sdk-python @`f5c30d0`](https://github.com/anthropics/anthropic-sdk-python/tree/f5c30d0490fb7bcd8e0b65d8d8e63c0e7d1bfe59/src/anthropic/types)(2026-07-28) | `usage.py`(`inference_geo`、`service_tier`、`output_tokens_details`)· `message_delta_usage.py`(只有 `output_tokens` 必填)· `output_tokens_details.py`(`thinking_tokens` 及其两条免责)· `cache_creation.py`(Optional 父级之下必填的 5m/1h int)· `server_tool_usage.py` |
| [Anthropic —— 流式](https://platform.claude.com/docs/en/build-with-claude/streaming) · [prompt 缓存](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)(均检索于 2026-07-29) | 那条累计 usage 的 Warning;§5.1 里 3.99× 背后的基础与网页搜索 SSE 示例;`total_input_tokens` 恒等式与 1.25×/2×/0.1× 倍率;为看不见的 thinking 计费;当前轮 vs 前序轮的价格档;thinking 配置导致的缓存失效 |
| [googleapis/python-genai @`fc282b3`](https://github.com/googleapis/python-genai/blob/fc282b359a7e9e16219587266c94d2bdc506164a/google/genai/types.py)(2026-07-28) · [Gemini generateContent 参考](https://ai.google.dev/api/generate-content) · [Gemini thinking](https://ai.google.dev/gemini-api/docs/thinking)(检索于 2026-07-29) | 四加数的 `total_token_count`;把缓存内容包含在内的 `prompt_token_count`;`tool_use_prompt_token_count`;`traffic_type`;*"response pricing is the sum of output tokens and thinking tokens"*;**以及文档对流式 usage 语义的沉默** |
| [DeepSeek —— KV cache](https://api-docs.deepseek.com/guides/kv_cache) · [token 用量](https://api-docs.deepseek.com/quick_start/token_usage)(检索于 2026-07-29) | `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`,以及任何求和恒等式的缺席 |
| [Portkey —— 创建虚拟 key](https://portkey.ai/docs/api-reference/admin-api/control-plane/virtual-keys/create-virtual-key) · [升级到 Model Catalog](https://portkey.ai/docs/support/upgrade-to-model-catalog) · [虚拟 key](https://portkey.ai/docs/product/ai-gateway/virtual-keys)(检索于 2026-07-29) | 那条 "Deprecated" 原文告示、上游凭据的请求体,以及 Virtual Keys → AI Providers / Model Catalog 的迁移 |
| [Bifrost —— 治理](https://docs.getbifrost.ai/features/governance)(检索于 2026-07-29) | VK 预算与重置周期;*"(VK-level only)"* 的限流;team 或 customer 的互斥挂载;UTC 日历边界重置 |

**GitHub issue 与 PR**(每条均于 2026-07-29 经 `gh api` 抓取,并确认其存在、确认带着所示状态、确认确实说了被引用的内容):

| 条目 | 状态 · 创建时间 | 引用于何处 |
|---|---|---|
| [litellm#34875](https://github.com/BerriAI/litellm/issues/34875) | **开放** · 2026-07-28 | 304,148 条流式记录里 80.7% 成本为 $0 —— 成功回调竞态(§10.1) |
| [litellm#33772](https://github.com/BerriAI/litellm/issues/33772) | **开放** · 2026-07-17 | OpenAI `cache_write_tokens` 被排除在成本计算之外;报告者:消费 *"well below"* 厂商账单(§7.1) |
| [litellm#26807](https://github.com/BerriAI/litellm/issues/26807) | **开放** · 2026-04-29 | 自定义定价路径里缓存 token 按全额输入价——多收 1.67×(§10.2) |
| [litellm#18599](https://github.com/BerriAI/litellm/issues/18599) · [PR #18607](https://github.com/BerriAI/litellm/pull/18607) | 已关闭 · 2026-01-03 · **已合并** 2026-01-03 | 推理被拿来代替总补全定价——少收 7.02%(§10.2) |
| [litellm#30488](https://github.com/BerriAI/litellm/pull/30488) | **已合并** 2026-06-17 | Perplexity 推理重复计费——多收 2.17×;自称是 #18607 的兄弟修复(§10.2) |
| [litellm#28735](https://github.com/BerriAI/litellm/issues/28735) · [#8450](https://github.com/BerriAI/litellm/issues/8450) · [PR #8751](https://github.com/BerriAI/litellm/pull/8751) | **开放** · 以 `not_planned` 关闭 · 以 `merged=false` 关闭 | 合成的 usage chunk 违反 `choices: []` —— 报了两次,修了零次(§5.3) |
| [litellm#22280](https://github.com/BerriAI/litellm/issues/22280) | 以 `not_planned` 关闭 2026-06-15 · 2026-02-27 | 那个强制流式 usage 的请求,因过期被自动关闭(§5.3、§11 第 1 步) |
| [litellm#34850](https://github.com/BerriAI/litellm/pull/34850) · [#27459](https://github.com/BerriAI/litellm/issues/27459) · [#28553](https://github.com/BerriAI/litellm/issues/28553) | 全部**开放** | 缓存 token 上的区域地理溢价(§10.5);Chat→Responses 的 usage 成本被丢掉;Azure Responses 拒绝 `stream_options.include_usage`(§5.1) |
| [litellm#34732](https://github.com/BerriAI/litellm/issues/34732) · [#34733](https://github.com/BerriAI/litellm/issues/34733) · [#33325](https://github.com/BerriAI/litellm/issues/33325) · [#34101](https://github.com/BerriAI/litellm/issues/34101) | 全部**开放** | 预算竞态:session 绕过、窗口重置覆盖、跨副本的 pod 本地消费、project 预算没进预留(§3.1、§9) |
| [litellm#34805](https://github.com/BerriAI/litellm/issues/34805) · [#34820](https://github.com/BerriAI/litellm/issues/34820) | 两者均**开放** | 停机时消费缓冲被丢弃;记录在 DB 写入被 await 之前就被弹出(§8) |
| [new-api#1103](https://github.com/QuantumNous/new-api/issues/1103) | **开放** · 2025-05-25 | Gemini 推理未计费——89.84% 的输出 token(§10.3) |
| [new-api#5003](https://github.com/QuantumNous/new-api/issues/5003) · [#5005](https://github.com/QuantumNous/new-api/issues/5005) | 以 `duplicate` 关闭 · 以 `not_planned` 关闭 · 均为 2026-05-21 | 二次扣减缓存读取导致输入 token 为负(§7.2) |
| [new-api#6353](https://github.com/QuantumNous/new-api/issues/6353) | **开放** · 2026-07-20 | 5m/1h 拆分缺席时 Claude 缓存写入 token 未计费(§7.3) |
| [new-api#2608](https://github.com/QuantumNous/new-api/issues/2608) | **开放** · 2026-01-08 | 整数额度截断与强行进位到 1(§10.4) |
| [new-api#4429](https://github.com/QuantumNous/new-api/issues/4429) · [#6144](https://github.com/QuantumNous/new-api/issues/6144) | 两者均**开放** | 信任旁路下的预扣泄漏(§3.3);按一份损坏的 usage 副本计费(§4) |
| [one-api#412](https://github.com/songquanpeng/one-api/pull/412) · [#925](https://github.com/songquanpeng/one-api/pull/925) | **开放** `merged=false` · 2026-05-25 关闭 `merged=false` | 函数调用逃费,自 2023-08-13 未合并(§10.6);两层预扣的修复在 2.4 年后被关闭(§3.3) |
| [Kong/kong#14816](https://github.com/Kong/kong/issues/14816) | **开放** · 2026-01-15 | `llm_total_tokens_count` 是推导而非存储,丢弃隐藏的推理 token(§6.2) |

**我们的算术**(全部可以按各自旁边印出的数字复算):§5.1 的 3.99× 服务端工具比值;§7.1 的 400+100+500=1000 OpenAI 划分;§7.2 的 −0.008907 对 0.064053 复现;§10.1 的 80.74%;§10.2 的 1.67× 与 7.02%;§10.3 的 10.16% 已计费 / 89.84% 未计费;§4 的 98.7% 命中。写于并核对于 2026-07-29。

**仓内文件:**[README.zh-CN.md](../README.zh-CN.md) 术语表里 *Virtual keys* 与 *Thinking / reasoning tokens* 两行 · [HANDBOOK.md](../HANDBOOK.md) 章节地图 · [BENCHMARKS.zh-CN.md](../BENCHMARKS.zh-CN.md) 第六部分的 token 类型判据 · [data/gateways_eval.json](../data/gateways_eval.json)(`as_of` 2026-07-28,one-api 那条)· [第一章](protocol-translation.zh-CN.md) §2 · [第四章](gateway-anatomy.zh-CN.md) §2.1 的第 2、9、10 环、§3.3、§3.5 与 §4 · [第六章](caching-economics.zh-CN.md) §2.1 与 §3.1。

---

*觉得有用?[⭐ 给榜单点个 Star](https://github.com/cuihuan/awesome-ai-gateway) — 下一个选网关的工程师就是这样找到它的。欢迎经 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充 — 上面每条论断都标了日期,并锚定到一份规范、一个 commit、一条 issue 或一条可重跑的命令,方便你自己复核。如果你敲定了 §12 里那六个开放问题中的任何一个,那正是我们想收的 PR。*
