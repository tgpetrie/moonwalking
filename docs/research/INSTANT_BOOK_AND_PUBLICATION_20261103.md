# Offline book state and publication-clock draft

November 3, 2026 (Pacific). This implements the next bounded step from the
[October 30 policy](INSTANT_COVERAGE_AND_QUOTE_POLICY_20261030.md).
The existing target evaluator, V1/V2 target JSON, recorder, baseline builder
and locked historical comparison remain unchanged. New code is offline only.

## Book adapter

`scripts/scoring_experiment/instant_book.py` implements `BookReplay` under
[a separate versioned contract](INSTANT_BOOK_CONTRACT_V1_DRAFT.json). It
consumes the existing receipt envelope, using the monitor for bounded packet,
clock, subscription and connection checks. It performs no network access.

The official Exchange channel specification defines a complete initial
snapshot, then absolute price-level sizes, with zero deleting a level.
`level2_batch` uses that schema in 50ms batches, with its exchange time referring
to the latest event in the batch.
[Coinbase channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels).
Our implementation uses receipt order and preserves exchange time as metadata.
It does not assume contiguous exchange sequence numbers for selected channels.

- Acknowledged `level2_batch`, `matches` and `heartbeat` memberships are required
  for each declared product. A valid book starts from a fresh snapshot.
- Decimal prices/sizes retain their exact level identity. Amounts must be
  finite, nonnegative and representable for downstream floating readers;
  prices and resting snapshot sizes must be positive. Duplicate snapshot
  prices, empty sides, and final locked/crossed books are unavailable.
- Update batches apply atomically. Absolute sizes replace prior quantities;
  zero deletes; repeated changes at a price use the final change. Temporary
  intrabatch crossings do not create synthetic intermediate quotes or peaks.
- An invalid batch discards book continuity until a new valid snapshot.
  Connection/subscription loss, queue/transport/audit failures require a fresh
  acknowledgement and snapshot. A heartbeat gap above 5s requires a snapshot.
  Stale heartbeat and stale quote are separately reported.
- Last actual book observation, whole-book change and BBO change times remain
  distinct. A real deep-level or no-op update is an observation; only an actual
  level/BBO change moves the corresponding change clock. Heartbeats and ticker
  packets never refresh the book observation. The original 10s observation TTL
  remains in force, with exactly 10s allowed.
- Processing completion is measured after book construction. Read-only frozen
  results retain that availability time and source/contract/monitor hashes.
  Queries filter receipt strictly before cutoff and knowledge at or before
  the requested as-of. Explicit later diagnostics do not rewrite earlier as-of
  views. A later failure becomes visible only when known.

`view(product, cutoff, asof=...)` describes the last **fully processed** state
then known. An in-flight/queued update is not certified by an older visible
quote. `full_feed_verified` and `target_sample_adapter_supported` stay false.
This is not a queue-durability certificate, a continuous F3 integral, a full
intrabatch path, or a bridge that silently substitutes books into legacy
`ReplayStore`/`Sample`. Historical replay uses today's processing clock;
the injected clock in synthetic tests is not authenticated historical evidence.

At most 100,000 levels per product are allowed. Packet/product limits inherit
the monitor's 100,000 packets/32 products. This is a bounded offline prototype,
not a claim that a multi-product one-hour book capture fits those limits.
Version and test streaming persistence/rotation, real connection identities,
queue-loss reporting and processing/durable-publication evidence before a
source pilot. Do not raise a cap merely to make an old sample pass.

## Publication timing

`scripts/scoring_experiment/instant_publication.py` creates immutable clock
diagnostics under the [publication contract](INSTANT_PUBLICATION_CONTRACT_V1_DRAFT.json).
It requires:

```text
feature_cutoff <= inputs_available <= decision_completed <= published
feature_cutoff lies on the existing 5s grid
```

The first inequality concerns all completed-window inputs and coverage, not
the timestamp of one old quote. Publication ID and product identity are
explicit. A window ending at 10,000ms, verified at 10,060ms, computed at
10,080ms and published at 10,100ms has 60ms verification lag, 100ms feature age
and 20ms decision-to-publication delay. It cannot be an input known at 10,000ms.

Legacy V1/V2 targets retain the decision cutoff as their anchor. A proposed
future publication-anchored target must use actual publication for its entry
reference and forward horizon, with an explicit policy for off-grid entry
prices and label maturity. Do not round entry backwards, silently shorten a
horizon, or relabel a cutoff outcome as publication performance. The new
module flags that an amendment is required; it implements no new outcome.

No numerical feature-age limit has been selected. A supplied diagnostic limit
can show an exact age comparison, but never enables fitting. That limit and
off-grid entry/price-availability rules must be predeclared and frozen after
the data-only source/latency diagnostic, before outcome inspection. Caller
timestamps remain trusted assertions; the function cannot prove a durable
publication or independently validate source completeness.

Keep immutable decision inputs separate from later grading knowledge.
Subsequent negative feed evidence must remain available to a future grading
policy; it must not rewrite what the decision knew. The current legacy sample
does not carry that later evidence, so this remains an explicit amendment
requirement rather than a silent target change.

## Checks, ownership and next work

54 new synthetic cases cover hand-calculated BBO/pressure, absolute quantities,
atomic multi-change batches, malformed amounts/books, stale observations,
clock boundaries/completion, reconnect and subscription/audit failures,
unavailable states, immutable history, and publication chronology/age bounds.
No real `level2_batch` data or empirical improvement is claimed.

The existing Gemini/Claude target and offline reviews remain accepted. Claude's
new monitor/sample review at `91f3043` is now independently reproduced and
accepted as `652f5af`; read the
[acceptance and remaining amendments](INSTANT_COVERAGE_REVIEW_ACCEPTANCE_20261103.md).
The combined targeted suite passes 468 tests, including 54 new book/timing
cases and nine independent review probes. Reconciliation and later-grading
amendments still require explicit contracts. The held original `d711832`
remains unmerged; opt-in V2 already contains its adapted policy.

The [cloud association/exposure assignment](../ai/CLAUDE_CLOUD_ASSIGNMENT_20261103.md)
is dispatched by the user; its screenshot shows Fable 5.1 reading the required
sources. Implementation/push is pending. It owns new association/exposure
code on its own branch. Codex owns book/timing here. Do not mark the study frozen until its
executable rules, review and remaining source/model/readiness gates are done.

Next: declare/verify bounded reordering reconciliation and later-grading
evidence, then instrument/validate the
streaming source and publication path before a predeclared pilot. Preserve
the four-product gate, >=62 complete warmup minutes, final label maturity,
14 valid shadow days, no physical-onset inference and locked historical
validation. Fitting, new captures and production integration stay off.
