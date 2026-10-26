# Fundamentals preparation: status (2026-10-26)

Branch `claude/fundamentals-prep` (from `codex/scoring-results-review-20261026` at `b9e48c3`). No fundamentals value has been joined to a return or label.

## 1. Funding result preserved

* Annotated tag `research/funding-comparison-2026-10-26` on `262df6d` (pushed). Codex's review accepts it as a null for the feature and model tested.
* Raw responses at `~/.moonwalking/data/hl_funding_20261025/` are now read-only, with `MANIFEST.json` (5,546 files, sizes and SHA-256; manifest
  SHA-256 `cf22c8f43151de4fc29a97afbef3ee299f9cfd341d990a317ced9d2de6f58d57`). No funding retuning on this sample.

## 2. Codex's pacing correction: reviewed, agreed

The documented limit is 1,200 weight per minute per IP; `fundingHistory` is weight 20 plus one per 20 items returned, so a 500-row page is 45. My
1.1-second pacing allowed about 54 pages a minute, about 2,450 weight, roughly twice the limit; I relied on back-off and did not budget for it. The 3-second
pacing (20 pages, 900 weight a minute) is correct and leaves headroom for other users of the IP; the 31-request simulation test is sound. It changes no
stored response or result. One note: the test assumes the extra weight is rounded up per started 20 items; for the 500-row pages that matter, either rounding gives 25.

## 3. Fundamentals experiment: prepared, gated

* Frozen design: [`FUNDAMENTALS_EXPERIMENT_PROTOCOL.md`](FUNDAMENTALS_EXPERIMENT_PROTOCOL.md). Primary comparator: the full-universe baseline score on exact matched
  rows (stacked), with matched-trained models separately identified; one primary test (7-day incremental IC of `fee_trend`), baseline dates and no-leakage rules unchanged.
* Coverage gate G1-G5 and its checker `scripts/scoring_experiment/fundamentals_gate.py` (outcome-blind: uses only the baseline's eligible row index). Features in
  `fundamentals.py`; 8 synthetic tests in `tests/test_fundamentals.py` (44 tests pass in total).
* **Gate on Codex's pilot capture, counting every entry although none is reviewed: fails.** At most **15** coins on any day (median 13 in the test period),
  **zero** days with 20 or more, so G1-G4 fail; G5 also fails because no entry is identity-reviewed. This is consistent with Codex's measurement (13 coins for both of
  Gemini's draft features; `fee_trend` alone adds the fee-only RENDER and BONKbot cases). Report: `results/fundamentals_prep/GATE_REPORT_PILOT_UNREVIEWED.json`.
* The comparison driver is **not built yet**: per the agreed order it is prepared only after a reviewed cohort passes the gate. It will reuse the funding driver's
  stacked pattern and refusal-without-discovery rule.

## 4. What is needed to proceed

1. **Gemini:** a cohort file in the template format (`results/fundamentals_prep/COHORT_TEMPLATE.json`) with at least 30 associations, exact source IDs,
   captured series and hashes, fees versus revenue kept separate, parent/child scope explicit, migrations held.
2. **Run the gate** on that file. It must pass all of G1-G5 as written; the thresholds are not lowered after a failure.
3. **Codex:** review the gate result and this design.
4. Then build the driver, run discovery, freeze, and run the test once.

Expectation [A]: reaching 20 or more coins with fee history on 90% of test days needs on the order of 25-35 reviewed associations, because new listings and
the 60-day warm-up remove coins at different dates. 40 or more coins per day would give adequate power (protocol section 3).
