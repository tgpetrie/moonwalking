# Offline price/volume baseline: results and interpretation

Written 2026-10-25 on branch `claude/scoring-baseline` (from `codex/scoring-data-checkpoint-20261024`
at `9630c81`). Research only: no production code, store, network call, purchase or merge is
involved. The frozen design is [`SCORING_BASELINE_PROTOCOL.md`](SCORING_BASELINE_PROTOCOL.md)
(committed before any outcome was computed, amended A1-A6 before the test period was read, and corrected
after Codex's review of commit `2959072` as C1-C3; all are listed there and in section 7 below). Code and run instructions: `scripts/scoring_experiment/README.md`.

Legend: **[V]** measured in this run; **[H]** hypothesis or interpretation, not shown; **[A]** assumption.

## 1. Bottom line

1. **A baseline built only from past daily price and volume ranks coins' next-day and next-week
   BTC-residual returns better than chance, and the result held out of sample.** Rank IC was
   +0.087 at 1 day and +0.051 at 7 days in the test period (2025-01-01 to 2026-10-10, 93 weeks), with
   week-block 97.5% intervals that exclude zero, and the same sign and similar size in discovery
   (2023-01 to 2024-12). By the protocol's pre-set rule both are *supportive*. They also hold one decision
   weekday at a time (labels never overlap: interval excludes zero on 7 of 7 weekdays at each horizon)
   and under a 4-week moving-block bootstrap (1 day [+0.076, +0.097], 7 days [+0.031, +0.069]). [V]
2. **What the score captures is mostly short-term reversal, and it is asymmetric.** A one-feature
   reversal rule (`-r1`) reaches IC +0.075 at 1 day; the full model adds only +0.012 (interval
   [+0.007, +0.018]) and at 7 days is not distinguishable from reversal (+0.010, [-0.006, +0.025]).
   The edge sits in the **lowest-scored decile**. Actual next-day (open to open) returns: bottom decile
   -0.84% [-1.17, -0.49], deciles 2-9 between -0.15% and -0.01%, top decile +0.22% [-0.07, +0.50]. Actual 7-day
   returns: bottom decile -2.15% [-3.59, -0.61], deciles 2-9 between -0.93% and -1.33%, top decile -1.31% [-2.86, +0.18].
   (In BTC-residual log-return terms the bottom decile is -1.23% and -3.05%; the first version of this
   document mislabelled those residual figures as raw returns, see section 7.) So the top decile is
   not distinguishable from the middle at 7 days and only weakly positive at 1 day: long-only top
   quintile minus the equal-weight universe was +0.06 percentage points per week gross (interval
   -0.21 to +0.34) and negative after every cost scenario of 0.5% or more. [V] The score is useful as an
   *avoid / caution* ranking; there is no demonstrated selection edge at the top.
3. **The effect is concentrated in small, thin coins.** About 76% of eligible coin-days are "thin"
   (20-day median Coinbase dollar volume under $1M). In the funding-candidate subset the 7-day IC is
   +0.011 ([-0.008, +0.028]) and excluding thin coins +0.004 ([-0.024, +0.033]); only the 1-day IC
   survives (+0.053 and +0.035). [V] Part of the daily reversal in thin names is likely a bid-ask
   bounce rather than a tradable move [H].
4. **Exhaustion is supported at 1 day, and at 7 days only against the universe; continuation shows no advantage
   over the universe.** After a sharp one-day rise on heavy volume or a stretched price, coins underperformed the
   same-day universe by -1.44 pp (1 day) and -2.69 pp (7 days), and their own clean quiet days by -1.16 pp at 1 day
   (test period, residual returns, sign frozen in discovery). Against their own quiet days at 7 days the gap is
   -0.77 pp with an interval that includes zero ([-1.88, +0.33]), so that cell is inconclusive (its discovery sign
   was also positive, +0.39). Corrected **continuation** days (momentum in the top quintile, not stretched, volume between
   the 20-day median and 3x) are no different from the universe (-0.03 pp at 1 day, -0.32 pp [-0.70, +0.05] at 7 days);
   their advantage over the coin's own quiet days (+0.23 pp at 1 day, +1.09 pp at 7 days) is formally supportive at
   7 days but the same +1 to +2 pp appears for every event class, which points at the quiet-day comparator being a weak
   baseline rather than at a continuation effect [H]. [V]
5. **The live reads do not behave as labelled.** Among recorded production signals (13 weeks,
   exploratory), `CONTINUATION FAVORED` (up) was followed by negative 15- and 60-minute
   returns (-0.11% and -0.20%) and, against clean matched same-coin hours, by a negative point
   estimate (net R -0.13, interval [-0.29, +0.01]). `REVERSAL RISK RISING` (up) also fell
   at 15 and 60 minutes (-0.15%, -0.35%) but was not distinguishable from matched hours.
   All "up" signals give back about -0.08% and -0.17% over the same windows. [V]
6. **Risk is far more predictable than direction:** the trailing-volatility rank has IC +0.25 against
   the next-day absolute residual move (+0.23 at 7 days). This is expected and confirms the risk number is
   meaningful, not that it is informative about direction. [V]
7. **Evidence coverage cannot be evaluated on this input set.** 99.86% of eligible rows have coverage
   100, so there is no variation to relate to forecast quality. It remains a data-sufficiency
   label only. [V]
8. **Nothing here is a trading result.** Entry is the next daily open (which for thin coins may not be
   executable), costs are scenarios, and shorting is not assumed available. The results do not validate the live score, a
   probability, a trade rule or position sizing.

## 2. The score as built

| Component | Definition |
|---|---|
| **Numeric score, 1-100, per horizon** | Same-day percentile rank of the walk-forward ridge prediction among eligible coins. `score_1d` and `score_7d`. Ordinal; above 50 means a higher predicted BTC-residual, volatility-scaled return than the median coin that day. Not a probability and not "bullish" in absolute terms. |
| **Timeframes** | Decision at the close of day d, entry at the open of d+1; labels end at the open of d+2 (1 day) and d+8 (7 days). Inputs look back 1, 7, 30 and 90 days. |
| **Factor contributions** | Eleven inputs, each converted to a within-day rank-normal score; contribution = score x ridge coefficient; contributions sum exactly to the prediction (tested). Groups: momentum (`r1`, `r7`, `r30`, `res7`, `streak`), extension (`ext30`, `pos30`), volume/liquidity (`relvol`, `thin`), volatility/beta (`vol30`, `beta90`). |
| **Evidence coverage (0-100)** | Share of the 90-day window with candles (60%) plus share of the 11 inputs present (40%). Data sufficiency only. |
| **Risk** | Same-day percentile rank of 30-day volatility, daily volatility itself, and flags (`thin liquidity`, `very high volatility` above 8% per day). Reported beside the score, never folded into it. |
| **Typical fitted weights (test-period months, mean of monthly fits, rank-normal units)** | 1-day: `r1` -0.030, `relvol` -0.022, `ext30` -0.019, `streak` -0.012, `res7` -0.010, `pos30` +0.007. 7-day: `pos30` +0.057, `r1` -0.055, `vol30` +0.041, `ext30` -0.034, `res7` -0.034, `relvol` -0.033, `beta90` -0.021. Ridge penalty hit the top of the grid (10,000) in 15 of 22 monthly fits at 1 day and 18 of 22 at 7 days. [V] |

## 3. Reading the evidence

**What supports using it as a caution ranking.** The out-of-sample IC is positive in both years
(2025: +0.089 and 2026: +0.084 at 1 day; +0.050 and +0.052 at 7 days), in all three BTC 30-day trend
regimes with at least 17 weeks each, and the shuffled-label null is about zero (-0.003), so the pipeline
does not manufacture signal. Removing the momentum group (which contains `r1`) lowers the 1-day IC from
+0.087 to +0.067; removing any other group changes it by 0.005 or less. [V]

**What limits it.** (a) Mostly a reversal effect that a one-line rule nearly matches; (b) bottom-decile
driven; (c) weak or absent in liquid coins at 7 days; (d) the universe is a 2026 product-list snapshot
that includes inactive products but is not proven complete, and returns after a product's last candle
are unobserved, which can flatter coins that later collapsed or were delisted [H]; (e) the next-open entry
and cost scenarios are not an execution model.

**Continuation versus exhaustion, separately.** Two comparators are reported because they disagree. Against the
same-coin clean quiet days three of four event classes look better by about +1 to +2 pp at 7 days (continuation +1.09,
capitulation +1.11, downside continuation +1.90, but not exhaustion at -0.77); against the same-day universe only the
exhaustion and capitulation classes differ materially from zero at 7 days (-2.69 and -0.76 pp), and
continuation and downside continuation are flat (-0.32 and +0.05 pp). The simplest reading [H] is that a coin's own quiet
days are below-average days for BTC-residual returns, so any active day beats them; the peer comparison is the
stricter test. On it, exhaustion is negative at both horizons in both periods (discovery -0.96 pp and -1.99 pp;
test -1.44 and -2.69), capitulation (bottom-decile `r1` on heavy volume or stretched) did not bounce against the universe
(-0.17 pp at 1 day, -0.76 pp at 7 days), and neither continuation class shows a robust edge. Event rules were
fixed before outcomes (protocol section 6), but my prior belief in exhaustion came from earlier daily work
on the other branch, so this is not independent support. **The corrected continuation test is not a clean one-shot:** the
test period had been read under the uncorrected rule before the volume bound was fixed (section 7).

**Recorded signals versus the daily test.** The daily rules and the live reads are different things on
different time scales; the live reads' short-horizon behaviour is consistent with the earlier finding
that the live score is followed by give-back within an hour. Neither the daily nor the recorded evidence
supports describing the live `CONTINUATION FAVORED` read as favourable.

## 4. What I did not do or could not evaluate

* **Overlap checks** (added in correction C3): per-weekday and moving-block checks are in the tables; they do not
  change the primary result. They do not address cross-sectional dependence between coins on the same day.
* **Funding.** Not started, per the handoff order; see section 6.
* **Calibration to a probability** is intentionally absent; only bucket averages are shown.
* **Original live score at daily scale** cannot be reconstructed from daily candles and is not invented;
  it appears only in the recorded-signal check.
* **Pegged assets.** The 0.3% daily volatility floor removes stablecoin-like products but not every
  low-volatility product (for example `PAX-USD` at 0.74% daily volatility received a score on the latest
  date). A product-level exclusion list is needed before any product use.
* **Evidence coverage** has no variation here (see item 7 above).
* **Ridge penalty grid** edge (above); I did not widen it after seeing results.

## 5. Exclusions and protocol deviations

Exclusion counts are in the table below. Deviations from the original protocol are recorded in its
Amendments section (A1-A6) and are limited to: removing `BTC-USD` from the scored universe, a 0.3% daily
volatility floor, counting 11 inputs instead of 9, ending discovery on 2024-12-23, defining event status
without a minimum effect, and two diagnostic fixes after the first discovery run. The three corrections made
after the test results were reviewed (C1-C3) are described in section 7. The test phase was run once with the
original code and once more after the corrections; the primary results are identical in both.

## 6. Recommended next step: funding, on the identical subset

The baseline on the 133-coin funding-candidate subset is IC +0.053 at 1 day and +0.011 at 7 days
(test). A funding feature therefore has a small 1-day baseline to add to and essentially no 7-day
baseline signal in that subset. The comparison should be run exactly as pre-registered in
`FIRST_EXPERIMENT_SPEC.md`, with the corrections in the protocol (90-day eligibility, subset-only
claims, frozen sign) and Codex's identity check completed first, since the 133 are ticker candidates.

## 7. For Codex's independent review: where to look first

1. `panel.py` feature and label construction (past-only, next-open entry) and `tests/test_scoring_experiment.py`.
2. `model.py` purge (`cutoff = month start - 8 days`, rows with label ends before the first prediction day).
3. The pair of event comparators and the `match_controls` clean-control rule.
4. Whether the "supportive" verdict is robust to treating the test weeks as dependent (7-day windows overlap).
5. Thin-coin handling and whether a minimum-liquidity filter should define the primary universe.
6. Whether the 2026 snapshot's unobserved post-delisting returns could account for the lower deciles.

## 7. Corrections after Codex's review of `2959072`

Found by Codex's independent check and confirmed by me against the code and data. The test period was already
read when they were made. The model, features, penalties, scores and primary tests were not changed, and their
reruns reproduce the earlier values exactly (+0.087 and +0.051).

| | Problem | Effect of the fix |
|---|---|---|
| **C1** | The score-bucket tables labelled the BTC-residual log return as "raw return". | Both are now shown. Actual next-day returns: bottom decile -0.84% (was shown as -1.23%), top decile +0.22% (was +0.04%). Interpretation in section 1 rewritten: the top decile is weakly positive at 1 day but not distinguishable from zero; the asymmetry (bottom decile) stands. The quintile-versus-universe table already used actual returns. |
| **C2** | Continuation events omitted the protocol's lower volume bound (relvol >= 0), so about half were below-median-volume days. | Test-period continuation events fall from 16,904 to 8,319. Superseded values (in git at `2959072`): continuation versus clean controls +0.77 pp [-0.36, +1.81] at 7 days, now +1.09 pp [+0.05, +2.09]; versus the universe -0.13 pp, now -0.32 pp. Discovery signs were refrozen from the corrected discovery run; **one changed: exhaustion at 7 days versus clean controls is now frozen as +1 (discovery +0.39 pp, interval including zero)**, which is why that cell is "inconclusive" in test. |
| **C2 side effect** | Controls exclude days within 7 days of any event of the same coin. With fewer continuation events, more control days remain, so the *exhaustion* control comparisons also moved although the exhaustion rule did not change (1 day -1.26 to -1.16 pp; 7 days -1.67 [-2.90, -0.45] to -0.77 [-1.88, +0.33]). | The earlier statement that exhaustion passed both comparators at 7 days in test no longer holds against clean controls; it holds against the universe (-2.83 earlier, -2.69 now). |
| **C3** | The protocol's non-overlapping 7-day check was not implemented (not merely uncommitted). | Implemented: per decision weekday, and a 4-week circular moving-block bootstrap. All seven weekdays exclude zero at both horizons in the test period; moving-block intervals are in the primary table. |

Regression tests were added for each (volume bound, including a check that the old rule would have been caught;
residual versus actual return columns; weekday-label non-overlap; moving-block bootstrap). All 23 tests pass.

## 8. Sensitivity: 60 days of required history instead of 90 (protocol section 7, item 6)

Same code and frozen settings, rerun after the corrections with `--min-history 60` (results in `results_*_hist60.json`).
Test-phase model IC: **1 day +0.087 [+0.076, +0.097]** (90-day rule: +0.087), **7 day +0.051 [+0.036, +0.067]**
(+0.051). Exhaustion versus the universe stays negative (-1.42 pp at 1 day, -2.76 pp at 7 days); versus clean controls
-1.14 pp at 1 day and -0.78 pp [-1.92, +0.33] at 7 days (inconclusive). Continuation versus the universe is flat
(-0.04 pp, -0.29 pp). The eligibility rule does not drive the result. [V]

## Tables (generated by `make_report.py`; do not edit by hand)

Input manifest SHA-256: `f6d35da4a7423b1b035926c951b6365b52f804a92b1c3cd194bcd898cef2ba71`. Code commit for the test run: `d48a5c2f74e9f662f563bf56ae2415c0eff9f851`. Config hash: `782717dcf276b941`.

### Eligibility and exclusions (counts of coin-days; categories overlap)

| Reason | Coin-days |
|---|---:|
| no candle on the day (not yet listed, delisted, or a gap) | 388,945 |
| has a candle but under 90 days of history | 43,699 |
| enough history but fewer than 80 usable days in the 90-day window | 158 |
| a core input is missing | 29,421 |
| 30-day volatility below 0.3% per day (pegged) | 6,690 |
| BTC-USD benchmark row | 1,752 |
| **eligible for scoring** | 421,064 |

Days with fewer than 20 eligible coins dropped: 0 rows. Funding-candidate rows in the eligible set: 121,949.

### Primary tests: rank IC of the score against the label (97.5% week-block interval)

| Horizon | Phase | Blocks (weeks) | Mean IC [interval] | 4-week moving-block interval | Weekdays with interval excluding 0 (of 7) | Frozen sign | Verdict |
|---|---|---:|---|---|---:|---:|---|
| 1 day | discovery | 105 | +0.081 [+0.071, +0.092] | [+0.071, +0.091] | 7 | +1 | (sign frozen here) |
| 1 day | test | 93 | +0.087 [+0.076, +0.098] | [+0.076, +0.097] | 7 | +1 | supportive |
| 7 day | discovery | 105 | +0.044 [+0.023, +0.065] | [+0.020, +0.069] | 6 | +1 | (sign frozen here) |
| 7 day | test | 93 | +0.051 [+0.034, +0.067] | [+0.031, +0.069] | 7 | +1 | supportive |

### Non-overlapping check: model IC for one decision weekday at a time (test phase; each weekday's labels never overlap)

| Horizon | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| 1d | +0.074 [+0.047, +0.100] | +0.092 [+0.067, +0.118] | +0.057 [+0.031, +0.085] | +0.077 [+0.052, +0.101] | +0.083 [+0.055, +0.110] | +0.117 [+0.088, +0.145] | +0.111 [+0.089, +0.131] |
| 7d | +0.046 [+0.022, +0.071] | +0.045 [+0.020, +0.070] | +0.045 [+0.020, +0.071] | +0.045 [+0.015, +0.073] | +0.048 [+0.020, +0.072] | +0.057 [+0.030, +0.084] | +0.071 [+0.045, +0.097] |

### Same-row comparison (all eligible coins): IC and model minus comparator

| Horizon | Phase | Predictor | Mean IC [interval] | Model minus predictor [interval] |
|---|---|---|---|---|
| 1d | discovery | model | +0.081 [+0.071, +0.092] | |
| | | reversal (-r1) | +0.068 [+0.056, +0.080] | +0.013 [+0.007, +0.019] |
| | | residual momentum (res7) | -0.072 [-0.082, -0.060] | +0.153 [+0.136, +0.171] |
| | | extension (-ext30) | +0.060 [+0.047, +0.074] | +0.021 [+0.010, +0.032] |
| | | shuffled-label null | -0.003 [-0.009, +0.002] | |
| 1d | test | model | +0.087 [+0.076, +0.098] | |
| | | reversal (-r1) | +0.075 [+0.064, +0.086] | +0.012 [+0.007, +0.018] |
| | | residual momentum (res7) | -0.060 [-0.072, -0.048] | +0.147 [+0.128, +0.165] |
| | | extension (-ext30) | +0.046 [+0.033, +0.059] | +0.041 [+0.029, +0.053] |
| | | shuffled-label null | -0.003 [-0.009, +0.002] | |
| 7d | discovery | model | +0.044 [+0.023, +0.065] | |
| | | reversal (-r1) | +0.049 [+0.038, +0.061] | -0.005 [-0.025, +0.015] |
| | | residual momentum (res7) | -0.056 [-0.076, -0.035] | +0.100 [+0.072, +0.131] |
| | | extension (-ext30) | +0.036 [+0.010, +0.062] | +0.008 [-0.025, +0.040] |
| | | shuffled-label null | -0.001 [-0.007, +0.004] | |
| 7d | test | model | +0.051 [+0.034, +0.067] | |
| | | reversal (-r1) | +0.041 [+0.031, +0.051] | +0.010 [-0.006, +0.025] |
| | | residual momentum (res7) | -0.028 [-0.051, -0.005] | +0.079 [+0.048, +0.110] |
| | | extension (-ext30) | +0.016 [-0.013, +0.044] | +0.035 [+0.003, +0.067] |
| | | shuffled-label null | -0.004 [-0.009, +0.001] | |

### By universe subset (test phase, model IC)

| Horizon | All eligible | Funding-candidate subset | Excluding thin coins |
|---|---|---|---|
| 1d | +0.087 [+0.076, +0.098] | +0.053 [+0.041, +0.064] | +0.035 [+0.016, +0.052] |
| 7d | +0.051 [+0.034, +0.067] | +0.011 [-0.008, +0.028] | +0.004 [-0.024, +0.033] |

### Score buckets, 1-day label, test phase (mean over days, week-block interval)

| Score | Rows | Scaled residual [interval] | BTC-residual log return % [interval] | Actual open-to-open return % [interval] |
|---|---:|---|---|---|
| 1-10 | 20,010 | -0.192 [-0.231, -0.150] | -1.23 [-1.46, -1.01] | -0.84 [-1.17, -0.49] |
| 11-20 | 20,327 | -0.045 [-0.080, -0.004] | -0.24 [-0.42, -0.06] | -0.08 [-0.38, +0.21] |
| 21-30 | 20,192 | -0.053 [-0.093, -0.015] | -0.24 [-0.41, -0.07] | -0.15 [-0.43, +0.15] |
| 31-40 | 20,344 | -0.038 [-0.081, +0.003] | -0.18 [-0.35, +0.01] | -0.08 [-0.38, +0.21] |
| 41-50 | 20,354 | -0.019 [-0.057, +0.022] | -0.12 [-0.30, +0.05] | -0.03 [-0.31, +0.27] |
| 51-60 | 20,149 | -0.032 [-0.071, +0.005] | -0.17 [-0.34, +0.02] | -0.07 [-0.37, +0.21] |
| 61-70 | 20,268 | -0.022 [-0.060, +0.016] | -0.12 [-0.29, +0.06] | -0.04 [-0.35, +0.26] |
| 71-80 | 20,264 | -0.024 [-0.064, +0.016] | -0.11 [-0.30, +0.08] | -0.04 [-0.35, +0.28] |
| 81-90 | 20,249 | -0.021 [-0.059, +0.015] | -0.09 [-0.26, +0.08] | -0.01 [-0.31, +0.29] |
| 91-100 | 20,570 | +0.011 [-0.027, +0.049] | +0.04 [-0.13, +0.22] | +0.22 [-0.07, +0.50] |

Top decile minus bottom decile (scaled residual): +0.203 [+0.171, +0.236].

### Score buckets, 7-day label, test phase (mean over days, week-block interval)

| Score | Rows | Scaled residual [interval] | BTC-residual log return % [interval] | Actual open-to-open return % [interval] |
|---|---:|---|---|---|
| 1-10 | 20,005 | -0.575 [-0.787, -0.350] | -3.05 [-3.98, -2.06] | -2.15 [-3.59, -0.61] |
| 11-20 | 20,320 | -0.368 [-0.587, -0.153] | -1.72 [-2.73, -0.73] | -1.09 [-2.68, +0.47] |
| 21-30 | 20,184 | -0.359 [-0.581, -0.126] | -1.71 [-2.66, -0.72] | -1.21 [-2.88, +0.56] |
| 31-40 | 20,322 | -0.356 [-0.570, -0.140] | -1.73 [-2.77, -0.75] | -1.33 [-2.93, +0.24] |
| 41-50 | 20,328 | -0.322 [-0.544, -0.112] | -1.54 [-2.53, -0.65] | -1.06 [-2.73, +0.57] |
| 51-60 | 20,137 | -0.299 [-0.519, -0.082] | -1.46 [-2.49, -0.45] | -0.93 [-2.48, +0.66] |
| 61-70 | 20,235 | -0.323 [-0.537, -0.111] | -1.60 [-2.61, -0.56] | -1.09 [-2.75, +0.59] |
| 71-80 | 20,240 | -0.332 [-0.535, -0.144] | -1.71 [-2.62, -0.78] | -1.17 [-2.83, +0.38] |
| 81-90 | 20,218 | -0.309 [-0.493, -0.128] | -1.69 [-2.63, -0.73] | -1.04 [-2.60, +0.62] |
| 91-100 | 20,493 | -0.318 [-0.466, -0.169] | -2.12 [-3.00, -1.29] | -1.31 [-2.86, +0.18] |

Top decile minus bottom decile (scaled residual): +0.257 [+0.118, +0.380].

### Long-only top quintile versus the equal-weight eligible universe, 7-day horizon, weekly (percentage points per week)

| | Discovery | Test |
|---|---|---|
| Gross excess | +0.32 [-0.03, +0.67] | +0.06 [-0.21, +0.34] |
| After 0.2% round-trip cost (assumed) | +0.12 [-0.22, +0.48] | -0.14 [-0.42, +0.16] |
| After 0.5% round-trip cost (assumed) | -0.18 [-0.52, +0.17] | -0.44 [-0.71, -0.15] |
| After 0.9% round-trip cost (assumed) | -0.58 [-0.93, -0.23] | -0.84 [-1.12, -0.57] |
| After 1.2% round-trip cost (assumed) | -0.88 [-1.25, -0.52] | -1.14 [-1.42, -0.85] |

The top quintile is rebalanced fully each week; the benchmark is cost-free. Costs are scenarios, not measured.

### Test-phase breakdowns of model IC

| Horizon | Cut | Group | Blocks | Mean IC [interval] | Interpretable |
|---|---|---|---:|---|---|
| 1d | BTC 30-day trend | down | 59 | +0.082 [+0.064, +0.102] | yes |
| 1d | BTC 30-day trend | flat | 61 | +0.083 [+0.064, +0.100] | yes |
| 1d | BTC 30-day trend | up | 17 | +0.093 [+0.067, +0.122] | yes |
| 1d | calendar year | 2025 | 53 | +0.089 [+0.072, +0.105] | |
| 1d | calendar year | 2026 | 41 | +0.084 [+0.073, +0.096] | |
| 1d | evidence coverage | complete_100 (rows 100%) | 93 | +0.087 [+0.076, +0.098] | |
| 1d | evidence coverage | below_100 (rows 0%) | 0 | n/a [n/a, n/a] | |
| 7d | BTC 30-day trend | down | 59 | +0.040 [+0.016, +0.064] | yes |
| 7d | BTC 30-day trend | flat | 61 | +0.063 [+0.041, +0.083] | yes |
| 7d | BTC 30-day trend | up | 17 | +0.058 [+0.012, +0.113] | yes |
| 7d | calendar year | 2025 | 53 | +0.050 [+0.024, +0.073] | |
| 7d | calendar year | 2026 | 41 | +0.052 [+0.035, +0.070] | |
| 7d | evidence coverage | complete_100 (rows 100%) | 93 | +0.051 [+0.034, +0.066] | |
| 7d | evidence coverage | below_100 (rows 0%) | 0 | n/a [n/a, n/a] | |

### Risk rank (same-day trailing-volatility percentile) versus the forward absolute residual move, test phase

| Horizon | Mean IC [interval] | Thin-coin mean absolute move over non-thin |
|---|---|---:|
| 1d | +0.246 [+0.235, +0.257] | 1.02 |
| 7d | +0.234 [+0.221, +0.248] | 0.98 |

### Drop-one factor group (test phase, model IC with the group removed)

| Group removed | 1-day IC [interval] | 7-day IC [interval] |
|---|---|---|
| momentum | +0.067 [+0.057, +0.077] | +0.039 [+0.017, +0.059] |
| extension | +0.087 [+0.076, +0.098] | +0.049 [+0.031, +0.067] |
| volume_liquidity | +0.082 [+0.071, +0.093] | +0.047 [+0.029, +0.065] |
| volatility_beta | +0.086 [+0.076, +0.098] | +0.047 [+0.037, +0.058] |

### Continuation versus exhaustion events, daily panel (percentage points of BTC-residual return)

Each cell: event minus comparator, mean [97.5% interval over weeks]. Frozen sign from discovery.

| Event | Phase | Events (matched) | Coins / weeks | Horizon | vs clean same-coin controls | vs same-day universe | Frozen sign | Status (test) |
|---|---|---|---|---|---|---|---:|---|
| exhaustion | discovery | 8,983 (7,903) | 278 / 105 | 1d | -0.52 [-0.83, -0.21] | -0.96 [-1.19, -0.75] | -1 | - |
| exhaustion | discovery | 8,983 (7,903) | 278 / 105 | 7d | +0.39 [-0.90, +1.64] | -1.99 [-2.47, -1.53] | +1 | - |
| exhaustion | test | 10,575 (8,757) | 398 / 93 | 1d | -1.16 [-1.48, -0.85] | -1.44 [-1.72, -1.14] | -1 | supportive |
| exhaustion | test | 10,575 (8,757) | 398 / 93 | 7d | -0.77 [-1.88, +0.33] | -2.69 [-3.45, -1.83] | +1 | inconclusive |
| continuation | discovery | 7,060 (6,223) | 276 / 105 | 1d | +0.42 [+0.10, +0.73] | -0.03 [-0.20, +0.16] | +1 | - |
| continuation | discovery | 7,060 (6,223) | 276 / 105 | 7d | +2.18 [+0.91, +3.59] | -0.18 [-0.70, +0.37] | +1 | - |
| continuation | test | 8,319 (7,088) | 391 / 93 | 1d | +0.23 [-0.01, +0.48] | -0.03 [-0.18, +0.11] | +1 | inconclusive |
| continuation | test | 8,319 (7,088) | 391 / 93 | 7d | +1.09 [+0.05, +2.09] | -0.32 [-0.70, +0.05] | +1 | supportive |
| capitulation | discovery | 6,092 (4,832) | 278 / 105 | 1d | +0.13 [-0.17, +0.41] | -0.31 [-0.53, -0.10] | +1 | - |
| capitulation | discovery | 6,092 (4,832) | 278 / 105 | 7d | +2.76 [+1.52, +4.05] | +0.33 [-0.30, +0.98] | +1 | - |
| capitulation | test | 8,033 (6,212) | 396 / 93 | 1d | +0.03 [-0.21, +0.29] | -0.17 [-0.36, +0.04] | +1 | inconclusive |
| capitulation | test | 8,033 (6,212) | 396 / 93 | 7d | +1.11 [+0.08, +2.15] | -0.76 [-1.34, -0.16] | +1 | supportive |
| downside_continuation | discovery | 5,893 (5,244) | 271 / 104 | 1d | +0.61 [+0.34, +0.89] | +0.11 [-0.02, +0.25] | +1 | - |
| downside_continuation | discovery | 5,893 (5,244) | 271 / 104 | 7d | +2.97 [+1.59, +4.36] | +0.40 [+0.03, +0.77] | +1 | - |
| downside_continuation | test | 6,537 (5,457) | 388 / 93 | 1d | +0.36 [+0.13, +0.61] | +0.13 [-0.00, +0.28] | +1 | supportive |
| downside_continuation | test | 6,537 (5,457) | 388 / 93 | 7d | +1.90 [+0.78, +2.93] | +0.05 [-0.27, +0.38] | +1 | supportive |

### Recorded production signals (short horizon, exploratory, selected population)

Excess over clean matched same-coin non-signal hours; ATR units for r4/r12/r24; net R after an assumed 0.2% cost.

| Read | Matched / weeks | Outcome | Signal | Control | Excess [interval] | First half | Second half |
|---|---|---|---:|---:|---|---|---|
| CONTINUATION FAVORED (up) | 4,235 / 13 | netR21 | -0.158 | -0.067 | -0.131 [-0.287, +0.013] | -0.056 | -0.275 |
| CONTINUATION FAVORED (up) | 4,235 / 13 | r4 | +0.007 | +0.045 | -0.067 [-0.181, +0.030] | +0.013 | -0.230 |
| CONTINUATION FAVORED (up) | 4,235 / 13 | r12 | +0.124 | +0.193 | -0.120 [-0.417, +0.181] | +0.005 | -0.380 |
| CONTINUATION FAVORED (up) | 4,235 / 13 | r24 | +0.269 | +0.355 | -0.145 [-0.747, +0.439] | +0.080 | -0.642 |
| REVERSAL RISK RISING (up) | 3,727 / 13 | netR21 | -0.096 | -0.072 | -0.053 [-0.188, +0.055] | -0.003 | -0.111 |
| REVERSAL RISK RISING (up) | 3,727 / 13 | r4 | +0.074 | +0.037 | +0.028 [-0.088, +0.126] | +0.154 | -0.142 |
| REVERSAL RISK RISING (up) | 3,727 / 13 | r12 | +0.207 | +0.195 | +0.004 [-0.280, +0.293] | +0.184 | -0.235 |
| REVERSAL RISK RISING (up) | 3,727 / 13 | r24 | +0.338 | +0.391 | -0.027 [-0.588, +0.523] | +0.130 | -0.364 |
| BREAKDOWN CONFIRMED (down) | 3,937 / 13 | netR21 | -0.225 | -0.261 | +0.063 [-0.074, +0.198] | -0.045 | +0.155 |
| BREAKDOWN CONFIRMED (down) | 3,937 / 13 | r4 | -0.112 | -0.041 | -0.037 [-0.141, +0.091] | -0.097 | +0.058 |
| BREAKDOWN CONFIRMED (down) | 3,937 / 13 | r12 | -0.208 | -0.210 | +0.036 [-0.248, +0.339] | -0.155 | +0.302 |
| BREAKDOWN CONFIRMED (down) | 3,937 / 13 | r24 | -0.330 | -0.432 | +0.136 [-0.445, +0.741] | -0.101 | +0.559 |
| DOWNSIDE PRESSURE BUILDING (down) | 8,764 / 13 | netR21 | -0.282 | -0.268 | -0.004 [-0.119, +0.119] | -0.069 | +0.059 |
| DOWNSIDE PRESSURE BUILDING (down) | 8,764 / 13 | r4 | -0.132 | -0.041 | -0.076 [-0.186, +0.062] | -0.083 | -0.011 |
| DOWNSIDE PRESSURE BUILDING (down) | 8,764 / 13 | r12 | -0.239 | -0.205 | -0.028 [-0.282, +0.231] | -0.125 | +0.157 |
| DOWNSIDE PRESSURE BUILDING (down) | 8,764 / 13 | r24 | -0.382 | -0.373 | -0.038 [-0.579, +0.546] | -0.215 | +0.378 |

Graded 15- and 60-minute returns (within-signal only; percent, week-block interval):

| Population | Rows | 15 minutes | 60 minutes |
|---|---:|---|---|
| CONTINUATION FAVORED (up) | 64,090 | -0.108 [-0.132, -0.082] | -0.201 [-0.264, -0.137] |
| REVERSAL RISK RISING (up) | 233,203 | -0.153 [-0.217, -0.089] | -0.350 [-0.501, -0.222] |
| all_up_signals_for_context | 603,807 | -0.083 [-0.114, -0.053] | -0.172 [-0.253, -0.103] |

### Sample scores (latest decision date)

Ordinal percentile ranks among that day's eligible coins; not probabilities. Drivers are the three largest signed contributions to the 7-day prediction (rank-normal feature times coefficient).

| Coin | 1-day score | 7-day score | Largest 7-day drivers | Evidence coverage | Risk rank | Daily vol | Flags |
|---|---:|---:|---|---:|---:|---:|---|
| ETH-USD | 27 | 19 | r1 -0.06, vol30 -0.04, ext30 +0.02 | 100.0 | 1.8 | 1.9% | - |
| SOL-USD | 25 | 18 | r1 -0.06, vol30 -0.03, ext30 +0.02 | 100.0 | 5.2 | 2.47% | - |
| XRP-USD | 20 | 13 | r1 -0.07, vol30 -0.03, relvol -0.02 | 100.0 | 6.7 | 2.66% | - |
| DOGE-USD | 33 | 29 | r1 -0.04, relvol +0.02, streak -0.02 | 100.0 | 29.9 | 3.75% | - |
| ADA-USD | 35 | 39 | r1 -0.06, relvol +0.02, streak -0.02 | 100.0 | 35.3 | 3.89% | - |
| LINK-USD | 29 | 29 | r1 -0.05, streak -0.02, thin +0.01 | 100.0 | 30.4 | 3.75% | - |
| AVAX-USD | 31 | 63 | pos30 +0.06, r1 -0.04, streak -0.02 | 100.0 | 72.2 | 5.89% | - |
| RENDER-USD | 72 | 89 | pos30 +0.06, relvol +0.02, thin +0.01 | 100.0 | 48.5 | 4.55% | - |
| HONEY-USD | 84 | 100 | r1 +0.10, pos30 +0.04, vol30 +0.04 | 100.0 | 96.4 | 14.26% | thin liquidity, very high volatility |
| KAIO-USD | 70 | 100 | relvol +0.08, pos30 +0.07, r1 +0.05 | 100.0 | 99.0 | 18.07% | thin liquidity, very high volatility |
| DIMO-USD | 85 | 100 | relvol +0.14, vol30 +0.04, pos30 +0.03 | 100.0 | 97.4 | 15.55% | very high volatility |
| RSC-USD | 1 | 1 | r1 -0.16, relvol -0.14, ext30 -0.07 | 100.0 | 42.8 | 4.29% | thin liquidity |
| PAX-USD | 3 | 1 | r1 -0.12, pos30 -0.09, vol30 -0.06 | 100.0 | 0.3 | 0.74% | thin liquidity |
| GODS-USD | 5 | 1 | r1 -0.09, relvol -0.09, pos30 -0.04 | 100.0 | 22.7 | 3.52% | thin liquidity |

Date: 2026-10-18; eligible coins that day: 388.

