# Elliott ABC chart engine: evaluation protocol, 2026-11-15

Written and committed before `evaluate_elliott_abc_20261115.py` was run on any
outcome. The engine, the driver and their synthetic checks are in the same
commit. Results go to
[ELLIOTT_ABC_CHART_ENGINE_20261115.md](ELLIOTT_ABC_CHART_ENGINE_20261115.md).

## What is being tested

`backend/elliott_wave_engine.py` reads swing structure from candles and names
ABC corrections and five-wave impulses. Two questions:

- **Part A.** Do its ABC signals mark turning points on their own? Does the
  indicator and higher-timeframe confluence add anything to the bare geometry?
- **Part B.** Does the chart structure at the moment of a Radar A1 flag separate
  runners from crashers among those flags?

## Frozen before the run

The engine is used as shipped. None of these were fitted to this data; they are
the task's defaults and textbook ratios.

- Swings: causal ZigZag, reversal at 2.2 × Wilder ATR(14) on a bar close, or a
  close through the previous opposite pivot.
- ABC: B retraces 0.236 to under 1.0 of A; C ends beyond A, between 0.618 and
  1.618 of A measured from B, without breaking the origin of the prior move.
- Confluence weights: higher-timeframe trend 0.30 (subtracted when it opposes),
  RSI(14) divergence 0.20, MACD histogram divergence 0.15, wave C volume at most
  0.85 of wave A 0.15, Bollinger reclaim 0.10, fast-EMA reclaim 0.05, a prior
  five-wave move 0.05. "With confluence" means a score of at least 0.50.
- Reads use a trailing window of 300 closed bars and up to 120 closed
  higher-timeframe bars: 4h for 15m and 1h reads, 1d for 4h reads.

## Data

- One-minute candles from the archive (from 2026-09-07) and the 2026-11-13
  backfill, merged at their seam, resampled to wall-clock 15m, 1h and 4h bars.
  The archive only supplies history before the scored window.
- Candles and entries from 2026-11-13 00:00 UTC stay sealed. The driver refuses
  to load them and refuses any outcome window that crosses the seal.
- Every read sees only bars that had closed by its decision time.

## Part A: standalone signals

- **Universe.** The 100 USD products with the most dollar volume in the archive
  from 2026-09-07 to 2026-10-11, among products that also appear in the
  backfill. Products whose whole price range in that period is under 2% are
  dropped as pegged. The top 40 are reported separately as a robustness line.
- **Signals.** Bar closes from 2026-10-13 00:00 to 2026-11-12 00:00 UTC.
  - `complete`: the bar whose close confirms wave C. One per count.
  - `zone`: the first bar that finds wave C inside its projected zone. One per
    count. Secondary.
- **Trade frame.** Entry at the signal bar's close. Target is the wave B
  extreme. Stop is the engine's `invalidation_price`: the wave C extreme for
  `complete`; the nearer of the 1.618 extension and the prior origin for
  `zone`. Signals with no room between stop, entry and target are counted and
  dropped.
- **Outcomes**, from one-minute candles opening at or after the entry time, at
  4h, 12h and 24h: maximum favorable and adverse excursion, target first, stop
  first, and R. R is reward over risk when the target comes first, −1 when the
  stop does, otherwise the mark at the horizon in risk units. A minute that
  touches both counts as the stop. `Rnet` subtracts a 0.25% round trip.
- **Comparisons.**
  - (a) ABC with confluence against all ABC geometry, and against ABC without
    confluence.
  - (b) Each signal against 20 placebo entries at random bar closes of the same
    product and timeframe in the same window, with the same percent stop and
    target distances. The difference is paired per signal.
  - Secondary control: the same, drawn only from bars that confirmed a swing of
    the same kind without completing an ABC.
- **Intervals.** 95% percentile intervals from 5,000 resamples of three-day
  blocks by entry day, seed 20261117.
- **Primary cell.** Bullish `complete` signals on 1h bars, at 24h. Every other
  timeframe, direction and signal type is secondary and descriptive.
- **Reading rule.**
  - Geometry beats placebo when there are at least 100 signals and both the
    target-first rate and mean R exceed the random placebo with interval lower
    bounds above zero.
  - Confluence beats placebo by the same test on at least 50 confluence signals.
  - Confluence adds to geometry when, on at least 50 confluence signals, both
    measures exceed ABC without confluence with lower bounds above zero.
  - Fewer signals than that reads as underpowered, not as a result.

## Part B: A1 flags and chart structure

- **Population.** Exactly the rows, labels, causal seven-day thresholds and
  windows of `confirm_a1_gate_20261115.py` (2026-10-13 to 2026-11-12, halves
  split at 2026-10-28). The driver refuses to continue unless it reproduces the
  published 51,997 entries and 12,773 / 12,465 flags on 3m gainers.
- **Structure at the flag.** 15m and 1h reads from bars closed by the flag's
  entry time. A live ABC is a complete count not yet resolved, or wave C inside
  its zone. Aligned means bullish on the gainer boards and bearish on 3m losers.
- **Arms**, each a subset of the A1 flags:
  - `w_abc_conf` (primary): aligned live ABC with confluence on 15m or 1h.
  - `w_abc`: aligned live ABC on 15m or 1h.
  - `w_trend`: aligned live ABC, or an aligned impulse in progress with no
    opposing live ABC.
  - `w_no_opp`: no opposing live ABC on 15m or 1h. A veto.
- **Comparison.** `screen.compare` unchanged: paired daily runner and crasher
  rates of the arm against all A1 flags, three-day block intervals.
- **Primary.** `w_abc_conf` on 3m gainers (`confirmation_3m_up/up`).
- **Reading rule.** The arm improves A1 when at least 20 days are scored, the
  net rate (runners minus crashers) rises by at least 1.00 point, and the block
  lower bound is above zero. Stability is the same sign in both halves.
- Also reported: pooled runner and crasher rates of A1 flags by structure class.

## Known limits, stated in advance

- These dates are not fresh. Radar outcomes on them have been read several
  times. The wave engine has never been scored on them, and its parameters were
  set without them, but any positive result here is a screen, not a
  confirmation.
- Signals cluster in time across products. Block intervals account for
  day-level clustering only.
- Placebos match stop and target distance, product and timeframe. They do not
  match the market state at the signal.
- One run. No parameter is revisited after outcomes are seen. Fixes to defects
  that do not change a definition are allowed and will be listed.

```powershell
~\.moonwalking\venv\Scripts\python.exe scripts/scoring_experiment/evaluate_elliott_abc_20261115.py
```
