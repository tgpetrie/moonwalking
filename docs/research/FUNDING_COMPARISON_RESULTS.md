# Funding comparison: results and interpretation

Written 2026-10-26 on branch `claude/funding-comparison` (from `codex/scoring-funding-audit-20261025` at `d7b1cfa`).
Research only: no production code, store, purchase, account, merge or deploy. Design: [`FUNDING_COMPARISON_PROTOCOL.md`](FUNDING_COMPARISON_PROTOCOL.md)
(frozen before any funding value was joined to a return; one amendment, A1, made after discovery and before the test phase). Code: `scripts/scoring_experiment/`
(`funding_fetch.py`, `funding.py`, `funding_run.py`, `make_funding_report.py`). The test phase was run once.

Legend: **[V]** measured here; **[H]** hypothesis or interpretation; **[A]** assumption.

## 1. Bottom line

1. **Adding Hyperliquid funding to the price/volume model does not improve the out-of-sample ranking, at either horizon.** On identical rows
   (127 approved products, 64,165 test-period coin-days, 93 test weeks, 99 coins per day on average), the incremental rank IC of M1 (baseline + funding)
   over M0-matched (baseline only) is **+0.0007 [-0.0005, +0.0020] at 1 day** and **-0.0024 [-0.0066, +0.0013] at 7 days** (97.5% week-block
   intervals; the 4-week moving-block intervals are nearly identical). The pre-registered minimum effect of interest was +0.02, so by the protocol's
   rule both horizons are **ruled out**: the data are precise enough to exclude any improvement as large as the threshold. [V]
2. **Nothing changes under the sensitivities:** same-day funding window (-0.002 and -0.001), excluding thin coins, excluding the 11 currently
   delisted Hyperliquid markets, excluding the four 1,000-unit contracts, each calendar year, and each decision weekday (labels non-overlapping): all within
   about +/-0.006 of zero. Adding funding to the *full-universe* baseline score (post-discovery secondary, amendment A1) also adds nothing: +0.0005
   [-0.0015, +0.0026] at 1 day, -0.0063 [-0.0189, +0.0062] at 7 days. [V]
3. **Funding on its own has a very small, barely detectable negative relation, which the model does not use.** The rolling funding z alone has IC -0.011
   [-0.021, -0.000] at 1 day and -0.018 [-0.034, -0.001] at 7 days in the test period (and the part of it not already explained by M0-matched, -0.012
   [-0.022, -0.001] and -0.019 [-0.035, -0.002]); the daily mean level alone is +0.012 [+0.002, +0.023] and +0.015 [-0.006, +0.036].
   These are secondary descriptive figures, unadjusted for the many cuts tabulated, with unstable signs between discovery and test at 1 day
   (-0.006 and +0.007 in discovery); their point estimates are at or below the 0.02 threshold. The fitted funding coefficients are tiny (about -0.001 at 1 day
   in rank-normal units) because the ridge penalty was at the top of its grid (10,000) in 20 of 32 monthly fits at 1 day and 11 of 32 at 7 days. [V] I would not build anything on them. [H]
4. **The matched baseline is itself a weaker comparator than the full-universe baseline.** Trained only on the funding-covered coins, M0-matched had no skill in
   discovery (IC about 0.00 at 1 day and -0.04 at 7 days, from March 2024, when the first fit was possible) and IC +0.044 and +0.023 in test. The baseline model fitted on all
   eligible coins and scored on these same rows had +0.054 / +0.027 (discovery) and +0.056 [+0.046, +0.067] / +0.012 [-0.005, +0.029] (test). The earlier
   133-candidate figures (+0.053 and +0.011) are therefore close to the recomputed matched-row figures for the full-universe model; the matched-trained model is
   noisier. [V]
5. **Extreme funding events show nothing usable.** Days with the rolling z at or above +2 (1,061 matched test events) or at or below -2 (3,323) were not
   distinguishable from clean same-coin controls or the matched universe at 1 or 7 days; every test status is inconclusive. [V]
6. **No look-ahead claim is stronger than the evidence.** The stored stamps fall a few milliseconds after the hour; the documentation does not say whether a
   stamp marks the end or the start of the averaging hour [U]. The primary design uses only prints stamped on the previous UTC day, which is safe either way. [V by construction]

This is a null result for the question asked. It does not show that funding is uninformative in general (see section 4), only that this funding feature adds nothing to
this score on these coins and dates.

## 2. What was collected [V]

