# Live movers: fresh-data replication of the frozen ranker — protocol, 2026-11-13

**Status: predeclared. Committed before any outcome in the fresh window was read.**
Only row counts, schema and label presence were inspected while writing this.
The run is allowed once. Its result is reported whatever it shows.

## Why this test

The [locked historical comparison](LIVE_MOVERS_RESULTS_20261027.md) asked whether
the nonlinear model M1 beat the simple model B2. That was inconclusive. The same
results contain a larger pattern that was never claimed because it was a
secondary comparison on a window that was not an untouched holdout:

- The stored live score (B1) and the displayed percentage move (B0) had negative
  within-day rank correlation with the forward directional return in all six
  board and horizon cells.
- The simple frozen price and volume ridge (B2) was positive in all six.
- On the primary cell, B2 minus B1 was +0.061 with a three-day block interval of
  +0.038 to +0.082.

F1–F5 cannot be tested yet: no multi-day 5s shadow sample exists. This pattern
can be tested now, because the model was frozen on 2026-10-27 and the local
collector has kept recording board episodes since then.

## Hypothesis

On board-entry episodes recorded after the model freeze, the frozen B2 ranker
orders five-minute outcomes better than the stored live score, by at least the
project's existing minimum effect of 0.02 IC, and B2's own rank correlation is
positive.

## Data

- Source: local ledger `~/.moonwalking/data/signal_outcomes.sqlite`, table
  `board_outcomes_v2`, read with `mode=ro` under one read transaction and copied
  unrevised to a private capture outside Git. The capture hash is recorded.
- **Primary holdout:** `entered_ts` from 2026-10-28T00:00Z up to, not including,
  2026-11-13T00:00Z. Every row is after the 2026-10-27 freeze and validation run.
- **Secondary window:** 2026-10-18T00:00Z to 2026-10-28T00:00Z, with the
  contract's 1,800s purge before its end. These rows are after the historical
  validation window and were never modelled. They are reported separately and do
  not affect the verdict.
- Eligibility: the frozen `freeze_live_contract.classify`, unchanged, run over
  the whole local ledger in `entered_ts,id` order so the 3,600s cooldown state
  is exact. Same snapshot and model version, same required inputs, both labels
  finite. Rejection counts by reason are reported.
- This is a different host from the production backup used historically. That
  is a limitation and also a harder replication.

## Models

B0, B1, B2 and M1 exactly as in
[the frozen specification](results/live_movers_contract_20261027/COMPARISON_SPEC.json).
The result file stores coefficients but not the winsor limits and scaling, so
B2 and M1 are refitted on the frozen train plus discovery rows with the frozen
alphas. The run refuses unless every refitted coefficient equals the stored one
to six decimals in all six cells. The locked validation rows are not scored
again. No parameter is fitted, selected or adjusted on the fresh data.

## Primary statistic and decision rule

Cell: `confirmation_3m_up/up`, `gross_return_5m`.

Statistic: mean across UTC days of the paired within-day Spearman
IC(B2) − IC(B1). A day counts with at least 20 rows and a nonconstant target and
predictions for all four models, so every model uses identical days and rows.
Days are weighted equally. Intervals are 95%: paired daily bootstrap and
three-calendar-day moving blocks, 5,000 replicates each, seed 20261113.

| Call | Condition |
|---|---|
| **Keep** | Difference ≥ +0.02, and both interval lower bounds > 0, and mean daily IC(B2) > 0 |
| **Drop** | Difference ≤ 0, or both interval upper bounds < +0.02 |
| **Inconclusive** | Anything else |
| **Insufficient** | Fewer than 12 scored days in the primary holdout; no call is made |

"Keep" means the ordering claim replicated on fresh data. It supports proposing
a board-ranking change for review. It is not a trading claim and changes no
live score, weight or production behavior.

## Secondary readouts, reported and not gated

1. Mean daily IC of B0, B1, B2 and M1 with both intervals, and the count of days
   on which each is positive.
2. The same paired differences in the other five cells and in the secondary
   window.
3. M1 − B2 on the fresh primary cell: the original preregistered question, on
   new data. Reported with its intervals; it does not change this test's call.
4. Rank-band tables for each ranker on the primary holdout: mean gross
   five-minute outcome per band, with the contract's 0.2, 0.5, 0.9 and 1.2%
   round-trip scenarios, and top band minus bottom band.

The prior expectation from the historical top bands is that no band clears
costs. A positive ranking result with negative band means is a ranking finding
and will be described that way.

## Limits fixed in advance

- Board-entry episodes with last-trade labels. No executable fills, spreads or
  whole-universe replay.
- One market stretch of about sixteen days. Regime coverage is narrow.
- Same-coin episodes on different boards are not independent. Strata are never
  pooled.
- No rerun, no second window, no changed threshold after the result is seen.
  A failed or interrupted attempt is recorded and blocks another run.
- The locked historical validation, the F1–F5 work, Codex's checkpoint files and
  every other worktree stay untouched.
