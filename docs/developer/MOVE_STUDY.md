# Large daily moves: continue or reverse?

First study toward "what comes before the next move". Candle data only. It
looks for a repeatable pattern and tests it on data it was not found in. It
does not explain causes, and nothing here changes the chart.

Code: `scripts/move_study/continuation_vs_reversal.py` (tests alongside).
Results: `data/move-study/continuation_vs_reversal.json`.

## Question

After a coin makes a large close-to-close daily move (up or down by 10% or
more), does it keep going, or give it back, over the next 1, 3 and 7 days?

## Method

- **Data:** read-only copy of the candle archive: hourly Coinbase USD candles
  for 407 products, rebuilt into UTC days, 2025-10-02 to 2026-10-10 (137,547
  coin-days). Days with no trades are absent, not filled.
- **Events:** 2,100 up-moves and 1,482 down-moves. Only liquid coin-days count
  (event-day volume of at least $100k and median prior 20-day volume of at
  least $50k). Repeat events by the same coin within 7 days are collapsed to
  the first.
- **Outcome:** forward close-to-close return, 1% winsorised, minus the average
  of comparable coins on the same day. Two comparisons are reported:
  against all liquid coins (market-adjusted), and against liquid coins in the
  same volatility quintile (trailing 20-day volatility, volatility-matched).
  The second is the one to trust.
- **Split:** discovery = days before 2026-04-01, test = 2026-04-01 onward.
  Forward windows that would cross the boundary are dropped.
- **Inference:** moving-block bootstrap over calendar days (7-day blocks,
  4,000 resamples), because events on the same or neighbouring days are not
  independent. 78 hypotheses per adjustment (2 directions x 3 horizons x 13
  splits); discovery p-values are Bonferroni-adjusted over all 78, test
  p-values over only the splits that survived discovery.
- **Six yes/no splits**, thresholds fixed beforehand: volume spike, uptrend
  into the event, near the prior 30-day high, closed at the extreme of the
  day's range, broad market day, Bitcoin up that day.

**Post-hoc changes, disclosed.** The first run used only the market
adjustment and a looser test rule. It showed up-moves and down-moves both
lagging, which suggested a volatility effect. I then added the
volatility-matched comparison and the stricter test-period family. Both
adjustments are in the file. Results below use volatility-matched.

## Findings

**1. Up-moves of 10% or more tend to give some back, relative to similar coins.**

| Horizon | Discovery (events, mean vs peers) | Test (events, mean vs peers) | Test 95% interval |
| --- | --- | --- | --- |
| 1 day | 1,068, -1.38% | 1,010, -1.73% | -2.24% to -1.19% |
| 3 days | 1,064, -1.95% | 993, -2.43% | -3.18% to -1.61% |
| 7 days | 1,056, -1.86% | 970, -2.80% | -3.81% to -1.75% |

It holds in both halves of the year and across about 300 different coins; no coin
accounts for more than 1% of events. About two in three events trail their
peers (a 33 to 36% share positive), and medians are more negative than the
means.

It is stronger in some conditions: volume spike (-4.6% at 7 days in discovery),
broad rallies not present (-6.1%), and days when Bitcoin was down (-7.2%).
These sub-splits replicate too, but they overlap each other and the headline
result, so do not count them as independent evidence.

**2. Down-moves of 10% or more show no reliable pattern.** Neither a bounce
nor continued falling replicates in the test half, for any horizon or split.
Discovery shows a mild lag (-0.2% to -0.7%) that does not hold in the test.

22 of 78 volatility-matched hypotheses replicate by the stated rule, all of
them up-moves.

## What this does and does not show

- **Relative, not absolute.** "-2% vs peers" means the coin did 2 points worse
  than similar coins that day. It does not say the coin fell. Absolute returns
  were not examined.
- **Not shown to be tradable.** No fees, spreads or slippage. Spot Coinbase
  accounts can't short, so the "sell strength" reading would need another
  venue. A signal that is real can still not be worth acting on.
- **Survivorship bias.** The archive holds only products listed today. Coins
  that spiked and then collapsed and were delisted are missing, so the true
  give-back after spikes is probably larger, not smaller.
- **One year, mostly a weak market for alts.** A different regime could behave
  differently. The test half helps, but it is the same year.
- **Not causal.** It does not say why spikes fade. Plausible reasons (thin
  liquidity, news-driven pumps, profit-taking) are untested.
- **Overlap.** Several splits are overlapping slices of the same events.

## Use in Moonwalking, if it holds up

Allowed now: describe it as an observed tendency in this sample, with the
numbers, scope and dates above.
Not allowed: any probability, price target, or date for a specific coin.

## Next steps

1. Add absolute returns and a cost/spread allowance, to see if the effect
   survives being acted on.
2. Extend history with daily candles (about 400 public requests at one per
   second) so more than one regime is covered, and include delisted products
   where Coinbase still serves them.
3. Add the causes half: news and listing dates for the event days (a
   researcher or Gemini can build this; it needs sources).
4. Repeat for a second event, such as arrival at a confirmed prior high or low,
   which is what the chart's level-reaction panel looks at.

## Reproducing

```powershell
$py = "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe"
& $py -I scripts\move_study\continuation_vs_reversal.py --archive archive_copy.sqlite --out data\move-study
& $py -I -m pytest scripts\move_study -q
```

`archive_copy.sqlite` is a consistent copy of the candle archive (see
RENDER_HISTORY.md, section 6). Seed and parameters are in the output file.
