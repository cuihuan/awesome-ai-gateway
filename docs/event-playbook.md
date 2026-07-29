# Event-response playbook: turning gateway-market news into being the cited source within 24h

The list wins by being the **freshest neutral reference when an event spikes attention** — the thread
happens with or without us; the only question is whether the data people cite is ours. This doc is the
drill for the four recurring event shapes. Companion to `OPERATIONS.md` (§3 launch mechanics, §9f venues).

## 0. Iron rules (read before every event)

1. **DRAFT-ONLY.** Everything here produces drafts + repo commits. A human (👤) posts to HN/Reddit/anywhere,
   live and present to answer. Never automation, never scheduled posts (OPERATIONS §9f boundary).
2. **Comments are data contributions, not promotion.** We join the *existing* thread with facts from our
   tables. Never start the thread about someone else's news, never "check out my list" as the point of the
   comment. One link max, and only where it's the source of a number we quoted.
3. **Disclose.** Every comment: "I maintain an independent (CC0, no vendor money) gateway list" when linking it.
   Never mention or link the maintainer's own commercial products anywhere in these venues.
4. **No speculation beyond sourced facts.** Rumor stays labeled **unconfirmed** in print (see the live
   Stripe–OpenRouter entry in README "What's new" — that's the house style). If we can't source it, we
   write "unconfirmed" or nothing. Watch-list rules apply: no naming without reproducible evidence.
5. **Update the repo BEFORE commenting anywhere.** The comment cites the page; the page must already be
   current when the click lands. Stale money page = wasted spike.

## 1. Event classes — 24h checklists

### 1a. Acquisition / consolidation (live example: Stripe–OpenRouter talks, WSJ Jul 23)

The rumor is already covered correctly (README "What's new", 2026-07 entry, marked **unconfirmed**). IF it confirms:

**What's new entry — ready to fill** (insert at top of `README.md` § 📰 What's new; bump "Last review" date):

```markdown
- 2026-MM-DD · **Stripe acquired OpenRouter for ~$__B** (announced MM-DD; [closed / pending regulatory close])
  — ~__× the $1.3B mark from its May Series B, capping the consolidation line (Portkey→Palo Alto,
  Helicone→Mintlify, TensorZero shutdown). What changes for users: [ONLY what the announcement states —
  pricing/fee, ZDR/data terms, enterprise SLA; everything else: "not yet stated"]. ([WSJ](url), [Stripe](url))
```

**`compare/openrouter-alternatives-2026.md` update checklist** (the money page — do this first):
- [ ] Byline: bump *Last updated* date (it auto-stamps `dateModified` in the HTML — never hand-fake it).
- [ ] Intro "four honest reasons" → add reason 5: **post-acquisition uncertainty** (roadmap/terms under a
      payments company) — stated neutrally, sourced to the announcement.
- [ ] Re-verify the ~5.5% credit fee and free-ZDR/EU-region facts against openrouter.ai *that day*; change
      only what actually changed, keep the "What OpenRouter still wins at" section fair.
- [ ] "Compliance gaps" bullet: recheck whether SOC 2 / SLA status changed under the new owner.
- [ ] Rebuild + publish: `python scripts/build_compare_html.py` → commit → `python scripts/ping_indexnow.py`.
- [ ] Mirror one line into the consolidation "Trend ·" bullet at the bottom of What's new.

