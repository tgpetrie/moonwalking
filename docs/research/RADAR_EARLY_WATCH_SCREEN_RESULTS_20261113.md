# Radar early-watch screen: results, 2026-11-13

**No early-watch signal passed the screen.** None of the candle signals picked
future runners among pre-board movers better than their raw 3-minute move,
under the [predeclared rule](RADAR_EARLY_WATCH_SCREEN_PROTOCOL_20261113.md).
The screen did show where the reversal risk sits: coins inside the top eight
crash well more often than they run, while moving coins just outside it are
about evenly balanced. Exploration only, on one-minute candles: 516,812
candidate coin-minutes on 24 days (2026-09-07 to 09-30), checked on 219,565 on
11 days (2026-10-01 to 10-11).

## Where runners and crashers are

Share of coin-minutes that became a runner or a crasher over the next 15
minutes, on candle closes. The last column drops the "entered the top eight"
route from the runner definition so that runner and crasher are exact mirrors;
that column is a check added after the run.

| Group | Window | Runner, as predeclared | Crasher | Runner, mirror definition |
|---|---|---:|---:|---:|
| All tradable coins | screen | 4.78% | 3.15% | 3.38% |
| | check | 4.35% | 3.18% | 3.07% |
| Pre-board movers (candidates) | screen | 6.24% | 3.93% | 4.78% |
| | check | 5.99% | 4.39% | 4.44% |
| Top quarter of candidates by 3-minute move | screen | 8.30% | 5.69% | 6.48% |
| | check | 7.98% | 6.65% | 6.20% |
| Inside the top eight | screen | 11.35% | 14.03% | 9.35% |
| | check | 11.13% | 16.01% | 9.23% |

Candidates are tradable coins outside the top eight by 1- and 3-minute return
whose 3-minute return is above +0.30%; there were about 14 per minute.

- Inside the top eight, crashers outnumber runners by roughly 1.5 to 1 on the
  mirror definition, in both windows. This agrees with the board studies.
- Pre-board movers are close to even: 4.8% against 4.2% in the screen window and
  4.4% against 4.5% in the check window. Ranking them by 3-minute move raises
  both rates by about a third and keeps them close to even.
- The predeclared runner definition is easier to meet than the crasher one,
  because it also accepts entering the top eight. The apparent surplus of
  runners among candidates under that definition mostly disappears with the
  mirror definition. No group reliably runs more often than it crashes.

## Signals against the raw 3-minute move

Top 25% of each day's candidate rows. `ΔP` is the runner-rate difference from
the 3-minute-move baseline, in percentage points, with the daily bootstrap 95%
interval.

| Signal | Screen runners / crashers | Screen ΔP | Check ΔP |
|---|---|---|---|
| R3, raw 3-minute move | 8.30 / 5.69 | baseline | baseline |
| EW5 Bitcoin-relative | 8.66 / 6.12 | +0.36 [+0.04, +0.61], 21 of 24 days | +0.43 [+0.19, +0.67] |
| EW2 volume pace | 6.45 / 3.44 | −1.85 | −2.14 |
| EW3 close location | 4.90 / 3.11 | −3.40 | −3.39 |
| EW4 range breakout | 4.27 / 1.90 | −4.02 | −4.44 |
| EW12 unusual move + volume pace | 4.15 / 1.52 | −4.14 | −4.89 |
| EW1 unusual move | 3.76 / 1.15 | −4.53 | −5.27 |

- The Bitcoin-relative move is consistently a little better than the raw move
  at finding runners, by about 0.4 points. That is under the +1.0 point bar, and
  it brings as many extra crashers, so it does not pass.
- The volatility-scaled signals pick quiet coins: few runners, very few
  crashers. They are not runner finders.

## What this means

- An early-watch list is not a place where runners are easy to find. The
  simplest version, moving coins ranked 9 and below by 3-minute move, flags a
  group that runs about 6–8% of the time and crashes about as often.
- The useful contrast is with the boards. A coin that is already in the top
  eight is past the point where the odds are even. That is an argument for
  showing users rows 9–16 with equal weight, and against treating a top-eight
  entry as a sign of more to come.
- The Bitcoin-relative move is the only candidate with a small, repeatable
  edge on runners. It would need its own confirmation and a use that does not
  depend on avoiding crashers.

## Limits

Exploration on 35 days of one archive holding 407 products; fetch gaps look
like no-trade minutes; consecutive minutes for one coin overlap, so only days
are treated as independent; closes only, with no spread or fill; gainers side
only; whole-day ranking uses later rows.

## Provenance

Protocol, script and three look-ahead checks are in the three commits before
this report. Numbers are in
[RESULTS.json](results/radar_early_watch_screen_20261113/RESULTS.json). The
mirror-definition column came from a one-off check after the run and is not in
that file.
