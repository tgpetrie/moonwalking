# Claude independent review of the offline book and publication clocks — 2026-11-04

Assignment: [CLAUDE_CLOUD_BOOK_REVIEW_20261104.md](../../ai/CLAUDE_CLOUD_BOOK_REVIEW_20261104.md).
Cloud session, own branch `claude/instant-book-publication-review-20261104`.
**Pending Codex review; not merged.** Codex's `codex/instant-radar-20261028` is still authoritative.

- **Inspected:** tip `3ad47b362a0255f09d3eeb5a322143517df10672`. It contains checkpoint `7671e58`.
- **Unchanged since `8c51878`:** `instant_book.py` `d5ee7119…`, `instant_publication.py` `db1c7ede…`,
  `tests/test_instant_book.py` `375ead28…`, the book contract `104aaa3e…` and the publication contract `884da206…`.
  All five match Codex's `instant_book_publication_20261103/CHECKS.json`.
- **Dependency only:** `instant_coverage.py` `e3299f59…` was read but not changed.
- **Probes:** `tests/test_instant_book_review.py`, 58 cases.
- **Checks record:** [CHECKS.json](../results/claude_book_publication_review_20261104/CHECKS.json).

Not covered here: the reconciliation `bfab9c8` (Codex owns it), association/exposure, and any monitor code or contract
change. There was no capture, real-data run, fit, target change or live work. Synthetic probes show engineering behaviour,
not predictive value.

**Verdict.** The book and pressure arithmetic, atomic batches, lifecycle recovery, TTL boundaries and the publication
chronology all hold under independent hand calculation. Two book defects were reproduced on the pinned code. Both are
fixed in `instant_book.py` with 9 changed lines. The publication module has no defect.

## Confirmed defects (each failed on unmodified `3ad47b3`; fixed)

**B1 — medium. The view used a heartbeat before the book had finished processing it** (`BookReplay.view`, `ingest`).
`CoverageMonitor.ingest` stamps its transport record with the monitor's own completion time. `BookReplay` keeps
processing that same envelope and stamps its own consequences later, at book completion. A heartbeat-gap invalidation is
one of them. `view` filtered transport by the monitor's time and book state by the book's time. For an as-of in between,
the gap heartbeat proved a book "fresh" that the same packet invalidates.

* Reproduction: `live()` leaves heartbeat 1500 and snapshot 600. A heartbeat then arrives at 9600, a gap of 8100ms.
  Its clocks are monitor start 9600, monitor done 10000 and book done 10500. Then `view(10000)` is called.
* Expected: unavailable. The latest fully processed heartbeat, 1500, is stale, and the 9600 packet requires a snapshot.
  Actual: `book_state_available=True`, `reason=None`, quote `100.5/101 3/1`, observation age 9400ms.
* Without that heartbeat, the same view is `stale_heartbeat`. An unprocessed packet raised the view to usable, which
  breaks "processing completion measured after book construction".
* The same root cause also acts in the fail-closed direction. A `connection_closed` with book completion at 7000 already
  vetoed `view(5000)` at 4001, as `heartbeat_unavailable`.
* Fix: record each packet's book completion by `receipt_seq` (`self.completed`). A transport record now counts only once
  both the monitor and the book have finished with its packet, so one packet has one knowledge time. Monitor records,
  code and contract are untouched.
* Probes: `test_gap_heartbeat_cannot_freshen_a_book_before_its_invalidation_is_known` and
  `test_one_packet_has_one_knowledge_time_for_transport_and_book`.
* Controls: `test_control_without_the_gap_heartbeat_the_view_is_stale`,
  `test_control_ordinary_heartbeat_is_still_usable_while_the_next_one_is_in_flight` and
  `test_late_failure_is_visible_only_after_processing_and_never_rewrites_earlier`.
* Likelihood: the default clock is milliseconds. The window opens only when book completion falls in a later millisecond
  than monitor completion, and the as-of falls inside that window. Rare on replay, but it is a false pass.

**B2 — low. A size change that only altered the text moved the BBO clock** (`BookReplay._consume`).
`book_change` compares `Decimal` levels, but `bbo_change` compared the string tuple returned by `_best`. `"3"` → `"3.00"`,
or deleting `"100.5"` and re-adding `"100.50"`, changed no price or quantity. It still moved `bbo_change_ts_ms` to 1600
while `book_change_ts_ms` stayed at 600. That is an impossible state, since a BBO change implies a book change, and it
breaks "only an actual level/BBO change moves the corresponding change clock".

* Fix: compare the BBO as `Decimal` amounts. The displayed strings still show the latest spelling.
* Probes: `test_numerically_identical_bbo_does_not_move_change_clocks` (two cases).
* Control: `test_control_real_bbo_size_change_moves_both_clocks`.

Pre-patch run: these 4 probe cases failed and the other 54 passed. Post-patch: all 58 pass, and so do Codex's
54 original book/publication cases, unchanged.

