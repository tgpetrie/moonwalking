# Live movers: fresh-data replication of the frozen ranker — results, 2026-11-13

**Call: keep.** On sixteen days recorded after the model freeze, the frozen
simple price and volume ranker (B2) ordered five-minute outcomes on the 3m-up
board better than the stored live score (B1) by +0.049 IC. The
[predeclared rule](LIVE_MOVERS_FRESH_REPLICATION_PROTOCOL_20261113.md) needed
+0.02 with both interval lower bounds above zero and a positive B2 correlation.
All four conditions held. The block interval's lower bound is +0.004, so the
pass is real but not wide.

This is a ranking finding. No band of any ranker had a positive mean gross
outcome, and nothing clears the smallest cost scenario. It changes no live
score, weight or production behavior.

## Primary result

Cell `confirmation_3m_up/up`, `gross_return_5m`, 2026-10-28 to 2026-11-12 UTC,
26,648 eligible episodes, 16 scored days. One run, from clean commit `7102185`.

| Measure | Result | Daily bootstrap 95% | Three-day block 95% | Days positive |
|---|---:|---|---|---:|
| **B2 − B1, primary** | **+0.0493** | +0.0134 to +0.0845 | +0.0043 to +0.0832 | 13 of 16 |
| Mean daily IC, B2 | +0.0260 | +0.0088 to +0.0424 | +0.0059 to +0.0395 | 14 of 16 |
| Mean daily IC, live score B1 | −0.0233 | −0.0429 to −0.0040 | −0.0446 to +0.0022 | 6 of 16 |
| Mean daily IC, percentage move B0 | −0.0261 | −0.0407 to −0.0109 | −0.0366 to −0.0071 | 2 of 16 |

The historical values were B2 +0.033, B1 −0.028 and a difference of +0.061.
The fresh values are a little smaller and have the same signs.

## What the ordering means in outcomes

Mean recorded gross five-minute outcome by rank band, lowest rank to highest:

| Ranker | Band 1 | Band 2 | Band 3 | Band 4 | Band 5 | Top minus bottom |
|---|---:|---:|---:|---:|---:|---:|
| B0 percentage move | −0.037% | −0.025% | −0.033% | −0.039% | −0.183% | −0.147% |
| B1 live score | −0.047% | −0.025% | −0.031% | −0.057% | −0.167% | −0.120% |
| B2 frozen ridge | −0.178% | −0.050% | −0.024% | −0.028% | −0.037% | +0.141% |
| M1 frozen nonlinear | −0.181% | −0.051% | −0.035% | −0.027% | −0.024% | +0.158% |

The effect sits in one band. Board entries with the highest live score or the
largest displayed move gave back about 0.17–0.18% over the next five minutes.
The other four fifths averaged −0.02% to −0.06%. At fifteen minutes the top
live-score band averaged −0.27% against −0.05% to −0.08% for the rest.

B2 mostly identifies that same group and ranks it last. Its own top band is no
better than the middle. The supported statement is an overextension warning:
the highest-scored entries on the mover boards retrace the most. It is not
evidence that any group goes on to rise.

## Every declared cell, both windows

B2 − B1 was positive in all twelve cells. B0 and B1 were negative in all twelve.

