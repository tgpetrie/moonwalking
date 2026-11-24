# Direction-specific exposure reporting draft

November 4, 2026 (Pacific). This opt-in reporting addition follows the
accepted cloud association work and corrected reconciliation checkpoint
`3c859ef`. It resolves the report's directional-denominator choice; the
evidence-producing eligibility adapter and overall study remain unfinished.
Claude's independent review `583a73a` is accepted as **`4925ac5`** with no
defect found and no code patch. **1,163 targeted tests pass**, including 51
new independent probes. Read
[the acceptance](INSTANT_DIRECTIONAL_REVIEW_ACCEPTANCE_20261104.md).

Implementation **`9da4987`** passes **1,112 targeted tests**, including 48
new directional cases. Black 24.8.0, guardrails and all 11 historical hashes
pass on Windows Python 3.12.10 / pytest 8.3.5. Existing implementation and
contracts are unchanged. No full-suite, native Mac or independent-review pass
was claimed at that initial checkpoint. The acceptance above records the
subsequent independent review and Windows verification.

Code: `scripts/scoring_experiment/instant_directional_exposure.py`.
[Contract](INSTANT_DIRECTIONAL_EXPOSURE_CONTRACT_V1_DRAFT.json),
[checks](results/instant_directional_exposure_20261104/CHECKS.json) and
[independent review assignment](../ai/CLAUDE_DIRECTIONAL_EXPOSURE_REVIEW_20261104.md).

## Per-board denominators

The up and down boards get separate decision-eligible and retrospectively
gradable rows at 300s and 900s. A row is gradable when its own direction's
label is ready and mature by report as-of. A ready negative outcome is still
gradable. Missing, pending and unavailable outcomes retain their reasons;
they never become failures. A missing opposite-direction label does not
remove the valid board's row.

The original `instant_association.exposure_report` remains an unchanged,
separately named joint both-direction diagnostic. Greedy event association,
pointwise targets, publication clocks and all existing contracts are unchanged.
This addition defines no physical onset or operational missed-move rate.

## Explicit eligibility input

```python
from instant_directional_exposure import exposure_report

out = exposure_report(
    v2_labels,
    directional_eligibility,
    asof_ts_ms=report_time,
    ranker_slots={"baseline": [("TEST-USD", "up", cutoff)]},
)
```

Each eligibility record contains `product_id`, `direction`, 5s-grid `ts_ms`,
`available_ts_ms` and the four actual booleans `universe_member`,
`warmup_complete`, `health_verified`, `candidate_eligible`. All four must be
true for decision eligibility. The assertion must be known by its cutoff,
which must not exceed report as-of. A delayed proof cannot be relabelled as
known at an earlier cutoff; a future publication-time adapter needs its own
declared semantics.

Both directions must explicitly account for each submitted product/cutoff,
with the same universe membership. Other flags may differ by board. Unpaired
records are rejected; universe counts use up-board membership only because
paired equal membership is enforced. Relaxing either rule requires revisiting
the counting rule. Malformed records, duplicates and coerced booleans are
rejected. These checks cannot
detect products or cutoffs omitted from both boards: a complete intended
inventory and independently verified evidence are still producer requirements.
The reporter explicitly identifies eligibility as **caller assertions**, not
authenticated monitor/book evidence. It does not accept monitor proofs as
full-feed or quote certification and creates no live eligibility records.

Future labels never change decision exposure. Exclusions use the existing
flag precedence, and reason counts are exclusive by first failed flag.
Product-hours count eligible product/cutoff slots. Board hours count the
union of eligible cutoffs per board; the either-board clock is a further
union, so concurrent products and boards do not multiply elapsed time.

Ranker slots carry `(product_id, direction, ts_ms)` triples and must refer to
recorded eligibility rows. Per board/horizon, identical comparison rows are
eligible, own-direction gradable and scored by every supplied ranker. Their
identities and counts are reported alongside natural per-ranker coverage.
With no ranker mapping, the complete-row table describes all gradable eligible
rows; it is not evidence that any model scored them.

## Boundaries and next work

Synthetic hand-calculated tests cover opposite-direction missingness, true
negative gradability, horizon maturity, ranker intersections, time unions,
causal cutoffs, exclusions and malformed inputs. The existing association
tests verify its joint and greedy behavior still holds. No market data or
historical outcome experiment is run for this addition.

The independent review is complete. Next is a separately versioned
eligibility/grading evidence producer with per-row completion, actual connection
identity, streaming bounds and durable publication. Publication entry/targets,
feature ages, F1-F5, stages/model/readiness and the full study still need freeze.
Preserve the original feed gate, >=62 complete warmup minutes, locked historical
validation and V1 default. Fitting and live integration remain off.
