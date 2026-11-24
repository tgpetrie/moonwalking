# Coverage review accepted; reconciliation remains a separate amendment

November 3, 2026 (Pacific). Codex inspected Claude's pushed review commit
`91f304380c0e5d1d8595eb564fb0df0da5fda690`, independently reproduced its five
failing C1-C3 cases on the unmodified monitor, and retained four passing
controls. After preserving its own book/publication work at `8c51878`, Codex
cherry-picked the three-file review contribution as **`652f5af`**. Claude's
worktree is untouched. The original separately held `d711832` was not merged.

Read [Claude's report](reviews/CLAUDE_INSTANT_COVERAGE_REVIEW_20261103.md),
the [independent raw-ID reproduction](results/instant_book_publication_20261103/COVERAGE_REVIEW_REPRODUCTION.json)
and [current checks](results/instant_book_publication_20261103/CHECKS.json).

## Accepted defects

- The recorder's `audit_*` parse/transport failure markers now invalidate
  transport, clear heartbeat continuity and require a new acknowledgement.
- Touching proof timestamps cannot bridge differing connection identities or
  discontinuous trade-ID watermarks. Each session's own interval remains usable.
- A trade received on an old connection cannot satisfy a new connection's
  interval, including at a shared receipt millisecond.

All nine independent review probes pass after integration. The new offline
book/publication code adds 54 cases; the combined targeted suite passes
**468 tests**. Black 24.8.0, repository guardrails, 11 historical artifact hashes
and unchanged target/evaluator/recorder checks are also required at this
checkpoint. No full-suite, native Mac or cloud execution claim is made.
The book/publication implementation has not had an independent code review.

## Independent real-data checks

Codex read the same pinned gzip without changing it. Its SHA-256 remains
`4b4a56ecf9e65a5c36d70a28be726f39dd67e6523c26c92bf16aa671bc8ea97b`.
The 63,258 envelopes contain 24,424 unique live matches. Comparing the old and
patched monitor yields identical 14,396 raw proof records apart from actual
processing availability times. There are 33 strict failures: 29 BTC and four
SOL, grouped into 13 BTC and two SOL adjacent runs. All 15 runs satisfy exact
merged receipt-interval ID equality. All expected IDs within each product's
first/last heartbeat range were eventually received. No price, return or
outcome label was analysed, and no new capture was launched.

This independently supports the reordering diagnosis. It does not certify
exchange-event completeness, timely arrival or the full pipeline. Claude's
41.4%/3.0% counterfactual clean-label shares and busy-tape median counts were
not independently recomputed here; they remain attributed descriptive
analysis of one hour. The reported merged 100% is only removal of those ID
vetoes, not total study eligibility, freshness or predictive performance.

## Reconciliation decision and remaining integration gates

Codex recommends **bounded merged reconciliation**, with unchanged strict
results retained as diagnostics. The user's later screenshot verifies its
explicit assignment to local Claude on `claude/instant-coverage-reconciliation`.
That implementation/push is pending; the current Codex strict contract is unchanged.

Before adoption, pin a separately versioned contract and engineering limits
on elapsed time, interval count, ID span and retained state. Require exact
set equality on a continuous connection/watermark chain. Only repair the two
ordering-failure classes; never merge heartbeat gaps, regressions, conflicts,
missing subscriptions, audit failures or connection boundaries. Preserve
receipt-attributed counts and actual reconciliation-completion availability.
Test true losses, cap exhaustion and late evidence before a fresh pilot. Do
not choose a cap merely because the longest observed run in this hour was four.

Keep the other review items explicit:

| Item | Current disposition |
|---|---|
| Late negative evidence for outcomes | Proposed grading policy: keep original decision inputs immutable; later bad-feed evidence known by grading time can make the outcome unavailable. The legacy Sample discards that evidence, so a versioned grading/evidence adapter is still needed. No target was silently changed. |
| Per-row processing | New book states measure completion after construction. Legacy ReplayStore quotes/trades still lack per-row processing timestamps; the paired adapter does not strengthen that trust. A new recorder/publication path must preserve those clocks. |
| Packet budget | The 100,000-packet cap remains an offline guard, not a verified one-hour book profile. Version and test persistence/rotation and volume before collection; no automatic cap increase is accepted here. |
| Connection IDs | The audit writer's hard-coded ID is only sufficient for the preserved single connection. A new writer needs real connection epochs and failure evidence. |
| Multiple active connections | The current monitor resets globally on connection changes. Interleaved sockets require a separate tested per-connection router; none is claimed here. |

The event-association/exposure cloud assignment is prepared separately; its
execution/review and the overall study freeze remain pending. Source quality,
publication timing/entry-price rules, >=62 complete warmup minutes, feature/
stage/model/readiness freeze and 14 valid shadow days remain required. V1 stays
default, physical onset remains undefined, historical validation stays locked,
and fitting/live integration remain off.
