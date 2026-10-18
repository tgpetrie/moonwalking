# Demoted reads and 4h/12h/24h outcomes

## Why

**Correction (2026-10-18).** An earlier version of this note said these two
reads did measurably *worse than a random entry*. That does not survive a
stricter control and has been withdrawn.

Compared with **matched same-coin controls** (each signal against other hours of
the same coin, same direction, similar volatility, same BTC 4h trend bucket,
1-7 days away so outcome windows never overlap; 24h, 1 ATR stop / 2 ATR target,
0.2% round trip; 62,468 matched signals, 93% of those tried; only 6 weeks):

**Evidence statement:** *we did not detect incremental predictive value over
matched same-coin baselines during the tested period.*

| Group | Matched / unmatched | Excess (net R) | 95% CI, calendar-week blocks | 95% CI, day blocks |
|---|---|---|---|---|
| QUIET FLOW BUILDING, up | 8,037 / 322 | -0.010 | [-0.265, +0.245] | [-0.176, +0.158] |
| QUIET FLOW BUILDING, down | 6,723 / 271 | +0.011 | [-0.178, +0.199] | [-0.157, +0.181] |
| MIXED - NO CLEAR EDGE, up | 4,675 / 277 | -0.080 | [-0.256, +0.095] | [-0.233, +0.065] |
| MIXED - NO CLEAR EDGE, down | 3,448 / 167 | +0.023 | [-0.071, +0.117] | [-0.133, +0.167] |
| **Both demoted reads, pooled** | 22,883 / 1,037 | **-0.013** | **[-0.067, +0.040]** | [-0.042, +0.014] |
| All signals, pooled | 62,468 / 4,920 | -0.036 | [-0.062, -0.010] | [-0.063, -0.009] |

Balance (signal vs matched controls): volatility gap -0.2% to -1.5% (log),
standardised difference about 0.00 to -0.02, median 38-49 controls per signal;
the BTC trend bucket is identical by construction. Unmatched signals are the
most volatile ones (median ATR 3.1% against 1.6%), so results describe the
matched 93%.

How to read the intervals (with a "useful advantage" taken as about +0.10 R per
signal before realistic costs):

* **Pooled demoted reads:** the upper end (+0.040 by week, +0.014 by day) is
  below +0.10, so a useful advantage is ruled out for them as a group.
* **Single label/direction cells:** the intervals are wide and span +0.10, so
  the data cannot decide those cells individually.
* **Only six calendar weeks**, so the week-block interval rests on six
  numbers and is imprecise. A longer history is needed before narrowing it.

The earlier "-0.09 to -0.32 R worse" came from comparing against all coins, and
only reflected which coins produce these reads. Across the board, no read
outperformed its matched controls, so this change is a **noise-reduction
choice**: demote the two reads that say the least, without claiming they are
worse than chance. Caveats: six weeks, a falling/choppy market, hourly candles,
the 7% of signals with no match are the most volatile, and the live-flow inputs
(order book, spot flow) cannot be replayed from candles.

## What changed

* `the_read.demoted` / `demotion_reason`, and `read_demoted` on the event, for
  the two labels above.
* A demoted read never notifies (not even for a coin you hold), sorts after
  every other event in the feed, and keeps being recorded and measured.
* The signal store records directional return at 4h, 12h and 24h, plus the
  best and worst excursion over 24h (`max_favorable_24h`, `max_adverse_24h`).
  The existing 1-hour grading, `complete` flag and every published statistic
  are untouched. A checkpoint is only recorded if read within the tolerance of
  its due time; a missed one stays NULL and is never filled late.

## Switches

| Variable | Default | Effect |
|---|---|---|
| `MW_DEMOTE_WEAK_READS` | on | `0` restores the previous behaviour. |
| `MW_EXTENDED_OUTCOMES` | on | `0` stops collecting 4h/12h/24h. |
| `MW_EXTENDED_CHECKPOINT_TOLERANCE_SECONDS` | 600 | How late a checkpoint may be read (minimum 60). |

## Reading the new data

Rows are final once `extended_complete = 1`. NULL means the checkpoint was
missed, not zero. Older rows from before this change stay NULL.

```sql
SELECT read_label, direction, COUNT(*) n,
       AVG(return_4h), AVG(return_12h), AVG(return_24h),
       AVG(max_favorable_24h), AVG(max_adverse_24h)
FROM signal_outcomes
WHERE extended_complete = 1 AND return_24h IS NOT NULL
GROUP BY 1, 2 ORDER BY n DESC;
```

`SignalOutcomeStore.extended_status()` reports how much has been collected.
Excursions are sampled about once a minute, so they are slightly conservative.

## Not done (UI)

The API exposes `read_demoted`; the frontend does not yet dim or collapse
demoted reads. That is left to the UI work in progress.
