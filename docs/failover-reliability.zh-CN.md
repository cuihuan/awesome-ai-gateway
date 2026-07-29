# 故障切换与可靠性——厂商在请求中途挂掉时,真正发生了什么

**语言：** [English](failover-reliability.md) · 简体中文

*最近更新 2026-07-29 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)与[诚实安全记分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · 六个开源网关,在 **2026-07-29** 按锁定 commit 读源码:**六家里恰好只有一家默认会在 LLM 层重发一次失败的 LLM 请求。** Bifrost 出货的是 `DefaultMaxRetries = 0`,Portkey OSS 是 `attempts: retry?.attempts ?? 0`,new-api 是 `RetryTimes = 0`;Envoy AI Gateway 自己不写任何重试*次数或触发条件*(只有 `PerTryIdleTimeout`);Kong OSS 压根没有 AI 级重试。只有 **LiteLLM** 默认非零——`num_retries` 会一路落到 `openai.DEFAULT_MAX_RETRIES` = **2**。**六家里恰好只有一家能在第一个 token 已经上线*之后*做故障切换**——同样是 LiteLLM,默认开启,做法是把已生成的残缺文本当作续写内容,重新 prompt 一个 fallback 模型。至于另外五家里的四家,「上游在流中途死掉时客户端看到了什么?」这个问题的诚实答案是*一条看起来很成功的被截断的流*:Portkey OSS 把错误写进 `console.error` 然后关掉 writer;new-api 的流处理器无条件返回 `usage, nil`。冷却比「熔断器」这个词暗示的更短也更罕见:**六家里只有两家在请求结束后还记得这次失败**,LiteLLM 的默认窗口是 **5 秒**,new-api 的是永久的、但出厂**默认关闭**。而且这一切都不是幂等的:**没有任何一家厂商为推理记录过幂等键**,OpenAI 与 Anthropic 的 Python SDK 也从来没把它真正发上线——所以每一次重试,在每一层,都是一次全新的、要计费的生成。

[第四章](gateway-anatomy.zh-CN.md)画出了整条请求路径,并把第 7 环——调用厂商、重试、故障切换——标记为它只能部分回答的那一环,把「有没有哪个网关会把重试过的请求计费两次?」明确留作开放假设。本章就是第 7 环与第 8 环流式那一半的完整深度:什么触发重试、什么触发故障切换,到底是什么字节被重新发上线,请求结束之后还有什么(如果有的话)记得这次失败,第一个 token 之后上游死掉时客户端看到什么,重试会不会被计费两次,三家厂商的 429 契约到底怎么写的,健康检查为什么在撒谎,以及——放在最后,因为这是厂商跳过不讲的部分——在你每一个请求前面多加一跳的那笔算术账。

来源约定与第一章、第四章相同:读源码的都锚定到 commit 并按文件与行号引用,厂商文档标明归属与日期,GitHub issue 均经 API 核实存在,算术与推断标明出自我们自己,取自本仓数据文件的数字标为*仓内来源*。凡是没有独立确认的论断,都在出现处直接说明。第四章那七个网关这里覆盖了六个——**Higress 这一轮没有读**,所以它在下面每一张表里都是缺席,而不是被猜出来的。

---

## 1. 60 秒讲清概念

有两个词被混用,但它们说的不是一回事:

- **重试(Retry)**——再发一次。同样的意图,可能还是同一个上游。
- **故障切换(Failover)**——发到*别的地方*去。不同的 deployment、不同的厂商,甚至是不同的线协议格式。

在普通 API 网关里,这是两个分开的层。在 LLM 网关里它们塌成了一层,因为你重试的东西并不是一个逐字节相同的上游请求——它是一个客户端请求,在发往任何地方之前都必须被*重新路由并重新翻译*。就这一个实现取舍,决定了跨厂商故障切换是否可能,也正是下面六个网关给出六种不同答案的原因。

四个问题决定了其余一切,而且没有一个会出现在功能对照表里:

1. **什么触发重试,什么触发故障切换?**(§2)
2. **到底是什么被重新发上线——原始的客户端请求,还是那个已经翻译好的上游请求?**(§3)
3. **请求结束之后,还有什么记得这次失败吗?**(§4)
4. **第一个 token 之后会发生什么?**(§5)

第 4 个问题最要紧,也最没人写,因为它的失败模式是唯一一种客户端检测不到的:一条提前停住的流,在线上看起来,跟一条正常结束的流一模一样。

---

## 2. 组内重试 vs 跨组故障切换

### 2.1 六个网关,六种答案——而其中五个开箱即零 LLM 级重试

| 网关 | 什么触发重试 | 什么触发故障切换 | 默认重试次数 | 这两层住在哪 |
|---|---|---|---|---|
| **LiteLLM** `c274cf3` | 408 / 409 / 429 / ≥500(`litellm._should_retry`,`utils.py:6339`)外加连接错误;配置了 `retry_policy` 会设置 `_retry_policy_applies` 并完全跳过触发条件判定 | `num_retries` 耗尽 → 走 `fallbacks` 列表;**或者立刻切换**,当配置了对应的 fallback 列表时,针对 `ContextWindowExceededError` / `ContentPolicyViolationError` | **2**——`num_retries` 一路落到 `openai.DEFAULT_MAX_RETRIES`(`router.py:601-606`);`max_fallbacks` = 5(`ROUTER_MAX_FALLBACKS`) | `async_function_with_fallbacks`(`router.py:6398`)包着 `async_function_with_retries`(`:6493`) |
| **Portkey OSS** `669825c` | 只看 HTTP 状态码:`RETRY_STATUS_CODES = [429, 500, 502, 503, 504]`,或者恰好是运维配的 `retry.onStatusCodes` | `strategy.mode: fallback` 在任何非 ok 状态上推进到下一个 target(设置了 `strategy.onStatusCodes` 时则恰好按它) | **0**——`attempts: retry?.attempts ?? 0`(`requestContext.ts:148`) | **三**层嵌套:`tryTargetsRecursively`(`:476`)→ `tryPost`(`:288`)→ `recursiveAfterRequestHookHandler`(`:1182`)→ `retryRequest` |
| **Bifrost** `e6952b6` | 500/502/503/504 + 网络错误 → 同一份凭据;401/402/403/429 → **轮换凭据** | 重试预算花完 → 遍历配置的 `Fallbacks`;每一跳各自拿到一份完整的重试预算 | **0**——`DefaultMaxRetries = 0`(`core/schemas/provider.go:13`) | `executeRequestWithRetries`(`bifrost.go:5818`)在 `handleRequest`(`:5000`)内部 |
| **new-api** `c27d1ef` | 非常宽:1xx、3xx、401–407、409–499、500–503、505–523、525–599。只有 **504 和 524** 被硬排除(这些区间运维可编辑;400、408 和 2xx 只是落在出厂默认值之外) | 没有单独的故障切换——循环每次尝试都重新选渠道,所以**每一次重试*就是*一次故障切换** | **0**——`RetryTimes = 0`(`common/constants.go:133`);循环边界是 `<=`,所以 N 意味着总共 N+1 次尝试 | 一个循环,`controller/relay.go:194` |
| **Envoy AI Gateway** `6722cca` | 运维的 Envoy Gateway `BackendTrafficPolicy` 怎么写就怎么算 | `backendRefs` 上的 `priority: 0 / priority: 1`,由同一份策略仲裁 | **它自己一个都没有**——控制平面唯一会写的 `RetryPolicy` 字段是 `PerTryIdleTimeout` | 完全委托给 Envoy Gateway |
| **Kong OSS** `391ee48` | OSS 树里不存在 AI 级重试 | 没有——掌管 `config.balancer` / `failover_criteria` / `max_fails` 的 `ai-proxy-advanced` 是 `tier: ai_gateway_enterprise`,不在这棵树里 | 只有传输层:`service.retries` = 5,跑在 nginx 默认的 `proxy_next_upstream error timeout` 之下 | nginx 的 balancer,不是插件 |

**关于 Kong 的一条脚注,好让标题和表格对得上:**Kong OSS *确实*带了一个非零的重试默认值——`services.lua:33-34`,`retries = 5`——但那是传输层的 balancer 重试,不是 LLM 级重试,而 §3 会说明为什么它对一次 chat completion 几乎从不触发。「六家里五家做零 LLM 级重试」这句话是精确的。

### 2.2 逐个网关看嵌套结构

**LiteLLM** —— `c274cf3` 上的这条链是 `function_with_fallbacks`(`router.py:6775`,一个三行的同步壳,套在 `run_async_function` 上)→ `async_function_with_fallbacks`(`:6398`)→ `async_function_with_retries`(`:6493`)→ `make_call`(`:6672`)→ `_acompletion`。决定*要不要*重试的逻辑住在 `should_retry_this_error`(`:6711`),它会在七种不同的条件下**抛异常**——也就是说,挡住重试、把错误交给 fallback 层——其中包括 `_num_healthy_deployments <= 0`、已经没有健康 deployment 时的 `RateLimitError`,以及模型组只有一个 deployment 时的 `AuthenticationError`。这就是「重试」在没人配置的情况下优雅地变成「故障切换」的机制。

> 📌 **关于命名,好让你 grep 的时候对得上。** 重试驱动函数是 `async_function_with_retries`;它没有同步孪生(同步的 `function_with_fallbacks` 包装器倒是存在)。2026-07-29 用两种方式核实过:GitHub 代码搜索 `"def function_with_retries" repo:BerriAI/litellm` 返回 `total_count: 0`,而在 `c274cf3` 的原始文件上跑 `grep -n "def .*function_with_retries" router.py` 恰好返回一行,`6493: async def async_function_with_retries`。[第四章](gateway-anatomy.zh-CN.md)最初印的是同步版的名字,在本章起草期间已于 `515b1b8` 修正。

**Portkey OSS** —— 第四章描述的是两层嵌套。实际上是**三**层。`tryTargetsRecursively`(`handlerUtils.ts:476`)按 `strategy.mode` 在 `{loadbalance, fallback, single, conditional}` 之间分派,而且它是*唯一*能换厂商的一层;它内部的 `tryPost`(`:288`)负责翻译与缓存;再往里 `recursiveAfterRequestHookHandler`(`:1182`)掌管 `retryRequest`。注意 `loadbalance` **不**做什么:它按权重挑一个 target,失败时不会继续遍历。Portkey OSS 里的加权负载均衡不是故障切换。

**Bifrost** —— 两个干净的循环。`executeRequestWithRetries` 跑在一个厂商内部;`handleRequest` 只有在那份预算花完之后才去遍历 `Fallbacks`。有两个行为值得写下来:当错误携带 `AllowFallbacks: false` 或者是一个 `RequestCancelled` 时,fallback 会被**整个跳过**(`shouldTryFallbacks`,`bifrost.go:4854`);而当所有 fallback 都失败时,调用方拿回的是**主厂商的那个错误**,不是最后那个(`:5133`)。所以想从你收到的错误去调试一条 fallback 链,设计上就会把你带偏。

**new-api** —— 一个循环,没有单独的故障切换层,还有一个重要的例外:如果请求钉死了渠道(context 里的 `specific_channel_id`),`shouldRetry` 返回 false。被钉死的流量完全没有故障切换。

### 2.3 重试层里两个谁的文档都没写的陷阱

**Portkey OSS:一次 guardrail 判定就能烧掉你的上游重试预算。** 在 `recursiveAfterRequestHookHandler`(`handlerUtils.ts:1249-1281`)里,`retryRequest` 返回,`responseHandler` 做反向翻译,`afterRequestHookHandler` 跑**输出 guardrail 并且能改状态**——然后*才*计算 `isRetriableStatusCode`,而且是针对那个过完钩子之后的响应算的。如果命中了、预算还有剩,处理器就会递归进一次新的 `retryRequest`。所以一条拒绝了完全健康的厂商响应的 guardrail,能把网关打回厂商去再生成一份,全价。另外,`Retry-After` 这条路径有全局上限:`MAX_RETRY_LIMIT_MS = 60 * 1000`,每次真等待都会扣减,header 的探测顺序是 `retry-after-ms`、`x-ms-retry-after-ms`、`retry-after`——而如果某个厂商要求的等待时间超过剩余预算,Portkey 会把 `retrySkipped = true` 一设、直接放弃,而不是干等。

**Envoy AI Gateway:没有挂 `BackendTrafficPolicy`,就根本没有故障切换。** AI Gateway 的控制平面从不写 `numRetries`、`retryOn` 或可重试状态码;出货的示例(`examples/provider_fallback/fallback.yaml`)是让*运维*去写 `numAttemptsPerPriority: 1`、`numRetries: 5`、`perRetry.backOff` 100 ms→10 s、`perRetry.timeout 30s`、`retryOn.httpStatusCodes: [500]`、`retryOn.triggers: [connect-failure, retriable-status-codes]`。注意项目自己的注释怎么解释 `numAttemptsPerPriority: 1` 的用途:*"This ensures that only one attempt is made per priority. For example, if the primary backend fails, it will not retry on the same backend."* 这是个好默认值——而它同时也意味着,你拿到的故障切换行为完全是一个网关并不出货的 YAML 文件的属性。

---

## 3. 到底是什么字节被重新发上线

这个问题决定了跨格式故障切换是否可能,而且它把这六家干净利落地分开了。

| 网关 | 第 2 次尝试发的是什么 | 能跨线协议格式故障切换吗? |
|---|---|---|
| **LiteLLM** | **原始客户端请求**,完整重新路由:`make_call` → `_acompletion` → `async_get_available_deployment` 每次尝试都重跑一遍,被冷却的 deployment 由 `_filter_cooldown_deployments` 过滤掉 | ✅ —— 而且注意它的推论:组内的「重试」本身就已经落到了另一个 deployment 上,所以 LiteLLM 在 `fallbacks` 还没被咨询之前就已经实现了跨 deployment 故障切换 |
| **new-api** | **原始客户端 body**,从 `common.GetBodyStorage(c)` 回放,并按新选中渠道的格式重新转换 | ✅ |
| **Envoy AI Gateway** | **原始 body**,每次尝试重新翻译:`forceBodyMutation := u.onRetry() \|\| u.parent.forceBodyMutation`,针对 `originalRequestBodyRaw`;上游认证也一并重跑 | ✅ —— 这正是让它成为原生能力的原因 |
| **Bifrost** | **同一个逻辑请求**,走同一个厂商适配器,遇到按 key 的失败时换一份凭据 | ⚠️ 只在 fallback 层可以(`prepareFallbackRequest` 会克隆到新的 provider/model),重试层永远不行 |
| **Kong OSS** | `MetaPlugin:retry` 在一次 balancer 尝试上重跑 `STAGES.REQ_TRANSFORMATION` | ❌ —— 每个 driver 都是对着一个 DNS 解析出来的 host 调 `kong.service.set_target(host, port)`,所以根本没有第二个厂商可去 |
| **Portkey OSS**(重试层) | **已经翻译好的**、厂商专属的 `fetchOptions`,逐字节回放到同一个 URL —— 那个 body 是在重试处理器跑起来*之前*由 `transformToProviderRequestAndSave` 构造的 | ❌ 在重试层不行。✅ 只有当 `tryTargetsRecursively` 换到另一个 target 时才行,那会重新进入 `tryPost` 并重新翻译 |

有两个推论值得直说。第一,一个重试时回放翻译后字节的网关,不爬到外面那一层就没法把请求切到形状不同的厂商去——这正是 Portkey OSS 的 `retry` 与 `strategy` 两个设置互相不能替代的原因。第二,每次尝试都重新翻译意味着每次尝试都会重跑第一章的[五种翻译失败模式](protocol-translation.zh-CN.md#3-五种失败模式):一个熬过了第 1 次尝试的 `cache_control` 断点,还得再熬过第 2 次尝试,而且可能是在另一个适配器上。

> ⚠️ **一条 Kong 的代码事实,其运行时后果未经确认。** `kong/llm/plugin/base.lua:154-161` 给每个插件初始化了 `balancer_retry_enabled = false`,`:218` 定义了一个方法 `enable_balancer_retry()` 来把它翻过来。但 `MetaPlugin:access`(`:78`)判的是 `if sub_plugin.enable_balancer_retry then` —— 那个**方法**,不是那个标志位。由于 `sub_plugin` 继承了 `__index = _M`、而该方法是一个函数,这个表达式对每一个基于这个基类构建的插件都为真。照字面读,重试回调是被无条件注册的,而 `balancer_retry_enabled` 被写了却从来没被读过。**我们没有在运行时观察到这一点;请把代码形状当作已核实,把影响当作推断。** 这对手上有 Kong 测试环境的人来说,是个五分钟就能复现的好题目。

---

## 4. 冷却与熔断

### 4.1 六家里只有两家在请求结束后还记得这次失败——而其中一家出厂就是关的

| 网关 | 失败会活过这次请求吗? | 触发条件 | 窗口 |
|---|---|---|---|
| **LiteLLM** | ✅ 一份冷却缓存,router 会拿它过滤 deployment | **多** deployment 组里的任何 429;当前这一分钟内 ≥5 个请求且失败率 >50%;≥1000 个请求且失败率 100%;任何被 `_should_retry()` 拒绝的状态码 | **5 秒**——`DEFAULT_COOLDOWN_TIME_SECONDS = 5`,在 `router.py:589` 赋值 |
| **new-api** | ✅ 而且永不过期——把 DB 状态翻成 `ChannelStatusAutoDisabled` | HTTP **401**(`AutomaticDisableStatusCodeRanges = [{401,401}]`)或者对错误 body 做 Aho-Corasick 关键词匹配命中 | **没有 TTL。** 重新启用需要 `AutomaticEnableChannelEnabled` *外加*一次通过的渠道测试——而 `AutomaticDisableChannelEnabled` 默认是 **`false`**,所以开箱状态下这条路永远不会触发 |
| **Bifrost** | ❌ `deadKeyIDs` / `usedKeyIDs` 只活一个请求的生命周期 | 401/402/403 → 死 key(本次请求内不再重试);429 → 已用 key(池子耗尽后重置) | 不适用——真正的熔断器是**企业版**;`e6952b6` 上的 `plugins/` 里没有任何 `circuitbreaker` |
| **Portkey OSS** | ❌ 钩子在,实现不在 | `handleCircuitBreakerResponse` 是通过可选链调用的,而 **OSS 树里没有任何地方给它赋过值**;也没有任何地方设置过 target 过滤器会读的 `target.isOpen` | 不适用 |
| **Kong OSS** | ❌ | `max_fails` / `fail_timeout` 住在 `ai-proxy-advanced`(企业版)。Kong 自家参考文档把默认值记作 `max_fails: 0`——*"The zero value disables the circuit breaker"* | 不适用 |
| **Envoy AI Gateway** | ❌ 它自己一个都没有 | Envoy 的异常点检测,**前提是**运维在 Envoy Gateway 里配了它 | 不适用 |

### 4.2 这张表真正在说的三件事

**(a) 这个品类里的「熔断器」,通常比 Hystrix 意义上的那个弱得多。** 六家里三家什么都不出货。一家出货了一个没有实现的调用点——形状跟第四章记录的 Portkey 预算层那个 `preRequestValidator` 空洞一模一样:**OSS 数据平面有钩子,托管产品才有状态。** 一家出货了一个默认开启的 5 秒窗口。一家出货了一个默认关闭的永久开关。

**(b) LiteLLM 的默认值里有一条刻意的豁免,常常让人意外。** 单 deployment 的模型组被明确排除在 429 规则*和*错误率规则*两者之外*(`is_single_deployment_model_group`)。这个推理是站得住的——把你唯一的 deployment 冷却掉,只会让下一个请求失败得更快——但这条豁免比看上去要窄。`_should_cooldown_deployment` 在 `c274cf3` 上有四条默认路径分支,只有两条带这个守卫(429 规则,第 225 行;>50% 错误率规则,第 233 行)。另外两条在单 deployment 上照样触发:**当前这一分钟内 ≥1,000 个请求且失败率 100%**(第 227 行——那个常量的名字字面上就叫 `SINGLE_DEPLOYMENT_TRAFFIC_FAILURE_THRESHOLD`),以及**任何被 `litellm._should_retry()` 拒绝的状态码**,实践中就是 401 和 404(第 238 行)。所以那两条本来能抓住*正在劣化*的厂商的规则是关的;只剩下认证/未找到类错误,或者一分钟内一千个请求全灭,才还会被记下来。

**(c) 在默认设置下,`allowed_fails` 实际上是死代码。** `should_cooldown_based_on_allowed_fails_policy` 只在设置了 `allowed_fails_policy` 时,或者 `Router.allowed_fails` 与模块默认值 `litellm.allowed_fails = 3` 不同时才会跑。开箱状态下当家的是百分比规则。如果你一直在调 `allowed_fails` 却看不到任何变化,原因就在这。

---

## 5. 流中途——第一个 token 之后客户端看到了什么

### 5.1 六家里一家能在第一个 chunk 之后故障切换;一家只能在第一个 chunk 上重试;四家完全无能为力

| 网关 | 上游在第 N 个 chunk 之后死掉 | 客户端观察到什么 | 重试了还是切换了? |
|---|---|---|---|
| **LiteLLM** | `_handle_stream_fallback_error` 抛出 `MidStreamFallbackError(generated_content=self.response_uptil_now, is_pre_first_chunk=not self.sent_first_chunk)` | 这条流**继续下去**,由另一个模型产出 | ✅ **默认开启**——每个 `CustomStreamWrapper` 都被包在 `_acompletion_streaming_iterator` 里。例外:任何被映射的 4xx(**429 除外**)会重新抛出,而不是走 fallback |
| **Bifrost** | `tryStreamRequest` 一旦把 channel 交出去就是终局 | 被截断 | ⚠️ **只有第一个 chunk**——嵌在第一帧 SSE 里的错误会重试并切换;再往后的都不会 |
| **Portkey OSS** | `catch (error) { console.error('Error during stream processing:', …) } finally { await writer.close() }` | 一条**看起来很成功的被截断的 SSE 流**——没有 error chunk,状态也没变 | ❌ 重试/fallback 机制看不见它:响应对象在 fetch 于 header 处 resolve 时就已经返回了 |
| **new-api** | `StreamScannerHandler` 没有错误返回值;scanner 的失败被记日志然后吞掉;`OaiStreamHandler` 以 `return usage, nil` 结束 | 被截断;这次请求按积累到的那点残缺 usage,走正常的 `PostTextConsumeQuota` 路径结算 | ❌ —— 没有错误可以往上传,重试循环也就永远不会被重新进入 |
| **Kong OSS** | nginx 原话:*"if an error or timeout occurs in the middle of the transferring of a response, fixing this is impossible"* | 被截断 | ❌ 结构上就不可能 |
| **Envoy AI Gateway** | Envoy router 文档原话:*"This timeout only applies before any part of the response is sent to the downstream, which normally happens after the upstream has sent response headers."* | 被截断 | ❌ 结构上就不可能。它唯一的流式控制项 `streamIdleTimeout` → `RetryPolicy.PerTryIdleTimeout` 是给一条空闲的流**设上限**,不是把它接回来 |

LiteLLM 的续写路径值得展开讲,因为这是这个品类里唯一有人真的把问题解决掉、而不是拿文档把它说过去的地方。发生流中途失败时,router 用 `stream_chunk_builder` 重建那份残缺响应,然后——在已经生成过内容的情况下——把 `messages` 改写成原始对话轮次*加上*一条以 `"Your response should be in continuation of this text: "` 结尾的 system 消息、以及一条带 `prefix: True`、装着残缺内容的 assistant 消息,再重新进入 fallback 路径。如果此前什么都还没生成,它就原样回放原始 messages。fallback 的 usage 会被合并进恢复后的流里,并由一个带 `anyio.CancelScope(shield=True)` 的 `finally` 块关掉已死的上游。**这是一次重新 prompt,不是续传**——你要在 fallback 模型上再付一遍输入 token,而那段续写是另一个模型的文本,粘在第一个模型的前缀后面。

### 5.2 为什么别人做不到:协议规定那段残缺内容已经没了

- **SSE 规范直接把它丢掉。** WHATWG HTML 原文:*"Once the end of the file is reached, any pending data must be discarded. (If the file ends in the middle of an event, before the final empty line, the incomplete event is not dispatched.)"*
- **规范自带的续传机制存在,但实践中是死代码。** SSE 定义了 `Last-Event-ID` 以及 `id:` 和 `retry:` 字段。OpenAI 和 Anthropic 的 Python SDK 都会把 `id:` *解析*进 `_last_event_id` 并暴露 `ServerSentEvent.retry`——而两者都从不发出 `Last-Event-ID` 请求头(2026-07-29,在两个仓里对这个字面字符串做代码搜索,命中数均为 0)。这份契约里负责重连的那一半,被解析出来然后扔掉了。
- **一个按状态码驱动的重试层,对 Anthropic 的流中途错误结构上就是瞎的。** Anthropic 错误页原文:*"When receiving a streaming response over server-sent events (SSE), an error can occur after the API returns a 200 response. In that case, error handling doesn't follow these standard mechanisms."* 线上的形状是 `event: error` / `data: {"type":"error","error":{"type":"overloaded_error",…}}`——一个 `overloaded_error`,在流之外它会是 HTTP 529。§2 里所有以 HTTP 状态码为重试触发条件的网关,看到的都会是 200。
- **真正的服务端续传只存在于恰好一家厂商的恰好一个 API 面上。** OpenAI 的 Responses API 后台模式:跟踪 `sequence_number` 游标,再用 `GET /v1/responses/{id}?stream=true&starting_after=42` 续传。OpenAI 自家的 TypeScript 示例里带着一句注释 *"SDK support coming soon"*,而指南里也注明后台响应的首 token 时间更长。
- **Anthropic 记录了一种手工恢复方式——而且在 Claude 4.6 上把它改了。** 对 4.5 及更早的模型,你构造一个续写请求,把残缺内容放进一条 **assistant** 消息;对 4.6 及更新的模型,你要*"add a user message that instructs the model to continue from where it left off"*,因为那些模型拒绝 assistant 预填(`"This model does not support assistant message prefill"`)。工具调用块与扩展思考块*"cannot be partially recovered."* **一个把 4.6 之前那套预填恢复写死的网关,现在在 4.6+ 模型上会产出 400**——而 §5.1 里 LiteLLM 的续写路径恰恰就是 4.6 之前那个形状,`{'role':'assistant', 'content': e.generated_content, 'prefix': True}`。LiteLLM 的适配器会不会针对 4.6+ 的目标把它改写掉,这一轮没有读;如果你要在 4.6 级别的模型上依赖流中途 fallback,先测过再信。

### 5.3 藏在这一切底下的计量空洞

一次流中途失败丢掉的不只是文本——它通常还会把数字一起丢掉,这就是为什么 §6 和本节其实是同一个问题:

- **Anthropic 的流式 usage 是累计的,而且到得很晚。** 文档警告说 *"the token counts shown in the `usage` field of the `message_delta` event are cumulative"*,而 `message_delta` 是四步里的第三步——排在所有 content block 之后。一个在 `content_block_delta`(也就是最长的那一段)期间死掉的客户端(或网关),从来没见过一帧 usage。
- **`message_start` 确实带了一个 usage 对象,但小得可怜。** Anthropic 给出的三个实例里,`"output_tokens"` 分别是 `1`、`2` 和 `3`。第四章 §3.5 引用过 LiteLLM 源码,把这个描述成一个固定占位值 `1`,而一个按真值判断的兜底逻辑随后没能覆盖掉它。Anthropic 自家文档显示这个值是**会变的**——所以一个专门给字面量 `1` 开特例的网关,在两个方向上都很脆。
- **OpenAI 对一个天真的客户端根本不给 usage。** Chat Completions 的流式除非调用方设置了 `stream_options: {"include_usage": true}`,否则一点 usage 都不发——这就是一个代理着未经修改的客户端的网关无东西可计量、只能退回估算器的文档级原因(Kong OSS 的 `chars ÷ 4`、new-api 的字符类权重表——两者都在第四章 §3.5 里编目过)。

把这些和 §6.2 里 Anthropic 的断连计费条款放在一起,形状就非常刺眼了:**流中途中断时,厂商照收你的钱,而网关通常没法告诉你收了多少。**

---

## 6. 重试幂等性与重复计费

### 6.1 协议层根本不提供任何保护

| 层 | 推理请求的幂等性保证 | 证据 |
|---|---|---|
| **OpenAI API** | ❌ 没有 | OpenAI 唯一有文档的 `Idempotency-Key` 在 **Agentic Commerce Protocol**(商户端点,`idempotency_conflict` / HTTP 409)。`/v1/responses` 或 `/v1/chat/completions` 上什么都没有 |
| **Anthropic API** | ❌ 没有 | Messages 不提供任何键;409 `conflict_error` 讲的是资源状态;Batches API 只在**一个 batch 内部**靠 `custom_id` 去重 |
| **Google Gemini** | ❌ 没有 | `google/genai/_api_client.py` @`fc282b3` 里没有任何 `Idempotency-Key` / `idempotency_key` 请求头的管道——这个仓里唯一一处 `idempotency` 命中是一个 usage-header 单测,与请求重放无关 |
| **openai-python / anthropic-sdk-python** | ❌ 生成了,但从不发送 | 每个 `_base_client.py` 都声明了 `_idempotency_header: str \| None`,在 `__init__` 里把它设成 `None`,并为每个非 GET 请求生成 `stainless-python-retry-<uuid4>`。写入被 `if idempotency_header and options.idempotency_key and …` 挡着——而这个条件永远不可能成立,因为那个属性从来没有被重新赋过值。openai-node 和 anthropic-sdk-typescript 里是同一套死代码模式 |

**所以每一次重试——不管是 SDK、网关还是人——都是一次全新的、要计费的生成。** 第四章把「有没有哪个网关会把重试过的请求计费两次」立成了开放假设。现在它有了一半答案:在协议层,重试导致的重复*生成*,今天没有任何人能防住。

### 6.2 关于「为你没收到的活付钱」,厂商是怎么说的

- **Anthropic,而且这是本章最硬的一张凭据**——计费 FAQ 原文:*"In general, failed requests are not charged, and you will only be billed for successful API calls and completed tasks. However you will be charged if your client disconnects or times out in the middle of an API call that was on track to be successful."* 来源层级很重要:这是一篇**支持中心文章**,不是 API 参考文档,后者对此保持沉默。它把第四章 §3.3 只能从网关侧 issue 去论证的流中途中断问题给敲定了:[litellm#14457](https://github.com/BerriAI/litellm/issues/14457)(客户端断开导致 usage 丢失)在吃真金白银的成本,而 [new-api#4463](https://github.com/QuantumNous/new-api/issues/4463) 那个刻意掐掉上游的取舍,是在把真金白银买回来。
- **OpenAI 记录的是可观测性后果,不是计费后果**——`chat.completion.chunk.usage` 的文档字符串警告说 *"If the stream is interrupted or cancelled, you may not receive the final usage chunk"*,而且除非调用方设置了 `stream_options: {"include_usage": true}`,usage 干脆完全不存在。OpenAI 会不会为残缺部分计费,我们能找到的任何地方都是 **NOT DOCUMENTED**。社区里两个方向的说法都请当作民间传闻。
- **Google 只记录了 400/500 的情况**——*"If your request fails with a 400 or 500 error, you won't be charged for the tokens used. However, the request will still count against your quota."* 流中途客户端断开:**NOT DOCUMENTED**。

### 6.3 唯一给出明确立场的网关,原文照录

> ⚠️ **这里修正第四章。** [gateway-anatomy.zh-CN.md](gateway-anatomy.zh-CN.md) §2.1 引用 Bifrost 的 `RequestID`+`AttemptNumber` 去重,作为「按尝试次数重复计费」的修复,读起来像是在保护你不必为重试付钱。`plugins/governance/tracker.go` @`e6952b6` 里那段完整的源码注释说的恰恰相反:*"Billing is deduped on RequestID+AttemptNumber so each token-consuming attempt bills at most once **while distinct attempts each bill**."* Bifrost 是刻意给每一次尝试都计费的。去重防的是**同一次物理厂商调用**被重复计费——这才是正确的设计,因为厂商本来就为每一次尝试收了钱,而这也正是它属于可靠性一章的原因:*你的重试预算是一个消费乘数。*

**仍然是 INCONCLUSIVE,并且明说:** LiteLLM、Kong OSS 或 new-api 会不会为重试中的同一次物理厂商调用向*客户*收两次钱。那需要一次针对故障注入上游的黑盒消费差值测量,而不是读源码。谁都不该拿本章去引用这一条。

---

## 7. 429 的算术——三家厂商,三份互不兼容的契约

限流不是边角料。仓内来源(README,Datadog 覆盖 1,000+ 组织的生产遥测,2026 年 3 月):限流错误占**全部 LLM 错误的约 ⅓——单月接近 840 万次**。*我们欠读者一条可复核性告诫:*那份报告是一个没有版本号、也没有带日期快照的实时营销页面,而且它还带着一个针对 2026 年 2 月的、不同的第二个数字(*"60% of those errors were caused by exceeded rate limits"*)——所以晚一些去核对的读者,可能看到的标题数字和本仓引的这个 3 月数字不一样。

| | **Anthropic** | **OpenAI** | **Google Gemini** |
|---|---|---|---|
| 429 上的 `Retry-After` | ✅ 明确记录在**每一个** 429 上 | ❌ 无文档(限流指南上 0 命中) | ❌ 无文档 |
| 限流 header | `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` + 6 个 `anthropic-priority-*` | 9 个 `x-ratelimit-*` | 无文档 |
| 重置时间的编码 | **RFC 3339 时间戳** | **时长字符串**(`1s`、`6m0s`) | — |
| 输出 token 这个维度 | OTPM,*"evaluated in real time as output tokens are produced"* | 折进单一的 TPM 维度 | **没有**——TPM 只算输入 |
| `max_tokens` 与限额的关系 | *"does not factor into OTPM rate limit calculations, so there is no rate limit downside to setting a higher max_tokens"* | *"calculated as the maximum of `max_tokens` and the estimated number of tokens"*——一次**预留** | 不适用 |
| 缓存读取算进 token 限额吗? | ✗ 多数模型不算——*"only uncached input tokens count toward your ITPM"*(† Haiku 3.5 **确实**会算 `cache_read_input_tokens`) | 无文档 | 无文档 |
| 失败的请求算数吗? | **无文档** | ✅ *"unsuccessful requests contribute to your per-minute limit"* | ✅ 400/500 不计费,但 *"the request will still count against your quota"* |
| 补充方式 | 连续的令牌桶——*"capacity is continuously replenished … rather than being reset at fixed intervals"* | 未说明;那种时长式的重置暗示的是固定窗口(**我们的推断**) | RPM / TPM(输入)/ RPD,外加一个基于**滚动 10 分钟窗口**的消费上限 |

**对网关而言的解读。** 一个要把「限流」在这三家之间归一化的网关,没法透传一套统一的重置语义——它必须在 RFC 3339 ↔ 时长 ↔ 无 之间做转换。对任何做事前准入的人来说更糟:**同一个 `max_tokens: 64000`,对你的 OpenAI TPM 是一次预留,对你的 Anthropic OTPM 是一个 no-op。** 单一的准入公式,在结构上至少对一家厂商是错的。而且「Anthropic 的 429 重试是免费的」属于民间传闻——Anthropic 的限流页面里,`unsuccessful` 和 `failed request` 出现次数都是零。

> ⚠️ **这里修正第四章。** [gateway-anatomy.zh-CN.md](gateway-anatomy.zh-CN.md) §6 无条件地声称 OpenAI 与 Anthropic SDK *"整个默认重试预算约为 1.1–1.5 秒"*。**两个** SDK 里的 `_calculate_retry_timeout()` 都会在指数退避之前短路:`retry_after = self._parse_retry_after_header(...)`,然后 `if retry_after is not None and 0 < retry_after <= 60: return retry_after`。Anthropic 明确记录了它会在每个 429 上发 `retry-after`,而它的错误页说 SDK 会 *"twice by default, honoring the `retry-after` header when present."* **面对 Anthropic 时,最坏情况下的默认 429 预算是 2 × 60 s = 约 120 秒,不是 1.5 秒。** 1.1–1.5 秒那个数字对连接错误、以及对没有 header 的 429 是正确的——也就是说,对 OpenAI 是正确的。既然那个数字是第四章整个「反对上网关的理由」的决策边界,这个限定条件就是承重的。

而且 SDK 的基线本来也不统一。`googleapis/python-genai` @`fc282b3`:`_RETRY_ATTEMPTS = 5`(含首次调用)、`_RETRY_INITIAL_DELAY = 1.0`、`_RETRY_MAX_DELAY = 60.0`、`_RETRY_HTTP_STATUS_CODES = (408, 429, 500, 502, 503, 504)`,用 `tenacity.wait_exponential_jitter` 实现——而这个实现是**不看 header 的**,所以 `Retry-After` 永远不会被遵守。**我们的算术:**约 1+2+4+8 = 15 秒的 sleep 再加上最多 4 秒抖动,大约是无 header 情况下 OpenAI/Anthropic 预算的 **10×**。另外注意 409 会被 OpenAI 和 Anthropic 重试,而 Google **不会**。谁要是拿「SDK 已经替你重试了」当成一条统一基线说给你听,那是差了一个数量级的错,而且错在对容量规划最要命的那个方向上。

---

## 8. 健康检查,以及它们为什么在撒谎

健康检查是用一次合成探针对未来做出的一个断言。有六个具体理由说明这个断言比看上去弱,每一个都扎在上面某处:

1. **一个需要流量才存在的健康信号,在低流量下压根不存在。** LiteLLM 的百分比规则需要当前这一分钟内 ≥5 个请求才能触发。一个跑 3 RPM 的组,按这条规则永远不会不健康,不管它失败得多惨。
2. **单 deployment 的组丢掉了那两条能检测劣化的规则**——§4.2(b) 里的 `is_single_deployment_model_group` 豁免关掉了 429 规则和错误率规则;只剩 401/404,或者 ≥1,000 请求且 100% 失败的那一分钟,还能触发冷却。你最想要健康信号的那个配置,只保留了它最钝的那一条。
3. **最明显的那个「厂商挂了」信号被明确排除在外。** LiteLLM 的 `_is_cooldown_required` 在异常字符串包含 `APIConnectionError` 时返回 `False`,对 429/401/408/404 之外的任何 4xx 也是。连接失败不会让一个 deployment 进入冷却。
4. **六家里有四家的这份状态要么只活一个请求、要么根本不存在**(§4.1)。Bifrost 的死 key 集合在请求结束时被丢弃;Portkey OSS 的 `isOpen` 从来没被设置过;Kong OSS 与 Envoy AI Gateway 在 AI 层面上压根没有上游健康这个概念。
5. **拿另一个 key 做探针,对你的 key 什么都说明不了。** 限流是按组织、按 key 算的,而 429 占生产 LLM 错误的约 ⅓。Anthropic 的 ITPM/OTPM 是连续补充的桶——一个 16 token 的探针成功了,并不能证明一秒钟之后一个 64k token 的请求会被放行。
6. **最可能把你打趴下的那次事故发生在网关内部,而那里没有任何上游健康检查指得到。** OpenRouter 自家 2026 年 2 月的复盘:**2 月 17 日 05:27 UTC 起 38 分钟**(峰值失败率 80–90%)与 **2 月 19 日 07:36 UTC 起 35 分钟**——根因是一个用于 **API key 查询**的第三方缓存层,它在恢复时又把数据库压垮了。用户先收到 500,然后是 401 `"User not found"`。OpenRouter 的原话:*"Returning an authentication error for what was actually an infrastructure problem caused real confusion: some customers spent time debugging their own API key configurations when nothing on their side was wrong."* 他们的整改是加熔断器,外加**把那个响应从 401 改成 503**。全程没有任何上游厂商参与。

实操准则:**把健康状态当作卸载流量的提示,永远别把它当作状态页的证据。** 如果你的看板说某个厂商是健康的,它实际说的是「我们最近一次用我们的探针 key 做的合成探针成功了,而且当前这一分钟内失败的请求少于五个。」

---

## 9. 把网关放进请求路径的诚实可靠性算术

**我们的推演,标准可靠性数学。** 网关是一个串联依赖:`A_total = A_gateway × A_provider`。故障切换只有靠掩盖*厂商*故障才能挣回自己的成本,所以净值是 `gain = P(厂商故障被掩盖) − P(网关自身引发的故障)`。本章逼着这个表达式做三处修正:

**(1) 第一项比事故数量暗示的要小,因为故障切换只在第一个字节之前有效。** §5.1:六家里四家在流中途失败时完全无法动作,一家只能对第一个 chunk 的错误动作,一家做重新 prompt。长的流式响应——agentic 编码轮次、长文生成——同时是最有价值、也最难被保护的请求。任何从事故数量推算出来的「被掩盖的故障」估计,都在默默假设每一次失败都发生在响应体开始之前。

**(2) 只配了一个厂商时,第一项恒等于零,于是整个表达式严格为负。** 与第四章相比没有变化,值得重复一遍,因为在单一厂商前面装网关,是白白加了一跳、一个有状态服务和一条供应链,却在这个维度上什么都没买到。

**(3) 人人都在引用的那些基线率是有日期的,而且日期并不新。** 那条长期引用——仓内来源,README,出自 Chu 等人,ICPE 2025([arXiv 2501.12469](https://arxiv.org/abs/2501.12469))——已按其发表原文核实:MTBF 中位数 **1.99 天**(OpenAI API)与 **2.09 天**(Anthropic API);*"Most failures are resolved between 0.5 and 3 hours, with the median values around 1 hour"*,OpenAI API 1.23 小时 vs Anthropic API 0.77 小时;以及 *"only 6.15% of incident reports disclose a postmortem."* **有两条告诫是本仓目前没有写出来的。** 那些数据集**截止到 2024-08-30**(OpenAI 2021-02-09→2024-08-28,n=365;Anthropic 2023-03-25→2024-08-30,n=141)——也就是说,一份 2021–2024 的基线率,在 2026 年 7 月被用现在时引用着。而且那里的 MTTR 定义是状态页的 **S1→S4**,即厂商自己那份事故报告的时长,不是实测的用户可见不可用时间。

**第二项的标定值,有日期且属一手来源:**§8 里 OpenRouter 那一对事故——**三天内 73 分钟的宕机**,全部由网关自身造成。这是一种没有网关就不可能存在的失败模式,而且它以第 1/2 环的症状(401)表现出来、根因却在第 11 环(控制平面的缓存),一个只测上游故障切换的买家永远抓不到它。

**还有两项谁都不写下来的东西。** *相关性:*多厂商故障切换隐含地假设故障是独立的。厂商故障基本上确实独立;你自己账号上的限流事件是独立的;**而你的网关的一次坏发布,对你配置的每一个厂商都是 100% 相关的。** 增加厂商完全不会降低这一项。*重试成本:*§6.3——因为没有任何一层是幂等的,你的重试预算就是一个消费乘数。Bifrost 的源码说得很直白:不同的尝试各自计费。一次事故期间一个慷慨的 `num_retries` 是一张账单,不只是一点延迟。

**这个决定,用一个问题而不是一条建议来表述:***我能接受的最坏停机时长,是不是短于大约一小时?我的流量里在第一个 token 之前失败的比例,是不是超过一个微不足道的份额?*如果两个都是,那网关的故障切换买到的是真东西。如果你的流量是长流,那就要明白:你买到的是连接阶段的保护,之后基本上什么都没有——除非你用的是 §5.1 里那个唯一会重新 prompt 的实现,而且除非你愿意把输入 token 付两遍、并接受输出里有一道接缝。

### 9.1 该拿去问厂商的八个问题

每一个在上面某处都有正确答案,而且没有一个会出现在功能对照表里。

1. 你们**出货的默认值**——重试次数、退避、冷却——分别是多少?不是最大值,是默认值。(§2.1、§4.1)
2. 一次重试是**重新路由**还是**回放**?第 2 次尝试能落到一个线协议格式不同的厂商上吗?(§3)
3. 一次失败会**活过这次请求**吗?给我看那份状态住在哪、TTL 是多少。(§4.1)
4. 上游在第一个 token **之后**死掉时,客户端看到什么——一个错误帧、一次截断,还是一条被恢复的流?(§5.1)
5. 如果你们在流中途恢复,那是**重连还是重新 prompt**,第二份输入 token 的钱谁出?(§5.1)
6. 跨尝试的**计费幂等键**是什么,一个重试过的请求会产出一行消费还是两行?(§6)
7. 你们遵守谁的 `Retry-After`,又是怎么把**三份互不兼容的限流契约**归一化成一次准入决策的?(§7)
8. 当挂掉的是*你们*、不是厂商时,我拿到什么状态码,我的健康检查又怎么分辨得出差别?(§8)

---

## 10. 自己动手验证

上面没有一条需要你信我们的话。按见效快慢排序:

1. **从源码而不是文档读出重试默认值,读你自己那个版本**——5 分钟,不需要 key。
   ```bash
   # LiteLLM:唯一的非零默认值,以及第四章弄错了的那个函数
   curl -s https://raw.githubusercontent.com/BerriAI/litellm/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router.py \
     | grep -n "def function_with_fallbacks\|def async_function_with_retries\|def function_with_retries"
   # Bifrost / new-api / Portkey:全都是零
   grep -n "DefaultMaxRetries" core/schemas/provider.go        # = 0
   grep -n "var RetryTimes"     common/constants.go            # = 0
   grep -n "attempts: retry"    src/handlers/services/requestContext.ts   # ?? 0
   ```
2. **证明没有任何幂等键离开过你的机器**——30 秒。
   ```bash
   python -c "import openai, anthropic; print(openai.OpenAI(api_key='x')._idempotency_header, anthropic.Anthropic(api_key='x')._idempotency_header)"   # -> None None
   OPENAI_LOG=debug  python your_script.py   # inspect the outgoing headers
   ```
3. **证明在 `retry-after` 之下 SDK 的重试预算不是 1.5 秒**——读你已安装的 `_base_client.py` 里的 `_calculate_retry_timeout`,确认那句 `if retry_after is not None and 0 < retry_after <= 60: return retry_after` 的提前返回坐在指数退避*之上*。然后读你自己的数字:
   ```bash
   python -c "from openai._constants import *; print(DEFAULT_MAX_RETRIES, INITIAL_RETRY_DELAY, MAX_RETRY_DELAY, DEFAULT_TIMEOUT)"
   python -c "from google.genai._api_client import _RETRY_ATTEMPTS,_RETRY_INITIAL_DELAY,_RETRY_MAX_DELAY,_RETRY_HTTP_STATUS_CODES as C; print(_RETRY_ATTEMPTS,_RETRY_INITIAL_DELAY,_RETRY_MAX_DELAY,C)"
   ```
4. **在流飞到一半时把它掐掉,看你的网关怎么反应。** 通过网关起一个长的流式 completion,然后 `iptables -A OUTPUT -d <provider-ip> -j REJECT`(或者在 mock 里把上游杀掉)。§5.1 已经预测了你的答案:续写文本(LiteLLM),或者一次干净的截断、200 且无错误(六家里的四家)。然后检查那段残缺内容有没有对应的消费流水。
5. **查一次重试是被计一次费还是两次。** 把网关指向一个 mock 上游,让它第 1 次尝试返回 503、第 2 次返回 200,并带一个已知的 usage 对象。读消费流水。**这就是能敲定 §6.3 那个 INCONCLUSIVE 的测量,而我们没有跑过它。**
6. **去测你实际的冷却窗口**,别去读它。故意让一个 deployment 失败,然后轮询:LiteLLM 的默认值会在约 5 秒后把它放回轮转。如果你以为是几分钟,那你有一处配置要改。
7. **拿真实 header 核对 429 契约**——各一次调用,需要 key。
   ```bash
   curl -sD - -o /dev/null https://api.anthropic.com/v1/messages \
     -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' -H 'content-type: application/json' \
     -d '{"model":"claude-sonnet-5","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}' \
     | grep -i 'ratelimit\|retry-after'
   curl -s https://developers.openai.com/api/docs/guides/rate-limits.md | grep -n 'unsuccessful\|maximum of `max_tokens`'
   ```
8. **把本章锁定的每一个 commit 重新核实一遍**,一个循环搞定:
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
9. **确认 Kong OSS 真的没出货任何故障切换插件:**
   ```bash
   gh api "repos/Kong/kong/contents/kong/plugins?ref=391ee48d3a68e8d0bbd0405ec1d02d75f768aa92" --jq '.[].name' | grep '^ai-'
   # -> exactly 6 names, none of them ai-proxy-advanced
   ```

---

## 11. 接下来去哪

如果你正在选网关,从[诉求速查表](../README.zh-CN.md#诉求速查表)和[如何安全选型](../README.zh-CN.md#如何安全选型)开始;与可靠性相关的证据住在[快速对比](../README.zh-CN.md#快速对比)和 [BENCHMARKS 第五部分](../BENCHMARKS.zh-CN.md#第五部分--真实评测生产环境里用户怎么说)里。

在本手册里——完整地图在[章节地图](../HANDBOOK.md)。[第一章——兼容面](protocol-translation.zh-CN.md)就是本章 §3 里那个每次尝试都会被重新进入的翻译层;如果你的任何一个故障切换目标说的是另一种线协议格式,请读它。[第四章——AI 网关解剖](gateway-anatomy.zh-CN.md)是整条请求路径,而本章补上了它留下的第 7 环空洞——并在上文就地标出了对第四章的四处修正(`async_function_with_retries`、Portkey 的第三层、Bifrost 计费的完整引文,以及 SDK 预算上 `retry-after` 那个限定条件),这就是「设计上可证伪」在实践中该长的样子。

**本章明确没有确立的结论**,免得有人拿本章去引用它们:LiteLLM、Kong OSS 或 new-api 会不会为重试中的同一次物理厂商调用向客户收两次钱(§6.3,需要一次消费差值测量);Kong 那个 `enable_balancer_retry` 命名错配的运行时后果(§3,代码形状已核实,行为属推断);Higress 的重试、冷却与流中途语义,这一轮没有读;以及任何关于 Kong 企业版或 Bifrost 企业版熔断器的、超出它们自家文档所述范围的说法。

---

## 附录——本章依赖的全部来源

**源码树,按锁定 commit 读取,每一个都在 2026-07-29 经 `gh api repos/<owner>/<repo>/git/commits/<sha>` 重新核实**(下面的日期就是那次调用返回的 committer date):

| 网关 | Commit | 提交于 | 读了哪些文件 |
|---|---|---|---|
| BerriAI/litellm | [`c274cf3`](https://github.com/BerriAI/litellm/commit/c274cf321c5c35c629220a89bb497d15b56f870f) | 2026-07-29 | [`litellm/router.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router.py) · [`router_utils/cooldown_handlers.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/router_utils/cooldown_handlers.py) · [`constants.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/constants.py) · [`utils.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/utils.py) · [`litellm_core_utils/streaming_handler.py`](https://github.com/BerriAI/litellm/blob/c274cf321c5c35c629220a89bb497d15b56f870f/litellm/litellm_core_utils/streaming_handler.py) |
| Portkey-AI/gateway | [`669825c`](https://github.com/Portkey-AI/gateway/commit/669825cbe89ee51569918b8f78a9db486fd69dd4) | 2026-05-25 | [`src/handlers/handlerUtils.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/handlerUtils.ts) · [`retryHandler.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/retryHandler.ts) · [`streamHandler.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/streamHandler.ts) · [`services/requestContext.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/handlers/services/requestContext.ts) · [`src/globals.ts`](https://github.com/Portkey-AI/gateway/blob/669825cbe89ee51569918b8f78a9db486fd69dd4/src/globals.ts) · `src/types/requestBody.ts` |
| maximhq/bifrost | [`e6952b6`](https://github.com/maximhq/bifrost/commit/e6952b6a7172658b2594208a59e064cd2b60b9cc) | 2026-07-28 | [`core/bifrost.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/bifrost.go) · [`core/utils.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/utils.go) · [`core/schemas/provider.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/schemas/provider.go) · [`core/streamfallback_test.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/core/streamfallback_test.go) · [`plugins/governance/tracker.go`](https://github.com/maximhq/bifrost/blob/e6952b6a7172658b2594208a59e064cd2b60b9cc/plugins/governance/tracker.go) · `docs/enterprise/circuit-breaker.mdx` · `plugins/` 目录树列表 |
| Kong/kong | [`391ee48`](https://github.com/Kong/kong/commit/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92) | 2026-07-22 | [`kong/llm/plugin/base.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/plugin/base.lua) · [`kong/db/schema/entities/services.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/db/schema/entities/services.lua) · [`kong/llm/drivers/openai.lua`](https://github.com/Kong/kong/blob/391ee48d3a68e8d0bbd0405ec1d02d75f768aa92/kong/llm/drivers/openai.lua) · `kong/runloop/handler.lua` · `kong/runloop/upstream_retry.lua` · `kong/init.lua` · `kong/templates/nginx_kong.lua` · `kong/plugins/` 目录树列表(6 个 `ai-*` 插件) |
| envoyproxy/ai-gateway | [`6722cca`](https://github.com/envoyproxy/ai-gateway/commit/6722cca8d33896c4464c12f2de5aaf1238a569b6) | 2026-07-23 | [`internal/extensionserver/post_translate_modify.go`](https://github.com/envoyproxy/ai-gateway/blob/6722cca8d33896c4464c12f2de5aaf1238a569b6/internal/extensionserver/post_translate_modify.go) · [`internal/extproc/processor_impl.go`](https://github.com/envoyproxy/ai-gateway/blob/6722cca8d33896c4464c12f2de5aaf1238a569b6/internal/extproc/processor_impl.go) · `examples/provider_fallback/fallback.yaml` · `site/docs/capabilities/traffic/provider-fallback.md` |
| QuantumNous/new-api | [`c27d1ef`](https://github.com/QuantumNous/new-api/commit/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b) | 2026-07-29 | [`controller/relay.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/controller/relay.go) · [`setting/operation_setting/status_code_ranges.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/setting/operation_setting/status_code_ranges.go) · [`common/constants.go`](https://github.com/QuantumNous/new-api/blob/c27d1ef651c608dd8b9e60848a7e0f13a8619d9b/common/constants.go) · `service/channel.go` · `model/option.go` · `relay/compatible_handler.go` · `relay/helper/stream_scanner.go` · `relay/channel/openai/relay-openai.go` |

**SDK 源码,按锁定 commit 读于 2026-07-29:**openai/openai-python [`4f40426`](https://github.com/openai/openai-python/commit/4f404262955cb711c56c07cce52076b6107303e5)(2026-07-28)—— `_constants.py`、`_base_client.py`、`_streaming.py` · anthropics/anthropic-sdk-python [`f5c30d0`](https://github.com/anthropics/anthropic-sdk-python/commit/f5c30d0490fb7bcd8e0b65d8d8e63c0e7d1bfe59)(2026-07-28)—— 同样这三个文件 · googleapis/python-genai [`fc282b3`](https://github.com/googleapis/python-genai/commit/fc282b359a7e9e16219587266c94d2bdc506164a)(2026-07-28)—— `google/genai/_api_client.py` · openai/openai-node `83e6b4a` 与 anthropics/anthropic-sdk-typescript `3b45cd3` —— `src/client.ts`(同一套「声明了却从不赋值」的 `idempotencyHeader` 模式)。

**厂商与标准文档,均检索于 2026-07-29:**[Anthropic 限流](https://platform.claude.com/docs/en/api/rate-limits) · [Anthropic 错误](https://platform.claude.com/docs/en/api/errors) · [Anthropic 流式,含 Error recovery](https://platform.claude.com/docs/en/build-with-claude/streaming) · [Anthropic Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python) · [Anthropic 计费 FAQ](https://support.claude.com/en/articles/8114526-how-will-i-be-billed)(支持中心层级,不是 API 参考)· [OpenAI 限流](https://developers.openai.com/api/docs/guides/rate-limits) · [OpenAI 流式事件参考](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events.md) · [OpenAI 后台模式](https://developers.openai.com/api/docs/guides/background) · [OpenAI Agentic Commerce 生产指南](https://developers.openai.com/commerce/guides/production)(OpenAI 唯一有文档的 `Idempotency-Key`)· [Gemini 限流](https://ai.google.dev/gemini-api/docs/rate-limits) · [Gemini 计费 FAQ](https://ai.google.dev/gemini-api/docs/billing) · [Gemini 排障](https://ai.google.dev/gemini-api/docs/troubleshooting) · [WHATWG SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html) · [nginx `ngx_http_proxy_module`](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) · [Envoy router filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/router_filter) · [Kong `ai-proxy-advanced` 参考](https://developer.konghq.com/plugins/ai-proxy-advanced/reference/)(`tier: ai_gateway_enterprise`;`max_fails: 0` = *"disables the circuit breaker"*)。

**引用的 GitHub issue**(每条均于 2026-07-29 经 `gh api` 核实存在):

| Issue | 状态 | 引用于何处 |
|---|---|---|
| [maximhq/bifrost#4788](https://github.com/maximhq/bifrost/issues/4788) | 已关闭,创建于 2026-06-29 | 那次首 chunk 流式回归,其修复出货了 `core/streamfallback_test.go`(`TestStreamFallbackAfterFirstChunkError`、`TestStreamRetryAfterFirstChunkError`) |
| [litellm#14457](https://github.com/BerriAI/litellm/issues/14457) | 开放 | 客户端在流中途断开导致 usage 丢失——Anthropic 断连计费条款在网关侧的代价 |
| [new-api#4463](https://github.com/QuantumNous/new-api/issues/4463) | 已关闭 | 刻意相反的取舍:客户端断开就掐掉上游 |

**仓内来源数字与前序章节:**[README](../README.zh-CN.md)(Datadog 生产遥测,2026 年 3 月:限流约占 LLM 错误的 ⅓,约 840 万次;Chu 等人 ICPE 2025 的 MTBF/MTTR 基线率——本章补充的数据集窗口告诫见 §9)· [BENCHMARKS 第五部分](../BENCHMARKS.zh-CN.md#第五部分--真实评测生产环境里用户怎么说) 与 [data/gateway_reality.json](../data/gateway_reality.json)——注意这个数据文件目前**没有 `as_of` 键**,与本仓其他经策展的数据集不同,所以它的行无法被消费者标注日期;因此本章里每一个 OpenRouter 数字都直接取自厂商复盘,而不是取自那个文件 · [OpenRouter 2026 年 2 月复盘](https://openrouter.ai/blog/announcements/openrouter-outages-on-february-17-and-19-2026/) · [第一章](protocol-translation.zh-CN.md) · [第四章](gateway-anatomy.zh-CN.md) · [章节地图](../HANDBOOK.md)。

---

*觉得有用?[⭐ 给榜单点个 Star](https://github.com/cuihuan/awesome-ai-gateway) — 下一个选网关的工程师就是这样找到它的。欢迎经 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充 — 上面每条论断都标了日期,并锚定到一个 commit、一条 issue、一份厂商文档或一次测量,方便你自己复核;如果某个锁定的 commit 已经往前走了,那正是我们想收的 PR。*
