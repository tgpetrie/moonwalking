# Indexed decision latency results

The indexed recorder completed the full 67-minute synthetic stream on
one connection, committing **241,208 packets and 80 local diagnostic
outbox records**. The capture path took 2,334.309 seconds of host time.
The journal occupied 206,057,472 bytes. SQLite integrity, every packet
digest and sequence, and all 80 outbox acknowledgments were verified.

| Operation | Samples | Median | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Indexed decision preparation during capture | 80 | 62.668 ms | 89.160 ms | 99.850 ms |
| Local outbox write and acknowledgment | 80 | 14.771 ms | 16.246 ms | 16.826 ms |
| Full serial cohort, eight preparations and local receipts | 10 | 619.181 ms | 681.971 ms | 681.971 ms |
| Batch decision preparation after capture | 16 | 2,505.282 ms | 2,666.977 ms | 2,666.977 ms |

The first and last cohorts supplied 16 exact comparisons. Feature and
anchor-quote content matched, including missingness, input availability
and the canonical known-packet prefix digest. The two paths computed at
different times. The batch reference ran after capture against the same
evidence as-of and a longer retained tape.

The writer read its next frame after each full serial cohort. The cohort
time measures how long the writer spent on that step in this run.
Synthetic receipts were released on demand, so real
socket backlog and external delivery latency are still open. Each
synthetic decision used cutoff +5s as its evidence probe. That offset
does not establish a decision age budget. Thin-product stale windows
remain explicit in the source evidence.

Next, predeclare a real-data latency and readiness protocol that
explicitly opts into the indexed writer and separates receipt lag,
evidence wait, cohort processing, and observed external publication.
Check host clock offset near that run and retain all four products in
coverage reporting.

The raw synthetic journal is on the Windows research host under
`%USERPROFILE%\.moonwalking\analysis\instant_indexed_latency_20261107\run-01`.

- [Declared workload and comparison](INSTANT_INDEXED_LATENCY_20261107.md)
- [Run manifest](results/instant_indexed_latency_20261107/RUN_01.json)
- [Verification](results/instant_indexed_latency_20261107/CHECKS.json)
