# Prospective live movers: corrected proposal contract - 2026-10-27

**Status: documentation review complete; collection verification pending.**
This records corrections to the two pasted early-warning proposals and their
review. It specifies a future shadow cohort; it reports no observed edge,
measured lead time, completed feed audit or deployed collection change.

The [historical contract](LIVE_MOVERS_DATA_CONTRACT_20261027.md) and every
artifact under `results/live_movers_contract_20261027/` remain frozen. Their
1m/3m comparison can proceed independently. Do not enrich historical episodes
with future microstructure, change their cooldown or replace their splits
with the prospective rules here. Implementation still needs a versioned
machine-readable contract and the evidence gates below before study collection.

## 1. Evidence and causal boundaries

Inspected: the pasted proposal/review, committed contract at `a936dec5`, its
workplan, `backend/coinbase_ws.py`, and primary Coinbase documentation on
2026-10-27. No live packets or database contents were sampled in this review.
The workplan's 23s median / 110s maximum BTC snapshot gaps are prior bounded
inventory findings, not new measurements. They establish inadequate exact
sub-minute coverage in that store. They do not establish a Nyquist floor or
a natural 30-second market timescale. Claims about typical 10-45s sweeps,
1-2m replenishment, trade counts and 407 currently active products remain
unverified hypotheses or sizing assumptions.

Keep the following timestamps separate:

| Field | Meaning and use |
|---|---|
| `exchange_event_ts_ms` | Message `time`; trade event time on match records. A ticker timestamp does not timestamp every intervening quote change. |
| `server_receipt_ts_ms` | UTC wall-clock receipt time, e.g. `time.time_ns() // 1_000_000`; determines when an input became available. This clock is not monotonic. |
| `receipt_monotonic_ns`, `connection_id`, `receipt_seq` | Local elapsed-time/ordering evidence, including clock jumps and reconnects; monotonic values are not UTC or comparable across restarts. |
| `feature_cutoff_ts_ms` (`t0`) | Frozen scoring cutoff; only observations received at or before this instant may contribute. |
| `board_publish_ts_ms` (`t_alert`) | Actual server publication of the scored row; separate from computation start and browser display. |

Use completed 5s buckets ending at `b = floor(t0 / 5000) * 5000`. Inputs are
the six buckets `[b-30s, b)` and 36 buckets `[b-180s, b)`, with endpoint and
observation-age metadata. At non-aligned publication times, record `t0-b`;
do not call the inputs exact windows ending at publication. Forward outcomes
start strictly after `t_alert`, for 5m and 15m. Never use messages received
after `t0` merely because their exchange timestamps precede it.
Invalidate buckets affected by a backward wall-clock jump; receipt ordering
must also agree with the connection's monotonic clock and sequence.

Only use closed baseline candles whose end time and first availability time
are both at or before `t0`. Define the 60m volatility baseline from prior
closed 1m log returns, with a declared 0.0015 per-minute floor. Record the
floor flag, sample count and source timestamp; this is a candidate scale,
not a distributional guarantee. Beta must also be available at `t0`; a
default of 1.0 requires an explicit fallback flag.

**Onset, future retention, peak time and fraction of move consumed are
evaluation labels only.** The proposal's "without later retracing" test
necessarily reads future prices. None of these fields may feed a live
feature, stage, eligibility gate, fitted-input column or universe selection.
The evaluator must freeze a direction-symmetric onset algorithm, search
interval, tie rule and horizon before fitting; the pasted onset description
alone is not a complete executable labeling algorithm. For downside labels,
use signed favorable excursion rather than an upside-only no-retrace test.

## 2. Channel responsibilities and the required side/coverage audit

Use Coinbase **Exchange** `wss://ws-feed.exchange.coinbase.com`, not Advanced
Trade or an international feed with differently defined fields.

| Input | Authoritative prospective source | Treatment |
|---|---|---|
| Trades, counts, USD volume | `matches` channel, `type == "match"`, `price * size` | Deduplicate by `(product_id, trade_id)`; never sum ticker `last_size` as complete volume. |
| Taker buy/sell USD | Exchange match maker `side` | `sell` maker -> taker buy; `buy` maker -> taker sell. Preserve raw side and mapping version. |
| Observed L1 quotes and sizes | `ticker` bid/ask and sizes | Sampled BBO observations; not every book change. Retain observation ages. |
| Coverage evidence | `heartbeat`, per-product trade IDs, connection/subscription state | Track missing, duplicate, reordered and delayed messages. |

