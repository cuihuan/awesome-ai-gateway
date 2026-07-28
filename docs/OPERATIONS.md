# Operations & Growth Playbook

How this project is maintained and grown. This is a **living, executable** doc — the
maintainer (and the agent helping) work against it. Pragmatic first goal: **grow stars
and make the project active**, by being *the cited neutral authority on "which AI gateway."*

Status legend: ✅ done · ⬜ todo · 👤 maintainer-does (outward/needs a human) · 🤖 agent-can-prep

---

## 1. Theory — why people star/share this, and our levers

A GitHub star is a cheap bookmark + an identity signal. People star a list/benchmark when, in ~5s,
they can (a) classify what it is, (b) believe it saves a real decision or real money, and (c) trust
it won't rot. Leaderboards (Artificial Analysis, LMArena) spread because they become **the scoreboard
people cite in arguments** — the citation *is* the distribution.

**Our 3–4 levers, ranked:**

1. **Be the cited neutral authority.** Our edge over every vendor blog = independence (CC0, no
   affiliate $), a *reproducible* cost benchmark, and a watch-list that names sketchy relays **on
   evidence**. That's quotable. It's what gets us into listicles, Reddit threads, and AI answers.
2. **Distribution as a sequence, not one spike.** Our lead asset is the **"$788 in a day" story** +
   the **>400× price-spread table**. Spend it across HN → 阮一峰周刊/Reddit → V2EX/linux.do →
   newsletters over ~2 weeks. Concentrated velocity (not one-day) is also what trips GitHub Trending.
3. **Backlinks from other awesome-lists + listicles = compounding discovery.** The awesome-list flywheel.
4. **Liveness + responsiveness.** Daily-update CI already signals "alive"; fast, warm issue triage
   converts the unsolicited relay reports we already get into contributors.

> The **$788 story** is the single strongest hook. Lead every launch post and the HN first comment with it.

---

## 2. Issue & community operations

### Label taxonomy ✅ (created 2026-06-24)
`new-gateway` · `entry-fix` · `watch-list` · `needs-evidence` · `benchmark` · `methodology`
(+ GitHub defaults `good first issue` / `help wanted` / `question`). The `report-relay.yml` template
emits `watch-list` + `needs-evidence`, so these must exist (they now do).

### Triage SLA (solo-maintainer-realistic)
- First human response **≤48h on weekdays**: a label + one acknowledging line. Batch triage 2–3×/week; don't go fully reactive.
- `needs-evidence` reports: auto-point at `scripts/canary_check.py`; **close after 14 days** without proof (per CONTRIBUTING).
- Gateway-add PRs: review **≤5 days**; merge or request the one-line fix.

### Saved-reply templates (GitHub → Settings → Saved replies)
- **New-gateway suggestion** → "Thanks! Fits [section]. To add it I need: (1) on the request path (not an SDK/UI), (2) public repo/docs, (3) active <12mo. It's a 2-line PR — format in CONTRIBUTING; happy to label it `good first issue` and guide you."
- **Relay report w/ evidence** → "Verified — canary diff shows [X]. Adding to the watch-list with your evidence linked. Thank you — this is exactly what keeps the list credible."
- **Relay report w/o evidence** → "We only name relays on shareable proof (rumor → liability). Fastest path is a canary diff: `python scripts/canary_check.py …`. Marking `needs-evidence`; reopen anytime with output."
- **Methodology question** → answer once, then **fold it into BENCHMARKS.md / FAQ** so the next person self-serves.

### Operator self-promotion PRs — the self-certification rule (precedent 2026-07-02)
Relay operators submit PRs editing *their own* listing. Welcome the factual parts; **never let a
party self-graduate its own watch-list status.** Reject-on-sight signals (all seen in one real PR):
- **Self-certifies ⚠️ Unverified → ✅ Verified** citing "my endpoint returns 200 / I tested it." Not the
  bar — ✅ needs an **independent** model-fidelity diff (`canary_check.py` / K2-Vendor-Verifier), never the operator's own key.
- **Deletes a true caveat** (e.g. removing the `new_api_error` → new-api note). Re-probe before believing the removal; keep verified-true signals.
- **Injects marketing** — `utm_*` tracking params, campaign links, "N% below official" as a headline (that price is itself a resale signal), or a star-span (`<!--s:owner/repo-->`) pointing at a non-repo (breaks the star-refresh CI).
- **New relay with no reachable `/v1`** — root serves a 404/placeholder, `/v1/models` 404s (a live one answers 401). Hold, don't merge; ask for a reachable base URL.

Disposition: post an evidence-based, non-hostile review (re-probe and cite what you found), keep the entry ⚠️ Unverified,
and **close** self-certification PRs with a clear path back (independent canary repro auto-flips the status). Honest-but-premature
entries (good format, just no live endpoint) get the review and stay **open** for the author to fix. Saved reply:
- **Operator self-certifies own listing** → "Thanks for the update. Status changes need *independent* verification — `/v1/models` returning 200 with your own key isn't the bar (that's a canary-diff). I re-probed and [finding]. Keeping ⚠️ Unverified; the moment there's an independent canary repro the ✅ is automatic."

