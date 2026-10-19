# COTI-USD analysis, 2026-10-19

Descriptive only: what the data says, not a forecast and not advice. Price
$0.010704 at 10:48Z on 2026-10-19 (open daily bar). Source: Coinbase Exchange
public candles, unauthenticated. Nothing on any trading page or account was
touched.

## 1. Data

- COTI-USD daily, 2021-08-26 to 2026-10-18: 1,880 complete candles, no missing
  day, plus today's open bar. Nothing earlier on Coinbase (the probe returned
  empty). Product online. Token: Ethereum, `0xDDB3...55c5`.
- Lowest daily low in that history: $0.0072 on 2026-07-20. This is a lifetime
  low for the Coinbase product only. COTI may have traded elsewhere before it
  listed there; that was not checked, so no all-time low is claimed.

## 2. Where price is

- 59.9% below the 2026-09-18 high ($0.026681), 49% above the 2026-07-20 low
  ($0.0072), 9% above the 60-day low ($0.009789, 2026-08-21).
- The run from $0.0072 to $0.026681 took 60 days (+271%). Price has given back
  about 82% of it. Linear retracement levels of that run: 0.618 = 0.01464,
  0.702 = 0.01301, 0.786 = 0.01137, 1.0 = 0.0072. Price is below the 0.786
  level. (Calculated with the chart engine's linear convention; the engine
  itself returns no scenario here, see section 5.)
- 7 days: -20.5%. 30 days: -49.5% (2nd percentile of 266 liquid coins). 90
  days: +45.3%.
- Activity is fading: median daily dollar volume $374k over the last 7 days vs
  $656k over 30 days; the Sep 17 spike day traded $5.3M. Daily volatility 5.6%
  over 30 days against 10.7% over 90.

## 3. The spike and what followed

| Day | Move | Next day | 3 days | 7 days |
| --- | --- | --- | --- | --- |
| 2026-09-17 | +46.9% | -16.0% | -28.1% | -35.9% |
| 2026-07-31 | +20.7% | -8.6% | -23.9% | -22.7% |
| 2026-08-12 | +25.0% | -9.6% | -16.0% | -20.7% |

(Forward returns from the event day's close.) Over COTI's whole Coinbase
history, 73 days rose 10% or more: the following 1, 3 and 7 days averaged
-2.1%, -1.9% and -4.2% (medians -2.7%, -3.5%, -5.5%). 62 days fell 10% or
more: +0.8%, -0.7%, -1.8%, small and noisy. This is one coin, so it is
descriptive. The cross-coin study (MOVE_STUDY.md) found the same tendency
after +10% days across 492 products, 2022 to 2026. The last 10%+ day was
2026-09-28 (-12.1%), so there is no current event for the study to speak to.

## 4. Levels (Codex's chart engine, run read-only on this data)

Confirmed weekly pivots (2 bars each side), latest: low $0.0072 (week of
2026-07-20), high $0.0206 (07-27), high $0.026681 (09-14, confirmed 10-05).
The week of 10-12 has a candidate low of $0.010234 that is provisional: it is
confirmed only if the next two weekly lows stay above it (earliest 2026-11-02).

Nearest confirmed support cluster, from February 2026: $0.0103 (week of 02-02)
and $0.0108 (week of 02-23). Price touched the ±3% bands of both on
10-15 to 10-18 (low $0.010234). Past touches of the $0.0103 band, and what
the next seven days did:

| Touch | Exit | 7 days after |
| --- | --- | --- |
| Jun 5 to 9 | below | +3.1% |
| Jun 11 to 18 | below | -12.5% |
| Jul 27 to 29 | above | -25.3% |
| Aug 11 to 21 | above | +10.3% |

Two up, two down: a touch of this level has not meant a reliable bounce. The
$0.0108 band (9 episodes) is similarly mixed.

Overhead references: $0.0134 (7 touch episodes, mixed), $0.016 (8 episodes,
every one followed by a negative 7-day return, -0.6% to -29%), $0.0206 (2
episodes, -6.4% and -21.1%). Small, overlapping samples; not predictive.

Engine outputs that do not apply: the recent A-B-C extension scenario errors
(the Sep high exceeds the starting high of $0.016, so it is not a
rise/pullback), and the macro range (high $0.689 on 2021-09-20 to low $0.0072)
puts the recovery band at $0.348 to $0.543, about 32x the current price.

## 5. Indicators, weekly (complete weeks to 2026-10-12)

Price is below the 50-, 100- and 200-week averages ($0.01575, $0.04551,
$0.06572; COTI has 250 weekly bars, so SMA200 is available). MACD -0.00067,
signal -0.00131, histogram +0.00063. RSI 42.7. Stoch RSI K 58.8, D 69.2.

The repo's chart reader (descriptive, outcome_validated false):
- 1h, last 12 days: direction down, lower area $0.010234 to $0.011099, upper
  $0.013214 to $0.01375, trading activity normal.
- 1d, last 60 days: direction down, lower area $0.009789 to $0.0117, upper
  $0.018504 to $0.026681, activity low. Range position 5% (near support).

## 6. Moonwalking's own COTI record

241 signals from 2026-09-06 to 2026-10-17, all graded: 13.7% followed
through (store-wide 16.0% over 132,523 signals on 402 coins), 82.6% did not.
"Breakdown confirmed" down: 10.0% of 40 (store 22.9%). "Continuation favored"
up: 1 of 9 (store 11.6%). "Quiet flow building": 0 of 41. 204 board entries
averaged -0.16% over 15 minutes against -0.13% for their matched controls, with
an estimated cost of about 0.2%. No edge shown. No COTI signals after
2026-10-17 03:52.

## 7. Market backdrop (checking the Quantum Macro Brief's own invalidation list)

As of the 2026-10-18 close, Coinbase daily data for 266 liquid coins:
- BTC $82,007: 13% above its 200-day average, 0.8% above its 50-day, 5% below
  its 90-day high, +1.4% over 30 days. Holding.
- Alts are weaker: ETH -5.6% vs its 50-day, SOL -4.9%; the median liquid coin
  fell 12.4% in 7 days and only 9% rose. 37% of coins are above their own
  50-day average, down from 85% a month ago; 52% above their 200-day.
- Rotation into alts is not visible: over 30 and 90 days, 43% and 44% of coins
  beat BTC.

So part of COTI's last week is market-wide; most of the 30-day fall is the
give-back of its own spike. The brief's macro claims (Fed path, liquidity) were
not verified and have no direct bearing on these numbers.

## Limits

One venue. Levels are touch counts from small overlapping samples, not
forecasts. Study results are relative to similar coins and before real costs.
Nothing here says where COTI goes next.