* **127 products, 5,416 stored responses, 2,671,366 hourly rows**, all complete to the 2026-10-18 23:00 UTC print (requested to 2026-10-19 00:00 inclusive). The earliest
  print is 2023-05-12; the median product starts 2024-02-02. **Zero duplicate or out-of-order stamps**; 9,634 estimated missing hours in total (0.36%), the most
  for one product being 570 (`SUI-USD`). Eight products have under a year of rows (`AERO`, `AXS`, `AZTEC`, `CHIP`, `DASH`, `ICP`, `MEGA`, `SKR`).
  Original responses with request bodies, capture times and SHA-256 are kept locally (275 MB, `~/.moonwalking/data/hl_funding_20261025/`); the hashes and coverage are in
  `docs/research/results/funding_comparison/collection_summary.json`. The approved map (copied into the collection folder) is the audit's, unchanged.
* **Matched rows** (eligible baseline row, approved product, valid funding feature, at least 20 matched coins that day): 88,650 of the 121,365
  baseline-eligible rows of those products. The loss is the 30-day warm-up (25 valid days needed), 535 days with fewer than 20 prints, and the 20-coin rule (712 rows on early dates).
  Discovery has 23,032 matched rows at 46 coins per day (the model could first be fitted in March 2024, giving 44 evaluated weeks); test has 64,165 rows at 99 coins per day over 93 weeks.
* **A feature weakness found in the data:** 22.9% of matched rows have a daily mean exactly equal to the 0.00125%-per-hour base rate (funding pinned at the interest term).
  For such a coin the 30-day z of a tiny deviation is huge (the maximum possible with 30 values is 5.29, and 1.1% of rows have |z| of 4 or more); on the latest date
  three of the six most extreme z values (`ME`, `TURBO`, `GMT`, all about -5.3) are this artefact. The rank-normal step limits its influence on the model, but the
  extreme-event tables are partly contaminated. The level feature is not affected. A more robust funding feature (for example deviation from the base rate, or a
  winsorised z) would be a new hypothesis for a new protocol, not an adjustment to this one.

## 3. Protocol record and deviations

Frozen before any funding-return join; commit `c8b7cf7`. One post-discovery amendment (**A1**): discovery showed M0-matched has no skill in discovery, so a stacked secondary
analysis (full-universe baseline score with and without funding) was added; primary tests, thresholds and verdict rules were not changed, and discovery was rerun with the
addition (its primary numbers were unchanged: -0.0018 and -0.0023). The verdict rule (supportive / ruled out / inconclusive, MEI +0.02) was applied as written.
Other disclosures: (a) the prior for this experiment was low and I held it before running; (b) I had seen only one product's collection structure (AAVE) before freezing; (c) the
coefficient-sign condition for "supportive" is reported but was not needed because the result is "ruled out"; (d) the 133-candidate set was selected by having a Hyperliquid
perpetual, so this result applies to those coins, not the whole Coinbase universe.

## 4. Limits and what would change my mind

* **Only one funding feature was tested**: the 30-day rolling z of the daily mean, lagged a day. Level, 7-day means, changes, premium, or regime-conditional use were not part of
  the pre-registered tests. The base-rate pinning above weakens the z in exactly the thin, low-activity coins where crowding would matter least anyway.
* **Heavy shrinkage.** The ridge penalty selected by the inner validation was the largest on the fixed grid in 20 of 32 monthly fits at 1 day (11 of 32 at 7 days), which also shrinks a real small funding effect. The
  nested-model design cannot distinguish "no information" from "information smaller than the noise the penalty removes"; the bounded intervals (+/-0.002 at 1 day) say that any effect the *model* can use is
  below the threshold.
* **Backfilled funding is not a point-in-time record**, and the pairs are corroborated by price correspondence, not proof of identical on-chain assets.
* **Small and selected universe**: 127 coins with perpetuals; the 7-day M0-matched baseline is itself unstable (-0.04 in discovery, +0.02 in test).
* The selected cuts in the tables (regimes, years, weekdays) are descriptive; one of them (7-day, BTC-up regime, 17 weeks, +0.011 [+0.002, +0.019]) excludes zero, and with this many cuts one would
  expect such a result by chance. It is not a finding.

## 5. For Codex's independent review: where to look first

1. `funding.py` alignment (`decision_series` shifts the funding day forward by the offset; tests in `tests/test_funding_features.py`), the 20-print rule and the no-fill rule.
2. `funding_run.py`: that M0-matched and M1 share rows, folds, grid and purge (they call the same `walk_forward` on the same frame), and the residualisation and stacked analyses.
3. Whether the base-rate pinning should be handled in a follow-up feature (new protocol).
4. Whether the missing-hours count and delisting tails (no data after a market stops) are handled as claimed.
5. The statement that the primary result is unchanged by the amendment (compare the first and second discovery runs in git history).

