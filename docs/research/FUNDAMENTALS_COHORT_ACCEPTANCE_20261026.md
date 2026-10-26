# Fundamentals cohort acceptance — 2026-10-26

**Coverage gate passed.** The reviewed input contains **27 approved associations
and 5 held products**. The hardened checker at Claude commit `8047ba7` passes
G1–G5 on the retained public captures. This clears the cohort-coverage prerequisite
for building the comparison driver. It is not evidence that fundamentals predict
returns, and no fundamentals outcome experiment has run.

The two new pasted attachments are byte-identical (SHA-256
`1cb5a34e0b3318c8f76e0e242151d8a0f12fd13cbfb4b95d29590ed8620a0450`).
One copy (with LF line endings) is retained as
[`GEMINI_SUBMISSION.md`](results/fundamentals_cohort_acceptance_20261026/GEMINI_SUBMISSION.md).
Its code and approval claims were treated as untrusted proposal data. The code
was not executed; only its literal `DECISIONS` table was parsed.

## What was completed

- Brought Claude's committed gate fixes into the separate Codex review branch.
  Repeated product IDs and duplicate eligible rows are rejected; distinct
  products are counted; review provenance, metric/source IDs and family overlap
  are checked. G3 uses the May 24 embargo cutoff. The primary 95% interval is
  now explicit in `fundamentals_config.json`.
- Replaced the proposed converter with
  `scripts/scoring_experiment/apply_verified_cohort_review.py`, which uses the
  actual nested cohort schema and rejects changed captures or an unreviewed
  provider-ID change. No source bytes were refetched, rewritten or fabricated.
- Matched protocol-token contracts against the saved Coinbase network/contract
  records and the captured fee response. EVM address case is normalized;
  Solana/base58 case is preserved. Chain associations are checked against
  explicit Coinbase-network, DeFiLlama chain-ID and CoinGecko-ID mappings.
- Verified all referenced fee files and capture metadata against the committed
  capture manifest, and the Coinbase currency file against its previously
  recorded hash. Review provenance names **Codex's local verification**, rather
  than claiming the cloud author inspected files it could not access.
- Ran both the converter's gate evaluation and the ordinary hardened gate CLI
  on the saved cohort. Their gate results, product counts and daily counts match.

Evidence: [`GATE_REPORT.json`](results/fundamentals_cohort_acceptance_20261026/GATE_REPORT.json),
[`REVIEWED_COHORT.json`](results/fundamentals_cohort_acceptance_20261026/REVIEWED_COHORT.json),
and [`IDENTITY_VERIFICATION.json`](results/fundamentals_cohort_acceptance_20261026/IDENTITY_VERIFICATION.json).

## Corrections applied to the submitted converter

The proposal was not ready to run unchanged:

1. Its default input path omitted `docs/research/`. Its `identity_evidence`
   objects, flat `metric` field and scope names did not match the hardened
   gate's string evidence, `source_metrics.fees` and `parent` / `chain` schema.
2. Its `expected_source_id` values were never used to validate or update actual
   nested source IDs. Three values disagree with retained fee responses:

   | Product | Proposed ID | Captured ID accepted after local contract/scope review |
   |---|---|---|
   | YFI-USD | `119` | `113` |
   | ORCA-USD | `283` | `parent#orca` |
   | PENDLE-USD | `382` | `parent#pendle` |

   ORCA and PENDLE are therefore explicitly parent aggregates in this cohort.
   These amendments are recorded per entry; the old IDs were not silently
   treated as matches. Activity context does not imply token-holder revenue.
3. Its OP glob would not find the actual retained files,
   `OP_alternative_capture.json` and `OP_alternative_fees.json`. Its replacement
   fields were also flat, leaving the nested fee-file references unchanged.
   The accepted **explicit OP amendment** binds those exact filenames, their
   frozen hashes, `chain#optimism` and the `op-mainnet` daily-fee URL together.
4. The converter now validates the saved bytes and token/source association
   before setting approval, rather than copying a proposed status and reviewer
   string into an unchecked record.

