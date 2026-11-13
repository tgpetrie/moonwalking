# Radar runner signal screen (step 1): results, 2026-11-13

**No stored-snapshot signal passed the screen.** None found runners more often
than plain percentage change on any board. The run followed the
[predeclared protocol](RADAR_RUNNER_SIGNAL_SCREEN_PROTOCOL_20261113.md) and
used only exploration data: 333,104 board entries from 2026-08-18 to 2026-10-17,
plus 54,033 from 2026-10-18 to 2026-10-27 as a check.

The more useful finding is about percentage change itself. Its top quarter
contains more runners than average and nearly twice as many crashers as
runners.

## Percentage change finds action, not direction

Daily average, top quarter of each day's entries by displayed move, screen
sample:

| Board | Runner base rate | Runner rate, top quarter | Crasher base rate | Crasher rate, top quarter |
|---|---:|---:|---:|---:|
| 1m gainers | 2.72% | 4.37% | 3.49% | 7.75% |
| 3m gainers | 2.95% | 4.81% | 3.98% | 8.98% |
| 3m losers | 2.71% | 4.95% | 4.07% | 8.78% |

A runner holds at least +1% at 15 minutes, has not fallen below −0.5% at 5
minutes, and reaches +1.5% by 15 or 30 minutes. A crasher is the mirror image.
On the losers board, "runner" means the fall continued.

So the coins moving most do run more often, about 1.6 to 1.8 times the base
rate, and they crash about 2.2 times as often. A ranking by percentage change
is a good answer to "where is the action", and a poor answer to "which way will
it go". This matches the fade found in the fresh replication and Codex's screen
that the biggest movers produce more runners: both are true, because those
coins move more in both directions.

The runner base rate is 2.7–3.0%, just under the 3–15% range Carbon expected.
Per the protocol, the thresholds were not changed.

## Every signal, against percentage change

`ΔP` is the signal's runner rate minus percentage change's, at the same 25%
flag share, in percentage points, with the daily bootstrap 95% interval.
`ΔNet` is the same comparison for runner rate minus crasher rate.

| Signal | 1m gainers ΔP | 3m gainers ΔP | 3m losers ΔP | ΔNet, all boards |
|---|---:|---:|---:|---|
| 1A acceleration | +0.09 [−0.07, +0.24] | −1.14 [−1.38, −0.90] | −1.43 [−1.72, −1.15] | +0.3 to +1.2 |
| 1A− the reverse | −2.37 | −2.23 | −2.24 | +3.1 to +3.4 |
| 1B staircase | −0.78 | −0.37 [−0.64, −0.11] | −0.56 | +1.2 to +1.6 |
| 3A volume and liquidity | −1.51 | −1.54 | −2.21 | +2.6 to +3.8 |
| 4A streak and alerts | −0.61 | −0.60 | −1.02 | +0.4 to +1.4 |
| 4B cross-board and repeats | −1.35 | −1.77 | −1.59 | +0.4 to +1.8 |
| 6 chase, crowding, volume | −1.10 | −1.26 | −1.71 | +2.5 to +3.3 |
| 6c chase alone | identical to percentage change | | | |

Every signal has a positive `ΔNet`. That is not a win: each flags quieter
coins than percentage change does, so it catches fewer crashers by catching
less movement of any kind. No signal flags a group that runs more often than it
crashes. The closest is the reverse of acceleration on the 1-minute board, at
2.00% runners against 1.98% crashers, and its runner rate is less than the base
rate.

The check window agrees: every `ΔP` is at or below zero, and all but
acceleration on the 1-minute board are below zero on every one of the ten days
or nearly so.

## Two specific results

- **Acceleration on the 1-minute board matches percentage change and does not
  beat it.** +0.09 points, interval −0.07 to +0.24, better on 29 of 61 days;
  −0.02 in the check window. Codex's screen found acceleration ahead on all 16
  post-freeze days, using a different runner definition (top 5% of peaks). The
  two are compatible only if acceleration's edge is in the size of the peak and
  not in whether the gain holds.
- **Carbon's snapshot-timing concern does not occur in this data.** The chase
  measure is exactly zero in every row on every board: the board's displayed
  move equals the snapshot's move. Signal 6c is therefore identical to
  percentage change.

## What this means

- The stored snapshot carries no usable runner signal beyond percentage change.
  Snapshot-based badges such as "staircase" or "volume behind it" would not be
  telling users anything that holds up.
- Percentage change is a sound way to order the boards for "what is moving".
  Calling the top rows likely runners would mislead: they are likelier to crash.
- The open candidates all need one-minute candles: the move against the coin's
  own normal, real dollar volume, and the Bitcoin-relative move, plus the whole
  early-watch idea. Candles from 2026-09-06 to 2026-10-12 are already on disk,
  so step 2 can start on that window now.
- The +1% / +1.5% runner definition is strict for these boards. That should be
  reviewed before confirmation, and on exploration data only.

## Limits

- Ranking within a whole day uses that day's later entries, which the live board
  cannot.
- Signal 4B's simultaneity check looks up to 180 seconds after entry.
- Outcomes use last-trade prices; the bounce and stale-price issues Carbon
  identified apply.
- Boards were screened separately and not pooled. This is exploration; nothing
  here is a confirmed result.

## Provenance

Protocol `aa94299`, script and checks `7ebd794`. Full numbers, including every
daily value, are in
[RESULTS.json](results/radar_runner_signal_screen_20261113/RESULTS.json).
Captures were read only; their hashes are recorded there. Four synthetic checks
pass.
