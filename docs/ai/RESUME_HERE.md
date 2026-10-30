# Resume Moonwalking from anywhere

Updated October 30, 2026 (Pacific). This page is the current portable
checkpoint for the **instant radar scoring work**. GitHub holds the code,
contracts, completed results, work status and downloadable research evidence.
The [active-work record](ACTIVE_WORK.json) supplies the branch, implementation
commit, owners, gates and next actions in machine-readable form.

Latest implementation: **`ab95159`** accepts Claude's `f2cc436` review of the
[offline recorder, diagnostics and causal baseline builder](../research/INSTANT_OFFLINE_PIPELINE_20261030.md).
356 targeted checks pass, including seven independent offline probes. The target evaluator and
V1/V2 target contracts remain unchanged at `92fb51d`; no label regeneration is
required solely for this additive layer. All feed/study/live gates remain off.
The [offline review acceptance](../research/INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md)
records the clock fix, producer provenance and qualified health/source notes.
That review is complete. Next is bounded replay of preserved feed data,
real-data health and paired immutable target-sample adapters.

October 30 update: both source-based Gemini responses have been received,
reproduced and [triaged](../research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md).
The opt-in v2 draft at `8b5b266` adds a forward-window catalog and names
reference-dependent timing metrics; it incorporates Claude's reviewed
baseline cutoff. V1 stays the default. Claude's independent code review is
complete at `10b0f96`; Codex accepted its catalog/version guard fix through
**`92fb51d`**, the current implementation. Read the
[acceptance and remaining decisions](../research/INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md).
The study remains unfrozen and fitting stays off.

Gemini's v2 design response is now received and reconciled in the
[consolidated study-rule candidate](../research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md).
The eight reported source hashes match its pinned packet. Synthetic checks
show why narrowing the peak window changes the metric, and why catalog
association must not erase a failed prediction at its own horizon. The draft
keeps both questions visible, retains causal cutoffs, proposes null reasons
and concrete five-feature formulas. These are reviewable recommendations,
not frozen code or fitted weights. Current executable labels stay at `92fb51d`.
The original [source packet](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a.txt)
and [manifest](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a_MANIFEST.json)
remain pinned to `941f47a` as evidence of what Gemini reviewed; they do not
contain the v2 draft. Gemini did not inspect the original unamended proposal
as a separate source, so a full original-fidelity claim is still unwarranted.
The full [pre-source conceptual response](../research/reviews/GEMINI_PRE_SOURCE_CONCEPTUAL_REVIEW_20261030.md)
is now archived separately. Its extra suggestions are classified in the triage;
that initial v1 review history is one conceptual response and two source-based
responses; the later v2 design response is recorded above.
It supplies no additional implementation verification or reason to change
the current v2 draft automatically.

Bookmark this page:
<https://github.com/tgpetrie/moonwalking/blob/codex/instant-radar-20261028/docs/ai/RESUME_HERE.md>

