# Real indexed latency pilot results

The November 7, 2026 run acknowledged all four products at 10:34:43 PM
Pacific. The last committed reader receipt arrived at 10:55:18 PM.
The run stopped at the 128-frame reader queue limit **20 minutes 35.553
seconds** after acknowledgment, before the 62-minute warmup cutoff.
The reader received 45,955 frames and delivered 45,826. The journal
preserved those frames plus its open and queue-loss markers, for
**45,828 committed records**. The 129 received but undelivered frames
are outside coverage. The ten post-warmup cohorts and local delivery
measurements were unreached.

## Measured prefix

| Product | Fresh cutoff quotes | Full fresh book windows | Trade windows ready at cutoff | Trade windows ready by +5s | p95 proof lag |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC | 39 / 40 | 40 / 40 | 0 / 40 | 40 / 40 | 204 ms |
| SOL | 40 / 40 | 40 / 40 | 0 / 40 | 40 / 40 | 199 ms |
| ALCX | 0 / 40 | 0 / 40 | 0 / 40 | 40 / 40 | 188 ms |
| AURORA | 34 / 40 | 21 / 40 | 0 / 40 | 40 / 40 | 185 ms |

Each product had 1,230 verified strict heartbeat intervals in the
committed prefix. The trade-window check covers the sampled recorded
intervals. Full feed certification requires the separate audit evidence.

For book updates, measured reader-to-writer p95 was 16.1 ms for BTC,
21.4 ms for SOL, 33.9 ms for ALCX, and 21.6 ms for AURORA. The maximum
was 570.2 ms across these groups. Writer-through-commit p95 for book
updates ranged from 8.8 to 14.7 ms, with a maximum of 458.0 ms. This
measures application queue and writer time after frames returned from
the socket reader.

The ending loss marker was recorded 109 ms after the last committed
reader timestamp. Twelve committed data frames shared a 16 ms receipt
span at the tail. The discarded frames have counts without individual
timings, so the journal locates the overflow at the application queue
and leaves its upstream cause unresolved.

## Startup ordering and clock evidence

The ALCX snapshot was committed at sequence 2. The subscription
acknowledgment followed at sequence 3 in the same millisecond. The book
replay only accepts snapshots after acknowledged membership. ALCX sent
no additional snapshot in this segment, leaving it at `awaiting_snapshot`
for all 40 probes. That is a startup ordering failure for this attempt.
AURORA's 19 missing full windows were attributed to stale book spans.

Five read-only startup clock samples reported +891 to +904 ms against
the time source. Five post-run samples reported +920 to +931 ms. The
ending probe began at 11:03:30 PM, about eight minutes after the stop.
Exchange timestamps remain raw signed cross-clock differences. Local
queue and writer durations use the host performance counter.

Next, verify causal handling of snapshots that precede acknowledgment
and build a burst test from the observed arrival pattern before
choosing the next writer and queue policy.

The raw journal is saved on the Windows host under
`%USERPROFILE%\.moonwalking\analysis\instant_real_indexed_pilot_20261107\attempt-01`.
Its SHA-256, all packet digests and sequence, and SQLite quick check
passed. The run and its loss marker are preserved.

- [Declared protocol](INSTANT_REAL_INDEXED_PILOT_PROTOCOL_20261107.md)
- [Aggregate report](results/instant_real_indexed_pilot_20261107/ATTEMPT_01.json)
- [Startup clock check](results/instant_real_indexed_pilot_20261107/CLOCK_BEFORE.txt)
- [Ending clock check](results/instant_real_indexed_pilot_20261107/CLOCK_AFTER.txt)
- [Verification](results/instant_real_indexed_pilot_20261107/CHECKS.json)
