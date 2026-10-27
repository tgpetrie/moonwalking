# Live-movers comparison driver: pre-fit review - 2026-10-27

Reviewed Claude's committed driver at `0832f24` against the frozen
`COMPARISON_SPEC.json` and `CONTRACT_PRODUCTION.json`. The review/fixes live
on `codex/live-movers-driver-review-20261027`, based on that commit, in a
separate worktree. Claude's worktree was inspected read-only and left intact.
No discovery or historical validation analysis was run for this review.

## Findings reproduced and fixed

1. **Frozen bootstrap seed was not used for the primary result.** The
   submitted driver added 100 for the primary stratum and another 1 for the
   block interval, yielding 20261127 / 20261128 instead of the specified
   20261027. Both methods now use the specified seed and 5000 replicates;
   those settings are explicit in each paired-comparison result.
2. **Tied scores produced artificial quintile separation.** With identical
   scores on ten synthetic rows having outcomes 0 through 9, the driver
   reported quintile means 0.5, 2.5, 4.5, 6.5, 8.5. Reversing row order
   reversed that apparent separation. Average-rank percentile bands now keep
   ties together and omit empty bands; a constant score has one band with
   mean 4.5. This matters for saturated ordinal scores and tied baselines.
3. **The one-test guard was local-only and had no attempt reservation.**
   A committed test report on another machine could be overwritten if the
   local work directory was empty. Both local/repository reports now block
   another run. Atomic exclusive reservation also blocks concurrent or
   interrupted local attempts; test-result writes cannot overwrite a file.
4. **A docs/result commit invalidated otherwise identical discovery.**
   Requiring the same entire HEAD would prevent committing discovery results
   for a normal Git handoff before validation. Input hashes and exact
   driver/classifier hashes now define compatibility; commit IDs remain
   provenance. A committed discovery artifact is a fallback when the local
   copy is absent. Actual code/input changes still refuse validation.

Four new regression cases failed on the submitted implementation and passed
after correction. Two additional cases verify full eligible-list identity
and daily reporting. These cases use synthetic data only.

## Additional contract checks

- Eligibility reruns the frozen classifier, sorted by `entered_ts,id`, with
  cooldown before feature completeness and the existing phase purges. The
  CSV comparison now checks **id, board, product, direction, entered timestamp
  and phase**, in order, rather than only id/phase. Frozen input hashes still
  protect both files before this independent identity check.
- Preprocessing is fitted on fitting rows only; nonlinear transforms use
  clipped raw inputs. Price features are direction-aligned, volume is not,
  and labels are already directional percentage returns. Cost scenarios
  subtract once from gross labels.
- Daily paired ICs use identical groups across all four models. Results now
  include each day's ICs, actual scored row counts and reasons for excluded
  groups, making coverage/attrition reviewable.
- Test still refits selected models on train plus discovery. The ordinal
  display reference uses that fixed fitting distribution; raw predictions
  remain the IC input. Direction, horizon and historical limitations remain
  explicit. No feature, date split, minimum effect or cost scenario changed.

All 23 targeted tests pass: six contract tests, the original eleven driver
tests with corrected discovery compatibility, and six review regressions.
Repository guardrails and `git diff --check` pass. The immutable
contract/result directory is unchanged.

## Next step on the main scoring track

Commit the reviewed driver, rerun **verify only** from that clean code, and
preserve the new verification artifact with the correct code hashes. Once
that gate passes, the driver is ready for the predeclared discovery phase.
Freeze its resulting choices before the one-time historical validation.
Do not relax any gate based on outcomes. Fourteen historical validation days
remain limited, previously inspected history; the result cannot authorize a
live ranking change. The independent 30s feed audit need not delay this lane.
