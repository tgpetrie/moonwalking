# Offline coverage monitor and next quote-source policy

October 30, 2026. Implementation specification; **not a frozen study or a live
feed certification**. This advances the blockers measured in the
[preserved replay](INSTANT_CAPTURE_REPLAY_RESULTS_20261030.md). It does not
reopen the locked historical comparison or evaluate F1-F5 outcomes.

## What is implemented

`scripts/scoring_experiment/instant_coverage.py` processes saved public
WebSocket envelopes, with no sockets, backend imports or account access.
The new [monitor contract](INSTANT_COVERAGE_CONTRACT_V1_DRAFT.json) is separate
from the existing recorder and target contracts.

- Subscription membership is acknowledged per product and connection.
  Disconnects, errors, queue-overflow markers and lost required subscriptions
  invalidate continuity. A new acknowledgement and heartbeat baseline are
  required before a fresh interval can pass.
- Consecutive heartbeat watermarks define an expected set of trade IDs.
  It must equal the unique live-match IDs received in the half-open receipt
  interval. Missing IDs, unexpected IDs, regressing watermarks, gaps above
  5 seconds and ID spans above 100,000 fail that interval. Boundary collisions
  are conservative failures, not reassigned executions.
- Identity is product plus trade ID, first receipt wins. Decimal amounts are
  compared exactly for duplicate conflicts. Later conflicting duplicates veto
  overlapping evidence only when the conflict is known. REST, `last_match`
  and ticker sizes cannot repair live receipt counts.
- Local logger sequence must be contiguous; receipt and monotonic clocks
  cannot regress. Missing monotonic metadata or invalid amounts fail the
  artifact closed. At most 100,000 packets and 32 declared products are
  accepted; a truncated prefix is never called a complete input.
- Evidence availability uses the measured **completion** of processing and
  at least receipt plus 1ms. A message received exactly at a cutoff is outside
  observations strictly before that cutoff. CLI replay uses the current clock,
  never the historical receipt time. The injectable clock is for testing and
  remains a trusted assertion, not authenticated historical evidence.

`assess(product, start, end, asof=...)` keeps `receipt_id_check_passed`,
`transport_observed_ok` and quote quality separate. A passing ID check is
conditional on the recorded heartbeat range and receipt attribution. It
does **not** establish exchange-event completeness before a lagging watermark,
independent REST agreement, upstream queue latency, durable consumer writes,
or unobserved book continuity. `full_feed_verified` and quote verification
remain false. Proofs are intentionally **not** a `ReplayStore.add_health`
drop-in. The legacy writer's omitted source tag is interpreted as WebSocket;
a reshaped recovery must retain an explicit non-WebSocket source. Shape and
hash metadata do not authenticate provenance.

The bounded CLI creates a new output directory outside the input directory,
hashes the unchanged input before/after and writes a report plus ID-check
records. Failures retain `FAILURE.json`; existing output is refused.

```sh
python scripts/scoring_experiment/instant_coverage.py ~/.moonwalking/analysis/feed_audit_campaign_20261028/attempt-01/websocket.jsonl.gz --products BTC-USD SOL-USD ALCX-USD AURORA-USD --out-dir ~/.moonwalking/analysis/coverage-check-new
```

The [paired-sample adapter](INSTANT_PAIRED_SAMPLE_CONTRACT_V1_DRAFT.json),
`scripts/scoring_experiment/instant_samples.py`, pairs the existing recorder's
coin and BTC snapshots at one cutoff. It exposes no later-asof override.
Both prices and coverage must qualify then. The immutable result contains a
target `Sample` or explicit missing reasons with `sample=None`. Genuine
verified empty windows stay zero. Quote receipt age, exact bucket-start trade
counts, input/producer provenance and separate signed-flow availability are
preserved. Unknown trade side does not turn otherwise valid target prices
and counts into an F2 observation. This adapter uses the recorder's existing
trusted health inputs; it neither strengthens them nor supports the new
book source yet. The target evaluator and V1/V2 JSON bytes stay unchanged.

## Quote-source choice for the next implementation

Use **Coinbase Exchange `level2_batch`**, initially alongside `ticker`,
`matches` and `heartbeat` on the same public feed profile. This is a declared
new source candidate, not a replacement for the old audit evidence. Keep all
four pilot products and the original thin-side gate.

Coinbase documents ticker batching on matches, possible drops from `matches`,
and heartbeat trade IDs for detecting gaps. Level 2 starts with a full book
snapshot, then sends absolute price-level sizes; zero deletes a level.
`level2_batch` uses the same schema in 50ms batches, without authentication.
Its timestamp refers to the latest event in the batch.
[Official channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels).
Coinbase also recommends batch channels and distributing heavy subscriptions
across connections. [Official feed practices](https://docs.cdp.coinbase.com/exchange/websocket-feed/best-practices).
The public Exchange endpoint is `wss://ws-feed.exchange.coinbase.com`.
[Official overview](https://docs.cdp.coinbase.com/exchange/websocket-feed/overview).

Our inference: book updates should improve observation opportunities for
thin products whose prices or sizes change between executions. This is a
testable source-quality hypothesis; the documentation does not promise a
fresh quote on every 5s cutoff or measure our consumer's performance.

The next book adapter must apply a whole batch atomically after a validated
snapshot, replace sizes rather than add them, delete zero levels, and expose
the best valid bid/ask and associated sizes. A reconnect, lost subscription,
invalid/crossed book, queue loss or processing failure requires an explicit
unavailable state and a new validated snapshot. Do not splice an old book
across connections or mix Exchange and Advanced Trade message schemas.

For the first source diagnostic, preserve the existing **10s maximum age from
the last actual book snapshot/update receipt**. A heartbeat must not refresh
the quote timestamp. Record book-change age, observation age, connection,
subscription state and processing/availability time separately. An unchanged
but continuously verified book could justify a different future policy only
through a versioned contract amendment, never a silently refreshed timestamp.
Batch observations are not a full intrabatch price path or continuous F3
availability. Keep missing sizes/quotes unavailable and never use last trade
price as a hidden fallback. Quiet books may still fail the initial TTL.

## Resolve publication timing before collecting study rows

There is a structural latency boundary: a heartbeat received after window end
can certify that earlier window only after receipt and processing. Emitting
health every 5 seconds cannot eliminate it. For example, a window ending at
10,000ms with its proving heartbeat at 10,050ms and processing complete at
10,060ms is unavailable for a 10,000ms decision, even if counts later match.

Best-practice direction for the next draft: use the latest certified feature
window available at the **actual publication time**, retain its window end
and age, enforce a declared maximum lag, and measure the forward outcome
from publication. This requires an explicit timing/target amendment before
use: current `Sample` and target contracts tie input and outcome anchors to
the same 5s cutoff. Do not put late verification into an earlier `Sample`,
shift a label backwards, drop the final unverified tail as if it were zero,
or silently change the target clock. Measure source/processing/proof lag in
the next data-only pilot before choosing a numerical lag limit. No limit
has been fitted or declared empirically validated here.

## Next bounded work

Implement and test the offline book adapter and explicit publication-timing
draft next. Then predeclare a bounded source/latency pilot and instrument
actual receipt, processing and durable-publication timestamps. This checkpoint
does not launch that pilot or modify the always-on collector. Allow at least
62 **complete** warmup minutes before eligible decisions, retain final outcome
maturity separately, and count at least 14 valid shadow days only after the
source/readiness and study rules are frozen. Raw elapsed time cannot replace
valid coverage. Feature formulas, stages, model/readiness and meaningful-effect
rules still require implementation/freeze. No fitting or live ranking change
follows from passing engineering checks.
