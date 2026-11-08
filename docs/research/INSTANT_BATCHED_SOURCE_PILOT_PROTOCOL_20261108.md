# Batched real-source coverage and latency follow-up

Run one isolated, read-only market-data attempt on the Windows research host.
Use the public Coinbase Exchange socket, BTC-USD, SOL-USD, ALCX-USD and
AURORA-USD, and the same level2_batch, matches, heartbeat and ticker
subscriptions as the original indexed pilot. Use the pre-acknowledgment
book staging amendment. Keep the 10-second quote age and full 30-second
book-span checks.

Select the explicit `batched-256` profile. One socket reader keeps a
256-frame queue and stamps frames before enqueue. The journal takes up to
16 frames that are already queued and preserves FIFO order. It durably
commits input before processing and invokes the diagnostic only after
committing the audit rows. Keep DELETE mode and synchronous EXTRA.
The historical `single-128` profile remains the command default.

## Capture limits

Use one connection, 67 minutes after the writer confirms all
subscriptions, a 249,990-packet soft stop, a 240 MiB logical byte
soft stop and a 1 MiB raw frame limit. The soft byte budget is checked
after each group, subject to the journal's hard 256 MiB record limit.
End the attempt at overflow, transport failure, a budget or the deadline.
Preserve committed records, any recovered pending ingress and the exact
stop reason. Report frames returned by the socket reader and frames
delivered to the writer separately. Coverage probes end at the last
accounted committed reader receipt.

Run a read-only five-sample clock check against time.windows.com before
and after capture. Record its exit status and signed differences.
Use raw signed comparisons for exchange and local wall-clock stamps.
Use the performance counter for local queue and commit durations.
Persist the code commit and selected bounds in the plan before opening
the socket. Keep the prior stopped attempt as separate evidence.

## Cohorts and interpretation

The first of ten consecutive 5s cutoffs is the first grid point at or
after the original acknowledgment receipt plus 62 minutes. At each
cutoff +5s, use the fixed as-of to prepare eight product/direction
diagnostics when the next committed group permits it. Keep unavailable
quotes, baseline inputs and features visible in the report.

The same separate local process polls the SQLite outbox every 25 ms
and records its actual read time for each digest-verified entry.
Report queue wait, receipt-to-audit-commit, cohort preparation,
local outbox commit, observed delivery and missing observations.
Report the 30s quote/trade/book probes at cutoff and cutoff +5s by
product, plus actual warmup and cohort counts.

The repeat addresses the two earlier startup and queue blockers.
Interpret all metrics within this single attempt and record partial
results if a stop prevents warmup. This run measures local research
readiness. The original feed audit and the prospective study freeze
remain separate gates for outcome collection and fitting.

- [Previous stopped attempt](INSTANT_REAL_INDEXED_PILOT_RESULTS_20261107.md)
- [Synthetic writer comparison](INSTANT_BATCHED_JOURNAL_RESULTS_20261108.md)
