# Demoted reads and 4h/12h/24h outcomes

## Why

**Correction (2026-10-18).** An earlier version of this note said these two
reads did measurably *worse than a random entry*. That does not survive a
stricter control and has been withdrawn.

Compared with **matched same-coin controls** (each signal against other hours of
the same coin, same direction, similar volatility, same BTC 4h trend bucket,
1-7 days away so outcome windows never overlap; 24h, 1 ATR stop / 2 ATR target,
0.2% round trip; 62,468 matched signals, 93% of those tried; only 6 weeks):

| Read | Net R excess over matched controls |
|---|---|
| QUIET FLOW BUILDING | up -0.010, down +0.011 (not significant) |
| MIXED - NO CLEAR EDGE | up -0.080, down +0.023 (not significant) |

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
