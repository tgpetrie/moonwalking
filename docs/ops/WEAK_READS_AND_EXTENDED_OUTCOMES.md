# Demoted reads and 4h/12h/24h outcomes

## Why

Over 369,611 production signals followed for about 24 hours
(2026-09-05 to 2026-10-11, hourly Coinbase candles, 1 ATR stop / 2 ATR target,
net of a 0.2% round trip), compared with 187,206 unconditional entries on the
same coins:

| Read | Net R vs a random entry, same direction |
|---|---|
| QUIET FLOW BUILDING | up -0.20 R, down -0.09 R |
| MIXED - NO CLEAR EDGE | up -0.23 R, down -0.32 R |

Together they were about 35% of de-duplicated signals. No read had a positive
net expectancy, so this is about removing the clearly worse ones, not about
finding a winner. Caveats: five weeks in a falling/choppy market, hourly
candles, and z-scores that overstate certainty because coins move together.

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
