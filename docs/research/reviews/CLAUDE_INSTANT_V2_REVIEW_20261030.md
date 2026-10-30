# Claude independent review of instant-target v2 draft — 2026-10-30

Reviewed implementation `8b5b266` (`codex/instant-radar-20261028`; `scripts/` and `tests/` byte-identical at tip `5e02268`).
Branch `claude/instant-radar-v2-review`. Synthetic probes only: no fitting, no historical discovery/validation, no live,
recorder or deployment change. Probes: `tests/test_instant_targets_v2_review.py`.

**Verdict: v2 targets are ready for protocol freeze, subject to the study decisions below.** One low-severity reproduced
defect was found and fixed. No defect was found in the labels themselves. The remaining blockers are study definitions and
the gates already listed in the contract, not code errors.

## Reproduced defect (fixed here)

**R1 — low. `forward_event_catalog` accepted v1 labels** (`instant_targets.py:forward_event_catalog`).
`forward_alert_timing` refuses v1 labels, but the forward catalog accepted them and stamped
`catalog_kind="forward_window_not_physical_impulse"`, a v2-only semantic, onto v1 rows without an `evaluator_sha256`.
* Reproduction: v1 `TargetEvaluator(samples with trade_count=3).evaluate(...)` → `verified_forward=True`;
  `forward_event_catalog([label])` returned one entry; `forward_alert_timing` raised.
* Expected: refuse, like the timing API. Actual: accepted.
* Fix: 3 lines; `forward_event_catalog` requires `contract_version == "instant-target-v2-draft"`. The generic
  `event_catalog` and all v1 behaviour are unchanged. Regression: `test_forward_catalog_refuses_v1_labels_like_forward_timing_does`.
* Effect: the edit changes `evaluator_sha256`, so any labels generated at `8b5b266` must be regenerated. None are frozen.

## Confirmed correct (with independent evidence)

| Area | Evidence |
|---|---|
| v1 valid-label behaviour unchanged | `test_v1_outputs_identical_to_pre_v2_reference`: the current code under the pinned v1 contract gives **dict-identical** `evaluate` output to the pre-v2 implementation `cb7034a`. Coverage: 40 random paths × up/down × 300/900 s, plus `alert_timing` at four publication times for every verified onset. |
| v2 delta is only the cutoff and named additions | `test_v2_differs_from_v1_only_by_cutoff_and_added_keys`: removing the nine named v2 keys gives v2 output equal to v1 output on the same rows (40 paths × directions × horizons). No other field changed. |
| Baseline cutoff (adaptation of `d711832`) | Same rule as `d711832` (`floor((anchor-35s)/60s)*60s`), applied only when `is_v2`, and it matches the contract's `sigma_end_rule`. `test_v2_rejects_the_v1_cutoff_when_they_differ`: at offsets 0, 5, 30, 34 s past the minute, v2 rejects the v1 end as misaligned; at 35, 36 and 55 s the two ends coincide. |
| Pre-window vs post-anchor peaks | Log additivity holds: `residual(ref,ts) = residual(ref,anchor) + residual(anchor,ts)`, so the pre-window peak equals the forward peak (same timestamp, values within 1e-12) unless an earlier point is higher. 60 random paths × both directions. |
| Peak search including earlier wicks | A wick inside `[anchor-30s, anchor)` becomes `pre_window_peak_ts_ms` (< anchor); `peak_ts_ms` stays ≥ anchor. Both are correct per contract; see S1. |
| Both directions | `test_up_and_down_labels_mirror`: residual paths built with opposite signs give identical status, flags, peak/breakout timestamps and residual values (within 1e-9) for up and down. 30 paths. |
| Maturity | `asof = end-1` → `pending`; `asof = end` → `ready`. The pre-window reference never extends maturity. |
| Missingness never False | A gap at `anchor-35s` keeps the forward label and the pre-window reference `ready`, but sets onset `unavailable` and `verified_onset=None`. A `last_trade` price source inside the pre-window gives `pre_window_reference_status=unavailable/price_fallback`, onset `unavailable`, and the forward label `ready`. |
| Backward publication lookup | Publications at grid+0 and grid+4999 ms both use the grid point at or before them, never the next one. Quote age is measured from the publication: 6.0 s passes; 10.999 s is `stale_alert_quote`. |
| Mixed-provenance rejection | v1 and v2 labels mixed in one catalog are rejected (contract hash). A v2 label with its `evaluator_sha256` removed, mixed with a genuine one, is rejected (evaluator set). Forged labels are rejected by both timing APIs (existing test). |

## Unresolved study definitions (decide before freeze; not code defects)

**S1 — earlier wick inside the activity window makes strict "early" unattainable.**
`_v2_alert_timing` requires `publish_ts_ms <= pre_window_peak_ts_ms`. If the highest point is a wick in
`[anchor-30s, anchor)`, every post-trigger publication is `late_after_activity_trigger`, even when
`pre_window_consumed_fraction` is below 0.5.
* Reproduction: `test_earlier_wick_makes_every_strict_publication_late`. A one-point 4.5% wick at `anchor-10s`, then a +2%
  forward leg with no retrace, is a verified strict onset. At the anchor the fraction is about 0.09 but the timing is
  `late`, with a negative `lead_to_pre_window_peak_seconds`.
* The code conforms to the contract (`pre_window_peak_search: reference..anchor+H`). Decide one of:
  (a) keep it: a consumed wick counts as already priced;
  (b) use the post-anchor peak for the "before peak" clause and the pre-window peak only for the fraction;
  (c) require a quote-validated, multi-point extreme.
  A one-grid-point wick is also exposed to quote noise.

**S2 — asymmetric exclusion windows.** The sigma baseline ends before `anchor-35s`, but the pace baseline ends at
`anchor-30s` (`pace_end_ts_ms == anchor - velocity_ms`). So the previous velocity window's first 5 s can still inform
pace. That is causal and not leakage, but decide whether the two should share a cutoff. Recorder provenance for the
120-window pace builder is still unverified (as the triage already notes).

**S3 — non-positive pre-window peak has no reason code.** For a forward-only label whose path from `anchor-30s` never rises
above it, `pre_window_consumed_fraction` is `None` with no reason. Strict timing cannot reach this case, because a
verified onset implies a positive run-up. Decide whether `None` should carry a reason
(e.g. `non_positive_pre_window_peak`) in the forward API's output.

**S4 — still open from the contract.** Physical-origin policy, event association/exposure denominators, the exact F1–F5
formulas, live-stage thresholds, readiness minima and the feed gate. Full fidelity to the original proposal still needs the
unamended original.

## Optional suggestions

* Record `contract_version` in the catalog outputs, and check for a single `product_id` per `evaluator_sha256` group if
  catalogs ever pool evaluators from mixed sources.
* `label` fields used by the timing APIs (`beta`, `pre_window_*`) are trusted after the hash check. Recomputing them from
  rows would remove reliance on an unmodified label dict.

## Tests run (Windows, project `.venv`, Python 3.12)

* `pytest tests/test_instant_targets.py tests/test_instant_targets_v2.py tests/test_instant_targets_v2_review.py`:
  **265 passed** (44 existing v1/v2 tests plus 221 probe cases).
* `pytest tests`: 309 passed, 1 failed. `tests/test_seed_fixture.py::test_load_dev_volume_fixture` fails identically on
  unmodified `8b5b266`; it is unrelated to the instant targets and was left untouched.
* `bash scripts/validate_mw_guardrails.sh`: all guardrails passed.
* Not run: `black` is not installed in either environment on this PC, so formatting of the two changed files is unchecked.
  Frozen historical hashes were not recomputed; no historical artifact was touched.
