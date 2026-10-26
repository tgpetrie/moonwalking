# Fundamentals experiment (DeFiLlama): prepared protocol and coverage gate

Written 2026-10-26 on branch `claude/fundamentals-prep` (from `codex/scoring-results-review-20261026` at `b9e48c3`).
**Status: prepared, not runnable.** The experiment may be run only after an identity-reviewed cohort passes the measured coverage
gate in section 3, as checked by `scripts/scoring_experiment/fundamentals_gate.py`, and after Codex has reviewed this design. No
fundamentals value has been joined to any return or label. This document freezes the design now so that it cannot be shaped by outcomes;
amendments go at the end with dates and reasons. Research only.

Legend: **[V]** verified; **[U]** unverified; **[A]** assumption; **[H]** hypothesis.

## 0. Inputs that decide this design

* The funding feature was a null at the +0.02 threshold (tag `research/funding-comparison-2026-10-26`); that result is not re-tuned or revisited here.
* Codex's review (`SCORING_RESULTS_REVIEW_20261026.md`) measured the Gemini pilot: at most 13 coins simultaneously usable and **zero
  days** meeting the 20-coin rule [V, by Codex]. It also set the ownership: Gemini expands and identity-reviews the cohort; Codex reviews the gate and
  this design; I run the experiment only after both.
* Lessons carried over: (1) the comparator must be the **strong full-universe baseline score on the exact matched rows**, with any
  matched-only model reported separately; (2) feature values pinned at a constant (for funding, the base rate) can make z-scores meaningless;
  (3) missing is not zero; (4) the frozen dates and no-leakage rules of the baseline apply unchanged.

## 1. Question and hypotheses

Does a fee- or revenue-trend input, from DeFiLlama, improve the out-of-sample ranking of BTC-residual returns beyond the full-universe
price/volume baseline score, on identical coins and dates? Prior [H]: low to moderate. Fundamentals plausibly matter more at horizons
longer than the baseline's 1 and 7 days, which this experiment cannot test without a new label (section 7).

* **H-F1 (primary):** `fee_trend` (defined below) adds incremental rank IC at **7 days**.
* Secondary (descriptive): the same at 1 day; `revenue_trend`; `usd_tvl_change`; extreme-trend events.

## 2. Cohort file (supplied by the identity review, not by this experiment)

`fundamentals_cohort.json`, one entry per Coinbase product (template: `docs/research/results/fundamentals_prep/COHORT_TEMPLATE.json`):

| Field | Meaning |
|---|---|
| `product_id` | Coinbase product, e.g. `AAVE-USD`. One entry per product; RNDR and RENDER separate; BTC excluded (benchmark). |
| `status` | `approved` (identity reviewed: token/network link verified, migrations resolved) or `held`. Only `approved` entries count toward the gate or enter the experiment. |
| `scope` | `parent`, `protocol`, `child_only`, `chain`, `ecosystem_app`, or other reviewed value. Never sum a parent with its children. |
| `source_ids` | exact DeFiLlama slugs or chain names per metric: `fees`, `revenue`, `tvl` (any may be absent). |
| `series_files` | the captured raw response for each metric, relative to the capture folder (stored byte-for-byte with fetch time and SHA-256). |
| `identity_evidence`, `reviewer`, `reviewed_at` | how the token/protocol or token/chain link was verified. |

Fees and revenue keep DeFiLlama's separate definitions; chain fees (category `Chain`, for example `/summary/fees/solana`) are native-chain metrics
and are **not** the same thing as the fees of applications on that chain. The `scope` is carried into every result table.

## 3. Coverage gate (measured; must pass before anything else runs)

Computed by `fundamentals_gate.py` from the approved cohort, the captured series and the **baseline-eligible rows only** (no labels, no outcomes).
A coin-day *counts* when it is a baseline-eligible row and its primary feature `fee_trend` is defined under the primary lag (section 4).

| Gate | Requirement | Why |
|---|---|---|
| G1 | At least **20 counting coins on at least 90%** of test-period decision days (2025-01-01 to 2026-10-10) | The baseline's 20-coin cross-section rule, applied to almost all test days rather than an average |
| G2 | At least **80 of the 93** test weeks contain a day with at least 20 counting coins | Enough independent weekly blocks for the week-block interval |
| G3 | At least **5,000 counting rows before 2024-06-01**, on days with at least 20 counting coins | The walk-forward needs 5,000 labelled training rows before its first fit (baseline rule); a fit by mid-2024 leaves a discovery period |
| G4 | At least **20 discovery weeks** (2024-06-01 to 2024-12-23) with a day of at least 20 counting coins | Discovery must exist to freeze signs before the test is read |
| G5 | Every counting product is `approved`; no `held` entry, no parent+child double counting, every series file hash-verified | Identity and provenance |

