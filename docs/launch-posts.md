# Launch posts — ready-to-paste drafts

Drafts the **maintainer posts** (see `OPERATIONS.md` §3). The agent prepares these; it does **not**
auto-post in your voice. Edit freely before posting.

## Pre-launch checklist (do first)
- [ ] **Push everything** so the repo + live site reflect all improvements (the launchers will look).
- [ ] Upload a **social-preview image** (Settings → Social preview, 1280×640 — `assets/social-preview.png`, already generated). Every share unfurls with it.
- [ ] **Warm up to ~100★ via your own network FIRST** (research-backed): a friends/colleagues/community-you're-in ask to "check it out" creates the social proof that converts cold launch traffic. Legitimate seeding — distinct from vote manipulation. Do NOT ask anyone to upvote HN/Reddit.
- [ ] Sanity-check the live site loads: https://cuihuan.github.io/awesome-ai-gateway/
- [ ] (Nice-to-have, #1 on-page lever) a short **demo GIF of the interactive site** at the top of the README.
- [ ] Be available to reply for a few hours after the HN/Reddit post.

### Sequencing for velocity (the part that actually trips GitHub Trending)
GitHub Trending ranks by star **velocity vs. *your own* baseline** (plus forks/issues/PRs/comments) — **not** absolute count. From **~71★** (current), even **15–30 stars in 24–48h** can trip it in a niche tag; spreading the same stars thin over two weeks never builds the spike. So:
- [ ] **Concentrate the high-velocity channels into one 24–48h window** — HN Show HN + r/LocalLLaMA + **daily.dev** (underrated, low-gate, dev audience — a case study's first +100★; draft in §8) + the X thread (ideally with a demo GIF, and pitched to a GitHub-projects reposter like @GithubProjects) — ideally **Tue–Thu, 12–17 UTC** (research: ~+200 stars vs off-hours; HN *score*, not the "Show HN" tag, is what predicts stars).
- [ ] **Then sustain** over the next 1–2 weeks with the slower channels (周刊 async, V2EX, linux.do, r/selfhosted) **and reply to every issue/PR** — ongoing engagement keeps feeding Trending's signal after the initial burst.
- [ ] **Never solicit upvotes** anywhere (esp. HN) — it gets the post flagged and undoes the whole launch.

> **Where you actually are (2026-07-28):** **73★** (GitHub API, checked 2026-07-28), ~19★/week natural velocity, **but the concentrated launch burst has still never fired.** The day-1 seed added 16★ in hours; a real multi-channel burst is the single biggest lever left to 100+. Assets woven into the drafts below — from 07-27: the **coding-agent routers deep-dive** (mechanism tiers + dated ban evidence), the **SSO-tax table** (BENCHMARKS Part 7, primary-sourced), the **curated Cost-first section**; and from 07-28: the **🛡️ supply-chain security matrix** (who signs releases, who got backdoored — machine-checked, with two circulating fake Kong CVEs debunked), the **July v4.1 scoreboard rebase** (Opus 5 / GPT-5.6 / Kimi K3 / GLM-5.2 / Gemini 3.6 Flash), and the **12/13 pricing-verification story** (the one miss was a silent retirement, not a reprice).

### ⏱️ Timely news-peg — LIVE AGAIN (window: ~Jul 28 – Aug 3)
The **July flagship wave** is a fresh hook this week: **Kimi K3 weights hit HF Jul 27** (it's now the top open-weights model on AA v4.1 — r/LocalLLaMA catnip), **Claude Opus 5 landed Jul 24** (AA #1 + SWE-bench Verified 96.0), plus GPT-5.6 / Grok 4.5 / Gemini 3.6 Flash earlier in the month. Optional opener for Reddit (the $788 opener stays the default elsewhere):
```
Kimi K3's weights dropped yesterday and it's now the top open-weights model on the (rebased) AA index;
Opus 5 took the overall #1 four days ago. Every time this happens, the per-task cost math reshuffles —
so I re-verified all 13 model prices in my gateway benchmark against official pages the same week.
12 of 13 matched. The 13th had been silently *retired* and rebilled at a different model's rate.
```
The old export-control pattern (kept in case a comparable provider outage lands during launch week): "provider X pulled model offline globally → no failover if you're single-provider → that's why the list leads with multi-provider routing."

**Evergreen stat pack (Amplify 2026 AI Engineering Report, n>1,000 — cite freely, doesn't decay):**
- **87%** of AI engineers actively run multiple models together (44% route by task type, 11% by cost) — multi-model routing is the default architecture.
- **75%** adjust how ambitiously they use AI because of cost; cost is the **#2 most-monitored production metric** after quality.
- Only **20%** rank reliability top-3 in model selection — pair this with the Fable 5 story: failover is underpriced insurance.
- Source: https://www.amplifypartners.com/blog-posts/the-2026-ai-engineering-report

---

## 1. Hacker News — Show HN  (highest ROI; US weekday morning PT)

**Title** (factual, no superlatives, explains the approach):
```
Show HN: Awesome AI Gateway – a reproducible cost benchmark + scorecard for 100+ LLM gateways
```
**URL:** `https://github.com/cuihuan/awesome-ai-gateway`

**First comment (post yourself, within a minute):**
```
I built this after burning $788 on AI coding in a single day — one flagship model ate 78% of it,
just because I'd defaulted everything to the priciest option. The same 100K-token report costs
$0.03 on DeepSeek vs $3.01 on GPT-5.5 — a 106× spread — and the gateway you route through decides
how easily you exploit that.

So I mapped the whole landscape (100+ gateways/proxies across 9 categories) and tried to make it
the opposite of a vendor blog:
- Every cost number is computed by a unit-tested script from open pricing data — reproducible, not asserted.
- A 5-axis scorecard (compliance/price/security/stability/observability) with honest CVE disclosure.
- A supply-chain matrix: which gateways sign releases / ship SBOMs, and what actually got exploited
  (the LiteLLM PyPI backdoor, unpatched CVEs on dormant projects) — machine-checked against CVE.org,
  including two widely-circulated "critical Kong CVEs" that turned out not to exist.
- An evidence-based watch-list that names gray-market relays caught swapping/downgrading models — with a
  runnable canary-diff script, not hearsay.
- A coding-agent router comparison (claude-code-router / OmniRoute / 9router / CLIProxyAPI / sub2api)
  classified by mechanism — BYO API key vs own-subscription OAuth vs pooled accounts — with the actual
  ToS clauses and dated account-ban reports per tool. Zero documented bans on the BYO-key path.
- An "SSO-tax" table: which of 9 gateway vendors paywall SSO / SCIM / RBAC / audit logs, every cell
  primary-sourced (6 of 9 gate SSO; one ships it free on all plans).
- CC0, no affiliate links, bilingual (EN/中文), star counts refreshed daily by CI.

Happy to answer anything about the methodology or where it's wrong.
```
*Etiquette: link the repo (not the Pages page). Stay in-thread. Do not ask for upvotes.*

---

## 2. 阮一峰《科技爱好者周刊》开源自荐  (open an issue in `ruanyf/weekly`)

**Issue title:**
```
【开源自荐】Awesome AI Gateway:100+ AI 网关的可复现成本基准 + 评分卡
```
**Body (200–500 字):**
```
我做这个项目,是因为有一天在 AI 写代码上烧了 $788——一个旗舰模型吃掉了 78%,只因为我把所有请求
都默认打给了最贵的那个。同一份 10 万 token 的报告,DeepSeek 上 $0.03,GPT-5.5 上 $3.01,差 106 倍;
而你用哪个网关,决定了你能多容易地吃到这个价差。

于是我把整个 AI 网关/中转生态摸了一遍(100+ 个,分 9 类),做成一个尽量"反厂商软文"的清单:

· 每个成本数字都由一个带单测的脚本从公开定价算出来——可复现,而不是嘴说。
· 一张 5 维评分卡(合规/价格/安全/稳定/可观测),如实披露 CVE;外加一张供应链安全矩阵——谁给发布签名、
  谁真被投毒过(LiteLLM PyPI 后门事件),全部对 CVE.org 机器核验,还证伪了两条流传的假 CVE。
· 一个基于证据的"避雷观察名单":点名那些被抓到偷换/降智模型的灰产中转,并附可运行的 canary 对比脚本,不靠传闻。
· 一篇编码 Agent 省钱路由器对比(claude-code-router / OmniRoute / 9router / CLIProxyAPI / sub2api),
  按机制分层讲清"省多少 vs 封号风险",附真实 ToS 条款与带日期的封号记录。
· CC0 协议、无返利链接、中英双语、star 数每天 CI 自动刷新。

在线站点:https://cuihuan.github.io/awesome-ai-gateway/
仓库:https://github.com/cuihuan/awesome-ai-gateway
```

---

## 3. Reddit — r/LocalLLaMA  (best fit; post as a resource, day 2–3)

**Title:**
```
I mapped 100+ AI gateways / LLM proxies and benchmarked their cost — open data, reproducible
```
**Body:**
```
After accidentally burning ~$788 of API spend in a day (one flagship model, defaulted everywhere),
I went down a rabbit hole and mapped the whole AI-gateway / LLM-proxy landscape — 100+ of them across
9 categories (cost-first, self-hosted/OSS, enterprise, first-party clouds, China ecosystem, MCP/agent).

What I tried to do differently from the vendor blogs:
- Cost numbers are computed by a unit-tested script from open pricing — reproducible. (Same 100K-token
  report: $0.03 on DeepSeek vs $3.01 on GPT-5.5.)
- A 5-axis scorecard (compliance / price / security / stability / observability) with CVE disclosure.
- Fresh this week: the whole benchmark table rebased to AA v4.1 with the July wave in it — Kimi K3
  (new top open-weights, weights on HF since yesterday), Opus 5, GPT-5.6, GLM-5.2 — and a monthly
  price re-verification where 12/13 matched official pages; the 13th had been silently retired and
  rebilled at a different model's rate.
- An evidence-based watch-list that names relays caught swapping or quantizing models — with a canary-diff
  script you can run yourself, not rumor.
- For the Claude Code / Codex crowd: a router deep-dive (claude-code-router vs OmniRoute vs 9router vs
  CLIProxyAPI vs sub2api) that answers "will this get my account banned?" by mechanism — BYO key vs
  own-OAuth vs pooled accounts — with dated ban reports straight from each tool's issue tracker.

It's CC0, no affiliate links. Curious where r/LocalLLaMA thinks I'm wrong on the self-hosted picks
(LiteLLM / Bifrost / Portkey / Kong / new-api).

Repo: https://github.com/cuihuan/awesome-ai-gateway
```
*Etiquette: lead with the resource, not a pitch. Read the sub's self-promo rules. Engage replies.*

---

## 4. Reddit — r/selfhosted  (day 4–5; self-hosted angle)

**Title:**
```
Comparison of self-hostable AI gateways (LiteLLM vs Bifrost vs Kong vs new-api…) + a reproducible cost benchmark
```
**Body:**
```
I maintain an open (CC0) comparison of 100+ AI gateways; the self-hosted section compares the ones you
can run in your own VPC — LiteLLM, Bifrost (Go), Portkey OSS, Kong/Higress/APISIX, new-api/one-api — on
markup, features, license, and known CVEs, with a reproducible per-task cost benchmark behind it.

The reason it matters for self-hosters: for sensitive data you want a gateway in your own infra (or a
0%-markup hosted one), and the model behind it can cost 100× more for the same task. There's also a
watch-list flagging gray-market relays that swap models — with a canary script to verify your own.

Three additions this sub will appreciate: a supply-chain security matrix — which gateways cosign/GPG
their releases, ship SBOMs, have a disclosure policy, and what actually got exploited (the real
LiteLLM package was backdoored on PyPI in March via its own CI; one popular panel has an unpatched
CVE and hasn't shipped a release since Feb 2025) — machine-checked against repos and CVE.org; an
SSO-tax table (in the sso.tax spirit) showing which of 9 gateway vendors paywall SSO / SCIM / RBAC /
audit logs — 6 of 9 gate SSO behind an enterprise tier, every cell linked to the vendor's own pricing
page; and the hosted "cost-first" section now leads with the 10 track-record options, with all
unverified relays folded behind a warning.

Repo: https://github.com/cuihuan/awesome-ai-gateway  ·  Self-hosted section:
https://github.com/cuihuan/awesome-ai-gateway#-self-hosted-open-source
```

---

## 5. V2EX — 分享创造 (`/go/create`)  (周五上午佳)

**标题:**
```
分享一个开源项目:Awesome AI Gateway —— 100+ AI 网关的可复现成本基准 + 评分卡(中英双语)
```
**正文:**
```
起因是有天在 AI 写代码上烧了 $788,一个旗舰模型占了 78%。同一份 10 万 token 的报告,DeepSeek $0.03、
GPT-5.5 $3.01,差 106 倍。于是把 AI 网关/中转生态(100+,9 类)整理成了一个清单:

· 成本由带单测的脚本从公开定价算出,可复现;
· 5 维评分卡(合规/价格/安全/稳定/可观测),如实写 CVE;新增供应链安全矩阵(谁给发布签名、谁被投毒过,
  对 CVE.org 机器核验);
· "避雷观察名单"用证据点名偷换模型的灰产中转,附可运行的 canary 对比脚本;
· 最近新增:编码 Agent 路由器对比(claude-code-router / OmniRoute / 9router / CLIProxyAPI / sub2api),
  按"自带 key / 订阅 OAuth / 拼车账号池"三种机制分层,逐个附 ToS 条款和带日期的封号记录;
· CC0、无返利、中英双语、star 每天自动刷新。

仓库:https://github.com/cuihuan/awesome-ai-gateway
在线:https://cuihuan.github.io/awesome-ai-gateway/
欢迎拍砖,尤其是国内中转那块的判断。
```
*纯开源分享,无 aff,不求 star。*

---

## 6. linux.do  (纯开源 GitHub 分享,无需推广 tag;无 AFF)

**标题:**
```
开源:Awesome AI Gateway —— 100+ AI 网关的可复现成本基准 + 避雷观察名单
```
**正文:** 同 V2EX 正文即可(去掉最后一行),结尾加:
```
特别想听听大家对"中转可信度"的看法——清单里有一套黑盒 canary 检测来判断中转是不是偷换/降智模型,
这块的方法论欢迎挑战。编码 Agent 路由器那篇(按机制分层讲封号风险,附各仓 issue 里带日期的封号
记录)应该也是这里最有发言权的话题,欢迎补充案例或反例。
```

---

## 7. X / Twitter  (build-in-public thread; ongoing, not one-shot)
```
1/ I burned $788 on AI coding in one day. One flagship model ate 78% of it — because I'd defaulted
everything to the priciest option.

So I mapped every AI gateway worth knowing and benchmarked the cost. Open source, CC0 🧵

2/ The same 100K-token report: $0.03 on DeepSeek vs $3.01 on GPT-5.5 — a 106× spread. Across 123 models
it's >400×. The gateway you route through decides how easily you exploit that. [price-spread chart]

3/ 100+ gateways across 9 categories. Every cost number computed by a unit-tested script from open
pricing — reproducible, not asserted. Plus a 5-axis scorecard with honest CVE disclosure.

4/ And an evidence-based watch-list that names gray-market relays caught swapping/downgrading models —
with a canary-diff script you can run yourself. No affiliate links, no vendor money.

5/ Newest: "will routing Claude Code through X get me banned?" — answered by mechanism, not vibes.
claude-code-router vs OmniRoute vs 9router vs CLIProxyAPI vs sub2api, with dated ban reports from
their own issue trackers. Zero bans documented on the BYO-key path. Plus an SSO-tax table for the
enterprise crowd.

6/ This week's find: I re-verified all 13 model prices against official pages. 12 matched exactly.
The 13th (Grok 4) had been silently *retired* in May — its old slug still answers, billed as a
different model at 2.4× less than the list price we carried. Pin models by dated slug; watch
retirement notices, not just price pages.

7/ Also new: a supply-chain matrix for gateways — who cosigns releases, who ships SBOMs, what
actually got backdoored (the real LiteLLM PyPI package, March) — and two viral "critical Kong CVEs"
that don't exist at CVE.org. Evidence cuts both ways.

→ https://github.com/cuihuan/awesome-ai-gateway
```

---

## 8. daily.dev  (low-gate, dev audience; fire inside the burst window)

Post as a **link submission in a relevant squad** (or your own squad) — daily.dev distributes by
engagement, not follower count, which is why it has minted first-+100★ runs for comparable repos.
Submit the **live site** (unfurls with the social preview), not the bare repo.

**URL:** `https://cuihuan.github.io/awesome-ai-gateway/`

**Title (daily.dev truncates long titles; keep it under ~100 chars):**
```
100+ AI gateways compared: reproducible cost benchmark, SSO-tax table, coding-agent ban-risk tiers
```
**First comment (the "author's note" that drives daily.dev engagement):**
```
Maintainer here. Started this after burning $788 on AI coding in one day. Everything opinionated in
it is backed by something you can run: cost tables come from a unit-tested script over open pricing
data, gateway overhead was measured independently (0.62 ms vs 5.83 ms per request is a real gap),
and the coding-agent router page classifies claude-code-router / OmniRoute / 9router / CLIProxyAPI /
sub2api by ban-risk mechanism with dated reports from their own issue trackers. CC0, no affiliate
links. Tell me what's missing.
```
*Etiquette: one submission, no cross-squad spam; reply to comments same-day — comment velocity is
the ranking signal.*

---

## Backlink PRs (agent-prepped; maintainer submits) — see OPERATIONS.md §4
sindresorhus/awesome (after list ≥30d + lint pass) · tensorchord/Awesome-LLMOps · InftyAI/Awesome-LLMOps ·
Hannibal046/Awesome-LLM · punkpeye/ & appcypher/awesome-mcp-servers (MCP section). Each: one-line entry in
their format, `[Awesome AI Gateway](https://github.com/cuihuan/awesome-ai-gateway) - …`.
