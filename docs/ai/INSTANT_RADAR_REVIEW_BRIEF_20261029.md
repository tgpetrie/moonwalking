# Instant radar review assignments - 2026-10-29

Implementation owner: Codex in `C:\Users\tgpet\Projects\Moonwalking-InstantRadar`,
branch `codex/instant-radar-20261028`. Other apps have not been dispatched by
Codex; these are ready-to-use assignments. The Windows work does not require
a MacBook. Use the branch's newest pushed commit for review.

## Claude: independent implementation review

Use the existing clean checkout `C:\Users\tgpet\Projects\Moonwalking-Claude`
in Claude Code's Local environment. If the conversation's remote-folder
approval keeps expiring, open a new Code session on this folder. Fetch and
inspect the target branch without overwriting local work. For any fixes,
create your own branch/worktree under the repository's `AGENTS.md` workflow.
Never edit Codex's active worktree.

Review the diff of `origin/codex/instant-radar-20261028`, especially:

- `docs/research/INSTANT_TARGET_CONTRACT_V1.json`
- `docs/research/INSTANT_TARGET_LABELS_20261029.md`
- `scripts/scoring_experiment/instant_targets.py`
- `tests/test_instant_targets.py`

Look for future-data leakage, false labels from missing observations,
direction asymmetry, exact-boundary errors, baseline contamination, onset
selection/overlap bias and double-counted costs. Add independent synthetic
counterexamples where a real defect is suspected. Report severity, location,
minimal reproduction and proposed correction. Do not retune thresholds,
rerun historical discovery/validation or touch live ranks/production.

## Gemini: design consistency and falsifiable hypotheses

Read the corrected prospective contract and the executable target doc/JSON
from the same GitHub branch. Compare them with your original early-warning
proposal. Explicitly assess the now-fixed breakout origin, full-horizon
no-retrace rule, activity-confirmed onset and market-relative consumed fraction.
Identify whether these operational choices distort the intended prediction
question; suggest corrections before any prospective outcome analysis.

For each F1-F5 mechanism, state its expected direction, whether evidence
should appear before onset or only afterward, its comparator/ablation, and
what result would reject the hypothesis. Preserve the fixed 30s/180s input
windows and 5m/15m outcome horizons. Do not invent weights, optimize using
the completed historical validation or claim mockup performance is measured.

## Local models: bounded assistance

Use the repository's local-assistant workflow and supply bounded, explicit
inputs. Local 14B may review a synthetic trace or audit summary for a specific
contradiction. Local 9B may summarize failing checks or collection status.
Require source locations and distinguish measured facts from suggestions.
They do not own repository changes, determine study acceptance, run fitting
or authorize changes to live scores. Deterministic code verifies every claim.
