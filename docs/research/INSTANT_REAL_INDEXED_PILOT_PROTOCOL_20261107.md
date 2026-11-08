# Indexed real-data latency and readiness pilot

Run one data-only attempt on the Windows research host. Use the same
public Coinbase Exchange endpoint, four products and subscriptions
as the [original source pilot](INSTANT_SOURCE_PILOT_PROTOCOL_20261107.md).
Use the indexed journal with the declared warmup profile. Keep the
10-second book age rule and the full 30-second book-span check.

## Capture and stopping

Start the 67-minute deadline when all subscriptions are acknowledged.
Use one connection, the 249,990-packet and 240 MiB logical soft limits,
and the journal's 1 MiB frame limit. The socket reader timestamps
returned frames before enqueue. The writer commits them in FIFO order.
Use a 128-frame bounded queue. Overflow or an oversized frame ends the
segment with a loss marker. Capacity, timeout or transport errors end
this attempt. Keep the committed prefix and report frames received
and delivered to the writer. Coverage probes end at the last committed
reader receipt. The reader-to-writer timing describes the application
queue. It excludes time before the socket reader returns a frame.

Collect a read-only five-sample host clock check against
`time.windows.com` near startup and again after capture. Preserve the
signed output with both timestamps. Exchange timestamp comparisons
remain raw signed wall-clock differences. Local elapsed durations use
the high-resolution host counter.

## Diagnostic cohorts and delivery observation

The first cutoff is the next 5s grid point at or after acknowledgment
plus 62 minutes. Sample ten consecutive 5s cutoffs. Begin each cohort
once the writer has committed a frame and the clock has reached
cutoff +5s. Freeze the evidence as-of at exactly cutoff +5s for the
eight product/direction snapshots. Use all four products even when
some features or baselines are unavailable. A late proof beyond
that as-of leaves its dependent fields unavailable. The fixed probe
offset is for measurement.

Write each diagnostic to the local outbox. A separate process opens
the journal read-only and polls every 25 ms for acknowledged rows.
It verifies the digest and records its first actual read time and
the decision identity. Report missing or invalid observations.
Cutoff-to-read includes the fixed probe wait, queue handling,
preparation, commit, and reader polling. The delivery observation
is for a separate local consumer. Public publication, market
outcomes, fitting and production changes are outside this pilot.

Report queue wait, frame callback and commit timing, coverage at cutoff
and cutoff +5s on the same 30s probe grid, per-feature readiness,
full cohort time, local outbox commit, and observed reader lag. Preserve
early capacity stops and missing probes. The original feed-audit
gate remains a separate requirement.
