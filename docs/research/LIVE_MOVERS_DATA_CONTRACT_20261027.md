# Live movers: frozen contract and retention fix — 2026-10-27

**The contract is published and the production-backup cohort passes readiness.**
The missing board metadata is fixed and regression-tested on a separate branch
based on `runtime/collector` at `ed3e231`. The running collector and dashboard
have not been changed; the fix takes effect for new rows after deployment.
No forecast has been fitted and no outcome performance has been calculated here.

**Prospective proposal review (2026-10-27):** the pasted 30s/3m early-warning
proposal is a separate, future cohort. Its corrected collection, smoothing,
eligibility and evaluation rules are in
[`LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`](LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md).
That addendum requires an hour-long `ticker`/`matches`/`heartbeat` audit before
micro-bar implementation. It does not amend the frozen historical JSON
contracts, eligible episodes, hashes, model comparison or date splits below.

Claude can build the separate short-horizon driver against the exact artifacts
below. Keep the daily/fundamentals experiment on its own branch. Its remote tag
`research/fundamentals-driver-2026-10-26` was verified to dereference to `058d740`;
this checkpoint does not approve that separate comparison driver.

## Authoritative inputs

- [`CONTRACT_PRODUCTION.json`](results/live_movers_contract_20261027/CONTRACT_PRODUCTION.json): episodes, timing, features, minimum history and date splits.
- [`COMPARISON_SPEC.json`](results/live_movers_contract_20261027/COMPARISON_SPEC.json): fixed comparison, model forms, primary statistic and reporting.
- [`PRODUCTION_CAPTURE_MANIFEST.json`](results/live_movers_contract_20261027/PRODUCTION_CAPTURE_MANIFEST.json): exact frozen research DB/eligible-list hashes.
- [`PRODUCTION_COVERAGE.json`](results/live_movers_contract_20261027/PRODUCTION_COVERAGE.json): readiness, rejection counts and non-null features by UTC day.
- [`STRATUM_COVERAGE.json`](results/live_movers_contract_20261027/STRATUM_COVERAGE.json): phase/board/direction counts.

