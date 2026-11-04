# Book/publication review accepted — November 4, 2026

Codex reviewed cloud commit `6abd95e` and independently reproduced its four
failing defect cases with 54 passing controls on the unchanged source. The
implementation/review was cherry-picked as **`5ff6a8f`**. The cloud's separate
handoff commit `b95df55` was not merged over the authoritative Codex records.

Accepted corrections are limited to `instant_book.py`:

- Book views now use each packet's book-processing completion before trusting
  its transport state. A gap heartbeat cannot freshen a stale book during the
  interval between monitor completion and book invalidation. A late failure
  likewise becomes visible consistently at the book's completion.
- BBO change detection compares Decimal amounts, so text-only differences
  such as `3` and `3.00` no longer move the BBO change clock.

The publication module had no confirmed defect in this review and remains
unchanged. Targets/V1/V2, monitor, contracts, recorder/baseline, historical
artifacts and production code are unchanged. The new book source hash identifies
the correction; older prototype reports retain their original provenance.

**579 targeted tests pass** on Windows Python 3.12.10 / pytest 8.3.5: the prior
521 plus 58 independent probes. The cloud report's Linux Python 3.12.3 runtime
is preserved as its own evidence. Neither run is a native Mac or full-suite
pass. Black 24.8.0, repository guardrails and all 11 historical hashes pass.
See [Claude's original report](reviews/CLAUDE_BOOK_PUBLICATION_REVIEW_20261104.md)
and [Codex's acceptance record](results/instant_book_review_acceptance_20261104/CHECKS.json).

The five design suggestions remain separate: later grading vetoes, first-
heartbeat clock policy, in-flight diagnostics, recovery wording and absent-
level deletion counters. They are not adopted as silent behavioral changes.
The current source is offline, has no legacy target-sample bridge, and does
not certify continuous F3, durable publication, queue completeness or throughput.

Local reconciliation `bfab9c8` remains unmerged because the independently
reproduced [same-millisecond boundary failure](RECONCILIATION_BOUNDARY_REVIEW_20261104.md)
still requires correction. No new capture, real-data run, scoring fit,
historical outcome rerun, physical-onset claim or live change occurred.
