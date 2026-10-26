# Funding comparison and DeFiLlama pilot: independent review

Checked 2026-10-26. Claude branch reviewed: `claude/funding-comparison`,
commit `262df6dba979acb7feb098c670e26cadca7b4120`. This review branch is
`codex/scoring-results-review-20261026`. No application or model feature changes.

## Decisions

1. **Accept the funding comparison as a null result for the feature and model
   tested. Do not add that funding feature to the numeric coin score.** This is
   not a finding that all funding features, derivatives data, or sources are useless.
2. **Keep DeFiLlama as a research candidate. Gemini's pilot and experiment draft
   are not ready to implement as written.** Direct endpoint measurements below
   correct catalog, history, missingness, aggregation and sample-size claims.
3. The actual numeric coin-score objective is unchanged. The existing baseline
   remains an experimental ordinal ranking; neither this null result nor a source
   coverage table establishes calibrated probabilities, buy recommendations or
   portfolio sizing.

## Funding result reproduced

The 35 inherited scoring, checkpoint, mapping and funding-feature tests pass.
The approved 127-product mapping matches the collection's copy. All **5,416
captured response hashes** match their saved original response text and the
committed collection summary. They contain **2,671,366 rows**. Product names,
request ranges, row counts, strictly increasing timestamps and unique UTC hours
check out. Every funding rate is finite. Four `premium` fields for ZRO are `NaN`;
premium is not a feature in this experiment, so these do not alter its result.
They must be treated as missing before any later premium-feature experiment.

The frozen price checkpoint's 496 hashes also verify. Independently rebuilding
the funding-matched frame produces **89,362** rows before the daily 20-coin rule,
**88,650** after it and **64,165 test-period rows**. Every per-product statistic
matches the result artifact. Independently refitting M0-matched and M1 on their
identical frame reproduces the test estimates, intervals and weekday cuts:

| Horizon | Incremental IC, M1 minus M0 | 97.5% weekly interval | Four-week moving-block interval |
|---|---:|---|---|
| 1 day | +0.000739128 | [-0.000466764, +0.001953106] | [-0.000466481, +0.001808573] |
| 7 days | -0.002408594 | [-0.006622552, +0.001304207] | [-0.007030450, +0.001494688] |

Both upper bounds are below the prespecified +0.02 minimum improvement. The
protocol's `ruled out` verdict is reproduced **at that threshold, for this model
and feature**. A much smaller relationship or a different funding design is not
ruled out. The weak matched-only comparator, heavy ridge shrinkage and
base-interest-rate pinning are appropriately disclosed. The primary lag excludes
funding stamped on the decision day, and there is no funding forward-fill.

The first discovery result is preserved in `e847811`; its primary mean and both
interval endpoints exactly equal the rerun stored in `6b7e652`. The stacked
secondary analysis is correctly disclosed as a post-discovery amendment. This
review independently reran the primary **test** comparisons, not the entire
secondary, sensitivity and discovery pipeline.

Evidence: `results/scoring_results_review_20261026/funding_input_verification.json`,
`funding_model_verification.json` and `discovery_amendment_verification.json`.

### Collector correction for future downloads

`funding_fetch.py` previously slept 1.1 seconds per request. A full 500-row
`fundingHistory` response costs 45 weight (20 plus 500/20), so the sleep setting
alone permits roughly 2,455 weight/minute, above the shared 1,200 limit. Response
latency and reactive backoff are not a sufficient planned budget.

This branch changes only the collector's pacing to **3 seconds**, at most 20 full
pages/minute or 900 weight/minute before response latency, leaving 300 for other
IP users. Concurrent consumers still share that budget. A simulated 31-request
paginated download verifies every rolling minute stays within the documented
limit; the old 1.1-second setting fails this check. This changes no historical
response, model, feature, result or hypothesis, and no download was repeated.

Source: [Hyperliquid rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits).

## DeFiLlama: measured corrections to Gemini's pilot

The current protocol and fee catalogs and 60 additional endpoint requests were
captured read-only from official public APIs: **64 request records, 52 successful
JSON responses and 12 endpoint errors**. An HTTP error for a particular alias
does not prove the vendor has no relevant data. Capture times, URLs and response
SHA-256 digests are in `results/scoring_results_review_20261026/MANIFEST.json`.
Complete raw responses are local at
`C:\Users\tgpet\.moonwalking\analysis\source_review_20261026` (not in Git).

The 20 products below are **Gemini's chosen cohort**. Only **12** belong to the
127-product approved funding map; the source research may use a broader cohort,
but must describe it accurately. This is measured endpoint availability, not
approval of every token-to-protocol association or an estimate for all 492 coins.

### Material factual corrections

- **Render is not devoid of DeFiLlama fundamental metrics.** Protocol
  `render-network-bme` (ID `7966`, category `DePIN`, Gecko ID `render-token`)
  has **503 fee/revenue observations** from 2025-06-03 through the frozen panel
  end, including six zero-fee days. Its TVL array is empty. Fee data without TVL
  is a different state from no fundamental data. The catalog's legacy ERC-20
  address needs migration-aware verification against RENDER and RNDR; their
  price histories remain separate.
- **Intuition exists in the catalog.** `intuition`, ID `5086`, symbol `TRUST`,
  category `Developer Tools`, returns **779 TVL observations** from 2024-08-31
  through 2026-10-18, of which **440 are zero**. This contradicts the claimed
  absence. The token/network association and usability of the zero-valued
  series still need review; a listing alone is not usable feature coverage.
- **The Aave parent endpoint works.** `/protocol/aave` returns parent ID
  `parent#aave` and an aggregate TVL series. Do not assume a parent must always
  be assembled manually, or add a parent aggregate to its children. Current
  catalog versions also include Aave V4 and other modules absent from the draft.
