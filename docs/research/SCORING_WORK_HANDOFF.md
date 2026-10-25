# Scoring implementation handoff

## Objective and ownership

Build and evaluate an actual numeric per-coin score using existing BHABIT as the
baseline. Keep the coin's outlook, the reliability of the evidence, and risk
separate. Personal portfolio context affects guidance and attention.

| Owner | Work | First deliverable |
|---|---|---|
| Codex | Preserve inputs, input QA, reproducibility, independent review and eventual integration | Verified daily-input checkpoint and reproducible validator (completed below) |
| Claude | Scoring specification, offline price/volume baseline, continuation versus exhaustion evaluation; then the funding comparison | Reviewed protocol plus a runnable offline baseline and results with explicit limitations |
| Gemini | Correct vendor research; verify endpoint access, cost, quotas, history and measured coin coverage | Corrected evidence table and a short ranked source shortlist |
| Tom | Route these briefs to the existing Claude/Gemini chats and choose product priorities | Return their deliverables to this chat for comparison |

Claude and Gemini have not been dispatched automatically from this task. These
are handoff assignments for their existing chats. Work on separate branches and
worktrees; no production changes, purchases, account creation, mergers or
deployments are part of this checkpoint.

## Code and input locations

- Starting branch: `codex/scoring-data-checkpoint-20261024`, based on the research
  checkpoint `d51011d25b0729c9a6e9fc634da89a32f61d393a` (`claude/data-source-plan`).
- Codex workspace: `C:\Users\tgpet\Projects\Moonwalking-ScoringData`.
- Input root: `C:\Users\tgpet\.moonwalking\data\daily_panel_2022_2026`.
- Daily files: the input root's `raw` subdirectory. Keep its original
  `products.json` and `manifest.json` with the per-product responses.
- Verification records: `MANIFEST.json` and `QUALITY_REPORT.json` in the input root.
- Frozen funding candidates: `metadata\funding_candidates.json` in the input root.
- Hourly comparison source: `C:\Users\tgpet\.moonwalking\data\candle_archive.sqlite`
  (read-only).

The input root is local to this PC. A remote researcher must state missing access;
Git contains the validator and this summary, not the raw panel or databases.

## Completed input checkpoint

- Preserved **494 source JSON files**, totaling **27,870,453 bytes**; these contain
  **492 product files and 2 collection-metadata files**.
- All 494 source-file hashes still match their untouched originals. Verification
  also checks the frozen funding map and quality report (496 hashed files total).
- **473,039 usable daily candles**, spanning **2022-01-01 through 2026-10-18**.
- All 492 products contain candles; **11 products have 535 missing days inside
  their individual observed spans**. Gaps are not imputed, and their cause is not
  established here. There are no invalid rows, failed fetch windows or conflicting
  duplicate days in this snapshot.
- Native daily closes agree within 0.1% on **85,054 of 85,056 complete overlapping
  hourly days (99.99765%)**. The quality report lists both discrepancies.
- **53,605 partial hourly days are excluded from that comparison**, and one hourly
  day has no usable native daily row. The comparison rate does not imply the full
  archive has complete hourly coverage.
- All **133 funding ticker candidates** have daily series. Their identities and
  contract multipliers still require verification before joining funding.
- Eight focused tests pass, including corruption detection, identity mismatch,
  conflicting duplicate exclusion, incomplete-day handling and refusing overwrite.

The source panel includes inactive products from a product-list snapshot. This
alone does not prove a complete historical universe or remove survivorship bias.
Backfilled candles and funding are not point-in-time availability records.

## Claude assignment

Create your own branch/worktree from the starting branch above. Read the corrected
`BHABIT_SCORING_RESEARCH.md`, `TRIAL_READY_PLAN.md`, `FIRST_EXPERIMENT_SPEC.md`, and
the new quality report. Keep your implementation under `scripts/scoring_experiment/`
and its tests; leave Codex's `scripts/scoring_data/` and frozen inputs unchanged.

1. Review the experiment protocol before examining new outcomes. Resolve: (a) the
   claim of a survivorship-free universe versus selection of current funding
   candidates; (b) 30 days of eligibility versus the 90-day beta requirement;
   (c) two-sided funding hypotheses versus positive-only acceptance criteria; and
   (d) the mapping from an ordinal 0-100 score to any probability claim. A negative
   relationship may be informative after its sign is frozen in discovery.
2. Build an offline price/volume baseline first, with past-only features,
   next-period entry, same-row model comparisons, costs stated as scenarios and
   purged walk-forward splits. Keep the original live score as a comparator where
   it was actually recorded; do not invent missing minute-scale history from daily
   candles. Short-horizon continuation/exhaustion tests use actual recorded signal
   outcomes as a separate, explicitly selected population.
3. Produce numeric experimental ranks for defined horizons, factor contributions,
   coverage and risk context. Do not label a rank as a calibrated probability or
   turn an arbitrary coverage percentage into predictive confidence.
4. Only then evaluate funding incrementally on the identical verified subset and
   dates. The hourly funding backfill has not been downloaded by Codex. Do not
   duplicate existing point-in-time collectors or write to their stores.
5. Deliver code, input hashes, the frozen protocol, results, exclusions and a
   sample score table. Commit and push the separate branch for review; do not
   merge or deploy it.

## Gemini assignment

Correct the source audit before recommending subscriptions or integrations.
Verify with exact primary links and a checked-at date. Dashboard entitlements and
API entitlements must be separate. StockGeist's dashboard watchlist limits do not
establish API limits; Santiment restricted metrics and subscription types require
metric-specific access checks. Vendor universe size does not prove BHABIT coverage.

For each shortlisted source, report endpoint/metric, API plan and licence,
historical depth, freshness, quota cost per asset, identity mapping, measured versus
claimed coverage, monthly polling feasibility and a small incremental-value test.
Correct unsupported 100%-coverage and 100%-confidence claims. Keep news/attention
as candidates rather than permanently rejecting all text sources from one test.
Deliver a corrected evidence table and at most five priorities. Research only;
do not change application code, open accounts or start paid trials.

## Return gate

Codex independently checks the methods, code and evidence together. A measured
improvement can become an experimental product proposal. This checkpoint itself
does not validate forecasts, trading actions, sizing rules, or any live score.
