# Study 2b: fixed-range volume profile levels vs placebo lines

Do volume-profile levels (point of control, value area high and low, high-
and low-volume nodes) built on confirmed swings get a different reaction
from price than placebo lines in the same range? This follows Gemini's
brief of 2026-10-19 and Study 2 (`LEVEL_STUDY.md`). Everything above
"Results" was committed **before** any result was computed.

## Preregistered design

**Data and split.** As Study 2: Coinbase daily candles, 492 USD products
(89 delisted), 2022-01-03 to 2026-10-17, study 1's liquidity filter,
discovery 2022 to 2024, test 2025-01-01 onward. Confirmed weekly pivots as in
Study 2 (strict, two weeks each side, confirmed at the close of the second
week after).

**Swing legs (built causally, no hindsight).** Pivots are processed in order
of confirmation. An alternating high/low sequence is kept as in Codex's
engine: a pivot of the same type as the last one replaces it only if more
extreme. Every time the sequence's last element is appended or replaced, the
leg from the previous element to it is emitted, **eligible from that
pivot's confirmation date and from then on**. A leg replaced later stays in
the sample: it was a real leg when it was drawn. Range `[L, H]` = the two
pivot prices; bars = daily candles from the first pivot's week through the
end of the second pivot's week.

**Profile.** 100 equal linear bins over `[L, H]`. Each bar's base-currency
volume is spread uniformly over the part of its `[low, high]` that lies
inside `[L, H]`; the share outside the range is dropped.
- **POC:** midpoint of the bin with the most volume (lowest bin on a tie).
- **Value area (70%):** from the POC bin, repeatedly add the neighbouring bin
  (above or below) with more volume (above on a tie) until the included bins
  hold at least 70% of the profile. VAH = top edge, VAL = bottom edge.
- **Nodes (interior bins 5 to 94 only):** HVN bins have volume at or above
  the 80th percentile of the 100 bins; LVN bins at or below the 20th
  percentile with an HVN bin somewhere above and below. Contiguous runs merge
  into one node, placed at the midpoint of the run.

**Placebos.** Same leg, same eligibility date, at ratios 0.37, 0.44, 0.56,
0.67, 0.73 and 0.83 of `[L, H]`.

**Arrival and outcome.** As Study 2: from below `High[t-1] < level <=
High[t]`, from above `Low[t-1] > level >= Low[t]`, consecutive days, first
touches only. Reaction = forward close-to-close return over 1, 3, 7 and 14
days minus same-day volatility-matched peers (1% winsorised), sign flipped
for arrivals from below so positive means price turned back away from the
level. Continuation = minus reaction. Break = the arrival day closes beyond
the level.

**Primary tests (22; Bonferroni within discovery, confirmed in test over the
discovery survivors, same sign required), bootstrap over calendar days in
7-day blocks:**
- **VP1** POC first touch minus placebo first touch, reaction, by side and
  horizon (8).
- **VP2** VAH from below and VAL from above minus placebo from the same side,
  reaction, by horizon (8).
- **VP3** LVN first touch minus HVN first touch, by side: break rate, and
  continuation at 1 and 3 days (6). The course claim predicts LVN > HVN.

**Secondary, descriptive only.** POC retests; at VAH/VAL, 7-day reaction
split by arrival-day close (back inside vs beyond) next to the same split at
placebo lines; shock vs grinding arrival; liquidity under / over $1M a day.

**Hourly check (secondary).** For legs lying wholly inside the hourly
archive (2025-10-01 to 2026-10-10; current products only), rebuild the
profiles from hourly candles and repeat VP1 and VP2 on that subset, with the
daily-profile result on the same subset next to it.

**Reported whatever it shows.**

## Results

(Added after the run, below this line.)

### Run of 2026-10-19 (`scripts/move_study/volume_profile_study.py`, `data/move-study/volume_profile_study.json`)

14,352 causal swing legs, 104,516 first touches among 1.37 million liquid
arrivals.

**Primary result: volume-profile levels behave like placebo lines.** 0 of 22
tests survive discovery, so nothing replicates. 7-day reaction, first
touches, real minus placebo (positive = price turned back from the level):

| Level | From | Discovery 2022 to 2024 | Test 2025 to 2026, 95% |
| --- | --- | --- | --- |
| POC | below | +0.49 | +0.09 (-0.59 to +0.71) |
| POC | above | -0.14 | +0.03 (-0.40 to +0.44) |
| VAH | below | -0.25 | +0.11 (-0.32 to +0.54) |
| VAL | above | -0.55 | -0.34 (-0.80 to +0.09) |

**Magnets vs highways (VP3): no difference.** Arrival-day break rate at LVNs
vs HVNs: 39.3% vs 38.7% from below, 42.6% vs 40.2% from above in discovery
(and alike in test). Continuation after 1 and 3 days is not faster through
LVNs; every interval includes zero. The course claim that price stalls at
HVNs and travels through LVNs does not show up in daily Coinbase data.

**Hourly profiles (the caveat about daily smearing).** For 3,534 legs inside
the hourly archive, profiles rebuilt from hourly candles give the same
answer as daily ones: 7-day difference vs placebo for POC from below -0.18
(hourly) vs -0.35 (daily), POC from above +0.65 vs +0.65, VAH -0.02 vs +0.14,
VAL +0.02 vs +0.10, every interval including zero. Coarse daily binning is
not hiding a signal here; the hourly sample is small (about 500 to 1,100
first touches per cell, one year).

**Secondary, descriptive.**
- *Reaction vs acceptance:* arriving from below and closing beyond VAH is
  followed by more give-back (+2.5%) than closing back inside (+1.2%), but the
  same split at placebo lines is +2.6% vs +1.35%. The candle pattern carries
  the information, not the level.
- *Path, again:* POC reached from below on a shock day (+10%, 5x volume,
  coin-specific): 7-day reaction +7.8% (median +10.6%, n = 1,060); grinding:
  +0.6%. Thin coins under $1M a day: +2.8%; $1M and up: +0.5%.
- *Retests* behave like first touches.
- One weak pattern, not a finding: falling into VAL, the 14-day difference
  is -0.64 (discovery) and -0.80 (test), price continuing a little lower than
  at placebo lines. Study 2 saw the same at the macro low (-0.86 / -0.85).
  Neither passed the discovery threshold. If it matters, it needs its own
  preregistered test.

**For the chart.** Same conclusion as Study 2: POC, value area and volume
nodes are fine as descriptive context but do not justify "support",
"resistance", "magnet" or "highway" language. What follows an arrival
depends on how price got there and how thin the coin is.

**Limits.** Daily arrivals (no intraday order of touches), one exchange,
base-currency volume, 100 bins and a 70% value area fixed in advance; legs
from one pivot rule. The hourly check covers one year and current products
only.
