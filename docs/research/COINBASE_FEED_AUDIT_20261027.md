# Coinbase side/coverage diagnostic - 2026-10-27

Step 2.5 of the [prospective contract](LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md)
is implemented in `scripts/coinbase_feed_audit.py`. It is a standalone public
market-data process and does not import the backend, use port 5003 or alter
any collector/database/ranking. The historical experiment stays frozen.

Run with an interpreter that has the existing `websocket-client` dependency:

```powershell
python scripts/coinbase_feed_audit.py capture --run-dir C:/Users/tgpet/.moonwalking/analysis/feed_audit_20261027 --seconds 3600
python scripts/coinbase_feed_audit.py analyze --run-dir C:/Users/tgpet/.moonwalking/analysis/feed_audit_20261027
```

The output directory must be new. Defaults freeze BTC-USD, SOL-USD, ALCX-USD
and AURORA-USD. These were online when checked; approximate last-price times
24h base volume was $521M, $42M, $23K and $61K respectively. This only justifies
the diagnostic's liquid/thin sample; it is not a universe-wide measurement.

Capture writes gzip JSONL for WS packets and separate, periodically paginated
REST responses, UTC/monotonic receipt times, subscription acknowledgment,
code commit/hash and dirty-code flag. `STATUS.json` updates during capture.
It makes one connection attempt and ends as failed if interrupted, so a
reconnect cannot masquerade as an uninterrupted hour. Final REST requests
retry briefly because the newest REST page can lag the feed.

On completion, `MANIFEST.json` hashes the raw files and capture metadata.
`REPORT.json` contains product-keyed ID overlap, count/volume coverage,
duplicates, reorder counts, raw-side cross-tabs, price/size mismatches,
heartbeat gaps and REST comparisons. Replay verifies hashes and recomputes
the report. No recovered trade is inserted into the received WS sample.

Coverage verdicts cover first-to-last heartbeat trade-ID watermarks, not
unobserved start/end slivers. Integer ID holes are candidate gaps and are
checked against REST. REST pagination is bounded at 20 pages/product/check;
unreconciled gaps remain incomplete. These REST requests are additional API
requests. There is no application queue; synchronous receipt/disk processing
does not itself guarantee upstream delivery.

A side verdict requires at least five identical-trade comparisons for each
maker side, unanimous same-side or opposite-side mapping, and no conflicting
duplicates or price/size discrepancies. Sparse or contradictory evidence is
inconclusive. The hour gate additionally requires >=3600s, a completed capture,
committed capture code, and a supported mapping plus reconciled coverage for
every sampled product. Extend evidence for thin products if necessary; do
not relax the gate after inspecting results.

Two short smoke captures exercised the real connection and reporting. The
second had 58 BTC and four SOL trade overlaps, one AURORA overlap and none
for ALCX. Its BTC cross-tab supported ticker taker-side semantics; other
products were inconclusive. All four coverage intervals reconciled. This
short, uncommitted-code smoke **does not pass the one-hour gate**.

Verification: seven synthetic audit tests and seven existing WS tests pass;
Black 24.8 formatting, repository guardrails and `git diff --check` pass.
Synthetic cases cover both mappings, product identity, ticker batching,
deduplication/reordering, missing matches despite REST recovery, payload
mismatch, heartbeat outage, short-run rejection, hash tamper and replay.

The full capture reports its own verdict automatically. A pending or failed
capture does not authorize micro-bar implementation or a visible sort change.
