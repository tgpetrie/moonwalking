# Arrival at confirmed highs and lows: does the level matter?

Study 2. The question behind the chart's level panel: when price comes back
to a confirmed swing high or low, or to a macro Fibonacci ratio, does it
react more than it would at an arbitrary line at a similar distance?

This section was written and committed **before** any result was computed.
Design follows Gemini's contract of 2026-10-19 with the corrections noted.

## Preregistered design

**Data.** Native Coinbase daily candles, all 492 USD products including the 89
delisted ones, 2022-01-03 to 2026-10-17 (the same pull as the extended move
study). Liquidity filter as in study 1. Discovery 2022 to 2024, test
2025-01-01 onward.

**Pivots (same rule as Codex's engine).** Weekly bars (Monday 00:00 UTC) built
from complete daily candles. A week is a swing high if its high is strictly
above the two weeks on each side (weeks contiguous); low likewise. A week that
is both is skipped. **Confirmed at the close of the second week after it**
(`confirmed_at`). Nothing about a pivot is used before `confirmed_at`.

**Levels.**
1. *Pivot levels*: every confirmed weekly swing high and low, at its price.
2. *Macro anchors*: as of each day, the highest confirmed high and the lowest
   confirmed low after it (the engine's default), r = 1 and r = 0.
3. *Macro Fibonacci ratios*: r = 0.5, 0.618, 0.786 of that range (linear).
   Each version of the range (it changes when a new pivot confirms) is a
   separate level, eligible from the confirmation that created it.

**Placebos.**
- For pivots: a shadow level for every pivot at `pivot × (1 + u)`, with `|u|`
  uniform in 3% to 15% and a random sign (fixed seed 20261019), same
  eligibility date.
- For Fibonacci ratios: the same range at non-Fibonacci ratios 0.37, 0.44,
  0.56, 0.67, 0.73 and 0.83.

**Arrival (corrected from the contract).** On daily candles, after
`confirmed_at`:
- from below: `High[t-1] < level <= High[t]` (the contract wrote `Low[t-1]`,
  which is almost always true and would count bars already above the level);
- from above: `Low[t-1] > level >= Low[t]`.
Days t-1 and t must be consecutive. `touch_number` counts arrivals at the same
level. **Primary analysis uses first touches only.**

**Outcome.** Forward close-to-close return from the arrival day's close over
1, 3, 7 and 14 days, minus same-day volatility-matched peers (study 1's
method), 1% winsorised. *Reaction* = minus that return when arriving from
below, plus it when arriving from above. So a positive reaction means price
turned back away from the level.

**Primary tests (24, Bonferroni within discovery; confirmed in test over the
discovery survivors; same sign required):** real minus placebo mean
reaction, first touches, by approach side (from below, from above) and
horizon (1, 3, 7, 14 days), for:
- P1 pivot levels vs pivot placebos (8 tests);
- P2 Fibonacci ratios vs placebo ratios (8 tests);
- P3 macro anchors (r = 1 from below, r = 0 from above) vs pivot placebos
  approached from the same side (8 tests).
Inference: moving-block bootstrap over calendar days (7-day blocks) on the
difference of means.

**Secondary, descriptive only (no claims):** reaction for retests
(touch 2+); break rate (arrival-day close beyond the level); entry at the
level price instead of the close; shock arrivals (arrival day ±10% with
5x+ volume) vs grinding arrivals; liquidity under / over $1M a day.

**Reported whatever it shows.** A null (levels behave like placebo lines) is
a valid and useful result for the chart's wording.

## Results

(Added after the run, below this line.)