The separate fundamentals driver review is complete at `8708c25` on
`codex/fundamentals-driver-review-20261030`. Corrected no-fit readiness and 77
targeted checks pass; discovery and the primary test have not run. The accepted
cohort does not need another Gemini pass. Its 30 exact input files have a
verified GitHub backup. Use the
[fundamentals resume page](https://github.com/tgpetrie/moonwalking/blob/codex/fundamentals-driver-review-20261030/docs/ai/FUNDAMENTALS_RESUME_20261030.md)
for that lane; its readiness does not enable instant-radar fitting.

## Current checkpoint

| Item | Current state |
|---|---|
| Repository | `tgpetrie/moonwalking` |
| Resume branch | `codex/instant-radar-20261028` |
| Current implementation | Offline layer `ab95159` (initial `8211262`); target evaluator unchanged `92fb51d` |
| Instant targets | V1 default preserved; Claude fix accepted; Gemini v2 response reconciled into a study-rule draft; no study freeze |
| Checks | 356 targeted checks pass including 40 offline cases/probes and 265 target cases; formatting, guardrails and 11 historical hashes pass; existing seed-fixture failure remains outside this suite |
| Historical experiment | Complete, locked, inconclusive; do not rerun discovery/validation or tune against it |
| Feed audit | One uninterrupted hour completed; sampled coverage REST-reconciled; thin-product side evidence insufficient, overall gate false |
| Live behavior | No ranking, weights, recorder integration or production deployment change |

The instant radar and developing-move boards were always meant to use their
own targets/formulas, sharing market data with broader outlook scores. The
historical three-input comparison did not evaluate Gemini's F1-F5 proposal.
Current work continues that proposal, with fixed 30s/180s input windows and
separate 5m/15m outcomes.

Read these next:

1. [Agent rules](../../AGENTS.md), [AI index](AI_INDEX.md),
   [handoff](../../HANDOFF.md) and [backlog](../../MW_BACKLOG.md).
2. [Review triage / v2 draft specification](../research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md)
   and [v2 JSON](../research/INSTANT_TARGET_CONTRACT_V2_DRAFT.json); the
   [v1 definition](../research/INSTANT_TARGET_LABELS_20261029.md) and
   [v1 JSON](../research/INSTANT_TARGET_CONTRACT_V1.json) remain available.
3. [Corrected prospective contract](../research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md),
   [execution sequence](../research/INSTANT_RADAR_NEXT_STEPS_20261028.md) and
   [locked historical results](../research/LIVE_MOVERS_RESULTS_20261027.md).
4. [Review assignments](INSTANT_RADAR_REVIEW_BRIEF_20261029.md) and
   [completed audit report](../research/results/feed_audit_20261028_completed/REPORT.json).

## Who owns the next actions

Copy-ready [v2 review prompts and attachments](INSTANT_V2_REVIEW_PROMPTS_20261030.md)
are prepared for Claude, Gemini, local 14B and local 9B. The new Gemini packet
contains eight complete sources at `cc3b6a6` (implementation `8b5b266`), so it
includes v2 rather than the old v1-only packet. Claude has now received the
user's start instruction and full role prompt and completed its code review.
Codex accepted its patch/probes; see the acceptance report. The full packet is
still pinned to the initial v2 source, before the catalog guard fix. Include
the acceptance report/patch as a follow-up addendum. Gemini's v2 response has
now been supplied by the user and reconciled; local v2 dispatch is unverified.

| Owner | Assignment | Verified status |
|---|---|---|
| Codex | Own implementation, reproduce findings, integrate reviewed fixes, maintain this checkpoint | Offline review accepted through `ab95159`; bounded real-data/health adapter verification next |
| Claude | Independent target and offline-pipeline reviews | V2 `10b0f96` and offline `f2cc436` accepted; no new general review pending; study freeze remains conditional |
| Gemini | Compare target choices with the corrected proposal; define supporting/rejecting evidence for F1-F5 | Two v1 source reviews plus a v2 design response received; eight v2 hashes checked; recommendations accepted/qualified in the draft; no empirical study |
| Local 14B | Bounded source/trace review; findings require deterministic verification | One bounded review completed; two suggestions unsupported by code/tests |
| Local 9B | Summarize supplied logs/test failures | No active assignment verified |

On this Windows PC, Codex works in
`C:\Users\tgpet\Projects\Moonwalking-InstantRadar`. Claude's current review
worktree is `C:\Users\tgpet\Projects\Moonwalking-InstantRadarReview`, branch
`claude/instant-offline-review`; its earlier `claude/instant-radar-v2-review`
and `claude/instant-radar-review` branches are preserved. Its original separate checkout is
`C:\Users\tgpet\Projects\Moonwalking-Claude`. These are location hints for
this computer, not required paths on another machine. Preserve other agents'
work and use separate branches/worktrees for fixes.

Next: bounded replay of preserved feed data and verification of real-data health
and paired immutable target-sample adapters. The
draft's formula, matching, stage/model and readiness policies still need
implementation review and freeze before study fitting.
Predeclare how to resolve the remaining
thin-product audit evidence under the existing gate. Recorder/features/live
stage thresholds, model readiness, collection and fitting remain subsequent
steps. Do not repeat completed samples simply to seek a passing verdict.

## Code and environment on another computer

For a new, absent destination directory:

```bash
git clone --branch codex/instant-radar-20261028 https://github.com/tgpetrie/moonwalking.git Moonwalking-InstantRadar
cd Moonwalking-InstantRadar
```

For an existing checkout, inspect remote, status and worktrees, then fetch
and use the named branch in a suitable separate worktree. Never overwrite
uncommitted work. Both checkout and Git common storage must be outside
OneDrive/synced folders. Follow [the access procedures](WORK_FROM_ANYWHERE.md).

Use Python 3.12 and a fresh local virtual environment. The research dependencies
are pinned in [this requirements file](requirements-macbook-research-20261027.txt);
the filename is historical, and the small environment also supports the new
standard-library target evaluator. Activate the environment for your OS, then:

```bash
python -m pip install -r docs/ai/requirements-macbook-research-20261027.txt
python -m pytest -o addopts= -q tests/test_micro_replay_review.py tests/test_micro_replay.py tests/test_instant_diagnostics.py tests/test_instant_targets.py tests/test_instant_targets_v2.py tests/test_instant_targets_v2_review.py tests/test_feed_audit_campaign.py tests/test_coinbase_feed_audit.py tests/test_live_contract.py tests/test_live_movers_run.py tests/test_live_movers_review.py tests/test_restore_macbook_evidence.py backend/tests/test_coinbase_ws.py
bash scripts/validate_mw_guardrails.sh
```

These tests use fixtures; they do not rerun historical discovery/validation.
Native Mac/cloud execution still requires checking the environment there.

## Research evidence stored in GitHub

The existing **draft** release `research-handoff-20261027` now carries two
complementary bundles. Use an authenticated GitHub account with release
access. A source checkout alone does not download release assets.

| Bundle | Contents | Committed manifest |
|---|---|---|
| `moonwalking-live-movers-evidence-20261027.tar.gz` (~112 MB) | Frozen public-market research DB/CSV, historical results and persistent validation-attempt marker, first interrupted audit | [Base manifest](MACBOOK_EVIDENCE_MANIFEST_20261027.json) |
| `moonwalking-instant-evidence-20261029.tar.gz` (~9.55 MB) | Second interrupted audit and completed one-hour campaign, raw WS/REST captures, reports, original hashes and status | [Supplement manifest](INSTANT_EVIDENCE_MANIFEST_20261029.json) |

Download from any authenticated machine into a new `handoff-downloads` folder:

```bash
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --dir handoff-downloads --pattern moonwalking-live-movers-evidence-20261027.tar.gz
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --dir handoff-downloads --pattern moonwalking-instant-evidence-20261029.tar.gz
python scripts/restore_macbook_evidence.py handoff-downloads/moonwalking-live-movers-evidence-20261027.tar.gz
python scripts/restore_macbook_evidence.py handoff-downloads/moonwalking-instant-evidence-20261029.tar.gz --manifest docs/ai/INSTANT_EVIDENCE_MANIFEST_20261029.json
```

The restore tool verifies the exact file list, archive/member hashes, safe
destinations and existing files. It skips identical files and refuses to
overwrite different files. Add `--verify-only` to inspect without restoring.
Default destination is `~/.moonwalking/analysis` on the new machine.

The supplement includes
`feed_audit_campaign_20261028/attempt-01/` and
`feed_audit_20261028_1h/`; use paths under the new machine's analysis directory.
Absolute Windows paths inside original status files describe provenance and
must not be treated as current paths. The base bundle's validation-attempt
marker must remain in place. Do not rerun the locked experiment after restore.

The [upload/verification receipt](INSTANT_GITHUB_TRANSFER_20261029.json)
records cloud asset hashes and round-trip verification. The older
[MacBook handoff](MACBOOK_HANDOFF_20261027.md) describes the base bundle;
its old resume branch and unfinished-audit instructions are superseded by
this checkpoint.

Public-market research is backed up. Live account/portfolio stores, production
credentials, `.env`, virtual environments and AI session folders stay on their
own machines. The Windows collector is a separate running service on port
5003; fetching the research branch does not migrate that service.

## Paste into any next session

> Resume Moonwalking's instant-radar work from repository
> `tgpetrie/moonwalking`, branch `codex/instant-radar-20261028`.
> Read `docs/ai/RESUME_HERE.md` and `docs/ai/ACTIVE_WORK.json`, then follow
> `AGENTS.md`. Verify the current GitHub tip and review status before acting.
> The accepted offline layer is `ab95159`; target evaluator unchanged at `92fb51d`;
> 356 targeted checks passed. Read INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md.
> Read the October 30 Claude acceptance and consolidated study-rule candidate.
> Gemini's v2 response is received/reconciled; this is a draft, not frozen code.
> V1 stays the default. The offline review is accepted; verify real-data and
> immutable sample adapters, and freeze event association/exposure and
> remaining study rules before fitting; no physical onset is inferred yet.
> Restore the documented GitHub evidence if needed. Historical validation
> is locked; the feed gate is still inconclusive. Keep live scoring and
> production unchanged. Update the portable checkpoint, commit and push
> completed work before handing off.

For a conversation without repository access, supply this page, the active-work
JSON, target definition and historical results as files or text.

## Keep this record current

At each coherent handoff, the implementation owner updates this page and
`ACTIVE_WORK.json` with the code checkpoint, evidence location, completed
checks, agent-review status, open gates and exact next action, then pushes.
Keep a new active-branch pointer here when work moves to another branch.
Documentation-only commits may follow the recorded implementation hash;
the branch's Git history gives the exact latest documentation checkpoint.
This page reconstructs the task without relying on a particular chat history.
