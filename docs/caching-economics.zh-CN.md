# 缓存经济学——两层缓存、它们到底省了多少,以及怎么证明

**语言：** [English](caching-economics.md) · 简体中文

*最近更新 2026-07-29 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)与[诚实安全记分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · 有三样东西共用「缓存」这个词,而其中只有一样能给你一个错误答案。**厂商 prompt 缓存**在当前所有 Anthropic、OpenAI 与 Gemini 旗舰上,读取价恰好是**基础输入价的 0.1×**——这是 **2026-07-29** 从官方价格表推导出来的,不是从厂商的文案里读来的(Claude Opus 5:读取 $0.50 vs 输入 $5.00)——在 DeepSeek V4-Flash / V4-Pro 上则是 **0.02×** / **0.008333×**。但写入不是免费的,而这正是每一篇「90% 折扣」文章都漏掉的事实:Anthropic 对一次 5 分钟缓存写入按基础输入价的 **1.25×** 计费,1 小时写入按 **2×**,而 **OpenAI 现在在 GPT-5.6 及之后的模型上也按 1.25× 收费**。所以低于 **21.74%** 的命中率(Anthropic 5m / OpenAI 5.6+)或 **52.63%**(Anthropic 1h)时,打开 prompt 缓存反而比不打开*更贵*。在我们实算的那个 50 轮 Claude Opus 5 编码会话里,账单从 **$6.6250 → $2.2400(−66.19%)**——而一个写了缓存却从不命中的网关,会让同一个会话**比完全不启用缓存还贵 18.87%**。**网关响应缓存**是另一种动物、带着另一种风险:Higress 的 `ai-cache` 只以最后一条消息为 key,别的什么都不看——不看模型,也不看租户——而默认 TTL 是 **0,意思是永不过期**(读自 `c8b8279`)。至于 **KV-cache 感知路由**,这第三样被叫做「缓存」的东西,根本不是缓存:它最坏的结果是延迟,永远不会是错误答案。

[第四章](gateway-anatomy.zh-CN.md)确立了缓存*坐在*请求路径的哪个位置,并发现七个网关里有两个的缓存命中会完全逃掉预算强制。本章回答下一个问题:**缓存到底值多少钱,你又怎么证明自己真的拿到了?** 诚实的答案有三部分——一个主导项并不是折扣率的公式,一组决定你到底能不能拿到折扣的厂商规则,以及一类风险落在*正确性*而不是账单上的网关侧缓存。

来源就地说明。厂商定价与行为都引自官方页面并附检索日期;网关行为按锁定 commit 读自源码;算术与推导标明出自我们自己,且可重跑;取自本仓数据文件的数字标为*仓内来源*并附其 `as_of`。凡是无法核实的,都在出现处说明,而不是抹平过去。

---

## 1. 60 秒讲清概念

这个品类里有三种截然不同的机制都戴着「缓存」这个词——标题说*两*层,是因为其中只有两种是你要为之付费、并且可能出错的缓存;第三种只是借了这个词,两样都不是。把它们混为一谈是网关评估里最常见的单一错误,因为它们在唯一要紧的那个维度上不一样——**缓存出错时会发生什么。**

| 层 | 存的是什么 | 归谁所有 | 怎么收费 | 出问题时的最坏情况 |
|---|---|---|---|---|
| **1 · 厂商 prompt 缓存** | 模型服务器对你 prompt 某个逐字节前缀的注意力状态 | 厂商(Anthropic、OpenAI、Google、DeepSeek) | 写入溢价 + 读取折扣,按 token 算 | 你悄无声息地付全价——或者,如果写入要收费而且从不命中,**比全价还贵** |
| **2 · 网关响应缓存** | 一整份此前的响应,以请求的某个函数为 key | 你装的那个网关 | 免费(你完全跳过了那次厂商调用) | **一个自信满满的错误答案,200 OK,没有报错** |
| **3 · KV-cache 感知路由** | *什么都不存。*一份「哪个副本最近见过哪个前缀」的索引 | 你的推理平台(vLLM/EPP) | 免费 | 首 token 时间变慢。响应永远是新生成的 |

README 的 [prompt 缓存章节](../README.zh-CN.md#-缓存过网关钱的问题)负责第 1 层的标题结论与 30 秒测试。本章在这三层上都再往下走一级:决定第 1 层划不划算的那笔算术、决定第 2 层安不安全的 key 内容,以及为什么第 3 层该被放进完全不同的心智格子里。

一个能让人保持诚实的说法:**第 1 层是一项只会让你花钱的计费优化;第 2 层是一个只会让你损失信任的正确性面。** 它们不是替代品,它们的风险也不会互相抵消。

---

## 2. 省钱公式,以及真正主导它的是什么

### 2.1 公式

**我们自己的**,由 §3 里核实过的那些倍率推导而来。令 `p` = 输入单价/token,`q` = 输出单价/token,`C` = 被缓存的前缀 token 数,`U_tot` = 整个会话未缓存的输入 token 数,`O_tot` = 输出 token 数,`N` = 轮数,`w` = 写入倍率,`d` = 读取倍率,`h` = 命中轮次的占比。

定义两个刻画负载形状的项:

- **`f`** = `N·C / (N·C + U_tot)` —— 本来要算作输入的那些 token 里,住在稳定可缓存前缀中的份额。
- **`r`** = `q·O_tot / [p(N·C + U_tot) + q·O_tot]` —— 输出在未缓存账单里的份额。

那么会话的节省率为:

```text
S  =  f · (1 − r) · (A·h − B)          where   A = w − d      B = w − 1
```

只有 `A` 和 `B` 是厂商相关的。其余一切都是*你的*负载。

| 厂商 / 模式 | `w`(写入) | `d`(读取) | `A = w−d` | `B = w−1` | 盈亏平衡 `h = B/A` | `h = 1` 时的上限 |
|---|---|---|---|---|---|---|
| Anthropic,5 分钟 TTL | 1.25× | 0.1× | 1.15 | 0.25 | **21.74%** | 90.00% |
| Anthropic,1 小时 TTL | 2.00× | 0.1× | 1.90 | 1.00 | **52.63%** | 90.00% |
| OpenAI GPT-5.6 及之后 | 1.25× | 0.1× | 1.15 | 0.25 | **21.74%** | 90.00% |
| OpenAI GPT-5.6 之前 | 1.00× | 0.1× | 0.90 | 0 | **0%** | 90.00% |
| Gemini,隐式缓存 | 1.00× | 0.1× | 0.90 | 0 | **0%** | 90.00% |
| DeepSeek V4-Flash | 1.00× | 0.02× | 0.98 | 0 | **0%** | 98.00% |
| DeepSeek V4-Pro | 1.00× | 0.008333× | 0.9917 | 0 | **0%** | 99.17% |

**先读盈亏平衡那一列,再读上限那一列。** 只要 `h < B/A`,`S` 就是负的。在 Anthropic 的 1 小时缓存上,你得有一半以上的时候命中,**才刚够和完全不缓存打平**。Anthropic 自家定价页用散文说的是同一件事,而且与我们的逐轮形式完全吻合:*"caching pays off after just one cache read for the 5-minute duration (1.25x write), or after two cache reads for the 1-hour duration (2x write)"*——我们的盈亏平衡点落在 N = 1.15/0.9 = 1.28 轮(也就是 N=2,一次读取)和 N = 1.90/0.9 = 2.11 轮(也就是 N=3,两次读取)。精确吻合。

### 2.2 实算示例——一个 Claude Opus 5 编码 Agent

假设**先摆在前面,而且是我们自己的、不是引来的**:静态前缀 `C` = 20,000 token(system prompt + 工具定义 + `CLAUDE.md`);`N` = 50 轮,全部落在滚动的 5 分钟 TTL 内;每轮新增的未缓存输入 `U` = 3,000 tok(工具结果、文件读取);输出 `O` = 700 tok/轮。价格是 Anthropic 官方的 Opus 5 费率,检索于 2026-07-29:每 MTok **$5.00 输入 / $6.25 5m 写入 / $10.00 1h 写入 / $0.50 读取 / $25.00 输出**。

| 明细 | 不缓存 | 5 分钟缓存 | 1 小时缓存 |
|---|---|---|---|
| 缓存写入 | — | 20,000 tok @ $6.25/MTok = **$0.1250** | 20,000 tok @ $10.00/MTok = **$0.2000** |
| 缓存读取 | — | 49 × 20,000 = 980,000 @ $0.50 = **$0.4900** | 980,000 @ $0.50 = **$0.4900** |
| 未缓存输入 | 50 × 23,000 = 1,150,000 @ $5.00 = **$5.7500** | 150,000 @ $5.00 = **$0.7500** | 150,000 @ $5.00 = **$0.7500** |
| 输出 | 35,000 @ $25.00 = **$0.8750** | **$0.8750** | **$0.8750** |
| **会话合计** | **$6.6250** | **$2.2400** | **$2.3150** |
| **省下** | — | **$4.3850 = 66.19%** | **$4.3100 = 65.06%** |

闭式交叉验算:`f` = 1,000,000/1,150,000 = 0.869565,`r` = 0.8750/6.6250 = 0.132075,`h` = 49/50 = 0.98 → `S` = 0.869565 × 0.867925 × (1.15×0.98 − 0.25) = 0.6619 ✓。这个阶梯就是从公开倍率算出来的普通算术——公式在上面写着,任何一张电子表格都能复现。

### 2.3 谁在主导——`f` 决定奖品多大,`h` 决定你有没有奖品

围绕那个基线做的单变量敏感性分析(**我们自己的**)。基线处的偏导数:`∂S/∂f` = 0.7612、`∂S/∂r` = −0.7626、`∂S/∂h` = 0.8679——单位变化上三者看起来不相上下。**按偏导数排序就是那个错误。** 决定谁主导的,是每个变量在真实负载里实际能走多远:

| 变量 | 现实取值区间 | 该区间上的 `S` | 摆幅 |
|---|---|---|---|
| **`f`** —— 前缀占输入的份额 | 0.50 → 0.95 | 38.06% → 72.31% | **34.3 pp** |
| **`r`** —— 输出占账单的份额 | 0.05 → 0.40 | 72.45% → 45.76% | 26.7 pp |
| **`h`** —— 命中率,*在一个能工作的缓存内部* | 0.80 → 1.00(任何 N ≥ 5 的会话) | 50.57% → 67.92% | 17.4 pp |
| **`h`** —— 命中率,*全区间* | 0.00 → 1.00 | **−18.87%** → 67.92% | **86.8 pp** |

两个结论,而且它们不是同一个结论。**(1) 在一个能工作的缓存内部,`f` 主导**——你的输入里有多少是稳定前缀,大约值会话长度的两倍,而那是一个 prompt 架构决策,不是网关决策。**(2) `h` 是唯一一个会跨过零的变量**——其他每一项都在缩放奖品;`h` 决定奖品的正负号。而 `h` 恰恰是网关坐在其上、并且能悄无声息地毁掉的那个变量(§5.1)。

**`N` 是个障眼法。** 单次写入的形式是 `S = f(1−r)(0.9 − 1.15/N)`,而 `(0.9 − 1.15/N)` 在 N=5 时已经达到其 0.9 上限的 74.4%,N=10 时 87.2%,N=20 时 93.6%,N=50 时 97.4%。过了大约十轮之后,会话长度只值不到 9 pp,而且是你手上最不可操作的旋钮。

**一个示意,明确不是测量。** 本仓引用了 Datadog 的遥测,称*"only 28% of calls show any cached input"*,同时 system prompt 吃掉 69% 的输入 token(仓内来源,[README](../README.zh-CN.md#-评测速递) 引 [Datadog State of AI Engineering](https://www.datadoghq.com/state-of-ai-engineering/),2026-04——那份底层报告**本章未独立复核**)。把 `h = 0.28` 代入基线得到 `S = 5.43%`。这个代入**不是**关于全行业节省率的论断:Datadog 的 28% 是有任何缓存读取的*调用*的占比,不是一个会话内部的按 token 命中率。它严格证明的是这种不对称的形状——从 90% 的标题到 5% 的结果,整个落差全在 `h` 上。

---

## 3. 厂商 prompt 缓存——四家厂商,没有可移植的契约

有六个维度决定你到底能不能拿到折扣——写入价、读取价、最小前缀、TTL、你怎么标记一处缓存,以及 usage 怎么上报——而这四家厂商在**每一个维度上**都不一致。不存在一份可供网关归一化的、可移植的 prompt 缓存契约。下面的一切要么引自、要么推导自官方页面,检索于 **2026-07-29**;那些倍率是*用除法从价格表推导出来的*,不是从营销文案里读出来的,所以你可以自己一行一条地重做一遍(§8)。

### 3.1 写入 vs 读取的定价

| 厂商 | 缓存写入 | 缓存读取 | 存储租金 | 白捡的钱? |
|---|---|---|---|---|
| **Anthropic** | 基础输入价的 **1.25×**(5m TTL)· **2×**(1h TTL) | **0.1×** | 无 | ❌ —— 必须命中 >21.74%(5m)/ >52.63%(1h) |
| **OpenAI GPT-5.6+** | **1.25×** —— *"cache writes cost 1.25× the uncached input token rate"* | **0.1×** | 无 | ❌ —— 必须命中 >21.74% |
| **OpenAI GPT-5.6 之前** | 免费 —— *"no additional fee on models before the GPT-5.6 family"* | **0.1×** | 无 | ✅ |
| **Gemini**(隐式) | 免费 | **0.1×** | 无 | ✅ —— 但**不保证省钱**(§3.4) |
| **Gemini**(显式 `CachedContent`) | 创建时按标准输入价 | **0.1×** | **每 1M tok 每小时 $1.00–$4.50** | ❌ —— 四家里唯一收租金的 |
| **DeepSeek V4-Flash** | 免费 —— *"Storage usage for the cache is free"* | **0.02×**(1/50) | 无 | ✅ |
| **DeepSeek V4-Pro** | 免费 | **0.008333×**(1/120) | 无 | ✅ |

用美元核一遍,好让这里没有任何东西建立在散文之上。Claude Opus 5($5.00 / $6.25 / $10.00 / $0.50):恰好是 1.25、2.00、0.10——而 Fable 5($10/$12.50/$20/$1)与 Haiku 4.5($1/$1.25/$2/$0.10)带着完全一样的比例。OpenAI gpt-5.6-sol($5.00/$6.25/$0.50):1.25 与 0.10,terra 与 luna 上也一样。Gemini:0.15/1.50 = 0.125/1.25 = 0.03/0.30 = 0.01/0.10 = 恰好 0.10。DeepSeek:0.0028/0.14 = 0.0200,0.003625/0.435 = 恰好 1/120。

> ⚠️ **本仓目前有两处写错了,在这里公布出来,让这次修正带上日期。**(a)README 里那条*"75–90% 缓存折扣"*的区间,以今天的情况看两头都是错的:当前每一个旗舰的读取折扣都恰好是 **90%**,而 DeepSeek 是 **98.00%** / **99.17%**。当前这套模型集合里没有任何一个是按 75% 打折的——那是 Gemini 2.0 时代的数字,而 Gemini 2.0 不在本仓的模型集合里。(b)「cache write」这个字符串在本仓里**一处都没有出现过**,而 [data/models.json](../data/models.json)(`as_of` 2026-07-28)带着 `input` / `output` / `cached_input`,却**没有缓存写入字段**——所以成本计算器在结构上就无法建模 1.25×/2× 的溢价、盈亏平衡命中率,或者 §3.5 里的 TTL 交叉点。那个文件里每一个 `cached_input` 值今天都对照官方页面复核过,全部精确;缺的是一个维度,不是一个错误的数字。

### 3.2 最小可缓存前缀——没人公布的那个门槛

低于这些 token 数,**什么都不会被缓存,而且什么都不会告诉你。** 没有报错,没有警告,没有字段。

| 厂商 | 最小可缓存前缀 | 陷阱 |
|---|---|---|
| **Anthropic** | **512**(Opus 5、Fable 5、Mythos 5)· **1,024**(Opus 4.8、Sonnet 5、Sonnet 4.6/4.5、Opus 4.1、Opus 4、Sonnet 4)· **2,048**(Mythos Preview、Opus 4.7、Haiku 3.5)· **4,096**(Opus 4.6、Opus 4.5、**Haiku 4.5**) | **对模型年份或档位都不是单调的。** Opus 4.5/4.6 需要 4,096;*更新的* Opus 4.7 需要 2,048,Opus 4.8 需要 1,024,Opus 5 需要 512。你推不出来。一个 4,096 token 以下的 Haiku 4.5 请求会静默地什么都不缓存 |
| **OpenAI** | **1,024** —— *"Caching is available for prompts containing 1024 tokens or more"* | 那句被广泛引用的 *"cache hits occur in increments of 128 tokens"* 说法**不在当前页面上**(针对字符串 "128" 做了两次定向重新抓取,均无结果)。别再把它当成现行规则复述 |
| **Gemini** | **2,048**(2.5 Flash、2.5 Pro)· **4,096**(3.5 Flash、3.1 Pro Preview) | 3.x 这一代把最小值**翻了一倍**,所以一个在 2.5 Flash 上缓存正常的 prompt,可能在 3.5 Flash 上静默地不再缓存 |
| **Gemini 3.6 Flash** | **Google 未说明** | 它在价格表上有 $0.15/MTok 的缓存读取费率,却**在 Google 那三个缓存页面的最小 token 表里全都缺席**。这一格留空;不要插值 |
| **DeepSeek** | **64** —— *"content less than 64 tokens will not be cached"* | 比其他所有家小 8×–64×。实际上等于没有下限 |

今天本仓里任何地方都不存在最小前缀的数字——在 README、BENCHMARKS 或 `docs/` 里,以缓存为上下文搜索这些数值,零命中。对一个「钱的问题」章节来说,这是页面上最可操作的一处缺失。

### 3.3 什么会打破缓存前缀

Anthropic 把缓存 key 记录为一个**层级式的逐字节前缀**,而其中「层级」这一部分正是咬编码 Agent 的地方。原文:*"Cache prefixes are created in the following order: `tools`, `system`, then `messages`. This order forms a hierarchy where each level builds upon the previous ones."* 以及:*"Changes at each level invalidate that level and all subsequent levels."* 匹配是逐字节精确的——*"Cache hits require 100% identical prompt segments, including all text and images up to and including the block marked with cache control."*

公开的失效矩阵(✘ = 失效,✓ = 存活):

| 你改了什么 | tools 缓存 | system 缓存 | messages 缓存 |
|---|---|---|---|
| 工具定义 | ✘ | ✘ | ✘ |
| Web search 开关 | ✓ | ✘ | ✘ |
| Citations 开关 | ✓ | ✘ | ✘ |
| Speed 设置 | ✓ | ✘ | ✘ |
| Tool choice | ✓ | ✓ | ✘ |
| 图片 | ✓ | ✓ | ✘ |
| Thinking 参数 | 按模型而定 | 按模型而定 | ✘ |
| Effort 设置 | 按模型而定 | 按模型而定 | ✘ |

**对 Agent 而言的后果就在第一行。** 工具定义坐在层级的*最顶层*,所以在会话中途增加、删除或重排哪怕一个 MCP 工具,都会让它下面的一切失效——包括 system prompt 和完整的对话历史。一个热加载 MCP server 的 Agent,就是一个每当工具列表变形就付一次完整缓存写入的 Agent。另外注意,Bifrost 的语义缓存把工具对象当作一个*无序*集合来做哈希,正是为了防住 *"MCP's randomized map iteration"*(读自 `e6952b6`)——同一个危险,只是高了一层。

OpenAI 的构造更松,但形状相同:*"Requests are routed to a machine based on a hash of the initial prefix of the prompt. The hash typically uses the first 256 tokens, though the exact length varies depending on the model."* 两家厂商给出的结构性建议完全一致——静态内容放前面,可变内容放后面。Gemini 说的也一样:*"Try putting large and common contents at the beginning of your prompt."*

### 3.4 标记、TTL,以及免费续期

| 维度 | Anthropic | OpenAI | Gemini | DeepSeek |
|---|---|---|---|---|
| **你怎么标记它** | 显式。两种模式:**自动**(请求顶层的单个 `cache_control` 字段;随着对话增长,系统会把断点往前推)或**显式断点**(在单个内容块上打 `cache_control`,**每请求 ≤4 个**) | 默认自动,现在带了旋钮:`prompt_cache_key`、`prompt_cache_options.mode` ∈ {`implicit`, `explicit`}、`prompt_cache_options.ttl`。在 GPT-5.6+ 上 *"you must set `prompt_cache_key` to use the more reliable matching"*,并把每个 key 控制在约 15 req/min 以内 | 在 2.5+ 上默认隐式,外加可选的 `CachedContent` 对象。**更新的 Interactions API 不支持显式缓存** | 完全自动,没有旋钮 —— *"enabled by default for all users, allowing them to benefit without needing to modify their code"* |
| **默认 TTL** | **5 分钟** | GPT-5.6+ 上 **≥30 分钟**;在那之前是空闲 5–10 分钟 / 最长 1 小时 | 显式缓存:**1 小时**,可通过 `ttl` 或 `expireTime` 设置 | *"a few hours to a few days"* —— **两个方向都没有契约** |
| **更长的 TTL** | 1 小时,**写入 2×** | `prompt_cache_retention: "24h"`(已废弃的参数),最长 24 小时 | 任意,但你要按小时付租金 | 不适用 |
| **命中时续期** | **免费** —— *"The cache is refreshed for no additional cost each time the cached content is used"* | 前缀保持可用 *"for at least 30 minutes, but OpenAI may retain it longer"* | — | — |
| **保证省钱吗?** | 是 | 是 | **否** —— Google 自家的功能清单写着 *"Implicit caching … no cost saving guarantee"* | 是 |

Anthropic 的**免费续期**是 Agent 经济账里的承重事实:一个各轮之间间隔不到五分钟的会话,整个会话只付**一次**缓存写入,不管它有多长。这就是为什么 §2.2 的实算示例里是一次写入、49 次读取。

Gemini 那一行是表里最尖锐的对比,值得直说:Anthropic 和 OpenAI 的显式模式让你能够*声明*一处缓存。Gemini 的隐式缓存是一项你无法强制的尽力而为优化,**而且 Google 自己在文档里就是这么写的**。(一句被广泛引用的 Google 原话,把折扣定为 *"90% … on Gemini 2.5 or later, 75% on Gemini 2.0"*,我们抓取的任何一手页面上都**无法**确认——三次直接抓取返回的都是导航壳或缺少该句的页面。因此我们改为引用价格表比值,它精确地确立了 90%,而且完全不需要散文。)

### 3.5 TTL 的决策规则

**我们自己的。** 设有 `G` 段超过 5 分钟的空闲间隔,5 分钟缓存要付 `G+1` 次写入,1 小时缓存只付一次:

```text
cost_5m = 1.25(G+1) + 0.1(N−G−1)          cost_1h = 2.00 + 0.1(N−1)
1h wins when  1.15G + 1.15 > 2.00   →   G > 0.7391   →   G ≥ 1
```

按数值算,在 C = 20,000 tok、N = 50、Opus 5 价格下(只算前缀成本):

| >5 分钟的间隔数(`G`) | 5 分钟缓存 | 1 小时缓存 | 赢家 |
|---|---|---|---|
| 0 | **$0.6150** | $0.6900 | 5 分钟 |
| 1 | $0.7300 | **$0.6900** | 1 小时 |
| 2 | $0.8450 | **$0.6900** | 1 小时 |
| 3 | $0.9600 | **$0.6900** | 1 小时 |

**一次真正的停顿就足以把它翻过来。** 因为每一次命中都会免费刷新 TTL,「一段间隔」意味着一次真实的、超过 5 分钟的空闲——一个人在读 diff、一次长测试跑批、一次构建。实操准则:**连续自主循环要 5m;有人参与其中的会话要 1h。** 另外注意,OpenAI GPT-5.6+ 的默认值已经在 5 分钟的价格上给了你 30 分钟的下限——在完全相同的 1.25× 写入倍率下,是 Anthropic 默认 TTL 的 6×。

### 3.6 usage 记账——一个概念,三种不同的包含语义

这就是网关计费出错的地方,因为这四家厂商在「缓存 token 是*算在*还是*不算在*prompt 计数里」这件事上并不一致。

| 厂商 | prompt 计数的语义 | 字段 |
|---|---|---|
| **Anthropic** | **不含** —— *"`input_tokens`: Number of input tokens which were not read from or used to create a cache (that is, tokens after the last cache breakpoint)"* | `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` = 总数。启用 1h 缓存时,`cache_creation` 会拆成 `ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` |
| **OpenAI** | **含** | `prompt_tokens`,其子集是 `prompt_tokens_details.cached_tokens` 以及——新增的—— `prompt_tokens_details.cache_write_tokens`(*"The unadjusted number of prompt tokens written to cache"*) |
| **Gemini** | **含** —— *"When `cachedContent` is set, this is still the total effective prompt size meaning this includes the number of tokens in the cached content"* | `promptTokenCount`、`cachedContentTokenCount`(REST)/ `usage.total_cached_tokens`(SDK) |
| **DeepSeek** | **分区** —— 完全是第三套方案 | `prompt_cache_hit_tokens` + `prompt_cache_miss_tokens` |

包含语义的翻转是 **2 比 1**(OpenAI 与 Gemini 含,Anthropic 不含),而 DeepSeek 自己在另一条轴上。[第一章 §3.3](protocol-translation.zh-CN.md#failure-3) 记录了当翻译器把字段 1:1 映射时,这会付出什么代价。下面的 §5.2 展示了最新的一个实例。

隔离性,值得写一行,因为审计会问:Anthropic 的缓存按组织隔离,而且在 Claude API / AWS 上的 Claude Platform / Microsoft Foundry 上按 workspace 隔离——Bedrock 和 Google Cloud 只到组织级。OpenAI:*"Prompt caches are not shared between organizations."* DeepSeek:*"Each user's cache is isolated and logically invisible to others."*

---

## 4. 网关响应缓存——key 就是产品的全部

第 2 层命中时能省下 100% 的厂商调用,这听起来严格优于第 1 层。并不是,因为一次第 2 层命中会**替换掉模型的答案**。所以一切都压在一个没有任何功能对照表会问的问题上:**缓存 key 里到底装了什么?** 下面除 Kong `ai-semantic-cache` 之外的所有行,都按附录里的锁定 commit 读自源码;Kong 企业版那一行读自它的文档,2026-07-29。

| 网关 | key 里装了什么 | 模型在 key 里吗? | 租户在 key 里吗? | 判定 |
|---|---|---|---|---|
| **Bifrost** `@e6952b6` | UUIDv5(固定 ns,`cache_key` + 请求哈希 + 参数哈希);参数哈希覆盖 temperature、top_p、max_tokens、stop、seed、response_format、reasoning_effort、tool_choice、**完整工具对象**的哈希,以及附件 URL | ✅ 默认 | ✅ —— 除非设置了每请求的 `CacheKey` 或 `DefaultCacheKey`,否则缓存是**关**的 | **失败即关闭(fail-closed)。** 六家里唯一的一个 |
| **LiteLLM** `@c274cf3`(精确匹配) | 对 `ModelParamHelper._get_all_llm_api_params()` 里的每一个 kwarg 做 SHA-256——model、messages、temperature、tools 全在里面 | ✅ 但那是模型***组***,不是 deployment | ❌ 对 redis/local/disk/s3 都不在——租户作用域**只有**语义后端才会被追加 | 参数上安全,**租户上是瞎的**,除非你设了 namespace |
| **Portkey OSS** `@669825c` | `SHA-256(JSON.stringify(transformedRequestBody) + '-' + endpointName)` | ✅(在 body 里面) | ❌ —— `getFromCache` *接受*一个 org/cacheIdentifier 参数然后忽略它;`cacheIdentifier` 在 OSS 树里**任何地方都没被设置过** | 完全没有分区;**厂商不在 key 里** |
| **Kong** `ai-semantic-cache`(企业版) | 默认对最后 **`message_countback = 1`** 条消息做向量 | — | — | 默认值就是经典的多轮误命中(§5.3) |
| **Higress** `ai-cache` `@c8b8279` | **最后一条消息**的文本,通过 `cacheKeyFrom` 默认值 `messages.@reverse.0.content` | ❌ | ❌ | **六家里最薄的 key。** 而且它是*精确*匹配,所以没有任何阈值能保护你 |
| **Kong OSS** `proxy-cache` `@391ee48` | `SHA-256(consumer_id:route_id \| method \| uri \| query \| vary_headers)` —— **请求 body 从不参与哈希** | ❌ | 部分(consumer_id,在未认证的 route 上为 nil) | 分不出两个不同的 prompt。见下 |

**Kong OSS 是最尖锐的一例,值得说精确。** `build_cache_key(consumer_id, route_id, method, uri, params_table, headers_table, conf)` 不接受 body 参数;body 只在未命中*之后*为了记日志才被读取。有两个默认值让这件事在开箱状态下够不着——`request_method` 默认是 `{GET, HEAD}`,所以 LLM 的 POST 会拿到 `X-Cache-Status: Bypass`——但 schema 的 `one_of` 明确允许 POST,`content_type` 的默认值里包含 `application/json`,而 `vary_headers` **没有默认值**,所以连 `Authorization` 都在 key 之外。**在一条 LLM 路由上启用 POST,同一个 consumer 的每一条 prompt 都会碰撞进同一个缓存条目。**

**Higress 是另一个原因上的最尖锐一例:它证明了精确匹配缓存可以比语义缓存更危险。** key 里只有最后一条消息,于是(a)同一条 prompt 发给两个不同的模型,返回的是先落地的那个答案,(b)任何共用这个网关的租户都能读到任何其他租户的答案,(c)用户轮次相同但 system prompt 不同的两段对话会碰撞。这里没有相似度阈值可调,因为根本没有相似度这一步。

### 4.1 决定你风险的那些默认值

| 网关 | 缓存 TTL 默认值 | 相似度阈值默认值 | OSS 里有语义缓存吗? |
|---|---|---|---|
| **Bifrost** | 5 分钟 | **0.8** 余弦(外加对话历史 3 条消息的截断线——更长的历史干脆不缓存) | ✅ |
| **LiteLLM** | `ttl` / `default_in_memory_ttl` / `default_in_redis_ttl`,没有隐式默认值 | **没有——不给显式阈值就拒绝启动** | ✅(redis · valkey · qdrant) |
| **Portkey OSS** | 代码里兜底 24 小时;文档把 `max_age` 定义为**秒**(最小 60,默认 7 天) | 0.95 —— **仅托管版/企业版** | ❌ |
| **Kong** `ai-semantic-cache` | 300 秒 | 运维设定,必填 | ❌ 企业版(`ai_gateway_enterprise`) |
| **Higress** `ai-cache` | **0 = 永不过期** | **1000**,关系为 `lt` | ✅ 但默认静默关闭(§5.4) |
| **Kong OSS** `proxy-cache` | 300 秒 | 不适用(只有精确匹配) | 不适用 |

那张表里有两个默认值是差了一个数量级的离群值。**Higress 的 TTL 为 0,实现上是一次没有过期时间的 Redis `SET`**——读自 `cache/redis.go`:`if rp.config.cacheTTL == 0 { return rp.client.Set(...) } else { return rp.client.SetEx(...) }`,而插件自己的 README 也确认 *"Default is 0 (never expire)"*。再叠加只看最后一条消息的 key,**一个错误答案一旦被缓存,就是永久的,直到有人去刷 Redis。** 而 **Higress 的阈值 1000 配关系 `lt`** 意味着,对一个欧氏距离的存储来说,任何距离小于 1000 的邻居都能通过——也就是说,在基本任意的距离上都接受最近邻。对比 Bifrost 的 0.8 和 Portkey 托管版的 0.95——不过 Bifrost 的 0.8 该得到的是一条告诫而不是一枚金星,因为在现代 embedding 上,*"capital of France"* 和 *"capital of Germany"* 的余弦相似度经常超过 0.8。失败即关闭的作用域,与一个宽松的阈值,是两个互相独立的属性。

**Envoy AI Gateway 完全没有网关响应缓存。** 在 `6722cca` 上做递归目录树列举,匹配 "cache" 的路径恰好只有两条——`examples/cache` 和 `examples/cache/cache_control.md`——而那份文档讲的是把 Anthropic 风格的 `cache_control` 跨 Anthropic / Vertex / Bedrock 转发,也就是第 1 层的透传。没有缓存 filter,没有缓存 CRD,也没有缓存状态 header。

---

## 5. 失败模式,附凭据

### 5.1 `cache_control` 被剥离——受影响 token 上 10×,整个会话约 3×

机制就是[第一章的失败模式 5](protocol-translation.zh-CN.md#failure-5):`cache_control` 只存在于 Anthropic 的 schema 里,所以任何「内部归一化到 OpenAI」的步骤都会把它丢掉,除非有人逐个适配器写了显式的保留代码。什么都不会报错。唯一的症状是 `cache_read_input_tokens: 0` 和一张更大的账单。已核实的凭据:[Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579)(2026-03-25,**开放**——在通往 Vertex AI Anthropic 模型的路上被剥离)与 [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797)(2026-07-27,**开放**——SAP provider 路径上同样的剥离),两者均于 2026-07-29 经 `gh api` 重新核实。

**三个数字,它们回答的是不同的问题——三个都说出来,不然你会被误读。** 按 token 算,本该是缓存读取的输入现在按全价计费:那些 token 上是 **10×**(1.0 ÷ 0.1)。按会话层面算,在 §2.2 那个负载上:$6.6250 ÷ $2.2400 = **2.96×**。而相对于压根没启用过缓存:**−18.87%**,因为一个忠实转发了你那 1.25× 缓存写入、然后又把命中弄坏的网关——通过轮换一个 header、重排工具,或者追加一个 request id——会把你留在 `h = 0`,而 `S(h=0) = −18.87%`。第一章 §3.5 的算术是正确的,但它的标题——*"无声的 10× 账单"*——读起来像是一个账单乘数,而它不是。README 的 30 秒代码片段能正确检测出这种情况;但它周围的文字说你是在*"付全价"*,而事实上你付的比全价还高出约五分之一。

**这一类里一个新的、没有文档的变体。** Anthropic 现在记录了第二种标记模式:*"Automatic caching: Add a single `cache_control` field at the top level of your request."* 本仓编目的每一个剥离 bug 讲的都是**块级**的 `cache_control`。一个只扫描 `system[]` 和 `messages[].content[]` 里的 `cache_control` 并复制它所找到内容的翻译器,会**静默丢掉顶层那种形式**——症状完全相同(`cache_read_input_tokens: 0`,不报错),但成因是新的,而且目前任何地方都没有文档。**我们的结论,来自把厂商文档与已知 bug 形状对照检视;尚未在任何已提交的 issue 里被观察到。**

### 5.2 重复计数陷阱,现在有了 OpenAI 变体

先例已核实且已关闭:LiteLLM 曾经把 Anthropic 的 `cache_creation_input_tokens` *"once as prompt tokens and then again as cache creation tokens"* 收了两遍,报出 **$0.091311**,而 Anthropic 控制台核实的是 **$0.05439**——约 1.7×([BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812),2025-04-08,已关闭)。

同样的形状现在在 OpenAI 上也够得着了。`prompt_tokens` **包含**缓存 token;`cache_write_tokens` 被描述为 *"the unadjusted number of prompt tokens written to cache"*——也就是一个**子集**;而 GPT-5.6+ 的写入按 1.25× 计费。因此一个计算 `prompt_tokens × input_rate + cache_write_tokens × write_rate` 的网关,会把写入的那些 token 收两遍钱。

> **⚠️ 已降级——假设,不是发现。** 我们从一手文档**无法**核实的是:OpenAI 对写入 token 是按 1.25× 收费(替换掉那 1.0× 的输入费),还是在其之上*再加 0.25×*。指南只说了 *"cache writes cost 1.25× the uncached input token rate"*;而定价表里那一列单独的 $6.25 暗示的是替换。**请把「替换」当作工作假设。** 这需要一次对着 OpenAI 发票的实时对账——步骤见 §8 的第 10 条。在有人跑过之前,本仓不该为它公布一个数字。

相关且已核实:[BerriAI/litellm#34801](https://github.com/BerriAI/litellm/issues/34801)(2026-07-27,**开放**)是一次干净的 40 请求对账,除缓存读取外每个字段都对上了——少算 24%,成本高估 8.5%。

### 5.3 语义缓存误命中——机制是厂商自己写在文档里的

这个品类里最强的一手证据,是某家厂商自己合并的一个 PR。[BerriAI/litellm#26990](https://github.com/BerriAI/litellm/pull/26990)(*"chore(caching): isolate semantic cache entries"*)——**2026-05-04 合入** `litellm_internal_staging`——原文就是这么写的(它针对 `main` 的姊妹 PR [#26992](https://github.com/BerriAI/litellm/pull/26992) 被关闭且**未合并**,所以引用的应该是 staging 那个 PR,不是那一个):

> *"The semantic caches retrieve based on prompt embedding similarity, so two callers from different teams could retrieve each other's cached LLM responses by sending semantically similar prompts."*

然后这个修复又造出了镜像失败。[BerriAI/litellm#29086](https://github.com/BerriAI/litellm/issues/29086)(2026-05-27,已关闭):*"`redis-semantic` cache never produces semantic hits"*——作用域 key 里仍然对 prompt 做了哈希,并被当作 RediSearch 的前置过滤器,使 KNN 无从触达。[PR #30339](https://github.com/BerriAI/litellm/issues/30339)(2026-06-13 合并)把两半都说清楚了:*"Identical requests still hit … fuzzy requests always returned 0.0"*,而修复的做法是把 prompt 内容排除出作用域 key,**同时**追加租户身份 *"so dropping prompt content cannot let one virtual key read another tenant's cached response."* [#31610](https://github.com/BerriAI/litellm/issues/31610)(2026-06-29,**开放**)报告它大体上仍然不命中,并重新打开了 2024-11-28 的 [#6954](https://github.com/BerriAI/litellm/issues/6954)。这就是同一个仓库里、有据可查的那架正确性/命中率跷跷板。

三个让这一类问题变得很可能发生的出厂默认值,均于今日读取:

- **Kong `ai-semantic-cache`**:`message_countback = 1`——只有最后一条消息被向量化。Portkey 自家博客用的正是这个形状当作警示例子:先问 *"What is the largest lake in North America?"*,过一会儿在一段无关的对话里再问 *"What is the second largest?"*——一次尾句匹配返回了 "Lake Huron"。
- **Portkey 托管语义缓存**:要求 model、temperature 和 max_tokens 精确匹配,但按 Portkey 的缓存文档,*"The system prompt is ignored — changing it does not affect cache hits"*——两个 system 指令不同、但用户文本相似的调用方,可能共享同一个答案。
- **Higress**:阈值 1000 / `lt`,也就是说一旦语义路径被打开,就没有有效阈值(§4.1)。

有一个用户报告的症状,**标注为未确认**:[BerriAI/litellm#28778](https://github.com/BerriAI/litellm/issues/28778)(2026-05-25,**开放**)报告在打开 `redis-semantic` 或 `qdrant-semantic` 时,Agent 的工具返回内容会丢失,导致 Agent 重新发起工具调用。报告者给出的根因是一个假设,没有维护者确认过,我们也没有复现。这里作为症状引用,不作为已证实的误命中。

### 5.4 安静的失败:缓存关着,却不吭声

比误命中更糟,因为你会一直付钱却永远学不到:

- **Higress `ai-cache` 的语义路径因为一个 nil 检查的顺序 bug 而默认关闭。** `config.go` 的 `FromJson` 只在 `GetVectorProvider() != nil` 时才把 `EnableSemanticCache = true`,但 provider *实例*是稍后在 `Complete()` 里构造的;`parseConfig` 的执行顺序是 `FromJson → Validate → Complete`,所以在 `FromJson` 期间那个 getter 永远是 nil,于是「默认 true」那条分支永远到不了。除非你显式设置 `enableSemanticCache`,这个插件就只有精确匹配。[higress-group/higress#4165](https://github.com/higress-group/higress/pull/4165)(2026-07-17,截至 2026-07-29 仍**开放**)做出了完全相同的诊断。另外,`Validate()` 里那句「语义缓存需要一个 embedding provider」的检查是**被注释掉的**。
- **Bifrost 的语义匹配对 Ollama/vLLM 的模型名会静默地永不触发。** [maximhq/bifrost#5333](https://github.com/maximhq/bifrost/issues/5333)(2026-07-17,**开放**):对包含 `:` 的 TAG 值,RediSearch 向量搜索会以 *"Syntax error"* 失败。因为 `CacheByModel` 默认为 true,任何带冒号的 model id(`gemma31b-q6:latest`)都会让 `FT.SEARCH` 非法;插件记录一条 *"semantic search skipped"*,而直接哈希缓存照常工作。失败方向是安全的——是未命中,不是误命中——但它是静默的。报告者的原话:*"so it's easy to miss."*
- **Higress 把一次命中报成一个合成响应,它的 `model` 字段是字面字符串 `from-cache`**,而 `usage` 全是零(读自 `c8b8279` 的 `config/config.go`)。任何以 `response.model` 为键的下游计量看到的都是 `from-cache`;一次命中对 `ai-statistics` 毫无贡献——这是机制层面的原因,叠在[第四章 §3.1](gateway-anatomy.zh-CN.md#31-缓存坐在哪儿五种排法其中两种让命中逃掉预算强制) 已经记录过的阶段顺序原因之上。
- **Portkey OSS 从不缓存一个显式发送了 `stream: false` 的请求。** 那个写入守卫读的是 `requestParams.stream === (false || undefined)`,而在 JavaScript 里 `(false || undefined)` 就是 `undefined`——所以这个判断实际是 `stream === undefined`。省略该字段的客户端会被缓存;发送 `false` 的客户端(LangChain 和很多裸 HTTP 客户端都会发)永远不会。另外,`max_age` 的文档单位是**秒**,却被以**毫秒**加到 `Date.now()` 上,所以一个文档里写的 `max_age: 3600` 变成了 3.6 秒的 TTL。代码读自 `669825c`;运行时后果是**我们的算术,不是一次执行过的测试**。

### 5.5 诚实的反面证据——你以为会有的现场证据并不存在

**这份榜单上的任何网关,都没有一份经核实的、关于语义缓存误命中的公开生产事故报告。** 我们在 LiteLLM、Kong、Higress、Bifrost 和 Portkey 的 GitHub issue 里搜过,也做了通用网络搜索。存在的是:(a)某家厂商在自己合并的 PR 里承认这类 bug 曾在其产品里活着(§5.3);(b)厂商自己记录的、让误命中变得很可能的默认值;(c)一个开放的、未确认的用户报告症状;以及(d)大量厂商博客内容在断言误报率,却**没有公布方法论**,我们刻意不把它们当作测量来引用。站得住的表述是:**机制是厂商自己写在文档里的,而且有一家厂商出货过又修掉过它;用户可见的现场证据缺席,而这种缺席恰恰是你应该预期到的**——一次误命中返回的是 200 OK 加一个自信满满的错误答案,而 §4 里那六个实现中,只有 Bifrost 和 LiteLLM 会发出你检测它所需要的相似度分数。

---

## 6. KV-cache 感知路由不是缓存

第三层共用了这个词,却不共用任何风险,而这对任何评估 Kubernetes 原生推理的人来说,是本章最有用的一条界定。Gateway API Inference Extension 的提案 0602(状态:**Implemented**,读自 `415f528`)自己就划了这条线:*"we use the term 'request scheduling' to mean the process of estimating the cost of a request and placing it to the best backend server. This is different from 'model routing'."* 它明确列出的非目标包括 *"Change how model server manages prefix caches, or add any prefix cache APIs."*

这个设计是一个**跑在 EPP 上的近似前缀缓存**:把请求切成固定大小的块,每块按 `hash(chunk_i content + hash(chunk_i−1))` 做哈希——*"we don't necessarily need to tokenize"*——所以某个块哈希匹配就蕴含着它之前所有块都匹配。EPP 记录哪个副本服务过哪些块哈希,并把新请求路由到匹配前缀最长的那个副本,目的是最大化**模型服务器自身的**前缀缓存命中(vLLM 的自动前缀缓存)。

**响应永远是新生成的。** 一条陈旧或错误的索引条目损失的是首 token 时间,永远不是正确性。这就是它与第 2 层的全部差别,而这应该改变你对它施加的审视力度。买方仍然该问的两个约束,提案里都写了:匹配必须按模型/adapter 分开,因为 *"different adapters don't share the same kv cache"*;而内存中的索引意味着 *"cache hit performance decreases with multiple active EPP replicas."*

它到底住在哪,因为营销把这一点搅浑了:

| 项目 | 它出货了什么 | 值得注意的默认值(按锁定 commit 读取) |
|---|---|---|
| **llm-d-router** `@c611977` | 两个 scorer:`prefix-cache-scorer`(近似)与 `preciseprefixcache`,作为框架 Scorer 产出一个 0..1 的分数,再与负载/延迟 scorer 混合 | `blockSizeTokens` 默认 16,但 *"values below the minimum of 64 are clamped up at request time"*;`maxPrefixTokensToMatch` 131072;`lruCapacityPerServer` 31250;`matchLengthWeight` **0.0**——默认只有匹配*比例*算数 |
| **AIBrix** `@a1626c8` | `pkg/plugins/gateway/algorithms/prefix_cache.go`,按模型分区的索引(`modelToPods`) | tokenizer 为 `character`(默认)或 `tiktoken`;块大小 128;块数量 200000;有文档记录的兜底:当 `max_running − min_running` 超过不均衡阈值时退回最小负载路由 |
| **kgateway** `@e448e21` | **什么都没有。** 只包含 Inference Extension 支持的设计文档,没有任何前缀打分代码 | 应该这样表述:*"kgateway 支持 Inference Extension;打分住在 EPP 里"*——它是消费方,不是实现方 |

有一处 AIBrix 的细节值得写一行,因为它是 GIE 那条多副本警告的具体形态:`prefixCacheHashSeed()` 在设置了 `AIBRIX_PREFIX_CACHE_HASH_SEED` 时用它,启用状态同步时用一个固定种子,否则用一个**来自 `time.Now().UnixNano()` 的随机种子**。于是两个网关副本对同一条 prompt 会算出不同的块哈希,无法汇集彼此的路由知识。

---

## 7. 30 秒自测

README 拥有这个测试的权威版本;这里给的是把四家厂商的字段名并排放好、并且——这是新增的部分——**告诉你那个答案要花你多少钱**的版本。

把同一个长前缀请求背靠背发两次,然后 diff 一个字段:

| 厂商 | **第二次**调用要读的字段 |
|---|---|
| Anthropic | `usage.cache_read_input_tokens` |
| OpenAI | `usage.prompt_tokens_details.cached_tokens` |
| Gemini | `usageMetadata.cachedContentTokenCount`(REST)/ `usage.total_cached_tokens`(SDK) |
| DeepSeek | `usage.prompt_cache_hit_tokens` |

**第二次调用是零,就意味着 `h = 0`。** 在 Anthropic 5m 或 OpenAI GPT-5.6+ 上,这不是「你在付全价」——在 §2.2 的负载上,这是 **−18.87%,也就是说你付的比关掉缓存还多约五分之一**,因为你买了那 1.25× 的写入,却从来没去收那 0.1× 的读取。在 OpenAI ≤5.5、Gemini 或 DeepSeek 上,`h = 0` 只是错失了一次机会:那里写入是免费的,所以下限是零,不是负数。

在你断定是网关的错之前,先排除两个厂商侧的合法零值原因:你的前缀可能**低于该模型的最小值**(§3.2——Haiku 4.5 和 Gemini 3.5 Flash 上是 4,096 token),或者一次**工具定义变更**让整个层级失效了(§3.3)。从外面看,这两者与被剥离的断点长得一模一样。

---

## 8. 自己动手验证

上面没有一条需要你信我们的话。按见效快慢排序:

1. **用除法把每一个倍率重新推一遍——不需要 key,两分钟。** Anthropic [定价](https://platform.claude.com/docs/en/about-claude/pricing):6.25/5 = 1.25,10/5 = 2.0,0.50/5 = 0.10。OpenAI [定价](https://developers.openai.com/api/docs/pricing):6.25/5.00 = 1.25,0.50/5.00 = 0.10。Gemini [定价](https://ai.google.dev/gemini-api/docs/pricing):0.15/1.50 = 0.10。DeepSeek [定价](https://api-docs.deepseek.com/quick_start/pricing):0.0028/0.14 = 0.02,0.003625/0.435 = 1/120。
2. **重跑我们的算术。** 下面每一个数字都是从公开倍率闭式算出来的——$6.6250 → $2.2400 的阶梯、交叉验算、每一个盈亏平衡点、敏感性表、N 的饱和曲线,以及 5m 对 1h 的交叉点。
3. **测你自己的 `h`**——那个决定正负号的变量。§7,一个字段,两个请求。
4. **证明 Kong OSS 对 body 是瞎的,不需要 key。**
   ```bash
   grep -n "build_cache_key" kong/plugins/proxy-cache/cache_key.lua kong/plugins/proxy-cache/handler.lua
   # confirm the arg list has no body; then enable proxy-cache with request_method
   # including POST on an LLM route, send two DIFFERENT prompts, diff the responses
   ```
5. **用明文读一个 Higress 的缓存 key。**
   ```bash
   redis-cli --scan --pattern "higress-ai-cache:*"   # these are your users' last messages
   redis-cli TTL <key>                               # -1 = never expires, the default
   ```
6. **确认 Kong 和 Envoy 到底出货了什么**——第一条只会返回 `proxy-cache`(OSS 里没有 `ai-semantic-cache`),第二条只会返回两条示例路径,别的什么都没有。
   ```bash
   gh api "repos/Kong/kong/contents/kong/plugins?ref=391ee48" --jq '.[].name' | grep -i cache
   gh api "repos/envoyproxy/ai-gateway/git/trees/6722cca?recursive=1" --jq '.tree[].path' | grep -i cache
   ```
7. **测试 LiteLLM 在精确缓存上的租户泄漏。** 在 `cache: redis` 且没有 namespace 的情况下,用两个不同的虚拟 key 发一个逐字节相同的请求,然后比较 `x-litellm-cache-key`。哈希相同就意味着条目是共享的。
8. **在有信号的地方审计语义误命中。** LiteLLM 在**命中和未命中**时都会设置 `x-litellm-semantic-similarity`(未命中写 0.0)——把它记下来并画出分布;凡是刚好聚在你阈值上方的,就是你的误命中群体。Bifrost 的 `BifrostCacheDebug` 会为每次命中带上 `HitType`(`direct`/`semantic`)、`Similarity` 和 `Threshold`。另外四个网关不发出任何你能拿来审计的东西。
9. **证明 KV-cache 感知路由不是缓存。** 把同一条 prompt 向一个 AIBrix 或 llm-d 池发两次,然后读 usage:`prompt_tokens` 两次都被收费。改善的只有 TTFT。
10. **把我们唯一没能敲定的那件事敲定。** 用 `prompt_cache_options.mode: "explicit"` 跑一个写入密集的请求,记录 `prompt_tokens`、`cached_tokens` 和 `cache_write_tokens`,再对着发票行对账,判定 OpenAI 对写入是按 1.25× 还是按 1.0× + 0.25× 计费(§5.2)。如果你跑了,请[开一个 issue](https://github.com/cuihuan/awesome-ai-gateway/issues)——这是本章缺失的那个事实。

---

## 9. 接下来去哪

如果你正在选网关,从[诉求速查表](../README.zh-CN.md#诉求速查表)和[快速对比](../README.zh-CN.md#快速对比)里的缓存那一列开始——然后把那一列里的每一个 ✅ 都当成一个关于 §4 那张 key 表的问题,而不是一个答案。如果你已经在跑一个了,§7 花你三十秒,§8 的第 4 步花你十五分钟。在本手册里(地图在 [HANDBOOK.md](../HANDBOOK.md)):[第一章——兼容面](protocol-translation.zh-CN.md)是 `cache_control` 被毁掉的地方,在翻译阶段,还有另外四种无声失败模式作陪。[第四章——AI 网关解剖](gateway-anatomy.zh-CN.md)是缓存*坐在*哪儿的地方——那里的 §3.1 展示了两个让命中完全逃掉预算强制的网关,而那正是本章的严格互补面:第四章问一次命中有没有被治理,本章问它对不对、以及它到底省没省下什么。

本章刻意留作开放的三件事,免得有人拿本章去引用它们:OpenAI 的缓存写入到底是按 1.25× 替换计费还是在其上 +0.25×(§5.2);一次 Bifrost 语义缓存命中会不会被计费两次(从插件顺序看机制上说得通,但它需要一次黑盒的消费差值测量,见[第四章的附录](gateway-anatomy.zh-CN.md#附录本章依赖的全部来源));以及 Gemini 3.6 Flash 的最小可缓存前缀,Google 没有公布过。

---

## 附录——本章依赖的全部来源

**厂商文档**(均检索于 2026-07-29):

| 来源 | 它在这里确立了什么 |
|---|---|
| [Anthropic —— prompt 缓存](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | 1.25×/2× 写入、0.1× 读取、按模型 512–4,096 的最小值、≤4 个断点 + 新的顶层自动模式、tools→system→messages 层级与失效矩阵、免费 TTL 续期、usage 字段、组织/workspace 隔离 |
| [Anthropic —— 定价](https://platform.claude.com/docs/en/about-claude/pricing) | 按模型的 Base Input / 5m Write / 1h Write / Cache Hit / Output 各列;那张倍率表;§2.1 里引用的盈亏平衡散文 |
| [OpenAI —— prompt 缓存指南](https://developers.openai.com/api/docs/guides/prompt-caching) | 1,024 token 最小值、256 token 路由哈希、GPT-5.6+ 上 1.25× 写入(此前免费)、`prompt_cache_key`、`prompt_cache_options.mode`/`ttl`、`prompt_cache_retention`、30m/1h/24h 保留期、不跨组织共享 |
| [OpenAI —— 定价](https://developers.openai.com/api/docs/pricing) | 新增的 **Cache Writes** 列:gpt-5.6-sol $5.00/$0.50/$6.25/$30.00,terra,luna;更老的家族显示 "—" |
| [OpenAI —— Chat 对象参考](https://developers.openai.com/api/docs/api-reference/chat/object) | `prompt_tokens_details.cached_tokens` 与 `.cache_write_tokens` 的定义;各缓存参数的定义 |
| [Gemini —— 定价](https://ai.google.dev/gemini-api/docs/pricing) | 按模型的输入 / 输出 / 缓存读取 / 每小时缓存存储;全系精确的 0.1× 比值 |
| [Gemini —— 上下文缓存](https://ai.google.dev/gemini-api/docs/caching) · [generateContent 缓存](https://ai.google.dev/gemini-api/docs/generate-content/caching) · [Interactions 缓存](https://ai.google.dev/gemini-api/docs/interactions/caching) · [CachedContent](https://ai.google.dev/api/caching) · [generateContent 参考](https://ai.google.dev/api/generate-content) | 2.5+ 默认开启隐式缓存、*"no cost saving guarantee"*、最小 token 表(以及 Gemini 3.6 Flash 在其中的缺席)、显式缓存默认 TTL 1 小时及其 `ttl`/`expireTime` 字段、Interactions API 不支持显式缓存、`promptTokenCount` **包含**缓存内容 |
| [DeepSeek —— 定价](https://api-docs.deepseek.com/quick_start/pricing) · [KV cache 指南](https://api-docs.deepseek.com/guides/kv_cache) · [发布说明](https://api-docs.deepseek.com/news/news0802/) | V4-Flash $0.0028/$0.14,V4-Pro $0.003625/$0.435;64 token 的存储单元;免费存储;「数小时到数天」的过期;按用户隔离;`prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` |
| [Kong —— ai-semantic-cache 参考](https://developer.konghq.com/plugins/ai-semantic-cache/reference/) | tier 为 `ai_gateway_enterprise`;`cache_ttl` 300 秒,`message_countback` 1,`exact_caching` false,`ignore_*_prompts` false |
| [Portkey —— 缓存文档](https://portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic) · [语义阈值博客](https://portkey.ai/blog/semantic-caching-thresholds/) | `max_age` 单位为**秒**(最小 60,默认 7 天);语义缓存仅企业版,0.95,*"system prompt is ignored for matching purposes"*;那个「最大的湖 / 第二大」的误命中例子 |
| [LiteLLM —— proxy 缓存](https://docs.litellm.ai/docs/proxy/caching) | 后端列表、TTL 旋钮、`x-litellm-cache-key`、`x-litellm-semantic-similarity` |

**尝试过但未能确认**(记录下来,免得有人再去引用):Google Cloud 那句 *"90% … on Gemini 2.5 or later; 75% on Gemini 2.0"* 的散文。2026-07-29 做了三次直接抓取——`docs.cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview`、`docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview`、`ai.google.dev/gemini-api/docs/caching.md.txt`——返回的都是导航壳或缺少该句的页面。这里的 90% 改为从价格表确立,精确且独立。

**源码树,按锁定 commit 读取**(每个 SHA 均于 2026-07-29 经 `gh api repos/OWNER/REPO/commits/SHA` 重新确认;committer date 按返回值):

| 项目 | Commit(committer date) | 读了哪些文件 |
|---|---|---|
| Portkey-AI/gateway | `669825cbe89ee51569918b8f78a9db486fd69dd4`(2026-05-25) | `src/middlewares/cache/index.ts` · `src/handlers/services/{cacheService,responseService,requestContext,logsService}.ts` · `src/globals.ts` |
| BerriAI/litellm | `c274cf321c5c35c629220a89bb497d15b56f870f`(2026-07-29) | `litellm/caching/{caching.py,caching_handler.py,redis_semantic_cache.py,s3_cache.py}` · `litellm_core_utils/prompt_templates/common_utils.py` |
| maximhq/bifrost | `e6952b6a7172658b2594208a59e064cd2b60b9cc`(2026-07-28) | `plugins/semanticcache/{main.go,utils.go,search.go}` —— 注意它的默认分支是 `dev`,不是 `main` |
| Kong/kong | `391ee48d3a68e8d0bbd0405ec1d02d75f768aa92`(2026-07-22) | `kong/plugins/proxy-cache/{cache_key.lua,handler.lua,schema.lua}` + 插件目录列表 |
| higress-group/higress | `c8b82797c51a97faca46e2ae12990453f5026802`(2026-07-23) | `plugins/wasm-go/extensions/ai-cache/{main.go,core.go,README_EN.md}` · `config/config.go` · `cache/{provider.go,redis.go}` · `vector/provider.go` |
| envoyproxy/ai-gateway | `6722cca8d33896c4464c12f2de5aaf1238a569b6`(2026-07-23) | 递归目录树列表 + `examples/cache/cache_control.md` |
| kubernetes-sigs/gateway-api-inference-extension | `415f528f866ad5c1663ee7ebb80a0b0271725625`(2026-07-28) | `docs/proposals/0602-prefix-cache-aware-routing-proposal/README.md`(状态:Implemented) |
| llm-d/llm-d-router | `c61197709c3318655ef290dcb8151397dd4fd236`(2026-07-28) | `pkg/epp/framework/plugins/scheduling/scorer/prefix/plugin.go` · `pkg/epp/framework/plugins/requestcontrol/dataproducer/approximateprefix/README.md` |
| vllm-project/aibrix | `a1626c811b3e399c0dd32f3a7aaada4ba747f622`(2026-07-29) | `pkg/plugins/gateway/algorithms/prefix_cache_readme.md` · `pkg/utils/prefixcacheindexer/hash.go` |
| kgateway-dev/kgateway | `e448e21dc0e89243f4d499b6a227828017321e8f`(2026-07-29) | `design/10411-gateway-api-inference-extension-support.md`(目录列表;没有前缀打分代码) |

**GitHub issue 与 PR**(每条均于 2026-07-29 经 `gh api` 抓取,并确认其存在且确实说了被引用的内容):

| 条目 | 状态 · 创建时间 | 引用于何处 |
|---|---|---|
| [litellm#26990](https://github.com/BerriAI/litellm/pull/26990) 于 2026-05-04 合并 · [#26992](https://github.com/BerriAI/litellm/pull/26992) 关闭且未合并 |  | 跨租户的语义缓存误命中,厂商在自己的 PR 正文里承认 |
| [litellm#30339](https://github.com/BerriAI/litellm/issues/30339) | 已关闭 · 2026-06-13 | 那个把 prompt 内容排除出作用域 key *并*重新加回租户身份的修复 |
| [litellm#29086](https://github.com/BerriAI/litellm/issues/29086) · [#31610](https://github.com/BerriAI/litellm/issues/31610) · [#6954](https://github.com/BerriAI/litellm/issues/6954) · [#32324](https://github.com/BerriAI/litellm/issues/32324) | 已关闭 · 开放 · 已关闭 · 开放 | 镜像失败——语义缓存静默地永不命中 |
| [litellm#28778](https://github.com/BerriAI/litellm/issues/28778) | **开放** · 2026-05-25 | 语义缓存下 Agent 工具返回内容丢失——**报告者的诊断,未确认,本章未复现** |
| [litellm#9812](https://github.com/BerriAI/litellm/issues/9812) | 已关闭 · 2025-04-08 | 重复计数的先例:$0.091311 vs 控制台核实的 $0.05439 |
| [litellm#34801](https://github.com/BerriAI/litellm/issues/34801) | **开放** · 2026-07-27 | 一次干净的 40 请求对账里,缓存读取少算 −24%,成本 +8.5% |
| [litellm#34797](https://github.com/BerriAI/litellm/issues/34797) · [Portkey#1579](https://github.com/Portkey-AI/gateway/issues/1579) | **开放** · 2026-07-27 · 2026-03-25 | `cache_control` 被剥离,两个适配器,两个项目 |
| [bifrost#5333](https://github.com/maximhq/bifrost/issues/5333) | **开放** · 2026-07-17 | model id 含 `:` 时语义匹配被静默跳过 |
| [higress#4165](https://github.com/higress-group/higress/pull/4165) | **开放** · 2026-07-17 | 那个让语义缓存默认关闭的 nil 检查顺序 bug |

**我们的算术:**在 §2 里完整写出,任何电子表格都能复现——$6.6250 → $2.2400 的阶梯、闭式交叉验算、所有盈亏平衡命中率、敏感性表、N 的饱和曲线,以及 5m 对 1h 的 TTL 交叉点。写于并跑于 2026-07-29;§2 和 §3.5 里的每一个数字都由它打印出来。

**仓内文件:**[README.zh-CN.md](../README.zh-CN.md) 的*缓存过网关*一节,以及术语表里语义缓存 / prompt 缓存输入 / KV cache / 缓存命中率各行 · [data/models.json](../data/models.json)(`as_of` 2026-07-28——每一个 `cached_input` 值今天都对照官方页面复核过,全部精确)· [第一章](protocol-translation.zh-CN.md) §2 与 §3.5 · [第四章](gateway-anatomy.zh-CN.md) §2.1 与 §3.1。

---

*觉得有用?[⭐ 给榜单点个 Star](https://github.com/cuihuan/awesome-ai-gateway) — 下一个选网关的工程师就是这样找到它的。欢迎经 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充 — 上面每条论断都标了日期,并锚定到一张价格表、一个 commit、一条 issue 或一个可重跑的脚本,方便你自己复核;如果某个锁定的 commit 已经往前走了,或者你敲定了 §5.2 里那个 OpenAI 缓存写入计费问题,那正是我们想收的 PR。*
