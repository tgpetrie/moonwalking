# Predeclared instant-radar source and latency pilot

One real-data attempt on the Windows research host will test the socket,
bounded journal, and evidence availability. The existing comparison and
feed-audit verdict remain pinned. The pilot produces source diagnostics
and measures timing without grading outcomes or fitting a ranker.

## Source and stop rules

Use one unauthenticated Coinbase Exchange Market Data WebSocket with
`level2_batch`, `matches`, `heartbeat`, and `ticker` for BTC-USD, SOL-USD,
ALCX-USD, and AURORA-USD. Book observations and matches supply their
separate ledger paths. Ticker supports source comparison by paired trade ID.
The four products stay in every denominator. This attempt does not run
REST reconciliation, and its scoped receipt-ID evidence cannot certify
full-feed completeness or change the earlier gate.

Start the 67-minute monotonic deadline at the first acknowledgment of
all four subscriptions for every product. The initial handshake gets a
5-second socket timeout. While connected, use a 2-second read timeout,
a 20-second limit for acknowledgment, and a 15-second idle stop. Allow
one reconnect following an established connection's transport error,
idle stop or remote close. Reconnects get fresh identities and the same
deadline. Keep the first attempt's failure records. Stop at 99,990
committed packets or 240 MiB of logical records, preserving headroom for
the closing marker under the journal's hard limits. A source or journal
error can stop the run sooner. Capacity exhaustion is a pilot result.
Keep the original bounds and all products for this attempt.

## Readout

For every product report packet counts by message type, paired match/ticker
side counts, first-receipt matches, strict proof failures, and bounded
reconciliations. Use each 30-second UTC grid point whose trailing 30 seconds
start after the first acknowledgment and whose later as-of elapsed by the
stop. Report point-quote, trade-window and full sampled-book-window
readiness at both the cutoff and cutoff plus 5 seconds. Include missing
reasons, quote ages and available proof delay. The 5-second view is a
diagnostic. A later study budget requires real latency measurements and
a separately declared selection rule.

Report p50, p95, p99, maximum and count for callback through local commit,
receipt through payload completion, payload completion through observed
commit, and exchange timestamp through callback where provided. Keep
negative counts. The last timing includes source timestamp semantics,
transport, buffering and wall-clock differences. It does not isolate
network transit. The level2_batch timestamp refers to the last event
in the batch. This pilot measures local recording latency separately
from publication delivery.

The first planned probe after 62 elapsed minutes also reports timed
baseline and feature readiness and post-capture calculation latency,
if reached. Actual warmup requires the full verified input windows.
Only readiness and timing are reported. Keep the raw SQLite journal
locally with its SHA-256 and push the aggregate report and handoff.
Socket and queue faults, journal failure, early capacity stop, and
short warmup are part of the result.

Source documentation is available in the [Exchange overview](https://docs.cdp.coinbase.com/exchange/websocket-feed/overview)
and [channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels).

## Startup correction

Attempt 01 preserved the exchange's `level2_50` acknowledgment and stopped
at the startup timeout, before the diagnostic clock started. Coinbase
documents `level2_50` as the legacy alias for `level2_batch`. Attempt 02
accepts that acknowledgment in both the monitor and the pilot. The raw
message retains the original spelling. The four products, subscriptions,
limits, proof rules and diagnostic readout remain the same. Keep both
attempts in the report.