## 6. Recommendation

Do not add the current funding feature to the score. Keep the free collector running if desired (cost is nil), but the next evidence-gathering step is not more funding data;
the baseline's own limits (reversal-driven, bottom-decile asymmetry, weak in liquid coins) are the larger open questions. If funding is revisited, pre-register a pinned-rate-robust
feature and a design that does not rely on a weak matched-only baseline (for example, evaluate the funding signal as a conditioner of the full-universe score on a longer sample).


## Tables (generated by `make_funding_report.py`; do not edit by hand)

Code commit for the test run: `6b7e652cbd99a4aea5291f9b72bb3fe78ce3a185`. Configuration hash: `12132c730d407fc9`.

### Matched rows (identical for every model)

| | Discovery | Test |
|---|---:|---:|
| Rows with a valid funding feature (all dates) | 89,362 | 89,362 |
| After the 20-coin-per-day rule (all dates) | 88,650 | 88,650 |
| Products with matched rows | 127 | 127 |
| First matched date | 2023-08-16 | 2023-08-16 |
| Last matched date | 2026-10-18 | 2026-10-18 |
| Matched rows in the phase | 23,032 | 64,165 |
| Weeks in the phase | 72 | 93 |
| Mean coins per day in the phase | 46.4 | 99.0 |
| Fewest coins on a day in the phase | 20 | 65 |
| Baseline-eligible rows of the 127 approved products | 121,365 | 121,365 |

First model fit (month): 1 day 2024-03-01, 7 day 2024-03-01.

### Primary tests: incremental rank IC, M1 (baseline + funding) minus M0-matched, identical rows, primary one-day lag

| Horizon | Phase | Mean IC M0-matched | Mean IC M1 | Difference [97.5% week-block interval] | 4-week moving-block interval | Verdict |
|---|---|---:|---:|---|---|---|
| 1 day | discovery | -0.005 | -0.007 | -0.002 [-0.005, +0.001] | [-0.005, +0.001] | (sign basis only) |
| 1 day | test | +0.044 | +0.045 | +0.001 [-0.000, +0.002] | [-0.000, +0.002] | ruled out |
| 7 day | discovery | -0.038 | -0.041 | -0.002 [-0.017, +0.011] | [-0.019, +0.011] | (sign basis only) |
| 7 day | test | +0.023 | +0.020 | -0.002 [-0.007, +0.001] | [-0.007, +0.001] | ruled out |

Test-phase verdict inputs: discovery difference positive? coefficient sign the same? Minimum effect of interest +0.02.

| Horizon | Discovery difference | Funding coefficient (mean of monthly fits) discovery | test | Same sign |
|---|---:|---:|---:|---|
| 1d | -0.002 | +0.0012 | -0.0012 | False |
| 7d | -0.002 | +0.0509 | +0.0031 | True |

### Rank IC of each model against the label on the matched rows (mean [97.5% interval])

| Horizon | Phase | M0-matched | M1 | Baseline model fitted on all eligible coins (M0-full) | Funding alone (z) | Funding level alone | Residualised funding (beyond M0-matched) |
|---|---|---|---|---|---|---|---|
| 1d | discovery | -0.000 [-0.025, +0.025] | -0.002 [-0.027, +0.025] | +0.054 [+0.034, +0.074] | -0.006 [-0.021, +0.011] | +0.007 [-0.008, +0.020] | -0.005 [-0.024, +0.017] |
| 1d | test | +0.044 [+0.030, +0.058] | +0.045 [+0.031, +0.060] | +0.056 [+0.046, +0.067] | -0.011 [-0.021, -0.000] | +0.012 [+0.002, +0.023] | -0.012 [-0.022, -0.001] |
| 7d | discovery | -0.044 [-0.094, +0.007] | -0.046 [-0.095, -0.001] | +0.027 [-0.012, +0.067] | +0.017 [-0.007, +0.044] | +0.021 [-0.008, +0.049] | -0.007 [-0.035, +0.019] |
| 7d | test | +0.023 [-0.008, +0.056] | +0.020 [-0.009, +0.051] | +0.012 [-0.005, +0.029] | -0.018 [-0.034, -0.001] | +0.015 [-0.006, +0.036] | -0.019 [-0.035, -0.002] |

