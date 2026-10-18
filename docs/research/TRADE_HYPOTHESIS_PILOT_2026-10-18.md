# Trade hypothesis pilot: 2026-10-18

Status: offline research only. No production engine, notification, scoring,
frontend, account, or deployment changes. No predictive edge established.

Branch: `codex/trade-hypothesis-evaluation`, based on
`origin/claude/retention-hotfix` at `ba11b062`.

This is separate from the owner's ongoing analysis under `~/.moonwalking/analysis`
and from `claude/demote-weak-reads` (`dc4dc97`, not available in this checkout).
It does not replace those results or take over their year-long archive pull.

## Findings

1. **Count the population explicitly.** A market-only, read-only Railway export
   contained 1,042,241 signal transitions across 408 products. Keeping the latest
   transition per product/hour produces 152,589 decisions. Those are different
   populations from the earlier 369,611 reconstructed records in the handoff.
   None of these numbers is a count of independent trades.
2. **The retained hourly table is unsuitable as native OHLC.**
   `backend/volume_1h_store.py:rollup_product_hours` takes the first, maximum,
   minimum, and last *minute closes*. These do not preserve intraminute extremes
   or the actual hourly open. Its `minute_coverage` also counts volume rows,
   which does not prove every row has a valid price. The evaluator rejects this
   source even when minute coverage is 60. This affects research replay, not the
   usefulness of that store for its intended volume calculations.
3. **The four-product pilot does not earn a threshold change.** Real hourly
   Coinbase OHLCV was fetched separately for BTC, ETH, SOL, and DOGE: 9,220
   candles, with the source responses cached. Their 25,236 signal transitions
   become 4,410 hourly decisions. Gross directional four-hour returns and the
   effect of volume filtering change across chronological splits. In the test
   split there are only three measured decisions with confidence at least 85.
4. **Quieter does not establish better.** At a 49-candle lookback and an assumed
   0.90% round-trip cost, 114 of the 4,410 decisions pass the experimental
   geometry and confirmation rules. At assumed 0.20% cost, 192 pass; before
   costs, 205 pass. The smaller candidate cohort does not demonstrate an
   out-of-sample advantage. The cost-dependent cohorts differ, so their mean
   returns must not be compared as though they held the same decisions.

The machine-readable aggregate is
[`trade-hypothesis-pilot-summary.json`](trade-hypothesis-pilot-summary.json).
It includes source hashes, exact sample counts, outcomes by horizon, threshold
comparisons, and the three cost scenarios. It contains no raw account data.

### Four-hour gross directional return: volume-only filter

This table pools up/down hypotheses, using the sign of the recorded direction.
It is an observational cohort comparison, not a replication of the other
session's down-hour volume experiment.

| Minimum volume ratio | Train mean | Validation mean | Test mean | Test n |
|---|---:|---:|---:|---:|
| No volume filter | +0.0397% | -0.0421% | -0.0154% | 810 |
| 1.25 | +0.0103% | -0.0948% | +0.0119% | 394 |
| 1.50 | +0.0332% | -0.1287% | +0.0430% | 307 |
| 1.80 | +0.0165% | -0.0789% | +0.0513% | 249 |

No threshold is selected from these results. Costs shift the fixed-cohort
forward returns by the explicitly supplied assumption; they are not fetched
from the owner's exchange account.

## What the evaluator measures

`scripts/evaluate_trade_hypotheses.py` is never imported by the live app. It
produces a per-decision gzip JSONL ledger and aggregate JSON report.

- **Setup:** preserve the signal's primary state, read label, direction, source
  signal ID, and event ID. These are observed labels, not newly inferred labels.
- **Context:** previous completed BTC 1h/4h returns, a descriptive ATR percentage
  bucket, and the recorded direction. Liquidity is unavailable, not guessed.
- **Confirmation:** separate price-structure and volume families. The price
  family is the sign of the last completed candle's close-to-close change.
  Volume compares its base volume with the median of earlier candles in the
  selected lookback. Different families are not proof of statistical independence.
- **Opportunity:** expose entry, invalidation, target, range position, ATR,
  extension, gross risk/reward percentages, and net reward/risk. A calibrated
  0-100 opportunity score remains null. The existing confidence score is carried
  separately and explicitly marked as not a calibrated probability.
- **Outcome:** 1h/4h/12h/24h directional close returns; assumed net forward
  returns; MFE/MAE in entry-time ATR units; and the first sampled bar touching
  +1/-1 ATR or the structural target/stop. The 15m result is unavailable from
  hourly candles. A missing or malformed candle makes its horizon unavailable;
  a later candle cannot fill the gap.

### Entry and geometry assumptions

The latest transition in each product/hour is selected using only its timestamp
and a deterministic signal-ID tie-break. Entry is the **following hour's native
exchange open**. Even a transition exactly on an hour waits until the next hour.
This evaluates a delayed-entry research policy; it does not reconstruct an
execution at the original signal's price. Filling at the first trade is a
simulation assumption, not a guarantee of executable liquidity.

Only completed candles strictly before the entry hour contribute features.
ATR is the arithmetic mean of the last 14 true ranges and requires at least
15 contiguous hourly candles. The tested support/resistance are lookback-wide
low/high extrema, not an inferred nearest order-book level. Long invalidation
is support minus 0.2 ATR, and the target is the prior resistance; short geometry
is mirrored. Extension is distance from the corresponding range base in ATR.
The short side is an analytical direction and omits funding, borrow costs, and
the availability of short execution on any account.

