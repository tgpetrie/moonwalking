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

**3. In plain returns, buying right after a spike lost money on average.**
Mean forward return of the event coin itself (no peer adjustment, 1%
winsorised), buying at the event-day close. The baseline is the average liquid
coin over the same period. The cost columns subtract an *assumed* round trip
of 0.5%, 1% and 2%. These are scenarios, not Coinbase's fee schedule.

| After a +10% day | Period | Mean | 95% interval | Baseline | After 1% cost |
| --- | --- | --- | --- | --- | --- |
| 1 day | discovery | -1.77% | -2.61 to -1.01 | -0.56% | -2.77% |
| 1 day | test | -1.59% | -2.48 to -0.68 | -0.03% | -2.59% |
| 3 days | discovery | -3.30% | -5.57 to -1.21 | -1.59% | -4.30% |
| 3 days | test | -1.64% | -3.83 to +0.42 | +0.13% | -2.64% |
| 7 days | discovery | -5.80% | -9.34 to -2.60 | -3.50% | -6.80% |
| 7 days | test | -1.95% | -5.18 to +1.28 | +0.53% | -2.95% |

The next-day result holds in both halves. At 3 and 7 days the test half is
negative on average but its interval includes zero, so in plain returns the
longer horizons are not established. After a -10% day, buying the dip shows no
edge: means are near zero or negative and every interval includes zero.

## What this does and does not show

- **Findings 1 and 2 are relative.** "-2% vs peers" means the coin did 2
  points worse than similar coins that day. Finding 3 gives the plain returns.
- **Not shown to be tradable.** Costs are assumed scenarios, and spreads and
  slippage on thin coins are not measured. Spot Coinbase accounts can't short,
  so a "sell strength" reading would need another venue. The practical use that
  fits spot is avoiding buys right after spikes.
- **Survivorship bias.** The hourly archive holds only products listed today.
  The extended run includes the 89 delisted products Coinbase still lists, and
  they fade more, so the first run understated the effect. Products Coinbase
  no longer lists at all cannot be retrieved.
- **Regimes.** The first run was one year of a weak alt market. The extended
  run covers 2022 to 2026 and every calendar year shows the same sign, but it
  is still one exchange and one crypto cycle.
- **Not causal.** It does not say why spikes fade. Plausible reasons (thin
  liquidity, news-driven pumps, profit-taking) are untested.
- **Overlap.** Several splits are overlapping slices of the same events.

## Use in Moonwalking

Allowed now: describe it as an observed tendency in Coinbase USD products,
2022 to 2026, with the numbers, scope and dates above, and note that it is
relative to similar coins and before real costs.
Not allowed: any probability, price target, or date for a specific coin.

## Extended-history run (2022 to 2026): result

Native daily candles for every Coinbase USD product, including delisted ones
(492 products, 89 not online; 472,362 coin-days), pulled at one request per
second (2,506 requests, all HTTP 200). Settings were fixed in the previous
commit, before any result from this data was seen: same events, outcomes,
features, 78 hypotheses and bootstrap; discovery 2022 to 2024, test 2025-01-01
to 2026-10-17. One small deviation: the first day used is 2022-01-03, not
2022-01-01 (the first two days have no prior day to move from). The hourly run
above lies inside this test period, so it is not independent confirmation.

**Finding 1 holds, on four times as many events and a different regime.**
After a +10% day, coins trail volatility-matched peers:

| Horizon | Discovery 2022 to 2024 (events, mean) | 95% interval | Test 2025 to 2026 (events, mean) | 95% interval |
| --- | --- | --- | --- | --- |
| 1 day | 4,847, -1.39% | -1.65 to -1.14 | 4,155, -1.34% | -1.69 to -1.04 |
| 3 days | 4,835, -2.18% | -2.59 to -1.78 | 4,141, -2.03% | -2.55 to -1.55 |
| 7 days | 4,807, -1.90% | -2.40 to -1.45 | 4,119, -2.20% | -2.79 to -1.64 |

All three replicate by the stated rule (Bonferroni over 78 tests in discovery,
over the 42 survivors in test). About 300 to 420 distinct coins per period; a
third of events beat their peers. 31 of 78 hypotheses replicate, all up-moves.

**Post hoc, descriptive only** (not part of the preregistered tests):
- Every calendar year is negative at 1, 3 and 7 days. Next-day means: 2022
  -1.9%, 2023 -1.5%, 2024 -1.0%, 2025 -1.2%, 2026 -1.6%.
- Delisted products fade more: 7-day mean -4.1% (1,316 events) against -1.7%
  (7,641) for products still online. Including them is what makes the earlier
  survivorship worry real. The effect is not produced by delisted coins alone.