### Incremental IC (M1 minus M0-matched), test phase, by weekday of decision (labels never overlap within a weekday)

| Horizon | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| 1d | +0.001 [-0.002, +0.004] | +0.001 [-0.002, +0.003] | +0.001 [-0.001, +0.004] | +0.001 [-0.002, +0.003] | +0.001 [-0.002, +0.004] | +0.001 [-0.002, +0.004] | -0.001 [-0.003, +0.001] |
| 7d | -0.003 [-0.009, +0.003] | -0.001 [-0.006, +0.004] | -0.002 [-0.007, +0.004] | -0.003 [-0.008, +0.002] | +0.000 [-0.007, +0.008] | -0.003 [-0.009, +0.002] | -0.006 [-0.012, -0.000] |

### Incremental IC by cut and sensitivity (test phase, difference M1 minus M0-matched)

| Horizon | Cut / variant | Difference [interval] | M0-matched IC | M1 IC |
|---|---|---|---|---|
| 1d | primary lag, all matched | +0.001 [-0.000, +0.002] | +0.044 | +0.045 |
| 1d | primary lag, excluding thin | -0.000 [-0.002, +0.002] | +0.021 | +0.021 |
| 1d | primary lag, excluding delisted hl markets | +0.001 [-0.000, +0.002] | +0.043 | +0.043 |
| 1d | primary lag, excluding k contracts | +0.001 [-0.000, +0.002] | +0.044 | +0.045 |
| 1d | same-day window (less conservative) | -0.002 [-0.004, +0.001] | +0.045 | +0.043 |
| 7d | primary lag, all matched | -0.002 [-0.007, +0.001] | +0.023 | +0.020 |
| 7d | primary lag, excluding thin | -0.003 [-0.009, +0.001] | -0.013 | -0.017 |
| 7d | primary lag, excluding delisted hl markets | -0.002 [-0.007, +0.001] | +0.023 | +0.021 |
| 7d | primary lag, excluding k contracts | -0.002 [-0.007, +0.001] | +0.024 | +0.022 |
| 7d | same-day window (less conservative) | -0.001 [-0.005, +0.002] | +0.022 | +0.021 |

### Incremental IC by BTC 30-day regime and calendar year (test phase)

| Horizon | Group | Blocks | Difference [interval] | Interpretable |
|---|---|---:|---|---|
| 1d | BTC down | 63 | +0.000 [-0.002, +0.002] | yes |
| 1d | BTC flat | 61 | +0.001 [-0.002, +0.003] | yes |
| 1d | BTC up | 17 | -0.000 [-0.005, +0.003] | yes |
| 1d | 2025 | 53 | +0.001 [-0.000, +0.002] | |
| 1d | 2026 | 41 | +0.001 [-0.001, +0.003] | |
| 7d | BTC down | 63 | -0.003 [-0.009, +0.002] | yes |
| 7d | BTC flat | 61 | -0.005 [-0.010, -0.001] | yes |
| 7d | BTC up | 17 | +0.011 [+0.002, +0.019] | yes |
| 7d | 2025 | 53 | -0.006 [-0.013, +0.001] | |
| 7d | 2026 | 41 | +0.002 [-0.000, +0.004] | |

### Extreme funding events (rolling z at least +2 / at most -2; percentage points of BTC-residual return)

| Event | Phase | Events (matched) | Coins / weeks | Horizon | vs clean same-coin controls | vs same-day matched universe | Frozen sign | Status (test) |
|---|---|---|---|---|---|---|---:|---|
| high funding | discovery | 1,311 (1,273) | 59 / 55 | 1d | +0.31 [-0.65, +1.32] | +0.33 [-0.28, +1.01] | +1 | - |
| high funding | discovery | 1,311 (1,273) | 59 / 55 | 7d | +1.25 [-1.94, +4.32] | +1.02 [-0.81, +2.98] | +1 | - |
| high funding | test | 1,100 (1,061) | 108 / 73 | 1d | -0.26 [-1.05, +0.55] | -0.02 [-0.72, +0.63] | +1 | inconclusive |
| high funding | test | 1,100 (1,061) | 108 / 73 | 7d | -1.46 [-4.18, +1.56] | -0.72 [-2.62, +1.60] | +1 | inconclusive |
| low funding | discovery | 686 (659) | 57 / 63 | 1d | -0.39 [-1.17, +0.32] | -0.35 [-0.93, +0.21] | -1 | - |
| low funding | discovery | 686 (659) | 57 / 63 | 7d | -0.88 [-3.29, +1.27] | -1.90 [-3.56, -0.63] | -1 | - |
| low funding | test | 3,363 (3,323) | 125 / 93 | 1d | +0.16 [-0.21, +0.54] | -0.10 [-0.35, +0.16] | -1 | inconclusive |
| low funding | test | 3,363 (3,323) | 125 / 93 | 7d | +0.52 [-0.98, +2.23] | -0.05 [-0.84, +0.89] | -1 | inconclusive |