ARB and OP are described as **governance-token chain context**, not as proof of
gas-fee accrual to their token holders. Their governance roles are documented by
the [Arbitrum Foundation](https://docs.arbitrum.foundation/concepts/arb-token) and
the [OP governance-token specification](https://specs.optimism.io/governance/gov-token.html).
This experiment does not infer token cash flows, buyback amounts or entitlements.

## Measured coverage under the unchanged prepared feature

Primary feature remains the log difference of the two trailing 30-day fee means,
with at least 25 present days in each half, the pinned-series filter and the
two-day lag. The seven-day horizon is the outcome horizon, not a seven-day
fee-feature window. No volume floor, token-deflated TVL quotient or new feature
was introduced.

| Gate | Measured result | Requirement | Verdict |
|---|---:|---:|---|
| G1 | 648 / 648 test days, 100% | At least 90% with 20 coins | Pass |
| G2 | 93 test weeks | At least 80 | Pass |
| G3 | 9,277 qualifying rows before 2024-05-24 | At least 5,000 | Pass |
| G4 | 31 discovery weeks | At least 20 | Pass |
| G5 | Zero provenance/identity-schema/source-family problems | Zero | Pass |

Test-day counts range from **23 to 27**, median **26**. Discovery counts range
from **16 to 24**; 657 of 723 discovery days have at least 20 counting coins.
The protocol does not require every discovery day to have 20 coins. Individual
late-start products may contribute only to the test; the gate is measured on
the actual eligible coin-days, not inferred from a protocol's launch date.

Held: **DYDX-USD, 1INCH-USD, JUP-USD, RAY-USD and AERO-USD**. JUP is not relabelled
as JUPITER; Aero's mixed parent remains excluded. OP is the only promotion from
the submitted script's held set, through the separately verified amendment.
The five additional suggested assets (ENS, LRC, UMA, OSMO, DOT) remain unverified
proposals and were not added. They are not needed to make these measured gates
pass.

**Limits.** These approvals concern the recorded retrospective token/source
associations and captured series, not perpetual coverage or economic value
capture. Publication-time and adapter-revision limitations remain. G3 is still
a coverage screen: missing labels or baseline-stack predictions can reduce the
actual fitting rows. First-fit readiness must be certified in the driver before
discovery. Passing the gate does not establish power or predictive value.

## Next handoff: Claude

The cohort prerequisite is cleared. Bring this checkpoint into the fundamentals
work through Git, preserving any active work first. Keep the 27/5 cohort, exact
source hashes, lag, primary feature, date splits, +0.02 criterion and explicit
95% interval fixed. No funding retuning or live-score change is authorized by
this result.

1. Build the comparison driver using S0 from out-of-sample full-universe baseline
   predictions and S1 on exactly the same matched rows. Report matched-trained
   models separately.
2. Confirm first-fit readiness from feature/label/prediction **availability**,
   respect the embargo, and keep all cohort/config/input hashes in outputs.
3. Have Codex review the driver before discovery; run discovery, freeze its
   permitted decisions, then run the single primary test. Refuse test execution
   without a matching discovery artifact. Do not change cohort membership or
   thresholds after seeing results.

No new Gemini document is needed to resolve the format errors already repaired
here. Future source expansion is separate work, with the same evidence standard.

## Reproduce and checks

On this PC, using the project's NumPy/pandas environment:

```powershell
python -B scripts/scoring_experiment/apply_verified_cohort_review.py --amend-op-mainnet
python -B scripts/scoring_experiment/fundamentals_gate.py --cohort docs/research/results/fundamentals_cohort_acceptance_20261026/REVIEWED_COHORT.json --captures C:/Users/tgpet/.moonwalking/analysis/fundamentals_review_20261026 --out docs/research/results/fundamentals_cohort_acceptance_20261026/GATE_REPORT_CLI.json
```

**58 tests pass**: 51 existing research tests after Claude's fixes and seven new
converter tests covering capture changes, wrong contracts, unreviewed source
IDs, Solana case sensitivity, literal-only parsing, nested schema preservation
and the exact OP amendment. The two gate executions match. Artifact hashes are
preserved separately in `SHA256SUMS.json`. No application code, market-data store,
funding result or fundamentals outcome was changed or evaluated.
