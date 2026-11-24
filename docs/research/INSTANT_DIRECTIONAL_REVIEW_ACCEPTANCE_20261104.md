# Directional exposure review accepted

November 4, 2026 (Pacific). Codex verified pushed Claude commit
`583a73a081be74e5c0960b178399b60e14da3312` on
`claude/instant-directional-exposure-review-20261104`, based on `f561706`.
The review, check record and 51 independent probes are integrated as
**`4925ac5`**. The reviewed implementation stays **`9da4987`**, unchanged.
No defect was found in the reviewed reporting scope and no patch was applied.

Read [Claude's report](reviews/CLAUDE_DIRECTIONAL_EXPOSURE_REVIEW_20261104.md),
[the original cloud checks](results/claude_directional_exposure_review_20261104/CHECKS.json)
and [Codex's acceptance checks](results/instant_directional_review_acceptance_20261104/CHECKS.json).
The original report's pending status describes its submission, not current status.

## Verification

Codex inspected all three changed files and checked the directional source,
contract, existing tests, association dependencies and new probe hashes against
Claude's record. No implementation or existing contract changed. **1,163
targeted tests pass** on Windows Python 3.12.10 / pytest 8.3.5, including all
51 new probes against the unchanged implementation. There is no pre-patch
failure to claim. Black 24.8.0, guardrails and all 11 historical hashes pass.

The probes independently exercise the three-product/four-cutoff hand oracle,
per-board and either-board time unions, own-direction gradability, true
negative gradability, separate horizon maturity, ranker intersections,
causal eligibility boundaries, missingness, malformed inputs and immutability.
The existing joint reporter remains unchanged. Claude additionally reports
seven deliberate mutants detected in scratch copies; Codex did not rerun
those mutation experiments and retains that result as attributed evidence.

Claude's Linux Python 3.12.3 runtime remains recorded separately. No full-suite,
native Mac, market-data, predictive-performance or new outcome-study pass is
claimed. Targets/V1/V2, monitor, samples, book, publication, diagnostics,
recorder/baseline, historical artifacts, backend and frontend are unchanged.

## Suggestions and dispositions

| Suggestion | Disposition |
|---|---|
| S1: malformed ranker shapes raise different exception types | They reject without a false pass. Consistent exception messages are optional hardening; no behavior change in this acceptance. |
| S2: association permits future-anchored pending/unavailable labels | Outside the directional scope. Such labels cannot match a valid directional eligibility cutoff; no current exposure is added. Preserve the accepted association behavior; producer/grading rules must handle their own chronology explicitly. |
| S3: a ranker with no scores on a board empties the shared comparator | Retain the declared all-ranker intersection, including the empty ranker. Natural coverage already reports its zero counts. Do not silently remove it and improve the comparison cohort. Any board-specific ranker roster must be predeclared. |
| S4: universe counts use up-board membership | Sound because both board records and equal membership are enforced. Clarify this dependency in the usage document without changing contract bytes. |

## Remaining boundary and next task

The two limitation probes are accepted too: a caller can assert an unverifiable
early availability time, and a product missing from both boards is invisible.
The reporter does not authenticate eligibility or prove intended-universe
completeness. Accepting the arithmetic does not close those evidence gates.

Next, implement a separately versioned eligibility evidence producer and
intended product/cutoff inventory, preserving actual row-processing completion
and explicit unavailable records. It must distinguish trade-ID proofs, quote
health, baseline warmup, feature availability and publication timing; existing
monitor proofs are not full-feed or quote-health assertions. Later grading
evidence, real connection identities, streaming/persistence bounds and durable
publication remain separate requirements before a predeclared source pilot.

This Claude assignment is complete. No duplicate review or new cloud task is
queued. The study remains unfrozen; original feed gate and >=62 complete
warmup minutes remain required. Historical validation stays locked, V1 stays
default, physical onset stays undefined, and fitting/live scoring are unchanged.
