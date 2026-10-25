# Offline price/volume baseline: frozen protocol

Written 2026-10-25 on branch `claude/scoring-baseline`, **before any label or forward
return was computed** by the code in `scripts/scoring_experiment/`. The commit that adds
this file is the freeze point; later changes go in the "Amendments" section with a reason
and a date, never as silent edits. Research only: nothing here touches production, and
no score here is a calibrated probability, a trade instruction or a validated forecast.

Legend: **[V]** verified; **[A]** assumption; **[H]** hypothesis; **[D]** decision
made in this protocol.

## 0. Disclosure of prior knowledge

I have seen aggregate results from earlier work that bear on these hypotheses: the
live score's 15-60 minute relation (`BHABIT_SCORING_RESEARCH.md` C1) and another
session's daily study that reported coins trailing peers after +10% days (C9, not
re-verified). **The exhaustion hypothesis below is therefore not independent of what I
already expected.** I have not seen any result from this codebase's labels. The test
period is evaluated once (section 8).

## 1. Resolutions to the four protocol questions in the handoff

**(a) "Survivorship-free universe" versus current funding candidates [D].**
The daily panel was fetched from a 2026 product list that includes delisted products
(`status_at_collection`); that does not prove that every product that ever traded on
Coinbase is present, and the hourly archive has only currently listed coins. The accurate
description is **"2026 product-list snapshot including inactive products"**, not
"survivorship-free". Consequences: (1) the baseline universe is every product in the
panel with sufficient history, not the 133 funding candidates; (2) the funding
comparison is restricted to the funding-candidate subset, which was **selected by having
a Hyperliquid perp today** (itself related to liquidity and survival), so baseline results
are reported on the full universe **and** on that subset, and any funding result is
labelled subset-only; (3) the wording "survivorship-free" in `FIRST_EXPERIMENT_SPEC.md`
is amended here.

**(b) 30-day eligibility versus the 90-day beta [D].** The beta window is 90 days, so
**a coin-day is eligible only with at least 90 prior calendar days of history in which at
least 80 days have a usable candle (and the decision-day candle is present).** The
30-day figure in the first-experiment spec applied only to funding statistics and is
subsumed. Exclusion counts by reason are written to the results.

**(c) Two-sided hypotheses versus positive-only criteria [D].** All tests are two-sided
at the stated level. A **direction is chosen from the discovery period only and frozen
before the test period is read.** "Supportive" then means: same sign as frozen, absolute
effect at or above the minimum effect of interest, and the interval excludes zero. A
negative relationship that is stable out of sample is a valid finding (it can be used by
inverting its sign in guidance) and is not treated as failure; an unstable sign is
inconclusive.

**(d) Ordinal 0-100 score versus probability [D].** The score is the **same-day
percentile rank (1-100) of the model prediction among eligible coins**. It is
ordinal. No probability is stated. Reliability is shown only as realised average
outcome per score bucket in the test period with intervals, labelled "empirical,
bucket-level, this period only". Evidence coverage and risk are separate numbers
(section 4) and are not combined with the rank.

## 2. Data, timing and exclusions

* **Input:** `~/.moonwalking/data/daily_panel_2022_2026`, parsed with Codex's
  `daily_rows` rules (identical repeats collapsed, conflicting repeats excluded, bounds
  respected, no gap filling). The run verifies the checkpoint's `MANIFEST.json` hashes
  before reading and records the manifest digest in the results. `RNDR` and `RENDER` stay
  separate.
* **Decision time** for day d is 00:00 UTC on d+1; **entry is the open of d+1**; the
  1-day label ends at the open of d+2, the 7-day label at the open of d+8. A day whose
  next-day open is missing has no label and is excluded (counted).
* **Dollar volume** is `volume x close` (base volume times daily close) [A].
* **Costs** are scenarios (0.2, 0.5, 0.9, 1.2% round trip), all [A]; the real fee tier is
  unknown. No cost is described as actual.
* **Minimum cross-section:** days with fewer than **20 eligible coins** are excluded from
  scoring, IC and event definitions (counted in the results). In the continuation rule,
  "median among those" means the median `ext30` of that day's top-`res7`-quintile coins.
* **Panel end:** last candle 2026-10-18; last decision day with a 7-day label is
  2026-10-10.

## 3. Features, labels and model

All features use data up to and including the day-d close, never later.

| Feature | Definition |
|---|---|
| `r1`, `r7`, `r30` | log close-to-close returns over 1, 7, 30 days, divided by trailing 30-day standard deviation of daily log returns (`vol30`) |
| `vol30` | trailing 30-day std of daily log returns, as given |
| `relvol` | log of day-d dollar volume divided by the median dollar volume of the prior 20 days |
| `beta90` | slope of coin on BTC daily log returns over the prior 90 days |
| `res7` | `r7` minus `beta90` times BTC's 7-day log return, vol-scaled |
| `ext30` | log(close / 30-day mean close), divided by `vol30` |
| `pos30` | position of close in the 30-day high-low range (0-1) |
| `streak` | consecutive up (or down) closes ending at d, signed, capped at 7 |
| `thin` | median 20-day dollar volume below $1M (flag; also a risk input) |

**Labels:** `y1`, `y7` = log return from the open of d+1 to the open of d+2 (or d+8) minus
`beta90` times BTC's return over the same interval, divided by `vol30`; winsorised at the
1st and 99th percentile of the training window only.

