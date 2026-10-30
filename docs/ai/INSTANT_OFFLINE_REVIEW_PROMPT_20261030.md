# Prepared Claude review prompt — offline instant pipeline

Completed: the user supplied Claude's `f2cc436` review; Codex accepted the fix
through `ab95159`. See
[the acceptance](../research/INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md).
Do not redispatch this completed general review. The original prompt below
is preserved as the assignment record.

Prepared only, not sent. Implementation `8211262` on
`codex/instant-radar-20261028`. This is a new bounded assignment, distinct from
the completed v2 target review and the remote onset/gap proposal.

Independently review the new offline instant pipeline at `8211262`. Follow
AGENTS.md, fetch GitHub, inspect status/worktrees and work on your own separate
review branch/worktree. Read HANDOFF.md, docs/ai/ACTIVE_WORK.json and
docs/research/INSTANT_OFFLINE_PIPELINE_20261030.md first. The target evaluator
and V1/V2 target JSON files remain unchanged from `92fb51d`.

Review instant_diagnostics.py, micro_replay.py, micro_baseline.py, both new
draft contracts and tests/test_instant_diagnostics.py plus
tests/test_micro_replay.py. Check that separate whole-window/forward-peak
metrics do not alter target labels, unavailable reasons are explicit and gap
censoring cannot masquerade as a physical onset. Check receipt boundaries and
the exact boundary-trade count, deduplication across connections, unknown
sides, last_match/REST exclusion, clock failure, original quote ages, health
known-at times, negative coverage assertions, sparse zero versus outage,
readonly/non-overwrite behavior and source/contract hashes.

For baselines, independently verify 60 paired closed-minute returns, sample
standard deviation, beta fallback, 120 nonoverlapping pace windows and both
cutoffs. Try to make a later quote, recovery or coverage verdict affect an
earlier feature. Distinguish an actual defect from deliberately unavailable
data or a supplied health assertion that still requires external validation.

Run the two new suites and relevant target compatibility tests. Report exact
checks, minimal counterexamples, expected/actual behavior and limitations.
Commit/push coherent findings or minimal verified fixes on your own branch.
Do not fit scoring models, rerun historical outcomes, start captures, alter
the feed gate, connect to the collector, change live ranking or merge unrelated
branches. Do not repeat a general review of the already-accepted target code.
