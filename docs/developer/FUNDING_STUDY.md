# Study 3a: does perp funding at the moment of a +10% day separate spikes that hold from spikes that fade?

From Gemini's spec of 2026-10-19, with the open details fixed here.
Everything above "Results" was committed **before** any funding data was
joined to outcomes.

## Data

- **Events:** study 1's extended run (Coinbase daily, 492 USD products incl.
  delisted, 2022-01-03 to 2026-10-17): every +10% up-day (7-day per-coin
  cooldown) as population **A**, and the shock subgroup **B** (5x+ volume vs
  20-day median, move at least 15 points above BTC's, as in study 1). Down
  days (-10%) for the secondary check. Discovery 2022 to 2024, test 2025-01-01
  onward.
- **Outcome:** forward close-to-close return over 1, 3 and 7 days minus
  same-day volatility-matched peers, 1% winsorised (study 1's `m` columns).
- **Funding sources** (public, unauthenticated, one request per second, no
  region workarounds):
  1. `data.binance.vision` USD-M monthly `fundingRate` archives;
  2. Hyperliquid `fundingHistory` (on-chain, hourly).
- **Point in time:** for event day t, only prints settled in
  `(t 00:00 UTC, t+1 00:00 UTC]`, i.e. the 24 hours ending at the daily
  close. Each print is converted to an 8-hour equivalent (`rate x 8 /
  interval_hours`; Hyperliquid interval = 1 h) and the day's value is the
  mean of those prints. Binance is used when it has prints in the window,
  otherwise Hyperliquid.
- **Symbol mapping:** Coinbase base `B` to Binance `BUSDT`, `1000BUSDT` or
  `1000000BUSDT`, and Hyperliquid `B` or `kB`. RNDR and RENDER map only to
  their own symbols. **Identity check** per pair: daily closes from one month
  of overlap (Binance monthly klines archive; Hyperliquid `candleSnapshot`)
  must match Coinbase within 5% (median absolute ratio error after the 1000x
  multiplier). Pairs that fail are treated as unverified and excluded from
  F1 and F2.
- **Perp-listed on day t** = a verified funding value exists for day t.
  **Spot-only** = no print from either source. Limitation: perps on other
  venues (OKX, Bybit, ...) are not seen, so some "spot-only" coins had a perp
  elsewhere.

## Regimes (8-hour equivalent)

- negative: below 0;
- neutral: 0 to +0.02%;
- crowded long: above +0.02%.

## Primary tests (10; Bonferroni within discovery, confirmed in test over the discovery survivors, same sign; 7-day block bootstrap over calendar days)

- **F1** negative minus crowded-long, populations A and B, horizons 1, 3, 7
  days (6). Hypothesis: short-squeezed rallies fade less (difference > 0).
- **F2** perp-listed minus spot-only at 7 days, within the two liquidity
  tiers (prior 20-day median dollar volume under / at least $1M), populations
  A and B (4). Two-sided.

## Secondary, descriptive

- Spearman correlation between day-t funding and the 7-day outcome.
- Tails: funding at or below -0.05% vs at or above +0.05%.
- -10% days: negative vs crowded-long funding, 7-day outcome.
- Binance vs Hyperliquid agreement on days where both exist (2025 to 2026).
- Coverage: how many events had a verified perp, by year.

**Reported whatever it shows.**

## Results

(Added after the run, below this line.)