These formulas are an explicit new research hypothesis, not a replay of the
complete production `sell_side_intelligence.build_sell_plan` implementation.
The action vocabulary is experimental:

| Action | Rule |
|---|---|
| NO_TRADE | Missing input/direction, zero ATR, invalid stop, or net reward/risk below 1 |
| WAIT_FOR_PULLBACK | Valid geometry but extension exceeds 2.4 ATR |
| WAIT | Geometry passes but the price and 1.5x volume families do not both confirm |
| RESEARCH_CANDIDATE | All these unvalidated rules pass |

The threshold grid separately compares confidence 0/65/72/85, volume gate
off/1.25/1.5/1.8, minimum net reward/risk off/1/2, and extension cap off/2.4.
Raw 15/85 range zones appear in descriptive test strata. Lookbacks 24, 49,
and 72 are compared in the 0.90% cost run. These values remain hypotheses.

### Boundary ordering and statistics

When both target and stop lie inside one hourly candle, ordering is
`ambiguous`. An opening gap crossing a boundary has known precedence. Touch
times identify the candle bucket, not an invented exact trade timestamp.
Target-first fraction bounds retain ambiguous and neither-hit cases in their
denominator. MFE/MAE and forward returns describe the full horizon even if a
boundary was touched; they are **not realized strategy P&L**. No stop-limit fill
or target execution is simulated.

The common calendar split is 60% train, 20% validation, 20% test, with a 24h
purge before both boundaries. For this pilot the UTC boundaries are
2026-09-11 13:24 and 2026-09-30 04:12. Of 4,410 decisions, 76 are purged.
The test has 820 decisions, of which 810 have measurable four-hour outcomes and
764 have complete 24-hour outcomes. Recent decisions naturally lack future data.

Exploratory baseline intervals resample UTC-day mean returns, keeping all coins
within a day together. They require at least 20 measured UTC days. The test
contains only 19 days at 4h, so its intervals are null. This simple day bootstrap
does not resolve serial dependence across days. Grid results receive no
intervals and are not corrected hypothesis tests. There are no matched placebo
controls, no independent episode sample guarantee, and no causal edge estimate.
Volatility, direction, setup, action, coin, confirmation family, and BTC-context
strata expose confounding; they do not remove it.

## Reproduce

All three tools use the Python standard library. `pytest` is needed for tests.
Use a clean working directory's ignored `.runtime/research/` for raw data.
The full input and HTTP cache for this run are saved there in this worktree;
they are intentionally not committed to Git.

1. To make another market-only production export, execute
   `scripts/export_trade_research.py --directory /var/lib/moonwalking` through
   the already authenticated Railway SSH connection. The script opens only
   `signal_outcomes.sqlite` and `volume_1h.sqlite` in SQLite read-only mode,
   with query-only transactions. Its stdout is a checksummed gzip/base64
   envelope. It creates no production files or tables. A fresh export is a new
   dataset; the report must retain its new checksum.
2. Save the stdout envelope locally and decode it:

```powershell
python scripts/export_trade_research.py --decode .runtime/research/production-envelope.txt --output .runtime/research/production.jsonl.gz
```

3. Backfill a separate four-product pilot export. HTTP responses are cached,
   requests are sequential with a 350ms pause, windows contain at most 299
   hours, and transient failures back off. Re-running reuses cached windows.
   Neither this tool nor this pilot touches the owner's shared candle archive.

```powershell
python scripts/backfill_research_candles.py --input .runtime/research/production.jsonl.gz --output .runtime/research/pilot.jsonl.gz --products BTC-USD ETH-USD SOL-USD DOGE-USD --cache-dir .runtime/research/coinbase-raw
python scripts/evaluate_trade_hypotheses.py --input .runtime/research/pilot.jsonl.gz --output-dir .runtime/research/results --lookbacks 24 49 72 --fee-bps 40 --slippage-bps 5
```

Fees/slippage are **per side**: those example inputs imply a 90-basis-point
round trip. The other saved runs use 5/5 (20 bps round trip) and 0/0 (gross).
Outputs refuse overwriting an existing report or export.

Coinbase documents candle schema, missing intervals, the 300-candle request
limit, and responses that may precede the requested start in its
[product-candle reference](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).
The backfiller filters outside each requested range and never synthesizes bars.

## Verification and next steps

- 76 relevant tests passed: 28 new research checks plus existing position-level,
  sell-side, signal-outcome, board-outcome, live-ranking, and storage-retention
  tests. Run with `PYTHONUTF8=1`, `PYTHONPATH=backend`, and `-o addopts=''` to avoid
  the sentiment-only coverage configuration in `backend/pytest.ini`.
- Black formatting and `git diff --check` pass.
- Repository guardrails fail on the existing
  `ScorecardPage.jsx` placeholder `BTC or BTC-USD`, which is present at the
  untouched base commit. No frontend file was edited here.
- Full backend/frontend suites and live UI checks were not run: no runtime
  or frontend code changed. The 561-test result on the other branch is the
  owner's handoff evidence, not a result reproduced here.

The next integration should use the original immutable reconstructed dataset
and the other session's expanding archive through an explicit adapter. Add
15-minute/native finer bars, matched controls within direction/volatility/regime,
and more independent calendar periods before selecting thresholds. Preserve
null predictive probabilities and null calibrated opportunity scores until
their calibration is demonstrated. No production gate change is justified by
this pilot.
