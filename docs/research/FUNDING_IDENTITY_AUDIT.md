# Corrected baseline review and funding identity audit

Audit date: 2026-10-25. Baseline under review:
`claude/scoring-baseline` at `5f489a942b59a12fdac104acd53153561408b9fd`.
This is an isolated research checkpoint. Production and the frozen input panel
are unchanged. No funding comparison or full hourly funding backfill is run here.

## Verification method fixed before reviewing the complete mapping results

The frozen 133 entries are **ticker candidates**, not a verified asset universe.
This audit checks all of them without changing the frozen file. It records current
Coinbase currency names, networks and contract addresses, Coinbase product IDs,
and Hyperliquid perpetual metadata, including delisted markets. Hyperliquid spot
token addresses are not treated as addresses of the perpetual's underlying.

For an independent economic-identity and unit check, request the documented
Hyperliquid `candleSnapshot` endpoint at interval `1M` for 2022-01-01 through
2026-10-18. Compare each **completed returned window's** close with the frozen
Coinbase daily close at the same UTC end date. Funding and model outcomes are not
inspected in this mapping check. See the interval amendment below.

Fixed proposed price-unit factors are 1 for exact ticker matches and 1,000 only
for the four explicit pairs BONK/kBONK, FLOKI/kFLOKI, PEPE/kPEPE and SHIB/kSHIB.
No multiplier is inferred from `szDecimals`, and no arbitrary best-fitting factor
is selected. For current delisted markets, omit their final returned monthly bar
from validation because its close may precede calendar month end.

The conservative research mapping screen requires at least six common completed
30-day closes, at least 90% within 10% after the fixed unit conversion, and a
correlation of at least 0.95 between adjacent common 30-day log returns (at least
four consecutive-bar return pairs). These thresholds are operational QA choices,
not statistical proof of asset identity or predictive performance. Unresolved,
short-history and inconsistent matches remain excluded from the primary comparison
until independently resolved. Verified price correspondence is corroboration of
economic exposure; it is not proof of identical on-chain token contracts.

BTC-USD remains a benchmark rather than a scored asset, consistent with the
baseline. Current delisting is recorded, not used to erase valid historical
coverage. Historical admissible dates still require the actual funding backfill
and per-row availability checks; monthly candles do not establish funding coverage.

## Units and timing for the next experiment

- Join by explicit Coinbase `product_id` and exact Hyperliquid contract name.
- A 1,000-token contract factor applies to price and position-size comparisons.
  **Do not multiply or divide the dimensionless funding rate by 1,000.**
- Preserve native funding rate, premium, exact timestamp and venue. Establish the
  endpoint's settlement timestamp meaning and lag the hourly data so the day-d
  decision uses only funding observable by that decision.
- No funding forward-fill across missing hours, before observed history, or after
  a market stops returning funding. Compare models on identical eligible rows.
- Backfilled values and today's metadata are not historical availability records.
  The old `first_ts` candidate fields are not assumed to be complete funding spans.

## Primary documentation

