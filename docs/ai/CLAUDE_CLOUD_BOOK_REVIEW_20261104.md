# Completed cloud task: independent book and publication review

Completed: `6abd95e` independently verified and accepted as `5ff6a8f`, with
579 targeted checks passing. The assignment below is historical; do not
redispatch it. See `docs/research/INSTANT_BOOK_REVIEW_ACCEPTANCE_20261104.md`.
The previous cloud association assignment is complete and accepted. This is
new code-review work, aimed at shipping useful fixes before the user's cloud
credit expires tonight. No dollar or completion-time estimate is assumed.

Start a fresh Claude Code **cloud** session with `tgpetrie/moonwalking` and
base branch `codex/instant-radar-20261028`. Fable is appropriate if available.
Use a fresh context to avoid repeatedly loading the completed association
implementation conversation. Paste the following assignment.

## Assignment

Independently review Codex's offline order-book and publication-clock code.
The repository is `tgpetrie/moonwalking`; fetch and inspect the actual tip of
`codex/instant-radar-20261028`. It must contain checkpoint `7671e58`.
Read `AGENTS.md`, the resume/active-work records and required project docs.
Record the exact inspected commit and source hashes. Create your own branch,
for example `claude/instant-book-publication-review-20261104` or the cloud
platform's required unique variant. Never commit or push to Codex's branch.

The implementation to inspect was introduced at `8c51878`:

- `scripts/scoring_experiment/instant_book.py`
- `scripts/scoring_experiment/instant_publication.py`
- `tests/test_instant_book.py`
- `docs/research/INSTANT_BOOK_CONTRACT_V1_DRAFT.json`
- `docs/research/INSTANT_PUBLICATION_CONTRACT_V1_DRAFT.json`
- `docs/research/INSTANT_BOOK_AND_PUBLICATION_20261103.md`

Read `instant_coverage.py` and its contract only as dependencies. Codex owns
the separate reconciliation review of local Claude's `bfab9c8`; do not repeat
that work, implement reconciliation, or change monitor code/contracts.
Cloud association/exposure `96f5652` is already accepted through `8631231`.
Do not repeat that implementation or its review.

Deliver one bounded adversarial review with executable counterexamples and
small fixes only for reproduced violations of the stated contracts. Cover:

1. Independent hand-calculated book/pressure oracles: absolute quantity
   replacement, zero deletion, repeated levels, atomic batches, final versus
   transient crossing, deep-level updates and stale/missing/invalid sides.
2. Session/acknowledgement isolation, same-millisecond boundaries, ignored
   REST/ticker inputs, recorder `audit_*` markers, queue failures, heartbeat
   gaps, snapshot recovery and failed-artifact behavior. Real connection IDs
   and multi-socket routing are not implemented upstream; do not claim them.
3. Receipt versus processing completion, actual observation/change clocks,
   no heartbeat freshness renewal, exact 10s TTL, and explicit historical
   as-of queries. Late inputs/failures must not rewrite earlier knowledge.
   A last fully processed quote is not a queue/completeness certificate.
4. Chronology `feature_cutoff <= inputs_available <= decision_completed <=
   published`, exact age bounds, immutable results, malformed metadata,
   provenance and the distinction between cutoff and proposed publication
   target anchors. No numerical lag policy is frozen. Caller clocks are
   assertions, not authenticated durable publication.
5. Imports and dependencies must remain offline. No existing target behavior,
   source contract, historical artifact or live service may silently change.
   Scope unsupported Sample integration, continuous F3 and throughput as
   documented limitations; do not call a missing unpromised feature a defect.

Use new paths such as `tests/test_instant_book_review.py` and
`docs/research/reviews/CLAUDE_BOOK_PUBLICATION_REVIEW_20261104.md` with a compact
checks record. If a defect is found, first demonstrate it on the pinned
unmodified code, then patch only the book/publication module as necessary and
verify the fix and controls. Separate confirmed defects from design proposals
and unverified concerns. Do not expand into a refactor or general repository
audit. One complete review pass and its fixes is the deliverable.

Use Python 3.12 and pytest 8.3.5 if available; otherwise report the actual
runtime and limitation. Run meaningful probes, existing book/publication
and relevant monitor/target tests, Black 24.8.0 and guardrails. Verify all 11
historical hashes and protected files against your pinned starting commit.
Do not repeat broad tests after they pass unless a new edit/failure warrants it.

No new market capture, historical discovery/validation, scoring fit, external
data download, target formula/contract changes, live integration, deployment
or auto-merge. Synthetic tests establish engineering behavior, not predictive
value. Preserve V1 default and held original `d711832`.

Commit/push the review, probes and any reproduced fixes to your own branch.
Maintain its branch-specific handoff under `AGENTS.md`, retaining the pointer
to the authoritative Codex branch and marking the contribution pending review.
Return the branch, commit, findings, test results, runtime and dirty files.
Codex will independently verify before integration.

## Use of any remaining credit

After this deliverable is pushed, Codex can supply a small implementation task
for a remaining confirmed blocker, based on actual review results. Finish the
current task before launching another overlapping one. Do not use expiring
credit to rerun locked outcomes, tune thresholds, or repeatedly review unchanged
code. Every task should leave a pushed, reviewable artifact before expiry.
