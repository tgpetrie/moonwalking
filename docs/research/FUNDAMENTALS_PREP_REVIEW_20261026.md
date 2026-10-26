# Fundamentals preparation and expanded-source review — 2026-10-26

**Assessment: needs revision before the experiment can run.** Funding preservation
is verified. Claude's design is a sensible prepared protocol, and the expanded
source proposal could supply enough observations. The new proposal is not an
approved cohort, and the coverage checker has reproducible validation gaps.
No fundamentals outcomes were evaluated, no model was fitted, and no live score
or another agent's worktree was changed.

Reviewed commit: `5cfbf26fff4698c13b08447d0237b2d46ea20bec` on
`claude/fundamentals-prep`. The attached Gemini proposal is preserved verbatim as
[`GEMINI_COHORT_PROPOSAL_20261026.md`](GEMINI_COHORT_PROPOSAL_20261026.md);
it supplies candidate claims, not authorization or verified measurements.

Evidence: [`MEASUREMENTS.json`](results/fundamentals_review_20261026/MEASUREMENTS.json).
Reproduction: `scripts/scoring_experiment/review_fundamentals_prep.py`.

## Verified: funding preservation and existing tests

- The remote annotated tag `research/funding-comparison-2026-10-26` dereferences
  to `262df6dba979acb7feb098c670e26cadca7b4120`.
- The local manifest SHA-256 is
  `cf22c8f43151de4fc29a97afbef3ee299f9cfd341d990a317ced9d2de6f58d57`, matching
  the tag and status document. All **5,546 listed files** match their sizes and
  hashes and have Windows' read-only attribute. This count includes collection
  metadata and logs; it does not mean 5,546 funding-response pages.
- **44 existing research tests pass:** scoring checkpoint, funding identity,
  baseline, funding features, request pacing and fundamentals features/gate.
  Those tests do not cover the new checker counterexamples below.
- The three-second funding pacing correction is inherited. No funding result
  was retuned or rerun.

## Expanded cohort: useful candidates, unverified approvals

I requested the **32 exact proposed daily-fee endpoints**, preserving first
responses and capture times outside Git under
`C:\Users\tgpet\.moonwalking\analysis\fundamentals_review_20261026`.
Thirty returned HTTP 200; the proposed `1inch-network` and `optimism` fee URLs
returned HTTP 400. A failed URL does not establish provider-wide absence.
No alternate URL was silently substituted. This review does not verify the
proposal's TVL or revenue histories.

Two separately saved follow-up diagnostics resolve the aliases: `1inch` returns
`parent#1inch` and the expected contract, but its captured fee history begins
only **2026-07-20**; `op-mainnet` returns `chain#optimism`, category `Chain`, with
history from **2021-11-18**. Both return HTTP 200. Neither alternative is included
in the fixed 32-candidate measurements below. Adopt them only through a reviewed
cohort amendment; do not treat the 1inch result as the claimed 2021 history.

The newer captures include dates through October 26. Coverage calculations use
only baseline-eligible decision dates and features dated at most decision day
minus two; the frozen test ends October 10. Later observations cannot enter a
past rolling feature. These are still **retrospective backfills subject to
adapter revisions**, not reconstructed point-in-time availability.

The proposal's claimed counts do not reproduce:

| Measurement | Discovery: 2023-01-01–2024-12-23 | Test: 2025-01-01–2026-10-10 |
|---|---:|---:|
| Proposed claim: price plus fee eligibility | 23–28 coins/day | 30–32 coins/day |
| Measured price eligibility only, proposed 32 product IDs | 21–28 | 28–30 |
| Measured price eligibility plus Claude's primary fee feature, **before identity approval** | 15–24 | 23–28 |
| Days with at least 20 in that unreviewed fee intersection | 657 / 723 | 648 / 648 |

With **every proposed identity admitted for a diagnostic upper bound**, the
numerical gates pass: G1 100% of test days, G2 93 weeks, G3 9,165 pre-June rows
on 20-coin days, and G4 31 discovery weeks. **G5 fails: these candidates have not
been approved in this review.** Removing wrong associations or reviewing scope
can reduce counts; these figures are not clearance to run the experiment.