- [Hyperliquid info endpoint and supported candle intervals](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- [Hyperliquid perpetual metadata](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals)
- [Contract specifications](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications)
- [Funding calculation and payments](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)
- [Rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- [Coinbase currency metadata](https://api.exchange.coinbase.com/currencies)
- [Coinbase product metadata](https://api.exchange.coinbase.com/products)

Raw public responses, request bodies, capture timestamps and SHA-256 digests are
preserved in `results/funding_identity_audit_20261025/`. Retrieval is paced at
approximately 29 monthly-candle requests per minute, leaving shared-IP budget.

## Results

### Baseline review: accepted as an offline experimental comparator

All **23 existing tests pass**. The model and feature files are unchanged from
`2959072`; config changes only add the already-written continuation lower bound
and the four-week resampling setting. Independently rebuilding from the frozen
raw files reproduces all 421,064 eligible rows exactly, and all 496 input hashes
verify. Input manifest SHA-256:
`f6d35da4a7423b1b035926c951b6365b52f804a92b1c3cd194bcd898cef2ba71`.

Independently refitting the monthly models for the 90-day-history test phase
reproduces the primary estimates, actual-return and residual deciles, all weekday
phase estimates, four-week moving-block intervals, and all corrected event
estimates exactly. This review does not claim a fresh full discovery or 60-day
sensitivity rerun. Those committed artifacts are retained as Claude's runs.

| Check | Reproduced result |
|---|---|
| 1-day ranking IC | +0.087046945967 |
| 7-day ranking IC | +0.050950184785 |
| 1-day four-week moving-block interval | [+0.076427, +0.096656] |
| 7-day four-week moving-block interval | [+0.031426, +0.069259] |
| Corrected test continuation events | 8,319 |
| 1-day actual return, bottom / top decile | -0.838746% / +0.218029% |
| 7-day actual return, bottom / top decile | -2.148690% / -1.308375% |

The two review findings are resolved. The changed seven-day exhaustion result
versus same-coin controls and the post-test correction status are disclosed in
Claude's write-up; this is not independent confirmation or a pristine one-shot
test. The score remains an ordinal experimental coin ranking, with no probability
or trading-action validation. The primary model's full-universe ranking survives
the added dependence checks, while liquid-coin and top-selection results remain
weak. Evidence: `results/funding_identity_audit_20261025/baseline_verification.json`.

### All 133 candidate mappings checked

**128 pass the conservative price-correspondence screen**, with minimum adjacent
30-day return correlation 0.993613. This is corroboration of economic exposure,
not a claim that the perpetual and spot asset have identical on-chain contracts.
Of those 128, BTC is benchmark-only, leaving **127 conditionally admissible scored
product mappings**. No pair with enough observations failed the fixed price screen.

Eleven current Hyperliquid-delisted markets pass on historical observations and
remain eligible for actual historical funding checks: BADGER, BLAST, BLZ, BNT,
ILV, IP, OGN, PROMPT, REQ, STG and TON. Current delisting is not a blanket historical
exclusion. Four unit conversions are corroborated across 23-39 common windows:

| Coinbase product | Hyperliquid contract | Proposed spot units per HL price unit | Median normalized price ratio |
|---|---|---:|---:|
| BONK-USD | kBONK | 1,000 | 1.000342 |
| FLOKI-USD | kFLOKI | 1,000 | 0.998911 |
| PEPE-USD | kPEPE | 1,000 | 1.000679 |
| SHIB-USD | kSHIB | 1,000 | 0.999844 |

All dimensionless funding-rate multipliers remain **1**, including these four.

| Held product | Completed common windows | Reason |
|---|---:|---|
| AI-USD | 0 | Coinbase metadata identifies Gensyn; its panel starts after the old HL AI market's returned price history. A ticker match is insufficient and this is an unresolved identity collision. |
| DOOD-USD | 5 | Matching observed prices, but less than the predeclared six-window minimum. |
| GRASS-USD | 2 | Too little common history under the fixed screen. |
| PONS-USD | 0 | No common completed returned window. |
| USELESS-USD | 1 | Too little common history under the fixed screen. |

These holds describe evidence insufficiency, not proof that every held pair is
the wrong project. Do not silently promote them after looking at funding outcomes.
They can be resolved separately with documented independent evidence or a new
prespecified validation design. The original frozen 133-entry file is untouched.

### Concrete next handoff to Claude

1. Use `results/funding_identity_audit_20261025/APPROVED_FUNDING_MAP.json` as the
   explicit 127-product research map, conditional on actual funding availability.
   Preserve the frozen original candidates and the five exclusions separately.
2. Specify the funding comparison before examining its outcomes: exact hourly
   timestamp alignment, gaps, rolling warm-up, baseline features, discovered sign
   handling and same-row model comparisons. Reconcile with the corrected protocol
   and `FIRST_EXPERIMENT_SPEC.md`; keep its intended horizons and no retuning.
3. Backfill hourly funding into a new isolated research dataset, storing original
   responses and per-product hashes, actual observed start/end timestamps, missing
   hours, duplicates and delisting tails. Funding history is still **not collected
   by this audit**. Neither monthly prices nor candidate `first_ts` prove coverage.
4. Recompute the price/volume comparator on the exact approved, funding-complete
   rows used by the augmented model. The previously quoted IC +0.053 / +0.011
   belongs to the original funding-candidate cut; it is not automatically the
   baseline for the revised map and actual overlapping dates.
5. Report the numeric-score comparison, costs as scenarios, exclusions and input
   hashes, then commit and push the separate experiment branch for review. No
   production score change or merge follows from this audit.

Reproduce the mapping screen without network calls, from repository root:

```powershell
python -B scripts/scoring_data/audit_funding_identity.py --checkpoint "$env:USERPROFILE\.moonwalking\data\daily_panel_2022_2026" --evidence docs/research/results/funding_identity_audit_20261025
python -B -m unittest discover -s tests -p test_funding_identity_audit.py -v
```

Six focused mapping tests pass: correct matching, explicit 1,000-unit conversion,
zero-trade/unfinished-window exclusion, no returns across gaps, delisting-window
exclusion, and absent overlap remaining unresolved. The frozen panel and all
application/experiment code remain unchanged by this audit branch; changes are
the separate QA helper, its tests, evidence and this report.

## API-semantics amendment M1

While collection was still running, inspection of four responses established that
Hyperliquid's `1M` candles are **fixed 30-day epoch-aligned windows**, not calendar
months. AAVE's first bar begins 2021-12-29 and ends 2022-01-27; its latest returned
bar ends 2026-11-02, beyond the requested cutoff. Therefore align on the actual `T`
end timestamp, require an exact UTC day end, and exclude any bar ending after the
frozen panel's last complete day. Also exclude zero-volume / zero-trade bars:
responses contain apparent pre-venue backfilled prices, which do not establish
executed Hyperliquid trading or historical funding availability. Counts and raw
responses are retained. Thresholds and proposed unit factors are unchanged. This
amendment precedes computation of the complete mapping screen.
