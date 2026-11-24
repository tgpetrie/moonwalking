# Claude independent review of the opt-in directional exposure report — 2026-11-04

Assignment: [CLAUDE_DIRECTIONAL_EXPOSURE_REVIEW_20261104.md](../../ai/CLAUDE_DIRECTIONAL_EXPOSURE_REVIEW_20261104.md).
Cloud session, own branch `claude/instant-directional-exposure-review-20261104`.
**Pending Codex review; not merged.** `codex/instant-radar-20261028` remains authoritative, and its
checkpoint files (`RESUME_HERE.md`, `ACTIVE_WORK.json`, `HANDOFF.md`) are untouched on this branch.

- **Inspected tip:** `f5617066397d26191d342b1956590aee65bc0f48` (docs-only on top of implementation `9da4987`).
- **Reviewed, byte-identical to Codex's `instant_directional_exposure_20261104/CHECKS.json`:**
  `instant_directional_exposure.py` `638db051…`, its contract `6bc66818…`, `tests/test_instant_directional_exposure.py` `2a528753…`.
- **Read-only dependencies:** `instant_association.py` `0e79b8f1…` and its contract `4a66c231…`, both unchanged since the accepted
  `8631231`.
- **Probes:** `tests/test_instant_directional_exposure_review.py`, 51 cases.
- **Checks record:** [CHECKS.json](../results/claude_directional_exposure_review_20261104/CHECKS.json).

**Verdict: no defect found.** Every property in the assignment holds under independent hand calculation, and seven deliberate
mutants of the module each fail at least one probe, so the probes are sensitive to the behaviours they claim to pin. No fix was
needed, so there is no patch and no pre-patch failure to report; the pre-patch evidence is that all 51 probes pass on the
unmodified pushed implementation. Four small robustness and policy suggestions follow; none is a contract violation.

## Verified by hand

Oracle universe: products A, B, C at four 5s cutoffs T0..T3, 24 eligibility records, with C@T0 outside the universe on both
boards and direction-specific flags elsewhere. Expected values were written before running the code.

1. **Product-hours and time unions.** Up board eligible {A@T0, A@T1, B@T1, C@T3}: 4 slots = 20 s of product-time,
   cutoff union {T0, T1, T3} = 15 s. Down board eligible {B@T0, B@T2, C@T2}: 15 s and union {T0, T2} = 10 s. Either-board union
   {T0, T1, T2, T3} = 20 s, strictly less than the 25 s sum. Universe sizes [2, 3, 3, 3]. Exclusions by first failed flag:
   up {1, 3, 1, 3}, down {1, 1, 3, 4}. All match.
2. **Ranker complete rows.** Three rankers with different coverage per board. Up board: R1∩R2∩R3 = {A@T1}; at 300 s it is
   gradable so the identical-row table is `[[A, T1]]`; at 900 s A@T1 is `unavailable:x`, so the table is empty. Down board: R3
   scored nothing there, so no row is scored by every ranker, and the natural per-ranker coverage still reports R1 1/1, R2 3/2,
   R3 0/0. Without rankers the table is every gradable row, as documented; with a ranker that scored nothing it is empty.
3. **Own-direction gradability.** A ready up failure stays gradable whether the down label is missing, pending, unavailable,
   or the down board is flagged ineligible. Both boards grade independently with opposite outcomes. The legacy joint reporter
   still requires both labels on the same inputs.
4. **Exposure independent of future labels.** The exposure keys of every board, the universe sizes and the either-board union
   are identical with no labels and with all 48 label rows ready.
5. **Unavailable never becomes a negative.** The directional output contains no success, failure, negative or
   `verified_forward` field anywhere; an unavailable own-direction label is counted only under its reason.
6. **Horizon maturity boundaries.** At as-of = anchor + 299,999 both horizons are immature; at + 300,000 only 300 s is mature;
   at + 899,999 still only 300 s; at + 900,000 both. Decision eligibility is unaffected throughout.
