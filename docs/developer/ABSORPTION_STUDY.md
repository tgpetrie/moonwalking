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
