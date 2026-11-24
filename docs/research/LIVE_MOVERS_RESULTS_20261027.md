# Live movers: frozen historical comparison - 2026-10-27

**Decision: inconclusive under the preregistered primary gate.** The nonlinear
model M1 improves five-minute ranking over the simpler B2 by 0.01265 IC on
the 3m-up board. This is below the 0.02 minimum effect, and the three-day
block interval includes zero. This result does not support a live score or
ranking change. No retuning or second validation run was performed.

## Primary result

Primary population: `confirmation_3m_up/up`; target: gross five-minute
directional return. There are **24,457 eligible episodes across 14 UTC days**
(2026-10-04 through 2026-10-17). Every model uses the same rows and days;
there were no additional daily-group exclusions. IC is within-day Spearman
rank correlation, averaged equally across days; it is not a return percentage.

| Primary measure | Result |
|---|---:|
| Mean daily IC, percentage-move baseline B0 | -0.03392 |
| Mean daily IC, current live-score baseline B1 | -0.02819 |
| Mean daily IC, regularized price/volume model B2 | +0.03280 |
| Mean daily IC, nonlinear extension M1 | +0.04545 |
| Primary difference M1 minus B2 | +0.01265 |
| Paired daily-bootstrap 95% interval | [+0.00159, +0.02393] |
| Three-day moving-block 95% interval | [-0.00047, +0.02545] |
| Discovery difference M1 minus B2 | +0.01311 |
| Required minimum primary difference | +0.02000 |
| Preregistered verdict | **inconclusive** |

Both intervals use 5000 replicates and seed 20261027. Discovery was positive,
but the validation effect-size and block-interval conditions did not pass.
The more favorable comparisons against the existing score do not replace
the preregistered M1-versus-B2 primary test.

## Absolute outcomes and cost scenarios

Higher rank correlation is not evidence of positive executable returns.
The primary population's highest score band had the following **mean recorded
gross five-minute outcomes**. Bands use average-rank percentiles and keep
equal scores together; B1's top-band count therefore differs.

| Ranker, top band | Episodes | Gross mean | Minus 0.2% | Minus 0.5% | Minus 0.9% | Minus 1.2% |
|---|---:|---:|---:|---:|---:|---:|
| B0 percentage move | 4,891 | -0.15630% | -0.35630% | -0.65630% | -1.05630% | -1.35630% |
| B1 current score | 4,800 | -0.15011% | -0.35011% | -0.65011% | -1.05011% | -1.35011% |
| B2 price/volume | 4,891 | -0.04345% | -0.24345% | -0.54345% | -0.94345% | -1.24345% |
| M1 nonlinear | 4,891 | -0.03006% | -0.23006% | -0.53006% | -0.93006% | -1.23006% |

These are episode-level scenario means, not portfolio P&L or executable fills.
Costs are subtracted once from gross labels; stored already-net outcomes are
not used. No historical spread or fill path was reconstructed. In this
primary test, the fitted models rank relatively less-adverse observations
above more-adverse ones, while even their highest band has a negative mean.

## All declared strata and horizons

These are separate descriptive/secondary results; do not pool them or choose
a new primary result after seeing them. All six comparisons retain all
14 validation days and all eligible rows in the stated stratum.

| Stratum | Forward horizon | Episodes | B0 IC | B1 IC | B2 IC | M1 IC | M1-B2 |
|---|---|---:|---:|---:|---:|---:|---:|
| ignition_1m/up | 5m | 28,061 | -0.03756 | -0.03810 | +0.03169 | +0.02358 | -0.00811 |
| ignition_1m/up | 15m | 28,061 | -0.07411 | -0.07791 | +0.06234 | +0.06439 | +0.00204 |
| confirmation_3m_up/up | **5m primary** | 24,457 | -0.03392 | -0.02819 | +0.03280 | +0.04545 | +0.01265 |
| confirmation_3m_up/up | 15m | 24,457 | -0.07407 | -0.06565 | +0.07320 | +0.06882 | -0.00437 |
| confirmation_3m_down/down | 5m | 24,586 | -0.02128 | -0.02493 | +0.02371 | +0.02602 | +0.00231 |
| confirmation_3m_down/down | 15m | 24,586 | -0.05573 | -0.06595 | +0.05974 | +0.06258 | +0.00284 |

There is no short-selling conclusion from downside directional returns.
Neither fitted model's primary display scores saturated at 0 or 100 in this
sample. Complete bands, coefficients, per-day ICs, selected alphas and paired
comparisons are retained in the machine-readable artifacts below.

## Provenance, limits and next step

- [Frozen comparison specification](results/live_movers_contract_20261027/COMPARISON_SPEC.json)
  and [data contract](LIVE_MOVERS_DATA_CONTRACT_20261027.md) were unchanged.
- The [pre-fit review](LIVE_MOVERS_DRIVER_REVIEW_20261027.md) and corrected
  driver are committed at `7a55922`; clean-code verification is in
  [`results_verify_live_movers.json`](results/live_movers_comparison/results_verify_live_movers.json).
- Discovery ran on clean commit `5db135a`. Its choices were committed and
  pushed at `9747f94` **before** validation. The matching input/code hashes
  and selected settings are in
  [`results_discovery_live_movers.json`](results/live_movers_comparison/results_discovery_live_movers.json).
- The one-time validation ran from clean commit `9747f94`; see
  [`results_test_live_movers.json`](results/live_movers_comparison/results_test_live_movers.json).
  An exclusive attempt record remains in the local analysis directory and
  either the local or committed result blocks another run. NumPy 2.5.3 and
  pandas 3.0.6 were recorded for both phases.

Result QA confirms identical code/input hashes across verify/discovery/test,
matching frozen alphas, all six common-cohort daily means, row/band totals,
and single cost subtraction. All 11 frozen artifact hashes still match;
an existing real result refuses another attempt. The 23 targeted tests,
repository guardrails, report links and diff checks pass.

The cohort is persisted board-entry episodes with last-trade labels, not a
whole-universe replay. Earlier research may have examined overlapping dates;
this is locked historical validation, **not an untouched holdout**. Fourteen
validation days provide limited market-regime coverage. The ordinal score
is not a probability, and this study does not measure 30s warning lead time.

Keep the current scoring behavior while preserving these results. The next
evidence source is the separately running Coinbase side/coverage diagnostic,
followed, if its gates pass, by prospective 5s recording and the fixed-window
shadow study. Do not rerun this validation to search for a more favorable
formula or extend it with retrospective microstructure.
