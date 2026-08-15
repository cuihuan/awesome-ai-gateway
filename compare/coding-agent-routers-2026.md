# Coding-Agent Routers (2026): claude-code-router vs OmniRoute vs 9router vs CLIProxyAPI vs sub2api — Savings vs. Ban Risk

*Last updated 2026-07-27 · Part of [Awesome AI Gateway](../README.md) — the only AI-gateway list with a [reproducible cost benchmark](../BENCHMARKS.md) and a [security-honest scorecard](../BENCHMARKS.md#part-4--gateway-scorecard-compliance--price--security--stability--observability). [⭐ Star it](https://github.com/cuihuan/awesome-ai-gateway).*

> 📊 **Key numbers** · The savings don't come from the router — the same coding-agent session costs **$0.021 to $1.75** depending on the model behind it, a **~83× spread** ([computed](../BENCHMARKS.md#33-coding-agent-session-mixed--reasoning-tokens), unit-tested script). The risk doesn't come from the router brand either — it comes from the **mechanism**: BYO API keys are provider-sanctioned; routing your own subscription OAuth through third-party tools has been **explicitly disallowed by Anthropic since 2026-02-20** ([policy change](https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use)); and pooled-account quota resale is the thing Anthropic says it is actively banning for ([clarified 2026-02-19](https://piunikaweb.com/2026/02/19/anthropic-claude-max-ban-agent-sdk-clarification/)).

Every heavy Claude Code / Codex / Cursor user eventually shops for a router — claude-code-router, OmniRoute, 9router, CLIProxyAPI, sub2api, opencodex, freellmapi — and asks the same two questions: how much do I actually save, and **will this get my account banned?** The honest answer depends almost entirely on which of three mechanisms the tool uses, not on its GitHub stars. Here is each tool classified by what **its own README** says it does, with the actual ToS clauses and dated ban reports — no vibes.

## The three mechanism tiers

| Tier | Mechanism | Provider stance | Realistic worst case |
|---|---|---|---|
| **1 · BYO API key** | Routes to providers over your own pay-per-token API keys | **Sanctioned** — API keys exist precisely for programmatic access | Rate limits; a bigger bill |
| **2 · Own-account OAuth proxying** | Reuses *your own* consumer subscription (Claude Pro/Max, ChatGPT Plus, Copilot) outside the official client | **Gray → disallowed.** Anthropic restricted subscription OAuth to its own surfaces on 2026-02-20; automated non-API access needs explicit permission under its consumer ToS | Your subscription — and the account behind it — gets banned |
| **3 · Pooled-account arbitrage** | Pools many subscription accounts and redistributes the quota to *other users*, often for money | **Violation** — both Anthropic and OpenAI consumer ToS prohibit sharing credentials and reselling access | Whole account pools banned; buyers are holding resold, unverifiable capacity |

## Where each tool sits — from its own docs

| Tool | Tier | What its own docs say (verbatim) |
|---|---|---|
| [Claude Code Router](https://github.com/musistudio/claude-code-router) <!--s:musistudio/claude-code-router-->⭐ 36.7k<!--/s--> | **1 — BYO key** | Quick start: "Open Providers → Add Provider … **enter the API key**, select the protocol and models". One gray edge: the features table lists "**local login import where supported**" — skip importing CLI logins and you stay cleanly in Tier 1 |
| [freellmapi](https://github.com/tashfeenahmed/freellmapi) <!--s:tashfeenahmed/freellmapi-->⭐ 18.5k<!--/s--> | **1 — BYO key, free tiers** | "add **your provider keys** on the Keys page"; ships its own per-provider ToS review (May 2026) with the rule of thumb "**one account per provider**, **no reselling**, **no sharing your endpoint with other humans**"; repo self-labels "personal experimentation only" |
| [opencodex](https://github.com/lidge-jun/opencodex) <!--s:lidge-jun/opencodex-->⭐ 10k<!--/s--> | **1 or 2 — mode-dependent** | Tier 1 path: "Paste your **API key** (or log in via OAuth…)". Tier 2 path: "It can also manage a **ChatGPT account pool** for Codex auth. Add multiple ChatGPT / Codex accounts" with quota-based auto-routing |
| [9router](https://github.com/decolua/9router) <!--s:decolua/9router-->⭐ 25.5k<!--/s--> | **2 — own-OAuth cascade** | Request flow: "**Tier 1: SUBSCRIPTION** — Claude Code, Codex, GitHub Copilot" falling back to cheap/free; "**Multi-account** — Round-robin between accounts per provider"; the repo carries a PR titled "Antigravity **anti-ban** alignment" |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) <!--s:diegosouzapw/OmniRoute-->⭐ 48.1k<!--/s--> | **2 — own-OAuth + free-tier stacking** | "auto-falls back across 4 provider tiers — **Tier 1 Subscription (Claude Code, Codex, Copilot)** … Tier 4 Free"; its own free-tier budget card admits "**15 providers ToS-flagged** so you decide"; the feature list includes "**TLS fingerprint stealth**" |
| [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) <!--s:router-for-me/CLIProxyAPI-->⭐ 47.3k<!--/s--> | **2, drifting toward 3** | "**Claude Code support via OAuth login**"; "Claude Code **multi-account load balancing**"; the README's sponsor slots sell "**ready-to-use accounts**" at "10% of the official GPT subscription price" |
| [sub2api](https://github.com/Wei-Shaw/sub2api) <!--s:Wei-Shaw/sub2api-->⭐ 37.1k<!--/s--> | **3 — pooled-account distribution** | Self-described "**AI API Gateway Platform for Subscription Quota Distribution**" where "Users can access upstream AI services through **platform-generated API Keys**"; its own disclaimer: "The authors assume no liability for **account bans**…" |

Three reads between the lines. First, what separates Tier 2 from Tier 3 is *whose* accounts are in the pool: 9router and OmniRoute route **your own** logins on your own machine; sub2api exists to redistribute pooled quota to **other people**, with "carpool" billing built in. Second, tooling tells you what the authors expect — OmniRoute ships TLS-fingerprint stealth and 9router ships anti-ban code, which only matter if providers are detecting you. Third, sub2api's sponsor list includes residential-IP and browser-fingerprint vendors marketed as reducing "the probability of association-based risk control" — infrastructure whose sole purpose is evading ban systems. None of this is hidden; it's all in the READMEs.

## What the ToS actually say

- **Anthropic Consumer Terms** (effective 2025-10-08, retrieved 2026-07-27): "You may not share your Account login information, Anthropic API key, or Account credentials with anyone else… You also may not make your Account available to anyone else" (Section 2), and Section 3 prohibits using the services "to… resell the Services" and — except via an API key or explicit permission — "to access the Services through automated or non-human means, whether through a bot, script, or otherwise" ([consumer terms](https://www.anthropic.com/legal/consumer-terms)). That last clause is what makes *every* Tier-2 tool gray by construction.
- **2026-02-20 — the gray zone closed.** Anthropic updated its compliance docs to prohibit subscription OAuth (Free/Pro/Max) in third-party products; developers "must now use API key authentication" ([report, 2026-02](https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use)).
- **What Anthropic says it enforces**: "a small number of users are violating our usage policies by **sharing and reselling accounts**… we're taking appropriate action to stop it." An Anthropic staffer clarified that holding multiple Max accounts is *not* a violation — "enforcement is aimed at people using accounts to **resell tokens**" ([2026-02-19](https://piunikaweb.com/2026/02/19/anthropic-claude-max-ban-agent-sdk-clarification/), [background](https://metricnexus.ai/blog/anthropic-banning-multiple-claude-accounts)). That is a precise description of Tier 3.
- **OpenAI Terms of Use**: "You may not share your account credentials or make your account available to anyone else and are responsible for all activities that occur under your account" ([terms](https://openai.com/policies/row-terms-of-use/); page is bot-gated — wording as quoted by [OpenAI's account-sharing policy coverage](https://help.openai.com/en/articles/10471989-openai-account-sharing-policy)). Same implication for ChatGPT-account pools (opencodex's pool mode, CLIProxyAPI, sub2api).
- **Scale — no reliable public figure.** Anthropic's [Transparency Hub](https://www.anthropic.com/transparency) publishes no account-enforcement statistics, and the ban guides in circulation document the ban/appeal process without aggregate numbers (both checked 2026-07-27). Treat any "X accounts banned" total you see quoted as unsourced.

## Ban evidence, tool by tool

- **CLIProxyAPI** — documented, repeatedly: "claude code subscription banned" ([#2211](https://github.com/router-for-me/CLIProxyAPI/issues/2211), 2026-03-18; follow-up [discussion #2244](https://github.com/router-for-me/CLIProxyAPI/discussions/2244)); "Account Suspended After Using Gemini CLI + Antigravity" ([#1803](https://github.com/router-for-me/CLIProxyAPI/issues/1803), 2026-03-03); a community thread titled "Tip on avoiding account being banned" ([#3431](https://github.com/router-for-me/CLIProxyAPI/issues/3431), 2026-05-16); and a security report that one leaked key "can exhaust all upstream credentials and cause **permanent account bans**" ([#3467](https://github.com/router-for-me/CLIProxyAPI/issues/3467), 2026-05-18).
- **sub2api** — documented: a user reports his Claude subscription was revoked **twice** while proxying OAuth through sub2api, on a $20 account, asking how to configure it "safely" ([#1715](https://github.com/Wei-Shaw/sub2api/issues/1715), 2026-04-17, zh); another asks whether a shared Singapore server IP will get **all pooled accounts** banned at once ([#2520](https://github.com/Wei-Shaw/sub2api/issues/2520), 2026-05-16, zh).
- **OmniRoute** — documented: "Claude Teams/Max accounts **banned by Anthropic right after connecting as provider**" ([#4118](https://github.com/diegosouzapw/OmniRoute/issues/4118), 2026-06-17 — closed by adding a warning in the UI); the project also maintains built-in account-ban detection ([#5600](https://github.com/diegosouzapw/OmniRoute/issues/5600), 2026-06-30).
- **9router** — documented: "Likelihood of Getting Banned — Claude Code" ([#291](https://github.com/decolua/9router/issues/291), 2026-03-12); "account suspended" ([#2050](https://github.com/decolua/9router/issues/2050), 2026-06-24); plus handling code for accounts that are "API-banned but OAuth is healthy" ([#1444](https://github.com/decolua/9router/issues/1444), 2026-05-26).
- **Claude Code Router** — **none documented as of 2026-07-27**: a search of its issue tracker finds no report of an account banned through CCR's BYO-key path. Consistent with the mechanism: API-key traffic is what providers sell.
- **opencodex** — none documented as of 2026-07-27 (young repo, ~6 weeks old; its ChatGPT-pool mode shares the risk profile of the tools above, evidence just hasn't accumulated).
- **freellmapi** — none documented as of 2026-07-27; its own ToS-review table is the closest thing to risk documentation in this cohort.

The pattern is exactly the tier table: every documented ban sits in Tier 2/3 OAuth or pooled traffic; we found zero ban reports against BYO-API-key routing.

## Claimed savings vs. measured reality

| Tool | Claimed savings | Status |
|---|---|---|
| OmniRoute | Compression "saves 15–95% tokens (~89% avg)"; "~1.53B free tokens/mo" across stacked free tiers | **Vendor-claimed** (README hero + free-tier card); not independently verified |
| 9router | "Save 20-40% tokens with RTK + auto-fallback" | **Vendor-claimed** (README tagline) |
| freellmapi | "roughly 4 billion tokens per month" of stacked free-tier capacity | **Vendor-claimed** (README); capacity, not a savings % |
| Claude Code Router | No headline savings figure — pitch is routing + observability | Not documented |
| CLIProxyAPI | No savings figure — the value prop is reusing subscription quota | Not documented |
| sub2api | No savings figure — the value prop is cost-sharing pooled quota | Not documented |
| opencodex | No savings figure | Not documented |

Now the measured contrast, from this repo's own unit-tested benchmark: the **same coding-agent session** (50K in / 20K out / +30K thinking) costs **$0.021 on DeepSeek V4-Flash and $1.75 on GPT-5.5 — ~83×** ([Part 3.3](../BENCHMARKS.md#33-coding-agent-session-mixed--reasoning-tokens)). On capability per dollar, **DeepSeek V4 Pro ties Gemini 3.1 Pro on SWE-bench Verified (80.6%) at ~11× less**, and the 95% ceiling costs ~46× the cheapest model that still clears 80%. In other words: **model choice through a plain Tier-1 BYO-key router captures the bulk of the savings these tools advertise — with zero ToS exposure.** And if you route Claude Code cross-format to an OpenAI-style upstream, use a gateway that measurably survives the translation: LiteLLM and Bifrost both pass 3/3 (tools + streaming + usage) in our [independent fidelity test](../BENCHMARKS.md#part-3--real-world-token-cost-computed); pin your version.

## What we'd do

- **Anything serious — work code, a client's repo, the account your history lives on: Tier 1 only.** BYO API keys behind Claude Code Router (or LiteLLM/Bifrost if you need cross-format translation), routed cheap-by-default with escalation. The 83× model spread is where the money is, and nobody has ever documented a ban for it.
- **Tier 2 (own-OAuth routing: 9router, OmniRoute, CLIProxyAPI, opencodex pool mode) — only with a burner subscription you can genuinely afford to lose**, on an isolated account with no work history. Since 2026-02-20 this is explicitly against Anthropic's stated policy, the ban reports above are real and dated, and "the tool has stealth features" should read as a warning, not a reassurance.
- **Tier 3 (sub2api-style pooled distribution) — we wouldn't.** As the operator you are the exact target Anthropic says it bans (and its sponsor ecosystem's ban-evasion tooling says the operators know it); as a buyer of pooled quota you're on unverifiable resold capacity — an [independent 2026 fingerprinting study](https://arxiv.org/abs/2603.01919) of resold relays measured **model-identity verification failures in 45.8% of fingerprint tests**.

Full cost tables, the SWE-bench-vs-cost chart and the gateway scorecard are in the **[evaluation set →](../BENCHMARKS.md)**. Browse every gateway by need in **[Awesome AI Gateway →](../README.md)**.

---

*Found this useful? [⭐ Star the list](https://github.com/cuihuan/awesome-ai-gateway) — it's how the next engineer choosing a gateway finds it. CC0, no signup, no tracking, no vendor money.*
