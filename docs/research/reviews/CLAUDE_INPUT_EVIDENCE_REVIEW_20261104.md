# Claude independent review of input-evidence stage 1 — 2026-11-04

Assignment: [CLAUDE_INPUT_EVIDENCE_REVIEW_20261104.md](../../ai/CLAUDE_INPUT_EVIDENCE_REVIEW_20261104.md).
Cloud session, own branch `claude/instant-input-evidence-review-20261104`. **Pending Codex review; not merged.**
`codex/instant-radar-20261028` remains authoritative; its checkpoint files are untouched on this branch.

- **Inspected tip:** `fee55a7dd2bbb32c661c531d6fe9a8432db9400d`, documentation-only on top of implementation `8607a36`.
- **Reviewed, byte-identical to Codex's `instant_input_evidence_20261104/CHECKS.json`:** `instant_input_evidence.py` `f507998c…`,
  its contract `beb5492f…`, `tests/test_instant_input_evidence.py` `240ef221…`.
- **Read-only dependencies, unchanged since their accepted reviews:** `instant_book.py` `c06834d7…`, `instant_coverage.py` `0682e134…`,
  `instant_directional_exposure.py` `638db051…`.
- **Probes:** `tests/test_instant_input_evidence_review.py`, 46 cases, with an independent tape helper that sets watermarks,
  connections and the five-step per-packet processing clock explicitly.
- **Checks record:** [CHECKS.json](../results/claude_input_evidence_review_20261104/CHECKS.json).

**Verdict: no defect found.** All 46 probes pass on the unmodified pushed implementation, so there is no patch and the pre-patch
evidence is that clean run. Ten deliberate mutants were run against the probes: eight are killed, and the two survivors are
equivalent mutants explained by an ordering invariant the probes pin (below). The scope statements in the contract and the
Markdown are accurate and are now executable facts rather than prose.

## Verified

1. **Inventory.** Rows are exactly products × every 5 s cutoff in `[first, stop)` × both directions; the inventory hash is
   independent of product order. A planned product with no packets keeps both rows with explicit `coin:quote:` and
   `coin:trades:` reasons, and its benchmark component is still evaluated. The row cap is inclusive at 10,000; 10,004 is
   rejected, as are a first cutoff below 30 s, off-grid or inverted ranges, empty or non-string products and 33 products.
2. **Declaration time versus plan hash.** Two recorders loading the same plan share one `inventory_sha256`; whether the plan
   "precedes" the first cutoff depends only on the measured load time. Loading at 29,999 precedes a 30,000 cutoff; at 30,000 it
   does not, and every row then carries `inventory_recorded_after_first_cutoff`.
3. **Payload completion is the gate, not receipt, book or monitor completion.**
   * Late merged proof: a heartbeat overtakes match 11, the match arrives, and the closing heartbeat at 30,000 is processed with
     monitor completion 30,002 but producer completion 30,500. The frozen 30,000 row records the then-known failed proof
     (`missing_live_match_ids`, count unknown). At as-of 30,100 the monitor already reports the merged proof
     (`proof_available_ts_ms = 30002`), yet the producer says `trade_row_processing_incomplete` and keeps the count null. At
     30,500 it reports one verified trade and 200 USD. The frozen row is unchanged afterwards.
   * Quote: a heartbeat at 29,999 whose book and monitor processing finish inside the cutoff but whose producer processing
     finishes at 30,001 makes the book view available while the component reports `quote_row_processing_incomplete` with no
     bid; at 30,001 the quote is available with the snapshot's own book completion time (25,011), not the heartbeat's.
   * A packet processed in the same millisecond it was received is available at receipt + 1 ms, and the envelope hash is the
     canonical JSON hash.
4. **Deduplication and sides.** The first receipt wins across connections even when the duplicate changes spelling
   (`100.00`/`2.0`); a conflicting duplicate vetoes the window. Maker sides are inverted; an unknown side keeps its amount
   separate, still counts in the verified total, and blocks `flow_available`.
5. **Epochs at a shared millisecond.** A trade received at 0 on connection 1, followed at 0 by a connection change (or a
   `queue_overflow` with resubscription), is kept in its original epoch, counted as known, and never certified by the new
   epoch's complete proof chain: `trade_row_continuity_mismatch`, count null.
6. **Verified zeros versus unknown.** With heartbeats but no snapshot, trades are a proven zero at 30,001 while the quote is
   unavailable; at the cutoff itself the zero is still unknown because the closing beat is known at 30,001. A stale quote keeps
   its original observation (age 29,990 ms) while the trade component independently reports a proven zero. A missing benchmark
   marks every row, including BTC's own, and the coin's fresh book is not inherited.
