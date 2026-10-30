# Instant offline diagnostics, replay and baselines — 2026-10-30

This checkpoint implements the next step from the consolidated study draft.
It is an **offline prototype**, not a running feed, frozen study or ranking
change. The existing target evaluator/contracts remain unchanged at `92fb51d`.
No raw market capture, historical experiment or scoring-model fit ran here.

## Versioned diagnostics

[`instant_diagnostics.py`](../../scripts/scoring_experiment/instant_diagnostics.py)
implements the separate
[diagnostic contract](INSTANT_DIAGNOSTIC_CONTRACT_V1_DRAFT.json).
`alert_report(evaluator, label, publication, strict_trigger=False)` validates
the existing v2 timing call and preserves its fields. Added report fields:

- `pre_window_consumed_fraction_reason`: source quality reason, invalid or
  nonpositive peak reason, or null when the original fraction is available.
- `pre_window_to_forward_peak_consumed_fraction`, its named peak timestamp
  and its own reason: reference remains anchor minus 30s, but this separate
  denominator uses the forward peak. Negative/>1 values are not clamped.
- `whole_window_peak_precedes_anchor`: explains why the existing strict
  timing can be late even with a low consumed fraction.
- Diagnostic version/contract/source hashes alongside the target hashes.

`forward_catalog_report(labels)` retains the target catalog's selection and
adds `previous_anchor_status`, `left_censored` and a reason. A missing or
unavailable previous grid anchor cannot establish that the selected anchor
is the first possible event. Full labels, including failures/unavailable rows,
must be supplied; a positive-only list is correctly flagged as censored.
Duplicate anchors are refused. These remain forward-window diagnostics,
not a physical-event denominator.

The newer remote Claude branch
`claude/instant-radar-onset-review-20261030` (`b281f97`, `4610bf2`) proposes a
similar gap annotation in the target module. Its committed diff was inspected;
it was not merged or represented as a newly completed independent review.
Here the annotation lives in the separate versioned reporting layer, preserving
the previously reviewed target outputs and evaluator hash.

## Sparse replay recorder

[`micro_replay.py`](../../scripts/scoring_experiment/micro_replay.py) implements
the [offline replay contract](INSTANT_OFFLINE_REPLAY_CONTRACT_V1_DRAFT.json).
It accepts local receipt-ordered JSONL/JSONL.gz envelopes in the existing feed
audit shape. No sockets, REST calls, backend imports, live stores or account
credentials are used. Create a new output only:

```sh
python scripts/scoring_experiment/micro_replay.py packets.jsonl.gz --health health.json --out offline-replay.sqlite
```

Every envelope retains receipt time/sequence, optional monotonic time,
connection identity and the raw public message including its exchange time.
Price/size validation and receipt/clock regressions fail the artifact closed.
Only complete sealed artifacts are queried; reopen uses SQLite read-only mode.
Input hashes are checked before/after replay and saved with contract/code
hashes. Existing output files are refused.

SQLite stores raw packets, quote observations, unique trades, explicit health
assertions, conflicts, and a sparse `micro_bars_5s` **occupied-bucket index**.
Bar values are derived from the normalized details, not dense carried writes.
This is not a disk-budgeted production aggregation/indexing design yet.

- Unique live `match` messages supply counts and USD volume, keyed by product
  and trade ID across connections. Match maker side is inverted for taker
  amounts. Unknown-side USD stays visible and makes signed flow unavailable.
- Duplicates add no execution. Conflicting duplicates invalidate affected
  intervals only once that contradiction is known. Trade-ID/exchange-time
  reordering does not move receipts to earlier buckets.
- `last_match`, ticker `last_size`, heartbeat and separately tagged
  `rest`/`rest_recovery` messages add no live executions. Source tags must be
  explicit and recognized. Late recovery remains raw evidence, not an earlier
  or recovery-time pace contribution.
