# Community maintenance — 2026-11-02

## Review contract

Review all open PRs and issues against `CONTRIBUTING.md` and the [curation policy](curation-policy.md). Inspect public primary documentation, preserve bilingual entries, strip tracking parameters, and distinguish operator claims from independent tests. A public catalog does not establish the identity of the model actually served. No submitted service was runtime-tested or granted independently verified status in this pass.

## Pull requests

The following contributions are integrated as actual Git merges retaining each reviewed PR head as a parent. README conflicts from daily refreshes were resolved against current main, with concise source-qualified descriptions, dated review notes and relay watch-list rows. Each merge passed regeneration, the existing unit suite and awesome-lint before commit. Contributor credit is preserved in each merge commit.

| PR | Entry | Evidence read on 2026-11-02 | Contributor |
| --- | --- | --- | --- |
| #163 | TokenLab | [Primary documentation](https://tokenlab.sh) | @bylinelog-bot |
| #164 | PromptUnit | [Primary documentation](https://www.promptunit.ai/docs) | @scorpion4ik26-lang |
| #165 | GenZi AI | [Primary documentation](https://ai.genzicorp.com/pricing) | @lunathetela |
| #166 | SinoGate | [Primary documentation](https://sinogate.ai/llms.txt) | @sinogate-admin |
| #167 | Vectoree | [Primary documentation](https://vectoree.ai) | @dolobster |
| #168 | Septor Labs | [Primary documentation](https://septorlabs.com/pricing) | @aideveloper03 |
| #170 | omni-route | [Primary documentation](https://github.com/attnstack/omni-route) | @attnstack |
| #171 | FastSubs | [Primary documentation](https://fastsubs.org/docs) | @fastsubai-byte |
| #172 | Nivana | [Primary documentation](https://nivana.one/docs/routing) | @aw3-technology |
| #173 | HopBase | [Primary documentation](https://hop-base.com/llms.txt) | @victor-zzh |
| #174 | BestLLM | [Primary documentation](https://bestllm.dev/) | @shia3420 |
| #176 | Cognipeer Console | [Primary documentation](https://github.com/Cognipeer/console) | @anilguleroglu |
| #177 | LowRouter | [Primary documentation](https://lowrouter.ai/docs/models/routing) | @obierlaire |

Review corrections:

- TokenLab (#163) and SinoGate (#166): remove UTM tracking links. TokenLab's own “Verified” delivery label is not an independent verification by this list.
- PromptUnit (#164): current documentation describes optional side-by-side checks, so do not assert these are mandatory before every model substitution.
- GenZi (#165), Vectoree (#167), Septor (#168), FastSubs (#171), HopBase (#173): omit volatile catalog counts, promotional credit amounts and untested billing guarantees. Septor's current pricing includes subscription tiers, so the prior no-seat-fee/cache-discount prose was not carried forward.
- omni-route (#170): the Go project is distinct from diegosouzapw/OmniRoute. Its cascades do not cover streaming; mock/local-model runs do not prove cloud-model quality or savings.
- Nivana (#172): describe automatic model selection without treating the routing quality/savings as independently measured.
- BestLLM (#174): use the current public brand; the PR calls it Maridian Gateway. Regional controls remain documented claims.
- Cognipeer (#176): retain AGPL Community licensing and identify SSO, realtime and cost optimization as commercial Enterprise features.
- LowRouter (#177): distinguish preference-based EU routing from hard scoped constraints; neither documented metadata nor carbon estimates establish independent residency/carbon verification.

Paidyun (#155) remains pending: Python retrieval of its catalog failed with TLS EOF and a separate curl attempt could not resolve the hostname. This is a limitation of this review environment, not proof of global downtime. The author has been asked for accessible primary documentation. The earlier review request remains unanswered in the inspected PR conversation.

## Issues

| Issue | Disposition |
| --- | --- |
| #162 TapVow | Add to Observability & cost tracking in both READMEs and track its public repository. Inspect the MIT license, README and gateway source at `cea11780b1e18540be2550ff1a133f2f6bb67489`. State static-price/final-bill limitations and lack of Responses/Codex support. Source inspection is not a production or budget-cap test. Close after publication. |
| #175 Related list | Add the inspected ai-gateways/awesome-ai-gateways directory to both Related lists sections. This is a scoped reference, with no reciprocity or endorsement requirement. Close after publication. |
| #146 Historical evidence | Still open. Reproduced seven overdue datasets: models.json is 49 days old, the other six are 63 days old. No `as_of` dates advanced. The existing [per-dataset backlog](maintenance-2026-10-28.md#snapshot-review-backlog) remains outstanding. |
| #11 Missing gateways | Standing discovery issue; inspected comments contain no new unresolved suggestions since the previous maintainer reply. Keep open. |
| #12 Canary results | Standing reproduction issue; no new independent result since the previous maintainer response. Keep open and retain self-reported status. |
| #13 Production experience | Standing invitation; inspected comments contain no new production evidence to incorporate. Keep open. |

## Publication checks

The directory now contains 248 distinct entries as counted by `scripts/count_entries.py`; the advertised coverage is rounded down to 240+. README translations, citation metadata, llms.txt and the Pages landing-page coverage are reconciled. The landing page now distinguishes daily stars/releases from historical evidence and links the review backlog.

Run `bash scripts/regen.sh`, `npx --yes awesome-lint`, `git diff --check`, and `python3 scripts/check_freshness.py --today 2026-11-02 --max-age-days 30`. The last command remains an expected failure until #146 is completed; content CI success must not be reported as freshness success.
