# AI 网关可观测性——研究全景、理论与开放问题

*一份经过诚实标注来源的综述。最近审阅 **2026-06-26**。属于 [Awesome AI Gateway](../README.zh-CN.md)。*

**语言：** [English](observability-landscape.md) · 简体中文

这是这块领域的**地图**：它借鉴了哪些经典理论、目前成熟到什么程度、有哪些奠基论文与公司文章、有哪些标准与工具，以及还有哪些没解决的问题。它与 [BENCHMARKS → 第六部分](../BENCHMARKS.zh-CN.md#第六部分--网关可观测性真正该看的因素)（「**怎么评估**一个网关的可观测性」的实操评分表）互补——本页讲的是「**为什么、从哪来**」。

> **先把话说在前面。**「LLM 可观测性」**并不是**一门成熟的学科。成熟、经过同行评审的文献集中在**评测**（LLM-as-judge、评测套件）与**模型漂移**两块。可观测/追踪/看板这套操作性话语，**绝大多数是厂商博客 + OpenTelemetry GenAI 约定**，学术界只是在 2025–2026 才开始零星跟进。全文我们都标注：**同行评审** vs **厂商/行业** vs **我方综合**。谁要是卖给你一套「LLM 可观测性的权威分类法」，那是夸大其词——目前还不存在。

---

## 1. 它借鉴的经典理论（经典可观测性 → AI 网关）

### 1.1 「三支柱」——以及对它的批判
metrics / logs / traces 这个框架由 **Peter Bourgon**（《Metrics, tracing, and logging》, 2017）定型——与其说是分层，不如说是按属性区分：**metrics** 可*聚合*（最便宜），**logs** 是*离散事件*（最贵，量常常超过它所记录的流量本身），**traces** 是*请求作用域*的。[[Bourgon]](https://peter.bourgon.org/blog/2017/02/21/metrics-tracing-and-logging.html)

三支柱后来变成了*厂商话术*，并被它的提出者们自己批判：**Ben Sigelman**（《Three Pillars with Zero Answers》, 2018）——*「metrics、logs、traces 只是数据——是燃料，不是车」*；可观测性是**度量 + 解释**，而非三套各自为政的工具。[[Lightstep]](https://medium.com/lightstephq/three-pillars-with-zero-answers-2a98b36358b8) **Charity Majors** 把它重构为**可观测性 1.0 → 2.0**：从「每个请求在各孤岛工具里存很多份拷贝」，到「**一个事实来源——宽的结构化事件**，metrics/traces 都从中派生」。[[Honeycomb]](https://www.honeycomb.io/blog/one-key-difference-observability1dot0-2dot0)

**映射到 AI 网关**（我方综合，依据 §5 的 OTel GenAI 约定）：

| 支柱 | 经典 | AI 网关对应 |
|---|---|---|
| **Metrics** | 延迟、RPS、错误率 | 输入/输出 token、**每请求美元成本**、首 token 时间、token/秒、缓存命中率——按 模型/路由/租户 切分 |
| **Logs** | 请求/错误事件 | **prompt + completion 本身**——价值最高、风险最高、量最大的产物（见 §7 PII） |
| **Traces** | 跨服务 RPC span | **多步 / Agent span**：`invoke_agent` → 子 `chat` 调用 → `execute_tool` 调用，含重试、兜底、RAG 检索 |

一个打破经典假设的 LLM 特性：**延迟与成本与 token 数相关，而非请求数。**

### 1.2 可观测性 vs 监控——以及为什么 LLM 是极端情形
经典区分（Majors/Honeycomb）：**监控**用预设看板回答*已知的未知*；**可观测性**是*「不发新代码就能向系统提新问题的能力」*——属于**未知的未知**，靠**高基数**（把 用户/请求/会话 当一等实体来分组）实现。[[Honeycomb 宣言]](https://www.honeycomb.io/blog/observability-a-manifesto) AI 网关是**极端**情形：每个请求带一段独一无二的自由文本 prompt，输出空间是无界的自然语言，失败是**语义性**的（一个 HTTP 200、内容却微妙地错了），所以你**无法预先枚举**将来需要查询的失败模式。

### 1.3 SRE 的 SLI/SLO/错误预算——以及难啃的新「质量 SLO」
出自 [Google SRE 手册](https://sre.google/sre-book/service-level-objectives/)：**SLI**（一个度量）、**SLO**（一个目标）、**错误预算** = 1 − SLO。AI 网关的 SLO 长什么样（我方综合）：
- **能干净移植的：** 可用性（非 5xx 占比）、延迟——但要拆成**首 token 时间**（流式 UX）与**总完成时间**（依赖 token 数、更抖）。
- **新但可行的：** **成本/消费预算**——错误预算的逻辑天然映射到美元。
- **真正难的：** **质量 SLO**。「正确」是模糊的、生产无 ground truth，所以质量 SLO 只能对一个*代理指标*来定（「抽样响应中 ≥X% 通过 LLM 评审打分」）——也就是**对一个噪声估计量设 SLO**，这是 SRE 从未面对过的一步。

**配套框架——四个黄金信号。** SRE 另一套经典指标（[*Monitoring Distributed Systems*](https://sre.google/sre-book/monitoring-distributed-systems/)）是检查网关埋点最快的尺子：

| 黄金信号 | 经典 | AI 网关形态 |
|---|---|---|
| **延迟 Latency** | 请求耗时 | TTFT **与** 总完成时间（依赖 token 数），按 模型/路由 |
| **流量 Traffic** | 请求/秒 | 请求/秒 **与 token/秒**（真正的负载单位） |
| **错误 Errors** | 错误率 | **按来源**——厂商 4xx/5xx vs 网关 vs 护栏 vs 内容过滤（笼统错误率没用） |
| **饱和度 Saturation** | 服务有多「满」 | 上游**限流/配额余量**、预算余量，以及（自托管）GPU/队列深度 |

### 1.4 控制论 → 闭环
经典反馈控制器（观察输出 → 比对设定值 → 调整）映射到**评测 → 路由/护栏调整**：LLM 后置护栏配自我纠正、LLM 评审同时充当评测与动态护栏。其局限（我方综合）：经典控制假设*被控对象稳定*、*误差可测*；而 AI 网关的「被控对象」（上游模型）可能被**静默改路由**，误差信号（质量）又是由另一个 LLM 估出来的——于是闭环可能去追一个被标定错的设定值。

---

## 2. AI 网关可观测性的成熟度分级

*我方综合提案（非行业标准）。各档是**能力的累加**，而非严格先后——且每升一档都会放大「可观测性成本」与隐私面（§7）。档位更高 ≠ 判定更可信，因为 L3–L4 都依赖噪声很大的 LLM 评审估计量。*

| 档 | 能力 | 解锁什么 |
|---|---|---|
| **L0 — 原始日志** | prompt/响应记成扁平日志 | 事后调试、审计轨迹（欧盟 AI 法案 Art. 12 的最低要求） |
| **L1 — 指标 + 成本归集** | token/延迟/成本指标按 模型/路由/租户 | 预算告警、延迟 SLO、按租户分账、回归发现 |
| **L2 — 分布式追踪** | 跨 Agent/工具/RAG 步骤的 OTel GenAI span | 多步失败根因、span 级成本/延迟归集 |
| **L3 — 在线评测：质量 + 漂移** | 对实时流量抽样做 LLM 评审/无参考打分；对固定端点跑黄金集回归；统计漂移（PSI/KS/embedding 质心） | 质量 SLO、**静默漂移/改路由检测**、未知-未知的语义失败 |
| **L4 — 闭环自动纠正** | 评测自动反馈到路由、兜底、护栏调整 | 自我纠正响应、质量回归时自动模型故障转移、自适应护栏 |

2026 年大多数团队稳在 **L1**、够向 **L2**；**L3** 是差异化工具的竞技场；**L4** 基本还是愿景。

---

## 3. 研究全景（论文——「扒下来」）

> **它真实的样子：** *评测*与*漂移*两个集群确实是学术的、同行评审的、被大量引用的。*可观测/追踪*集群很薄、刚冒头（2025–2026），且是从 **agent-trace 溯源 / 失败定位**这个角度切入的，而非一个专门的「可观测性」传统。

### 3.1 评测与 LLM-as-judge（学术最强集群）
- **Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena** — Zheng 等，**NeurIPS 2023**。奠基性的 LLM-as-judge 论文：GPT-4 评审与人类偏好一致 >80%；点名**位置/冗长/自我偏好**偏差。[arXiv:2306.05685](https://arxiv.org/abs/2306.05685)
- **HELM（语言模型的整体性评测）** — Liang、Bommasani、Lee 等（Stanford CRFM），**TMLR 2023**。多指标整体评测 + 活榜单。[arXiv:2211.09110](https://arxiv.org/abs/2211.09110)
- **Chatbot Arena** — Chiang、Zheng 等（LMSYS），**ICML 2024**。众包成对人类偏好 Elo；事实上的「真实世界」评测基础设施。[arXiv:2403.04132](https://arxiv.org/abs/2403.04132)
- **G-Eval** — Liu 等，**EMNLP 2023**。CoT + 填表式 LLM 评审；与人类相关性高，也指出对 LLM 生成文本的自偏。[arXiv:2303.16634](https://arxiv.org/abs/2303.16634)
- **lm-evaluation-harness**（EleutherAI）——Open LLM Leaderboard 背后的标准可复现评测套件。[GitHub](https://github.com/EleutherAI/lm-evaluation-harness)
- **A Survey on LLM-as-a-Judge** — Gu 等，2024。可靠性策略 + 偏差缓解。[arXiv:2411.15594](https://arxiv.org/abs/2411.15594)
- 生产监控用的幻觉信号：**SelfCheckGPT** — Manakul 等，EMNLP 2023。[arXiv:2303.08896](https://arxiv.org/abs/2303.08896)

*文献趋同的评审偏差：**位置偏差**（最高约 75% 偏向第一个回答）、**自我偏好**（~10–25%）、**冗长偏差**（越长越被偏好）。*

### 3.2 静默模型漂移（「GPT 是不是变笨了？」）
- **How Is ChatGPT's Behavior Changing over Time?** — Chen、Zaharia、Zou（Stanford/Berkeley）。arXiv 2307.09009（2023）；**已于《Harvard Data Science Review》6(2), 2024 同行评审发表。** 经典的静默漂移研究：GPT-3.5/4 行为在 2023 年 3→6 月间显著变化；主张对不透明的托管模型**持续监控**。[arXiv:2307.09009](https://arxiv.org/abs/2307.09009) · [HDSR](https://hdsr.mitpress.mit.edu/pub/y95zitmz)
- 经典漂移根源（LLM 之前，用于框定）：**ADWIN**（Bifet & Gavaldà, SDM 2007）、**STEPD**（Nishida & Yamauchi, 2007）。

### 3.3 可观测/追踪/溯源（新兴，多为 2025–2026）
- **TRAIL：Trace Reasoning and Agentic Issue Localization** — Patronus AI, 2025。错误分类法 + 148 条标注 agent trace；最强 LLM 在 trace 中定位错误也只得分 ~11%。[arXiv:2505.08638](https://arxiv.org/abs/2505.08638)
- **From Agent Traces to Trust：执行溯源综述** — 2026。最严谨的「框定该领域」的综述，但以*溯源/可信*而非「可观测性」为框架。[arXiv:2606.04990](https://arxiv.org/abs/2606.04990)
- **A Survey on Evaluation of LLM-based Agents** — Yehudai 等，2025/26。§6 评述了可观测*框架*（LangSmith、Langfuse、Vertex、OTel）。[arXiv:2503.16416](https://arxiv.org/abs/2503.16416)
- ⚠️ **AI Observability for LLM Systems：多层分析** — 2026。*唯一*明确提出「AI 可观测性」分类法（5 层）的预印本——但**单作者、未经同行评审**；当作一种综述，而非共识。[arXiv:2604.26152](https://arxiv.org/abs/2604.26152)

### 3.4 本清单为什么要维护一份中转观察名单——测量研究
这些是 [社区中转观察名单](../README.zh-CN.md#社区中转避雷观察名单) 与 [`canary_check.py`](../scripts/canary_check.py) 的学术依据：
- **Real Money, Fake Models：影子 API 里的欺骗性模型宣称** — 2026。首个对「官方 vs 转售影子 API」的系统性审计；发现巨大的质量/安全落差（如某模型 MedQA 准确率从官方 ~83.8% 掉到影子 API 上 ~37%）。[arXiv:2603.01919](https://arxiv.org/abs/2603.01919)
- **Your Agent Is Mine：测量 LLM 供应链上的恶意中间人攻击** — UC Santa Barbara, 2026。首个把恶意路由/中转当作攻击面的系统研究（投毒注入、密钥外泄）；测了 28 个付费 + 400 个免费路由。[arXiv:2604.08407](https://arxiv.org/abs/2604.08407)
- **你的「Pro」订阅可能其实是「Free」：LLM 推理服务里的指纹伪冒风险** — 2026。展示恶意供应商可服务一个更弱的模型却*规避*用户侧指纹（攻击 PoC，非现场普查）。[arXiv:2606.16100](https://arxiv.org/abs/2606.16100)

*（均为 2026 预印本；ID/标题已在 arXiv 核实，实证宣称取自摘要、未经独立审计。）*

### 3.5 实战检测——借鉴经典的概念漂移检测

漂移论文（§3.2）与转售测量论文（§3.4）指向同一个运维问题：*这个端点背后的模型还是它声称的那个吗？* 有两条方法谱系，而第一条正是值得借鉴的经典传统：

**经典概念漂移检测**（ML 监控谱系）：
- 对 输入/输出/质量分 在滚动窗口上做**分布检验**——**PSI**（总体稳定性指数）、**KS**（柯尔莫哥洛夫–斯米尔诺夫）、**embedding 质心/余弦漂移**：便宜、无监督，抓*渐变*。
- **序贯变点检测**——**ADWIN**（自适应窗口；Bifet & Gavaldà 2007）、**DDM/EDDM**、**Page–Hinkley**：在误差/质量流里报突变；就是为「世界在我脚下变了」设计的。

**LLM 网关专属**（转售研究 + 本项目工具补充的）：
- **黄金集 canary 回归**——把一组固定的判别性 prompt 同时走端点*和*同模型的可信参照，再 diff 输出；相似度下降即换模型/降智的信号。这正是 [`canary_check.py`](../scripts/canary_check.py) 做的。
- **模型指纹**——比对 `system_fingerprint`、相同 prompt 下的 `prompt_tokens`/tokenizer 足迹，以及主动行为指纹（LLMmap 式）。⚠️ **研究给出的局限：** [指纹伪冒论文（§3.4）](https://arxiv.org/abs/2606.16100) 表明恶意供应商能*规避*指纹——所以指纹通过是*必要而非充分*；要配合输出 diff 并随时间重复。
- **记录解析后的模型**——只要记下 `gen_ai.response.model`（§5），供应商改路由（`gpt-4` → 更便宜的变体）无需任何测试即可见。

**诚实的局限（接 §7.11）：** 生产无 ground truth，所以以上每一种都是*估计量*。真正管用的纪律：**钉住一个可信参照、持续抽样、对*变化*告警——而非对某个绝对分数。** 这正是经典漂移检测的思路，用在你租来的黑盒上。

---

## 4. 各公司发表了什么（「扒下来」）

### OpenAI
- **`openai/evals`** — 开源评测框架（ground-truth + 模型评分）。[GitHub](https://github.com/openai/evals)
- **Agents SDK — Tracing** — 默认开启的运行追踪（LLM 调用、工具、交接、护栏），可经 OTel 导出。[文档](https://openai.github.io/openai-agents-python/tracing/)
- **评测最佳实践** — *「评测驱动开发：尽早且频繁评测」*，从日志里挖评测用例。[文档](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- **Model Spec** — 定义期望行为；配套 Model-Spec **evals**。[model-spec.openai.com](https://model-spec.openai.com/)

### Anthropic（该主题上*工程+研究*写作最强的一家）
- **Building Effective Agents**（2024-12）——奠基；*「成功的关键是度量表现并迭代」*（但偏部署前测试，无专门可观测章节）。[链接](https://www.anthropic.com/research/building-effective-agents)
- **Demystifying evals for AI agents**（2026）——直击主题：Agent 更难评（多步、外部状态）；轨迹 vs 结果指标、评审标定、evals-as-CI。[链接](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **A statistical approach to model evals**（2024-11）——评测即实验；要报**误差棒/置信区间**。[链接](https://www.anthropic.com/research/statistical-approach-to-model-evals) · [arXiv:2411.00640](https://arxiv.org/abs/2411.00640)
- **Auditing language models for hidden objectives**（2025-03）——**可解释性即监控/审计工具**：稀疏自编码器能挖出行为搜索看不到的隐藏概念。[链接](https://www.anthropic.com/research/auditing-hidden-objectives)

### OpenRouter
*诚实标注：产品文档很强，但**几乎没有可观测性工程文章**（其博客是产品/融资公告）。* 它的贡献是**面本身**：[用量记账](https://openrouter.ai/docs/cookbook/administration/usage-accounting)（每次响应带 token/成本/时延）、[用量/成本导出](https://openrouter.ai/docs/cookbook/administration/activity-export)、[延迟/性能指南](https://openrouter.ai/docs/guides/best-practices/latency-and-performance)。

### 云平台
- **Google Vertex AI — Gen AI 评测服务**（模型评分 + 计算指标、Agent/轨迹评测）。[文档](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/run-evaluation)
- **Microsoft Azure AI Foundry — 可观测性 / Agent 追踪**（OTel + Azure Monitor；LangChain/LangGraph/OpenAI-Agents-SDK；trace 留存 90 天）。[概念](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability)；Semantic Kernel 按 GenAI 约定发 OTel。
- **AWS Bedrock + CloudWatch** — 模型调用日志 + GenAI 可观测视图（调用数、token、错误）。[博客](https://aws.amazon.com/blogs/mt/monitoring-generative-ai-applications-using-amazon-bedrock-and-amazon-cloudwatch-integration/)

### 塑造该领域的厂商奠基文
- **Honeycomb / Charity Majors** — 《LLMs Demand Observability-Driven Development》（2023-10）：LLM 是非确定性黑盒——在生产里上线 + 观测、再回灌。[链接](https://www.honeycomb.io/blog/llms-demand-observability-driven-development) · 以及《Observability Manifesto》。
- **Arize** — 推广了*「ML 可观测性」*；**Phoenix**（开源 AI 可观测 + 评测，OpenInference 埋点）。[Phoenix](https://github.com/Arize-ai/phoenix)
- **Langfuse**（开源 LLM 工程平台，OTel 原生）[GitHub](https://github.com/langfuse/langfuse) · **Helicone**（代理式开源可观测）[GitHub](https://github.com/Helicone/helicone) · **Datadog LLM Observability**（2024-06 GA） · **LangSmith**（LangChain） · **W&B Weave**。

---

## 5. 标准

**事实上的跨厂商标准是 [OpenTelemetry GenAI 语义约定](https://github.com/open-telemetry/semantic-conventions-genai)**——`gen_ai.*` span（operation.name、provider.name、request/response.model、finish_reasons）与指标（**Required** 的 `gen_ai.client.operation.duration`、`gen_ai.client.token.usage` 直方图、流式 TTFT），且**内容留存默认关闭**（`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`）。由 OTel GenAI SIG 自 ~2024 推进；**OpenLLMetry/Traceloop** 的约定被上游合并。**状态告诫：2026 年多数 `gen_ai.*` 属性仍是 “Development”（非 Stable）**——今天做的埋点有返工风险；固定 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`。互补的还有：**OpenInference**（Arize）、**OpenLLMetry**（Traceloop）。已被 Datadog/Honeycomb/Grafana 原生消费。*（要验证的具体信号见 [BENCHMARKS → 第六部分](../BENCHMARKS.zh-CN.md#第六部分--网关可观测性真正该看的因素)。）*

**治理、沿革与开放争论。** OTel **GenAI SIG** 于 **2024 年 4 月**成立（隶属语义约定 SIG，CNCF / Linux 基金会）；Traceloop 的 **OpenLLMetry**（2023）是早期推动者，其约定被上游合并、成为官方 `gen_ai.*` 命名空间的种子。**2026 年年中**整套 `gen_ai.*` 在主 semconv 仓库被弃用、**迁到专门的 [`semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai) 仓库**（用 Weaver 管理）。两个进行中的争论：
- **约定频繁变动 / 版本固定。** v1.36 → v1.37 带来*破坏性*变更，所以规则是埋点**不得静默改变它发出的约定版本**；`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 是显式切到最新（并丢弃 ≤1.36 形态）的开关。弃用 `gen_ai.prompt`/`gen_ai.completion` 曾打断下游工具——是真实变动，不是假设。
- **OpenInference（Arize）↔ `gen_ai.*` 融合。** OpenInference *早于* OTel 命名空间（2023），带 AI 专属 span 种类（LLM/Tool/Agent/Retriever 等）。这不是地盘之争：2026 年 OpenInference 埋点**同时发出**自家与 `gen_ai.*` 属性——两者正在合并。可这样框定：*「OTel 定义遥测怎么成形/传输；OpenInference 与 `gen_ai.*` 定义其中的 AI 专属载荷。」*

*截至 2026 年 6 月**尚无 GenAI 指标 Stable**——唯一 **Required** 的信号是 `gen_ai.client.operation.duration`；token 用量与 TTFT 为 Recommended，均仍 “Development”。*

> 📌 *标准变化快——多数 `gen_ai.*` 属性仍是 “Development”，做看板前请到 [OTel GenAI 约定仓库](https://github.com/open-telemetry/semantic-conventions-genai) 复核当前稳定性。工具全景见下方 §6。*

---

## 6. 工具（分类法）

按功能（OSS = 开源；⊟ = 托管/商业）。很多已在 [清单的可观测章节](../README.zh-CN.md#-可观测与成本核算)：

- **通用 LLM 可观测 / 追踪：** Langfuse(OSS)、Arize **Phoenix**(OSS)、**Helicone**(OSS, 代理)、LangSmith(⊟)、**Pydantic Logfire**(OTel 原生)、Honeycomb(⊟)、**Datadog LLM Observability**(⊟)、W&B **Weave**(OSS)、**OpenLLMetry/Traceloop**(OSS 埋点)、**OpenLIT**(OSS, OTel 原生 + GPU 监控；可埋点编码 Agent)、**MLflow Tracing**(OSS, 经典 MLOps 工具跨界 LLM-obs，实现 OTel GenAI 约定)、**TruLens**(OSS, RAG 三元组评测/追踪)。
- **漂移 / 安全 / 偏监控类：** Arize、**Fiddler AI**(⊟；发表过清晰的「OTel 到哪为止」分析)、**Guardrails AI**(OSS, 输出校验)、**Maxim AI**(⊟, Bifrost 背后的评测/可观测平台)、**Confident AI**(⊟, DeepEval 背后)。
- **评测 / 质量：** **Braintrust**(⊟)、Phoenix evals(OSS)、**DeepEval**(OSS)、**Ragas**(OSS)、**OpenAI Evals**(OSS)、**promptfoo**(OSS)。
- **网关原生可观测：** **LiteLLM**（Prometheus 指标 + Grafana——自托管参考标签集）、**Portkey**（OTLP 导出 + 预算 + 缓存/护栏遥测）、**Kong AI Gateway**（`gen_ai.*` span 映射 + PII 清洗）、**Cloudflare AI Gateway**（消费上限 + DLP/PII 扫描）、**Bifrost**、**vLLora**（前 LangDB）。
- **2026 洗牌（需留意）：** **Helicone → Mintlify**（2026-03，维护态）、**Portkey → Palo Alto Networks**（2026-05-29 完成，并入 Prisma AIRS）、**TensorZero 归档**（仓库 2026-06-12 只读）、**promptfoo → OpenAI**（2026-03）、以及 **LiteLLM 的 PyPI 供应链投毒**（v1.82.7/.8，2026-03-24）——独立可观测的洗牌*与*供应链风险，正是为什么**开放导出/不锁定** + 版本固定（Part 6 必备项）很重要。

---

## 7. 开放问题 / 进行中的争论

1. **LLM 评审的效度与循环论证** — 评审有位置/冗长/自我偏好偏差，可能*可靠但无效*；而用来验证评审的基准本身又依赖人工标注（循环）。[综述](https://arxiv.org/abs/2411.15594)
2. **可观测 ↔ 评测 的边界** — 有些打分需要网关没有的上下文（领域 ground truth、业务结果），把评测推向应用层；没有公认的界。
3. **静默漂移 / 改路由** — 厂商不改版本号就更新权重/过滤器（「'GPT-4' 一直是好几个模型」）；没有公认检测器——提议信号：PSI/KS、embedding 质心漂移、畸形输出尖峰、对固定端点的黄金集回归。
4. **非确定性与可复现** — 即便 temp 0 + 固定 seed，输出仍不同；根因是浮点非结合 + **批次相关的 kernel**，而不仅是采样——破坏可复现调试。
5. **Agent / 多步 trace 复杂度** — 一次 agent 运行可在几十个嵌套 span 里吐出 MB 级数据；压垮存储、查询与人的理解。
6. **高基数 + 可观测性成本** — 在每个 span 存完整 prompt/响应，成本可与生产相当；采样？截断？全存？未解。
7. **prompt/PII 隐私 vs 合规** — prompt/completion（最有价值的 trace 数据）含 PII；而**欧盟 AI 法案 Art. 12 *强制***高风险系统记录事件日志（留存 ≥6 月；**2026-08-02 生效**）——「为合规而记录」与「最小化 PII」直接冲突。[Art. 12](https://artificialintelligenceact.eu/article/12/)
8. **标准不成熟与频繁变动** — OTel GenAI 约定明确「积极开发中」。
9. **「质量到底是什么」** — 没有公认的操作化定义；无参考打分器衡量的是逐应用的代理指标，而非一套度量理论。
10. **在线 vs 离线评测** — 离线（黄金集）会偏离生产实况；在线只在用户撞上后才发现漂移；如何加权未定。
11. **生产无 ground truth** — 实时流量没有参考答案，质量只能用噪声大的 LLM 评审/无参考方法估计，并需对稀疏人工标注做标定——这是 #1、#9、#10 之下的根本缺口。

---

## 8. 与*本项目*的映射

- **[BENCHMARKS 第六部分](../BENCHMARKS.zh-CN.md#第六部分--网关可观测性真正该看的因素)** = 实操评估**评分表**（必备 → 进阶），依据 §5 的标准。
- **[中转观察名单](../README.zh-CN.md#社区中转避雷观察名单) + [`canary_check.py`](../scripts/canary_check.py)** = 本项目对 §3.4「假模型」测量论文的*操作性回应*——你能自己跑的保真/身份监控。
- **[可复现成本基准](../BENCHMARKS.zh-CN.md)** = 把成本/用量信号（§1.1, L1）做成透明、可复跑的形式。

---

*欢迎通过 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充。这是一份活的综述——领域年轻、变化快，每条都标了日期与来源，方便你自己复核。*
