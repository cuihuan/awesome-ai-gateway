# OpenRouter Alternatives (2026): 8 AI Gateways Compared by Markup, Compliance & Self-Hosting

*Last updated 2026-07-07 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

> 📊 **Key numbers** · OpenRouter adds **~5.5%** on credits; **Vercel AI Gateway** and **Helicone** pass through at **0% markup**. But the bigger lever is the model, not the fee: a 100K-token report spans **$0.03 → $3.01** (a **~106×** spread, [reproducible benchmark](../BENCHMARKS.md#part-3--real-world-token-cost-computed), computed 2026-06). Provider loyalty is also short-lived: enterprise LLM-API spend flipped to Anthropic 40% · OpenAI 27% (was 50% in 2023) · Google 21% in two years ([Menlo Ventures, n=495](https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/); Menlo is an Anthropic investor) — pick an alternative that doesn't hard-wire you to any one of them.

**[OpenRouter](https://openrouter.ai)** is the default hosted AI gateway — change one `base_url`, get <!--omc-->~340<!--/omc--> models behind a single key, with auto-failover and a smart `auto` router. It's the fastest way to start. But teams go looking for alternatives for four honest reasons:

1. **The ~5.5% credit fee.** OpenRouter takes a cut on top of provider pricing. At scale, a **0%-markup** gateway or self-hosting saves real money.
2. **Compliance gaps.** Its SOC 2 Type II is **unverified** and there's **no public SLA outside enterprise** — a blocker for regulated teams.
3. **They want their keys on their own infra** → a self-hosted gateway.
4. **EU data residency** → an EU-first provider.

Here's the honest, data-backed map. Scores are ★1–5 from the [scorecard rubric](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability) (snapshot 2026-06).

## TL;DR — pick by your actual constraint

| Alternative | Type | Markup | Compliance | Reach for it when |
|---|---|---|---|---|
| **Cloudflare AI Gateway** | Hosted | 0% | ★4.5 | You want zero markup + DLP/PII scanning + a real SLA, free |
| **Vercel AI Gateway** | Hosted | 0% (incl. BYOK) | ★4.0 | You're on Vercel / the AI SDK and want true 0% markup |
| **Requesty** | Hosted | ~5% | ★3.5 | You need EU residency (Frankfurt) + PII masking, OpenRouter-style |
| **Eden AI** | Hosted | ~5.5% | ★3.5 | You're EU-first / GDPR-default and want no-training guarantees |
| **Portkey (cloud)** | Hosted | free tier + usage | ★4.5 | You need guardrails, RBAC, SSO and a 99.99% SLA |
| **Azure / Bedrock / Vertex** | First-party | n/a | ★4.5–5.0 | You need the strongest certs (HIPAA, FedRAMP) |
| **LiteLLM** | Self-hosted | $0 | ★3.0 | You want your keys, your infra, no middleman fee |
| **Bifrost** | Self-hosted | $0 | ★3.0 | You self-host and want maximum throughput |

> Same task, the **model behind the gateway can cost 100× more** ($0.03 vs $3.01 for one 100K-token report — a [106× spread](../BENCHMARKS.md)). The gateway's own fee is the *small* number; routing cheap-by-default is where the savings are.

## If your reason is the markup (you want 0%)

- **[Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)** — **0% markup**, runs on Cloudflare's edge, with free DLP + PII scanning, caching, analytics, guardrails and fallback. SOC 2 II / ISO 27001 / PCI / GDPR and a 100% SLA on Business+. The strongest free hosted option on compliance — the obvious first stop if cost is why you're leaving OpenRouter.
- **[Vercel AI Gateway](https://vercel.com/docs/ai-gateway)** — **true 0% markup including BYOK**, SOC 2 II, 99.99% SLA (Enterprise), ZDR option, and tight integration with the Vercel AI SDK. The natural choice if you already deploy on Vercel.

## If your reason is EU data residency / compliance

- **[Requesty](https://requesty.ai)** — the closest drop-in: an EU-friendly OpenRouter-style router, 400+ models, sub-20ms failover, ~5% markup, with **Frankfurt residency, PII masking and ZDR**. (SOC 2 is "in progress, Q2 2026" per their page — verify before an audit.)
- **[Eden AI](https://www.edenai.co/)** — France-based, **EU-default residency, GDPR-first, no-training**, ~5.5% platform fee. Good when "data never leaves the EU" is the hard requirement.
- **For the strongest certs**, go first-party: **[Azure OpenAI](https://azure.microsoft.com/products/ai-services/openai-service)**, **[AWS Bedrock](https://aws.amazon.com/bedrock/)** and **[Google Vertex AI](https://cloud.google.com/vertex-ai)** carry HIPAA-BAA and FedRAMP High — at the cost of single-vendor lock-in (no cross-provider failover).

## If your reason is keys-on-your-infra (self-host)

- **[LiteLLM](https://github.com/BerriAI/litellm)** — the default self-hosted proxy: virtual keys, budgets, load balancing, 100+ providers, **$0 markup**. Patch to ≥1.84.0 (12 advisories landed in 2026; two of them, including a critical auth bypass, are fixed only there) and keep the admin panel private. See [LiteLLM alternatives](litellm-alternatives-2026.md) if you want a self-hosted option with a cleaner CVE record.
- **[Bifrost](https://github.com/maximhq/bifrost)** — Go-native, **0.62 ms** measured added latency per request ([independent harness](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/overhead.json); the vendor's ~11µs claim did not reproduce there); one high SSRF advisory on record (CVE-2026-55245, fixed 1.5.16), adaptive load balancing, cluster mode, 1000+ models. Pick it when throughput matters.

## If your reason is enterprise governance

- **[Portkey (cloud)](https://portkey.ai)** — SOC 2 II + ISO 27001 + HIPAA + GDPR, a 50+ guardrail marketplace, RBAC, SSO, key vault and a 99.99% SLA. The hosted choice when policy enforcement and audit matter more than the lowest fee.

## What OpenRouter still wins at

Be fair: OpenRouter is hard to beat on **breadth and time-to-first-call** (<!--omc-->~340<!--/omc--> models, one key, five minutes), its **`auto` router** picks a model per prompt for you, and its **free zero-data-retention + EU region-lock** cover many privacy needs. Leave it when you have a *specific* constraint:

- **Cost / 0% markup** → Cloudflare or Vercel
- **EU residency** → Requesty or Eden AI
- **Hard compliance certs** → Azure / Bedrock / Vertex or Portkey
- **Keys on your infra** → LiteLLM or Bifrost

Full scorecard (compliance / markup / security / stability for 20+ gateways) and the reproducible cost tables are in the **[evaluation set →](../BENCHMARKS.md)**. Browse all gateways by need in **[Awesome AI Gateway →](../README.md)**. Prefer a one-screen version? The condensed [by-reason shortlist guide](https://cuihuan.github.io/awesome-ai-gateway/openrouter-alternatives.html) walks the same decision.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. CC0, no signup, no tracking, no vendor money.*
