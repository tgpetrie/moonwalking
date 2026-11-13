# Radar early-watch screen: protocol, 2026-11-13

**Status: exploration, predeclared before any early-watch outcome was
computed.** It follows section 7 of Carbon's runner-study memo. The question:
among coins that are moving but are not yet in the top eight, can one-minute
candles pick the ones that go on to run better than their raw 3-minute move
does? Nothing here confirms a signal or changes a board.

## Data and timing

Local one-minute Coinbase candles, 2026-09-06 to 2026-10-12, gainers side only.
Screen sample: decision minutes on 2026-09-07 to 2026-09-30. Check sample:
2026-10-01 to 2026-10-11.

A decision is made at each minute boundary `τ`. Features read only candles that
closed at or before `τ`. A minute with no row had no trades: its price is the
last earlier close and its volume is zero. The reference price `P(τ)` is that
carried close.

**Universe at `τ`:** USD products, stablecoins excluded, with at least 30 traded
minutes in the previous 24 hours and at least 5 in the previous 60 minutes.

**Candidates at `τ`:** universe coins that are outside the top eight by 1-minute
return and outside the top eight by 3-minute return, with a 3-minute return
above +0.30%.

## Outcome

With returns measured from `P(τ)` on carried closes:

- **Early runner:** 15-minute return ≥ +1.00%, 5-minute return > −0.50%, and
  either the highest close in the next 15 minutes is ≥ +1.50% or the coin enters
  the top eight by 1- or 3-minute return in the next 10 minutes.
- **Early crasher:** 15-minute return ≤ −1.00%, 5-minute return < +0.50%, and
  the lowest close in the next 15 minutes is ≤ −1.50%.

## Signals

All use candles closed at or before `τ`. `r3` is the 3-minute return in percent.

| Id | Formula |
|---|---|
| R3, baseline | `r3` |
| EW1 unusual move | `r3/100 / (sqrt(3)·sigma)`, `sigma = max(0.001, root mean square of the last 60 one-minute returns)` |
| EW2 volume pace | `ln((DV3 + 500) / (DVprior + 500))`, `DV3` = dollar volume of the last 3 minutes, `DVprior` = mean 3-minute dollar volume over the 57 minutes before those |
| EW3 close location | `(P − lowest low of last 3) / (highest high − lowest low of last 3)`, 0.5 if the range is zero |
| EW4 range breakout | `ln(high/low of last 3) / max(0.002, ln(high/low of the 15 minutes before those))` |
| EW5 Bitcoin-relative | `r3 − r3 of BTC-USD` |
| EW12 | mean of the within-day ranks of EW1 and EW2 |

## Metric and screen rule

Rows are candidate coin-minutes. For each UTC day with at least 200 rows and 5
runners, each signal flags its top 25% of that day's rows. `ΔP` is the signal's
flagged runner rate minus R3's; `ΔNet` compares runner rate minus crasher rate
the same way. Days are weighted equally; daily bootstrap 95% intervals, 5,000
replicates, seed 20261116.

A signal goes forward if screen mean `ΔP ≥ +0.010` with the lower bound above
zero, screen mean `ΔNet > 0`, and check mean `ΔP > 0`. The report also gives the
runner rate of all universe coin-minutes, of candidates, and candidates per
minute.

## Known limits, fixed in advance

- Consecutive minutes for one coin overlap heavily; only the day is treated as
  an independent unit.
- The archive holds 407 products pulled once; products absent from it are
  absent from the universe, and fetch gaps look like no-trade minutes.
- Returns use candle closes, with no spread or fill.
- Whole-day ranking uses later rows, which a live list cannot.
