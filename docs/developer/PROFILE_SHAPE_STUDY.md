# Study 2d: daily profile shapes, multi-day balance breakouts, volume ledges

From Gemini's brief of 2026-10-19 (Deep Charts auction-market claims), local
data only. Everything above "Results" was committed **before** any result was
computed.

## Common

- Outcome: forward close-to-close return from day t's close over 1, 3 and 7
  days minus same-day volatility-matched peers, 1% winsorised (study 1's
  method). For downside events the sign is flipped, so positive always means
  "continued in the event's direction".
- Liquidity: study 1's rule on day t. 7-day cooldown per coin per event type
  (first event counts).
- Inference: 7-day moving-block bootstrap over calendar days. 22 primary
  tests in one family: Bonferroni within discovery, confirmed in test over
  the discovery survivors, same sign required.
- Splits: hourly-archive tests (S1, S2h) use discovery 2025-10-02 to
  2026-03-31 and test 2026-04-01 to 2026-10-10; daily tests (S2d, S3) use
  discovery 2022 to 2024 and test 2025-01-01 to 2026-10-17.

## S1: P-shape vs bottom-heavy rally, b-shape vs top-heavy drop (hourly archive)

- Day profile: the day's hourly candles (at least 20 of 24 present), 20
  equal bins over the day's `[Low, High]`, each hour's volume spread uniformly
  over its own `[low, high]`. `poc_pos` = POC bin midpoint position in the
  range; `close_pos` = close position in the range.
- Directional day: `|move| >= 5%` (close to close) and `(High - Low) / Low >= 5%`.
- **P-shape**: move >= +5%, `poc_pos >= 0.60`, bottom 6 bins (30% of the
  range) hold < 15% of the day's volume, `close_pos >= 0.70`.
  **Bottom-heavy rally (control)**: move >= +5%, `close_pos >= 0.70`,
  `poc_pos <= 0.40`.
- **b-shape**: move <= -5%, `poc_pos <= 0.40`, top 6 bins hold < 15% of
  volume, `close_pos <= 0.30`. **Top-heavy drop (control)**: move <= -5%,
  `close_pos <= 0.30`, `poc_pos >= 0.60`.
- Tests (4): P minus bottom-heavy, and b minus top-heavy (continuation sign),
  at 1 and 3 days. The claim predicts both differences > 0.

## S2: three-day balance, then a breakout (two versions)

- **S2h (hourly archive):** each day's 70% value area from its 20-bin
  profile (Study 2b's rule). Balance = days t-3, t-2, t-1 where the POC of t-2
  lies inside the value area of t-3, and the POC of t-1 lies inside the union
  of the value areas of t-3 and t-2. Merged area = lowest VAL to highest VAH
  of the three days. Breakout: day t closes above the merged VAH (up) or below
  the merged VAL (down).
- **S2d (daily 2022 to 2026):** balance = days t-3, t-2, t-1 each with range
  (`(High - Low) / Close`) at most 1.5x its prior 20-day median range, each
  overlapping the previous day's range. Merged range = lowest low to highest
  high. Breakout: day t closes beyond it.
- **Control:** days t in the same direction with no balance before them,
  matched on day t's move in 2-point bins and reweighted to the breakouts'
  distribution of moves.
- Tests (12): breakout minus control, up and down, 1 / 3 / 7 days, for S2h and
  S2d.

## S3: volume ledges on swing legs (daily 2022 to 2026)

- Legs and 100-bin profiles exactly as Study 2b. Smoothed profile = 3-bin
  centred moving average. A ledge is the boundary between bins b and b+1
  where `|S[b] - S[b+1]|` is largest among boundaries where the higher side is
  an HVN bin (at least the 80th percentile of the smoothed profile); one ledge
  above the POC bin and one below. Level = the boundary price.
- Placebos: Study 2b's range ratios on the same leg.
- Arrival and first touch as Study 2; reaction sign as Study 2 (positive =
  turned back from the level).
- Tests (6): ledge minus placebo, from below and from above, 1 / 3 / 7 days.

**Reported whatever it shows.**

## Results

(Added after the run, below this line.)
