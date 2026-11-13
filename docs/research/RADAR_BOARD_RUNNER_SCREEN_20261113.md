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

### Relative drawdown check

The follow-up used the identical capture, dates, eligibility, score weights,
and top-fifth flag budget. Each UTC board/day has two outcome cutoffs: the
upper 5% of `max_favorable_15m` and the lower 5% of `max_adverse_15m`. Both
include boundary ties and use all entries with the existing 15m grade.
The adverse field measures the worst excursion from entry, with the same
sampling and possible checkpoint overshoot as the favorable field. On the
losers board, an adverse excursion is a price rebound. The two events can
occur in one episode. Their order is unavailable.

Each cell shows the average daily flagged runner / adverse-tail rates.
Matched base rates were about 5% for each tail on every board.

| Entry-time signal | 1m gainers | 3m gainers | 3m losers |
| --- | ---: | ---: | ---: |
| Directional percentage move | 9.45% / 15.67% | 10.12% / 16.24% | 11.14% / 16.47% |
| Entry rank | 8.89% / 13.86% | 9.43% / 15.01% | 9.71% / 15.11% |
| Direction-aligned stored live score | 8.34% / 13.71% | 9.32% / 14.19% | 9.87% / 14.84% |
| Nominal 1m acceleration | 10.96% / 16.49% | 7.91% / 13.24% | 9.08% / 13.36% |
| 1h volume change | 5.65% / 6.20% | 6.23% / 5.62% | 6.04% / 5.99% |
| Prior same-board entries over 24h | 4.53% / 3.36% | 6.40% / 5.40% | 6.30% / 5.29% |

On 3m gainers, the raw-move flags had a 16.24% adverse-tail rate against
2.26% unflagged. For 1m acceleration the rates were 16.49% and 2.16%.
About 2% of flags in each of these comparisons reached both tails.
At equal-sized 1% excursions, 3m raw-move flags reached +1% in the board
direction 11.52% of the time and −1% 26.52%. The 1m acceleration figures
were 11.96% and 24.34%.

The 1m acceleration runner-minus-adverse gap was −5.53 percentage points
(exploratory three-day block interval −6.61 to −4.32), versus −6.22 for
raw move. The paired improvement was +0.69 points (+0.27 to +1.14).
On 3m gainers the raw-move gap was −6.12 points (−8.65 to −4.20).
Volume on 3m gainers and prior entries on both 3m boards had small
positive gaps of 0.61–1.01 points. Prior entries on 1m gainers also had
a positive gap, driven by fewer adverse events and a runner rate below
base. Intervals use 5,000 draws of contiguous three-UTC-day blocks of
paired daily rates. They are descriptive across signals on 16 explored
days, with no multiplicity adjustment.

### Carbon's sustained-runner proposal

Carbon's November 13 memo supplied a useful absolute label. On the same
dates, score a runner when the gross directional 15m checkpoint is at
least +1%, the 5m checkpoint is above −0.5%, and either the stored 15m
peak or the 30m checkpoint reaches +1.5%. Its mirror uses the negated
directional returns and adverse excursion. Require all three finite
checkpoints and the original non-interrupted 15m grade. This label
matures at the 30m checkpoint and inherits ledger timing and last-trade
limitations. It allows an episode to qualify from the 30m value, so
the extension need not precede the 15m checkpoint.

For this separate sensitivity, use Carbon's 25% daily quota, rounded down,
on the same input-eligible rows before grading. Ties receive proportional
weights. This preserves the alert denominator when an outcome is missing.
The full-day quota remains a retrospective comparison.

| Entry-time signal | 1m gainers runner / reversal | 3m gainers runner / reversal | 3m losers runner / reversal |
| --- | ---: | ---: | ---: |
| Matched base rates | 2.05% / 3.69% | 2.18% / 4.33% | 2.36% / 3.80% |
| Directional percentage move | 3.49% / 9.25% | 4.19% / 11.02% | 4.81% / 9.79% |
| Entry rank | 3.39% / 8.50% | 3.85% / 10.50% | 3.75% / 9.09% |
| Direction-aligned stored live score | 3.19% / 8.44% | 4.02% / 10.15% | 4.25% / 9.50% |
| Nominal 1m acceleration | 3.96% / 9.59% | 3.01% / 9.33% | 3.56% / 8.38% |
| 1h volume change | 2.51% / 4.41% | 2.57% / 4.87% | 2.78% / 4.59% |
| Prior same-board entries over 24h | 2.13% / 2.67% | 2.79% / 4.64% | 2.48% / 3.67% |

The sustained comparison has 29,903 graded rows for 1m gainers, 26,227
for 3m gainers, and 26,189 for 3m losers. Every tested flag has a higher
sustained reversal rate than runner rate. The small positive gaps for
volume and prior entries under the relative labels disappear under the
sustained definition. Carbon expected a 5–10% runner base rate. The observed
2.05–2.36% matters for any power calculation.

### Disposition

No tested flag clears the requested directional screen. Keep percentage
move as the reference. The two-sided enrichment supports describing
activity or reversal exposure. Volatility, liquidity and quote effects
remain possible explanations that the ledger cannot separate.

Use Carbon's absolute label as a design candidate alongside its adverse
mirror. Before any freeze, specify an entry-time flag rule with a practical
budget, and derive sample requirements from paired day or market-wave
variation under the observed base rates. Carbon's full-day quota cannot
run at entry. The proposed stopping rules also leave the 12–13 valid-day
case ambiguous and need one fixed rule or a calibrated sequential design.
Set the holdout after the finalized rule. No confirmation outcomes were
read and no signal or protocol was frozen in this follow-up.

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
The follow-up matched every previously emitted result across three boards
and 18 score cells. The 14 board and gap tests passed again. Synthetic
checks covered tied cutoffs, both tails on one row, ungradable flags,
and the sustained label boundaries.

```powershell
python scripts/scoring_experiment/screen_board_runners_20261113.py "$env:USERPROFILE/.moonwalking/analysis/live_movers_fresh_replication_20261113/board_episodes.sqlite"
python scripts/scoring_experiment/screen_board_runners_20261113.py "$env:USERPROFILE/.moonwalking/analysis/live_movers_fresh_replication_20261113/board_episodes.sqlite" --carbon
```
