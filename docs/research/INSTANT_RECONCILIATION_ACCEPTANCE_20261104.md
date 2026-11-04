# Bounded reconciliation accepted with continuity barriers

November 4, 2026 (Pacific). Codex verified the pushed
`claude/instant-coverage-reconciliation` tip `1af0a64`, reviewed the three
commits separately and integrated them on `codex/instant-radar-20261028`:

| Source | Integrated as | Contribution |
|---|---|---|
| `bfab9c8` | `a82f182` | Bounded merged reconciliation and draft amendment |
| `d26c57d` | `d80418e` | Per-product continuity epochs and barrier tests |
| `1af0a64` | `055d590` | Second 30-case barrier probe set |

The original [boundary blocker](RECONCILIATION_BOUNDARY_REVIEW_20261104.md)
is resolved. In isolated temporary source trees, Codex reproduced **26 failures
and four passing controls** from the second probe set on unmodified `bfab9c8`;
all **30 pass** on `1af0a64`. This includes the original same-millisecond audit
reset counterexample. The local Claude worktree was inspected read-only and
left untouched. The user reported two Claude sessions writing the review
branch; the commits were reviewed individually, with no force push or copying
of active worktree files.

## Accepted behavior

The first check remains exact receipt-interval trade-ID equality. Only the
two ordering-failure classes can be reconciled, within **four proofs,
10,000ms and 100,000 IDs**. Original failures remain on record; a later
merged proof supersedes them only once its computation has completed.

Each product has a continuity epoch. Connection changes, audit/transport/
queue failures and lost or re-added required subscriptions advance it in
receipt-sequence order. Merging, assessment chaining and interval trade
counts cannot cross an epoch, including at one shared millisecond with a
reused connection ID. Healthy repeated acknowledgements preserve continuity;
valid intervals and races on either side of a barrier remain usable separately.
Trades keep their first receipt and are never shifted into another bucket.

Merges are deliberately disjoint. A nested race around an already merged
pair can still cause a false veto. The caps were chosen after observing one
hour's coverage, without outcome analysis; they remain engineering limits
in a draft amendment. Neither those caps nor this review freeze the study.

## Verification

**1,064 targeted tests pass** on Windows, Python 3.12.10 and pytest 8.3.5.
This includes all `tests/test_instant_*`, both newer book test files,
association/publication, micro/preserved replay, feed audit, live contract/
movers, evidence restore and `backend/tests/test_coinbase_ws.py`. Black
24.8.0 passes for the five changed Python files, guardrails pass and all
11 locked historical artifact hashes match. Targets/V1/V2, diagnostics,
recorder/baseline, book/publication, backend and frontend are unchanged from
`010031c`. No full-suite or native Mac execution is claimed.

Read [the check record](results/instant_reconciliation_acceptance_20261104/CHECKS.json)
and [the preserved-hour ID check](results/instant_reconciliation_acceptance_20261104/PRESERVED_ID_CHECK.json).
Codex independently compared the accepted strict monitor `652f5af` with the
amended monitor on the unchanged, already backed-up gzip:

- 63,258 packets and 24,424 unique matches retain identical first receipts.
- All 14,396 raw proofs match, apart from actual processing availability and
  the added continuity epoch. The 33 strict failures remain recorded.
- 16 merged proofs reconcile those 33 failures; none remains unreconciled.
  The largest merge uses three proofs and spans 2,990ms.
- Across the 16 merges, the earliest repaired interval waits an additional
  median **965.5ms**, maximum **1,993ms**, measured between receipt boundaries.
  This is not a measurement of live processing or publication latency.

Only ID/receipt quality was evaluated. No return label, outcome, fit or new
capture was run. The earlier 41.4%/3.0% clean-anchor and busy-tape comparisons
remain Claude's attributed descriptive results, not a newly verified study.
Original source and historical result artifacts are unchanged; the new small
check summaries and synthetic tests are in Git, with no new PC-only evidence
needed for handoff.

## Remaining gates and next work

The monitor still does not certify full-feed or quote health and is not wired
into target `Sample` eligibility. Keep inputs immutable at their cutoff;
later grading evidence, per-row processing clocks, actual connection identity,
streaming/persistence bounds and durable publication require versioned adapters.
Define per-direction eligibility/gradation before board-specific exposure,
then finish publication-entry, feature-age, F1-F5, stage/model and readiness
rules before freezing the prospective study. Both completed cloud assignments
stay closed; any further agent work needs a distinct branch and bounded scope.

V1 stays default. Whole-window strict timing and its separate forward-peak
diagnostic remain unchanged; physical onset remains undefined. The original
feed gate is inconclusive, >=62 complete warmup minutes are still required,
historical validation is locked, and fitting and live scoring remain unchanged.