The original 20-coin pilot and this expanded 32-entry capture are different
inputs. Claude's original pilot failure and the new quantity upper bound are
consistent with each other.

### Material identity and coverage corrections

1. **JUP is the wrong Coinbase product for the proposed Solana source.**
   The saved Coinbase currency record identifies `JUP` as the delisted Ethereum
   token at `0x4B1E80cAC91e2216EEb63e29B957eB91Ae9C2Be8`.
   Coinbase `JUPITER` is the Solana token at
   `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN`; the captured DeFiLlama Jupiter
   response gives that Solana address. Hold the `JUP-USD` association and evaluate
   **`JUPITER-USD` as a separate candidate**, with its own frozen-panel eligibility.
   Do not rename, splice or reuse JUP's older price history.
2. **AERO's requested alias returns a broader current parent.**
   `aerodrome` returns `parent#aero-protocol`, named Aero, with linked protocols
   including Velodrome V1/V2/V3 and Aerodrome modules. Its fee series begins in
   June 2022. This is not the claimed Aerodrome-only parent and cannot silently
   become AERO's historical fee series. Resolve the source family, token migration
   and time-varying attribution, or hold it.
3. **Some claimed historical price coverage is absent.** In the frozen baseline
   index, `DYDX-USD` has zero rows; PENDLE first becomes eligible on **2025-06-25**,
   RAY on **2026-04-14**, RPL on 2023-03-08 and LDO on 2023-02-15. Thus those
   products cannot supply the alleged early-discovery observations.
4. **Fee start dates are not protocol launch dates.** Returned first observations
   include ORCA **2024-11-12**, STX **2025-05-11**, PENDLE **2023-07-07**, SNX
   **2021-11-12** and AVAX **2022-11-08**. The proposed earlier continuous spans
   are not supported by these requested endpoints. Missing dates remain missing.
5. Only **22 of the proposed 32 approved product IDs** occur in the committed
   approved funding map. In particular, that map does not contain `DYDX-USD`,
   `1INCH-USD`, `YFI-USD` or `JUP-USD`. Funding-map membership is context, not a
   requirement for this fundamentals experiment; do not filter out valid spot
   products merely because no funding match exists.
6. The claimed **$50,000 trailing-volume eligibility floor is not the baseline
   rule**. The frozen implementation uses the history, completeness, core-feature
   and volatility checks; volume contributes a thinness input. Preserve the
   actual baseline index instead of adding the proposal's filter.

[`PROPOSED_COHORT_HELD.json`](results/fundamentals_review_20261026/PROPOSED_COHORT_HELD.json)
provides 32 machine-readable candidate records with actual fee capture filenames,
hashes, URLs and returned metadata. **Every status is held**, with no reviewer or
identity-evidence approval. It is a starting worksheet for Gemini, not an
approved experiment input. `--captures` must point to the capture folder above.

## Coverage checker: fixes required

### P1 — duplicate products can fabricate a passing cross-section

In `fundamentals_gate.py`, `coverage()` accumulates `(date, product)` rows for
every cohort entry and counts their total, without rejecting duplicate product
IDs or deduplicating the final index. `per_product` overwrites earlier entries,
so the reported per-product section can obscure the duplicate accumulation.

The saved synthetic counterexample supplies **20 entries for one eligible
product**, distinct claimed source names, and one correctly hashed fee file.
The unmodified checker reports **20 coins every test day and passes G1–G5**,
although the actual cross-section has one coin. No actual source approval or
market outcomes are needed to reproduce it.

Required: reject repeated product IDs before processing; assert uniqueness of
baseline and matched `(date, product)` pairs; count distinct products. Add a
regression that rejects the one-coin/20-entry counterexample. Merely comparing
source-name strings does not enforce these invariants.

### P1 — G5 does not establish the review and scope guarantees it claims

