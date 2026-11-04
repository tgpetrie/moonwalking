# Claude independent review of the coverage monitor and paired samples — 2026-11-03

Reviewed implementation `4ed9045` (`codex/instant-radar-20261028`; code identical at tip `6c22952`): `instant_coverage.py`,
`instant_samples.py`, their two draft contracts, the policy document and `tests/test_instant_coverage.py`.
Branch `claude/instant-coverage-review`. Probes: `tests/test_instant_coverage_review.py`.

No fitting, new capture, live hook, outcome evaluation, or historical discovery/validation. The preserved one-hour capture
was replayed read-only to check real envelope shapes and to classify failed proofs. Trade IDs, receipt times and trade
counts were read; no price, return or label was analysed. Output stayed outside Git and the capture's folder.

**Verdict: sound as an offline, fail-closed ID check, with three small defects fixed here. It should not become target
coverage until D1 is decided.** On real data its strict rule produced only false vetoes, and those would remove most
labels. D1 is a contract decision, so I measured it and did not change it.

## D1 — highest priority: strict interval attribution vetoes real coverage (design decision, measured)

`_ingest` requires each heartbeat pair's expected ID set to equal the IDs received in that half-open receipt interval. A
heartbeat that overtakes its match on the wire fails two adjacent intervals, although nothing was lost.

Replay of `feed_audit_campaign_20261028/attempt-01/websocket.jsonl.gz` (63,258 packets, input hash `4b4a56ec…`):

| Product | Proofs | Failed | Expected IDs | Never received | 5s buckets vetoed |
|---|---:|---:|---:|---:|---:|
| BTC-USD | 3,599 | 29 | 21,770 | **0** | 16 / 719 (2.2%) |
| SOL-USD | 3,599 | 4 | 2,641 | **0** | 2 / 719 (0.3%) |
| ALCX-USD | 3,599 | 0 | 4 | 0 | 0 |
| AURORA-USD | 3,599 | 0 | 3 | 0 | 0 |

All 33 failures are false alarms: 15 runs of adjacent failures (13 BTC, 2 SOL), each reconciling exactly once merged.

**Why 2.2% matters.** BTC is the benchmark for every coin (`paired_sample` needs both), and `TargetEvaluator._quality`
needs every grid point from anchor to horizon. So one BTC veto removes every label whose window touches it. If these
proofs became `Sample` coverage, the anchors left clean of trade-ID vetoes would be:

| Anchors with no veto in window | 5m | 15m |
|---|---:|---:|
| BTC, ALCX, AURORA (strict) | 41.4% (273/659) | **3.0%** (16/539) |
| SOL (strict) | 37.2% (245/659) | 3.0% (16/539) |
| All products, merged reconciliation (below) | 100% | 100% |

**It is also selective.** Vetoed BTC buckets had a median of 91 trades against 22 for clean buckets (n=16). Labels would be
lost mainly around active BTC tape, which is when a move radar most needs them. That is missing-not-at-random, not noise.

Limits: this is one hour, descriptive, and counterfactual, because the monitor is not wired into `Sample` today. These
shares count trade-ID vetoes only; quote freshness, warmup and proof latency remove further rows.

**Status update: adopted by the user and implemented on `claude/instant-coverage-reconciliation`** as coverage
contract amendment 1 (limits: 4 proofs, 10,000ms, 100,000 IDs). Correction to the cap remark below: merging the smallest
closing run splits the run of 4 into two pairs, so the largest merge actually needed on this hour is 3 proofs.

**Recommended amendment.** Allow a bounded reconciliation of adjacent failed proofs on one connection:
* The merged span must satisfy the same exact rule: expected IDs in `(low, high]` equal the unique IDs received in it.
* Merge only `missing_live_match_ids` and `receipt_ids_outside_watermarks`, never a heartbeat gap, regression, ID-span or
  conflict failure. A truly lost ID still fails.
* Bucket counts stay attributed by first receipt, so a race does not move any trade.
* Availability becomes the later heartbeat's processing time, so nothing is backdated.
* Predeclare the cap. The longest run observed is 4 proofs (two consecutive races); a cap of 3 would leave that one vetoed.
  Set the cap before the next pilot, from engineering reasoning rather than from any outcome.

The alternative of keeping the strict rule means accepting the table above, and should be chosen knowingly.

## Reproduced defects (fixed; each failed on unmodified `4ed9045`)

**C1 — medium. The real recorder's failure markers were ignored** (`CoverageMonitor._ingest`).
`scripts/coinbase_feed_audit.py` writes `audit_transport_error` and `audit_parse_error`. The monitor handled only
`connection_closed`, `error` and `queue_overflow`, and these markers carry no `product_id`, so they fell through silently.
* Reproduction: `simple()`, then `audit_transport_error` at 2100, then `assess(1000, 2000, asof=2101)`.
* Expected: `transport_observed_ok=False`, and no pair straddling the marker. Actual: `True`, and the pair straddled it.
* Fix: treat `audit_*` as failure markers, the same rule `coinbase_feed_audit.py:130` already uses. Completed proofs are
  not rewritten. **Consequence for the recorder:** a new acknowledgement is required afterwards, so a live connection
  that merely logged a parse error stays unproven until it resubscribes or reconnects. A lost book frame makes this
  essential for the coming `level2_batch` adapter.
