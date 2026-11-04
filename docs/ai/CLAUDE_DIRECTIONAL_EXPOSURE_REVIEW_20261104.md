# One bounded independent review: directional exposure

Prepared for the user to dispatch to one Claude session. Not sent by Codex.
The older association and reconciliation assignments are complete and accepted.
New implementation to review: **`9da4987`**, with 48 new cases and 1,112
combined targeted tests passing in Windows. Documentation-only commits may
follow it; check the active-work record before starting.

Copy this task:

> Fetch `tgpetrie/moonwalking` and verify the current tip of
> `origin/codex/instant-radar-20261028`. Read AGENTS.md,
> docs/ai/RESUME_HERE.md, docs/ai/ACTIVE_WORK.json and HANDOFF.md.
> Use your own new branch/worktree,
> `claude/instant-directional-exposure-review-20261104`, from that tip.
> Never write to another session's active branch or worktree.
>
> Review only the new opt-in directional report:
> scripts/scoring_experiment/instant_directional_exposure.py,
> docs/research/INSTANT_DIRECTIONAL_EXPOSURE_CONTRACT_V1_DRAFT.json,
> docs/research/INSTANT_DIRECTIONAL_EXPOSURE_20261104.md and
> tests/test_instant_directional_exposure.py. Use instant_association.py and
> its existing contract/tests as read-only dependency references.
>
> Check that a missing opposite-direction outcome cannot remove a valid
> board row; eligible exposure never depends on future labels; mature ready
> failures remain gradable; each horizon is separate; and unavailable labels
> never become negatives. Independently hand-check product-hours versus
> per-board/either-board time unions and ranker complete-row intersections.
> Check same-universe paired board records, duplicate rejection, clock types
> and boundaries, malformed flags, empty inputs and mixed label provenance.
> Verify the old joint reporter, greedy association, targets, monitor, book,
> publication and source contracts remain unchanged.
>
> Important limitation: these eligibility flags and availability times are
> caller assertions. Reject claims that this reporter produces authenticated
> eligibility or proves the intended universe is complete. That evidence
> producer remains future work. Review the limitation explicitly rather than
> implementing an unapproved feed bridge.
>
> For any defect, write a minimal counterexample and run it on the unmodified
> pushed implementation first. Keep narrow fixes/probes on your own branch.
> Separate defects from study-policy suggestions. Run the directional and
> association tests, then the repository's current targeted set, Black 24.8.0,
> guardrails, protected-source and 11 historical-hash checks. Use pinned Python
> 3.12 if available; report actual runtime and any unavailable checks.
>
> No new capture, market outcome analysis, fitting, historical validation rerun,
> cap/threshold tuning, live scoring or production changes. Do not alter the
> authoritative Codex checkpoint files on your review branch. Commit and push
> the report, probes and any minimal fix. Return branch, commit, checks,
> pre-patch evidence and remaining limitations. One completed review only;
> no scheduled checks or duplicate session on this branch.
