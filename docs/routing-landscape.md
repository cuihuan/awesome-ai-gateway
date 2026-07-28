# AI-Gateway Routing & Model Selection — Research Landscape, Theory & Open Problems

*A curated, honestly-sourced survey. Last reviewed **2026-07-23**. Part of [Awesome AI Gateway](../README.md).*

This is the **map of the field** behind the [🧠 Smart routing & model selection](../README.md#-smart-routing--model-selection) section: the theory routing borrows from, how mature it actually is, the seminal papers and company writing, the evaluation benchmarks, and the problems still open. Where the section lists the *tools*, this doc is the *why and where-from* — read it before you trust any router's "we cut cost 70%" claim, because most of those numbers come from the papers below, measured on one benchmark that may not be yours.

> **Honesty up front.** Unlike LLM *observability* (which is barely an academic field yet — see the [sibling survey](observability-landscape.md)), **LLM routing has a real, peer-reviewed literature**: cost-aware cascades, learned query routers, and multi-model ensembling each have canonical papers with reproducible benchmarks. But two caveats run through all of it. (1) **Almost every headline cost/quality number is benchmark-specific** — a router tuned on RouterBench or MT-Bench can lose its edge on your traffic; the gains rarely transfer unchanged. (2) **A large share of "routing" in production is not learned at all** — it's static rules (by task, by header, by cost tier), and a recent enterprise survey finds buyers often just [move to the single best model rather than route for savings](https://menlovc.com/perspective/2025-mid-year-llm-market-update/). We flag *peer-reviewed* vs *vendor/industry* vs *our own synthesis* throughout, and every claim is dated and linked so you can re-check it.

---

## 1. The theory it borrows from (classical ML → LLM routing)

### 1.1 The premise: no single model dominates on cost *and* quality
Routing only makes sense because the frontier is a **Pareto front**, not a point: the cheapest model that can handle an *easy* prompt is 10–100× cheaper than the flagship you'd need for a *hard* one (this list's own [cost tables](../BENCHMARKS.md) put the same 100K-token report at **$0.03 vs $3.01** — a 106× spread). If one model were best at everything you'd hard-wire it and routing would be pointless. The empirical basis: real gateway traffic shows **quality — not price — drives model switching**, and the "best" model turns over rapidly ([the 100T-token study](https://arxiv.org/abs/2601.10088)). Routing is the operational bet that *per-prompt* model choice beats *per-application* model choice.

### 1.2 Cascades & learning to defer (the deepest root)
The cascade — *try a cheap model, escalate only if a confidence/quality signal says to* — descends from two classical ideas:
- **Selective prediction / reject option** (Chow, 1970; El-Yaniv & Wiener, 2010): a classifier may *abstain* when unsure, trading coverage for accuracy. An LLM cascade's "escalate to the big model" is exactly a reject-and-defer.
- **Learning to defer / learning with a rejector** (Cortes, DeSalvo & Mohri, 2016; Mozannar & Sontag, 2020): formalizes *when to hand off to a more expensive expert*. The LLM cascade is this with "expert = flagship model" under a cost budget.

The open hard part is the **deferral signal**: self-reported confidence is miscalibrated, so cascades reach for verifier models, answer-consistency, or a learned meta-model — and there's a peer-reviewed result showing plain confidence-thresholding is *provably* not enough in the general case (§3.1).

### 1.3 Ensembling & mixture-of-experts (the other lineage)
Where cascades pick *one* model, **ensembling** combines *several*. This borrows from classical bagging/boosting/stacking and from **Mixture-of-Experts** (Jacobs et al., 1991; Shazeer et al., 2017): a **gating function** routes to (or blends) experts. The 2024–26 twist is that the "experts" are whole frontier LLMs from *different vendors*, combined at the API layer — the "use several models together to beat any one of them" pattern (§3.3). The cost is real: an ensemble that queries N models pays ~N× per prompt, so it only wins where quality is worth more than tokens — and a 2025 result argues that mixing *different* models often loses to sampling the single best one (§3.3, Self-MoA).

