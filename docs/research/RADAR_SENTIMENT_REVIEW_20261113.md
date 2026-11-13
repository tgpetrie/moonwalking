# Radar sentiment review dispositions · November 13

The received review is a design proposal. It confirms the code paths in
the [sentiment and Chart Read audit](RADAR_SENTIMENT_AND_CHART_20261113.md)
and the reported [candle screen results](RADAR_CANDLE_RESULTS_20261113.md).
Keep percentage-change ranking. No external data has demonstrated
incremental directional value for the mover boards.

The assignment was distributed as a separate copy-ready prompt with the
packet and manifest. The review reports receiving the packet and manifest
and worked from the audit addendum. Apply the original assignment when
judging whether provider feasibility and the pilot are complete.

## Source checks

| Source | Verified evidence | Disposition |
| --- | --- | --- |
| Existing derivatives context | The sentiment service fetches BTC/ETH positioning across configured venues, averages available funding values after nominal period normalization, and caches the result for 120 seconds. Its cache timestamp is taken before provider requests. Venue availability and input mix can change. | Use the underlying BTC/ETH fields as potential market-regime controls. Retain venue, asset, venue funding interval, upstream timestamp where supplied, and actual local receipt. A cache interval supplies no evidence of provider latency. |
| Hyperliquid perp positioning | A read-only request to `metaAndAssetCtxs` returned HTTP 200 in about 500 ms on the Windows host. It returned 235 instrument contexts, with 173 uppercase alphanumeric, non-delisted candidates containing funding, OI and mark fields. The response has no top-level observation timestamp. Four follow-up polls 20 seconds apart returned HTTP 200 in 250–422 ms. The funding/OI pair for each of BTC, ETH and SOL changed across each successive reply. Exact ticker overlap with the frozen October 28–November 12 ledger was 117 of 406 distinct 3m-up products and 11,151 of 27,828 entries (40.1%). | First candidate for an external positioning feasibility pilot. Ticker overlap gives a rough estimate with asset identity and contemporaneous historical availability still open. The one-minute probe establishes reachability and changing values in that interval. |
| Bybit perp positioning | Public linear tickers are documented with funding and OI fields. The live request from this host returned HTTP 403. | Leave unavailable on this host pending an independently verified usable route. |
| LunarCrush social attention | The code has an optional legacy API adapter. The provider's documented authenticated coin time series uses hourly or daily buckets. Minute-level availability, entitlement and latency for the proposed social measure remain unknown. | Keep as an attention hypothesis. Require a documented feed and measured receipt lag before opening a score study. |
| Official listing announcements | Coinbase currently identifies its asset announcements account as the primary source for listings, delistings and asset changes. | Potential sparse catalyst tag. A documented feed, canonical mapping and announcement-to-receipt lag are open. No current 1–3 minute ranking candidate. |

Hyperliquid documents current funding and OI in the same public context
snapshot. Funding is linked to the perp's premium versus the underlying,
so compare any funding-derived feature with a price comparator for
redundancy. An increase in OI gives leverage participation context. OI
alone does not identify which side initiated exposure.
[Hyperliquid contexts](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals)
[Hyperliquid funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)
[Bybit tickers](https://bybit-exchange.github.io/docs/v5/market/tickers)
[LunarCrush time series](https://lunarcrush.com/api3)
[Coinbase asset announcements](https://www.coinbase.com/blog/update-to-our-asset-listings-announcements)

## One data-only pilot candidate

Start from one public batch endpoint and an explicit, reviewed map from
Coinbase USD product ID to perp instrument. Keep ambiguous tickers and
contract multipliers out of the pilot roster until resolved. Use BTC/ETH
as market controls. For each batch retain request start, receipt after
response, time the parsed values become usable, source identity, raw
funding and OI, and upstream observation time if present. Keep repeated
values and request failures, and record minutes since the last change.
An absent upstream time stays unavailable. HTTP response time measures
transport only. A successful poll does not reset the age of an older
provider observation.

One tangible numeric candidate is the change in `log(open interest)`
over the prior five minutes, using the same mapped contract, valid
positive OI and observations known at decision time. Keep this change
unsigned with respect to board direction. Hypothesize separately that
it identifies higher activity or changes runner versus reversal rates
relative to raw move plus activity. Fixed contract units avoid adding a
mechanical price component through `open_interest_usd`. For a pilot,
measure batch success, stale or unchanged runs, mapping coverage across
original board entries, and the rate of usable causal joins to entries.
Choose the roster, cadence, maximum age, and pass/fail coverage rules
before running a sustained intake pilot. A readiness pilot uses no
runner outcomes.

For a later score comparison, report actual flags, runners captured, both
outcome rates, and missing grades on the same decision universe. A common
rolling percentile and hourly cap can produce different realized counts
with different score distributions and cooldowns. Set calibration and
the treatment of unequal burden before opening the holdout. The earlier
planning sensitivity is sufficient to rule out choosing 28 days as a
default. For a one-point gain at a two-point paired daily SD and
dependence multiplier 1.5, the illustrative requirement was 48 valid
days. Estimate variation with the chosen causal policy and choose one
fixed sample and cap after a data-only pilot. See the
[day-level planning calculation](RADAR_BOARD_RUNNER_SCREEN_20261113.md#independent-step-1-comparison-and-confirmation-sizing).

## Collector and archive status

The always-on collector is still on `ed3e231`. A read-only query found
the v2 board ledger recording through November 13 at 19:13 UTC, with
maximum entry rank 8 and no v3 board table. The v3 research implementation
at `eaf5acf` stores bid and ask, age at local sampling, and observation
time as JSON when a quote is usable. It does not persist a
`spread_bps` column. The extrema window ends at 900 seconds; the
standalone gross-return checkpoints still permit collection slack.
Use these quote samples to measure last-trade versus midpoint sensitivity.
Sparse checkpoint samples cannot show an executable intrawindow path.
The pasted review's rollout proposal remains a proposal. No runtime
change or new outcome study was performed here.

The 497-product archive process was still running during the check.
The SQLite progress row recorded 1,377 requests with zero errors and
zero rate-limit responses. At that point 1,644 window records across
11 products were visible, including in-flight product work. The existing
on-disk manifest describes the completed BTC pilot. Use the wider run's
final manifest once available.
