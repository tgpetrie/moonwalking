# Radar runner candle screen (step 2): protocol, 2026-11-13

**Status: exploration, predeclared before any step 2 outcome was computed.**
Step 2 of Carbon's design: signals that need one-minute candles. Same
outcomes, metric, flag share, bootstrap and pass rule as
[step 1](RADAR_RUNNER_SIGNAL_SCREEN_PROTOCOL_20261113.md), seed 20261115.
Nothing here confirms a signal or changes a board.

## Data

Eligible board entries from the frozen production capture, joined to the local
one-minute candle archive (`candle_archive.sqlite`, 2026-09-06 to 2026-10-12).
Screen sample: entries from 2026-09-07 to 2026-09-30. Check sample: 2026-10-01
to 2026-10-11. Entries need 61 minutes of archive before them, so the first and
last archive days are left out.

For an entry at `t`, `k = floor(t/60)*60 − 60` is the open time of the last
candle closed before entry. Only candles with open time `<= k` are read. A
minute with no row had no trades.

## Signals

`d` is +1 on up boards, −1 on the down board.

| Id | Formula | Available when |
|---|---|---|
| 2A unusual move | `d·pct_3m/100 / (sqrt(3)·sigma)`, `sigma = max(0.001, sqrt(mean of ln(close/open)^2 over the 60 minutes ending at k))`, no-trade minutes count as 0 | at least 10 traded minutes in those 60 |
| 3B dollar activity | `ln(1 + sum(close·volume) over k−120..k) · (traded minutes in k−840..k)/15` | product has any candle in the archive before `k` |
| 5A Bitcoin-relative | `d·(r_coin − r_BTC)` if `abs(r_BTC) < 0.75`, else 0; `r = close(k)/open(k−120) − 1` in percent | coin and BTC-USD both have candles at `k` and `k−120` |
| 2A×3B | 2A, set to the day's minimum when traded minutes in `k−840..k` is under 10 | as 2A |

## Comparison and coverage

Each signal is compared with percentage change (`B0`) on exactly the rows where
that signal is available: both flag the top 25% of those rows per board and
day. For each signal and board the report gives the share of eligible entries
kept, and the runner and crasher base rates of kept and dropped rows, so
selection by coverage is visible. Days need 20 kept rows and 2 runners.

A signal goes forward on a board under the step 1 rule: screen mean `ΔP ≥
+0.010` with the daily lower bound above zero, screen mean `ΔNet > 0`, and
check mean `ΔP > 0`.