### 1.4 The economics that make routing rational
Routing is a response to a price structure, not a fashion:
- **Inference prices fall fast but unevenly** — the price of a *fixed capability level* drops ~9×–900×/year (median ~50×; [Epoch AI](../README.md#-essential-reading)), so yesterday's flagship task is today's budget route.
- **The live price spread is >400×** across the model market ([aipricing.guru snapshot](../README.md#-latest-evaluations)); every prompt sent to a model stronger than it needs is money set on fire.
- **Multi-model is already the default** — >70% of production orgs run 3+ models, 44% route by task type, 11% by cost ([Datadog / Amplify](../README.md#-latest-evaluations)). Routing is the mechanism that turns "we use many models" into "we spend the least on each."

---

## 2. A maturity tiering for LLM routing

*Our proposed synthesis (not an industry standard). Tiers are **cumulative sophistication**, not a strict quality order — a well-tuned L1 rule often beats a poorly-generalizing L3 learned router on real traffic. Each tier up adds decision latency, a training/data dependency, and a new failure mode.*

| Tier | How it decides | What it buys | Cost / risk added |
|---|---|---|---|
| **L0 — Static / manual** | One model, or a human-set default | Simplicity; zero routing overhead | Leaves the whole price spread on the table |
| **L1 — Heuristic rules** | Regex/length/task-tag/header rules ("code → model A, chat → model B") | Cheap, transparent, no training data; most production "routing" is here | Brittle; humans maintain the rules as models change |
| **L2 — Learned predictive router** | A trained classifier scores prompt difficulty and picks cheap-vs-strong *before* generating | Per-prompt cost/quality optimization at one forward pass of overhead | Needs training data; **generalization gap** — tuned on one benchmark, deployed on another |
| **L3 — Cascade / deferral** | Generate cheap first; a confidence/verifier signal escalates only hard cases | Pays the big model only when needed; often the best cost/quality point in practice | Extra latency on escalated prompts; the deferral signal is hard to calibrate |
| **L4 — Ensemble / mixture + online-adaptive** | Query several models and aggregate (MoA), or adapt routing weights online from feedback | Can exceed *any single model's* quality; adapts to drift | ~N× token cost; complexity; aggregation can amplify a shared error |

Most teams in 2026 sit at **L1**, with **L2/L3** where the differentiated routers compete and **L4** reserved for quality-critical, cost-insensitive workloads.

---

## 3. The research landscape (the papers)

> **How to read these numbers:** every "X% cost saving at Y% of GPT-4 quality" below is **measured on a specific benchmark** (RouterBench, MT-Bench, MMLU, GSM8K…). Treat them as *existence proofs that routing can work*, not as a spec sheet for your traffic. The one reliable way to know your number is to A/B the router against your own eval set.

### 3.1 Cost-aware routing & cascades
- [FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance](https://arxiv.org/abs/2305.05176) — Chen, Zaharia & Zou (Stanford), arXiv 2023 — Introduces the LLM cascade: query cheaper models first and escalate to costlier ones only when a learned scoring function judges the current answer unreliable, reporting matching GPT-4 accuracy at up to 98% lower cost on the authors' benchmarks.
- [AutoMix: Automatically Mixing Language Models](https://arxiv.org/abs/2310.12963) — Aggarwal, Madaan et al., arXiv 2023 (NeurIPS 2024) — Routes queries from a smaller to a larger LM using few-shot self-verification plus a POMDP-based meta-verifier to decide when to escalate, cutting compute cost by over 50% at comparable accuracy.
- [Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing](https://arxiv.org/abs/2404.14618) — Ding et al., Microsoft/UBC, ICLR 2024 — Trains a router that sends each query to a small or large model by predicted quality gap and a tunable threshold, cutting large-model calls by up to 40% while preserving response quality.
- [When Does Confidence-Based Cascade Deferral Suffice?](https://arxiv.org/abs/2307.02764) — Jitkrittum, Gupta, Menon et al. (Google Research), NeurIPS 2023 — Shows simple confidence-based cascade deferral is provably suboptimal under specialist downstream models, label noise, or distribution shift, where post-hoc deferral rules do better — the theory behind why the escalation signal is the hard part.
- [Language Model Cascades](https://arxiv.org/abs/2207.10342) — Dohan, Xu, Lewkowycz et al. (Google), arXiv 2022 — Formalizes scratchpads, verifiers, STaR, selection-inference and tool use as probabilistic programs that compose multiple LM calls — the unifying framing behind verifier- and selection-based cascades.

### 3.2 Learned predictive routers
- [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665) — Ong et al., UC Berkeley/Anyscale (LMSYS), arXiv 2024 — Trains routers from human preference data to send each query to a strong or weak model, cutting cost over 2× at matched quality while transferring to unseen model pairs; the canonical open router paper.
- [RouteLLM: An Open-Source Framework for Cost-Effective LLM Routing](https://lmsys.org/blog/2024-07-01-routellm/) — LMSYS Org, blog 2024 — The companion release: an open router with an OpenAI-compatible server that cut cost ~85%/45%/35% on MT-Bench/MMLU/GSM8K while holding ~95% of GPT-4 quality.
- [Routing to the Expert: Efficient Reward-guided Ensemble of Large Language Models (Zooter)](https://arxiv.org/abs/2311.08692) — Lu et al., Alibaba, arXiv 2023 — Distills reward-model supervision into a query router that dispatches each prompt to the best of several expert LLMs, beating the best single model across 26 task subsets.
- [RouterDC: Query-Based Router by Dual Contrastive Learning for Assembling Large Language Models](https://arxiv.org/abs/2409.19886) — Chen et al. (HKUST / SUSTech), NeurIPS 2024 — Trains a query encoder plus per-LLM embeddings with dual contrastive losses to pick the best model per query, with gains on in- and out-of-distribution tasks over single models and prior routers.
- [GraphRouter: A Graph-based Router for LLM Selections](https://arxiv.org/abs/2410.03834) — Feng, Shen & You (UIUC), arXiv 2024 — Frames model selection as edge prediction over a task-query-LLM heterogeneous graph, generalizing to newly added LLMs without retraining the router.
- [Universal Model Routing for Efficient LLM Inference](https://arxiv.org/abs/2502.08773) — Jitkrittum et al., Google Research, arXiv 2025 — Represents each LLM by feature vectors from its predictions on representative prompts so one router generalizes to 30+ LLMs unseen at training time, with excess-risk bounds.
- [TensorOpera Router: A Multi-Model Router for Efficient LLM Inference](https://arxiv.org/abs/2408.12320) — Stripelis et al., TensorOpera, EMNLP 2024 (Industry) — Integrates multiple LLM experts behind one interface and dynamically routes each query to the best-suited model, reporting up to 40% efficiency and 30% cost gains while maintaining quality.

### 3.3 Ensembling / mixture / multi-model collaboration
*The "combine several models to beat any single one" cluster — and the honest counter-evidence that it doesn't always pay.*
- [Mixture-of-Agents Enhances Large Language Model Capabilities](https://arxiv.org/abs/2406.04692) — Wang et al. (Together AI, Duke, Stanford), arXiv 2024 — Layers multiple open-source LLMs as proposers then aggregators, reaching 65.1% on AlpacaEval 2.0 vs GPT-4o's 57.5% — at the cost of several extra forward passes per query.
- [Together MoA — collective intelligence of open-source models](https://www.together.ai/blog/together-moa) — Together AI, blog 2024 — The vendor writeup of MoA: tunable proposers, aggregators and number of layers, trading slower time-to-first-token for higher accuracy.
- [LLM-Blender: Ensembling Large Language Models with Pairwise Ranking and Generative Fusion](https://arxiv.org/abs/2306.02561) — Jiang, Ren & Lin (USC, AI2), ACL 2023 — PairRanker selects the best per-query candidate via pairwise cross-attention comparison and GenFuser merges the top outputs; the foundational LLM-ensembling paper.
- [Fusing Models with Complementary Expertise](https://arxiv.org/abs/2310.01542) — Wang et al., MIT-IBM Watson AI Lab, ICLR 2024 — Casts combining complementary domain-expert models' outputs as a supervised fusion problem, with a frugal variant that queries fewer experts per input.
- [More Agents Is All You Need](https://arxiv.org/abs/2402.05120) — Li et al. (Tencent), arXiv 2024 — Sampling many independent responses from a *single* LLM and majority-voting scales accuracy with the sample count — a useful single-model baseline to beat before adopting multi-model ensembling.
- [Rethinking Mixture-of-Agents: Is Mixing Different LLMs Beneficial? (Self-MoA)](https://arxiv.org/abs/2502.00674) — Li et al., Princeton, arXiv 2025 — The counterpoint: aggregating multiple samples from the *single best* model (Self-MoA) often beats mixing different LLMs, because a mixture's quality is dragged down by the weaker models in it. Read this before you assume more models = better.

### 3.4 Self-routing / self-selection
*Approaches where the model itself decides whether to answer or defer/escalate — the self-selection idea: the routing signal comes from the model's own self-assessment, not an external classifier.*
- [Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach (Self-Route)](https://arxiv.org/abs/2407.16833) — Li et al., Google, EMNLP 2024 — Self-Route sends each query to cheap RAG first and falls back to full long-context only when the model *self-reflects* that the retrieved context is insufficient, cutting cost ~65% (Gemini-1.5-Pro) / ~39% (GPT-4o) at comparable quality.
- [Learning to Route LLMs with Confidence Tokens](https://arxiv.org/abs/2410.13284) — Chuang et al., arXiv 2024 — Trains LLMs to emit calibrated confidence tokens (Self-REF) that a router uses to accept, reject, or defer to another expert — outperforming verbalized-confidence and raw token-probability baselines.
- [OrchestraLLM: Efficient Orchestration of Language Models for Dialogue State Tracking](https://arxiv.org/abs/2311.09758) — Lee, Cheng & Ostendorf (UW / Microsoft Research), NAACL 2024 — Routes each dialogue turn between a small and a large LLM via kNN retrieval over labeled exemplar pools (no trained router), cutting compute over 50% while improving accuracy.

### 3.5 Benchmarks & evaluation of routers
- [RouterBench: A Benchmark for Multi-LLM Routing System](https://arxiv.org/abs/2403.12031) — Martian (withmartian), arXiv 2024 — The first large-scale routing benchmark: 405k inference outcomes plus a theoretical framework for comparing routers on the cost-quality frontier.
- [RouterArena: An Open Platform for Comprehensive Comparison of LLM Routers](https://arxiv.org/abs/2510.00202) — Lu et al. (RouteWorks), arXiv 2025 — Open evaluation platform + [live leaderboard](https://github.com/RouteWorks/RouterArena) benchmarking open-source and commercial routers across 9 domains / 44 categories on five metrics (accuracy, cost, optimality, robustness, latency).
- [RouterEval: A Benchmark for Routing LLMs to Explore Model-level Scaling Up](https://arxiv.org/abs/2503.10657) — Huang et al., EMNLP 2025 Findings — An offline router benchmark with 200M+ precomputed performance records over 8,500+ LLMs, surfacing a "model-level scaling" effect where stronger routers gain more as the candidate pool grows.

### 3.6 Surveys & the economics
- [Doing More with Less: A Survey on Routing Strategies for Resource Optimisation in LLM-Based Systems](https://arxiv.org/abs/2502.00409) — Varangot-Reille et al., arXiv 2025 — Taxonomizes query-routing methods (similarity-based, supervised, RL, generative) and frames when routing to smaller/specialised models improves the cost/quality/latency tradeoff.
- [Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey](https://arxiv.org/abs/2603.04445) — Moslem & Kelleher (ADAPT Centre, Trinity College Dublin; Huawei Ireland), arXiv 2026 — Systematizes routing and cascading at inference time via a framework organized by decision timing, information used, and computation approach.
- The routing *economics primaries* — Epoch AI price trends, the [100T-token study](https://arxiv.org/abs/2601.10088), and the LLM-service outage study (the case for failover) — are curated in [📚 Essential reading → Routing & fallback](../README.md#-essential-reading); this doc doesn't duplicate them.

---

## 4. What the companies have published

### The commercial routers (vendor docs — read for the *interface*, discount the marketing)
- [How OpenRouter Model Routing Works: Providers, Fallbacks & Auto Router](https://openrouter.ai/blog/insights/model-routing/) — OpenRouter, blog 2026 — Two independent routing decisions (which *model* answers vs which *provider* serves it), with provider-level failover, model-level fallback arrays, and an `openrouter/auto` endpoint that picks a model per prompt.
- [Auto Router (Intelligent Model Selection)](https://openrouter.ai/docs/guides/routing/routers/auto-router) — OpenRouter, docs 2026 — Classifies each prompt into ~30 task types, ranks candidate models by trailing 7-day community spend-share, and exposes a cost/quality dial with primary + fallback selection.
- [What is Model Routing?](https://docs.notdiamond.ai/docs/what-is-model-routing) — Not Diamond, docs 2026 — The vendor definition: per-query selection of the best candidate LLM under one of three explicit modes — quality (default), cost, or latency.
- [Introducing RouterBench](https://withmartian.com/post/introducing-routerbench) — Martian, blog 2024 — The company behind RouterBench: the ~405k-outcome benchmark plus the AIQ (area-under-the-cost-quality-curve) metric, with Zero-Router and Oracle-Router baselines.

### Frontier models are becoming routers themselves
- [Introducing GPT-5](https://openai.com/index/introducing-gpt-5/) — OpenAI, blog 2025 — GPT-5 ships as a *unified system* whose real-time router decides per query between a fast model and a deeper reasoning model based on conversation type, complexity, tool needs and explicit intent. The routing layer moved *inside* the model — a reason the "which model?" question is now often "which route within a model?".

### The market data (industry surveys — the counter-evidence too)
- [State of AI: An Empirical 100-Trillion-Token Study with OpenRouter](https://arxiv.org/abs/2601.10088) — OpenRouter + a16z, arXiv 2026 — 100T+ tokens of gateway traffic: open-weight models at ~⅓ of volume, reasoning models over half, and a map of which models developers actually spend on per task type — the primary dataset on real routing behavior.
- [2025 Mid-Year LLM Market Update](https://menlovc.com/perspective/2025-mid-year-llm-market-update/) — Menlo Ventures, 2025 — The honest counterpoint to cost-routing: 66% of enterprise builders upgrade models *within* their existing provider and only 11% switch vendors, favoring frontier models over cheaper tiers — buyers often *don't* route for savings.

### Gateway routing mechanics
The concrete retry/fallback/weighting mechanics you actually configure — **LiteLLM** (routing & load balancing, router architecture) and **Portkey** (load balancing) — are in [📚 Essential reading](../README.md#-essential-reading). Cloud first-party routers (AWS Bedrock, Azure AI Foundry, Vertex) are listed in [🌐 First-party gateways](../README.md#-first-party-gateways-cloud--model-vendors).

---

## 5. Standards & interfaces (or the lack of one)

There is **no routing standard** — worth stating plainly. Routing rides on the **OpenAI-compatible** surface: you either (a) send a real model id and let the *gateway* apply configured rules, or (b) send a **sentinel model id** (`openrouter/auto`, a tier name) and let the provider route. There's no interoperable way to express "route this by cost with a quality floor of X" across gateways, no standard for *reporting which model actually served* a routed request (the closest is OTel GenAI's `gen_ai.response.model` — see the [observability landscape §5](observability-landscape.md#5-standards)), and no standard router-eval protocol beyond the community benchmarks in §3.5. **Practical consequence:** always log the *resolved* model, because a router (or a relay) silently downgrading you is otherwise invisible — the same fidelity problem the [relay watch-list](../README.md#community-relay-watch-list) exists for.

---

## 6. The tools (taxonomy)

The router *tools* live in the list itself — [🧠 Smart routing & model selection](../README.md#-smart-routing--model-selection) — spanning commercial routers (Not Diamond, Martian, OpenRouter Auto, Inworld, Unify), open frameworks (RouteLLM, LLMRouter, vLLM Semantic Router, NVIDIA LLM Router), coding-agent routers (Claude Code Router, ClawRouter, workweave/router, UncommonRoute, NadirClaw), gateway-native routing (Bifrost, Cloudflare, Kong), and the evaluation layer (RouterArena, OrcaRouter). This doc is the theory behind that taxonomy; the section is the buy-list.

---

## 7. Open problems / active debates

1. **Generalization / the benchmark trap** — a router tuned on RouterBench or MT-Bench often loses its cost/quality edge on out-of-distribution traffic. Reported savings rarely transfer unchanged, and there's no accepted way to predict a router's *your-traffic* number without running it (§3.5 exists precisely because of this).
2. **Deferral-signal calibration** — cascades live or die on "is this answer good enough to stop?" Self-reported confidence is miscalibrated, verifier models add cost and their own errors, and plain confidence-thresholding is *provably* insufficient in general ([§3.1](https://arxiv.org/abs/2307.02764)). No cheap, well-calibrated escalation signal is settled.
3. **Does mixing even help?** — MoA-style ensembling assumes the models err *independently* enough that aggregation helps; [Self-MoA](https://arxiv.org/abs/2502.00674) shows mixing weaker models in can *lower* quality vs. sampling the single best. When multi-model beats single-model is unresolved and workload-dependent.
4. **Routing overhead vs savings** — a learned router adds a classify step; an ensemble adds ~N× tokens. For short/cheap prompts the routing cost can exceed the routing savings; the break-even is workload-specific and under-measured.
5. **Non-stationarity** — the models behind a route change under you (new versions, silent re-points, deprecations). A router trained last quarter can be dispatching to a model that no longer behaves the same — routing and [silent-drift detection](observability-landscape.md#32-silent-model-drift-is-gpt-getting-worse) are the same problem wearing two hats.
6. **Privacy / who sees the prompt to route it** — predictive routing reads the prompt *before* choosing a model, so the router (often a third party) sees everything — an added data-exposure surface on top of the gateway itself (see the [data-retention matrix](../README.md#-who-sees-your-prompts--the-data-retention-matrix)).
7. **Quality has no production ground truth** — every routing decision optimizes an *estimate* of quality (a judge, a reward model, a proxy). The router is only as good as that estimator, which is itself noisy — the same limit as the [observability landscape §7](observability-landscape.md#7-open-problems--active-debates).

---

## 8. How this maps to *this* project

- **[🧠 Smart routing & model selection](../README.md#-smart-routing--model-selection)** = the tool buy-list this doc is the theory for.
- **[📊 BENCHMARKS](../BENCHMARKS.md)** = the reproducible cost spread that makes routing rational (§1.1, §1.4) — measured, not asserted.
- **[Community relay watch-list](../README.md#community-relay-watch-list) + [`canary_check.py`](../scripts/canary_check.py)** = the operational answer to §5/§7.5 — verify the model a router *actually* served you.
- **[Observability landscape](observability-landscape.md)** = the sibling survey; routing and drift-detection are two views of the same "is this endpoint still what it claims?" question.

---

*Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues). This is a living survey — the field is young and moving; every claim is dated and sourced so you can re-check it. The numbers are benchmark-specific by nature — always re-measure on your own traffic.*