7. **Frozen cohorts.** `SlotEvidence` is frozen; decoded copies are independent; later trades, an audit failure and sealing
   leave the cohort object and its decoded rows identical. A checkpoint taken late, after more packets, yields the same
   components as one taken at the cutoff. Assessment completion is measured separately from knowledge as-of.
8. **Failures.** Float, boolean, negative or string clocks, a tape not starting at sequence 1, a sequence gap and the monitor's
   packet cap each fail the artifact closed; checkpoint, seal and report then refuse. Component queries reject float or
   boolean cutoffs, unplanned cutoffs and as-of before the cutoff.
9. **CLI.** Output nested inside the input directory is refused before anything is created. A valid run records the plan and
   tape hashes, 4 planned rows all `unavailable`, and a packet ledger of the right length. A tape with a sequence gap leaves
   `FAILURE.json` naming the sequence failure and no `REPORT.json`.

Mutants killed: quote producer gate dropped, proof heartbeat producer gate dropped, epoch ignored in continuity, predeclaration
boundary `<=`, taker side not inverted, cohort not cached, first-sequence check removed, deduplication by `seen` replaced.

## Scope, reviewed as executable facts

* **No positive eligibility path.** A fully healthy synthetic tape (fresh snapshots, continuous heartbeats, proven windows) still
  yields every row `unavailable`, `study_eligible = False`, with the four not-implemented reasons present, and every report flag
  (`full_feed_verified`, `positive_eligibility_supported`, `directional_report_adapter_supported`,
  `durable_publication_verified`, `study_frozen`, `feed_gate_pass`, `fitting_allowed`, `live_integration`) false.
* **An empty tape accounts for every planned row but proves nothing.** Zero packets, eight rows, every component unavailable.
* **Completeness is relative to the plan.** A product present on the wire but absent from the plan produces no row and no
  warning; `expected_rows == recorded_rows` holds by construction. That equality is an accounting assertion, not a check that
  can fail. The intended exchange universe still needs an external, predeclared inventory.
* **Nothing is strengthened elsewhere.** The module imports only the book and monitor; a clean `-I` interpreter loads it without
  the directional reporter, association, targets, diagnostics, replay store, sockets or backend code. Directional and target
  hashes are unchanged.
* Baseline and feature evidence, continuous quote health, durable publication and full-feed certification are not produced
  here; the trade window is a 30 s receipt-ID check and the quote is a last processed state with its original age.

## Observations and suggestions (not defects)

- **O1, ordering invariant.** Under sequential ingest with a monotone clock, a trade row's producer completion is always at or
  before the closing heartbeat's completion, so the `len(known) == len(rows)` branch of `proof_rows_known` cannot fire on its own
  (mutants M4 and M9 survive for this reason). The reachable gate is the closing heartbeat's producer completion, which is
  tested. The branch is harmless and defensive; keep it, but the docs should not describe it as a separate observable case.
- **O2, reason precedence.** When the producer has not finished a quote packet, `quote.reason` is `quote_row_processing_incomplete`
  even if the book's own reason (for example `stale_book_observation`) would also apply. Fail-closed; reporting both would help
  diagnostics.
- **O3, failed runs and cached cohorts.** After a failure, `checkpoint` refuses even already-frozen cohorts. Consistent with "a
  failed or partial output is not an eligibility artifact"; worth a sentence in the contract so it is not read as data loss.
- **O4, Decimal rendering.** Amounts are rendered with `str(Decimal)`, so exotic exchange spellings such as `1E+2` would appear
  in exponent form. Cosmetic.
- **O5, prospective use.** With the real clock, a replayed historical plan can never precede its first cutoff, so every replay row
  carries `inventory_recorded_after_first_cutoff`. That is correct and means a pilot must load its plan before the first cutoff;
  that procedure belongs to the future evidence producer and pilot design, not to this module.

## Checks

- **Runtime:** cloud Linux, Python 3.12.3 (pinned 3.12.10 unavailable), pytest 8.3.5, Black 24.8.0.
- **Existing input-evidence tests:** 32 passed. **Review probes:** 46 passed on unmodified code.
- **Targeted set, Codex's recorded command:** 1,241 passed (Codex's 1,195 plus these 46).
- Black clean on the module, both test files, book and monitor. Guardrails pass.
- All 11 historical hashes in `live_movers_contract_20261027/SHA256SUMS.json` match.
- **Protected sources:** `git diff fd1079d HEAD` over scripts, tests, backend, frontend, results and every contract, excluding the
  three new input-evidence files and their checks record, is empty.
- Not run: the full test folder, native Windows or Mac, any real tape. No capture, outcome study, fit, historical rerun,
  threshold change, pilot, live scoring or production change.