| Window | Stratum | Horizon | Episodes | Days | B1 IC | B2 IC | B2 − B1 | Block 95% | Days positive |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| Primary | ignition_1m/up | 5m | 30,356 | 16 | −0.033 | +0.035 | +0.068 | +0.032 to +0.088 | 14/16 |
| Primary | ignition_1m/up | 15m | 30,356 | 16 | −0.072 | +0.067 | +0.140 | +0.100 to +0.178 | 16/16 |
| Primary | confirmation_3m_up/up | **5m** | 26,648 | 16 | −0.023 | +0.026 | **+0.049** | +0.004 to +0.083 | 13/16 |
| Primary | confirmation_3m_up/up | 15m | 26,648 | 16 | −0.062 | +0.077 | +0.139 | +0.092 to +0.188 | 15/16 |
| Primary | confirmation_3m_down/down | 5m | 26,563 | 16 | −0.031 | +0.029 | +0.059 | +0.017 to +0.120 | 13/16 |
| Primary | confirmation_3m_down/down | 15m | 26,563 | 16 | −0.077 | +0.085 | +0.162 | +0.120 to +0.221 | 16/16 |
| Oct 18–27 | ignition_1m/up | 5m | 20,047 | 10 | −0.027 | +0.024 | +0.051 | +0.022 to +0.070 | 8/10 |
| Oct 18–27 | ignition_1m/up | 15m | 20,047 | 10 | −0.068 | +0.051 | +0.120 | +0.096 to +0.130 | 10/10 |
| Oct 18–27 | confirmation_3m_up/up | 5m | 17,105 | 10 | −0.019 | +0.022 | +0.040 | +0.026 to +0.050 | 8/10 |
| Oct 18–27 | confirmation_3m_up/up | 15m | 17,105 | 10 | −0.051 | +0.065 | +0.116 | +0.099 to +0.125 | 10/10 |
| Oct 18–27 | confirmation_3m_down/down | 5m | 17,186 | 10 | −0.022 | +0.014 | +0.036 | +0.002 to +0.058 | 8/10 |
| Oct 18–27 | confirmation_3m_down/down | 15m | 17,186 | 10 | −0.056 | +0.064 | +0.120 | +0.102 to +0.127 | 10/10 |

The fifteen-minute cells are the strongest: the gap is +0.12 to +0.16 and B1
was negative on at least fifteen of sixteen primary days in each. Fifteen
minutes was not the predeclared primary and does not change the call. Strata
are not pooled; the same coin can appear on more than one board.

## The original question, on new data

M1 − B2 on the fresh primary cell was +0.0152, daily interval +0.0031 to
+0.0275, block interval +0.0059 to +0.0248, positive on 14 of 16 days. The
historical value was +0.0127. It is again positive and again below the +0.02
minimum effect. In the other five primary-window cells it ranged from −0.004 to
+0.008. The nonlinear extension remains unproven; the simple model carries the
result.

## What does not hold up

- **No tradable edge is shown.** Every band of every ranker has a negative mean
  gross outcome. The best band is −0.024% before any cost.
- **Not every day.** On 2026-11-07 the signs reversed (B1 +0.062, B2 −0.063),
  and from 2026-11-08 to 2026-11-11 the daily difference was between −0.023 and
  +0.009. Nine of the sixteen daily differences exceed +0.02.
- **Last-trade labels.** A bid/ask bounce after a fast move could produce some
  of the giveback. The effect grows from five to fifteen minutes, which a
  bounce alone would not do, but no quotes were recorded to separate them.
- **One host, about sixteen days.** The local ledger differs from the
  production backup used historically. Regime coverage is narrow.
- **Board entries only.** Nothing here describes coins that never reach a
  board, warning lead time, or F1–F5.

## Provenance

- Protocol committed at `671b80f` before any outcome in the window was read;
  driver at `175078d` and `37e6c78`; outcome-blind verification at `7102185`.
- [Verification](results/live_movers_fresh_replication_20261113/results_verify_fresh_replication.json):
  frozen inputs match their manifest, and refitted B2 and M1 coefficients equal
  the stored ones to six decimals in all six cells. The first capture copied
  183,347 ledger rows, SHA-256 `7a3eca14…ea82c`; it stays outside Git. The
  recorded `code_dirty: true` at verification was the verification file itself
  being rewritten; the code hashes are pinned and matched at the test.
- [Result](results/live_movers_fresh_replication_20261113/results_test_fresh_replication.json):
  all daily correlations, intervals, band tables and counts. Seed 20261113,
  5,000 replicates, NumPy 2.5.3, pandas 3.0.6. An attempt marker and the
  existing result both block another run.
- Rejections over the whole ledger: 40,719 outside the two windows, 2,762
  missing a required input, 1,661 without both labels, 224 without a snapshot,
  76 inside the cooldown.
- 14 new synthetic checks and the 11 existing driver tests pass. The locked
  historical validation was not rescored. Codex's checkpoint files and every
  other worktree are unchanged.
