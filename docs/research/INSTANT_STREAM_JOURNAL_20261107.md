# Streaming input journal and local publication receipts

`StreamJournal` is the bounded offline-testable recording boundary for
the instant-radar pilot. It uses one writer thread and one active
transport per segment. An adapter calls `open_connection` once for each
new socket, `receive` for each frame, and `end_connection` at shutdown or
loss. Each connection gets a unique segment-and-open ID. A closed or
failed connection cannot submit later frames under its old ID.

The journal stamps wall and monotonic receipt clocks at the callback
boundary. It processes the canonical WebSocket envelope through the
timed input ledger, then commits the envelope, packet processing clocks
and first-receipt trade evidence together. The caller receives the
separately measured time of the commit return. Frame decode failures,
transport errors and reported queue losses create explicit barriers.
Malformed frames retain a hash and byte count. A write error stops the
writer. The last committed prefix remains independently readable.

## Storage and restart

Use a fresh local SQLite file per segment. The writer requires rollback
journaling in DELETE mode with EXTRA synchronization. Creation is exclusive.
The bounds are at most 100,000 packets, 1 MiB per incoming frame, and
256 MiB of logical record payload per segment. Lifecycle records also
count toward the packet cap. A smaller packet or record limit can be
supplied. The payload limit excludes SQLite page and journal overhead.
The recorder retains the existing bounded in-memory evidence state.

`finish` marks an explicit end after the final connection closes.
`read_segment`, `iter_packets` and `read_local_publication` recover committed
records. The readers verify record digests and packet sequence. A file
still marked recording is an unfinished prefix. Open a fresh segment after
a stop or restart. Each new segment has independent connection IDs and
warmup evidence. There is no proof chain across segment boundaries.
Recovered processing fields are observations from the original writer.
Any new replay of the envelopes measures its own processing.

## Local publication receipts

`append_publication` verifies the frozen decision's inventory, recorder
source and packet prefix. It commits the decision and publication ID
before reading the local commit clock, then persists that observation
in a second transaction. Repeating the same ID and decision returns
the original receipt. Reusing the ID for a different decision fails.
If the process exits between commits, the entry is recoverable with
an absent commit observation. It remains unacknowledged.

The receipt describes local database persistence. External delivery needs
a separate observed publication time. The draft accepts incomplete
diagnostic snapshots to preserve their missingness. Local receipt,
publication delivery and grading remain distinct.

## Pilot preparation

Socket ownership and callback wiring come next. The synchronous recording
path has no application queue. The pilot must measure callback lag,
transport backlog, processing, storage latency and capacity on the
intended host. The bounds are engineering limits and the observed
callback time may follow arrival at the socket. The prototype uses
synthetic input and a real subprocess exit for crash recovery. Host
power-loss behavior and end-to-end feed coverage require separate evidence.

See the [check record](results/instant_stream_journal_20261107/CHECKS.json).