### Convert reporters → contributors
Every "you should add X" → offer the 2-line PR + `good first issue`. Recognize contributors in
`CHANGELOG.md` and a README `## Contributors` block. Keep 3–5 genuinely-10-minute `good first issue`s open.

---

## 3. Launch sequence (one concentrated 48–72h burst — distinct post per channel)

> **Corrected 2026-06-25 (was "spread over ~2 weeks").** GitHub Trending ranks star *velocity vs. this repo's own ~1–2 star/day baseline*, so 15–25 stars in one day is already a large multiple — spreading the same posts over two weeks *dilutes* that multiple. HN delivers ~92% of its star impact within 48h. So: fire the high-velocity channels inside **one 48–72h window** (ideally Mon–Tue ~13–16 UTC), each with a **channel-distinct** post (copy-paste across subreddits triggers shadowbans), and stay present to answer. "Never same-day" still applies *per channel* (don't repost the same HN/subreddit), not across channels.

Lead asset everywhere: **$788/day** + **>400× price spread** + **reproducible benchmark**. Link the **repo** (not the Pages page) on HN.

| # | Channel | How | Owner |
|---|---|---|---|
| 1 | **Hacker News — Show HN** (highest ROI) | Title factual, no superlatives, explain the *approach*: `Show HN: Awesome AI Gateway – reproducible cost benchmark + scorecard for 100+ LLM gateways`. Post the $788 story as your **own first comment** within minutes. Live in-thread for hours. **Never solicit upvotes** (ring-detection nukes you). | 👤 (🤖 drafts) |
| 2 | **阮一峰《科技爱好者周刊》** | Open an issue in `ruanyf/weekly` titled `【开源自荐】…`, 200–500字: what/why, screenshot, $788 hook, license. Don't resubmit until a major update. | 👤 (🤖 drafts) |
| 3 | **r/LocalLLaMA** (best Reddit fit) | Post as a *resource* ("I mapped 100+ gateways & benchmarked cost — sharing the data"), lead with the table. Day 2–3. | 👤 (🤖 drafts) |
| 4 | **r/selfhosted** | Angle on the self-hosted/OSS gateway section. Day 4–5 (stagger). | 👤 (🤖 drafts) |
| 5 | **V2EX `/go/create`** + **linux.do** | Pure OSS share (no aff). V2EX Fri AM; linux.do needs no 推广 tag for a pure GitHub share. | 👤 (🤖 drafts) |
| 6 | **Newsletters** | Console.dev → `osh@codesee.io`; TLDR AI / Ben's Bites tip forms. | 👤 |
| 7 | **X/Twitter + dev.to** (ongoing) | Build-in-public: price-spread chart, $788 thread, weekly benchmark deltas; dev.to repurpose of the README. | 👤 (🤖 drafts) |
| — | r/MachineLearning (weekends only), lobste.rs (needs invite, <25% self-promo), Product Hunt (weak fit for a list) | low priority | — |

Subreddit etiquette: read each sub's self-promo rules; r/LLMDevs **bans** self-promo (only answer "which gateway" questions there).

---

## 4. Get listed elsewhere (the compounding flywheel)

