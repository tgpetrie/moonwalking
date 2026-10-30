# Claude independent review of the offline instant pipeline — 2026-10-30

Reviewed implementation `8211262` (`codex/instant-radar-20261028`); prompt `docs/ai/INSTANT_OFFLINE_REVIEW_PROMPT_20261030.md`.
Branch `claude/instant-offline-review`. Synthetic probes only (`tests/test_micro_replay_review.py`): no capture, collector
connection, fitting, historical rerun, feed-gate change or live change. The accepted target code was not re-reviewed.

**Verdict:** the offline replay, baseline builder and diagnostics behave as their draft contracts state, with one
low-severity recorder defect, which is fixed here. The baseline matches an independent numpy computation. No probe made a
later quote, recovery, conflict or coverage verdict alter an earlier feature.

## Reproduced defect (fixed)

**D1 — low. A monotonic-clock regression passed when the packet in between had no monotonic time**
(`micro_replay.py: ReplayStore._ingest`).
* Reproduction: packets carrying `receipt_monotonic_ns` 100 s, then none, then 50 s, with increasing receipt times.
  The third packet was accepted.
* Expected: abort and mark the artifact `failed`, like any other clock regression. Actual: it was accepted, because the
  check compared only with the immediately previous packet's `mono`, which was null.
* Fix: compare with the last packet that carried a monotonic time. Regression:
  `test_monotonic_regression_across_a_packet_without_monotonic_time_fails_closed`.
* Real feed-audit envelopes always carry `receipt_monotonic_ns`, so captured data is unlikely to hit this. The fix changes
  `recorder_sha256`; no replay artifact is frozen.

## Examined, not a defect

**Untagged `source` defaults to `ws`.** The pipeline doc says source tags "must be explicit and recognized", but
`coinbase_feed_audit.envelope()` writes no `source` field. The default is therefore required to read real WebSocket
captures. REST trades live in a separate file in a different shape (no `type`), so they cannot become executions even when
untagged. Unknown tags fail closed. Only a REST row re-wrapped as a WebSocket `match` message would be at risk.
**Action: correct the doc wording**, not the code. Pinned by
`test_untagged_source_defaults_to_ws_but_rest_shaped_trades_still_never_count`.

## Verified behaviour

| Area | Evidence |
|---|---|
| Baseline: 61 closes, 60 returns, sample SD | Constructed 2-hour history (anchor 120 min + 15 s): `sigma_end` 7,140,000, `pace_end` 7,185,000, 60 returns. `sigma_1m == np.std(returns, ddof=1)` (rel 1e-9). |
| Beta and fallback | `beta == np.polyfit(btc, coin, 1)[0]` (rel 1e-9). Flat BTC → beta 1 with `beta_fallback=True`. Missing BTC history → `unavailable/baseline_coverage` for `BTC-USD`, never a fallback. |
| 120 non-overlapping pace windows | Medians of trade count and USD equal numpy medians of the constructed per-window values. A trade received exactly at `pace_end` is excluded (half-open windows). All availability fields equal the anchor. |
| Later knowledge cannot reach back | A conflicting duplicate known at 113 s, a negative health audit known at 120 s and a quote received after the cutoff all leave the cutoff-105 s snapshot byte-identical. Explicit later `asof` queries do see the conflict and the audit. A span known only after the query's as-of does not verify it. |
| Receipt boundaries and boundary count | Read and covered by the existing suite: `[start, end)` receipts, `trade_count_at_window_start` = receipts exactly at the start, matching the target's bucket-start exclusion. |
| Dedup, sides, exclusions | First receipt wins across connections; a conflicting duplicate adds an issue known at its own receipt. Maker side is inverted for taker amounts. Unknown-side USD is retained and makes signed flow unavailable. `last_match`, heartbeats and REST/recovery add no executions. |
| Quotes and sparse zero vs outage | Original quote receipt time kept; > 10 s stale, invalid, missing or crossing an unverified interval → unavailable midpoint. Verified empty buckets read as zero; unverified → `None`, never zero. |
| Read-only and non-overwrite | `create` uses exclusive open (existing paths refused). Reopen is SQLite read-only. Only `complete` artifacts are queryable. Failed or sealed artifacts cannot be written. |
| Diagnostics do not alter labels | `alert_report` builds a new dict from the unchanged timing result and never writes into `label`. The whole-window and forward-peak fractions carry separate names and reasons. `forward_catalog_report` keeps catalog selection and only annotates left-censoring. |

## Study and integration items (not code defects)

1. **Live coverage needs completed spans per cutoff.** Health spans count only once `available >= end`. So a snapshot at
   cutoff `c` is verified only by spans that end at or before `c` and are known by `c`. A live health monitor must emit
   completed spans at least every 5 s bucket, or every live snapshot reads `unverified_coverage`. The adapter and monitor
   contract should state this explicitly.
2. **Health assertions are trusted inputs.** The store checks shape and known-at times, not truth. Independent
   subscription and reconciliation evidence is still required (as the doc says). The feed gate stays false.
3. **The recorder hash is recorded but not checked on reopen.** `meta.recorder_sha256` is written but never compared on
   read-only open, and the baseline provenance records only the replay contract hash. Optional: record the recorder hash
   in `build_baseline` provenance so a replay built by older code is visible.
4. **Diagnostic reason precedence (optional).** When both the pre-window reference and the publication are unavailable,
   `alert_report` reports the pre-window reason (`whole_reason or timing reason`). The publication's own reason (for
   example `stale_alert_quote`) is then only in the timing fields. Consider reporting both.

## Tests run (Windows, project `.venv`, Python 3.12)

* Specified suites plus the target compatibility suites: `pytest tests/test_micro_replay_review.py tests/test_micro_replay.py
  tests/test_instant_diagnostics.py tests/test_instant_targets.py tests/test_instant_targets_v2.py
  tests/test_instant_targets_v2_review.py` gives **302 passed**.
* Before the fix, the new monotonic probe failed (`DID NOT RAISE`).
* `pytest tests`: 346 passed, 1 failed. The failure is the pre-existing, unrelated
  `test_seed_fixture.py::test_load_dev_volume_fixture`.
* `bash scripts/validate_mw_guardrails.sh`: all guardrails passed. `black` is not installed on this PC, so formatting is
  unchecked.
