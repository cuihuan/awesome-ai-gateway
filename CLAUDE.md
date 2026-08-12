# CLAUDE.md — working rules for this repository

Read this before changing anything here. It states what the project is *for*, so that
edits can be judged against a goal instead of taste.

## What this repository is

`awesome-ai-gateway` is not a link dump. It is meant to be **the integration point for the
AI-gateway space**: one place where a visitor can see the whole landscape — open-source
projects, hosted services, relays, the protocols they translate, and the evidence behind
every claim — without having to trust a vendor.

## The two goals — judge every change against these

**Goal 1 — a visitor understands the space at a glance.**
Within the first screen and a few clicks, a reader should get three things:

1. **The state of play** — what exists, what consolidated, what died, what is actually
   maintained. Not a catalogue: a picture.
2. **How to choose** — the decision path from *their* requirement to a specific name,
   with the trade-off stated.
3. **Where it is heading** — the direction of travel, with dated evidence and a stated
   way to be proven wrong.

If a change does not make one of those three clearer, it is decoration. Length is not
value: a section that makes the first screen slower to read is a net loss even if every
sentence in it is true.

**Goal 2 — grow stars and users, because that is the honest signal of Goal 1.**
Stars are not vanity here; they are the proxy for "this actually helped someone choose."
So optimise for the things that earn a star from an engineer in a hurry:

- A **reusable artifact** beats a list entry (a rubric, a computed table, a reproducible
  test, a calculator). People star what they will come back to.
- **A number nobody else publishes** beats a paraphrased vendor claim.
- **Being right when it is inconvenient** — naming an archived project, a CVE, a stale
  vendor promise — is what makes the rest of the list credible.

Never chase the metric directly: no star-for-star, no reciprocal-listing deals, no
inflating entry counts. Those raise the number and destroy the reason it means anything.

## Non-negotiable rules

**Language.** Everything is English — content, commits, issue and PR replies, code
comments. `README.zh-CN.md` and the other `*.zh-CN.*` files are the only Chinese surface,
and they are translations, never the source of truth.

**Evidence bar.** Every factual claim carries a source and a date, or it does not ship.
Vendor-run figures are labelled as vendor-run. If something cannot be verified, say
"unverified" — that is a status, not a verdict, and it is more useful than a guess.

**Numbers are generated, never typed.** Star counts live in `<!--s:owner/repo-->` markers
refreshed daily by CI; model prices come from `data/models.json` through
`scripts/cost_calc.py`. Hand-typing a count into prose is a bug — `scripts/test_update_readme.py`
fails the build for it, deliberately.

**Neutrality.** Descriptions state what a thing does, its licence and one differentiator.
No superlatives lifted from a project's own marketing, no affiliate links, no paid
placement. A submitter's enthusiasm is not evidence. The list is CC0 and takes no vendor
money — that independence is the product.

**Inclusion.** A project must sit on the request path, be publicly available, be active
within 12 months (or be labelled ⚠️ stale), and must not resell stolen quota or depend on
reverse-engineered private APIs. Routing someone's own subscription is allowed but always
carries the provider-ToS / account-ban flag.

**Prune as hard as you add.** Stale content costs a reader more than a missing entry.
Dead links, resolved caveats, superseded news, and duplicated explanation get deleted, not
archived in place. The list is judged by what a newcomer reads, not by how much it holds.

## Before you commit

```bash
bash scripts/regen.sh        # regenerates every derived artifact, then runs 259+ tests
npx --yes awesome-lint       # blocking CI gate
```

Mirror every content change into `README.md` **and** `README.zh-CN.md`. Content PRs are
usually applied by hand on `main` rather than merged, because the daily star refresh
conflicts with any content branch within a day — credit the author in the commit and in
the closing comment.