| Target | Action | Bar | Owner |
|---|---|---|---|
| **sindresorhus/awesome** | PR adding us under AI | list ≥**30 days old**, `awesome-lint` clean (see `docs/awesome-lint-triage.md`), title-case heading, slug repo name, **review 4 other PRs**, comment `unicorn` | 👤 (🤖 preps PR) |
| **tensorchord/Awesome-LLMOps** | PR under gateways/routing | fork→PR | ✅ submitted #572 |
| **Hannibal046/Awesome-LLM** | PR under tools/infra | active queue | ✅ submitted #682 |
| ~~InftyAI/Awesome-LLMOps~~ · ~~punkpeye/awesome-mcp-servers~~ | — | verified bad fit (don't PR) | ❌ skip — but punkpeye is now **reciprocally linked** in our Related-lists footer |
| **Next-wave awesome targets** (see §9): kyrolabs/awesome-langchain, eudk/awesome-ai-tools, awesomelistsio/awesome-llmops | PR under each list's meta/LLMOps section | verified actively-merging 2026 | 🤖 preps — hold ~1/mo |
| **"best AI gateway" listicles** (TechSY, TrueFoundry, Braintrust, denshub, …) + **OpenAlternative.co** directory | offer our independent benchmark as a citable source / submit via their form | — | 👤 |
| **AI answer engines (GEO)** | llms.txt/sitemap/JSON-LD/feed shipped; **+ machine-readable `dateModified` + IndexNow→Bing shipped 2026-06-25**; Bing WMT account still 👤 (see §9) | partial — see §9 | 🤖 + 👤 |

**Submitted backlink PRs (check here before opening new ones — don't duplicate):**
- ✅ [kelvins/awesome-mlops #216](https://github.com/kelvins/awesome-mlops/pull/216) — OPEN (Other Lists)
- ✅ [tensorchord/Awesome-LLMOps #572](https://github.com/tensorchord/Awesome-LLMOps/pull/572) — OPEN (Awesome Lists)
- ✅ [Hannibal046/Awesome-LLM #682](https://github.com/Hannibal046/Awesome-LLM/pull/682) — OPEN (Miscellaneous)
- ✅ [steven2358/awesome-generative-ai #902](https://github.com/steven2358/awesome-generative-ai/pull/902) — OPEN (More lists)
- ✅ [mahseema/awesome-ai-tools #1631](https://github.com/mahseema/awesome-ai-tools/pull/1631) — OPEN (Related Awesome Lists)
- ✅ [underlines/awesome-ml #65](https://github.com/underlines/awesome-ml/pull/65) — OPEN (llm-tools.md / Libraries & Wrappers)
- ❌ skip (verified bad fit): InftyAI/Awesome-LLMOps & EthicalML/awesome-production-machine-learning (tools-only, no meta-list section + star gate) · punkpeye/awesome-mcp-servers (MCP-only) · DefTruth/Awesome-LLM-Inference (deprecated/papers-only) · formulahendry/awesome-gpt (PR-averse, unmerged since 2023)
- ⏳ sindresorhus/awesome — **eligible ~2026-07-11** (repo created 2026-06-11; the ≥30-day gate is the only blocker — topics/branch already pass). Then: lint-clean + maintainer personally reviews 4 PRs + `unicorn`; 👤. Do NOT submit before then (auto-closed).
- **6 backlink PRs is plenty for launch period — hold further submissions (more same-week = spam-perception).**

---

## 5. GitHub discovery
- **Topics** ✅ (20, incl. `benchmark`, `cost-optimization`, `llm-gateway`, `llmops`, `mcp`, `openrouter`, `litellm`).
- **Description** ✅ ("100+ …", keyword-rich).
- **Website field** ✅ (Pages site).
- **Social-preview image** ✅ — uploaded (og:image verified 2026-07-27: `repository-images.githubusercontent.com` custom card). Every share unfurls with it.
- **Profile README + pinned repos** ⬜👤 — pin all three repos; cross-link them (READMEs already cross-link ✅).
- **Trending** = star *velocity vs. own baseline* + issues/PRs/forks. Concentrate launch pushes to create velocity; keep activity flowing after.

---

## 6. Weekly cadence
| When | Do | Time |
|---|---|---|
| Daily | glance new issues/PRs, label only | 5m |
| 2–3×/wk | triage batch: respond w/ templates, merge trivial PRs | 20m |
| Weekly | post a "benchmark delta / what's new" (X + the README `📊 Latest evaluations` table); engage 1 Reddit thread genuinely | 45m |
| Weekly | refresh 1 `good first issue`; thank contributors in CHANGELOG | 15m |
| Monthly | 1 backlink PR to another awesome-list; 1 dev.to/掘金 article | 2h |

## 7. Metrics (only these)
Total stars + **weekly velocity** (star-history.com) · **GitHub Insights → Traffic → Referrers**
(which channel actually converts — double down) · issue first-response time · PR merge time. Ignore the rest.

---

## 8. Foundation status (2026-06-24)
✅ Label taxonomy created · ✅ #8 classified (`watch-list`+`needs-evidence`) · ✅ description→"100+" · ✅ topics tuned ·
✅ artifacts complete (llms.txt/sitemap/feed/JSON-LD/CITATION/SECURITY) ·
✅ launch-post drafts (`docs/launch-posts.md`) · ✅ +8 verified gateways (coverage audit) · ✅ batch pushed live (Pages verified) ·
✅ 3 awesome-list backlink PRs open (kelvins#216, tensorchord#572, Hannibal046#682) ·
✅ social-preview image (uploaded; og:image verified 2026-07-27) · ⬜👤 pin+profile README · ⬜👤 execute forum launch (drafts ready).

### Maintenance / growth log
- **2026-06-24 · accuracy audit** — all 66 GitHub-backed entries verified via `gh api`: 61 active, 5 stale/archived (TensorZero, pydantic-ai-gateway, BricksLLM, Glide, RouteLLM) — **all 5 already correctly labeled** in the list. 0 uncorrected issues; the "active within 12 months or labeled stale" promise holds. Re-run quarterly (or after big additions).
- **2026-06-24 · growth actions executed (agent-doable):** +8 verified gateways · cost-calculator.html live · 3 `good first issue`s (#11–13) · 3 awesome-list backlink PRs (kelvins#216, tensorchord#572, Hannibal046#682) · 阮一峰周刊 self-rec ([ruanyf/weekly#10435](https://github.com/ruanyf/weekly/issues/10435)).
- **Still 👤 (needs you — live presence / your account):** the real-time forum launch (HN Show HN, r/LocalLLaMA, r/selfhosted, V2EX, linux.do — drafts in `launch-posts.md`), social-preview image upload, pin repos, sindresorhus/awesome PR. These move stars most but backfire if fired without you present.
- **2026-07-27 · full-cycle audit → ship batch.** A multi-agent audit (5 reader personas + SEO/GEO + market trends + growth-state + accuracy verification) produced 13 ranked actions; the agent-ownable ones all shipped same-day. By rank:
  1. Cost-first curated — 10 track-record picks up front, 16 unverified relays folded into one details block (`55416b6`).
  2. Decision layer moved above the catalog; TOC gained the user-task entry (`071fed5`).
  3. Numbers pipeline sealed — top-table sort CI-enforced (`71abcf7`), hand-typed star counts single-sourced (`e3d80fe`), OpenRouter model count single-sourced (`61fa219`), compare pages carry measured overhead (`3f3a427`), 6 fact-check corrections (`383bd24`).
  4. Watch-list canary seeding — 👤 pending; exact commands + cost estimate prepped in the maintainer action memo.
  5. Coding-agent routers deep-dive shipped — mechanism tiers, ToS reality, dated ban evidence (`06c8b8b`) — and wired into TOC / hero / fast-answer / smart-routing / guides in both languages (`52f27c6`).
  6. Missed fast-risers added (freellmapi, opencodex, CPA-Manager-Plus, ccglass et al., `5500b1e`); July market events + star-farming caution in What's new (`a3b77fe`).
  7. Launch burst — 👤 pending; every channel draft refreshed to 71★ + the three new assets, daily.dev draft added (`bef75ac`).
  8. Data-retention matrix joined the freshness watch (`c04c8a0`).
  9. SEO consolidation — canonical pairing old guides → 2026 deep-dives (`0893379`), index links every money page (`f9926f2`), llms.txt gained Guides + Tools (`3dc0b65`), sitemap lastmod from git history (`453bce2`), §9c status brought honest (`a703cc3`).
  10. GEO schema — ItemList + SoftwareApplication + honest dateModified (`7c602b6`), FAQPage on all EN deep-dives (`7d35b7d`).
  11. Homelab questions answered in-list — UI / Ollama / deploy-weight columns (`f861654`).
  12. SSO-tax identity & governance matrix, primary-sourced, BENCHMARKS Part 7 (`581db03`).
  13. Hygiene batch — external PRs #39/#40/#41 merged with evidence-based edits (`6da5855` / `c35c619` / `db3dbc0`); social-preview + HelloGitHub statuses corrected in this doc; duplicate self-rec close-notes, GoModel discussion reply and canary runbook drafted for 👤 (see decision memo below for sindresorhus).

- **2026-07-28 · user-value + growth batch (agent-run).** Two research agents (pricing/benchmark verification vs official pages + supply-chain security with primary sources) fed a same-day ship: ① **supply-chain matrix shipped** — the §10d candidate is now a README section in both languages + `data/supply_chain.json` + 30d freshness CI + 10 tests; incidents primary-sourced, 2 circulating fake Kong CVEs debunked in print. ② **July scoreboard rebase** — AA v4.1 single-source columns, 5 new flagships, Fable/Mythos SWE-Pro misattribution fixed; monthly pricing re-verification 12/13 exact, the miss being retired-Grok-4 (stand-in price was 2.4× the real rate) — the retirement-not-reprice lesson now leads the evaluations digest. ③ **Otari (Mozilla AI) added** (66→344★/3wk); DEEIX-Chat ruled out (workspace, not request-path). ④ Housekeeping: §9c-3 zh-CN follow-up verified done; monthly backlink PR **skipped** — all 4 next-wave targets fail the actively-merging bar (recorded above §9f table); 6 open PRs unchanged, no nudges. Tests 232→242 green; cited key numbers (83×/106×/$17.50) re-verified against regenerated tables.

_Sources & full research: condensed from a 2026 competitive-research pass (HN/Reddit/周刊/awesome-list mechanics, GitHub Trending, issue-ops). The bottleneck is distribution + issue-ops + backlinks — not more artifacts._

---

## 9. Deep-research update (2026-06-25) — evidence-backed method v2

A 6-agent research pass (how comparable awesome-lists + LLM-gateway projects actually grow & maintain, + GEO citation mechanics, + verified new backlink targets) sharpened the method. The headline: **the moat is credibility + freshness, and the unfixed bottleneck is the retrieval layer (Bing) + the human-led launch — not more on-page artifacts.**

### 9a. What the research changed (corrections to conventional wisdom — all evidence-backed)
- **llms.txt is near-dead for AI *citations*** (~0.1% of AI-bot traffic touches it; Google's Illyes confirmed Google won't support it). Keep it (≈0 cost) but **reclassify it as a B2A / IDE-agent convenience** (Cursor/Claude Code/Copilot *do* fetch it); optionally add `/llms-full.txt`. It is *not* the GEO win §4 used to imply.
- **The real GEO precondition is being in Bing's index** — ~87% of ChatGPT Search citations match Bing top results. → shipped **IndexNow** (push protocol, no account needed) + machine-readable **`dateModified`**; Bing Webmaster Tools account is still 👤 (9d).
- **Buying stars backfires** (controlled study: zero effect on real downloads; detection tooling flags the inorganic spike — the *opposite* of the velocity pattern Trending rewards). The maintainer's no-fraud stance is *empirically* correct, not just ethical.
- **"Show HN" tag isn't magic** — engagement *score* predicts stars (r≈0.29), comment count barely does (r≈0.10). Optimize for a clear factual title + fast author replies, not a lively comment thread.
- **Badge walls + posting-time obsession are cargo-cult** — current 5–6 functional badges are at the right ceiling; best-vs-worst HN slot is only ~4×. Don't let timing anxiety delay a ready launch.
- **"Asking for stars" is nuanced, not banned** — a soft README CTA + *personalized 1:1 thank-you-and-ask* to people who already engaged converts; generic "please star" pleas + mass-DMs are spam. Crossing **~100 real stars** is the human-credibility gate that lets organic traffic convert against a visible number.
- **The 2014 category land-grab is not replicable in 2026** — `awesome-ai-gateway` enters a crowded namespace, so chasing first-mover timing is wasted; win on the moats incumbents won't build (independence/CC0, the reproducible $788 benchmark, the evidence-based relay watch-list).

### 9b. Shipped 2026-06-25 (agent-doable, done)
- ✅ **IndexNow** key + `scripts/ping_indexnow.py` (+6 unit tests) + daily-CI ping step → Bing/Yandex discovery.
- ✅ **Machine-readable freshness** — `dateModified`/`datePublished` + `article:modified_time` on compare pages, auto-stamped from the byline (never fabricated).
- ✅ **Reciprocal "Related lists" footer** (EN+zh) — the backlink-graph play's missing half.
- ✅ **Release-tracking** for the 13 audit-added repos; **CHANGELOG** brought current + first contributor (@c99e) credited.

### 9c. Agent-doable queue (next iterations — do NOT do all at once; one focused change per loop)
1. ✅ **DONE 2026-07-27** — honest `dateModified` on the remaining static pages: index.html (+ Dataset `dateModified`) plus gateway-picker/cost-calculator via `article:modified_time` (commit `7c602b6`; the guide pages already carried it, and three of them now canonicalize to their compare/ successors — commit `0893379`). Bonus: sitemap `<lastmod>` now comes from per-file git history, never fabricated (commit `453bce2`).
2. ✅ **DONE 2026-07-27** — schema extended: `FAQPage` auto-generated on all 6 EN compare deep-dives from each article's own headings, 3–5 Q&As each, CI-guarded (commit `7d35b7d`); `ItemList` (explicitly unordered — matches the "winner per constraint" stance) + `SoftwareApplication` for the top 4 gateways on index.html (commit `7c602b6`).
3. ✅ **DONE (fully closed 2026-07-28)** — every EN compare page opens with a dated + sourced 📊 **Key numbers** blockquote directly under the byline ($0.03-vs-$3.01 = 106×, markup %, CVE/outage stats, each with a source link). The zh-CN follow-up is also done: both zh-CN twins (coding-agent, one-api) carry the 关键数字 block in .md and .html (verified 2026-07-28).
4. ✅ **DONE 2026-06-25** — **"won't-rot" stale-gateway CI** (`scripts/check_stale_gateways.py` + monthly `stale-check.yml` + published removal rule in CONTRIBUTING). Flags any release-tracked repo that's archived/no-push-in-12mo AND not already ⚠️-labeled (cross-references the README), so the "active within 12mo or labeled stale" promise is mechanical. Advisory (own workflow, doesn't touch the main CI badge); red only on an actionable unlabeled-stale or a 0-coverage fetch failure. Code-reviewer-vetted (caught + fixed a substring-match blocker). Link-check workflow already existed; keep the contribution *gate* narrow (3-criteria + 5-day SLA) — the opposite of punkpeye's 1,700-open-PR firehose.
5. ✅ **DONE** — above-the-fold visual shipped: `assets/hero-demo.gif` (the 4-step method in ~10s) linked atop the README (commit `ceca30b`).

### 9d. New verified backlink/listing targets (the NEXT WAVE — hold to ~1/month; 6 already open is enough for the launch window)
| Target | Section we fit | Recent-merge evidence | Priority |
|---|---|---|---|
| [kyrolabs/awesome-langchain](https://github.com/kyrolabs/awesome-langchain) (9.4k★) | `## Complement to this list` | **OUTCOME: PR #447 closed unmerged, no comment (2026-07-09)** — maintainer passed; do NOT resubmit | ~~TOP~~ closed |
| [eudk/awesome-ai-tools](https://github.com/eudk/awesome-ai-tools) (522★) | `## LLM Ops` | 10 recent merges 2026-06-05→07 from distinct authors | secondary (≠ the already-submitted mahseema/awesome-ai-tools #1631) |
| [awesomelistsio/awesome-llmops](https://github.com/awesomelistsio/awesome-llmops) | `## Related Awesome Lists` | ext. PRs #16 (06-22), #28 (06-23); 0 open | lowest-friction (small but compounding network cross-links) |
| [OpenAlternative.co](https://github.com/piotrkulpinski/openalternative) (6.4k★) | AI-gateways category, via /submit form | repo pushed 2026-06-24; public /submit | best **non-awesome** directory — 👤 (lists tools, not catalogs; submit individual angle) |
| [TechSY "8 Gateways Ranked 2026"](https://techsy.io/en/blog/best-llm-gateway-tools) | listicle citation (no PR path) | updated 2026-06-13; admits it uses only internal testing + star counts, **no independent benchmark** | 👤 outreach — offer our benchmark as the missing independent cross-check |

### 9e. 👤 Maintainer-only — the moves that actually move stars now (agent has maxed the prep)
1. **Create a Bing Webmaster Tools account** (bing.com/webmasters) → *Import from Google Search Console* (1-click) → submit `sitemap.xml` → record the June-2026 **Citation Share** baseline (it can't be backfilled, so every week of delay loses trend history). This unlocks the IndexNow pings already firing.
2. **Submit to sindresorhus/awesome** — ⏳ **NOT YET ELIGIBLE.** The repo was created **2026-06-11**, and sindresorhus auto-closes lists **< 30 days old** — so the earliest valid submission is **~2026-07-11**. Topics (`awesome`+`awesome-list`) ✅ and branch `main` ✅ already pass; only the age blocks it. *(Correcting an earlier note that claimed we clear the age gate — we don't until mid-July.)* When eligible: agent preps (`npx awesome-lint` to zero via `docs/awesome-lint-triage.md`, PR body); you open the PR, **review 4 other open PRs**, post `unicorn` in one sitting. No star minimum exists. This is the single biggest evergreen backlink — worth doing the day it's eligible.
3. **Run the 48–72h launch burst** (§3) — HN (factual title, $788 first comment) + r/LocalLLaMA + r/selfhosted + one newsletter, channel-distinct posts, present to answer. Drafts in `docs/launch-posts.md` (agent keeps them channel-distinct).
4. **Warm 1:1 outreach** to people who already engaged (issue reporters, the #14 contributor, anyone who forked) — the proven path to the first ~100 real stars.

### 9f. Venue + backlink refresh (2026-07-01 industry scan)

**Boundary reminder:** every venue below is for **organic discovery / human-led discussion or a submit-once self-rec** — never bot auto-posting (that backfires). Drafts live in `docs/launch-posts.md`; the maintainer posts.

**Highest-signal venues (ranked):**
1. **r/LocalLLaMA** (~762k) — the single best organic-discovery venue; blunt, benchmark-driven, they actually run these gateways. Lead with data.
2. **Hacker News** — still the top launch surface but saturated; a gateway Show HN needs a sharp benchmark angle (most land 1–5 pts; breakouts are data-led).
3. **Gateway project Discords** — LiteLLM (~6k, most on-topic) + OpenRouter (~49k). Highest-intent, participate don't dump.
4. **Latent Space + AINews (smol.ai)** — the AI-engineering canon + a discovery flywheel (AINews auto-summarizes top AI Discords/subreddits). Amplifier, not a post target.
5. **AI Engineer community / World's Fair** — highest practitioner density; the SF World's Fair ran Jun 29–Jul 2 2026. Gateway/inference/ops angle is on-topic.
6. **MLOps Community Slack** (~70k) — genuine LLMOps/AgentOps discussion.
7. **HelloGitHub 【开源自荐】** ([521xueweihan/HelloGitHub](https://github.com/521xueweihan/HelloGitHub), ~163k★) — best single submit-once move for a CN audience (site + WeChat + Weibo). ✅ **submitted 2026-07-08** ([#3426](https://github.com/521xueweihan/HelloGitHub/issues/3426), open). ✅ **Duplicate cleanup done 2026-07-27** (maintainer-directed): closed the repo-creation-day dup [#3345](https://github.com/521xueweihan/HelloGitHub/issues/3345) with a pointer to #3426, and the ruanyf/weekly dup [#10290](https://github.com/ruanyf/weekly/issues/10290) with a pointer to [#10435](https://github.com/ruanyf/weekly/issues/10435) — one open self-rec per venue now.
8. **阮一峰周刊 【开源自荐】** — already submitted ([ruanyf/weekly#10435](https://github.com/ruanyf/weekly/issues/10435)); the other high-leverage CN submit-once.
Runner-ups (CN human discussion): linux.do 开发调优, 掘金/知乎 writeups, GitHub-Chinese-Top-Charts (auto-ranks on star velocity). **New in 2026:** r/AI_Agents surged to ~392k (routing lives inside agent-stack talk); **Datadog "State of AI Engineering"** (verified 2026-07-07: https://www.datadoghq.com/state-of-ai-engineering/, telemetry from 1,000+ orgs, Apr 2026) is a citation-magnet anchor — verified framing: **>70% run 3+ models** (press release said 69%), **rate limits ≈ ⅓ of LLM errors (Mar 2026, 8.4M)**, only 28% of calls show cached input, OpenAI share 75%→63%. Now cited in the README digest + Essential reading — reuse these stats in posts. Low fit: r/MachineLearning (research-skewed), lobste.rs (invite-only, AI-cool), dev.to.

**⚠️ Target-health re-check 2026-07-28 — the monthly backlink PR was SKIPPED this month.** All four next-wave awesome-list targets now fail the "actively merging" bar: KennethanCeyer/awesome-llmops last push 2025-03-17 (dormant 16mo), awesomelistsio/awesome-llmops last merge 2026-06-23 with an unmerged queue since, filipecalegario/awesome-generative-ai 0 merged of last 20 closed PRs, eudk/awesome-ai-tools 0 merged of last 8 closed. Opening PRs into non-merging lists = perceived spam with zero backlink yield. All 6 previously-opened PRs remain open/unmerged (checked 2026-07-28) — no nudges sent (anti-spam). Re-verify targets next month; OpenAlternative.co (form submit, 👤) is now the best remaining listing move.

**New backlink/listing targets (verified 2026-07-01; still hold to ~1/mo — 6 already open):**
| Target | How we fit | Note |
|---|---|---|
| [KennethanCeyer/awesome-llmops](https://github.com/KennethanCeyer/awesome-llmops) (~55★) | its `Awesome`/related-lists block links out to other awesome-lists | **cleanest home to list *the list itself*** |
| [filipecalegario/awesome-generative-ai](https://github.com/filipecalegario/awesome-generative-ai) (~3.5k★, active) | `LLMOps` / `AI Engineering` subsection | high authority (≠ steven2358, already done) |
| [Sumanth077/ai-engineering-toolkit](https://github.com/Sumanth077/ai-engineering-toolkit) (~3.2k★) | has an **AI Gateway** entry | tool-row ask (list a gateway), not the catalog |
| [InftyAI/Awesome-LLMOps](https://github.com/InftyAI/Awesome-LLMOps) (~252★) | literal **AI Gateway** + **LLM Router** sections | ⚠️ earlier flagged bad-for-*meta-list*; fits a **tool entry**, not listing our list |
| [EthicalML/awesome-production-machine-learning](https://github.com/EthicalML/awesome-production-machine-learning) (~20.7k★) | MLOps meta | highest authority, but MLOps-lean → acceptance less certain |

**sindresorhus/awesome:** eligibility opens **~2026-07-11** (30-day age gate; repo created 2026-06-11). Landing it cascades passive backlinks into awesome.ecosyste.ms / trackawesomelist / project-awesome automatically. Agent preps lint+body; 👤 opens + reviews 4 PRs + `unicorn`. **This is the imminent high-value move.**

## 10. Growth research v3 (2026-07-06) — the star-velocity playbook + content strategy

Two research agents (growth mechanics + fast-rising competitors). What's NEW vs §3/§9 below; older sections stand.

### 10a. Star growth is a velocity game (evidence-backed)
Trending ranks stars-gained **vs your own ~1–2★/day baseline**, so at ~39★ a **30–60★ day** can trend and self-reinforce (Explore → search → "users also starred"). Concrete lift data (arXiv 2511.04453 + case studies): HN front page ≈ **+121/+189/+289 stars @ 24h/48h/7d** (right-skewed — most posts land modest); post **12–17 UTC** (~+200 vs off-hours); **HN *score*, not the "Show HN" tag, predicts stars** (tag has no significant lift after controls). Fast-grower pattern = **(unique content OR first-mover on a wave) × owned distribution × freshness cadence** — our reproducible benchmark IS the unique content, so **lead every post with the numbers, not the link list**.

### 10b. New / re-prioritized channels (add to the launch set)
- **daily.dev** — underrated, low-gatekeeping, dev audience; a case study got its **first +100★** here. Submit — high ROI, low effort.
- **X repost by a GitHub-projects influencer** (e.g. @GithubProjects) — the single highest-leverage *external* trigger (drove a repo to #2 daily Trending); needs a **demo GIF/video** + crisp hook.
- **Warm-up to ~100★ via your network BEFORE the public push** — legitimate social-proof seeding that converts cold traffic (distinct from vote manipulation). Do this first.
- Still true & load-bearing: **never solicit upvotes** (HN voting-ring detector silently kills front-page eligibility; ToS bans bought/solicited stars). Say "check it out," never "upvote/star it."
- Chinese stack unchanged and high-ROI: **HelloGitHub 开源自荐** + **阮一峰周刊** (submitted) → cascade to V2EX/juejin/linux.do.

### 10c. #1 README lever still open: an above-the-fold demo
The single highest-leverage on-page change (named #1 in a 8k-star case) is an **animated GIF/screenshot of the interactive site + a results table in the first screen**. We have the hook + links but no top-of-fold visual. 👤/🤖: record a short GIF of the gateway-picker/cost-calculator; drop it above the fold. (OG/social-card image already = the cost-spread chart. ✓)

### 10d. Content strategy from the competitor scan (informs future adds, not just growth)
- **The highest-velocity 2026 segment is "free/cheap model routing for coding agents"** (Claude Code / Codex / Cursor / Cline). Nearly every fast riser (OmniRoute, 9router, ClawRouter, workweave/router, UncommonRoute) pitches this. Leaning into the `claude-code` / `token-saver` framing captures the segment AND earns inbound links from those repos. (6 such gateways added 2026-07-06, commit `b1b5d0c`.)
- **Benchmarks are the credibility engine** — OrcaRouter (RouterArena #1–2 + arXiv + wire) and UncommonRoute (accuracy/cost stats + Trendshift) grew on numbers. **Tightly link each router entry to its RouterArena score** — a differentiator no competitor list has.
- **Security/supply-chain is now a first-class buying axis** after the **LiteLLM PyPI supply-chain attack (March 2026)**. A short "Security & supply-chain" angle (audit tooling like `toby-bridges/api-relay-audit`, each gateway's provenance/signing story) would age well and match buyer attention. Candidate future addition.
- **Watch-list (below the add-bar for now):** ferro-labs/ai-gateway (195★, 2026-07-28) and Mirrowel/LLM-API-Key-Proxy (530★, flat) — keep watching. **Graduated:** mozilla-ai/otari 66→344★ in 3 weeks (added to Self-hosted 2026-07-28); CPA-Manager-Plus (added earlier as CLIProxyAPI companion). **Ruled out (re-checked 2026-07-28):** DEEIX-AI/DEEIX-Chat (1.1k★ but self-describes as an "enterprise AI workspace" — webchat/webui topics, not on the request path; fails the CONTRIBUTING add-bar, revisit only if it ships a standalone gateway mode).

### 10e. Ranked top-5 moves for a list at ~39★ (from the research)
1. **Above-the-fold demo GIF + headline results table** (§10c) — compounds every downstream click.
2. **One concentrated launch day (12–17 UTC)** firing 4–6 channels at once (r/LocalLLaMA + r/selfhosted + daily.dev + HN "Show HN: reproducible cost benchmark…" + a Dev.to methodology writeup), after warming to ~100★. Lead with data; never ask for upvotes.
3. **Fire the Chinese stack in parallel** — HelloGitHub + 阮一峰 (both submit-once), then V2EX/juejin/linux.do.
4. **Cross-list in the adjacent hype ecosystem** — awesome-llmops / awesome-mcp-servers / awesome-ai-agents (MCP adjacency), + sindresorhus/awesome when eligible.
5. **Monthly freshness cadence** — announce each benchmark re-run as a milestone; freshness is what kept awesome-llm-apps re-triggering Trending and what makes AI assistants cite you.

## 11. Five-axis scorecard maintenance (added 2026-07-06 — the observability axis)

The gateway scorecard is now **compliance · markup · security · stability · observability** (Part 4). Continuity rules:
- **Observability rubric = 5 evidence pillars** (metrics export · OTel trace export · per-key token/cost attribution · log export · dashboard), published in the Part 4 rubric table; what each pillar means in practice is Part 6. Score ≈ pillar count (partial = ½), halves allowed.
- **Evidence lives in `data/gateways_eval.json` → `observability_note`** (one line per gateway: which pillars, from which docs, reviewed date). Never change a score without re-checking the vendor docs and updating the note — same "sourced, not asserted" bar as pricing.
- **Re-review cadence:** rides the existing `check_freshness.py` 30-day gate on `gateways_eval.json` (`as_of`). On each refresh, spot-check the 3 most volatile: **Portkey OSS** (score jumps to ~4.5 the day the 2.0 branch ships a stable release — watch releases), **Kong OSS** (features drift Enterprise-ward; verify against the OSS source tree, not docs), **Requesty/Eden/Martian** (sparse docs — "not documented" ≠ absent, revisit).
- **New gateway added to the scorecard ⇒ must get all 5 axes** incl. an observability_note; `export_csv.py` exports the column (tests enforce the field).
- **Adding a 6th axis someday:** follow this precedent — publish the rubric row first, evidence-note per gateway in the JSON, sweep the Part-4 heading anchor repo-wide (10+ refs incl. compare/*.md sources → regenerate HTML), bump `as_of`.

## 12. Decision memo — sindresorhus/awesome submission (needs a 👤 call, 2026-07-27)

**The contradiction, on record for 16+ days:** the age gate passed 2026-07-11 and §9e-2/§9f still call this "the imminent high-value move," while `docs/awesome-lint-triage.md`'s 07-03 PoC concluded a lint-green pass requires **flattening every emoji-decorated table** — a UX sacrifice it recommended against. Net effect: the item is neither being done nor formally dropped. Pick one:

- **Option (a) — formally deprioritize per the triage PoC.** Keep the emoji tables and the double-link money anchors (they serve readers; the lint rules punish exactly what makes this list scannable). Accept losing the single biggest evergreen backlink. Agent then edits §9e-2/§9f to "deprioritized per triage PoC" and closes the loop.
- **Option (b) — accept emoji-flattening and let the agent drive lint-to-green.** Mechanical but large, and **the bill grows with the list**: verified 2026-07-27 by running `npx awesome-lint` against the live repo — **1,191 errors + 11 warnings**, up ~2× from the ~656 in the 07-03 triage snapshot (breakdown: 599 table-pipe-alignment · 247 awesome-list-item · 231 double-link · 108 table-cell-padding · 3 no-emphasis-as-heading · 1 emphasis-marker · rest singletons). Every content addition since 07-03 deepened the gap, and future growth keeps deepening it — so option (b) also implies keeping lint green forever (a CI gate), not a one-time cleanup. After green: 👤 reviews 4 other PRs + posts `unicorn`.

**Recommendation (agent):** (a). The doubling in three weeks is the argument — lint debt scales with exactly the growth we want, and the flattened tables would degrade the product for every reader to win one backlink. But this is a strategy call: 👤 decides; agent syncs whichever answer into §9e/§9f the same day.