- **Parent IDs and URL aliases are not interchangeable.** Current Sky Lending
  uses `parent#maker`, not `parent#sky`. Tested parent-style aliases `maker`,
  `kamino-finance` and `bonkfun` returned HTTP 400; confirmed child endpoints
  `sky-lending`, `kamino-lend` and `bonkbot` returned data. These child series
  are labelled as children, not silently promoted to whole-parent totals.
- **History dates and missingness need actual series checks.** Sui's returned
  native-chain fee series begins **2024-07-01**, with two internal missing days,
  rather than at mainnet launch in May 2023. Drift parent fee data begins
  **2024-05-31** in the returned series. Uniswap's parent revenue series has
  **276 missing calendar days inside its observed span**, as well as 831
  explicitly zero-valued days. Missing is not zero.
- **Chain application fees are not native chain gas fees.** An overview scoped
  to Solana lists applications on Solana. The native chain fee series used here
  is `/summary/fees/solana`, category `Chain`; protocol and chain metrics must
  retain their different meanings.

Selected direct sources:
[Render fees](https://api.llama.fi/summary/fees/render-network-bme?dataType=dailyFees),
[Intuition](https://api.llama.fi/protocol/intuition),
[Aave aggregate](https://api.llama.fi/protocol/aave),
[Sui chain fees](https://api.llama.fi/summary/fees/sui?dataType=dailyFees),
[Uniswap revenue](https://api.llama.fi/summary/fees/uniswap?dataType=dailyRevenue).

### Availability table

Counts are unique UTC dates within 2022-01-01 through 2026-10-18. A gap count
is missing dates between that metric's first and last returned dates, not its
unavailable pre-inception history. Values on duplicate dates are reduced to the
last returned value for this availability profile. Raw stamps are retained locally.
These counts are not point-in-time coverage and do not establish token economics.

The complete table is
[`results/scoring_results_review_20261026/PILOT_TABLE.md`](results/scoring_results_review_20261026/PILOT_TABLE.md).
Per-metric dates, zeros, missingness, scope, identity-review flags, response hashes
and baseline-date overlap are in `DEFILLAMA_PILOT_MEASUREMENTS.json` beside it.
FET and PROVE were not found as token/protocol candidates in the captured current
catalogs; that is a bounded catalog observation rather than permanent exclusion
of all possible metrics. RNDR remains a separate legacy-token review case. BONKbot
is labelled as an ecosystem application, not the meme token's own TVL.

## Why Gemini's experiment draft is not ready to run

1. **The sample cannot satisfy the existing scoring protocol.** Even optimistically
   admitting migration and child-only cases, at most **13** pilot coins have
   simultaneous baseline-eligible rows with the proposed lagged TVL-change and
   fee-acceleration inputs. **Zero days** meet the baseline's 20-coin minimum.
   Expand and verify the cohort before running cross-sectional IC, or separately
   specify and review a different evaluation design. Do not quietly lower the
   requirement after seeing outcomes.
2. **The dates are inconsistent with the frozen baseline.** Discovery predictions
   start in 2023 and end 2024-12-23; the held-out decisions end 2026-10-10 so that
   seven-day exits remain inside the panel. The draft's discovery through
   2024-12-31 and test through 2026-10-18 must not be substituted.
3. **USD TVL growth is not net accumulation.** Valuation changes in deposited
   assets can raise USD TVL with no new deposits. DeFiLlama explicitly distinguishes
   price-adjusted inflows from TVL growth. Neutral feature names and price controls
   are needed before interpreting a price/TVL difference as speculative stretch
   or fundamental accumulation.
4. **The scoring rule and acceptance tests are only a proposal.** The +/-10-point
   modifier and thresholds are heuristic; they have not been validated or frozen
   in executable code. An OR gate between an IC improvement and a selected
   +10%-shock subgroup needs an explicit multiple-testing decision and uncertainty
   requirement. Use the established same-row, purged, dependence-aware comparison
   and freeze all details before joining new features to outcomes.
5. **One-day lag does not repair revisions or establish publication time.** Retain
   raw timestamps and observed fetch time, document unverified publication delays,
   and label retrospective results honestly. Do not add another writer to the
   existing point-in-time store as an incidental research step.

Definitions source: [DeFiLlama data definitions](https://docs.llama.fi/analysts/data-definitions)
(TVL/inflows, fees/revenue, parent aggregation and chain/app boundaries).

The pilot repeats a claim that paying $300 automatically resolves commercial
rights. This review does not establish that claim. Data access and the intended
display or redistribution rights require separate evidence; no purchase or
provider contact is part of this review.

## Next work and ownership

- **Claude:** preserve the null funding result as the completed test of this
  feature. Review the pacing-only correction. Prepare the next fundamentals
  experiment only after its measured, identity-reviewed cohort passes the minimum
  coverage gate. Use the strong full-universe baseline as a comparator on exact
  matched rows, with matched-trained comparisons separately identified; retain
  the frozen date and no-leakage rules. No funding retuning on this test sample.
- **Gemini:** use the measured corrections rather than repeating the broad audit.
  Expand to a candidate cohort of at least 30 token/protocol or native-chain
  associations with exact source IDs, verified token/network links, separate
  fees versus revenue definitions, and explicit parent/child scope. Mark all
  migrations and unverified relationships as held. The acceptance gate is measured
  eligibility of at least 20 assets on enough dates, not a catalog count of 30.
- **Codex:** review that coverage gate and frozen comparison design before any
  proposed source contributes to the numeric coin score. Coverage and predictive
  value remain different questions.

The new 31-request pacing regression joins the 35 inherited tests. All verification
artifacts are research outputs. No live score, production collector, input panel
or application store is changed.
