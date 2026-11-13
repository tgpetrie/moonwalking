# Board runner screen · November 13, 2026

The replicated overextension finding and a concentration of runners coexist
in the October 28 through November 12 UTC sample. Among 3-minute gainers,
the largest entry moves averaged a 10.12% runner rate when flagged and
3.82% otherwise. This exploratory result uses the same dates as the
[fresh replication](https://github.com/tgpetrie/moonwalking/blob/7bd275748e1b9ee5758835337843a2dc1fe2a64e/docs/research/LIVE_MOVERS_FRESH_REPLICATION_RESULTS_20261113.md),
which measured directional return and found a negative mean in the
highest-move band. The two outcomes answer different questions.

## Exploratory results

Each cell is the mean across 16 UTC days of the runner rate among gradable
flagged entries. A runner had a stored directional peak at or above that
day's top-5% cutoff for its board, with outcome ties included. Each score
gets the same flag count per board/day, the largest fifth of entries with
all compared inputs present, rounded up. A tied score at the flag cutoff
gets a proportional share. Flags are ranked before excluding ungradable
outcomes. The all-day ranking gives a common comparison budget and uses
future entries, so it supplies no live flag threshold.

| Entry-time signal | 1m gainers | 3m gainers | 3m losers |
| --- | ---: | ---: | ---: |
| Matched base rate | 5.01% | 5.07% | 5.01% |
| Directional percentage move | 9.45% | **10.12%** | **11.14%** |
| Entry rank | 8.89% | 9.43% | 9.71% |
| Direction-aligned stored live score | 8.34% | 9.32% | 9.87% |
| Nominal 1m acceleration | **10.96%** | 7.91% | 9.08% |
| 1h volume change | 5.65% | 6.23% | 6.04% |
| Prior same-board entries over 24h | 4.53% | 6.40% | 6.30% |

Acceleration on 1m gainers beat percentage move on all 16 days in this
sample. Its unflagged rate was 3.53%. The daily runner cutoff varied from
about 0.67% to 1.53% across boards and days. As a sensitivity read, 11.96%
of gradable 1m acceleration flags had a sampled peak of at least 1% and
6.24% still had at least 1% at the observed 15-minute checkpoint.
For 3m gainers, the raw-move flags were 11.52% and 6.48% on those two
measures. The 1% level is an exploratory reference. The illustrative flag
budget averaged 14–16 flags per calendar hour per board. A notification
budget would need its own cap.

The score for acceleration is the directional difference between the
nominal last-minute log return and the per-minute log return of the
preceding two minutes. The volume field describes 1h change and gives no
trade count at entry. The persistence count uses only earlier entries and
inherits the tracker's cooldown. These single-variable comparisons do not
measure incremental value from a blend or activity gate. No model was fitted.
Use the results to select a question for fresh confirmation, accounting for
overlapping windows, repeated products and cross-board dependence.

## Coverage and label audit

| Board | Total entries | Gross 15m checkpoint present | Gross 60m checkpoint present | All compared inputs | All compared inputs and 15m grade |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1m gainers | 31,454 | 30,928 | 29,609 | 30,825 | 30,358 |
| 3m gainers | 27,828 | 27,345 | 26,103 | 27,085 | 26,652 |
| 3m losers | 27,873 | 27,385 | 26,168 | 27,003 | 26,567 |

- All 87,155 entries have ranks 1–8. The checked dashboard uses 1m gainers
  and 3m gainers and losers. The sample can study a coin at its tracked entry.
  It cannot compare simultaneous board rows, measure every later appearance,
  evaluate ranks 9–16 or describe coins before board entry.
- The minimum same-board entry spacing was 3,615 seconds. There were zero
  re-entries within an hour. The 24h count is a coarse repeat-appearance proxy.
- `max_favorable_15m` is the largest observed gross directional excursion
  from entry, floored at zero. The code updates it through age 900 seconds
  **or while the 15m checkpoint is missing**. Consequently it can include
  the first observation after 900 seconds and keep accumulating if that
  checkpoint is never recorded. The screen requires a stored gross 15m
  return and an observed, non-interrupted 15m grade. This excludes missing
  checkpoint cases but cannot remove checkpoint overshoot. The default
  checkpoint slack is 300 seconds. A synthetic probe on the existing
  tracker included a move at +940s in the stored 15m peak and excluded
  the next move at +960s after the checkpoint. The ledger has no peak clock,
  per-product observation count or quote age. A wick can grade as a runner
  and then fade. The 60m checkpoint is a directional return; the generic
  peak is over the tracked horizon. No 60m runner screen was run.
- 87,069 rows have feature snapshots and all are v2, dated within the
  contract's 60-second pre-entry window. None has numeric realized
  volatility, quote-volume USD or BTC-relative return. The local 60-second
  candle archive has 5,920,622 rows for 407 products and ends October 12
  at 17:59 UTC, so it contributes no candle in the discovery interval.
  This also blocks reconstructing a staircase from completed minutes for
  these dates.

## Next research decision

Use raw percentage move as the baseline at a practical flag budget. The
cleanest challenger from this screen is 1m acceleration on the 1m gainers.
Freeze a threshold or ranking against data available at decision time and
an absolute continuation sensitivity alongside the daily relative tail.
Validate on days after the rule is fixed. Determine the required number of
days and episodes from day-block uncertainty and a meaningful lift before
declaring a stopping rule. Keep 3m up and down separate. A fresh holdout
needs enough independent periods, even when entry volume is high.

One-minute candles can support research on unusual moves, activity and
BTC-relative movement, and a separate pre-entry early-watch comparison.
Start with explicit historical product IDs and audit completed-minute
coverage. Current listings, old archive rosters and observed episode IDs
give partial roster evidence. Successful requests may still leave gaps.
A candle-only replay can measure minute-scale opportunities under an
explicit observation model. Live board membership, sub-minute lead and
delivery require their own timestamped evidence.
[Coinbase Exchange candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).

For any future recorder extension, retain the original top-eight entry
series and add separate observation for ranks 9–16, including transitions
into the top eight and re-entries during cooldown. Timestamp sampled
peaks, checkpoint observations and any BBO measurements. These data
changes require a separate implementation and deployment decision.

## Reproduction

The analysis uses the immutable private `board_episodes.sqlite` from the
fresh replication and checks its published SHA-256 before reading it. It
uses October 27 entries only to initialize prior appearances and reads no
entries from November 13 onward. No new capture or candle backfill ran.
The 23 existing board, gap and candle-archive tests, the synthetic peak
probe, formatting, JSON, diff and repository guardrail checks passed.

```powershell
python scripts/scoring_experiment/screen_board_runners_20261113.py "$env:USERPROFILE/.moonwalking/analysis/live_movers_fresh_replication_20261113/board_episodes.sqlite"
```
