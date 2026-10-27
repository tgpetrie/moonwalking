# Live movers comparison driver — implementation notes (2026-10-27)

Driver: `scripts/scoring_experiment/live_movers_run.py`; tests: `tests/test_live_movers_run.py`.
Implements `COMPARISON_SPEC.json` (`live-movers-pilot-comparison-v1`) on `CONTRACT_PRODUCTION.json`.
**Verification, discovery and the one-time historical validation are complete.** The primary verdict is **inconclusive**;
read [the results](LIVE_MOVERS_RESULTS_20261027.md). All frozen hashes match, the 333,170 re-derived eligible episodes equal
the frozen `eligible_episodes.csv` row for row, and readiness passes (train 217,302 / 40 days /
192 products; discovery 38,764 / 7 / 119; test 77,104 / 14 / 205).

Choices the spec left open, fixed here before any outcome:

* **Eligibility is re-derived, not trusted.** The driver reruns the frozen `freeze_live_contract.classify` (its hash must
  equal the manifest's `freeze_script_sha256`) over the frozen DB and refuses unless it reproduces the frozen list exactly.
* **Labels:** `gross_return_*` are already direction-signed percentages (`board_outcomes._directional_return`), so they are
  used as stored; cost scenarios are gross minus the round-trip percentage. Stored net `return_*` fields are never read.
* **Direction alignment:** `pct_1m` and `pct_3m` are multiplied by -1 on the down board; `volume_change_1h_pct` is not.
* **Fitting is per stratum and per horizon** (strata are kept separate); ridge on standardized columns with an unpenalized
  intercept equal to the fitting-row mean; target is the raw gross label (no within-day demeaning).
* **Alpha selection** compares each candidate's own discovery mean daily IC (days with >= 20 rows and nonconstant target,
  B0, B1 and that candidate). Iteration runs from the largest alpha with a strict `>`, so ties choose the larger alpha.
* **Identical day groups:** in evaluation, a day counts only if the target and all four models' predictions are
  nonconstant, so every paired difference uses the same days. Reports include daily ICs, scored row counts and explicit
  exclusion reasons, not just the pre-filter day counts.
* **Moving-block sensitivity:** blocks of 3 consecutive UTC calendar dates over the observed span; missing dates contribute
  nothing (never zero, never bridged).
* **Display score:** percentile of the prediction against the refit model's in-sample train+discovery predictions; share at
  0 and 100 reported. Return-table percentile bands keep equal scores together using average ranks. Empty bands are omitted;
  a constant score creates one band, never five chronological slices.
* **Bootstrap seed:** both uncertainty methods use the preregistered 5000 replicates and seed 20261027, for every stratum,
  horizon and comparison. Former per-stratum and moving-block seed offsets are removed.
* **Verdict labels:** "historically supportive", "below the minimum effect" (iid upper bound < 0.02) or "inconclusive".
* **Not run:** the optional `pct_1h`/`trend_streak` complete-case secondary and excursion (MFE/MAE) tables.

Discovery/test refuse uncommitted driver/contract changes. Discovery artifacts include exact driver/classifier hashes;
`test` requires matching input and code hashes. A documentation/result-only commit does not invalidate unchanged model code.
The discovery artifact can be read from its committed repository copy when the local copy is absent. Test refuses a result
in either location and atomically reserves a local attempt before modeling; an interrupted attempt also blocks another run.
Test reports use exclusive creation, and JSON rejects nonfinite numbers.

The pre-fit [review and regression evidence](LIVE_MOVERS_DRIVER_REVIEW_20261027.md) describe the corrected implementation.
The prospective Coinbase side/coverage audit is independent of this frozen historical comparison.
