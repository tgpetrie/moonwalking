# Study 2c: hourly absorption triggers, and breakdowns at macro lows and VAL

Two final price-only checks, from Gemini's brief of 2026-10-19. Everything
above "Results" was committed **before** any result was computed.

## Part 1: two-step hourly absorption / exhaustion triggers

**Data.** Archived Coinbase hourly candles, 407 current USD products,
2025-10-02 to 2026-10-10 (whole UTC days inside the fetched hourly range).
Liquidity filter: study 1's daily rule on the trigger's UTC day. Split:
discovery 2025-10-02 to 2026-03-31, test 2026-04-01 onward.

**Bullish trigger.**
- *Bar 1* (hour h): `Low[h]` strictly below the lows of the previous 24
  hourly candles, all 24 present and consecutive; `Volume[h]` at least 2x the
  median volume of those 24; lower wick `min(Open, Close) - Low` at least 40% of
  `High - Low` (which must be positive); close in the upper half of the range.
- *Bar 2*: the first hour in h+1 to h+4 (consecutive hours) with
  `Low < Open`, `Low > Low[h]`, `Close > Open` and `Close > Close[h]`. If any
  bar between h and that bar trades at or below `Low[h]`, there is no trigger.
- The trigger time is the close of bar 2.

**Bearish trigger.** The mirror image: a 24-hour high, upper wick at least
40%, close in the lower half; bar 2 with `High > Open`, `High < High[h]`,
`Close < Open`, `Close < Close[h]`, and no bar in between at or above
`High[h]`.

At most one trigger per coin per direction in any 24 hours (the first one
counts).

**Outcome.** Forward return from the trigger close over 24, 72 and 168
hours, minus the same-window average return of liquid coins in the same
volatility quintile (trailing 20-day daily volatility, as in study 1). Both
are 1% winsorised. For bearish triggers the sign is flipped so that positive
always means the trigger was right.

**Primary tests (20; Bonferroni within discovery, confirmed in test over the
discovery survivors, same sign required), moving-block bootstrap over
calendar days (7-day blocks):**
- **A1** edge: mean outcome of all triggers vs zero, by direction and
  horizon (6).