**Model:** within each day, every feature is converted to a rank-normal score (no
cross-day information); ridge regression of the label on these scores, refit each
calendar month on rows whose label ended at least 8 days before the first prediction day
(purge and embargo), with the ridge penalty chosen by inner walk-forward error inside the
training window. Linear, so each prediction decomposes exactly into feature
contributions. Comparators, evaluated on the **same rows**: M-rev (`-r1`), M-mom (`res7`),
M-ext (`-ext30`), and a zero-information shuffle (labels permuted within day) to check the
pipeline produces a null.

**Score (0-100):** same-day percentile rank of the prediction, one score per horizon
(`score_1d`, `score_7d`). **Outlook** is the sign convention: above 50 means a higher
predicted residual return than the median coin that day; it is not "bullish" in absolute
terms.

## 4. Confidence and risk, defined separately

* **Evidence coverage (0-100)** = share of the 90-day window with usable candles (60%
  weight) plus share of the 9 inputs finite (40%). It describes **data sufficiency, not
  predictive confidence**. It is tested only descriptively (section 7, item 7); if it does
  not relate to forecast quality, it is reported as such.
* **Risk** = `vol30` percentile rank (same day) with flags for `thin`, a 30-day drawdown
  larger than 40%, and any missing-day count above 5 in the window. **Tested**: whether
  the risk rank predicts forward absolute residual return (it should, and is a more
  reliable claim than direction).

## 5. Primary tests (pre-registered)

Two primary tests: incremental rank IC of `score_1d` and of `score_7d` versus the label,
computed per day across coins (tie-aware), averaged within ISO calendar weeks (the block),
**97.5% bootstrap interval over weeks** (Bonferroni for two tests). Secondary and
descriptive: IC of each comparator; the same-row nested comparison (model versus each
comparator, difference in weekly IC); decile and top-minus-bottom-quintile spreads;
long-only top quintile versus the equal-weighted universe at 7 days with weekly
(non-overlapping, rebalance weekday rotated across all seven phases) rebalancing under
each cost scenario; results by BTC 30-day trend tercile **with block counts** (not
interpreted under 15 blocks); results on the full universe, on the funding-candidate
subset, and excluding thin coins.

**Minimum effect of interest:** IC 0.02 [A], from the cost arithmetic in
`FIRST_EXPERIMENT_SPEC.md`. **Verdicts** (per horizon): *supportive* (frozen sign, |IC|
at least 0.02, interval excludes zero, sign agrees in discovery and test); *ruled out*
(interval upper bound of |IC| below 0.02); *inconclusive* otherwise. Expected result
[H]: a small or null IC; the point of the baseline is to be the bar a later input has to beat.

## 6. Continuation versus exhaustion (separate tests, defined on past data only)

Event rules use only day-d information and are **mutually exclusive, exhaustion first**:

* **Exhaustion (E):** `r1` at or above the same-day 90th percentile **and** (`relvol`
  at or above 1.1, i.e. about 3x the 20-day median, **or** `ext30` at or above its
  same-day 90th percentile).
* **Continuation (C):** not E, and `res7` in the same-day top quintile, `ext30` at or
  below its same-day median among those, and `relvol` between 0.0 and 1.1 (normal
  to elevated, not a spike).
* The mirrored downside events (D-E: capitulation, D-C: downside continuation) are run
  with the same rules and reported, since the score is two-sided.

Outcomes: `y1`, `y7`. **Comparators:** (i) clean same-coin controls (non-event days of the
same coin at least 7 days from any event of the same coin, matched on `vol30` quintile
and BTC 7-day trend bucket, 1 to 4 per event, nearest in time not required), (ii) the
same-day eligible cross-section mean. **Inference:** day-block (ISO week) bootstrap
interval for event minus control, discovery and test separately, same two-sided rule as
section 1(c). Events cluster by day and by market regime, so event counts, distinct
coins and distinct weeks are reported beside every estimate.

**Recorded-signal population (separate, explicitly selected).** The production signal
store (latest local backup, opened read-only) holds `read_label`, a stored `live_score`
and graded 15-minute and 60-minute returns. The live system's own reads
`CONTINUATION FAVORED` and `REVERSAL RISK RISING` are compared with the **same-coin
non-signal base hours already built in `recon.sqlite`** where that table has the
needed horizon; otherwise only within-signal contrasts are reported. This population is
**selected by the live system having fired**, covers about 13 weeks, and is not a test of
the daily rules above. It is reported separately and not pooled.

## 7. Further checks (all reported, none a primary test)

1. Shuffled-label null (should give IC about 0). 2. Score with each feature group removed
(drop-one). 3. Coin-level concentration (largest single-coin share of event counts, and
results excluding BTC/ETH). 4. Results by calendar year. 5. Tie handling and sample
sizes by day. 6. Sensitivity to the 90-day-history rule (60 days). 7. Evidence-coverage
buckets: IC within each bucket. 8. Risk rank versus forward absolute residual return.

## 8. Sequencing and what "frozen" means

1. Commit this protocol and `config.json` (all constants). 2. Run the **discovery** phase
(predictions 2023-01-01 to 2024-12-31 from walk-forward fits). It may inform only the
sign convention (section 1(c)) and nothing else; **no thresholds, features or penalties
change after the discovery run** except bug fixes recorded under Amendments. 3. Record
the discovery output and the config hash. 4. Run the **test** phase once
(2025-01-01 to 2026-10-10); the driver refuses to run it unless the discovery output and
the matching config hash exist. 5. Anything learned from the test period is exploratory
and written as such.

## 9. Not in scope

Funding (it is next, on the identical verified subset, after this baseline has been
reviewed), any production code, any live score change, any new external data, trade
sizing, portfolio personalisation, and any statement about probabilities.

## Amendments

(none yet)