The [Exchange channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels)
documents ticker batching and match maker-side semantics. Its ticker example includes `side` but does
not establish its meaning. Do not apply the match inversion to ticker by
assumption, or assert the opposite interpretation without packet evidence.
The existing `TickerStore.update_market()` inverts ticker side and labels
coverage `coinbase_ticker_sample`; it already retains sampled quote/flow
context in memory. Persistence and complete trade coverage are the gaps.
Do not silently relabel that existing sample as verified taker flow.

**Step 2.5, required before step 3:** retain `ticker`, `matches` and
`heartbeat` together for at least one uninterrupted hour, spanning liquid
and thin USD products. A diagnostic capture must not start another backend
or interfere with the always-on collector. Freeze its product list and
record endpoint, subscription acknowledgments, UTC start/end, reconnects,
parser errors and local queue/drop counters.

Join ticker and match records by **both** `product_id` and `trade_id`, allowing
arrival reordering. For each product report:

- Unique match and ticker trade IDs, intersection, unmatched counts, duplicate
  counts and the count/volume represented by ticker relative to matches.
- A side cross-tab for identical trades, plus price/size discrepancies.
  Preserve both raw sides. Equal sides support maker semantics for ticker;
  opposite sides support taker semantics. Report both maker sides separately.
  Missing overlap, one-sided samples or contradictions are inconclusive;
  extend the audit rather than choosing a mapping by majority vote.
- Heartbeat last-trade-ID watermarks versus received match IDs, missing
  ranges, reorder delay and disconnect intervals. Reconcile suspected gaps
  with paginated Exchange REST trades; retain the comparison manifest.
  Do not interpret nonconsecutive full-feed sequence numbers on a filtered
  channel as a count of missing trades.
- Mapping verdict and an explicit coverage verdict for each interval/product:
  reconciled, incomplete or unverified. Publish the raw-capture hash and
  deterministic summary so another reviewer can reproduce the verdict.

