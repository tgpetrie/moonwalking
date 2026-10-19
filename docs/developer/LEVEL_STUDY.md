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

### Run of 2026-10-19 (`scripts/move_study/level_study.py`, `data/move-study/level_study.json`)

16,672 confirmed weekly pivots across 492 products produced 76,783 levels
(real and placebo) and 276,209 liquid arrivals, 27,313 of them first touches.

**Primary result: the levels do not matter.** No test survives in discovery
(0 of 24 after Bonferroni), so nothing can replicate. Real and placebo means
are close throughout. 7-day reaction, first touches, discovery / test:

| Level | From | Real | Placebo | Difference (discovery) | Difference (test), 95% |
| --- | --- | --- | --- | --- | --- |
| Confirmed pivot | below | +2.31% | +2.19% | +0.11 | +0.02 (-0.79 to +0.85) |
| Confirmed pivot | above | -0.35% | -0.23% | -0.12 | -0.26 (-0.70 to +0.15) |
| Fibonacci 0.5 / 0.618 / 0.786 | below | +3.73% | +3.28% | +0.45 | -0.07 (-1.29 to +0.99) |
| Fibonacci 0.5 / 0.618 / 0.786 | above | -0.45% | +0.37% | -0.83 | +2.15 (-0.01 to +4.40), n = 90 |
| Macro high (r = 1) | below | +2.05% | +2.19% | -0.14 | -0.98 (-4.21 to +2.71) |
| Macro low (r = 0) | above | -0.44% | -0.23% | -0.21 | -0.30 (-0.84 to +0.20) |

(Reaction: positive means price turned back away from the level.) Break
rates on the arrival day are also alike: about 40% for real pivots and 39 to
42% for placebo lines. One weak pattern: at the macro low, the 14-day
difference is -0.86 in discovery and -0.85 in test (price kept falling a little
more than at placebo lines), but it does not pass the discovery threshold
(p 0.71 after correction). Not a finding.

**What does matter is the path (descriptive, post hoc).** Rising into *any*
line, real or placebo, is followed by a fall of about 2% relative to peers
over 7 days. That is study 1's give-back, not the level. For first touches of
real pivots from below:
- shock arrival (+10% day, 5x+ volume, coin-specific): 7-day reaction +6.0%
  (median +9.9%, n = 1,366); grinding arrival: +0.3% (median +2.6%,
  n = 2,727);
- under $1M a day: +3.3%; $1M a day and up: -0.3%.
Falling into a level shows no bounce on average (-0.2%, median -0.9%), and
retests behave like first touches.

**For the chart.** There is no evidence that a confirmed high, low, macro
anchor or Fibonacci ratio produces a reaction beyond an arbitrary line at a
similar distance, on Coinbase daily data from 2022 to 2026. Levels are fine as
historical reference and context. Do not label them support or resistance,
and do not suggest a reaction is likely there. If the panel says anything
about what happens next, the evidence is about the approach: sharp,
high-volume rises into any level, especially in thin coins, have tended to
give back.

**Limits.** Daily bars only (no intraday touch order), one exchange, linear
Fibonacci on the engine's default macro range, a ±3 to 15% placebo
distance chosen in advance and not tuned. A different pivot rule or other
timeframes could behave differently and would need their own preregistration.
