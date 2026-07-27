# LiteLLM Alternatives (2026): 8 AI Gateways Compared by Cost, Security & Self-Hosting

*Last updated 2026-07-07 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

> 📊 **Key numbers** · **LiteLLM** is the most-starred OSS gateway (51k★) but shipped two serious 2026 CVEs — a pre-auth SQL injection and an unauthenticated RCE on CISA's KEV list (both fixed in current stable; pin it and don't expose the admin panel) ([security scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability)). On cost the model dominates, not the gateway: a 100K-token report ranges **$0.03–$3.01** (a **~106×** spread, [computed](../BENCHMARKS.md#part-3--real-world-token-cost-computed) 2026-06). Whatever alternative you pick, configure fallback: **rate limits alone caused ~⅓ of all LLM errors** in production telemetry ([Datadog, Mar 2026](https://www.datadoghq.com/state-of-ai-engineering/)).

**[LiteLLM](https://github.com/BerriAI/litellm)** is the default self-hosted LLM gateway — one OpenAI-compatible proxy in front of 100+ providers, virtual keys, budgets, load balancing. It's popular for good reason. But people go looking for alternatives for three honest reasons:

1. **Security posture.** LiteLLM had two serious 2026 CVEs — a pre-auth SQL injection (CVE-2026-42208) and an unauthenticated RCE that landed on CISA's Known-Exploited-Vulnerabilities list (CVE-2026-42271). **Both are fixed in `v1.83.7-stable`** — if you run LiteLLM, pin to current stable and never expose the admin panel — but the track record sends some teams looking.
2. **They don't want to run a server at all** → a *hosted* gateway.
3. **They want lower latency or a different governance model** → a Go/Rust-native proxy, or an enterprise guardrail platform.

Here's the honest, data-backed map. Scores are ★1–5 from the [scorecard rubric](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability) (snapshot 2026-06).

## TL;DR — pick by your actual constraint

| Alternative | Type | Markup | Security | Reach for it when |
|---|---|---|---|---|
| **Bifrost** | Self-hosted (Go) | $0 | ★3.5 · no known CVEs | You want LiteLLM's job but faster and with a clean CVE record |
| **Portkey Gateway (OSS)** | Self-hosted (Apache-2.0) | $0 | ★4.0 | You want guardrails + circuit breakers + MCP OAuth built in |
| **Kong AI Gateway** | Self-hosted | $0 core | ★4.5 | You already run Kong, or need PII sanitization + RBAC |
| **Envoy AI Gateway** | Self-hosted (K8s) | $0 | ★4.0 | You're Kubernetes/Istio-native and want a CNCF-aligned proxy |
| **OpenRouter** | Hosted | ~5.5% | ★3.0 | You want zero ops and 400+ models in five minutes |
| **Cloudflare AI Gateway** | Hosted | 0% | ★4.0 | You want a free, 0-markup hosted gateway with DLP/PII scanning |
| **Vercel AI Gateway** | Hosted | 0% | ★3.5 | You're on Vercel and want true 0% markup incl. BYOK |
| **new-api / one-api** | Self-hosted | $0 | ★1.5–2.0 | You need a China-friendly relay panel — *and will patch aggressively* |

> Same task, the **model behind the gateway can cost 100× more** ($0.03 vs $3.01 for one 100K-token report — a [106× spread](../BENCHMARKS.md)). Every alternative below lets you route cheap-by-default and escalate only when needed — that, not the gateway's own fee, is where the money is.

## If you want to stay self-hosted (just better than LiteLLM)

- **[Bifrost](https://github.com/maximhq/bifrost)** — the closest drop-in *upgrade*. Go-native, ~11µs overhead at 5k RPS (vendor benchmark), adaptive load balancing, cluster mode, 1000+ models, and **no known CVEs**. If your reason for leaving LiteLLM is performance or security hygiene, start here.
- **[Portkey Gateway (OSS)](https://github.com/Portkey-AI/gateway)** — Apache-2.0, <1ms overhead, with **guardrails, circuit breakers, fallbacks and MCP OAuth 2.1 free to self-hosters**. The richest governance feature set of the open-source options; upgrade path to the managed cloud if you scale.
- **[Kong AI Gateway](https://github.com/Kong/kong)** — if you already run Kong or APISIX, the AI plugins (PII sanitization across 20+ categories/12 languages, AI Prompt Guard, Model Armor, RBAC) bolt onto infrastructure you already operate. Highest security score here (★4.5).
- **[Envoy AI Gateway](https://github.com/envoyproxy/ai-gateway)** — built on Envoy, native to Kubernetes/Istio, with multi-provider routing and an MCP gateway (OAuth + CEL authz). No semantic cache or per-key budgets yet, but the cleanest fit for a CNCF-aligned platform team.

## If you'd rather not run a server (hosted alternatives)

- **[OpenRouter](https://openrouter.ai)** — the fastest start: change `base_url`, get 400+ models behind one key, auto-failover, free zero-data-retention, EU region-lock. ~5.5% credit fee; no public SLA outside enterprise.
- **[Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)** — **0% markup**, SOC 2 II / ISO 27001 / PCI / GDPR, with free DLP + PII scanning, guardrails and fallback. 100% SLA on Business+. The strongest free hosted option on compliance.
- **[Vercel AI Gateway](https://vercel.com/docs/ai-gateway)** — **true 0% markup including BYOK**, SOC 2 II, 99.99% SLA (Enterprise), ZDR option. The obvious choice if you already deploy on Vercel.

## If you need a China-friendly relay panel

- **[new-api](https://github.com/QuantumNous/new-api)** is the most active successor to one-api (~38k★) and **[one-api](https://github.com/songquanpeng/one-api)** is the MIT original. They're great for multi-key, multi-provider reselling panels — but be clear-eyed: new-api carries a **cluster of 2026 CVEs** (IDOR auth-bypass, two SSRF, a SQLi/DoS), so sandbox it, restrict egress, and patch aggressively. See the dedicated [one-api vs new-api vs LiteLLM (Chinese)](one-api-vs-new-api-vs-litellm.zh-CN.md) breakdown.

## So, should you actually leave LiteLLM?

**Often, no.** Patched to `v1.83.7-stable` and kept off the public internet, LiteLLM is a healthy project with weekly releases and the broadest provider coverage. Leave it when you have a *specific* reason:

- **Performance / clean CVE record** → Bifrost
- **Built-in guardrails & governance** → Portkey
- **Already on Kong/APISIX/Envoy/K8s** → the matching native gateway
- **Zero ops** → OpenRouter (fastest) or Cloudflare/Vercel (0% markup)

Full scorecard (compliance / markup / security / stability for 20+ gateways) and the reproducible cost tables are in the **[evaluation set →](../BENCHMARKS.md)**. Browse all gateways by need in **[Awesome AI Gateway →](../README.md)**.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. CC0, no signup, no tracking, no vendor money.*
