# Radar runner candle screen (step 2): results, 2026-11-13

**No candle-based signal passed the screen.** None raised the runner rate above
plain percentage change under the
[predeclared rule](RADAR_RUNNER_CANDLE_SCREEN_PROTOCOL_20261113.md). One result
is still worth keeping: ranking by dollar activity found about as many runners
as percentage change with roughly half the crashers. Exploration only:
131,684 entries from 2026-09-07 to 2026-09-30, checked on 60,659 from
2026-10-01 to 2026-10-11.

## Results against percentage change, same rows, top 25% per day

Runner and crasher rates of the flagged rows, in percent. `ΔP` is the signal's
runner rate minus percentage change's, with the daily bootstrap 95% interval.

| Signal | Board | Rows kept | Signal runners / crashers | % change runners / crashers | Screen ΔP | Check ΔP |
|---|---|---:|---|---|---|---:|
| 3B dollar activity | 3m gainers | 100% | 5.36 / 5.71 | 4.98 / 9.53 | +0.37 [−0.29, +1.06] | −0.44 |
| 3B dollar activity | 1m gainers | 100% | 4.46 / 4.83 | 4.50 / 8.10 | −0.04 [−0.71, +0.52] | −1.17 |
| 3B dollar activity | 3m losers | 100% | 4.97 / 6.10 | 5.44 / 8.77 | −0.47 [−1.02, +0.10] | −1.27 |
| 5A Bitcoin-relative | 3m gainers | 30% | 9.29 / 10.26 | 9.16 / 13.29 | +0.13 [−0.79, +1.12] | −0.41 |
| 5A Bitcoin-relative | 1m gainers | 34% | 6.44 / 6.64 | 8.05 / 11.27 | −1.61 | −1.83 |
| 5A Bitcoin-relative | 3m losers | 31% | 9.03 / 9.99 | 10.24 / 12.23 | −1.21 | −1.40 |
| 2A unusual move | all three | 59–62% | 3.0–3.9 / 4.5–5.1 | 6.9–8.4 / 10.1–11.6 | −3.2 to −5.4 | −2.6 to −3.9 |
| 2A with activity floor | all three | 59–62% | 3.4–4.5 / 4.1–4.9 | as above | −2.7 to −5.0 | −3.1 to −4.1 |

## What it shows

- **Dollar activity is the one piece with support, as a filter.** On every
  board, in both windows, its flagged rows crash far less often than the rows
  percentage change flags (for example 3.9% against 8.5% on 3m gainers in the
  check window) at a similar or slightly lower runner rate. It does not find
  more runners, and its flagged rows still crash at least as often as they run.
  This supports the activity gate as a way to remove bad rows, not as a runner
  signal.
- **Ranking by how unusual the move is for the coin does worse.** It finds
  fewer than half the runners percentage change finds.
- **The Bitcoin-relative move matches percentage change on 3m gainers and is
  worse elsewhere.** Only about 30% of entries have the candles it needs.
- **Still no group that runs more often than it crashes.** The closest was the
  unusual-move signal with an activity floor on 3m gainers in the screen window,
  4.53% runners against 4.32% crashers; in the check window that was 2.33%
  against 2.99%.

## Coverage is not neutral

Rows with candle coverage are different from rows without. Entries that had
enough traded minutes for the volatility estimate ran about twice as often as
those that did not (4.3% against 1.9% on 3m gainers), and the same holds for the
Bitcoin-relative rows. Each comparison above is therefore between signals on
the same kept rows, and says nothing about the dropped ones.

## Limits

Exploration on historical data; whole-day ranking uses later entries; last-trade
outcomes; one archive of 36 days. The archive covers 407 products. A fuller
backfill could change coverage for the volatility and Bitcoin-relative signals.

## Provenance

Protocol `0ce6efc`; script and three synthetic checks in the following commit.
All numbers are in
[RESULTS.json](results/radar_runner_candle_screen_20261113/RESULTS.json).