**Power note [A].** With about 20 coins a day, one day's rank IC has a standard error near 0.23; averaged over five days and 93 weeks, the
smallest detectable incremental IC is roughly 0.02-0.03 depending on how correlated the two models' daily ICs are. At 20 coins the experiment is therefore
at the edge of the +0.02 minimum effect of interest; **40 or more coins per day would be adequate.** The gate is a floor, not a recommendation.

The gate checker writes `GATE_REPORT.json`: per-day counting coins, per-product counting rows and first/last dates, and pass/fail for G1-G5. A failing
gate stops the experiment; the gate is not lowered after a failure. Coverage passing does **not** imply predictive value.

## 4. Features (fixed now)

**Timing.** DeFiLlama publication time and revisions are not verified [U]; backfilled history is a retrospective series, not a record of what was
known at the time. The primary design uses **data dated up to L = d - 2** for decision day d (decision at 00:00 UTC on d+1; entry at the open of d+1), i.e.
two full days of slack. Sensitivity: L = d - 7. Results are labelled *retrospective*. Raw responses, their fetch times and hashes are kept; nothing is written to the
point-in-time store.

**Daily values.** A day's value is the returned value for that UTC date (duplicate dates: the last returned value, as in Codex's profile, with the count reported).
Explicit zeros are zeros; **dates absent from the response are missing and never filled**.

* **`fee_trend` (primary):** `log(mean fees over L-29..L) - log(mean fees over L-59..L-30)`, each mean over present days only, **requiring at least 25 present
  days in each 30-day half and both means strictly positive**; otherwise missing (counted by reason). The quantity is a unitless trend, so protocol and chain
  scopes are comparable in rank; a sensitivity excludes `chain` scope.
* **`revenue_trend`:** the same on revenue.
* **`usd_tvl_change`:** `log(TVL_L / TVL_{L-30})` with both positive. **Named neutrally**: USD TVL moves with the price of deposited assets, so it is not net
  deposits; the model's own 30-day return input is the price control, and no "accumulation" or "stretch" label is attached to it.
* **Pinned or flat series:** a 60-day window in which more than half of the present values are identical (including all-zero) is set to missing for that
  feature and counted, so that a near-constant series cannot produce extreme ratios.
* Each feature is converted to a within-day rank-normal score among the counting coins (same convention as the 11 baseline inputs).

## 5. Models and comparisons (identical rows throughout)

Matched rows = baseline-eligible rows of approved products with `fee_trend` defined and at least 20 such coins that day.

| Name | Inputs | Role |
|---|---|---|
| **S0** | within-day rank-normal of the full-universe baseline prediction (walk-forward, out-of-sample) | primary comparator (strong) |
| **S1** | S0 + `fee_trend` | primary model |
| M0-matched / M1-matched | 11 baseline inputs / + `fee_trend`, trained on matched rows only | separately identified secondary comparison |
| Full baseline score itself | the baseline model's ranking on the matched rows | context |

Same ridge, penalty grid, monthly refit, 8-day purge and embargo as the baseline. Discovery: decision days through 2024-12-23 (first fit when the 5,000-row rule is met);
test: 2025-01-01 to 2026-10-10. Discovery may freeze only signs and regime cut points. The driver will refuse the test phase without a matching discovery result,
as in the funding driver.

## 6. Tests and verdicts

**One primary test:** incremental rank IC = weekly mean of daily (IC of S1 minus IC of S0) at **7 days**, **95%** week-block bootstrap interval, plus the 4-week
moving-block interval and the per-weekday non-overlapping check. Minimum effect of interest **+0.02** (unchanged).

* *Supportive:* test difference at least +0.02, both intervals exclude zero, discovery difference positive, `fee_trend` coefficient sign the same in discovery and test.
* *Ruled out:* upper bound of the week-block interval below +0.02.
* *Inconclusive:* anything else.

Secondary (reported, not tested for significance): 1-day horizon; revenue and USD-TVL inputs; M0/M1-matched; residualised IC of `fee_trend` beyond S0; scope cuts
(excluding chains; excluding child-only and ecosystem-app scopes); lag-7 sensitivity; BTC 30-day regimes (not interpreted under 15 blocks); events where `fee_trend`
is in the top or bottom decile versus clean same-coin controls and the same-day matched universe. Multiple secondary results are expected to cross zero by chance.

## 7. Not in scope

A 30-day or 90-day label (needs its own baseline extension and protocol), price-adjusted inflows, token unlocks, any paid DeFiLlama endpoint or licence
question, any change to the live score, purchases or provider contact. Display or redistribution rights for DeFiLlama data are a separate question that this
experiment does not answer.

## Amendments

(none)
