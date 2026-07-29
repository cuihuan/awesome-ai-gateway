# AI-Gateway Observability — Research Landscape, Theory & Open Problems

*A curated, honestly-sourced survey. Last reviewed **2026-06-26**. Part of [Awesome AI Gateway](../README.md).*

**Languages:** English · [简体中文](observability-landscape.zh-CN.md)

This is the **map of the field**: the classic theory it borrows from, how mature it actually is, the seminal papers and company writing, the standards and tools, and the problems still open. It complements [BENCHMARKS → Part 6](../BENCHMARKS.md#part-6--gateway-observability-the-factors-that-matter), which is the practical *how-to-evaluate-a-gateway's-observability* rubric. This doc is the *why and where-from*.

> **Honesty up front.** "LLM observability" is **not** a settled academic field. The mature, peer-reviewed literature lives in **evaluation** (LLM-as-judge, eval harnesses) and **model drift**. The operational observability discourse — tracing, telemetry, dashboards — is **overwhelmingly vendor blogs + the OpenTelemetry GenAI conventions**, with only a thin, very recent (2025–2026) academic trickle. Throughout, we flag *peer-reviewed* vs *vendor/industry* vs *our own synthesis*. Anyone selling you a "canonical taxonomy of LLM observability" is overselling — there isn't one yet.

---

## 1. The theory it borrows from (classical observability → LLM gateways)

### 1.1 The "three pillars" — and the critique
The metrics / logs / traces framing was crystallized by **Peter Bourgon** (*"Metrics, tracing, and logging,"* 2017) — less a hierarchy than a distinction by property: **metrics** are *aggregatable* (cheapest), **logs** are *discrete events* (most expensive, often out-volumes the traffic they describe), **traces** are *request-scoped*. [[Bourgon]](https://peter.bourgon.org/blog/2017/02/21/metrics-tracing-and-logging.html)

The pillars became a *vendor frame* and were critiqued by their own originators: **Ben Sigelman** (*"Three Pillars with Zero Answers,"* 2018) — *"metrics, logs and traces are just data — the fuel, not the car"*; observability is **measurement + explanation**, not three siloed tools. [[Lightstep]](https://medium.com/lightstephq/three-pillars-with-zero-answers-2a98b36358b8) **Charity Majors** reframes it as **Observability 1.0 → 2.0**: from many siloed copies of each request to *one source of truth — wide, structured events* from which metrics/traces are derived. [[Honeycomb]](https://www.honeycomb.io/blog/one-key-difference-observability1dot0-2dot0)

**Mapping onto an AI gateway** (our synthesis, grounded in the OTel GenAI conventions in §5):

| Pillar | Classical | AI-gateway analogue |
|---|---|---|
| **Metrics** | latency, RPS, error rate | tokens in/out, **$-cost per request**, time-to-first-token, tokens/sec, cache-hit rate — by model/route/tenant |
| **Logs** | request/error events | the **prompt + completion** themselves — highest-value, highest-risk, highest-volume artifact (see §7 PII) |
| **Traces** | RPC spans across services | **multi-step / agent spans**: `invoke_agent` → child `chat` calls → `execute_tool` calls, with retries, fallbacks, RAG retrievals |

One LLM twist that breaks a classical assumption: **latency and cost correlate with *token counts*, not request count.**

### 1.2 Observability vs monitoring — and why LLMs are the extreme case
The canonical distinction (Majors/Honeycomb): **monitoring** answers *known-unknowns* via pre-built dashboards; **observability** is *"the power to ask new questions of your system without shipping new code"* — the realm of **unknown-unknowns**, enabled by **high cardinality** (group by user/request/session as first-class). [[Honeycomb manifesto]](https://www.honeycomb.io/blog/observability-a-manifesto) An AI gateway is the **extreme** case: every request carries a unique free-text prompt, the output space is unbounded language, and failure is **semantic** (an HTTP 200 with subtly wrong content), so you *cannot pre-enumerate* the failure modes you'll need to query.

### 1.3 SRE SLI/SLO/error-budgets — and the hard new "quality SLO"
From the [Google SRE book](https://sre.google/sre-book/service-level-objectives/): **SLI** (a measure), **SLO** (a target), **error budget** = 1 − SLO. What an AI-gateway SLO looks like (our synthesis):
- **Transplants cleanly:** availability (% non-5xx), latency — but split into **time-to-first-token** (streaming UX) and **total completion** (token-count-dependent, noisier).
- **New but tractable:** a **cost / spend budget** — error-budget logic maps naturally onto dollars.
- **The genuinely hard part:** a **quality SLO**. "Correct" is fuzzy and production has no ground truth, so a quality SLO is defined over a *proxy* ("≥X% of sampled responses pass an LLM-judge rubric") — i.e. **an SLO over a noisy estimator**, a move SRE never had to make.

**Companion frame — the Four Golden Signals.** SRE's other canonical set ([*Monitoring Distributed Systems*](https://sre.google/sre-book/monitoring-distributed-systems/)) is the fastest sanity-check of a gateway's instrumentation:

| Golden signal | Classical | AI-gateway form |
|---|---|---|
| **Latency** | request time | TTFT **and** total completion (token-dependent), per model/route |
| **Traffic** | requests/sec | requests/sec **and tokens/sec** (the real load unit) |
| **Errors** | error rate | **by origin** — provider 4xx/5xx vs gateway vs guardrail vs content-filter (a flat rate is useless) |
| **Saturation** | how "full" the service is | upstream **rate-limit/quota headroom**, budget headroom, and (self-hosted) GPU/queue depth |

### 1.4 Control theory → closed loop
The classical feedback controller (observe output → compare to setpoint → adjust) maps onto **evals → routing/guardrail adjustment**: post-LLM guardrails with self-correction, LLM-judge as both eval and dynamic guardrail. The limit (our synthesis): classical control assumes a *stable plant* and a *measurable error*; an LLM gateway's "plant" (the upstream model) can be **silently re-pointed**, and the error signal (quality) is itself estimated by another LLM — so the loop can chase a miscalibrated setpoint.

---

## 2. A maturity tiering for AI-gateway observability

*Our proposed synthesis (not an industry standard). Tiers are **cumulative capability**, not strict sequence — and each tier up multiplies the cost-of-observability and privacy surface (§7). Higher tier ≠ more trustworthy verdicts, since L3–L4 rest on the noisy LLM-judge estimator.*

| Tier | Capability | What it unlocks |
|---|---|---|
| **L0 — Raw logs** | Prompt/response captured as flat logs | Post-hoc debugging, audit trail (min. for EU AI Act Art. 12) |
| **L1 — Metrics + cost attribution** | Token/latency/cost metrics by model/route/tenant | Budget alerts, latency SLOs, per-tenant chargeback, regression spotting |
| **L2 — Distributed tracing** | OTel GenAI spans across agent/tool/RAG steps | Root-cause multi-step failures, span-level cost/latency attribution |
| **L3 — Online evals: quality + drift** | Sampled LLM-judge / reference-free scoring on live traffic; golden-set regression vs a pinned endpoint; statistical drift (PSI/KS/embedding-centroid) | Quality SLOs, **silent-drift / provider-re-point detection**, unknown-unknown semantic failures |
| **L4 — Closed-loop auto-remediation** | Evals feed back into routing, fallback, guardrail adjustment automatically | Self-correcting responses, auto model-failover on quality regression, adaptive guardrails |

Most teams in 2026 are solidly at **L1**, reaching for **L2**; **L3** is where the differentiated tools compete; **L4** is largely aspirational.

---

## 3. The research landscape (the papers — "扒下来")

> **The honest shape of it:** the *evaluation* and *drift* clusters are genuinely academic, peer-reviewed, heavily cited. The *observability/tracing* cluster is thin and just emerging (2025–2026), arriving via **agent-trace provenance / failure-localization**, not a dedicated "observability" tradition.

### 3.1 Evaluation & LLM-as-judge (the strongest academic cluster)
- **Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena** — Zheng et al., **NeurIPS 2023**. The foundational LLM-as-judge paper: GPT-4 judges match human preference >80%; names **position / verbosity / self-enhancement** biases. [arXiv:2306.05685](https://arxiv.org/abs/2306.05685)
- **Holistic Evaluation of Language Models (HELM)** — Liang, Bommasani, Lee et al. (Stanford CRFM), **TMLR 2023**. Multi-metric holistic eval + living leaderboard. [arXiv:2211.09110](https://arxiv.org/abs/2211.09110)
- **Chatbot Arena** — Chiang, Zheng et al. (LMSYS), **ICML 2024**. Crowdsourced pairwise human-preference Elo; the de-facto in-the-wild eval infra. [arXiv:2403.04132](https://arxiv.org/abs/2403.04132)
- **G-Eval** — Liu et al., **EMNLP 2023**. CoT + form-filling LLM-evaluator; high human correlation, also flags self-bias toward LLM-generated text. [arXiv:2303.16634](https://arxiv.org/abs/2303.16634)
- **lm-evaluation-harness** (EleutherAI) — the standard reproducible eval harness behind the Open LLM Leaderboard. [GitHub](https://github.com/EleutherAI/lm-evaluation-harness)
- **A Survey on LLM-as-a-Judge** — Gu et al., 2024. Reliability strategies + bias mitigation. [arXiv:2411.15594](https://arxiv.org/abs/2411.15594)
- Hallucination signal for production monitoring: **SelfCheckGPT** — Manakul et al., EMNLP 2023. [arXiv:2303.08896](https://arxiv.org/abs/2303.08896)

*The converging documented judge biases: **position** (up to ~75% first-response preference), **self-enhancement** (~10–25%), **verbosity** (longer = preferred).*

### 3.2 Silent model drift ("is GPT getting worse?")
- **How Is ChatGPT's Behavior Changing over Time?** — Chen, Zaharia, Zou (Stanford/Berkeley). arXiv 2307.09009 (2023); **peer-reviewed in Harvard Data Science Review, 6(2), 2024.** The canonical silent-drift study: GPT-3.5/4 behavior shifted substantially Mar→Jun 2023; argues for **continuous monitoring of opaque hosted models**. [arXiv:2307.09009](https://arxiv.org/abs/2307.09009) · [HDSR](https://hdsr.mitpress.mit.edu/pub/y95zitmz)
- Classical drift roots (pre-LLM, for framing): **ADWIN** (Bifet & Gavaldà, SDM 2007), **STEPD** (Nishida & Yamauchi, 2007).

### 3.3 Observability / tracing / provenance (emerging, mostly 2025–2026)
- **TRAIL: Trace Reasoning and Agentic Issue Localization** — Patronus AI, 2025. Error taxonomy + 148 annotated agent traces; the best LLM scores only ~11% at localizing errors in traces. [arXiv:2505.08638](https://arxiv.org/abs/2505.08638)
- **From Agent Traces to Trust: A Survey of Evidence Tracing & Execution Provenance in LLM Agents** — 2026. The most rigorous field-framing survey, but framed as *provenance/trust*, not "observability." [arXiv:2606.04990](https://arxiv.org/abs/2606.04990)
- **A Survey on Evaluation of LLM-based Agents** — Yehudai et al., 2025/26. §6 reviews observability *frameworks* (LangSmith, Langfuse, Vertex, OTel). [arXiv:2503.16416](https://arxiv.org/abs/2503.16416)
- ⚠️ **AI Observability for LLM Systems: A Multi-Layer Analysis** — 2026. The *only* preprint explicitly proposing an "AI observability" taxonomy (5 layers) — but **single-author, not peer-reviewed**; treat as one synthesis, not consensus. [arXiv:2604.26152](https://arxiv.org/abs/2604.26152)

### 3.4 Why this list keeps a relay watch-list — the measurement studies
These are the academic basis for [the community relay watch-list](../README.md#community-relay-watch-list) and [`canary_check.py`](../scripts/canary_check.py):
- **Real Money, Fake Models: Deceptive Model Claims in Shadow APIs** — 2026. First systematic audit of official vs resold "shadow" APIs; finds large quality/safety gaps (e.g. a model's MedQA accuracy dropping ~83.8%→~37% on shadow APIs). [arXiv:2603.01919](https://arxiv.org/abs/2603.01919)
- **Your Agent Is Mine: Measuring Malicious Intermediary Attacks on the LLM Supply Chain** — UC Santa Barbara, 2026. First systematic study of malicious routers/relays as an attack surface (payload injection, secret exfiltration); 28 paid + 400 free routers measured. [arXiv:2604.08407](https://arxiv.org/abs/2604.08407)
- **Your "Pro" LLM Subscription May Actually Be "Free": Fingerprint Spoofing in LLM Inference Services** — 2026. Shows a malicious provider can serve a weaker model that *evades* user-side fingerprinting (an attack PoC, not a field survey). [arXiv:2606.16100](https://arxiv.org/abs/2606.16100)

*(2026 preprints; IDs/titles verified on arXiv, empirical claims are per-abstract, not independently audited.)*

### 3.5 Detecting it in practice — borrowing from classical concept-drift detection

The drift papers (§3.2) and the relay-fraud papers (§3.4) pose one operational question: *is the model behind this endpoint still what it claims?* Two method lineages answer it — and the first is exactly the classical tradition worth borrowing:

**Classical concept-drift detection** (the ML-monitoring lineage):
- **Distribution tests** on inputs / outputs / quality-scores over a rolling window — **PSI** (Population Stability Index), **KS** (Kolmogorov–Smirnov), **embedding-centroid / cosine drift**: cheap, unsupervised, catch *gradual* shift.
- **Sequential change-point detectors** — **ADWIN** (adaptive windowing; Bifet & Gavaldà 2007), **DDM/EDDM**, **Page–Hinkley**: flag an abrupt change in an error/quality stream; built for "the world moved under me."

**LLM-gateway-specific** (what the relay studies + this project's tooling add):
- **Golden-set canary regression** — push a fixed discriminating prompt set through the endpoint *and* a trusted reference for the same model, then diff the outputs; a similarity drop signals a swap/downgrade. This is what [`canary_check.py`](../scripts/canary_check.py) does.
- **Model fingerprinting** — compare `system_fingerprint`, the `prompt_tokens`/tokenizer footprint on identical prompts, and active behavioral fingerprints (LLMmap-style). ⚠️ **Limit from the research:** the [fingerprint-spoofing paper (§3.4)](https://arxiv.org/abs/2606.16100) shows a malicious provider can *evade* fingerprinting — so a passing fingerprint is *necessary, not sufficient*; pair it with output-diff and repeat over time.
- **Resolved-model capture** — simply logging `gen_ai.response.model` (§5) makes a provider re-point (`gpt-4` → a cheaper variant) visible with no test at all.

**The honest limit (ties to §7.11):** production has no ground truth, so every one of these is an *estimator*. The discipline that works: **pin a trusted reference, sample continuously, and alert on *change* — not on an absolute score.** That is precisely the classical drift-detection mindset, applied to a black box you rent.

---

## 4. What the companies have published ("扒下来")

### OpenAI
- **`openai/evals`** — open eval framework (ground-truth + model-graded). [GitHub](https://github.com/openai/evals)
- **Agents SDK — Tracing** — on-by-default run tracing (LLM calls, tools, handoffs, guardrails), exportable via OTel. [docs](https://openai.github.io/openai-agents-python/tracing/)
- **Evaluation best practices** — *"eval-driven development: evaluate early and often,"* mine logs for eval cases. [docs](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- **Model Spec** — defines intended behavior; complemented by Model-Spec **evals**. [model-spec.openai.com](https://model-spec.openai.com/)

### Anthropic (the strongest *engineering+research* writing on the topic)
- **Building Effective Agents** (Dec 2024) — foundational; *"the key to success is measuring performance and iterating"* (but pre-deployment-testing focused, no dedicated obs section). [link](https://www.anthropic.com/research/building-effective-agents)
- **Demystifying evals for AI agents** (2026) — directly on the topic: agents are harder to eval (multi-step, external state); trajectory-vs-outcome metrics, judge calibration, evals-as-CI. [link](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **A statistical approach to model evals** (Nov 2024) — evals are experiments; report **error bars / confidence intervals**. [link](https://www.anthropic.com/research/statistical-approach-to-model-evals) · [arXiv:2411.00640](https://arxiv.org/abs/2411.00640)
- **Auditing language models for hidden objectives** (Mar 2025) — **interpretability as a monitoring/auditing tool**: sparse autoencoders surface concealed concepts behavioral search misses. [link](https://www.anthropic.com/research/auditing-hidden-objectives)

### OpenRouter
*Honest note: strong product docs, **essentially no observability engineering essays** (its blog is product/funding announcements).* Its contribution is the **surface itself**: [Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) (per-response token/cost/timing), an [activity export for cost analytics](https://openrouter.ai/docs/cookbook/administration/activity-export), and a [latency/performance guide](https://openrouter.ai/docs/guides/best-practices/latency-and-performance).

### Cloud platforms
- **Google Vertex AI — Gen AI evaluation service** (model-based + computed metrics, agent/trajectory eval). [docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/run-evaluation)
- **Microsoft Azure AI Foundry — Observability / Agent tracing** (OTel + Azure Monitor; LangChain/LangGraph/OpenAI-Agents-SDK; 90-day trace retention). [concept](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability) · Semantic Kernel emits OTel following the GenAI conventions.
- **AWS Bedrock + CloudWatch** — model-invocation logging + GenAI observability views (invocations, tokens, errors). [blog](https://aws.amazon.com/blogs/mt/monitoring-generative-ai-applications-using-amazon-bedrock-and-amazon-cloudwatch-integration/)

### The vendor-foundational pieces that shaped the field
- **Honeycomb / Charity Majors** — *"LLMs Demand Observability-Driven Development"* (Oct 2023): LLMs are nondeterministic black boxes — ship + observe in prod, loop back. [link](https://www.honeycomb.io/blog/llms-demand-observability-driven-development) · plus the *Observability Manifesto*.
- **Arize** — popularized *"ML observability"*; **Phoenix** (OSS AI observability + evals, OpenInference-instrumented). [Phoenix](https://github.com/Arize-ai/phoenix)
- **Langfuse** (OSS LLM engineering platform; OTel-native). [GitHub](https://github.com/langfuse/langfuse) · **Helicone** (proxy-based OSS obs). [GitHub](https://github.com/Helicone/helicone) · **Datadog LLM Observability** (GA Jun 2024). · **LangSmith** (LangChain) · **W&B Weave**.

---

## 5. Standards

The **de-facto cross-vendor standard is the [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)** — `gen_ai.*` spans (operation.name, provider.name, request/response.model, finish_reasons) and metrics (the **Required** `gen_ai.client.operation.duration`, the `gen_ai.client.token.usage` histogram, streaming TTFT), with **content capture OFF by default** (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`). Driven by the OTel GenAI SIG since ~2024; conventions originally from **OpenLLMetry/Traceloop** were upstreamed. **Status caveat: most `gen_ai.*` attributes are still "Development" (not Stable) in 2026** — instrumentation built today risks rework; pin `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`. Complementary: **OpenInference** (Arize), **OpenLLMetry** (Traceloop). Natively consumed by Datadog/Honeycomb/Grafana. *(See [BENCHMARKS → Part 6](../BENCHMARKS.md#part-6--gateway-observability-the-factors-that-matter) for the exact signals to verify.)*

**Governance, history & the open debates.** The OTel **GenAI SIG** formed **April 2024** (under the Semantic-Conventions SIG, CNCF / Linux Foundation); Traceloop's **OpenLLMetry** (2023) was the early mover and its conventions were upstreamed to seed the official `gen_ai.*` namespace. In **~mid-2026** the whole `gen_ai.*` set was **deprecated in the main semconv repo and moved to a dedicated [`semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai) repo** (managed via Weaver). Two live debates worth knowing:
- **Semconv churn / version pinning.** v1.36 → v1.37 shipped *breaking* changes, so the rule is that an instrumentation **must not silently change the convention version it emits**; `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` is the explicit opt-in to the newest (and drop the ≤1.36 shape). Deprecating `gen_ai.prompt`/`gen_ai.completion` broke downstream tools — concrete churn, not hypothetical.
- **OpenInference (Arize) ↔ `gen_ai.*` convergence.** OpenInference *predated* OTel's namespace (2023) with AI-specific span kinds (LLM / Tool / Agent / Retriever / Chain / Embedding / Reranker). It's **not** a turf war: in 2026 OpenInference instrumentations **dual-emit** both their own and `gen_ai.*` attributes — the two are merging. Frame it as *"OTel defines how telemetry is shaped/transported; OpenInference & `gen_ai.*` define the AI-specific payload."*

*As of June 2026 **no GenAI metric is Stable yet** — the single **Required** signal is `gen_ai.client.operation.duration`; token-usage + TTFT are Recommended, all still "Development".*

> 📌 *The standard moves fast — most `gen_ai.*` attributes are still "Development" status, so re-check the [OTel GenAI conventions repo](https://github.com/open-telemetry/semantic-conventions-genai) for current stability before building dashboards. The tool landscape is in §6 below.*

---

## 6. The tools (taxonomy)

By function (OSS = open-source; ⊟ = hosted/commercial). Many are in [the list's Observability section](../README.md#-observability--cost-tracking):

- **General LLM observability / tracing:** Langfuse (OSS), Arize **Phoenix** (OSS), **Helicone** (OSS, proxy), LangSmith (⊟), **Pydantic Logfire** (OTel-native), Honeycomb (⊟), **Datadog LLM Observability** (⊟), W&B **Weave** (OSS), **OpenLLMetry/Traceloop** (OSS instrumentation), **OpenLIT** (OSS, OTel-native + GPU monitoring; can instrument coding agents), **MLflow Tracing** (OSS, the classic MLOps tool crossed into LLM-obs, implements the OTel GenAI semconv), **TruLens** (OSS, RAG-triad eval/tracing).
- **Drift / safety / monitoring-leaning:** Arize, **Fiddler AI** (⊟; publishes a clear "where OTel stops" analysis), **Guardrails AI** (OSS, output validation), **Maxim AI** (⊟, the eval/obs platform behind Bifrost), **Confident AI** (⊟, behind DeepEval).
- **Evals / quality:** **Braintrust** (⊟), Phoenix evals (OSS), **DeepEval** (OSS), **Ragas** (OSS), **OpenAI Evals** (OSS), **promptfoo** (OSS).
- **Gateway-native observability:** **LiteLLM** (Prometheus metrics + Grafana — the reference self-hosted label set), **Portkey** (OTLP export + budgets + cache/guardrail telemetry), **Kong AI Gateway** (`gen_ai.*` span mapping + PII sanitization), **Cloudflare AI Gateway** (spend limits + DLP/PII scan), **Bifrost**, **vLLora** (ex-LangDB).
- **2026 market shifts to note:** **Helicone → Mintlify** (Mar 2026, maintenance mode), **Portkey → Palo Alto Networks** (closed May 29 2026, into Prisma AIRS), **TensorZero archived** (repo read-only Jun 12 2026), **promptfoo → OpenAI** (Mar 2026), and the **LiteLLM PyPI supply-chain compromise** (v1.82.7/.8, Mar 24 2026) — the independent-observability shakeout *and* the supply-chain risk are exactly why **open export / no lock-in** + version-pinning (Part 6 table-stakes) matter.

---

## 7. Open problems / active debates

1. **LLM-as-judge validity & circularity** — judges show position/verbosity/self-enhancement bias and can be *reliable without valid*; the benchmarks that validate judges themselves rest on human labels (circular). [survey](https://arxiv.org/abs/2411.15594)
2. **The observability ↔ evaluation boundary** — some scoring needs context the gateway lacks (domain ground truth, business outcomes), pushing eval into the app layer; no agreed line.
3. **Silent model drift / provider re-pointing** — providers update weights/filters without version bumps ("'GPT-4' has been many models"); no canonical detector — proposed signals: PSI/KS, embedding-centroid drift, malformed-output spikes, golden-set regression vs a pinned endpoint.
4. **Non-determinism & reproducibility** — even at temp 0 + fixed seed, outputs differ; root cause is non-associative floating-point + **batch-dependent kernels**, not just sampling — undermines reproducible debugging.
5. **Agent / multi-step trace complexity** — one agent run can emit megabytes across dozens of nested spans; straining storage, query, and human comprehension.
6. **High cardinality + cost-of-observability** — storing full prompts/responses at every span can rival production cost; sample? truncate? store-all? unresolved.
7. **Prompt/PII privacy vs compliance** — prompts/completions (the most valuable trace data) carry PII; meanwhile **EU AI Act Art. 12 *mandates* event logging** for high-risk systems (≥6-month retention; **effective 2026-08-02**) — direct tension between "log for compliance" and "minimize PII." [Art. 12](https://artificialintelligenceact.eu/article/12/)
8. **Standards immaturity & churn** — OTel GenAI conventions explicitly "under active development."
9. **"What even is quality"** — no agreed operationalization; reference-free scorers measure per-application proxies, not a measurement theory.
10. **Online vs offline eval** — offline (golden sets) drifts from production reality; online catches drift only after users hit it; weighting unsettled.
11. **No ground truth in production** — live traffic has no reference answer, so quality is estimated by noisy LLM-judge/reference-free methods needing calibration against sparse human labels — the gap underlying #1, #9, #10.

---

## 8. How this maps to *this* project

- **[BENCHMARKS Part 6](../BENCHMARKS.md#part-6--gateway-observability-the-factors-that-matter)** = the practical evaluation **rubric** (table-stakes → advanced) grounded in the §5 standard.
- **The [relay watch-list](../README.md#community-relay-watch-list) + [`canary_check.py`](../scripts/canary_check.py)** = this project's *operational response* to the §3.4 "fake models" measurement papers — fidelity/identity monitoring you can run yourself.
- **The [reproducible cost benchmark](../BENCHMARKS.md)** = the cost/usage signal (§1.1, L1) made transparent and re-runnable.

---

*Corrections & additions welcome via [PR](https://github.com/cuihuan/awesome-ai-gateway) or [issue](https://github.com/cuihuan/awesome-ai-gateway/issues). This is a living survey — the field is young and moving; every claim is dated and sourced so you can re-check it.*
