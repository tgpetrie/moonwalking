# Resume fundamentals research — 2026-10-30

Repository: <https://github.com/tgpetrie/moonwalking>.
Branch: `codex/fundamentals-driver-review-20261030`.
Use the current pushed tip; reviewed model code is `6809933`.

Codex has completed the requested independent review of Claude's `058d740`
driver. Gemini's earlier cohort work is accepted: 27 products approved, five
held. Do not restart the cohort request. The corrected readiness check passes
with no model fits. **No fundamentals discovery or primary test has run.**

Read [the review](../research/FUNDAMENTALS_DRIVER_REVIEW_20261030.md),
[the protocol including amendment A2](../research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md),
[the readiness evidence](../research/results/fundamentals_driver_review_20261030/READINESS.json)
and [machine-readable status](FUNDAMENTALS_ACTIVE_WORK_20261030.json).
The older preparation status and July application handoff are preserved history.

## Checkout and exact inputs

Use a clean checkout/worktree connected to the authoritative remote, with both
the checkout and Git common storage outside synced folders. Before edits, fetch,
inspect branch/status/diff/worktrees and read the repository's agent rules.
Keep parallel Claude and Codex work on separate named branches/worktrees.
Windows review checkout:
`C:\Users\tgpet\Projects\Moonwalking-FundamentalsDriverReview`.
Other computers may use any suitable local path.

The input archive contains exactly 30 public-market research files: the
project-generated baseline cache, its build metadata and panel manifest, and
27 approved dailyFees captures. The cache already includes the frozen market
features/labels required by this driver; full raw candles are not required to
resume this comparison. It does not contain credentials or account data.
Only load this exact verified project-generated pickle; never substitute an
untrusted pickle or silently rebuild/recapture inputs.

The archive remains on the existing **draft** GitHub release and requires
authenticated repository access. Download with GitHub CLI from a clean branch
checkout:

```sh
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --pattern moonwalking-fundamentals-inputs-20261030.tar.gz --dir ../fundamentals-inputs
python scripts/restore_macbook_evidence.py ../fundamentals-inputs/moonwalking-fundamentals-inputs-20261030.tar.gz --manifest docs/ai/FUNDAMENTALS_INPUT_MANIFEST_20261030.json --destination ~/.moonwalking
```

The destination is **`~/.moonwalking`**, not its `analysis` subfolder. The tool
checks the archive, complete allowlist and every member hash, rejects unsafe
paths and refuses to overwrite different existing files. The pinned
[manifest](FUNDAMENTALS_INPUT_MANIFEST_20261030.json) and
[cloud transfer receipt](FUNDAMENTALS_GITHUB_TRANSFER_20261030.json) establish
the exact bytes. Restore both result and attempt artifacts as well if work has
advanced beyond this checkpoint; do not evade the single-test policy on a new
computer. Check GitHub's latest branch and handoff before starting any phase.

Use Python **3.12.10**, NumPy **2.5.3**, pandas **3.0.6** (pytest **8.3.5** for
the checks). Code/protocol/runtime fingerprints must match across discovery and
test. Preserve the accepted cohort's LF bytes and source hashes. Native Mac or
cloud model execution has not been verified; the archive has been downloaded,
checked and restored to a fresh directory on Windows.

## Next action and ownership

The implementation owner (Claude or Codex, in its own worktree based on this
reviewed branch) can next run discovery once:

```sh
python scripts/scoring_experiment/fundamentals_run.py discovery
```

Review and commit/push the emitted discovery artifact from
`docs/research/results/fundamentals_comparison/` before the single primary test.
Do not change formulas, cohort, windows, lag, effect threshold or ridge grid
after viewing outcomes. The driver requires the local discovery to match its
committed freeze, unchanged inputs/code/protocol/runtime, and no prior test
result or attempt marker. A failed test attempt stays recorded; investigate
without deleting the marker or retrying silently. This review did not authorize
or execute discovery or the primary test on the user's behalf.

The frozen primary comparison is the joint S1 stack versus raw S0. A positive
primary verdict alone cannot attribute lift specifically to fees: inspect the
prespecified descriptive calibration-only control. It adds no confirmatory
test and does not change the frozen primary rule. These are retrospective
backfilled sources; passing coverage does not establish statistical power or
point-in-time deployability. No live ranking, weights or deployment changes
follow from this review.

The funding null and historical live-movers result remain locked. The instant
board remains a different prediction problem on `codex/instant-radar-20261028`;
its v2 review, thin-product feed gate and shadow-data requirements remain open.
Do not disturb the always-on Windows collector on port 5003.

## Verification

77 targeted checks passed: 70 research checks (13 independent new driver-review
regressions) and seven existing safe-restore tests. Formatting and diff checks
pass. The full repository guardrail fails on the pre-existing untouched
`frontend/src/components/ScorecardPage.jsx:775` placeholder `BTC or BTC-USD`.
That application issue was not changed to clear this research review.
