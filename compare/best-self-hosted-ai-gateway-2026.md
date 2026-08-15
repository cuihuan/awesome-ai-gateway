# Best Self-Hosted AI Gateway in 2026 (LiteLLM vs Bifrost vs Portkey vs Kong)

*Last updated 2026-07-07 · Part of [Awesome AI Gateway](../README.md). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

> 📊 **Key numbers** · Self-hosting adds **$0** per-token markup — but the model still dominates the bill: a 100K-token report ranges **$0.03–$3.01** (a **~106×** spread, [computed](../BENCHMARKS.md#part-3--real-world-token-cost-computed), 2026-06). And star count ≠ safety — **LiteLLM** (<!--s:BerriAI/litellm-->⭐ 56.4k<!--/s-->) shipped 2026 CVEs, so weigh [patch discipline](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability), not just popularity. Self-hosting the gateway doesn't exempt you from provider outages: peer-reviewed measurements show the OpenAI/Anthropic APIs fail **~every 2 days** with ~1h median recovery ([ICPE 2025](https://arxiv.org/abs/2501.12469)) — cross-provider fallback in your gateway config is the fix.

If you want one OpenAI-compatible endpoint for every model — but on **your own infrastructure, with $0 markup** — you're choosing a self-hosted AI gateway. Here are the four that matter in 2026, and how to pick.

## Quick comparison

| Gateway | Language | Best at | Overhead (measured¹) | License | Stars |
|---|---|---|---|---|---|
| **LiteLLM** | Python | Breadth (100+ providers), features | 5.83 ms | MIT | <!--s:BerriAI/litellm-->⭐ 56.4k<!--/s--> |
| **Bifrost** | Go | Raw throughput | 0.62 ms | Apache-2.0 | <!--s:maximhq/bifrost-->⭐ 7.3k<!--/s--> |
| **Portkey Gateway** | TypeScript | Guardrails + governance built in | 2.65 ms | MIT | <!--s:Portkey-AI/gateway-->⭐ 12.7k<!--/s--> |
| **Kong AI Gateway** | Lua/Go | Enterprise K8s + mature plugins | low | Apache-2.0 | <!--s:Kong/kong-->⭐ 44k<!--/s--> |

¹ Independently measured mean added latency per request ([llm-gateway-bench data](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/overhead.json), self-hosted defaults). The vendor-marketed figures — Bifrost "~11µs @ 5k RPS", Portkey "<1ms" — did not reproduce in that harness; treat cross-vendor "Nx faster" claims as marketing until independently reproduced. Kong: not yet measured ("low" per vendor).

## Pick by what you care about

- **Broadest features, fastest to adopt → LiteLLM.** The default. Virtual keys, budgets, load balancing, guardrails, 100+ providers. Python, huge community. Downside: it's feature-heavy and its broad surface has been a security target (see below).
- **Maximum throughput, minimal footprint → Bifrost.** Go, adaptive load balancing, cluster mode; the lowest independently measured overhead (0.62 ms added per request — its marketed ~11µs did not reproduce). Pick it when the gateway must not be your bottleneck.
- **Guardrails and governance built in → Portkey Gateway (OSS).** TypeScript, MIT, 2.65 ms measured overhead (marketed "<1ms" did not reproduce), with a 50+ guardrail set, circuit breakers, fallbacks and MCP OAuth 2.1 free to self-hosters. Pick it when you want policy enforcement *in* the gateway, with a clean upgrade path to the managed cloud if you scale.
- **Already run Kubernetes / need mature governance → Kong AI Gateway.** AI plugins (semantic caching, prompt guard, PII sanitization across 20+ categories) on a battle-tested gateway. One less new service if Kong is already in your stack. (Higress and Apache APISIX are strong alternatives here.)

## What about TensorZero?

You'll still see TensorZero (Rust; gateway + observability + evals in one binary) in older comparisons — it once hit #1 GitHub Trending. **As of June 2026 its repo is archived / read-only** (the company wound down). The Apache-2.0 code and community forks remain usable, but there's **no upstream maintenance or security response**, so it's not a safe default for a new project. If TensorZero's single-binary "gateway + observability" pitch was the draw, the closest maintained paths today are **Bifrost** (throughput) or **Portkey** (governance + observability hooks), with a dedicated tool like MLflow or Helicone for evals.

## Security: patch discipline matters more than the logo

Self-hosting means **you own the security**. Honest 2026 facts:

- **LiteLLM** published **twelve advisories in 2026**, three critical — including a pre-auth SQLi (CVE-2026-42208) and an unauth RCE on CISA's exploited list (CVE-2026-42271) — **both patched in v1.83.7**, with 10 further advisories since — treat ≥1.84.0 as the floor. It's fine *if* you pin to current stable, restrict egress, and never expose the admin panel publicly.
- **Bifrost**: one high SSRF advisory (CVE-2026-55245, fixed 1.5.16) — pin at or above it. **Portkey OSS**: one medium SSRF (fixed 1.14.0). Far thinner records than LiteLLM's, but absence of *found* CVEs is not proof of security — it can mean less scrutiny.
- **Kong**: inherits Kong's mature, hardened auth/RBAC stack.

Full ★1–5 compliance/security/stability scores for 23 gateways: [gateway scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability).

## Don't forget the model cost

The gateway is $0-markup; your bill is the **model**. Same 100K-token report: **$0.03 on DeepSeek vs $3.01 on GPT-5.5** (106×). A self-hosted gateway's biggest win is routing cheap-by-default and escalating only when needed — see the [computed cost tables](../BENCHMARKS.md).

## Verdict

- **Most teams → LiteLLM** (then tune for security).
- **Performance-critical → Bifrost.**
- **Guardrails/governance in the gateway → Portkey.**
- **K8s / enterprise governance → Kong / Higress / Envoy AI Gateway.**

Still deciding *whether* to self-host at all? The condensed [self-hosted gateway how-to-choose guide](https://cuihuan.github.io/awesome-ai-gateway/self-hosted-llm-gateway.html) covers the why and the one-line picks.

See all 100+ gateways organized by need, with decision tree and data:
👉 **[Awesome AI Gateway](https://github.com/cuihuan/awesome-ai-gateway)** · [interactive site](https://cuihuan.github.io/awesome-ai-gateway/)
