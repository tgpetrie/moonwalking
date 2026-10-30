# Instant-radar v2 review acceptance — 2026-10-30

Codex reviewed Claude's pushed `10b0f96`, reproduced its catalog defect before
applying the patch, and cherry-picked the review, probes and fix as `1da6f4e` on
`codex/instant-radar-20261028`. Black 24.8.0 formatting follows at **`92fb51d`**,
the current implementation. Parsed code is equivalent to Claude's patch apart
from docstring whitespace. Claude's worktree and earlier branch are untouched.

Read [Claude's original review](reviews/CLAUDE_INSTANT_V2_REVIEW_20261030.md)
and [Codex's verification record](results/instant_v2_review_acceptance_20261030/CHECKS.json).

## Accepted fix

Before the patch, `forward_event_catalog` stamped a verified v1 label as a v2
forward window although `forward_alert_timing` rejected it. The wrapper now
requires the v2 draft. The generic v1 catalog and target formulas are unchanged.
Codex verified rejection of v1 input and acceptance of genuine v2 and empty
generator inputs. This corrects provenance/API consistency; it supplies no
market-performance evidence.

Both contract JSON files are byte-identical to `8b5b266`. The source edit and
formatting change the evaluator hash. Regenerate unfrozen v2 labels with the
accepted source before new evaluation; do not mix evaluator hashes. No study
labels were frozen here. The old Gemini packet and reproduction record remain
pinned to the initial `8b5b266` source; their hash is not the current hash. The
new verification record contains current-source examples. Full proposal
fidelity still requires the unamended original.

## Decisions before study freeze

| Item | Codex disposition |
|---|---|
| S1: earlier wick controls strict early/late timing | Reproduced: a wick ten seconds before the trigger gives `late_after_activity_trigger` with about 8.9% consumed at the trigger. This follows the whole-reference-window peak rule. Retaining it, changing the peak reference, or requiring a sustained extreme needs an explicit prespecified choice. No policy changed here. |
| S2: sigma and pace cutoffs differ | Confirmed causal: sigma ends at the completed minute before anchor minus 35 seconds; pace ends at anchor minus 30 seconds. They estimate different quantities. This is not future-data leakage. Decide whether to retain the distinction and verify the recorder's pace construction. |
| S3: null fraction lacks a reason | Independently reproduced for a complete forward-only label with no positive peak relative to anchor minus 30 seconds. Record an explicit non-positive-reference-peak reason before freezing the reporting schema. No field/contract change was silently added here. |

The target code review is complete with one accepted fix. The study is **not
frozen or ready for fitting**. Gemini's v2 consistency review, physical-origin
or explicit proxy policy, association/exposure and operational denominators,
exact F1-F5 formulas, stages/readiness, feed gate and recorder contract remain
open. At least 14 valid shadow days and fresh validation are still required.
No fit, historical rerun, live ranking, collector or deployment change occurred.

Next: consolidate these choices with Gemini's v2 review and write one explicit
freeze candidate with supporting/rejecting criteria, then check unchanged data
gates. Do not repeat Claude's completed code review or historical validation.

## Verification

**316 targeted checks pass**, including **265 instant-target cases**; guardrails,
Black 24.8.0 and diff checks pass. Collected target cases are 53 existing v1,
26 existing v2 and 186 new Claude cases. Claude's total of 265 is reproduced;
its prose breakdown of 44 existing plus 221 probes is corrected by collection.
All 11 frozen historical contract artifact hashes are unchanged.

The isolated `tests/test_seed_fixture.py::test_load_dev_volume_fixture` still
fails with 60 points rather than the expected 10. Both the test and its
implementation are identical to `8b5b266` and were left untouched. Codex did
not rerun the full tests folder and claims no full-suite pass. These synthetic
checks do not establish predictive improvement or native Mac execution.
