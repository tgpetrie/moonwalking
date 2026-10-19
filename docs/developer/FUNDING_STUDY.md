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

### Run of 2026-10-19 (`scripts/move_study/funding_study.py`, `data/move-study/funding_study.json`)

**Data.** About 11,100 public requests in total: 6,256 Binance monthly funding
archives (some 404, meaning no perp that month), 4,383 Hyperliquid daily windows,
and identity checks.
The download was resumed once after a dropped connection (`d987304`); cached files
were not re-fetched.

**One change before outcomes were joined.** The first identity check used each
coin's median event month for Binance prices; for 22 coins that month predated the
perp (klines 404). Those were re-checked on the median month among event months that
have a funding file (17 more requests). This was decided and run with `--checks-only`
(identity and coverage only) before any funding was joined to returns. Result:
Binance 298 of 309 pairs verified. Failures: price mismatches, i.e. a different
token under the same ticker, for AI (49% median error), RAY (83%), CVC (41%), HNT
(81%), EDGE (5x) and AERGO (10%), plus 5 with no usable price month (LOOM, QUICK,
BOND, JUP, WAL). Hyperliquid: 132 of 140 verified (MATIC, JUP, STG, LIT, USELESS, AI
returned no candles; RNDR had 8 overlapping days; LOOM none). Failed pairs are
excluded as preregistered.

**Coverage, +10% days:** 5,282 with verified funding on the day (Binance 5,212,
Hyperliquid 70), 3,573 spot-only, 179 unverified. Regimes: neutral 3,147, negative
1,735, crowded long 400 (only 87 crowded in the 2025 to 2026 test period, 15 among
shocks). Binance and Hyperliquid agree where both exist (3,801 event days: Pearson
0.95, same regime 71%).

**Primary result: the funding hypothesis fails; perp listing replicates.** 1 of 10
tests survives discovery and it replicates. Outcome: 7-day return minus
volatility-matched peers (1 / 3 / 7 days for F1).

| Test | Discovery | Test | Verdict |
| --- | --- | --- | --- |
| F1 all +10% days, negative minus crowded, 1 / 3 / 7 d (n 651 vs 313) | +0.12 / +0.17 / +0.63, Bonferroni p 1.0 | +0.56 / +2.65 / +1.79 (n 1,078 vs 87) | fails |
| F1 shocks, negative minus crowded, 1 / 3 / 7 d (n 120 vs 55) | -1.52 / -2.28 / -0.99, p 1.0 | too few crowded (15) | fails |
| **F2 thin coins (<$1M), perp-listed minus spot-only, 7 d** | **+2.17** (+0.60 to +3.70), p 0.035; perp -1.05% vs spot-only -3.22% (n 1,097 / 1,912) | **+3.26** (+1.89 to +4.63), p 0.0003; -1.69% vs -4.95% (n 1,727 / 1,057) | **replicates** |
| F2 liquid (>=$1M), 7 d | +1.99 (+0.01 to +3.87), p 0.50; -0.53% vs -2.52% | +2.15 (-0.43 to +4.54); n spot-only 121 | fails |
| F2 thin shocks, 7 d | +3.81 (+0.39 to +7.14), p 0.29; -3.17% vs -6.98% | +4.49 (+2.11 to +6.79); -5.84% vs -10.33% | fails discovery |
| F2 liquid shocks, 7 d | +5.04, n 94 vs 42, p 1.0 | too few (11) | fails |

**Reading.**
- **Funding does not separate spikes that hold from spikes that fade.** Negative
  funding at the close (shorts paying, the "short squeeze" story) did no better
  than crowded-long funding. Among shocks it did slightly *worse* in discovery.
- **Perp listing does.** Among thinly traded Coinbase coins, +10% days on coins
  with a Binance or Hyperliquid perp gave back about 2 to 3 points less over 7
  days than spot-only coins, in both periods. Perp-listed thin coins still lag
  their peers (-1.05% / -1.69%), just less. The same sign shows for liquid coins and
  for shocks, but those tests did not pass.
- **Spot-only thin coins carry most of Study 1's thin-coin fade:** -3.2% / -5.0% over
  7 days, and spot-only thin shocks -7.0% / -10.3%.

**Not causal.** A perp listing goes with other things: a Binance listing, more
trading on other venues, an older and larger coin. "Thin on Coinbase" can mean
"liquid elsewhere" for a perp-listed coin. One plausible reading, not tested here: a
spike in a spot-only coin is local to a few venues and nothing arbitrages it, so it
reverts. Perp status is known on the day (settled prints in the day's window), so
this is not look-ahead, but "spot-only" includes coins with perps on venues we did
not see (OKX, Bybit and others).

**Secondary, descriptive only.**
- Funding vs the 7-day outcome: Spearman -0.02 (discovery) and +0.07 (test). No
  relationship.
- By regime, all periods: neutral -0.38% (median -2.25%), negative -1.93%
  (-3.47%), crowded -2.43% (-6.39%). Both tails fade more: funding <= -0.05% -3.88%,
  >= +0.05% -3.65%. Unusual funding in either direction goes with more give-back,
  not less. This was not preregistered, and the neutral bucket overlaps with
  Binance's default 0.01% rate on quiet, liquid coins.
- -10% days, negative minus crowded, 7 days: +1.55 (discovery) and +1.38 (test),
  both intervals across zero.

**For the chart.** Perp status is a fact known on the day, so it could be shown as
context. Defensible wording: "Among thinly traded Coinbase coins, +10% days on coins
without a Binance or Hyperliquid perpetual have tended to give back more over the
next week than on coins with one (2022 to 2026, relative to similar coins)." No
per-coin number, probability or target. Funding itself should not be presented as
a squeeze or continuation signal.
