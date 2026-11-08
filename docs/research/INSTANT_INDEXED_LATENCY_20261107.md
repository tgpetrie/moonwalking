# Indexed feature and decision latency draft

The recorder can opt into append-only evidence indexes. Point quote
queries use receipt and availability bounds. Trade queries use indexed
product windows, preserving the same receipt-ID, merge, continuity and
late-conflict checks. Book pressure retains the last known carry-in
state and all known observations through the window. The incremental
SHA-256 state keeps checkpoints every 128 packets and reproduces
earlier evidence prefixes. Verified 30s activity-bin sums are reused
across overlapping baselines. The whole requested activity window is
rechecked before using its arithmetic cache. A bounded cache invalidates
if Decimal arithmetic settings change.

The indexed path shares the formulas and record shapes with the batch
path. Its journal manifest records the index implementation. The
ordinary batch path remains the oracle for delayed evidence, barriers,
older as-of queries and comparison of complete diagnostic decisions.

## Declared latency run

Use the same 67-minute synthetic socket workload and the full-warmup
journal profile. Keep SQLite commit and synchronization settings for
the entire run. At ten consecutive 5s cutoffs beginning at minute 62,
prepare a diagnostic cohort on the writer thread after the first
committed frame at or beyond cutoff +5s. That offset is a probe rule.
Each cohort prepares eight decision snapshots, two directions for
each of four products, and records each in the local diagnostic outbox.

Use the high-resolution host duration clock for decision preparation,
outbox write and acknowledgment, and full serial cohort time. Record
frame callback durations separately. The synthetic receipt clock does
not advance during computation. Serial cohort time is the amount of
host time spent before the writer reads its next frame. The accelerated
socket supplies frames on demand, so the run cannot measure network
backlog or actual exchange-to-publication age.

After the capture, use the batch path on the same ledger to verify the
first and last cohort. Compare all feature and anchor-quote content,
including evidence hashes, missingness and evidence availability.
Actual calculation completion clocks are compared separately from
content. Report both timings, the number of parity cases and the
committed packet and publication counts. The post-capture batch path
also scans the trailing portion of the ledger, so its time is a
reference measurement for the same evidence rather than a live
same-thread benchmark.

Run from the research checkout with
`python scripts/scoring_experiment/instant_indexed_latency.py --out-dir <new-directory>`.
A real source and decision latency diagnostic requires a separately
predeclared protocol and contemporaneous clock validation.
