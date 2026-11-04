# Claude Code cloud assignment: association and exposure

Completed: cloud implementation `96f5652` was accepted as `e3529c2`, with
Codex validation followup `8631231` and 521 passing targeted checks.
Read [the November 4 acceptance](../research/INSTANT_ASSOCIATION_ACCEPTANCE_20261104.md).
The assignment below is preserved history; do not redispatch it as new work.

Prepared November 3, 2026 (Pacific). **User cloud dispatch/source-reading is
verified by screenshot; implementation/push remains pending.** Codex did not
start the session. The screenshot shows Fable 5.1 in the cloud.
The user has cloud-session promotional credit expiring November 4 at 11:59 PM
Pacific, according to the supplied Usage screenshot. This task needs only
repository sources and synthetic tests; no PC-only files or raw market data.

Start a **cloud** session at <https://claude.ai/code>, connect
`tgpetrie/moonwalking`, and select base branch `codex/instant-radar-20261028`.
The verified starting checkpoint is `6c229528047bfd5ed75fd0a44b35e95c9e9b0614`,
with monitor/sample code `4ed9045` and 405 recorded targeted checks. Later
Codex commits may implement the book adapter; do not duplicate that work.

The promotional credit is applied automatically to eligible cloud sessions;
ordinary chat, Cowork and local Remote Control are excluded. Included models
can use the bonus without paid usage credits. On Pro, Fable requires usage
credits enabled with a positive purchased balance; eligible cloud sessions
use the bonus first. Auto-reload is a separate purchase control. Verify which
balance decreases after starting.
[Official promotion](https://support.claude.com/en/articles/17152539-cloud-sessions-bonus-credit-promotion).
[Cloud workflow](https://support.claude.com/en/articles/12618689-use-claude-code-in-the-cloud).

## Paste this into the cloud session

Work on Moonwalking's instant-radar lane in repository `tgpetrie/moonwalking`.
Fetch and inspect the current GitHub tip of `codex/instant-radar-20261028`;
confirm it contains checkpoint `6c22952`. Read `AGENTS.md`,
`docs/ai/RESUME_HERE.md`, `docs/ai/ACTIVE_WORK.json`, `HANDOFF.md`,
`MW_BACKLOG.md` and the relevant specs before edits. Follow the repository's
cloud/runtime setup instructions if present. Work on a new isolated branch
such as `claude/instant-association-cloud-20261103` (or the cloud platform's
required unique variant). Never push directly to Codex's branch.

Implement a standalone **offline association and exposure reporting module**
with a versioned draft contract, meaningful adversarial tests and a concise
review report. This is a new implementation task, not a repeat of completed
Claude target/offline reviews. Codex is implementing the order-book adapter
and publication timing separately.

Read these source documents in full:

- `docs/research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md`
- `docs/research/INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md`
- `docs/research/INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md`
- `docs/research/INSTANT_CAPTURE_REPLAY_RESULTS_20261030.md`
- `docs/research/INSTANT_COVERAGE_AND_QUOTE_POLICY_20261030.md`
- `scripts/scoring_experiment/instant_targets.py`
- `scripts/scoring_experiment/instant_diagnostics.py`

Use new scoped paths, for example:

- `scripts/scoring_experiment/instant_association.py`
- `tests/test_instant_association.py`
- `docs/research/INSTANT_ASSOCIATION_CONTRACT_V1_DRAFT.json`
- `docs/research/INSTANT_ASSOCIATION_EXPOSURE_20261103.md`
- `docs/research/results/instant_association_20261103/CHECKS.json`

Requirements:

1. Preserve primary pointwise success/failure at its declared fixed horizon.
   Association with another catalog window must never forgive a failed
   pointwise prediction. Pending/unavailable outcomes remain ungradable and
   visible outside success/failure denominators. Keep 300s and 900s separate.
2. Implement the proposed **forward-window coverage diagnostic**, separately
   named and explicitly unrelated to physical onset: group by product,
   direction and horizon; sort catalog windows by anchor; assign the earliest
   unused qualifying alert in `[anchor-180s, forward_peak]`, using actual
   publication time and retained publication ID to break timestamp ties.
   One alert can cover at most one window per horizon. Preserve unmatched
   alerts/windows and left-censor flags. Validate duplicates, malformed rows,
   incompatible contract/evaluator provenance and ambiguous identities.
   Reject or explicitly mark invalid inputs; never coerce missing to false.
3. Define exposure from explicit 5s-grid eligibility records. Report causal
   decision-eligible product-hours separately from retrospectively gradable
   product-hours; missing future data must not erase the decision universe.
   Board wall-clock hours are the union of eligible slots, not their sum
   across products. Preserve universe size per cutoff, warmup/health/universe/
   candidate exclusions, trailing maturity, ungradable counts and coverage.
   Refuse duplicates or overlapping/ambiguous slots rather than double-count.
   Specify identical complete-row comparisons versus natural ranker coverage.
4. Test both directions and horizons; zero/empty denominators; absent rows;
   shrinking universes; timestamp/ID ties; one-to-one matching; censored
   windows; a 5m alert with a move only at +340s; a 15m alert with a move only
   at +940s; and publication at a completed window endpoint. The latter cases
   must demonstrate that association cannot alter primary pointwise failures.
   Include independent small hand-calculated matching/exposure oracles.
5. Retain input anchor, actual publication and input availability separately.
   Accept no late feature as known at an earlier anchor. Current targets are
   anchored at the decision cutoff; any proposed publication-anchored target
   is a separate draft amendment. Do not silently change target timing.
6. Keep physical onset undefined and operational physical missed-move rates
   disabled. A conditional catalog coverage rate may be reported under its
   explicit name and denominator. Keep the full study unfrozen, feed gate
   false and fitting disabled. This module can pin an executable reporting
   rule for review; it cannot approve the entire study or manufacture readiness.

Do not modify existing target/recorder/baseline/monitor/sample/book modules,
existing target contracts, frozen historical artifacts, old review reports,
live services, frontend or scoring weights. Preserve V1 default behavior and
the separate held original Claude `d711832` commit. Do not run historical
discovery/validation, fundamentals experiments, new captures, scoring fits,
external-data downloads or another general review of already accepted code.

Run the meaningful new tests and relevant existing target/diagnostic tests,
formatting and repository guardrails. Report exact commands, Python/library
versions and real results; report environment limitations honestly. Synthetic
checks are not market performance. Verify target/evaluator bytes remain
unchanged and the 11 historical hashes still match. Follow `AGENTS.md` for a
branch-specific handoff; keep a pointer to the authoritative Codex resume
branch and identify your contribution as pending Codex review. Do not mark
other agents' work complete or merge your branch.

Commit and push coherent work to your own branch. Return the branch, commit,
review report, test results and any remaining dirty files. A draft PR against
`codex/instant-radar-20261028` is welcome if supported; never merge it.

## After this task

Let Codex verify the returned commit and tests before integration. Remaining
cloud credit can fund a separate bounded review of the newly pushed book and
publication-timing implementation, or a Linux portability run of the relevant
offline tests. Pin those assignments to actual new commits. Do not rerun the
locked outcome experiment or repeatedly review unchanged code to use credit.
No dollar-per-task or completion-time estimate is established here.