* Probes: `test_real_recorder_failure_markers_invalidate_transport`, `test_real_recorder_failure_markers_require_a_new_ack_and_baseline`.

**C2 — low likelihood, but a false pass. `assess` joined proofs by timestamp alone** (`CoverageMonitor.assess`).
Two sessions touching at one millisecond joined into continuous coverage, hiding executions between their watermarks.
* Reproduction: `hb(1000,10)`, `trade(1200,11)`, `hb(1500,11)`, then connection 2: `ack(1500)`, `hb(1500,20)`, `hb(2000,20)`.
* Expected: `[1000,2000)` not proven, since trades 12–20 were never seen. Actual: `receipt_id_check_passed=True`.
* Fix: joined spans must share `connection_id`, and each lower watermark must equal the previous upper. Same-connection
  coverage is unaffected, and each session's own interval still passes.
* Probes: `test_proofs_join_only_when_connection_and_watermark_continue`, `test_contiguous_heartbeats_on_one_connection_still_join`.

**C3 — low. An old-session receipt could satisfy a new session's check** (`CoverageMonitor._ingest`).
The contract says `same_connection`, but IDs were selected by receipt time only, so a trade received on connection 1 at the
new baseline's millisecond counted for connection 2.
* Fix: retain each trade's connection and select only the proof's own. Conservative: a redelivery on the new connection
  is a duplicate, so that interval fails rather than passes.
* Probe: `test_old_session_receipt_cannot_satisfy_new_session_id_check`.

**Real-data effect of the fixes:** none. All 14,396 real proofs are identical apart from processing time. The edits change
`implementation_sha256`; nothing is frozen against it.

## Open items for the publication-timing amendment and next adapter

* **D2 — late negative evidence and labels.** `paired_sample` is pinned to `asof=cutoff`. That is right for inputs. But a
  failure discovered later leaves `Sample.coverage_verified=True`, including on rows used as the forward *outcome* path,
  even though label maturity comes after the discovery (`test_late_negative_evidence_cannot_change_the_decision_time_sample`).
  Decide whether grading may veto on evidence known by maturity. I recommend yes: inputs stay cutoff-only, labels become
  `unavailable`. Today's design cannot do this because the sample discards that evidence.
* **D3 — "known by the cutoff" covers health, not rows.** The monitor measures processing completion. `ReplayStore` stores
  no processing time for quotes or trades, so a row received 1ms before the cutoff but processed after it still counts
  (`test_sample_availability_reflects_health_not_row_processing`). The policy says the adapter does not strengthen trust, but
  the contract's `both_coin_and_benchmark_known_by_the_same_cutoff` reads stronger. The next recorder needs per-row availability.
* **D4 — packet bound versus the book channel (estimate, not measured).** `MAX_PACKETS` is 100,000 and the capture without
  a book already used 63,258 in an hour. One product's 50ms batches can add up to 72,000 an hour, so the one-hour pilot
  could fail closed by exceeding the bound. `quote_channel="level2_batch"` is accepted today, so raise the bound or define
  rotation before the pilot.
* **D5 — connection identity depends on the recorder.** `coinbase_feed_audit.py:55` hard-codes `connection_id: 1`. Today's
  runs are single-connection and write a close marker, so this is safe, but connection-change protection is inert until the
  recorder assigns real IDs.
* **D6 — one connection at a time.** Every change of `connection_id` resets all state. The policy cites Coinbase's advice to
  distribute heavy subscriptions across connections; interleaved connections would never pass. The current one-profile
  plan is fine; a split needs per-connection state.

## Confirmed correct

| Area | Evidence |
|---|---|
| Never backdates | The real CLI run reported `first_proof_available_ts_ms` at today's clock, not the capture's. A same-ms receipt is excluded, and availability uses completion (existing tests pass). |
| ID-set rule | Bounds plus an exact count mean a verified proof is set equality. Duplicates, REST and `last_match` cannot repair it (read and existing probes). Across the real capture, the only failures were the races above. |
| Real envelope shape | The CLI completes on the preserved capture: 63,258 packets, 24,424 unique matches (matching the replay report), maximum heartbeat gap 1,223ms, source hash unchanged. |
| Fail-closed artifact | Bad sequence, clock, amount or missing metadata fails the artifact; truncated and empty inputs are refused (existing tests pass). |
| Quote non-claim | `full_feed_verified` and `quote_coverage_verified` stay False; proofs are not an `add_health` drop-in by shape. |
| `paired_sample` | Grid and as-of checks are enforced by `snapshot`; no later as-of path exists; unavailable rows stay `sample=None`; both legs and the quote-crossing check are required. `input_available_after_cutoff` is defensive and unreachable through `ReplayStore`, since `asof=cutoff` filters later evidence. |

## Tests run (Windows, Python 3.12, project `.venv`)

* The documented targeted list plus `tests/test_instant_coverage.py` and the new probes: **414 passed** (Codex's 405 plus 9 probes).
* The 5 probe cases for C1–C3 failed on unmodified `4ed9045` before the fixes.
* `bash scripts/validate_mw_guardrails.sh`: all guardrails passed.
* Not run: `black` is not installed here, so formatting is unchecked. Frozen historical hashes were not recomputed; no
  historical artifact was touched. Not a full-suite claim. No live feed, REST reconciliation or second capture was exercised.
