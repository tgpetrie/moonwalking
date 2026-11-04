# Offline association and exposure reporting draft — 2026-11-03

Implemented by a Claude Code cloud session on branch
`claude/instant-association-cloud-20261103`, based on Codex tip `1d394e4`
(book/publication `8c51878`, integrated monitor review `652f5af`). This is the
[cloud assignment](../ai/CLAUDE_CLOUD_ASSIGNMENT_20261103.md). **Pending Codex
review; not merged.** It is a standalone offline reporting module with a
versioned draft contract. It changes no target label, recorder, monitor,
sample, book or publication code, no existing contract, no frozen artifact
and no live service. Fitting, operational rates and physical onset stay off.

Code: `scripts/scoring_experiment/instant_association.py`. Contract:
[`INSTANT_ASSOCIATION_CONTRACT_V1_DRAFT.json`](INSTANT_ASSOCIATION_CONTRACT_V1_DRAFT.json).
Tests: `tests/test_instant_association.py`. Record:
[`results/instant_association_20261103/CHECKS.json`](results/instant_association_20261103/CHECKS.json).

## Primary pointwise outcomes stay fixed

`association_report(labels, alerts, asof_ts_ms=...)` takes complete v2 labels
(`instant-target-v2-draft`, one contract hash and one evaluator hash) and alert
records with `publication_id`, `product_id`, `direction`, `anchor_ts_ms`,
`inputs_available_ts_ms` and `published_ts_ms`. For each alert and **each
horizon separately** it looks up `verified_forward` at the alert's declared
decision-cutoff anchor:

| Label at (product, direction, horizon, anchor) | Primary outcome |
|---|---|
| `ready`, `verified_forward` True | `success` |
| `ready`, `verified_forward` False | `failure` |
| `pending`, `unavailable` or absent | `ungradable`, reason retained, outside both denominators |

`success_rate_among_graded` divides by success plus failure only;
`graded_fraction` shows how much of the alert set that covers. A ready label
whose outcome is not a boolean, an incomplete label carrying an outcome, a
ready label maturing after the as-of, a v1 label, mixed provenance, duplicate
identities, off-grid anchors and malformed rows are rejected. Nothing missing
is coerced to false.

Alerts carry no horizon: every alert is graded in both tables because the
study evaluates 300s and 900s outcomes separately. `publication_id` is the
retained identity and must be unique.

## Forward-window coverage diagnostic

Windows are the deduplicated verified forward windows from
`instant_diagnostics.forward_catalog_report`, so left-censor flags come from
the existing reporting layer unchanged. Per product, direction and horizon,
windows are sorted by anchor and each receives the earliest unused alert with
actual publication in `[anchor - 180s, forward_peak]`, ordering alerts by
`published_ts_ms` and then `publication_id`. One alert covers at most one
window per horizon; the same alert may cover a 5m window and a 15m window.
Unmatched windows and alerts are listed. Rates are named
`uncovered_forward_window_rate` and `conditional_catalog_coverage_rate`;
`physical_missed_move_rate` is always null and `association_kind` is
`forward_window_not_physical_impulse`.

The report counts `failed_alerts_that_cover_a_forward_window` and states
`association_alters_primary_outcomes: false`. Three evaluator-graded tests
make this executable: a 5m alert whose move begins at +340s and a 15m alert
whose move begins at +940s both cover the later catalog window and both remain
pointwise failures; an alert published at a completed window's endpoint,
where the forward peak equals maturity, covers that window and is still a
failure at its own anchor.

**Known property for review.** Earliest-unused assignment is the declared
rule from the freeze candidate, implemented literally. It is not a maximum
matching: when a window's lead edge overlaps the previous window's tail, the
greedy choice can leave a later window uncovered although a different pairing
would cover both. The rule is transparent and deterministic; changing it is a
contract amendment, not a tuning step.

## Exposure from explicit eligibility records

`exposure_report(labels, eligibility, asof_ts_ms=..., ranker_slots=None)` takes
one record per product and 5s cutoff with four explicit booleans:
`universe_member`, `warmup_complete`, `health_verified`, `candidate_eligible`.
A slot is **decision-eligible** when all four hold. Exclusions are counted by
the first failing flag in that order. Duplicate or overlapping slots, missing
or non-boolean flags, off-grid cutoffs and cutoffs after the as-of are rejected.