**Plain returns, buying at the close of a +10% day:** next-day mean -1.45% in
discovery and -1.66% in test, against baselines of -0.07% and -0.28%. After an
assumed 1% round-trip cost, -2.5% and -2.7%. At 3 days -2.1% and -2.7%, at 7
days -1.5% (interval includes zero) and -4.6%. Costs are assumed, not
Coinbase's fee schedule.

**Down-moves of 10% or more: still no pattern.** No volatility-matched
hypothesis replicates. Dip-buying means are small and every interval includes
zero except the 7-day test (-2.4%), which sits next to a -1.6% baseline and
does not beat peers.

## Causes behind the 80 reviewed events (Gemini, 2026-10-19)

Gemini returned one row per event:
`data/move-study/cause_review_gemini_2026-10-19.csv`, re-quoted because three
rows had unescaped commas. All 80 rows match the input and every category is
from the allowed list. **Treat it as unverified research, not data.**

**Checks**
- Four high-confidence claims were confirmed in independent sources:
  Farcaster's Clanker acquisition (2025-10-23), Binance delisting NKN and GHST
  on 2026-02-13, the 2026-04-01 Drift hack (about $285M), and zkPass's Binance
  listing (2026-01-07, 14:00 UTC).
- 20 rows cite a source dated after the event day. Nine of those give a cause
  other than "no known cause", so that cause rests on after-the-fact
  explanation: ALCX, TNSR, ZKP, APE, ALLO, BIRB, AERGO, ESP, DEEP.
- Two rows mark `published_before_move = yes` with a same-day source (GHST,
  DRV). That should be "unclear".
- Some summaries use information from after the event, which the brief
  forbade: TNSR cites a later Coinbase deal, VELO a later merger, ZAMA a later
  announcement, IMU a later report.
- Gemini's own summary counts are off by one in three places. Actual counts:
  largest has 21 no-known-cause; random has 26 no-known-cause and 9
  market-wide.

**Counts.** Of the 40 largest up-moves, 21 have no known cause, 8 protocol or
partnership news, 3 listings, 3 delistings or warnings, and 5 other
categories. Of the 40 random moves, 26 have no known cause and 9 track a
market-wide Bitcoin move. Only 8 of 80 have a source dated before the move.

**Joined to outcomes** (forward return vs volatility-matched peers, from the
hourly-archive run; 79 of 80 matched, 7-day values missing for 3):

| 40 largest up-moves | n | 1 day | 3 days | 7 days | 7-day median |
| --- | --- | --- | --- | --- | --- |
| All | 40 | -8.3% | -13.1% | -14.9% | -24.2% |
| Known cause | 19 | -5.3% | -7.1% | -8.6% | -25.9% |
| No known cause | 21 | -11.0% | -18.8% | -20.9% | -23.9% |
| Protocol/partnership news | 8 | -2.1% | +5.8% | +5.6% | +6.6% |
| Listing (3) or delisting (3) | 6 | about -15% | about -23% | about -33% | |

Spikes with no known cause fell further on average, but the medians are about
the same (-23.9% vs -25.9%). The 12-point gap in means is not significant
(permutation p = 0.13). 37% of known-cause spikes beat their peers after 7
days, against 10% with no known cause. Protocol-news spikes held their gains
best; listings and delistings faded hardest. Every group here has 8 or fewer
events.

**Reading.** This is hypothesis-generating only. There is also a
built-in bias: articles explaining a move are more likely to be written when
the move lasts, so "known cause" may partly mean "held up". A proper test
needs causes logged at the time (point in time), for many more events.

## Next steps

1. Causes: first pass done (above). Next is logging causes point in time for many more events (a researcher or
   Gemini can build this; it needs sources). The brief and event list are in
   `GEMINI_BRIEF_MOVE_CAUSES.md` and `events_for_cause_review.csv`.
2. Separate liquidity effects from news effects: the give-back may be
   concentrated in thin coins or listing days.
3. Measure actual spreads on thin coins so the cost allowance stops being a
   guess.
4. Repeat for a second event, such as arrival at a confirmed prior high or low,
   which is what the chart's level-reaction panel looks at.

## Reproducing

```powershell
$py = "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe"
& $py -I scripts\move_study\continuation_vs_reversal.py --archive archive_copy.sqlite --out data\move-study
# Extended run (needs the daily pull from fetch_daily_all.py)
& $py -I scripts\move_study\fetch_daily_all.py --out daily_all
& $py -I scripts\move_study\continuation_vs_reversal.py --daily-dir daily_all --out data\move-study --first-day 2022-01-03 --last-day 2026-10-17 --split-day 2025-01-01 --tag _daily_2022
& $py -I -m pytest scripts\move_study -q
```

`archive_copy.sqlite` is a consistent copy of the candle archive (see
RENDER_HISTORY.md, section 6). Seed and parameters are in the output file.
