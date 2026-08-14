# 编码 Agent 省钱路由器对比(2026):claude-code-router vs OmniRoute vs 9router vs CLIProxyAPI vs sub2api——省多少 vs 封号风险

*更新于 2026-07-27 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)和诚实安全记分卡的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · 省钱的来源不是路由器本身——同一个编码 Agent 会话,换个模型成本就从 **$0.021 到 $1.75**,差 **~83 倍**([实测](../BENCHMARKS.zh-CN.md),单测脚本可复算)。风险的来源也不是路由器的牌子,而是**机制**:自带 API key(BYOK)是官方支持的用法;把自己订阅的 OAuth 路由给第三方工具,**Anthropic 自 2026-02-20 起明确禁止**([政策变更](https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use));而拼车倒卖订阅额度,正是 Anthropic 明说在主动封禁的行为([2026-02-19 澄清](https://piunikaweb.com/2026/02/19/anthropic-claude-max-ban-agent-sdk-clarification/))。

重度 Claude Code / Codex / Cursor 用户迟早会去找路由器——claude-code-router、OmniRoute、9router、CLIProxyAPI、sub2api、opencodex、freellmapi——问的都是同两个问题:到底能省多少?**会不会封我号?** 诚实的答案几乎完全取决于工具用的是三种机制中的哪一种,而不是它有多少 star。下面按每个工具**自己 README 的原文**分类,配上真实的 ToS 条款和有日期的封号报告——不凭感觉。

## 三个机制档位

| 档位 | 机制 | 厂商态度 | 现实中的最坏结果 |
|---|---|---|---|
| **1 · 自带 API key(BYOK)** | 用你自己的按量付费 API key 转发请求 | **官方支持**——API key 就是为程序化访问设计的 | 限流;账单变大 |
| **2 · 自有账号 OAuth 代理** | 在官方客户端之外复用*你自己*的消费级订阅(Claude Pro/Max、ChatGPT Plus、Copilot) | **灰色 → 已被禁止。** Anthropic 2026-02-20 把订阅 OAuth 限定回自家产品;消费级 ToS 规定非 API 的自动化访问需明确许可 | 订阅被掉、背后的账号被封 |
| **3 · 账号池套利** | 把一堆订阅账号拼成池子,把额度分发给*其他用户*,通常收钱 | **违规**——Anthropic 和 OpenAI 的消费级 ToS 都禁止共享凭证与转售访问 | 整池账号被封;买家买到的是无法验证的转售容量 |

## 每个工具在哪一档——依据其自家文档

| 工具 | 档位 | 自家文档原文 |
|---|---|---|
| [Claude Code Router](https://github.com/musistudio/claude-code-router) <!--s:musistudio/claude-code-router-->⭐ 36.6k<!--/s--> | **1 — BYOK** | 快速上手:"Open Providers → Add Provider … **enter the API key**"。一个灰色边缘:功能表里有 "**local login import where supported**"——不用这个导入 CLI 登录的功能,你就干净地待在第 1 档 |
| [freellmapi](https://github.com/tashfeenahmed/freellmapi) <!--s:tashfeenahmed/freellmapi-->⭐ 18.5k<!--/s--> | **1 — BYOK,免费额度叠加** | "add **your provider keys** on the Keys page";自带逐厂商 ToS 审查表(2026-05),经验法则是 "**one account per provider**, **no reselling**, **no sharing your endpoint with other humans**";仓库自我标注 "personal experimentation only" |
| [opencodex](https://github.com/lidge-jun/opencodex) <!--s:lidge-jun/opencodex-->⭐ 9.9k<!--/s--> | **1 或 2 — 看模式** | 第 1 档路径:"Paste your **API key** (or log in via OAuth…)"。第 2 档路径:"It can also manage a **ChatGPT account pool** for Codex auth. Add multiple ChatGPT / Codex accounts",按额度自动调度 |
| [9router](https://github.com/decolua/9router) <!--s:decolua/9router-->⭐ 25.4k<!--/s--> | **2 — 自有 OAuth 级联** | 请求流:"**Tier 1: SUBSCRIPTION** — Claude Code, Codex, GitHub Copilot" 逐级降到便宜/免费;"**Multi-account** — Round-robin between accounts per provider";仓库里还有标题为 "Antigravity **anti-ban** alignment" 的 PR |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) <!--s:diegosouzapw/OmniRoute-->⭐ 47.4k<!--/s--> | **2 — 自有 OAuth + 免费额度叠加** | "auto-falls back across 4 provider tiers — **Tier 1 Subscription (Claude Code, Codex, Copilot)** … Tier 4 Free";其免费额度看板自己承认 "**15 providers ToS-flagged** so you decide";功能列表包含 "**TLS fingerprint stealth**" |
| [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) <!--s:router-for-me/CLIProxyAPI-->⭐ 47.2k<!--/s--> | **2,向 3 漂移** | "**Claude Code support via OAuth login**";"Claude Code **multi-account load balancing**";README 赞助位在卖 "**ready-to-use accounts**",标价 "10% of the official GPT subscription price" |
| [sub2api](https://github.com/Wei-Shaw/sub2api) <!--s:Wei-Shaw/sub2api-->⭐ 37k<!--/s--> | **3 — 账号池分发** | 自我描述 "**AI API Gateway Platform for Subscription Quota Distribution**","Users can access upstream AI services through **platform-generated API Keys**";自带免责声明:"The authors assume no liability for **account bans**…" |

字里行间有三层信息。第一,第 2 档和第 3 档的分水岭是池子里是*谁的*账号:9router 和 OmniRoute 在你自己机器上路由**你自己的**登录;sub2api 的存在意义就是把池化额度分发给**别人**,连"拼车"计费都是内置的。第二,工具配置暴露作者预期——OmniRoute 内置 TLS 指纹伪装、9router 内置 anti-ban 代码,这些只有在厂商正在检测你时才有意义。第三,sub2api 的赞助商里有住宅 IP 和浏览器指纹隔离厂商,宣传语是降低"关联风控"的概率——这种基础设施的唯一用途就是规避封号系统。这些都不是秘密,全写在 README 里。

## ToS 到底怎么写的

- **Anthropic 消费级条款**(生效 2025-10-08,查阅于 2026-07-27):"You may not share your Account login information, Anthropic API key, or Account credentials with anyone else… You also may not make your Account available to anyone else"(第 2 节);第 3 节禁止 "resell the Services",并规定除 API key 或明确许可外,禁止 "access the Services through automated or non-human means, whether through a bot, script, or otherwise"([条款原文](https://www.anthropic.com/legal/consumer-terms))。最后这一条,让*所有*第 2 档工具天生就是灰色的。
- **2026-02-20——灰色地带正式关闭。** Anthropic 更新合规文档,禁止在第三方产品中使用订阅 OAuth(Free/Pro/Max),开发者"必须改用 API key 认证"([报道,2026-02](https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use))。
- **Anthropic 明说的执法对象**:"a small number of users are violating our usage policies by **sharing and reselling accounts**… we're taking appropriate action to stop it."。Anthropic 员工澄清:持有多个 Max 账号*不*违规——"enforcement is aimed at people using accounts to **resell tokens**"([2026-02-19](https://piunikaweb.com/2026/02/19/anthropic-claude-max-ban-agent-sdk-clarification/)、[背景](https://metricnexus.ai/blog/anthropic-banning-multiple-claude-accounts))。这就是对第 3 档的精确描述。
- **OpenAI 使用条款**:"You may not share your account credentials or make your account available to anyone else and are responsible for all activities that occur under your account"([条款](https://openai.com/policies/row-terms-of-use/);页面有反爬,措辞引自 [OpenAI 账号共享政策的公开转述](https://help.openai.com/en/articles/10471989-openai-account-sharing-policy))。对 ChatGPT 账号池(opencodex 的池模式、CLIProxyAPI、sub2api)含义相同。
- **规模——没有可靠的公开数字。** Anthropic 的 [Transparency Hub](https://www.anthropic.com/transparency) 不发布账号处置统计,流传的封号指南也只讲封号原因与申诉流程、没有总量数字(两处均核查于 2026-07-27)。看到任何「封禁 X 万账号」的总数,都当作无出处对待。

## 封号证据,逐个工具看

- **CLIProxyAPI**——有据可查,且不止一次:"claude code subscription banned"([#2211](https://github.com/router-for-me/CLIProxyAPI/issues/2211),2026-03-18;后续[讨论 #2244](https://github.com/router-for-me/CLIProxyAPI/discussions/2244));"Account Suspended After Using Gemini CLI + Antigravity"([#1803](https://github.com/router-for-me/CLIProxyAPI/issues/1803),2026-03-03);社区帖 "Tip on avoiding account being banned"([#3431](https://github.com/router-for-me/CLIProxyAPI/issues/3431),2026-05-16);还有安全报告指出一把泄露的 key "can exhaust all upstream credentials and cause **permanent account bans**"([#3467](https://github.com/router-for-me/CLIProxyAPI/issues/3467),2026-05-18)。
- **sub2api**——有据可查:有用户报告通过 sub2api 代理 OAuth 后,$20 账号的 Claude 订阅**两次**被掉,发帖问怎么配置才"安全"([#1715](https://github.com/Wei-Shaw/sub2api/issues/1715),2026-04-17);另一位问共享的新加坡服务器 IP 会不会导致**整池账号**一起被封([#2520](https://github.com/Wei-Shaw/sub2api/issues/2520),2026-05-16)。
- **OmniRoute**——有据可查:"Claude Teams/Max accounts **banned by Anthropic right after connecting as provider**"([#4118](https://github.com/diegosouzapw/OmniRoute/issues/4118),2026-06-17——最终以在 UI 加警告收尾);项目还内置了账号封禁检测([#5600](https://github.com/diegosouzapw/OmniRoute/issues/5600),2026-06-30)。
- **9router**——有据可查:"Likelihood of Getting Banned — Claude Code"([#291](https://github.com/decolua/9router/issues/291),2026-03-12);"account suspended"([#2050](https://github.com/decolua/9router/issues/2050),2026-06-24);外加处理"API-banned but OAuth is healthy"账号状态的代码([#1444](https://github.com/decolua/9router/issues/1444),2026-05-26)。
- **Claude Code Router**——**截至 2026-07-27 无记录**:检索其 issue 区,没有任何经 CCR 的 BYOK 路径被封号的报告。与机制自洽:API key 流量本来就是厂商卖的东西。
- **opencodex**——截至 2026-07-27 无记录(仓库才 ~6 周;其 ChatGPT 池模式与上面几家风险同源,只是证据还没积累起来)。
- **freellmapi**——截至 2026-07-27 无记录;它自带的 ToS 审查表是这批工具里最接近"风险文档"的东西。

规律和档位表完全吻合:每一条有记录的封号都发生在第 2/3 档的 OAuth 或池化流量上;BYOK 路由的封号报告,我们一条都没找到。

## 宣称的省钱 vs 实测数据

| 工具 | 宣称的省钱 | 状态 |
|---|---|---|
| OmniRoute | 压缩 "saves 15–95% tokens (~89% avg)";叠加免费额度 "~1.53B free tokens/mo" | **厂商自称**(README 头图 + 免费额度卡);未经独立验证 |
| 9router | "Save 20-40% tokens with RTK + auto-fallback" | **厂商自称**(README 标语) |
| freellmapi | 叠加免费额度约 "4 billion tokens per month" | **厂商自称**(README);是容量,不是省钱百分比 |
| Claude Code Router | 无省钱数字——卖点是路由 + 可观测 | 无记录 |
| CLIProxyAPI | 无省钱数字——卖点是复用订阅额度 | 无记录 |
| sub2api | 无省钱数字——卖点是池化额度拼车 | 无记录 |
| opencodex | 无省钱数字 | 无记录 |

再看本仓库自己的单测基准怎么说:**同一个编码 Agent 会话**(输入 50K / 输出 20K / +30K 思考),DeepSeek V4-Flash 花 **$0.021**,GPT-5.5 花 **$1.75**——**约 83 倍**([Part 3.3](../BENCHMARKS.zh-CN.md))。按每美元能力算,**DeepSeek V4 Pro 在 SWE-bench Verified 上追平 Gemini 3.1 Pro(80.6%),价格约 1/11**;95% 天花板模型的价格约是"最便宜且过 80%"模型的 46 倍。换句话说:**用一个普普通通的第 1 档 BYOK 路由器做模型选择,就能拿到这些工具宣传的绝大部分省钱——ToS 风险为零。** 如果要把 Claude Code 跨格式路由到 OpenAI 风格上游,选实测扛得住协议翻译的网关:我们的[独立保真度测试](../BENCHMARKS.zh-CN.md)里 LiteLLM 和 Bifrost 都是 3/3(工具调用 + 流式 + usage);记得锁版本。

## 我们会怎么选

- **任何正经用途——工作代码、客户的仓库、承载你历史记录的账号:只用第 1 档。** BYOK API key 挂在 Claude Code Router 后面(需要跨格式翻译就用 LiteLLM/Bifrost),默认路由便宜模型、按需升级。83 倍的模型价差才是钱的所在,而且从没有人因为这条路径被封号。
- **第 2 档(自有 OAuth 路由:9router、OmniRoute、CLIProxyAPI、opencodex 池模式)——只用你真赔得起的小号**,隔离账号、没有工作历史。2026-02-20 之后这已明确违反 Anthropic 的公开政策,上面的封号报告全是真实且有日期的,"这工具有伪装功能"应该读作警告,不是安心丸。
- **第 3 档(sub2api 式账号池分发)——我们不会碰。** 做池主,你就是 Anthropic 明说要封的对象(其赞助商生态里的反风控工具说明池主们心知肚明);做买家,你买到的是无法验证的转售容量——[2026 年针对转售中转的独立指纹研究](https://arxiv.org/abs/2603.01919)测出**45.8% 的指纹测试模型身份验证失败**。

完整成本表、SWE-bench-vs-成本图和网关记分卡见**[评测集 →](../BENCHMARKS.zh-CN.md)**。按需求浏览全部网关见 **[Awesome AI Gateway →](../README.zh-CN.md)**。

---

*有用的话给榜单[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)——下一个选网关的工程师就是这样找到它的。CC0,无注册,无跟踪,不拿厂商的钱。*
