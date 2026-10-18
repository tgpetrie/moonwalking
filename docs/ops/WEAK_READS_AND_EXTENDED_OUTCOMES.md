# Demoted reads and 4h/12h/24h outcomes

## Why

**Correction (2026-10-18).** An earlier version of this note said these two
reads did measurably *worse than a random entry*. That does not survive a
stricter control and has been withdrawn.

Compared with **matched same-coin controls** (each signal against other hours of
the same coin, same direction, similar volatility, same BTC 4h trend bucket,
1-7 days away so outcome windows never overlap; 24h, 1 ATR stop / 2 ATR target,
0.2% round trip; 117,787 matched signals, 92% of those tried, over **13 calendar
weeks**, 2026-07-17 to 2026-10-11, using a year of hourly Coinbase candles):

**Evidence statement:** *we did not detect incremental predictive value over
matched same-coin baselines during the tested period.*

| Group | Matched / unmatched | Excess (net R) | 95% CI, calendar-week blocks | 95% CI, day blocks |
|---|---|---|---|---|
| QUIET FLOW BUILDING, up | 17,361 / 671 | -0.000 | [-0.101, +0.100] | [-0.112, +0.109] |
| QUIET FLOW BUILDING, down | 14,427 / 526 | -0.006 | [-0.092, +0.080] | [-0.103, +0.093] |
| MIXED - NO CLEAR EDGE, up | 9,070 / 525 | -0.043 | [-0.125, +0.039] | [-0.140, +0.060] |
| MIXED - NO CLEAR EDGE, down | 6,370 / 322 | +0.009 | [-0.049, +0.067] | [-0.094, +0.115] |
| **Both demoted reads, pooled** | 47,228 / 2,044 | **-0.009** | **[-0.039, +0.021]** | [-0.031, +0.015] |
| All signals, pooled | 117,787 / 9,858 | -0.031 | [-0.052, -0.010] | [-0.052, -0.008] |

Balance (signal vs matched controls): volatility gap -0.1% to -1.4% (log),
standardised difference about 0.00 to -0.02, median 40-55 controls per signal;
the BTC trend bucket is identical by construction. Unmatched signals are the
most volatile ones (median ATR 3.1% against 1.5%), so results describe the
matched 92%.

How to read the intervals (with a "useful advantage" taken as about +0.10 R per
signal before realistic costs):

* **Pooled demoted reads:** the upper end (+0.021 by week, +0.015 by day) is
  well below +0.10, so a useful advantage is ruled out for them as a group.
* **Single label/direction cells:** the upper ends are now about +0.04 to +0.10,
  so a +0.10 R advantage is essentially ruled out for each of them as well.
* **All signals pooled:** slightly *below* their matched controls (-0.031 R),
  and the interval excludes zero. High-confidence "up" signals are the weakest
  (-0.07 to -0.09 R).
* **Thirteen calendar weeks** in a falling/choppy period. This supersedes an
  earlier six-week version of this table.

The earlier "-0.09 to -0.32 R worse" came from comparing against all coins, and
only reflected which coins produce these reads. Across the board, no read
outperformed its matched controls, so this change is a **noise-reduction
choice**: demote the two reads that say the least, without claiming they are
worse than chance. Caveats: hourly candles, the 8% of signals with no match are
the most volatile, and the live-flow inputs (order book, spot flow) cannot be
replayed from candles.

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
