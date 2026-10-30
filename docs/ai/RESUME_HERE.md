# Resume Moonwalking from anywhere

Updated October 30, 2026 (Pacific). This page is the current portable
checkpoint for the **instant radar scoring work**. GitHub holds the code,
contracts, completed results, work status and downloadable research evidence.
The [active-work record](ACTIVE_WORK.json) supplies the branch, implementation
commit, owners, gates and next actions in machine-readable form.

October 30 update: Gemini's first response could not inspect the repository
and is a conceptual review only. A complete, hash-verified
[single-file source attachment](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a.txt)
now contains the five requested files exactly as committed at `941f47a`.
Download it and upload it directly to Gemini with the existing review prompt;
repository search/index access is unnecessary. Its
[export manifest](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a_MANIFEST.json)
identifies each source blob and byte range. Await a source-based replacement
review before treating any claim as an implementation finding.

Bookmark this page:
<https://github.com/tgpetrie/moonwalking/blob/codex/instant-radar-20261028/docs/ai/RESUME_HERE.md>

## Current checkpoint

| Item | Current state |
|---|---|
| Repository | `tgpetrie/moonwalking` |
| Resume branch | `codex/instant-radar-20261028` |
| Implementation / Claude review commit | `cb7034a` |
| Instant targets | Executable forward/onset labels, event catalog and retrospective alert timing implemented; independent review pending |
| Checks | 104 targeted tests passed at the implementation checkpoint; guardrails, links and 11 frozen historical hashes passed |
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
2. [Executable target definition](../research/INSTANT_TARGET_LABELS_20261029.md)
   and [JSON contract](../research/INSTANT_TARGET_CONTRACT_V1.json).
3. [Corrected prospective contract](../research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md),
   [execution sequence](../research/INSTANT_RADAR_NEXT_STEPS_20261028.md) and
   [locked historical results](../research/LIVE_MOVERS_RESULTS_20261027.md).
4. [Review assignments](INSTANT_RADAR_REVIEW_BRIEF_20261029.md) and
   [completed audit report](../research/results/feed_audit_20261028_completed/REPORT.json).

## Who owns the next actions

| Owner | Assignment | Verified status |
|---|---|---|
| Codex | Own implementation, reproduce findings, integrate reviewed fixes, maintain this checkpoint | Implementation pushed; awaiting independent review |
| Claude | Review target contract/code/tests for leakage, label errors and missing counterexamples | Separate review worktree observed at `cb7034a`; completion not verified |
| Gemini | Compare explicit onset choices with original design; define supporting/rejecting evidence for F1-F5 | Review brief prepared; delivery/completion not verified |
| Local 14B | Bounded source/trace review; findings require deterministic verification | One bounded review completed; two suggestions unsupported by code/tests |
| Local 9B | Summarize supplied logs/test failures | No active assignment verified |

On this Windows PC, Codex works in
`C:\Users\tgpet\Projects\Moonwalking-InstantRadar`. Claude's current review
worktree is `C:\Users\tgpet\Projects\Moonwalking-InstantRadarReview`, branch
`claude/instant-radar-review`; its original separate checkout is
`C:\Users\tgpet\Projects\Moonwalking-Claude`. These are location hints for
this computer, not required paths on another machine. Preserve other agents'
work and use separate branches/worktrees for fixes.

Next: obtain independent reviews and reproduce concrete findings before
changing the label definition. Then predeclare how to resolve the remaining
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
python -m pytest -o addopts= -q tests/test_instant_targets.py tests/test_feed_audit_campaign.py tests/test_coinbase_feed_audit.py tests/test_live_contract.py tests/test_live_movers_run.py tests/test_live_movers_review.py tests/test_restore_macbook_evidence.py backend/tests/test_coinbase_ws.py
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
> The implementation checkpoint is `cb7034a`; 104 targeted tests passed.
> Continue independent target/code review and resolve concrete findings.
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