### Per-product funding coverage and matched rows (test-phase run; all dates)

| Product | First funding | Last funding | Rows | Missing hours (est.) | Duplicates | Valid daily means | Matched rows |
|---|---|---|---:|---:|---:|---:|---:|
| 2Z-USD | 2025-10-02 | 2026-10-18 | 9,154 | 0 | 0 | 381 | 278 |
| AAVE-USD | 2023-07-18 | 2026-10-18 | 28,534 | 2 | 0 | 1189 | 1,164 |
| ADA-USD | 2023-10-22 | 2026-10-18 | 26,225 | 1 | 0 | 1092 | 1,067 |
| AERO-USD | 2025-11-11 | 2026-10-18 | 8,201 | 0 | 0 | 341 | 316 |
| ALGO-USD | 2024-12-04 | 2026-10-18 | 16,403 | 0 | 0 | 683 | 658 |
| ALT-USD | 2024-01-25 | 2026-10-18 | 23,936 | 1 | 0 | 997 | 481 |
| APE-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| APT-USD | 2023-06-30 | 2026-10-18 | 28,962 | 3 | 0 | 1207 | 1,182 |
| ARB-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| ASTER-USD | 2025-09-19 | 2026-10-18 | 9,469 | 0 | 0 | 394 | 243 |
| ATOM-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| AVAX-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| AVNT-USD | 2025-09-21 | 2026-10-18 | 9,424 | 0 | 0 | 392 | 315 |
| AXS-USD | 2026-01-18 | 2026-10-18 | 6,572 | 0 | 0 | 274 | 249 |
| AZTEC-USD | 2026-02-12 | 2026-10-18 | 5,967 | 0 | 0 | 248 | 159 |
| BADGER-USD | 2023-11-09 | 2026-10-18 | 25,784 | 1 | 0 | 1074 | 1,029 |
| BCH-USD | 2023-06-30 | 2026-10-18 | 28,962 | 3 | 0 | 1207 | 1,182 |
| BERA-USD | 2025-02-06 | 2026-10-18 | 14,866 | 0 | 0 | 619 | 530 |
| BIGTIME-USD | 2023-10-11 | 2026-10-18 | 26,477 | 1 | 0 | 1103 | 1,013 |
| BIO-USD | 2025-01-03 | 2026-10-18 | 15,682 | 0 | 0 | 653 | 355 |
| BLAST-USD | 2024-06-26 | 2026-10-18 | 20,263 | 1 | 0 | 844 | 639 |
| BLUR-USD | 2023-10-18 | 2026-10-18 | 26,309 | 1 | 0 | 1096 | 1,071 |
| BLZ-USD | 2023-09-12 | 2026-10-18 | 27,179 | 1 | 0 | 1132 | 1,107 |
| BNB-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 272 |
| BNT-USD | 2023-10-08 | 2026-10-18 | 26,551 | 1 | 0 | 1106 | 549 |
| BONK-USD | 2023-11-20 | 2026-10-18 | 25,535 | 1 | 0 | 1064 | 950 |
| CAKE-USD | 2023-12-30 | 2026-10-18 | 24,560 | 1 | 0 | 1023 | 404 |
| CHIP-USD | 2026-04-22 | 2026-10-18 | 4,317 | 0 | 0 | 180 | 91 |
| COMP-USD | 2023-07-18 | 2026-10-18 | 28,534 | 2 | 0 | 1189 | 1,164 |
| CRV-USD | 2023-05-15 | 2026-10-18 | 29,563 | 493 | 0 | 1229 | 1,204 |
| DASH-USD | 2026-01-18 | 2026-10-18 | 6,572 | 0 | 0 | 274 | 249 |
| DOGE-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| DOT-USD | 2023-09-12 | 2026-10-18 | 27,179 | 1 | 0 | 1132 | 1,107 |
| EIGEN-USD | 2024-04-30 | 2026-10-18 | 21,643 | 1 | 0 | 902 | 658 |
| ENA-USD | 2024-04-02 | 2026-10-18 | 22,305 | 1 | 0 | 929 | 411 |
| ENS-USD | 2024-01-05 | 2026-10-18 | 24,416 | 1 | 0 | 1017 | 983 |
| ETC-USD | 2024-01-12 | 2026-10-18 | 24,262 | 1 | 0 | 1011 | 986 |
| ETH-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| ETHFI-USD | 2024-03-21 | 2026-10-18 | 22,606 | 1 | 0 | 942 | 530 |
| FARTCOIN-USD | 2024-12-20 | 2026-10-18 | 16,020 | 0 | 0 | 667 | 404 |
| FET-USD | 2023-10-26 | 2026-10-18 | 26,119 | 1 | 0 | 1088 | 1,063 |
| FIL-USD | 2023-11-14 | 2026-10-18 | 25,675 | 1 | 0 | 1070 | 1,045 |
| FLOKI-USD | 2024-03-12 | 2026-10-18 | 22,823 | 1 | 0 | 951 | 607 |
| GMT-USD | 2023-11-26 | 2026-10-18 | 25,373 | 1 | 0 | 1057 | 1,032 |
| HBAR-USD | 2024-04-24 | 2026-10-18 | 21,785 | 1 | 0 | 907 | 882 |
| HYPE-USD | 2024-12-05 | 2026-10-18 | 16,382 | 0 | 0 | 682 | 166 |
| HYPER-USD | 2025-04-22 | 2026-10-18 | 13,064 | 0 | 0 | 544 | 223 |
| ICP-USD | 2025-11-08 | 2026-10-18 | 8,276 | 0 | 0 | 345 | 320 |
| ILV-USD | 2023-11-17 | 2026-10-18 | 25,591 | 1 | 0 | 1066 | 1,041 |
| IMX-USD | 2023-11-17 | 2026-10-18 | 25,591 | 1 | 0 | 1066 | 1,041 |
| INJ-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| IO-USD | 2024-06-12 | 2026-10-18 | 20,612 | 1 | 0 | 859 | 650 |
| IP-USD | 2025-02-13 | 2026-10-18 | 14,702 | 0 | 0 | 612 | 442 |
| JTO-USD | 2023-12-07 | 2026-10-18 | 25,110 | 1 | 0 | 1046 | 957 |
| KAITO-USD | 2025-02-20 | 2026-10-18 | 14,530 | 0 | 0 | 605 | 516 |
| LAYER-USD | 2025-02-11 | 2026-10-18 | 14,744 | 0 | 0 | 614 | 288 |
| LDO-USD | 2023-05-16 | 2026-10-18 | 29,562 | 486 | 0 | 1229 | 1,204 |
| LINEA-USD | 2025-09-01 | 2026-10-18 | 9,902 | 0 | 0 | 412 | 285 |
| LINK-USD | 2023-05-18 | 2026-10-18 | 29,555 | 437 | 0 | 1229 | 1,204 |
| LTC-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| ME-USD | 2024-12-10 | 2026-10-18 | 16,257 | 0 | 0 | 677 | 587 |
| MEGA-USD | 2025-10-22 | 2026-10-18 | 8,672 | 0 | 0 | 361 | 82 |
| MET-USD | 2025-10-10 | 2026-10-18 | 8,965 | 0 | 0 | 373 | 271 |
| MINA-USD | 2023-10-24 | 2026-10-18 | 26,168 | 1 | 0 | 1090 | 1,065 |
| MON-USD | 2025-10-08 | 2026-10-18 | 9,019 | 0 | 0 | 375 | 239 |
| MOODENG-USD | 2024-10-25 | 2026-10-18 | 17,366 | 0 | 0 | 723 | 594 |
| MORPHO-USD | 2025-01-17 | 2026-10-18 | 15,351 | 0 | 0 | 639 | 509 |
| NEAR-USD | 2023-11-01 | 2026-10-18 | 25,974 | 1 | 0 | 1082 | 1,057 |
| OGN-USD | 2023-10-01 | 2026-10-18 | 26,732 | 1 | 0 | 1114 | 1,068 |
| ONDO-USD | 2024-01-20 | 2026-10-18 | 24,056 | 1 | 0 | 1002 | 911 |
| OP-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| PAXG-USD | 2025-04-06 | 2026-10-18 | 13,448 | 0 | 0 | 560 | 439 |
| PENDLE-USD | 2023-10-26 | 2026-10-18 | 26,119 | 1 | 0 | 1088 | 481 |
| PENGU-USD | 2024-12-17 | 2026-10-18 | 16,089 | 0 | 0 | 670 | 523 |
| PEPE-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 615 |
| PNUT-USD | 2024-11-14 | 2026-10-18 | 16,892 | 0 | 0 | 704 | 553 |
| POL-USD | 2024-09-17 | 2026-10-18 | 18,281 | 0 | 0 | 761 | 685 |
| POPCAT-USD | 2024-04-28 | 2026-10-18 | 21,687 | 1 | 0 | 903 | 523 |
| PROMPT-USD | 2025-04-12 | 2026-10-18 | 13,317 | 0 | 0 | 555 | 467 |
| PROVE-USD | 2025-08-06 | 2026-10-18 | 10,532 | 0 | 0 | 439 | 350 |
| PUMP-USD | 2025-07-10 | 2026-10-18 | 11,180 | 0 | 0 | 466 | 371 |
| PYTH-USD | 2023-11-14 | 2026-10-18 | 25,656 | 1 | 0 | 1069 | 516 |
| RENDER-USD | 2024-07-31 | 2026-10-18 | 19,428 | 1 | 0 | 809 | 774 |
| REQ-USD | 2023-10-11 | 2026-10-18 | 26,481 | 1 | 0 | 1103 | 668 |
| REZ-USD | 2024-04-30 | 2026-10-18 | 21,634 | 1 | 0 | 901 | 502 |
| RSR-USD | 2023-12-05 | 2026-10-18 | 25,155 | 1 | 0 | 1048 | 442 |
| S-USD | 2025-01-17 | 2026-10-18 | 15,352 | 0 | 0 | 639 | 392 |
| SAND-USD | 2024-12-04 | 2026-10-18 | 16,403 | 0 | 0 | 683 | 658 |
| SEI-USD | 2023-08-15 | 2026-10-18 | 27,849 | 2 | 0 | 1160 | 1,071 |
| SHIB-USD | 2023-08-11 | 2026-10-18 | 27,935 | 2 | 0 | 1164 | 1,139 |
| SKR-USD | 2026-01-22 | 2026-10-18 | 6,477 | 0 | 0 | 270 | 181 |
| SKY-USD | 2025-09-17 | 2026-10-18 | 9,522 | 0 | 0 | 396 | 371 |
| SNX-USD | 2023-05-25 | 2026-10-18 | 29,535 | 297 | 0 | 1229 | 1,190 |
| SOL-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,204 |
| SPX-USD | 2025-01-07 | 2026-10-18 | 15,594 | 0 | 0 | 649 | 315 |
| STG-USD | 2023-10-26 | 2026-10-18 | 26,119 | 1 | 0 | 1088 | 342 |
| STRK-USD | 2024-02-14 | 2026-10-18 | 23,456 | 1 | 0 | 977 | 881 |
| STX-USD | 2023-05-18 | 2026-10-18 | 29,555 | 437 | 0 | 1229 | 1,204 |
| SUI-USD | 2023-05-12 | 2026-10-18 | 29,574 | 570 | 0 | 1229 | 1,160 |
| SUPER-USD | 2023-11-26 | 2026-10-18 | 25,373 | 1 | 0 | 1057 | 1,032 |
| SUSHI-USD | 2023-11-17 | 2026-10-18 | 25,591 | 1 | 0 | 1066 | 1,041 |
| SYRUP-USD | 2025-06-26 | 2026-10-18 | 11,514 | 0 | 0 | 479 | 454 |
| TAO-USD | 2024-02-19 | 2026-10-18 | 23,337 | 1 | 0 | 972 | 516 |
| TIA-USD | 2023-10-19 | 2026-10-18 | 26,280 | 1 | 0 | 1095 | 993 |
| TNSR-USD | 2024-04-08 | 2026-10-18 | 22,153 | 1 | 0 | 923 | 828 |
| TON-USD | 2023-10-22 | 2026-10-18 | 26,225 | 1 | 0 | 1092 | 150 |
| TRB-USD | 2023-09-17 | 2026-10-18 | 27,068 | 1 | 0 | 1128 | 1,102 |
| TRUMP-USD | 2025-01-18 | 2026-10-18 | 15,330 | 0 | 0 | 638 | 546 |
| TURBO-USD | 2024-05-31 | 2026-10-18 | 20,887 | 1 | 0 | 870 | 585 |
| UMA-USD | 2024-01-19 | 2026-10-18 | 24,091 | 1 | 0 | 1004 | 979 |
| UNI-USD | 2023-08-11 | 2026-10-18 | 27,935 | 2 | 0 | 1164 | 1,139 |
| VIRTUAL-USD | 2024-12-16 | 2026-10-18 | 16,123 | 0 | 0 | 671 | 83 |
| VVV-USD | 2025-01-28 | 2026-10-18 | 15,095 | 0 | 0 | 629 | 539 |
| W-USD | 2024-02-07 | 2026-10-18 | 23,621 | 1 | 0 | 984 | 384 |
| WCT-USD | 2025-04-15 | 2026-10-18 | 13,233 | 0 | 0 | 551 | 305 |
| WIF-USD | 2023-12-22 | 2026-10-18 | 24,751 | 1 | 0 | 1031 | 615 |
| WLD-USD | 2023-07-24 | 2026-10-18 | 28,376 | 2 | 0 | 1182 | 447 |
| WLFI-USD | 2025-08-23 | 2026-10-18 | 10,117 | 0 | 0 | 421 | 323 |
| XLM-USD | 2024-11-23 | 2026-10-18 | 16,677 | 0 | 0 | 695 | 670 |
| XPL-USD | 2025-08-22 | 2026-10-18 | 10,142 | 0 | 0 | 422 | 231 |
| XRP-USD | 2023-06-18 | 2026-10-18 | 29,253 | 3 | 0 | 1219 | 1,104 |
| ZEC-USD | 2025-10-02 | 2026-10-18 | 9,154 | 0 | 0 | 381 | 356 |
| ZEN-USD | 2023-11-09 | 2026-10-18 | 25,784 | 1 | 0 | 1074 | 959 |
| ZETA-USD | 2024-02-02 | 2026-10-18 | 23,758 | 1 | 0 | 990 | 901 |
| ZK-USD | 2024-06-12 | 2026-10-18 | 20,603 | 1 | 0 | 858 | 664 |
| ZORA-USD | 2025-04-23 | 2026-10-18 | 13,041 | 0 | 0 | 543 | 453 |
| ZRO-USD | 2023-09-07 | 2026-10-18 | 27,308 | 1 | 0 | 1138 | 761 |