## Verified without defect

1. **Oracles** (hand-calculated mid and `(bid_size−ask_size)/(bid_size+ask_size)`):
   * Absolute replacement: 5 → 2, not 7.
   * Zero deletion, and the next level surfacing after a deletion.
   * Three repeated changes at one price, last change wins: pressure 7/11.
   * Deep-level updates change the book clock but not the BBO clock.
   * A transient cross removed within the same batch is an observation only.
   * Final locked and final crossed books, at the top or deeper, are invalid. An exhausted side is invalid.
   * Deleting an absent level is an observation only.
2. **Sessions:**
   * An ack covering only product A leaves product B unconfirmed.
   * An invalid batch on one product does not affect another.
   * An ack carrying `level2` but no `level2_batch` does not confirm the book.
   * REST/`rest_recovery` snapshots carrying another `connection_id`, and ws tickers, change nothing.
   * `queue_overflow`, `error` and `audit_*` invalidate every product. Each then needs a fresh ack and then a snapshot.
   * The heartbeat gap is strictly greater than 5000ms: 6500 is allowed and 6501 invalidates.
   * A same-millisecond heartbeat fails closed until the next beat.
3. **Clocks:**
   * A receipt at 4999 is included at cutoff 5000. A receipt at 5000 is excluded, even at a later as-of.
   * Heartbeat freshness is exactly 5000ms. The observation TTL is exactly 10000ms, and heartbeats never renew it.
   * A late failure appears only at its completion and does not rewrite earlier as-of views.
   * A queued packet leaves the older processed quote visible, as documented; that is not a completeness certificate.
   * A regressing or non-integer book clock fails the artifact, and queries are then refused.
   * Queries require a grid cutoff and an integer as-of no earlier than the cutoff.
   * Results are frozen, and their hashes match the LF-normalised sources.
4. **Publication:**
   * Hand-calculated ages are 150/40/80ms. Equal neighbouring clocks are allowed.
   * Age bounds are exact: 149, 150 and 0. A bound never enables fitting.
   * Inputs at the cutoff with a late publication still flag the amendment.
   * Non-string IDs, float or negative clocks, and every order violation are rejected.
   * Arguments are keyword-only, results are frozen, and the source hash is correct.
   * The cutoff and publication anchors stay distinct. No lag policy is frozen.
5. **Offline:** a clean `-I` interpreter imports both modules without `socket`, `ssl`, `http`, `urllib.request`,
   `requests`, `websocket(s)`, `aiohttp` or backend modules. The level and TTL constants are unchanged.

## Design proposals (not implemented, not defects)

* **P1 — retrospective gap.** A heartbeat gap that ends after a cutoff is not applied backwards to that cutoff, even at
  a later as-of. That is consistent with the contract. A later grading policy should decide whether later-known gap
  evidence vetoes an earlier sample.
* **P2 — first beat after a snapshot.** The gap timer starts at the first heartbeat, not at the ack or snapshot. A long
  silence between snapshot and first heartbeat is caught only by `heartbeat_unavailable` and the 10s TTL. Consider
  starting the gap clock at the ack.
* **P3 — in-flight count.** `view` could report how many receipts before the cutoff were still unprocessed at the as-of.
  That would let queue diagnostics avoid treating an older quote as complete.
* **P4 — contract wording.** The contract's `recovery` text lists queue loss under "new snapshot". The implementation and
  the Markdown both also require a fresh ack, which is stricter. Clarify the text; the behaviour was not changed.
* **P5 — absent-level deletes.** Deleting an absent level is tolerated. It may signal a desynchronised book, so consider
  counting it as a diagnostic.

## Limitations and unverified concerns

* **Connection identity.** The recorder writes a constant `connection_id=1`. Real reconnect identity and multi-socket
  routing are not implemented upstream, and nothing here claims them.
* **Real-data frequency of B1.** It was not measured, because no real `level2_batch` capture exists.
* **Out of scope.** `Sample` integration, the continuous F3 integral and throughput are documented limitations, not
  defects.

## Checks

* **Runtime:** cloud Linux, Python 3.12.3. Pinned 3.12.10 was unavailable, so this is the closest 3.12. pytest 8.3.5,
  Black 24.8.0.
* **Targeted suite: 579 passed.** That is Codex's 521-test command from the association acceptance plus these 58 probes.
* Black 24.8.0 is clean on all four book/publication files. Repository guardrails pass.
* All 11 historical hashes in `live_movers_contract_20261027/SHA256SUMS.json` match.
* **Protected files:** `git diff 3ad47b3` touches only `instant_book.py`. This covers the targets and V1/V2,
  diagnostics, monitor, samples, association, recorder, verifier, `docs/research/results`, backend and frontend, and all
  the contracts. V1 stays the default, and the held `d711832` stays unmerged.
* Not run: the full test folder, native Windows/Mac, and anything with real data.