7. **Clock types and boundaries.** Report as-of and `available_ts_ms` reject bool, float, negative, string and None.
   `available_ts_ms == ts_ms` and `ts_ms == asof` are accepted; `available_ts_ms = ts_ms + 1` and off-grid or bool cutoffs are
   rejected.
8. **Pairing, universe, duplicates, flags.** Pairing is per product *and* cutoff. Missing or integer flags are rejected for every
   flag. Unknown directions are rejected. A duplicate ranker slot given once as a tuple and once as a list is still a duplicate.
   Mixed label provenance is rejected even when the odd row belongs to a slot that is not on any board.
9. **Empty and immutable.** Empty labels, eligibility and rankers at as-of 0 give a zero report with null fractions. Labels,
   eligibility and ranker inputs are not mutated.
10. **Legacy and provenance.** The report embeds `instant_association.provenance()` unchanged, hashes its own LF-normalised
    source and contract correctly, and the joint reporter's output shape is untouched.

Mutants killed by the probes: ready failure made ungradable (6 probes fail), maturity boundary off by one (2), ranker union
instead of intersection (1), availability checked against as-of instead of cutoff (1), either-board sum instead of union (1),
pairing check skipped (1), opposite-direction label required (4).

## The limitation, reviewed explicitly

The contract and the module both say eligibility is `caller_assertions_not_authenticated_feed_evidence`, and that is accurate.
Two probes make the limitation executable rather than a sentence:

- The reporter accepts a record claiming `available_ts_ms = 0` for a cutoff an hour later. It cannot know that is false.
- Submitting only A and B at T0 yields a universe of size 2. A product omitted from both boards is invisible; the pairing check
  only catches a product that is present on one board and not the other.

So this reporter does not produce authenticated eligibility and does not prove the intended universe is complete. Any claim to
that effect should be rejected until the separately versioned evidence producer exists, with per-row processing completion
and an intended-inventory record. I did not implement a feed bridge or any producer; that is future work by design.

## Suggestions (not defects)

- **S1, robustness.** A malformed ranker slot shape (two items, four items, a dict, a bare string) raises `TypeError` from
  `_key(*record)` rather than the module's usual `ValueError`. It still rejects; a shape check before unpacking would make the
  failure message consistent. A non-mapping `ranker_slots` similarly raises `AttributeError`.
- **S2, association module, out of scope here.** `_labels` accepts pending or unavailable labels anchored after the report
  as-of; the directional reporter simply ignores them because no eligibility can exist there. Rejecting `anchor > asof` for all
  statuses would make the two modules' causality checks symmetric. No behaviour of the reviewed module depends on it.
- **S3, study policy.** A ranker that scored no rows on one board collapses that board's identical-row set to empty. That is
  the stated definition, but a caller comparing one-direction rankers may not expect it. Reporting the number of rankers with
  any eligible score on the board would make such tables self-explanatory.
- **S4, documentation.** `universe_size_by_cutoff` is derived from up-board membership. That is sound only because the pairing
  check enforces equal membership; a one-line note in the contract would prevent a future reader from loosening one without
  the other.

## Checks

- **Runtime:** cloud Linux, Python 3.12.3 (pinned 3.12.10 unavailable), pytest 8.3.5, Black 24.8.0.
- **Directional and association tests:** 101 passed (48 + 53). **Review probes:** 51 passed.
- **Targeted set, Codex's recorded command:** 1,163 passed (Codex's 1,112 plus these 51).
- Black clean on the directional module, association module and both directional test files. Guardrails pass.
- All 11 historical hashes in `live_movers_contract_20261027/SHA256SUMS.json` match.
- **Protected sources:** `git diff 3c859ef HEAD` outside the three new directional files and their checks record touches only
  documentation. Targets, V1/V2, diagnostics, monitor, samples, book, publication, association, recorder, results, backend,
  frontend and every existing contract are byte-identical.
- Not run: the full test folder, native Windows or Mac, and anything with real data. No capture, outcome analysis, fitting,
  historical rerun, threshold change, live scoring or production change.