**Neutral HN-comment draft** (for the inevitable thread — 👤 posts, adapts to what's above it):

> Some context on what the fee landscape looks like around OpenRouter, since "will Stripe raise the take
> rate" is the obvious question: OpenRouter adds ~5.5% on credit purchases; Vercel AI Gateway, Cloudflare
> AI Gateway and Helicone pass through at 0% markup; Requesty ~5% (Frankfurt residency + ZDR); Eden AI
> ~5.5% (EU-default). On reliability: OpenRouter has no public SLA outside enterprise, and its Feb 17/19
> 2026 outages hit ~80–90% request-failure rates (their own postmortem) — vs Cloudflare's 100% SLA on
> Business+ and Vercel/Portkey at 99.99% enterprise. Numbers from an independent CC0 comparison I maintain
> (no vendor money, sources per row): [openrouter-alternatives page]. Disclosure: I maintain that list.

### 1b. Major outage / incident (a top-listed gateway or provider goes down hard)

- [ ] Wait for a primary source (status page, postmortem, provider announcement). No thread-hearsay in print.
- [ ] **Digest entry** (README § 📊 Latest evaluations, 🛡️ Reliability row — newest first, dated, sourced):

```markdown
| 2026-MM-DD | 🛡️ Reliability | **[Gateway] outage MM-DD (~Xh): [failure mode], [error-rate if published]%
of requests failed.** [One-line takeaway — usually: single-provider stacks have no fallback; multi-provider
routing is the mitigation]. | [postmortem](url) |
```

- [ ] What's new entry too if it's category-shaping (house style: the Feb 17/19 OpenRouter entry).
- [ ] If it moves the **stability** score: edit `data/gateways_eval.json` (score + evidence note + `as_of`),
      never a score change without a sourced note (OPERATIONS §11 bar). CSV re-exports via `export_csv.py`.
- [ ] Recheck any compare page that cites that vendor's SLA/uptime; fix + rebuild HTML if touched.
- [ ] **Reliability-data comment draft** (neutral, for the outage thread):

> Base rates, for calibration: a peer-reviewed study of 8 public LLM APIs (Chu et al., ICPE 2025) found a
> failure roughly every 2 days per API, median recovery ~1h, and only ~6% of incidents ever get a
> postmortem — [vendor] publishing one puts it in the honest minority. Datadog's Apr 2026 telemetry across
> 1,000+ orgs has rate limits alone causing ~⅓ of LLM errors. This is the standing case for multi-provider
> failover regardless of which gateway you front it with. (Sources collected in an independent list I
> maintain: [link]. Disclosure: I'm the maintainer.)

### 1c. Pricing change / free-tier rug-pull (provider kills or guts a free tier)

- [ ] Verify against the provider's **own** docs page (the file's rule: no third-hand listicle numbers).
- [ ] **`data/free_tiers.json`**: update the provider's row (`limits`, `catch`, `sources`, `confidence`);
      if the tier is *gone*, move it to the "recently discontinued" pattern (see Together AI precedent —
      we keep the tombstone, it's citable). Bump top-level `as_of`.
- [ ] Sync the README free-tier table row (CI test `scripts/test_free_tiers_data.py` + the ≤30-day
      freshness gate keep JSON/table honest — run `python -m pytest scripts/ -k free_tiers`).
- [ ] **Digest entry template** (🆓 Free tiers row):

```markdown
| 2026-MM-DD | 🆓 Free tiers | **[Provider] [killed / cut] its free tier MM-DD**: [old limit] → [new limit
or "gone — $X minimum prepaid"]; docs page [changed silently / announced]. Stale listicles will quote the
old numbers for months — verified against the provider's own page. | free_tiers.json |
```

- [ ] Rug-pulls of a *popular* tier also earn a What's new line. Comment angle (if a thread exists): the
      verified-limits table row + "which free tiers still work" — our most-asked question, per the README.

### 1d. Gateway shutdown / abandonment (repo archived, company folds, relay vanishes)

- [ ] Confirm: repo archived flag / official announcement / dead `/v1` endpoint (re-probe yourself).
- [ ] **Stale-flagging path**: `python scripts/check_stale_gateways.py` flags archived/no-push-12mo repos
      that aren't ⚠️-labeled. Manual completion: add the inline ⚠️ label in the entry's section, house
      style = the TensorZero line ("**Archived June 2026** ⚠️ (company wound down; repo read-only, code +
      forks remain)"). Don't delete the entry — labeled tombstones are part of the "won't rot" promise.
- [ ] If it's in the Top-gateways table or a compare page, update those too (and any "Start with" defaults).
- [ ] Hosted relay vanished → watch-list update instead (evidence rules from OPERATIONS §2 apply).
- [ ] **What's new template**:

```markdown
- 2026-MM-DD · **[Gateway] shut down / went unmaintained** — [repo archived MM-DD / endpoint dead since
MM-DD, verified by probe] ([funding/acquirer context if sourced]). [One neutral line on what users should
migrate to, by constraint, linking the relevant section]. ([source](url))
```

- [ ] Fold it into the consolidation "Trend ·" bullet — the shakeout narrative is ours to keep current.

## 2. Where the traffic spike lands (money page per class) — freshen it FIRST

| Event class | Money page | Freshness actions before any comment goes out |
|---|---|---|
| Acquisition/consolidation | `compare/openrouter-alternatives-2026.md` (+ its Pages twin) | checklist 1a; byline date → `dateModified`; rebuild HTML; IndexNow ping |
| Major outage | README digest + the data-retention/SLA rows; `compare/` page of the affected vendor | digest row shipped; scorecard note if scores moved; SLA claims re-verified |
| Free-tier rug-pull | README 🆓 verified-limits table (our strongest "internet's answers are stale" asset) | `free_tiers.json` + table row + `as_of` bumped; tests green |
| Shutdown | The section holding the entry + Top-gateways table; `best-self-hosted-ai-gateway-2026.md` if OSS | ⚠️ label in place; defaults/compare pages no longer recommend the dead project |

Citability = the page already answers the thread's question, dated *today*, with sources. That's what AI
answer engines and thread commenters both reward (OPERATIONS §9a: retrieval goes through Bing/IndexNow).

## 3. Response SLA

**Within 4h of confirmation (agent-doable, ship it):**
- Data file updated (`free_tiers.json` / `gateways_eval.json` / README row) with sources + `as_of`.
- What's new and/or digest entry live, unconfirmed parts marked unconfirmed. Commit, push, tests green.
- `python scripts/ping_indexnow.py` after the push (freshness signal into the Bing→AI-answer chain).

**Within 24h:**
- Affected compare page refreshed + HTML rebuilt (checklist 1a-style) — before any human comments.
- Comment drafts written for 👤 into `docs/launch-posts.md` (one per venue, channel-distinct, disclosure
  included), plus links to the HN/Reddit threads found. **👤 posts; the agent never does.**
- Ping 👤 with: what shipped, what's drafted, which thread is live and how hot.

**Never:** comment before the page is updated · post from automation · speculate past the source ·
start the promotional thread ourselves. Miss the 24h window? Ship the update anyway — freshness still
compounds via search/GEO even after the thread cools.
