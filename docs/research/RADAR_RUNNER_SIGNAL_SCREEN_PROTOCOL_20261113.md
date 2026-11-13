# Radar runner signal screen (step 1): protocol, 2026-11-13

**Status: exploration, predeclared before any runner outcome was computed.**
This is step 1 of the design in Carbon's runner-study memo of 2026-11-13. It
screens signals that the stored entry snapshot already supports. It selects
candidates for later confirmation; it confirms nothing. No board, score or
production behavior changes.

## Data

- **Screen sample:** the frozen production capture, board entries from
  2026-07-19 to 2026-10-17 that pass the frozen eligibility rules
  (`freeze_live_contract.classify`, contract `CONTRACT_PRODUCTION.json`, all three
  phases). Snapshot fields exist from 2026-08-18, so in practice that is the
  start.
- **Check sample:** the local ledger capture, 2026-10-18 to 2026-10-27 with the
  1,800s purge before its end, under the same rules.
- **Not used:** 2026-10-28 onward. That window has been inspected, and days from
  2026-11-13 are reserved for confirmation.
- Extra eligibility for this screen: `gross_return_30m` finite and
  `outcome_15m` not `interrupted`. Rows failing it are counted and excluded.

## Outcomes, from Carbon's memo

All returns are the stored directional gross returns, so the same rule serves
gainers and losers.

- **Runner:** `gross_return_15m >= 1.00` and `gross_return_5m > -0.50` and
  `max(max_favorable_15m, gross_return_30m) >= 1.50`.
- **Crasher**, the mirror, added so a signal that only finds volatile coins is
  visible: `gross_return_15m <= -1.00` and `gross_return_5m < 0.50` and
  `min(max_adverse_15m, gross_return_30m) <= -1.50`.

Thresholds are fixed for this screen. If the runner base rate on a board falls
outside 3–15%, that is reported, not tuned.

## Signals

`d` is +1 on up boards and −1 on the down board; `a1 = d·pct_1m`,
`a3 = d·pct_3m`, from the entry snapshot. Higher values are meant to predict a
runner.

| Id | Formula |
|---|---|
| B0, baseline | `abs(start_change_pct)` |
| 1A | `a1 / max(a3, 0.25)` |
| 1A− | `−(1A)` |
| 1B | `a3 − 2·max(0, a1 − 0.60·a3) − 2·max(0, 0.15·a3 − a1)` |
| 3A | `ln(1 + max(volume_change_1h_pct, −99) + 100)` if liquidity is `normal`, else 0 |
| 4A | `min(trend_streak or 0, 6) + 2·aligned_alerts − 2·opposing_alerts` |
| 4B | `2·simultaneous + [repeat_6h = 1] − 2·[repeat_6h ≥ 3]` |
| 6 | `−chase − 0.15·max(0, W60 − 3) + 0.01·volume_change_1h_pct` |
| 6c | `−chase` alone |

- `simultaneous`: another same-direction entry for the same product on a
  different board within 180 seconds either side.
- `repeat_6h`: earlier entries for the same product and direction, any board,
  in the six hours before entry.
- `chase = max(0, abs(start_change_pct) − abs(a_board))`, where `a_board` is
  `a1` on the 1-minute board and `a3` on the 3-minute boards.
- `W60`: same-board, same-direction entries in the 60 seconds up to and
  including entry.
- History-based fields (`simultaneous`, `repeat_6h`, `W60`) are computed from
  every recorded row in the capture, eligible or not. `simultaneous` looks up to
  180s after entry; this is a known look-ahead, kept because Carbon specified
  it, and it is flagged in the results.

## Metric

For each board and UTC day with at least 20 eligible rows and at least 2
runners:

- each signal flags `floor(0.25·N)` rows, its highest values, ties broken by
  higher `B0`, then by row id;
- `X` is the day's runner rate, `Y(S)` the runner rate of the rows S flags,
  `C(S)` their crasher rate;
- the paired gain over the baseline is `ΔP = Y(S) − Y(B0)`, and the net gain is
  `ΔN = (Y(S) − C(S)) − (Y(B0) − C(B0))`.

Days are weighted equally. Daily bootstrap 95% intervals, 5,000 replicates,
seed 20261114. Ranking within the whole day uses the full day's entries, which
is a look-ahead the live board cannot use; a live-feasible budget is needed
before confirmation.

## Screen rule

A signal goes forward on a board if, on the screen sample:

1. mean `ΔP ≥ +0.010` with the daily lower bound above zero, and
2. mean `ΔN > 0`,

and on the check sample its mean `ΔP` is above zero. Everything else is
reported. At most three signals go forward in total, ranked by screen `ΔP`.
Boards are never pooled.