The immutable capture on this PC is
`C:\Users\tgpet\.moonwalking\analysis\live_movers_contract_20261027_production\`:
`board_episodes.sqlite` (`episodes` table), `eligible_episodes.csv`, its copied
data contract, and `MANIFEST.json`. Every file is SHA-256 recorded and read-only.
Raw public-market records stay outside Git. Git carries their manifest and the
complete contract. Use the CSV's `id` to join to the **same frozen DB**, not the
running ledger or another backup's integer IDs.

## Why production is the primary cohort

The first consistent capture of the local ledger retained 90,518 episodes before
2026-10-27 00:00 UTC. Despite its calendar span, eligible training covered only
six days and discovery only one. It **fails** the unchanged 21/7/14-day minimums.
Its capture and [`COVERAGE.json`](results/live_movers_contract_20261027/COVERAGE.json)
are preserved. It is not merged with production or used to fill production gaps.

Before inspecting any outcome magnitudes, amendment 1 selected the existing
production backup `prod-backup/20261018-0109/signal_outcomes.sqlite`, using its
last complete UTC day as the decision cutoff. The minima, feature rules and
episode policy were retained. `freeze_live_contract.py` copied 495,539 rows
under an explicit read-only SQLite read transaction, preserving their values.
The readiness report uses feature/label **availability**, not return values.

| Phase | Decision dates, UTC | Eligible episodes | Observed days | Products |
|---|---|---:|---:|---:|
| Train | 2026-07-19 to 2026-09-26, with end purge | 217,302 | 40 | 192 |
| Discovery | 2026-09-27 to 2026-10-03, with end purge | 38,764 | 7 | 119 |
| Historical validation | 2026-10-04 to 2026-10-17 | 77,104 | 14 | 205 |

All three strata (`ignition_1m/up`, `confirmation_3m_up/up`,
`confirmation_3m_down/down`) cover every reported observed day in their phase.
Snapshot fields start on **2026-08-18**; earlier rows are not invented or filled.

**Historical limitation:** earlier research examined overlapping dates and may
have inspected these outcomes. This is a locked historical comparison, **not an
untouched holdout**. Fourteen validation days also give limited regime coverage.
Fresh prospective confirmation after a model freeze is required for any live
release. Row count alone is not independent evidence.

## Episode, identity and timing rules

1. The unit is a persisted board-entry episode, identified by frozen DB `id`,
   `board`, canonical `product_id`, `direction` and `entered_ts`. It describes
   the first **server board observation**, not the user's browser impression.
2. Existing board tracking records top-eight membership and normally permits
   re-entry one hour after exit. Historical environment settings were not
   retained, so do not assume those settings prove every old episode's spacing.
   Apply an additional deterministic rolling **3,600-second entry cooldown per
   `(board, product_id)`**, keeping the earliest record before checking feature
   completeness. Never select a later, more complete duplicate instead.
3. Keep board/direction strata separate. Same-coin appearances on different
   boards are not independent replications. The primary test is
   `confirmation_3m_up/up`; other strata are secondary and reported separately.
4. Preserve exact historical USD product IDs, including delisted products. No
   mapping from today's listing universe, symbol renaming, RNDR/RENDER or
   JUP/JUPITER splicing is allowed. The study does not join external token data.
5. `captured_ts` must be present, no later than entry and at most **60 seconds**
   before entry. It is the ranking computation start, not proof of the last
   exchange trade's freshness or of an atomic cross-store observation.
6. Eligible snapshots have `live-strength-v1-snapshot-v2` and model
   `live-strength-v1`; version 3 forward captures are a different cohort.
7. Split intervals are start-inclusive/end-exclusive. Remove **30 minutes**
   before the next phase boundary so 15-minute labels and observation slack
   cannot straddle training/discovery or discovery/test.

## Features and labels

| Field | Availability in this production capture | Phase-1 treatment |
|---|---|---|
| `pct_1m`, `pct_3m`, `volume_change_1h_pct` | Recorded from Aug 18 through Oct 17; daily counts in the report | Required finite values; reject missing rows |
| Stored `live_score`, board `start_change_pct` | Retained entry-time baselines | Compare current score and displayed move ranking on identical eligible episodes |
| `pct_1h`, `trend_streak` | Partially populated over the same period | Profiled, excluded from the primary formula; complete-case secondary comparisons rerun all baselines on that same subset |
| Quote-volume USD and realized-volatility numeric metadata | Zero non-null board values in the production capture | Forward-only after the retention fix; never retroactively fill old snapshots |
| Liquidity/pressure/market-relation categories | Defaults and measurements not fully distinguishable in old snapshots | Excluded from primary features; neither `normal` nor `neutral` proves measurement |
| Spread, numeric taker delta, market-relative return | Point-in-time numeric coverage not established | Excluded from this first experiment |

Snapshot `raw_inputs` are authoritative; do not reconstruct missing features
from later APIs. Historical 1m/3m fields are nominal past-return features: their
exact baseline ages were not stored, so a derived acceleration is a nominal
proxy, not a verified exact wall-clock interval. The fixed primary model uses
only the three required inputs and its declared nonlinear transforms.

Both `gross_return_5m` and `gross_return_15m` must be finite for the common
cohort. This is a label-observability rule, not conditioning on their sign or
size. The primary target is five-minute gross directional return; 15 minutes
is secondary. Existing last-trade grades do **not** certify executable fills
or per-checkpoint latency. Record these limits in every result.

Use the frozen gross fields for the cost scenarios (0.2/0.5/0.9/1.2% round trip).
Stored `return_*` fields have estimated costs already deducted: do not subtract
them again. Historical bid/ask bounce is a plausible confound, not a measured
explanation of the earlier score's negative relationship. No profitability or
short-selling claim follows from the downside board's directional labels.

## The 30-second ruling

**Exclude 30-second inputs from this historical comparison.** The local price
tape retains roughly one day at irregular intervals; the archived candles are
60s/3600s. They cannot establish a long, exact sub-minute event history. A refresh
timer is not a return window and an OHLC bar does not reveal its internal path.

A prospective 30-second feature is possible only after retaining sufficient
event/receipt timestamps, price source and baseline-age/coverage information.
Its allowed endpoint ages and storage budget must be frozen before collection.
No interpolation or retrospective synthetic 30-second series is permitted.
This task does not start another collector or change retention on port 5003.

## Retention-path fix and regression evidence

The actual function is `build_live_rankings()`. The board call already passed
price, volume, context and alerts; it omitted only the optional matching maps.
It now reads `realized_volatility_by_product()` and
`latest_quote_volume_by_product()` at **the board calculation's own timestamp**,
then supplies both maps. It does not reuse the earlier signal sample.
Each provider failure degrades independently to missing metadata.

`live_ranking.py` adds the hourly quote-volume bucket timestamp and
`context_input_supplied` flags in **snapshot v3**. Supplied means a non-null
context field was passed; it does not by itself certify an actual measurement.
Legacy scoring defaults remain compatible while their provenance is explicit
for future research. New fields stay in `raw_inputs` and are stripped from the
public payload. Model version and score weights remain unchanged.

Tests execute the **actual board call-site statements**, check provider times,
store and reread the board snapshot, and verify original snapshots remain
immutable on later observations. An integration case uses real temporary
price/volume stores and their real provider functions. Missing/failing provider
cases retain nulls. Published rankings, scores, data quality and payloads match
the pre-enrichment calculation.

The running collector still uses its current checkout; this tested branch has
not been deployed or used to repair historical rows. Apply the patch through a
reviewed runtime update, preserving that worktree and following its service
handoff. Do not run a second backend on its port.

## Source-audit reconciliation

The new Gemini attachment is retained as `SOURCE_AUDIT_SUBMISSION.md`; its claims
are evidence candidates, not instructions. Its closed-bin and historical
microstructure cautions are useful. Several statements need qualification:

- The code has in-memory quote/trade context in `coinbase_ws.py`; it does not
  simply discard every quote or side. Persistent historical coverage is the
  separate missing piece.
- Coinbase documents maker-side semantics for Exchange `match` and REST trades;
  do not automatically generalize a channel's interpretation to a differently
  named API. [Exchange channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels),
  [REST trades](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades).
- Exchange `ticker_batch` has the same schema as Exchange `ticker`; Advanced
  Trade is a different feed. Coinbase describes L2 REST as the **full aggregated
  book**, not a guaranteed top-50-level response.
  [Exchange channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels),
  [product book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book).
- A closed historical candle is causally settled, but is not proof that the
  application fetched it before that episode. Candle enrichment is outside
  this first frozen comparison. One candle's close and the next candle's open
  also need not be equal.

## Claude's concrete next step

Build the separate driver now, using the **production** contract and capture,
not the failed local cohort or a mutable live ledger. The fixed comparison is:
percentage-move baseline, current live score, a regularized price/volume model,
and its declared nonlinear extension. Select regularization on discovery,
freeze inputs/code and run the historical validation once. The JSON comparison
spec defines the exact primary statistic, 0.02 minimum effect, uncertainty and
ordinal 0–100 score mapping. A score is not a probability.

Refuse fitting if the capture hashes, eligible-row identity, readiness,
contracts or required feature schema differ. No comparison code needs to wait
for the forward retention fix to be deployed: the primary historical features
are already present. The richer forward cohort must be evaluated separately.

Outcome performance, fundamentals-driver approval, live deployment and any
change to dashboard ranking remain separate work. This checkpoint delivers
the missing trace, tested fix, frozen episode/data rules and 30-second ruling.
