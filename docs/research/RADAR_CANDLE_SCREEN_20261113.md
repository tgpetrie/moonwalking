# Radar candle exploration · November 13

## Board continuation

Use the immutable production board capture and its verified eligible episode
index. Restrict to complete UTC dates September 7 through October 11 in the
existing 1m Coinbase Exchange archive. Compare the first 21 days with the
remaining 14 days as a stability check within exploration. Earlier research
already used this period. Leave November 13 onward for a separately frozen
confirmation.

Reuse the sustained runner and mirrored reversal labels from
[the board screen](RADAR_BOARD_RUNNER_SCREEN_20261113.md). All three gross
checkpoints and both sampled extrema must be finite, with an observed
non-interrupted 15m grade. Keep each board and direction separate.

Anchor candle features to the earlier recorded feature snapshot time.
Allow a 60-second publication lag after a candle closes. Require the exact
minute bars each feature consumes and leave gaps missing. Use directional
percentage change as the reference. Compare these standalone scores:

- **Unusual move** divides the displayed move by the root mean square of 60
  consecutive 1m log returns ending before the trailing 3m signal interval,
  with a 0.10% one-minute floor. Compare on the same fully observed rows.
- **Activity** ranks the estimated USD notional of the trailing three candles
  (`sum(close × base volume)`). It measures activity and cannot identify
  the number or size of individual prints.
- **BTC-relative move** ranks the direction-aligned difference between the
  coin and BTC's synchronized 3m log returns, with BTC excluded as a candidate.

Rank and flag the top quarter per board/day before reading grades. Break
score ties by original move then episode ID. Score the comparator both on
the full input roster and on each signal's matched subset. Report input and
outcome coverage, actual grade coverage among flags, runner precision, adverse
rate, paired precision gain and directional gap. Equal-weight days with at
least 20 input-eligible rows and positive graded denominators for both arms.
Retain days with zero runners. Use paired three-calendar-day blocks for
descriptive 95% intervals on the longer window. A candidate needs positive
runner-minus-reversal balance and at least +1 point precision over raw move
in the first window, a positive lower interval bound for precision gain,
and positive gains and directional balance in the second window before
designing confirmation. The all-day quota measures exploration only.

## Early watch

Replay the same archive dates on a 5m decision grid. Use exact closed
minute candles with the same 60s publication lag and no gap imputation.
The fixed roster is all archived USD products excluding stablecoins.
Before each cutoff require exact coin endpoints, at least 30 traded minutes
in the prior day and five in the prior hour, then exclude the synthetic
top eight by 1m or 3m gain. Consider the remaining coins with at least
+0.30% 3m gain. This synthetic board models ranks from candle closes.

Compare raw 3m return with estimated 3m dollar-volume pace against the prior
57 minutes and volatility-adjusted 3m return. Use matched candidate sets for
each comparison. Both arms may flag one coin per cutoff and use their own
60m product cooldown. Grade flags against the last close known at the cutoff.
Require fresh checkpoints at +5m and +15m and complete intervening observed
closes for this first screen. Success requires +1% at +15m, above −0.5%
at +5m, and either an observed +1.5% close within 15m or graduation into
the synthetic top eight within ten minutes. The adverse mirror uses −1% at
+15m, below +0.5% at +5m, and −1.5% close or synthetic top-eight loser
graduation. Report grade coverage, flag counts, both rates, and observed
lead to graduation among successful graduates. This is a minute-candle
replay with a publication-lag assumption. It cannot establish delivery or
lead time relative to the live board.