### Sample scores on the latest decision date (ordinal percentile ranks among matched coins; not probabilities)

| Coin | Rolling funding z | Daily mean hourly funding (%) | 1-day M0 | 1-day M1 | 7-day M0 | 7-day M1 | Funding contribution (7-day) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OP-USD | +0.50 | +0.00125 | 44 | 37 | 27 | 13 | -0.026 |
| WLFI-USD | +0.62 | +0.00115 | 19 | 9 | 29 | 15 | -0.029 |
| S-USD | +0.64 | +0.00086 | 53 | 44 | 74 | 43 | -0.034 |
| ME-USD | -5.29 | +0.00085 | 72 | 80 | 26 | 61 | 0.034 |
| TURBO-USD | -5.27 | +0.00083 | 55 | 65 | 7 | 19 | 0.029 |
| GMT-USD | -5.26 | -0.00124 | 65 | 72 | 71 | 87 | 0.026 |
| ETH-USD | -1.44 | +0.00045 | 27 | 35 | 60 | 73 | 0.014 |
| SOL-USD | -2.26 | +0.00004 | 21 | 27 | 45 | 65 | 0.018 |
| XRP-USD | -1.27 | +0.00024 | 6 | 12 | 35 | 49 | 0.013 |
| DOGE-USD | -0.45 | +0.00107 | 24 | 22 | 53 | 50 | -0.002 |
| ADA-USD | -1.05 | -0.00084 | 31 | 31 | 63 | 74 | 0.011 |
| LINK-USD | -1.75 | -0.00008 | 28 | 30 | 64 | 77 | 0.016 |
| AVAX-USD | -1.31 | -0.00014 | 39 | 45 | 79 | 85 | 0.014 |

Date: 2026-10-18; matched coins that day: 119.


## Preservation (added 2026-10-26)

The result is fixed by the annotated tag `research/funding-comparison-2026-10-26` (commit `262df6d`). The raw responses are kept locally
and made read-only at `~/.moonwalking/data/hl_funding_20261025/`; `MANIFEST.json` there lists 5,546 files with sizes and SHA-256
(manifest SHA-256 `cf22c8f43151de4fc29a97afbef3ee299f9cfd341d990a317ced9d2de6f58d57`). Rerunning `funding_run.py` from those files and the frozen
daily panel reproduces the tables. A future funding feature (for example, robust to the base-rate pinning) needs a new protocol; this result is not to be re-tuned.