- **A2** location, by direction and horizon, real zone minus placebo zone,
  and real zone minus open air (12). For a bullish trigger the reference price
  is bar 1's low, for a bearish one bar 1's high.
  - *Real zone*: within 1% of a level eligible on that day: confirmed swing
    lows (bullish) or highs (bearish); VAL (bullish) or VAH (bearish) of any
    causal leg (Study 2b); or the 0.705 to 0.886 retracement band of the
    latest leg (measured from its high for an up leg, bullish; from its low
    for a down leg, bearish) where that band lies outside the leg's value
    area.
  - *Placebo zone*: within 1% of a placebo line (Study 2's pivot shadows,
    Study 2b's range ratios).
  - *Open air*: neither. Triggers within 1% of both a real level and a
    placebo line are excluded from A2.
- **A3** timing on shock days (study 1: +10% day, 5x volume, 15 points above
  BTC): for shock days with a bearish trigger in the 48 hours after the day's
  close, the relative move from the daily close to the trigger close
  (positive = the trigger came at a higher relative price, a better point to
  avoid or exit), at 3 and 7 days measured to the same end point (2).

Levels and legs are built from daily data and used only once confirmed.

## Part 2: breakdowns at the macro low and VAL

**Data and split.** As Study 2: daily, 492 products, 2022-01-03 to
2026-10-17; discovery 2022 to 2024, test 2025 onward.

**Events.** First touches from above (`Low[t-1] > level >= Low[t]`) of the
macro low (r = 0, Study 2) or VAL (Study 2b) whose arrival day **closes below
the level**. Placebo: first touches from above of Study 2's pivot shadows and
Study 2b's range-ratio placebos that also close below.

**Single primary hypothesis.** The 14-day forward return (vs
volatility-matched peers, 1% winsorised) after real breakdowns is lower than
after placebo breakdowns. Two-sided p < 0.05 in discovery **and** in test,
same sign. The 7-day result and the hold-above split are reported alongside
as secondary.

**Reported whatever it shows.**

## Results

(Added after the run, below this line.)

### Run of 2026-10-19 (`scripts/move_study/absorption_study.py`, `data/move-study/absorption_study.json`)

#### Part 1: hourly two-step triggers (19,342 liquid triggers: 8,532 bullish, 10,810 bearish)

Outcome: relative return after the trigger vs volatility-matched peers,
signed so positive means the trigger was right. Discovery Oct 2025 to Mar
2026, test Apr to Oct 2026.

| Test | Discovery | Test |
| --- | --- | --- |
| A1 bullish, 1 / 3 / 7 days | +0.06 / +0.01 / -0.02% | -0.01 / -0.14 / -0.21% |
| A1 bearish, 1 / 3 / 7 days | **+0.33** / +0.28 / +0.42% | +0.11 / +0.22 / +0.33% |

- **Bullish absorption: no edge.**
- **Bearish exhaustion: a small, consistent edge that does not pass the
  replication rule.** Only the 1-day discovery test survives Bonferroni (p
  0.005); its test-period result is +0.11% (interval -0.00 to +0.20, p 0.06).
  The 3- and 7-day results are positive in both halves (test p 0.026 and
  0.007), but they did not survive in discovery, so by the preregistered rule
  nothing replicates. Size: 0.1 to 0.4 points relative to peers, below
  realistic trading costs for most of these coins.
- **A2, location: no help.** Triggers near real structural levels do no
  better than those near placebo lines or in open air, in either direction or
  half (all 12 tests fail in discovery). Real zones were rare (697 bullish,
  242 bearish triggers); most triggers were in open air.
- **A3, timing on shock days: no reliable improvement.** 97 of 463 shock days
  had a bearish trigger within 48 hours of the close. Waiting for it gave a
  better relative exit by +4.7% in discovery (n = 45, wide interval 0.8 to
  11, not significant after correction) and +0.4 to +0.6% in test (n = 47 to
  49, intervals well across zero).

#### Part 2: breakdowns at the macro low and VAL

| 14-day, first touch from above, closed below | Real | Placebo | Difference, 95% | p |
| --- | --- | --- | --- | --- |
| Discovery 2022 to 2024 (n 1,601 / 3,768) | -0.27% | +0.56% | **-0.83** (-1.63 to -0.06) | 0.037 |
| Test 2025 to 2026 (n 1,610 / 3,104) | -0.27% | +0.79% | **-1.06** (-1.94 to -0.27) | 0.012 |

**The single preregistered hypothesis passes:** breakdowns through the macro
low or VAL were followed by about 1 point more 14-day underperformance than
breakdowns through placebo lines, in both periods.

**Read it carefully.**
- **It is not fresh data.** The hypothesis came from Studies 2 and 2b, whose
  hint already used both periods (including 2025 to 2026). This run narrows it
  to breakdowns and confirms it on the same years, so it is a consistency
  check, not an independent replication. The first truly out-of-sample check
  is data from 2026-10-18 onward.
- **It is not specific to breakdowns.** Arrivals that *held* above the level
  also underperformed placebo arrivals in discovery (14 days -0.58, p 0.048;
  7 days -0.66), though not in test (-0.52, p 0.09; 7 days 0.00).
- **It comes mostly from the macro low.** 14-day means: macro-low breakdowns
  -0.79% (median -1.92%, n = 892), VAL -0.06% (n = 2,330); placebo pivot
  shadows +0.27%, range placebos +0.82%.
- **It is small.** About one point over two weeks, relative to peers.
- The 7-day result agrees in test (-0.75, p 0.012) but not in discovery
  (-0.19, p 0.58).

**Reading for the chart.** At most, the macro low may be described as
"price that broke below the prior cycle low has tended to keep lagging
similar coins slightly over the next two weeks (Coinbase USD, 2022 to 2026)",
with the caveat that this is a small effect not yet confirmed on new data.
No support/resistance language for anything else.

**Closing the price-only track.** Across Studies 2, 2b and 2c: horizontal
levels and candle-pattern triggers add little beyond what price and volume
already say. The consistent findings are about the approach (sharp,
high-volume spikes in thin coins give back) and, weakly, continuation after
breaking the macro low. Further work should use point-in-time context from
the PIT log rather than more price geometry.