The checker accepts `status: approved` without checking `identity_evidence`,
`reviewer` or `reviewed_at`. The saved one-entry counterexample omits all three,
counts **1,696 rows**, and reports no problem. Required source IDs are not
independently validated either. G5 only checks equality of supplied source IDs;
it does not establish parent/child relationships or that a fee file contains
the claimed metric and scope.

Required: validate the cohort schema and nonempty review provenance, require
exact metric/source metadata, and define a reviewed source-family/parent-child
overlap policy that can actually be checked. A hash verifies captured bytes,
not a correct token association or metric meaning. Keep Gemini's prose
`APPROVED_USABLE` labels separate from accepted, evidenced cohort approvals.

### P2 — training-history count precedes the actual embargo cutoff

G3 counts rows with decision dates before June 1, while the first June monthly
fit uses dates **before May 24** under the eight-day embargo. A boundary
counterexample has 5,000 rows before June 1 and passes G3, but only **4,840**
before May 24. The gate can therefore promise an earlier fit than the model
can make. Missing labels can reduce fitting rows further.

Required: make G3 conservatively respect the first-fit cutoff and required
feature/label *availability*, without inspecting return values. Or explicitly
label it a rough coverage screen and separately certify first-fit readiness
before discovery. This boundary issue does not explain the observed expanded
cohort's current G5 failure.

## Protocol review

**Keep:** the strong full-universe baseline prediction on exactly matched rows;
one primary seven-day fee-trend test; the two-day lag and seven-day sensitivity;
missing/zero separation; present-day minimums and pinned-series filter;
retrospective provenance; and refusal to proceed without discovery and review.
The prepared feature code implements the stated daily-window, lag and missing
data rules in the tested cases.

**Resolve before building the comparison driver:**

- Claude freezes one seven-day primary test with **95%** intervals, whereas the
  inherited baseline config has `bootstrap.level = 0.975`. A single primary test
  can justify a different interval level, but explicitly freeze the chosen level
  and its config before running. Do not silently inherit the other value.
- Gemini's attached experiment is **a different design**: one-day source lag,
  a 7/30-day fee ratio, token-deflated TVL, and both horizons in its acceptance
  rule. It does not replace Claude's prepared protocol. Record any intentional
  amendment before outcomes, rather than mixing definitions across artifacts.
- Dividing protocol USD TVL by its governance token's own price does **not**
  generally strip out the prices of the assets deposited in that protocol.
  Keep Claude's neutral USD-TVL label and explicit limitation; the proposed
  quotient does not establish inflows or complete price adjustment.
- The statement that 40 coins would provide adequate power is an assumption,
  not a demonstrated result. Power for paired incremental IC depends on serial
  dependence and covariance of the models' ICs. Retain it as provisional and
  report observed interval widths; coverage thresholds alone cannot certify power.

## Concrete handoff

1. **Claude:** harden the gate and add the counterexample regressions on its own
   branch; reconcile the interval configuration and first-fit readiness. Preserve
   thresholds and the funding null. Do not run a fundamentals outcome test yet.
2. **Gemini:** use the held worksheet to supply reviewed, reproducible associations;
   correct JUP/JUPITER, resolve Aero's broad parent, review the two alternate URLs, and
   replace claimed spans/counts with captured measurements. Supply exact
   identity evidence, reviewer/time, source family/scope and hashes per record.
3. **Codex:** rerun the hardened gate on the reviewed cohort, inspect the matched
   counts and source-family exclusions, and review the comparison driver before
   its single test run. The numerical coverage upper bound is encouraging;
   identity and checker correctness remain the present blockers.

## Reproduce

Use a Python environment with the project's NumPy and pandas dependencies:

```powershell
python -B scripts/scoring_experiment/review_fundamentals_prep.py --verify-funding
# Only to populate a new review capture folder: --capture
```

The script reads the locally built baseline eligibility index, captured public
responses and optional funding manifest. It does not read outcome values for
this analysis or run a fitted model. First captures are retained without retry
or overwrite. Raw response hashes are recorded in the measurements; report
artifacts have a separate SHA-256 manifest.