- `decision_eligible_product_hours` sums eligible slots across products.
  `board_wall_clock_hours_with_any_eligible_product` counts the union of
  cutoffs with at least one eligible product; it is never the sum. A separate
  union counts cutoffs with any verified health.
- `universe_size_by_cutoff` lists the universe size at every cutoff, with
  first, last, minimum and maximum, so a shrinking universe stays visible.
- Per horizon, an eligible slot is **retrospectively gradable** only if its
  trailing horizon matured by the as-of and both direction labels are
  `ready`. Immature, missing and incomplete cases are counted by reason.
  The decision-eligible counts never depend on labels, so missing future
  data cannot erase the decision universe.
- `comparison` distinguishes identical complete rows (eligible, gradable and
  scored by every supplied ranker) from each ranker's natural coverage of
  eligible and of gradable slots. Ranker slots must be recorded slots.

Eligibility flags are caller assertions. This module does not verify
health, warmup or universe membership itself; the monitor, book adapter and
future recorder supply that evidence under their own contracts.

## Clocks and timing

Each alert retains its input anchor, input availability and actual
publication separately, with derived `input_lag_ms`, `publication_delay_ms`
and `inputs_known_at_anchor`. Records must satisfy anchor <= inputs available
<= published <= as-of; a violation is rejected, so no late feature is accepted
as known at an earlier anchor. The primary outcome is graded at the declared
decision-cutoff anchor, as the current V1/V2 contracts require. A
publication-anchored target remains a separate amendment; this module does
not shift any label.

## Verification

Linux cloud container, Python 3.13.18, pytest 8.3.5, Black 24.8.0. Not the
pinned Python 3.12 environment and not a native Mac pass.

```bash
python -m pytest -o addopts= -q --tb=short tests/test_instant_association.py tests/test_instant_book.py tests/test_instant_coverage.py tests/test_instant_coverage_review.py tests/test_preserved_feed_replay.py tests/test_micro_replay_review.py tests/test_micro_replay.py tests/test_instant_diagnostics.py tests/test_instant_targets.py tests/test_instant_targets_v2.py tests/test_instant_targets_v2_review.py tests/test_feed_audit_campaign.py tests/test_coinbase_feed_audit.py tests/test_live_contract.py tests/test_live_movers_run.py tests/test_live_movers_review.py tests/test_restore_macbook_evidence.py backend/tests/test_coinbase_ws.py
python -m black --check scripts/scoring_experiment/instant_association.py tests/test_instant_association.py
bash scripts/validate_mw_guardrails.sh
```

- **518 targeted checks pass**: Codex's recorded 468 plus 50 new association
  and exposure cases. The new cases cover both directions and horizons, a
  hand-calculated matching oracle, zero and empty denominators, absent,
  pending and unavailable labels, shrinking universes, timestamp and ID ties,
  one-to-one matching across horizons, censored windows, the +340s and +940s
  delayed moves, the completed-endpoint publication, late input retention,
  rejected non-causal clocks and provenance, a hand-calculated exposure
  oracle with rankers, decision-universe independence from labels, immature
  trailing horizons and input immutability.
- Black 24.8.0 and repository guardrails pass. All 11 frozen historical
  artifact hashes match.
- `instant_targets.py`, `instant_diagnostics.py`, both target contracts, the
  diagnostic contract, monitor, samples, book, publication, recorder and
  baseline builder are byte-identical to Codex's `1d394e4` record.

Not done: the full test folder, the unrelated seed-fixture failure, any
capture, replay, real-data run, fit, historical rerun or live change. The
synthetic checks establish definitions, not market performance, and this
module cannot approve the study or manufacture readiness.

## Handoff

Authoritative resume branch: `codex/instant-radar-20261028`
([resume page](../ai/RESUME_HERE.md)). This contribution is pending Codex
verification and integration; it should be reviewed alongside local Claude's
separate bounded reconciliation branch, which this work does not touch.
Decisions for Codex and the user: whether gradability should require both
direction labels or be reported per direction; whether to keep the literal
greedy rule; and how eligibility records will be produced from the monitor,
book and future recorder before any pilot.
