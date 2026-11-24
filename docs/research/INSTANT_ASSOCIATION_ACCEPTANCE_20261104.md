# Cloud association/exposure contribution accepted — November 4, 2026

Codex verified the pushed branch `claude/instant-association-cloud-20261103`
and its base `1d394e4`. Implementation `96f5652` was reviewed and cherry-picked
as `e3529c2`. The cloud's documentation-only `a7604845` was not cherry-picked;
the authoritative Codex handoff is updated separately. Earlier rejected cloud
pushes did not modify Codex's branch. No backup refs were deleted.

The contribution supplies a standalone versioned reporting module and 50
synthetic tests. Codex reproduced them in Windows Python 3.12.10 / pytest
8.3.5. The original cloud report remains pinned to its Linux Python 3.13.18
execution; neither run is a native Mac verification.

## Accepted behavior and follow-up checks

Primary success/failure stays at each alert's declared cutoff and fixed 300s
or 900s horizon. Missing/pending/unavailable labels stay outside graded
denominators. Association cannot forgive a pointwise failure. The three
evaluator-graded delayed-move/endpoint cases verify that distinction.

Forward-window coverage retains the predeclared earliest-unused publication
rule, ordered by publication time then ID. This is a deterministic greedy
diagnostic, not maximum matching or physical-event recall. Keep it rather
than optimize the coverage number after observing outcomes. Left-censor flags,
unmatched alerts/windows and null physical missed-move rates remain visible.

Exposure counts causal eligible slots independently of future label quality;
board wall-clock exposure is their time union. Existing gradable/comparator
rows explicitly require both directional labels ready. This conservative joint
table is accepted as named in the contract; it must not be presented as a
direction-specific board's denominator. Per-direction eligibility/gradability
and the evidence-producing recorder adapter remain pre-freeze requirements.

Codex reproduced and fixed two validation gaps, with three new tests:

- Duplicate ranker slots were silently converted to a set. They are now
  rejected, matching the contract's duplicate-rejection rule.
- A float horizon with otherwise integer metadata could match an integer
  horizon identity. Horizon metadata now requires an actual integer.

**521 targeted tests pass**: the prior 468, 50 cloud tests and three Codex
cases. Black 24.8.0, guardrails and all 11 historical hashes pass. Targets,
diagnostics, recorder/baseline, monitor, samples, book, publication and their
existing contracts are unchanged. The original cloud check record is retained;
[the new acceptance record](results/instant_association_acceptance_20261104/CHECKS.json)
identifies the tested code. Hash metadata and explicit eligibility flags remain
caller assertions, not authentication or independently proven feed health.

## Older October 30 onset proposal

Codex compared `4610bf2` against the current target source. Its raw-catalog
left-censor addition is not reapplied: the separately versioned
`instant_diagnostics.forward_catalog_report` already provides previous-anchor
status, a left-censor flag and its reason, and this new association module
uses that wrapper. The unchanged raw target API is not claimed to emit these
report fields. Keeping the wrapper preserves the target evaluator's pinned
bytes and V1 behavior. Historical synthetic reproduction scripts may still
call the raw API for their original examples.

S1 remains the consolidated draft choice: whole-reference-window peak for
strict timing, plus a separately named forward-peak consumption diagnostic.
The proposed one-line substitution would change the meaning of strict timing;
it is not applied. Neither reference is physical onset. `d711832` also remains
unmerged as an exact commit; its policy was already adapted into opt-in V2.

The reporting component is integrated as a draft, not an overall study freeze.
No new data, return-label experiment, fit, historical rerun, capture or live
change ran. The next independent contribution is bounded reconciliation at
`bfab9c8`, now pushed on local Claude's branch but **not reviewed or integrated
by this acceptance**. Publication/entry timing, later grading evidence,
per-row availability, streaming limits, feature/model/readiness rules and the
original feed gate still precede the pilot and 14 valid shadow days.