- Receipt buckets are `[start,end)`; a receipt at `end` belongs to the next
  bucket. Queries expose the exact count at the bucket start for the existing
  target's boundary-exclusion rule. Quotes at `cutoff` are also excluded from
  that closed snapshot.
- Within explicitly verified coverage, a logical absent bucket has zero
  trades and may retain a valid <=10s-old quote with its original observation
  time. There is no invented observed OHLC. Stale/crossed/invalid/missing
  quotes or an intervening coverage gap produce an unavailable midpoint.
- Missing BBO sizes remain unavailable for size-pressure features even when
  the midpoint is valid. Quote age uses receipt observation time; exchange
  timestamps remain raw evidence. Transport backlog/exchange-clock quality
  must be established by the external health auditor, not assumed here.

Health is an explicit JSON list, for example this **synthetic schema example**:

```json
[{"product":"TEST-USD","start":100000,"end":110000,"available":110000,"verified":true,"evidence":"synthetic test assertion"}]
```

Real intervals need independently reviewed product/subscription and quote/match
coverage evidence; the store does not certify an assertion merely because it
has a nonempty evidence string. Completed intervals cannot be claimed known
before their end. Negative assertions veto overlaps. An absent/unverified
interval yields unknown counts, never zero.

`snapshot(product, cutoff)` uses only knowledge available at that cutoff.
Explicit `asof=later_time` permits retrospective coverage audit and reports
the later `available_ts_ms`. It never alters the result of the original as-of
query or makes that late audit valid for an earlier live feature. Replaying
the completed one-hour audit alone cannot establish contemporaneous coverage
that was never recorded by a live monitor. The feed gate stays false.

## Causal baseline builder

[`micro_baseline.py`](../../scripts/scoring_experiment/micro_baseline.py)
provides `build_baseline(store, product, anchor, benchmark="BTC-USD")`:

- Sigma ends at `floor((anchor-35000)/60000)*60000`. Sixty log returns come
  from 61 already-received minute-boundary midpoint closes for coin and BTC.
  Sigma is the sample standard deviation (ddof 1); the target applies its
  existing floor. This is receipt-time midpoint history, not invented trade
  candles or a read from the historical candle archive.
- Beta is centered OLS on the same 60 paired returns. A completely observed
  flat BTC denominator gives beta 1 with `beta_fallback=True`; missing BTC
  history stays unavailable. No scoring-model weights are trained.
- Pace is the median count and USD volume over 120 completed nonoverlapping
  30s receipt windows ending at `anchor-30000`. Genuine zero baselines stay
  zero and will fail the existing onset pace rule, rather than gaining epsilon.
- Coverage must span the entire history, including between minute endpoints.
  Missing/stale endpoints and future-only health evidence fail closed. All
  inputs and coverage must be known by the anchor; late knowledge is not
  backdated to historical snapshots. Returned `Baseline` availability is the
  current anchor, with exact windows and builder/contract hashes recorded.

## Verification and remaining work

The targeted suite covers diagnostics, wick/reference separation, gap
censoring, unknown versus zero, receipt boundaries, duplicates, reordered
trades, unknown sides, late recovery, clocks, invalid/stale/carried quotes,
as-of audits, read-only/non-overwrite behavior, baseline counts/cutoffs,
future evidence and beta fallback. It also runs the existing target/feed/
historical-contract/driver/restore/WS checks. **346 targeted checks pass**,
including 30 new cases. See the
[verification record](results/instant_offline_pipeline_20261030/CHECKS.json).

Still required: independent review of these new prototype contracts,
continuous health/subscription/reconciliation monitoring, an adapter that
builds paired immutable target samples, bounded real-data replay/throughput
and disk sizing, F1-F5 feature implementation, stages/model/readiness freeze,
the unchanged feed gate and 14 valid shadow days with fresh validation once.
No market-performance, adequate-power, native Mac execution or full-suite
pass is established by these synthetic checks. The unrelated existing
seed-fixture failure remains documented in the previous acceptance report.
