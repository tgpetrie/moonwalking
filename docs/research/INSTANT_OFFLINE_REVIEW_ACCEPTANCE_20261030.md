# Offline instant review acceptance — 2026-10-30

Codex reviewed Claude's `f2cc436` on `claude/instant-offline-review`, based on
offline implementation `8211262`. The first pasted report was the already
accepted `10b0f96` target review, not another new assignment; it was not
reapplied. The new report/probes/fix were cherry-picked as `749e792`.
Formatting and follow-up provenance/reason improvements are at **`ab95159`**.
Claude's worktree is untouched.

Read [Claude's report](reviews/CLAUDE_INSTANT_OFFLINE_REVIEW_20261030.md),
[pipeline usage](INSTANT_OFFLINE_PIPELINE_20261030.md) and the
[verification record](results/instant_offline_review_acceptance_20261030/CHECKS.json).

## Accepted defect and fix

D1 reproduced before applying the patch: with increasing receipt times,
monotonic timestamps `100s, absent, 50s` were accepted and the artifact could
be sealed. The recorder checked only the immediately previous packet.
It now checks the last packet with a monotonic timestamp; the regression
raises and leaves the artifact failed. The capture writer supplies this field,
but this review did not inspect every historical packet or prove that absent
values never occurred in real data.

The recorder hash changes. No prospective replay artifact is frozen. Before
future study use, regenerate or independently revalidate older prototype
replays; do not silently relabel them as newly clock-validated data.

## Integration items resolved or qualified

| Item | Disposition |
|---|---|
| Missing `source` defaults to WS | Retained: this matches the audit's envelope writer. Ordinary REST-shaped data without a match type cannot become an execution in the probe. This does not authenticate packet origin: any adapter converting recovery to match-shaped messages must preserve `rest`/`rest_recovery` explicitly. Unknown tags fail closed. The "all tags must be explicit" doc wording is corrected. |
| Health at each cutoff | To verify every 5s cutoff, sufficiently granular spans must be completed and their evidence available by that cutoff. A larger interval can verify eligible endpoints, not every earlier snapshot. Cadence alone does not prove coverage or eliminate reconciliation/processing latency. Late verdicts remain late; adapters must preserve cutoff, publication and availability times. |
| Trusted assertions | Shape/known-at checks do not independently prove subscriptions, trade coverage or quote quality. Feed gate remains false. |
| Recorder/source identity | Baselines now retain producer hash and full replay provenance: reader hash, producer/reader equality and canonical input-manifest hash. Reopen can pin `expected_recorder_sha256`; mismatches are refused. Default historical reading remains possible with a visible producer mismatch, rather than pretending a new reader produced old data. Metadata checks do not authenticate inputs or replace frozen raw-artifact manifests. |
| Two missing-data causes | Added `pre_window_reference_unavailable_reason` and `publication_unavailable_reason`. Original reason precedence is retained; both independent causes are visible without changing target labels. |

Claude's independent numpy checks reproduce sample volatility, centered OLS
beta, flat-benchmark fallback and the 120-window pace medians. Later conflict,
audit, quote and coverage knowledge leave earlier snapshots unchanged in the
committed probes. This establishes tested synthetic behavior, not market
predictability or continuously verifiable live coverage.

## Verification and next step

**356 targeted checks pass**: the previous 346, seven independent Claude
probes and three new producer/reason regressions. Black 24.8.0, repository
guardrails, all 11 historical contract hashes, compatibility and documentation
checks pass. The target evaluator and V1/V2 target JSON files are unchanged
at `92fb51d`; no target-label regeneration is required solely for this layer.

Codex did not rerun the full test folder. Claude reported the existing seed-
fixture failure; that unrelated implementation/test are untouched. No full-
suite or native Mac/cloud execution pass is claimed.

The independent offline review is accepted with the fix and qualified items
above. Next is bounded replay of preserved captures, evidence-backed health/
subscription/reconciliation adapters and paired immutable target samples.
Do not repeat completed general target/offline reviews because older records
say pending. The feed gate, feature/stage/model/readiness freeze, 14 valid
shadow days and fresh validation remain required. No new capture, scoring-
model fit, historical experiment, collector, ranking or other worktree changed.
