# AI 网关路由与模型选择——研究全景、理论与开放问题

**语言：** [English](routing-landscape.md) · 简体中文

*一份经过诚实标注来源的综述。最近审阅 **2026-07-23**。属于 [Awesome AI Gateway](../README.zh-CN.md)。*

这是 [🧠 智能路由与模型选择](../README.zh-CN.md#-智能路由与模型选择) 章节背后的**领域地图**：路由借鉴了哪些理论、它实际成熟到什么程度、有哪些奠基论文与公司文章、有哪些评测基准，以及还有哪些没解决的问题。那个章节列的是*工具*，本页讲的是「**为什么、从哪来**」——在你相信任何 router 的「我们省了 70% 成本」宣称之前先读这篇，因为那些数字大多来自下面这些论文，是在某一个基准上测出来的，而那个基准未必是你的流量。

> **先把话说在前面。**与 LLM *可观测性*不同（那还算不上一门学科——见[姊妹综述](observability-landscape.zh-CN.md)），**LLM 路由有一套真实的、经同行评审的文献**：成本感知级联、学习型 query router、多模型集成各自都有配可复现基准的奠基论文。但有两条告诫贯穿始终。（1）**几乎每个标题级的成本/质量数字都是基准特定的**——在 RouterBench 或 MT-Bench 上调出来的 router，换到你的流量上可能就失去优势；收益很少能原样迁移。（2）**生产环境里很大一部分「路由」根本不是学习出来的**——就是静态规则（按任务、按 header、按成本档），而且一份近期企业调研发现买家往往干脆[换到单一最强模型，而不是为省钱做路由](https://menlovc.com/perspective/2025-mid-year-llm-market-update/)。全文我们都标注**同行评审** vs **厂商/行业** vs **我方综合**，且每条宣称都标了日期、给了链接，方便你复核。

---

## 1. 它借鉴的理论（经典 ML → LLM 路由）

### 1.1 前提：没有哪个模型能在成本*和*质量上同时占优
路由之所以成立，是因为前沿是一条**帕累托前沿**而不是一个点：能搞定*简单* prompt 的最便宜模型，比*困难* prompt 所需的旗舰模型便宜 10–100×（本清单自己的[成本表](../BENCHMARKS.zh-CN.md)测得同一份 100K token 的报告 **$0.03 vs $3.01**——106× 的价差）。如果有一个模型样样最强，你直接写死它就行，路由毫无意义。实证依据：真实网关流量表明**驱动模型切换的是质量而非价格**，且「最佳」模型更替得很快（[100T token 研究](https://arxiv.org/abs/2601.10088)）。路由押的是一个运营层面的赌注：*按 prompt* 选模型胜过*按应用*选模型。

### 1.2 级联与「学会移交」（最深的一条根）
级联——*先试便宜模型，只有置信度/质量信号说要升级时才升级*——源自两条经典思路：
- **选择性预测 / 拒识选项（selective prediction / reject option）**（Chow, 1970；El-Yaniv & Wiener, 2010）：分类器不确定时可以*弃答*，用覆盖率换准确率。LLM 级联的「升级到大模型」正是一次拒识加移交（reject-and-defer）。
- **学习移交 / 带拒绝器的学习（learning to defer / learning with a rejector）**（Cortes、DeSalvo & Mohri, 2016；Mozannar & Sontag, 2020）：形式化了*何时移交给更贵的专家*。LLM 级联就是它在成本预算下、「专家 = 旗舰模型」的版本。

尚未解决的难点是**移交信号（deferral signal）**：模型自报的置信度标定不准，所以级联转而依赖校验模型、答案一致性或学出来的元模型——而且有一个同行评审结果表明，在一般情形下朴素的置信度阈值*可证明*不够用（§3.1）。

### 1.3 集成与 Mixture-of-Experts（另一条谱系）
级联挑*一个*模型，**集成（ensembling）**则组合*多个*。它借鉴自经典的 bagging/boosting/stacking 与 **Mixture-of-Experts**（Jacobs 等, 1991；Shazeer 等, 2017）：由一个**门控函数（gating function）**把请求路由给（或混合）各专家。2024–26 的新变化在于「专家」变成了来自*不同厂商*的整个前沿 LLM，在 API 层组合——即「同时用几个模型打败其中任何一个」的模式（§3.3）。代价是实打实的：查询 N 个模型的集成每条 prompt 要付约 N× 的钱，所以只有当质量比 token 更值钱时才划算——而且 2025 年有结果指出，混合*不同*模型常常不如对单一最佳模型多次采样（§3.3, Self-MoA）。

### 1.4 让路由变得合理的经济学
路由是对一种价格结构的回应，不是一种时髦：
- **推理价格降得快但不均匀**——*固定能力水平*的价格每年下降约 9×–900×（中位数约 50×；[Epoch AI](../README.zh-CN.md#-必读精选)），昨天的旗舰任务就是今天的平价路由。
- **模型市场的实时价差 >400×**（[aipricing.guru 快照](../README.zh-CN.md#-评测速递)）；每一条发给「比所需更强的模型」的 prompt 都是把钱点着烧。
- **多模型已经是默认状态**——>70% 的生产组织跑 3 个以上模型，44% 按任务类型路由，11% 按成本路由（[Datadog / Amplify](../README.zh-CN.md#-评测速递)）。路由就是把「我们用很多模型」变成「每条请求都花最少的钱」的机制。

---

## 2. LLM 路由的成熟度分级

*我方综合提案（非行业标准）。各档是**复杂度的累加**，而非严格的优劣排序——在真实流量上，一条调得好的 L1 规则常常胜过一个泛化差的 L3 学习型 router。每升一档都会增加决策延迟、一份训练/数据依赖，以及一种新的失败模式。*

| 档 | 怎么决策 | 换来什么 | 增加的成本/风险 |
|---|---|---|---|
| **L0 — 静态/人工** | 一个模型，或人工设的默认值 | 简单；零路由开销 | 整个价差都留在桌上 |
| **L1 — 启发式规则** | 正则/长度/任务标签/header 规则（「代码 → 模型 A，聊天 → 模型 B」） | 便宜、透明、不需要训练数据；生产环境大多数「路由」在这档 | 脆弱；模型一换，规则得靠人维护 |
| **L2 — 学习型预测 router** | 训练一个分类器在*生成之前*给 prompt 难度打分、选便宜还是选强 | 只花一次前向传播的开销，做到按 prompt 的成本/质量优化 | 需要训练数据；**泛化鸿沟**——在一个基准上调、部署到另一个上 |
| **L3 — 级联/移交** | 先用便宜模型生成；置信度/校验信号只把难例升级 | 只在需要时才为大模型付钱；实践中常是最优的成本/质量点 | 升级的 prompt 有额外延迟；移交信号难标定 |
| **L4 — 集成/混合 + 在线自适应** | 查询多个模型并聚合（MoA），或根据反馈在线调整路由权重 | 质量可超过*任何单个模型*；能适应漂移 | 约 N× token 成本；复杂度；聚合可能放大共同错误 |

2026 年大多数团队处在 **L1**；差异化 router 在 **L2/L3** 竞争；**L4** 留给质量关键、对成本不敏感的负载。

---

## 3. 研究全景（论文）

> **怎么读这些数字：**下面每个「以 GPT-4 质量的 Y% 省 X% 成本」都是**在某个特定基准上测出来的**（RouterBench、MT-Bench、MMLU、GSM8K……）。把它们当作*路由可以奏效的存在性证明*，而不是你流量的规格书。想知道你自己的数字，唯一可靠的办法是拿 router 在你自己的评测集上做 A/B。

### 3.1 成本感知路由与级联
- [FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance](https://arxiv.org/abs/2305.05176) — Chen、Zaharia & Zou（Stanford），arXiv 2023 — 提出 LLM 级联：先查询更便宜的模型，只有当一个学出来的打分函数判定当前答案不可靠时才升级到更贵的模型；在作者的基准上报告以最多低 98% 的成本达到与 GPT-4 相当的准确率。
- [AutoMix: Automatically Mixing Language Models](https://arxiv.org/abs/2310.12963) — Aggarwal、Madaan 等，arXiv 2023（NeurIPS 2024）— 用少样本自我校验加一个基于 POMDP 的元校验器决定何时升级，把请求从较小 LM 路由到较大 LM，在准确率相当的情况下削减 50% 以上的计算成本。
- [Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing](https://arxiv.org/abs/2404.14618) — Ding 等，Microsoft/UBC，ICLR 2024 — 训练一个 router，按预测的质量差距和一个可调阈值把每条 query 发给小模型或大模型，在保持响应质量的同时把大模型调用削减最多 40%。
- [When Does Confidence-Based Cascade Deferral Suffice?](https://arxiv.org/abs/2307.02764) — Jitkrittum、Gupta、Menon 等（Google Research），NeurIPS 2023 — 证明在下游是专精模型、有标签噪声或分布偏移时，简单的基于置信度的级联移交可证明是次优的，事后（post-hoc）移交规则表现更好——「升级信号才是难点」背后的理论。
- [Language Model Cascades](https://arxiv.org/abs/2207.10342) — Dohan、Xu、Lewkowycz 等（Google），arXiv 2022 — 把 scratchpad、校验器、STaR、selection-inference 与工具使用形式化为组合多次 LM 调用的概率程序——校验器式与选择式级联背后的统一框架。

### 3.2 学习型预测 router
- [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665) — Ong 等，UC Berkeley/Anyscale（LMSYS），arXiv 2024 — 用人类偏好数据训练 router，把每条 query 发给强模型或弱模型，在质量持平的情况下把成本削减超过 2×，并能迁移到未见过的模型对；开源 router 的经典论文。
- [RouteLLM: An Open-Source Framework for Cost-Effective LLM Routing](https://lmsys.org/blog/2024-07-01-routellm/) — LMSYS Org，博客 2024 — 配套发布：一个带 OpenAI 兼容 server 的开源 router，在 MT-Bench/MMLU/GSM8K 上分别削减约 85%/45%/35% 的成本，同时保住约 95% 的 GPT-4 质量。
- [Routing to the Expert: Efficient Reward-guided Ensemble of Large Language Models (Zooter)](https://arxiv.org/abs/2311.08692) — Lu 等，Alibaba，arXiv 2023 — 把奖励模型的监督蒸馏进一个 query router，把每条 prompt 派发给多个专家 LLM 中最合适的那个，在 26 个任务子集上击败最强单模型。
- [RouterDC: Query-Based Router by Dual Contrastive Learning for Assembling Large Language Models](https://arxiv.org/abs/2409.19886) — Chen 等（HKUST / SUSTech），NeurIPS 2024 — 用双对比损失训练一个 query 编码器加每个 LLM 的 embedding，按 query 选出最佳模型，在分布内与分布外任务上都优于单模型和先前的 router。
- [GraphRouter: A Graph-based Router for LLM Selections](https://arxiv.org/abs/2410.03834) — Feng、Shen & You（UIUC），arXiv 2024 — 把模型选择框定为「任务-query-LLM」异构图上的边预测，新加入的 LLM 无需重训 router 即可泛化。
- [Universal Model Routing for Efficient LLM Inference](https://arxiv.org/abs/2502.08773) — Jitkrittum 等，Google Research，arXiv 2025 — 用每个 LLM 在代表性 prompt 上的预测构造特征向量来表示它，让一个 router 泛化到训练时未见过的 30+ 个 LLM，并给出超额风险界。
- [TensorOpera Router: A Multi-Model Router for Efficient LLM Inference](https://arxiv.org/abs/2408.12320) — Stripelis 等，TensorOpera，EMNLP 2024（Industry）— 在一个接口后集成多个 LLM 专家，动态把每条 query 路由到最合适的模型，报告在保持质量的同时获得最高 40% 的效率收益与 30% 的成本收益。

### 3.3 集成 / 混合 / 多模型协作
*「组合多个模型打败任何单个模型」这一簇——以及诚实的反证：它并不总是划算。*
- [Mixture-of-Agents Enhances Large Language Model Capabilities](https://arxiv.org/abs/2406.04692) — Wang 等（Together AI、Duke、Stanford），arXiv 2024 — 把多个开源 LLM 分层作为 proposer 与 aggregator，在 AlpacaEval 2.0 上达到 65.1%，对比 GPT-4o 的 57.5%——代价是每条 query 多花好几次前向传播。
- [Together MoA — collective intelligence of open-source models](https://www.together.ai/blog/together-moa) — Together AI，博客 2024 — MoA 的厂商解读：可调的 proposer、aggregator 与层数，用更慢的首 token 时间换更高的准确率。
- [LLM-Blender: Ensembling Large Language Models with Pairwise Ranking and Generative Fusion](https://arxiv.org/abs/2306.02561) — Jiang、Ren & Lin（USC、AI2），ACL 2023 — PairRanker 用成对交叉注意力比较选出每条 query 的最佳候选，GenFuser 把最优的几个输出融合起来；LLM 集成的奠基论文。
- [Fusing Models with Complementary Expertise](https://arxiv.org/abs/2310.01542) — Wang 等，MIT-IBM Watson AI Lab，ICLR 2024 — 把组合互补领域专家模型的输出建模为一个有监督融合问题，并给出一个每次输入只查询更少专家的节俭变体。
- [More Agents Is All You Need](https://arxiv.org/abs/2402.05120) — Li 等（Tencent），arXiv 2024 — 从*单个* LLM 采样许多独立回答再做多数投票，准确率随采样数上升——在采用多模型集成之前，这是一个值得先打败的单模型基线。
- [Rethinking Mixture-of-Agents: Is Mixing Different LLMs Beneficial? (Self-MoA)](https://arxiv.org/abs/2502.00674) — Li 等，Princeton，arXiv 2025 — 反方观点：对*单一最佳*模型聚合多次采样（Self-MoA）常常胜过混合不同的 LLM，因为混合的质量会被其中较弱的模型拖低。在假设「模型越多越好」之前先读这篇。

### 3.4 自路由 / 自选择
*由模型自己决定回答还是移交/升级的方法——自选择思想：路由信号来自模型的自我评估，而非外部分类器。*
- [Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach (Self-Route)](https://arxiv.org/abs/2407.16833) — Li 等，Google，EMNLP 2024 — Self-Route 先把每条 query 发给便宜的 RAG，只有当模型*自我反思*认为检索到的上下文不足时才回退到完整长上下文，在质量相当的情况下削减约 65%（Gemini-1.5-Pro）/约 39%（GPT-4o）的成本。
- [Learning to Route LLMs with Confidence Tokens](https://arxiv.org/abs/2410.13284) — Chuang 等，arXiv 2024 — 训练 LLM 输出经过标定的置信 token（Self-REF），router 据此接受、拒绝或移交给另一个专家——胜过口头置信度与原始 token 概率基线。
- [OrchestraLLM: Efficient Orchestration of Language Models for Dialogue State Tracking](https://arxiv.org/abs/2311.09758) — Lee、Cheng & Ostendorf（UW / Microsoft Research），NAACL 2024 — 通过在带标注的范例池上做 kNN 检索（无需训练 router），把每个对话轮次在小 LLM 与大 LLM 之间路由，在提升准确率的同时削减 50% 以上的计算。

### 3.5 router 的基准与评测
- [RouterBench: A Benchmark for Multi-LLM Routing System](https://arxiv.org/abs/2403.12031) — Martian（withmartian），arXiv 2024 — 首个大规模路由基准：405k 条推理结果，外加一个在成本-质量前沿上比较 router 的理论框架。
- [RouterArena: An Open Platform for Comprehensive Comparison of LLM Routers](https://arxiv.org/abs/2510.00202) — Lu 等（RouteWorks），arXiv 2025 — 开放评测平台 + [活榜单](https://github.com/RouteWorks/RouterArena)，在 9 个领域 / 44 个类别上按五个指标（准确率、成本、最优性、鲁棒性、延迟）对开源与商业 router 做基准测试。
- [RouterEval: A Benchmark for Routing LLMs to Explore Model-level Scaling Up](https://arxiv.org/abs/2503.10657) — Huang 等，EMNLP 2025 Findings — 一个离线 router 基准：覆盖 8,500+ 个 LLM 的 2 亿+ 条预计算性能记录，揭示一种「模型级 scaling」效应——router 越强，候选池扩大时的收益越大。

### 3.6 综述与经济学
- [Doing More with Less: A Survey on Routing Strategies for Resource Optimisation in LLM-Based Systems](https://arxiv.org/abs/2502.00409) — Varangot-Reille 等，arXiv 2025 — 给 query 路由方法做分类（相似度、有监督、RL、生成式），并框定何时路由到更小/更专精的模型能改善成本/质量/延迟权衡。
- [Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey](https://arxiv.org/abs/2603.04445) — Moslem & Kelleher（ADAPT Centre, Trinity College Dublin；Huawei Ireland），arXiv 2026 — 用「决策时机、所用信息、计算方式」组织的框架，系统化推理时的路由与级联。
- 路由的*经济学一手资料*——Epoch AI 价格趋势、[100T token 研究](https://arxiv.org/abs/2601.10088)、以及 LLM 服务中断研究（故障转移的依据）——已收录在 [📚 必读精选 → 路由与兜底](../README.zh-CN.md#-必读精选)；本页不再重复。

---

## 4. 各公司发表了什么

### 商业 router（厂商文档——看*接口*就好，营销要打折扣）
- [How OpenRouter Model Routing Works: Providers, Fallbacks & Auto Router](https://openrouter.ai/blog/insights/model-routing/) — OpenRouter，博客 2026 — 两个相互独立的路由决策（由哪个*模型*回答 vs 由哪个*供应商*服务），配供应商级故障转移、模型级 fallback 数组，以及一个按 prompt 挑模型的 `openrouter/auto` 端点。
- [Auto Router (Intelligent Model Selection)](https://openrouter.ai/docs/guides/routing/routers/auto-router) — OpenRouter，文档 2026 — 把每条 prompt 分类到约 30 种任务类型，按近 7 天的社区消费份额给候选模型排序，并暴露一个成本/质量旋钮，支持主选 + fallback。
- [What is Model Routing?](https://docs.notdiamond.ai/docs/what-is-model-routing) — Not Diamond，文档 2026 — 厂商定义：在三种显式模式（质量（默认）、成本、延迟）之一下，按 query 选出最佳候选 LLM。
- [Introducing RouterBench](https://withmartian.com/post/introducing-routerbench) — Martian，博客 2024 — RouterBench 背后的公司：约 405k 条结果的基准，加上 AIQ（成本-质量曲线下面积）指标，配 Zero-Router 与 Oracle-Router 基线。

### 前沿模型自己正在变成 router
- [Introducing GPT-5](https://openai.com/index/introducing-gpt-5/) — OpenAI，博客 2025 — GPT-5 以*统一系统*的形态发布：一个实时 router 按对话类型、复杂度、工具需求和显式意图，逐条 query 在快模型与更深的推理模型之间决策。路由层挪到了模型*内部*——这也是「用哪个模型？」如今常变成「用模型内哪条路？」的原因。

### 市场数据（行业调研——也包括反证）
- [State of AI: An Empirical 100-Trillion-Token Study with OpenRouter](https://arxiv.org/abs/2601.10088) — OpenRouter + a16z，arXiv 2026 — 100T+ token 的网关流量：开放权重模型约占 ⅓ 的量，推理模型过半，外加一张「开发者在各任务类型上真实把钱花在哪些模型」的地图——关于真实路由行为的一手数据集。
- [2025 Mid-Year LLM Market Update](https://menlovc.com/perspective/2025-mid-year-llm-market-update/) — Menlo Ventures，2025 — 对成本路由的诚实反证：66% 的企业构建者在*现有供应商内部*升级模型，只有 11% 更换厂商，且偏爱前沿模型而非更便宜的档位——买家往往*并不*为省钱做路由。

### 网关路由机制
你实际会配置的具体重试/兜底/权重机制——**LiteLLM**（路由与负载均衡、router 架构）与 **Portkey**（负载均衡）——见 [📚 必读精选](../README.zh-CN.md#-必读精选)。云厂商第一方 router（AWS Bedrock、Azure AI Foundry、Vertex）列在 [🌐 原厂直连](../README.zh-CN.md#-原厂直连云厂商模型厂商)。

---

## 5. 标准与接口（或者说：并没有）

**不存在路由标准**——这话值得直说。路由骑在 **OpenAI 兼容**的接口面上：你要么（a）发一个真实 model id，让*网关*套用配置好的规则；要么（b）发一个**哨兵 model id**（`openrouter/auto`、某个档位名），让供应商来路由。没有一种可互操作的方式能跨网关表达「按成本路由、质量下限为 X」；没有*上报路由后实际服务的模型*的标准（最接近的是 OTel GenAI 的 `gen_ai.response.model`——见[可观测性全景 §5](observability-landscape.zh-CN.md#5-标准)）；除了 §3.5 的社区基准，也没有标准的 router 评测协议。**实际后果：**永远记录*解析后的*模型，否则 router（或中转）静默给你降档是不可见的——正是[中转观察名单](../README.zh-CN.md#社区中转避雷观察名单)所针对的那个保真问题。

---

## 6. 工具（分类法）

router *工具*就在清单本身——[🧠 智能路由与模型选择](../README.zh-CN.md#-智能路由与模型选择)——涵盖商业 router（Not Diamond、Martian、OpenRouter Auto、Inworld、Unify）、开源框架（RouteLLM、LLMRouter、vLLM Semantic Router、NVIDIA LLM Router）、编码 Agent router（Claude Code Router、ClawRouter、workweave/router、UncommonRoute、NadirClaw）、网关原生路由（Bifrost、Cloudflare、Kong），以及评测层（RouterArena、OrcaRouter）。本页是那套分类法背后的理论；那个章节是购买清单。

---

## 7. 开放问题 / 进行中的争论

1. **泛化 / 基准陷阱**——在 RouterBench 或 MT-Bench 上调出来的 router，在分布外流量上常常失去成本/质量优势。报告的节省很少能原样迁移，而且没有公认的方法能在不实际运行的情况下预测某个 router 在*你的流量*上的数字（§3.5 的存在正是因为这个）。
2. **移交信号的标定**——级联的生死取决于「这个答案够好了吗，可以停了吗？」。自报置信度标定不准，校验模型增加成本且自带误差，而朴素的置信度阈值在一般情形下*可证明*不够用（[§3.1](https://arxiv.org/abs/2307.02764)）。廉价且标定良好的升级信号尚无定论。
3. **混合到底有没有用？**——MoA 式集成假设各模型的错误足够*独立*，聚合才有帮助；[Self-MoA](https://arxiv.org/abs/2502.00674) 表明把较弱模型混进来可能反而*拉低*质量，不如对单一最佳模型采样。多模型何时胜过单模型仍无定论，且依赖负载。
4. **路由开销 vs 节省**——学习型 router 多一步分类；集成多花约 N× 的 token。对短/便宜的 prompt，路由成本可能超过路由节省；盈亏平衡点因负载而异，且缺乏测量。
5. **非平稳性**——路由背后的模型会在你脚下变化（新版本、静默改指向、弃用）。上个季度训练的 router 可能正把请求派给一个行为已经不同的模型——路由与[静默漂移检测](observability-landscape.zh-CN.md#32-静默模型漂移gpt-是不是变笨了)是同一个问题戴了两顶帽子。
6. **隐私 / 谁为了路由先看到 prompt**——预测式路由要在选模型*之前*读 prompt，于是 router（往往是第三方）什么都看得到——在网关本身之上又多了一层数据暴露面（见[数据留存矩阵](../README.zh-CN.md#-谁看得到你的-prompt-数据留存矩阵)）。
7. **质量在生产中没有 ground truth**——每个路由决策优化的都是质量的一个*估计*（评审模型、奖励模型、代理指标）。router 的好坏受限于那个估计器，而估计器本身有噪声——与[可观测性全景 §7](observability-landscape.zh-CN.md#7-开放问题--进行中的争论) 相同的极限。

---

## 8. 与*本项目*的映射

- **[🧠 智能路由与模型选择](../README.zh-CN.md#-智能路由与模型选择)** = 本页为其提供理论的工具购买清单。
- **[📊 BENCHMARKS](../BENCHMARKS.zh-CN.md)** = 让路由变得合理的可复现成本价差（§1.1、§1.4）——实测出来的，不是断言的。
- **[社区中转观察名单](../README.zh-CN.md#社区中转避雷观察名单) + [`canary_check.py`](../scripts/canary_check.py)** = 对 §5/§7.5 的操作性回应——验证 router *实际*给你服务的模型。
- **[可观测性全景](observability-landscape.zh-CN.md)** = 姊妹综述；路由与漂移检测是「这个端点还是它声称的那个吗？」这同一个问题的两个视角。

---

*欢迎通过 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充。这是一份活的综述——领域年轻、变化快，每条宣称都标了日期与来源，方便你复核。这些数字天然是基准特定的——永远要在你自己的流量上重测。*
