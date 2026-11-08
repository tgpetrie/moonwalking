# Startup book recovery and queue burst diagnostic

The saved November 7 run observed an ALCX snapshot before the
subscription acknowledgment. It also stopped with 129 received frames
outside the committed prefix after reaching a 128-frame queue limit.

## Startup amendment

On a new connection whose first journal event is an explicit open
marker, stage at most one bounded book per product. Use the existing
snapshot and atomic delta validation. Process staged updates in receipt
order. Invalid book data discards that product's staged book until a
fresh snapshot. The first subscription response either activates the
staged book for confirmed products or discards it. Loss or a connection
change clears the staging area. Repeated acknowledgments and same-ID
recovery use the existing recovery path.

Visibility starts at the acknowledgment's receipt and processing
completion. Observation and change ages retain the actual staged
receipts. A post-acknowledgment heartbeat is required for a valid quote
view. The change is recorded in the book draft contract amendment.

## Burst protocol

Use the real indexed SQLite writer and queued socket with a synthetic
source. Send the four observed-depth synthetic snapshots and the
subscription acknowledgment, placing ALCX's snapshot first. After
startup commits, send 160 frames over a target 100 ms, followed by
40 frames over one second. Use the fixed book, heartbeat and trade
mix from the capacity fixture. The burst shape is a stress workload
motivated by the saved tail counts. Discarded live frames have no
individual receipt times in the archive.

Run three repetitions at each queue size, 128 and 256, with no
injected pause and with a 450 ms writer pause at burst onset. The
pause is motivated by the largest live callback-through-commit times.
It is a separate stress factor. Keep the normal one-transaction-per-frame
writer and its durability settings.

Record the observed returned burst span, queue high-water reading,
delivered and committed counts, loss or close marker, and queue wait.
Verify the original frame order and SQLite integrity for each
journal. A larger queue in this experiment measures burst tolerance
and added wait. The live entry point still uses the original cap;
a later live protocol needs a separate queue and writer decision.

Run with
`python scripts/scoring_experiment/instant_queue_burst.py --out-dir <new-directory>`.
