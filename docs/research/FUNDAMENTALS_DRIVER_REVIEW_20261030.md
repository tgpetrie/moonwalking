# Fundamentals driver review - 2026-10-30

Reviewed Claude implementation `058d740fd2fe95c3e55376a97039c47e738219ab`
from `claude/fundamentals-prep`. Work is isolated on
`codex/fundamentals-driver-review-20261030` in
`C:\Users\tgpet\Projects\Moonwalking-FundamentalsDriverReview`.
Claude's worktree, the funding null, source captures and approved cohort remain
untouched. The pasted live-movers handoff at `0832f24` describes a different,
already-completed historical study and is not this driver's review target.

## Confirmed findings and corrections

| Finding | Reproduced consequence | Correction |
|---|---|---|
| Readiness called the model fitter | Full-universe walk-forward fits and internal validation ran before the readiness exit, despite the outcome-blind claim. No fundamentals comparison result was produced, but the phase was not strictly no-fit. | Compute S0 availability from label-presence masks and purged row counts, then exit before any fitter. An integration test makes any readiness fitter call fail. |
| Guards ran after model work | A test request without discovery could already fit baseline models. | Preflight runs before loading model data/fitting; malformed or incomplete discovery fails closed. |
| Local-result-only once guard | Removing a local file or retrying after an interrupted run could bypass the intended one-test policy. | Check local and committed copies; reserve exclusive local/repository attempt markers before test fitting; retain failures. |
| HEAD equality conflicted with freezing discovery | Committing the discovery artifact changed HEAD and would make an otherwise identical test incompatible. | Fingerprint code dependencies, protocol and runtime; require the local discovery to match its committed freeze. Documentation/results commits alone are compatible. |
| Baseline cached data were not in phase identity | A changed pickle/build artifact could be used with the same cohort/config/fee provenance. | Hash baseline pickle, build metadata and panel manifest; verify the build's recorded manifest matches. |
| Input identity used native path separators | Identical input bytes could yield different provenance on Windows and macOS. | Store the repository-relative cohort path with portable forward slashes. |
| Reported scored rows included missing labels/unscoreable dates | Prediction availability could inflate counts relative to paired daily IC evaluation. | Separate prediction/scored counts and retain only actual common IC dates; expose paired daily IC values. |
| Moving bootstrap compacted missing weeks | Adjacent array entries could represent nonadjacent calendar weeks. | Use actual four-consecutive-ISO-week windows, with explicit unavailable results when coverage cannot support them. |

The frozen primary comparator is retained. The additive S1 fit also learns
S0's scale/sign, while raw S0 is not recalibrated. In a synthetic counterexample,
S1 gains almost 2 IC over an inverted raw S0 even with zero cross-sectional fee
information; its gain over a calibration-only stack is zero. This is not a market
result. A prespecified descriptive control now exposes that attribution issue.
The original primary verdict applies to the joint stack and cannot by itself
establish that the fee feature supplied the improvement.

Protocol amendment A2 records these choices before any fundamentals discovery
or primary test. No feature/window/cohort/lag, ridge grid, held-out dates or
primary effect threshold was selected or changed using outcomes.

## Readiness and remaining work

Corrected readiness **passed** on the actual frozen inputs at reviewed code
`6809933`. Both the 1-day and 7-day horizons first satisfy the fit-size gate in
December 2023: **5,355 training rows against the 5,000 minimum**. All G1-G5
coverage gates pass for the saved 27-approved/5-held cohort. The
[saved report](results/fundamentals_driver_review_20261030/READINESS.json) records
`model_fits_run: false`. It consumes availability masks, hashes and counts;
no comparison fits, ICs, discovery result or primary test ran in this review.

After the readiness checkpoint passes, the next action is discovery using this
reviewed driver, followed by a committed/pushed freeze and the single primary
test. No live ranking/deployment follows merely from readiness or statistical
support for a retrospective backfilled source. Publication/revision caveats
remain, and adequate power is not established by passing coverage minima.

The instant-radar v2 study is separate. Its 130-test result and pending design
review do not establish this fundamentals driver's correctness; this driver
has its own targeted regression checks and readiness evidence.

Verification: **77 targeted tests pass**: 70 research checks, including
13 independent driver-review regressions, plus seven existing safe-restore
checks imported unchanged from committed instant-radar checkpoint `1aa9926`.
Black 24.8.0 and diff checks pass.
The accepted cohort hash manifest and frozen feature/config/baseline/evaluation
files match the original reviewed checkpoint. Full repository guardrails fail
on the pre-existing `frontend/src/components/ScorecardPage.jsx` placeholder
`BTC or BTC-USD` (line 775 at the reviewed checkpoint); that unchanged UI file
is outside this research patch. No full-repository guardrail pass is claimed.

## Portable checkpoint

Start with [the fundamentals resume page](../ai/FUNDAMENTALS_RESUME_20261030.md).
The code, protocol, accepted cohort, readiness and review live on the named
GitHub branch. A separate hash-pinned input archive carries the project-generated
baseline cache, build/panel provenance and the 27 approved fee captures. It
excludes credentials, account databases, held captures and discovery/test output.
The committed transfer receipt records verification after downloading from
GitHub. Native Mac/cloud model execution remains unverified.