**`matches` is not lossless.** The [matches-channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels#matches-channel)
warns of drops and recommends heartbeat tracking and REST recovery. The first `last_match`
message is a subscription snapshot, not a newly observed execution: use it
as a watermark, never add it to the current bucket. Continuous monitoring
and deduplication remain necessary after the hour-long audit.

Subscribing to extra channels on the existing socket needs no per-trade
REST polling. It increases feed traffic; REST reconciliation/backfill does
add requests. A strict zero-extra-REST mode must mark unresolved intervals
incomplete and withhold flow-dependent features rather than claim coverage.
The one-hour check establishes evidence for that sample, not a guarantee for
future trades or all products.

## 3. Five-second storage, reconstruction and freshness

**Choose sparse persistence and reconstruct logical empty buckets on read.**
Write a `micro_bars_5s` row when a unique match or a ticker observation is
received, including unchanged quote observations needed to retain freshness.
Use receipt-time buckets `[start, start+5000)`. Alongside the sparse table,
retain subscription membership and feed-health intervals so an absent row
can be distinguished from collector downtime. No reconstruction across an
unverified interval is permitted.

Minimum row/provenance fields:

- Canonical `product_id`, `bucket_start_ts_ms`, first/last receipt times,
  last exchange event time per source, connection/receipt ordering fields,
  and first/last match trade IDs with coverage status.
- Observed midpoint OHLC, last trade price, last observed bid/ask and sizes,
  spread, quote observation time, last live-match receipt time, and
  `seconds_since_last_trade` / `seconds_since_last_quote` separately.
- `trade_count`, `quote_vol_usd`, `taker_buy_usd`, `taker_sell_usd`, all from
  unique live match executions. Unknown sides require an unknown-side amount
  and unavailable F2; do not force a two-way split.
- `price_source` (`mid`, `last_trade_fallback`, `unavailable`), fallback
  reason, observed/carried flags, quote validity, endpoint ages, feature
  coverage and whether any source or connection gap affects the window.

Within a continuously verified healthy interval, reconstruct a missing 5s
row with zero observed trades/volume and carry the prior quote state and its
**original** observation timestamp. Do not create a new trade, fresh quote
or observed OHLC path. Carried midpoint values describe last-known state.
Missing rows during downtime are unknown, not zero-volume observations.
Completeness verdicts can arrive later; retain the verdict known at `t0`
and any later audit verdict separately. Never rewrite a published feature.

For primary 30s/3m midpoint features, require valid positive non-crossed BBO
at each return endpoint, quote age <=10s at each endpoint, continuous feed
coverage across the window, and at least one unique live match in it. Record
the true endpoint ages. This replaces the loose proposed +/-10s reference
search. Midpoint-path features also require valid quote coverage throughout
their calculation. An `IGNITING` candidate additionally needs >=5 matches
in its 30s window; a volume multiple alone cannot let one print pass.
These fixed candidate gates may exclude thin coins; report that coverage.

If only a last trade is available, retain it with `last_trade_fallback` on
that row and propagate the flag to affected features. Exclude such rows
from the primary midpoint acceleration/decay cohort and report a separate
fallback cohort. Do not mix sources or treat a missing spread as zero.
Ticker-derived OBI averages are time averages of last-observed BBO state,
with stale durations marked unavailable; six endpoint snapshots do not
establish a continuously observed book. A future L2 feed would be a separate
versioned source change.

Late WS matches belong to their actual receipt bucket. Recovered REST trades
need `recovery_receipt_ts_ms` and exchange-time attribution in a separate
reconciliation record. They may repair an offline coverage audit, but must
not retroactively enter an earlier live bucket or inflate the recovery
instant's trading pace. Windows with unresolved earlier gaps stay ineligible
for complete-flow features at the original cutoff.

### Storage budget and retention

Sizing assumes **407** products; use actual subscription counts in reports.
There are 17,280 possible buckets/product/day, or **7,032,960 dense rows/day**.
At an illustrative 80 bytes/row this is **562.6 MB/day** before index, WAL and
other overhead (3.94 GB/7d). The 80-byte assumption has not been measured and
is optimistic for this richer schema.

At an equally unverified **15% sparse occupancy**, the count is 1,054,944
rows/day and **84.4 MB/day** at 80 bytes/row (590.8 MB/7d), before overhead.
Quote observations can increase occupancy. The 84 MB figure applies only
to that sparse assumption; it cannot budget dense carry-forward writes.
Measure database, index and WAL bytes/day during the pilot and freeze a
disk limit before expanding the universe. These are decimal MB/GB.

A proposed 7-day rolling `live_microstructure.sqlite` is only the live cache.
Preserve immutable daily shadow partitions/captures covering **all 14 study
days**, baseline warmup and final 15m label maturity before rolling deletion.
Budget that archive separately (at the same illustrative sparse size, 14d
alone is 1.18 GB before overhead/copies). Keep public raw captures outside
Git and commit their hashes/manifests. Do not touch `candle_archive.sqlite`.

## 4. Correct the smoothing math and keep feature hypotheses separate

Keep raw 30s and 3m percentage-return columns available for interpretation.
For smoothed candidate inputs use an **unnormalized decayed sum of log-return
increments**, per product, with fixed half-lives `h = 30s` and `h = 180s`:

```text
delta = 5 seconds; q_h = 2 ** (-delta / h)
x_i,j = log(mid_i,j / mid_i,j-1) - beta_i * log(mid_BTC,j / mid_BTC,j-1)
S_i,h,j = q_h * S_i,h,j-1 + x_i,j
decayed_move_sigma_i,h,j = S_i,h,j / sigma_i,1m(t0)
```

Use synchronized valid midpoint endpoints and beta known before the
increment; unavailable BTC/beta provenance makes the residual unavailable.
The denominator is that coin's causal one-minute baseline volatility, with
the declared floor. This is a scaled move, not a calibrated Gaussian z-score
or a claim of equal variance across half-lives. Any feature scaling for a
fit is learned on discovery only and frozen before validation.

There is **no leading `lambda = 1-q` multiplier and no unit-sum
normalization**. Those produce a weighted average increment rather than a
decayed cumulative move. For an isolated 0.02 log-return impulse, its weight
at age 30s with a 30s half-life is 0.500, at 31s it is 0.48858, and at 35s
it is 0.44545. The contribution is respectively 0.01000, 0.00977 and 0.00891
in log-return units. The 31s value describes continuous exponential decay;
closed-bucket observations still update every 5s.

Maintain the state independently per coin and half-life. Warm up for at
least ten slow half-lives (30m) plus the required baseline history. A true
no-trade bucket with valid observed price state can contribute a zero
increment; an unknown/stale interval cannot. Reset or mark state warming
after such a gap and satisfy warmup again. Never bridge a missing interval
with a newly received multi-minute return presented as a 5s impulse.

F1-F5 remain candidate mechanisms; their independence and usefulness are
unproven. The source/interpretation corrections apply as follows:

| Feature | Corrected dependency / interpretation |
|---|---|
| F1 acceleration | Midpoint returns over non-overlapping 30s and preceding 150s, normalized by per-coin baseline; flagged trade-price fallbacks are excluded from the primary cohort. |
| F2 signed participation | `TakerImb * log(1 + PaceRatio)`, gated on >=5 unique matches. Imbalance uses match-derived buy/sell USD; pace uses prior completed matched-volume windows. Historical 1m candle volume is not measured 30s taker flow. |
| F3 book pressure | Valid observed ticker BBO/sizes and spread, with observation ages and time weighting; no claim to full-book coverage. Optional perp data cannot substitute for missing required spot features. |
| F4 compression | Prior closed, already available candle history; require >=10 traded candles in the prior 15 completed minutes. Missing or late-fetched candles cannot become earlier features. |
| F5 market residual | Coin and BTC endpoints at the same causal cutoff, with beta provenance; a beta fallback remains visible. |

Freeze exact formulas, minimum baseline sample counts, missing-feature
policy and model inputs in the implementation contract. Do not automatically
add both decayed sums as extra fitted predictors beyond the declared five,
or choose between smooth and boxcar variants using test outcomes.

## 5. Extension, stage, score and reliability

Keep `score_0_100` (ordinal), `direction`, `stage`, `reliability`, input
windows and forward horizon as separate fields. Missing required evidence
produces an unavailable score and reason, not a fabricated neutral 50.
Feature coverage means measured feature coverage, not a count of connected
vendors; an optional missing perp feed does not automatically remove F1-F5.

For this prospective candidate retain the proposal's extension definition:

```text
E = abs(r_15m) / (sigma_1m * sqrt(15))
  + abs(r_60m) / (sigma_1m * sqrt(60))
```

This is a sum of two overlapping standardized lookbacks, not the number of
standard deviations of one independent return. Use causal midpoint prices
and declare missing extension history unavailable.

**`EXTENDED` is a hard exclusion from early-warning eligibility**, before
percentile ranking. For the candidate, `E > 3.5`, or an absolute daily move
`>10%` with measured trailing daily USD volume `<$1M`, sets `EXTENDED`. Missing
extension/liquidity data must not be treated as proof of eligibility. Stage
precedence is `EXTENDED`, then `FADING/ABSORBED`, then `CONFIRMED`, then
`IGNITING`; otherwise stage is unclassified. `E == 3.5` is not extended
by the E gate. Only complete-data `IGNITING` / `CONFIRMED` candidates enter
the early board, in separate UP/DOWN cohorts. Extended/fading rows may be
retained in shadow diagnostics or a separate risk-context view.

The original soft damper `exp(-max(0,E-3)^2/8)` retains 60.7% at E=5 and
32.5% at E=6 and cannot ensure exclusion. Dividing by 2 would retain 13.5%
and 1.1%; that remains a different hypothesis. The hard stage gate is the
chosen policy here. Do not infer the AURORA mockup's score of 18 from either
formula, or add another penalty/threshold search to this pilot.

Exact stage thresholds other than the extension/activity gates must be
frozen before fitting. Stage names do not establish "<30% of the move
elapsed"; that quantity requires future labels and cannot define live stage.

## 6. Fourteen-day shadow protocol and uncertainty

Run shadow logging for **at least 14 valid collection days before any UI
sort/ranking change**. Keep the window pair and decay half-lives fixed at
30s/180s. Do not search the proposed 4x3 window grid while also estimating
five feature weights for each direction on the same discovery week.

- Days 1-7: discovery/calibration of the declared regularized five-feature
  model, with all scaling, regularization choices and missingness rules
  recorded. Purge decision times in the last 60m before the next phase.
- Days 8-14: validation once, after code, weights, universe policy and
  decision thresholds are hashed and frozen. Labels must mature before
  analysis. No retuning after seeing these results.
- Fourteen days is a pilot, not evidence that two five-weight fits have
  enough independent episodes or market regimes. Set readiness minima in
  the machine-readable contract before fitting; insufficient evidence
  requires more collection, not relaxed minima or reuse of validation.
- If window tuning is later needed, preregister a separate experiment with
  a fixed scoring rule and fresh validation period. Neither the sampled
  snapshot gap nor human-friendly UI labels select an optimal timescale.

At each shadow publication retain the contemporaneous eligible universe,
all three rankers (percentage move, current live strength, candidate), raw
features, exclusions, source timestamps, model version, direction, stage
and reliability. Compare on identical complete-data universes/timestamps;
also report each ranker's natural coverage so exclusions remain visible.
Retain all eligible products, not just top entries, for missed-move metrics.

Use first Top-K entry, primary K=5 and descriptive K=10, with a 15m per-coin
cooldown shared across the prospective boards. Keep discovery and validation
episodes separate. A cooldown does not make different products, boards or
alerts in the same market episode independent; timing slack can also extend
outcome windows. Do not carry this policy into the historical contract.

Retain lead time to favorable peak, onset-to-publication delay, signed
fraction of move already consumed, false alerts/hour and missed-move rate,
separately by direction and 5m/15m horizon. Onset and verified impulses are
retrospective labels only. Freeze impulse magnitude, retention, minimum
trades, observation slack and cost rules before labels are inspected. A
last-trade grade or three observed trades does not certify executable fills.
Use gross outcomes plus declared spread/fee scenarios; never deduct costs
again from an already-net stored return.

For intervals, bootstrap **paired UTC-day blocks**, retaining all products,
boards and rankers together in each sampled day. Report episode counts,
distinct days, effective blocks and missingness. Seven validation days
provide only seven day blocks; intervals will be fragile. Naive per-alert
standard errors or binomial confidence claims are not acceptable. A boundary
purge prevents cross-split labels; it does not remove within-phase dependence.

Every mockup score, trade count, volume multiple, "historical fade" and
20-35% versus 65-90% move-consumed figure in the pasted proposal is
**illustrative or a hypothesis, not measured Moonwalking performance**.
Never publish an invented historical warning such as AURORA's -6.5% fade.

## 7. Implementation checklist and acceptance evidence

- [ ] **1. Preserve frozen experiments.** Leave historical manifests,
  JSON contracts, research DBs and daily/fundamentals work unchanged.
- [ ] **2. Review/apply board-retention parity through a runtime handoff.**
  The actual `build_live_rankings()` fix is already committed at `080f124b`
  in the parent contract branch. Verify deployment separately; do not repeat
  the fix or claim the running collector has it. Preserve missing numeric
  inputs and provenance; do not rewrite legacy categories or old snapshots.
- [ ] **2.5. Verify taker-side semantics and match coverage.** Complete the
  >=1h ticker/matches/heartbeat capture and reproducible per-product
  cross-tab/coverage report from section 2. Inconclusive remains pending.
- [ ] **3. Separate sources in the recorder.** Use `matches` for deduplicated
  counts, `price * size` and maker-inverted taker amounts; use `ticker` for
  sampled BBO. Handle `last_match`, reconnects, heartbeats and recovery.
- [ ] **4. Add sparse 5s buckets and read-time reconstruction.** Freeze the
  machine contract, eligibility ages, health intervals, source flags, disk
  budget and study archive before recording. Verify no-trade versus outage,
  duplicate/reordered trades, stale quotes, fallback prices, clock jumps,
  late recovery and causality at cutoffs. Check decayed-sum impulse/decay
  behavior and that `EXTENDED` cannot rank on the early board.
- [ ] **5. Shadow-log F1-F5 for >=14 valid days.** Preserve baselines and
  exclusions, keep windows fixed, fit on discovery only and evaluate once
  with paired day-block uncertainty. A visible ranking change remains a
  later decision based on measured prospective results.

No checklist implementation or live-audit item is marked complete by this
documentation change. The concrete next deliverable is the side/coverage
diagnostic and its captured evidence.

## Primary source references

- [Coinbase Exchange WebSocket channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels):
  ticker batching/schema; matches/`last_match`; maker side for match;
  heartbeat watermarks; match drops and REST recovery.
- [Coinbase Exchange WebSocket overview](https://docs.cdp.coinbase.com/exchange/websocket-feed/overview):
  public endpoint, subscriptions and loss/out-of-order caveats.
- [Coinbase Exchange REST product trades](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades):
  trade IDs, maker-side definition and pagination for reconciliation.
