# Bounded review: inventory and processing-time evidence

Prepared, not dispatched. Earlier directional, association, book and
reconciliation reviews are complete; do not repeat them.

> Fetch `tgpetrie/moonwalking`, verify the current tip of
> `origin/codex/instant-radar-20261028`, and read AGENTS.md, HANDOFF.md,
> docs/ai/RESUME_HERE.md and docs/ai/ACTIVE_WORK.json. New implementation is
> `8607a36`; documentation-only checkpoints may follow it.
>
> Use your own new branch/worktree:
> `claude/instant-input-evidence-review-20261104`. Review only
> scripts/scoring_experiment/instant_input_evidence.py,
> docs/research/INSTANT_INPUT_EVIDENCE_CONTRACT_V1_DRAFT.json,
> docs/research/INSTANT_INPUT_EVIDENCE_20261104.md and
> tests/test_instant_input_evidence.py. BookReplay/CoverageMonitor and the
> directional reporter are read-only dependencies, already reviewed.
>
> Independently test complete product × cutoff × direction accounting,
> missing products, canonical inventory/hash versus actual declaration time,
> actual payload completion versus receipt/book-only completion, first-receipt
> deduplication, unknown maker sides, connection/continuity epochs at a shared
> millisecond, and verified zeros versus unknown counts. Test late merged
> proofs without backdating, cached cohort immutability, benchmark missingness,
> stale quotes, clock/sequence/cap failures and synthetic CLI outputs.
>
> Verify the scope honestly: positive eligibility, baseline/feature evidence,
> continuous quote health, durable publication and full-feed certification
> remain unsupported. An empty tape can account for every planned row but
> cannot prove a healthy capture. Completeness is relative to the supplied
> plan, not an independently authenticated exchange universe. No existing
> directional-report or target semantics may be silently strengthened.
>
> For defects, write counterexamples and run on the unmodified implementation
> first. Keep minimal fixes and probes on your own branch. Separate defects
> from future policy/feature work. Run the current targeted set, Black 24.8.0,
> guardrails, 11 historical hashes and protected-source checks; report actual
> runtime and any missing checks. Commit/push your review report, probes and
> minimal fixes, leaving Codex's checkpoint files alone.
>
> No new capture, real-data outcome study, fit, historical validation rerun,
> cap/threshold tuning, source pilot, live scoring or production change. No
> scheduled checks or second session sharing this branch. Return one completed
> review with branch, commit, check results, pre-patch evidence and limitations.
