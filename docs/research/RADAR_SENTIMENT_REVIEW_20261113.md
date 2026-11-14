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

## Revised Gemini review · November 13

The second attachment traces the major code paths and proposes an
attention score, a catalyst feed and a prospective study. This review
checked the proposal against the assignment, provider documentation,
Moonwalking code, and both exploratory candle screens. The provider
checks below use documentation and the earlier Hyperliquid probe. They
supply no measured arrival lag for a news or social feed.

| Candidate | Verified | What a data pilot must establish |
| --- | --- | --- |
| LunarCrush attention | The legacy adapter uses a v2 URL and a query key. The current API documents v4 with bearer auth. The v4 coin-list batch publishes `social_volume_24h` and response generation time. Its documented schema lacks a matching rolling 60m post count. The coin history endpoint uses hour/day buckets. The provider advertises $1 per 1,000 requests. | Identify an accessible like-for-like 60m and 24h feed, including exact coin roster and request count. At one request every two minutes the illustrative cost is $0.72/day for that request pattern. The price of obtaining both score inputs is unknown. Measure first availability and local receipt for the metric itself. [API reference](https://lunarcrush.com/api3) · [Provider pricing](https://lunarcrush.com/) |
| Santiment attention | The restricted `social_volume_total` series has five-minute buckets. Santiment reports a 10-minute median and 20-minute P95 end-to-end availability for Social Volume. Free and Pro API access to restricted metrics excludes the latest 30 days. The default social version can receive late data for up to 12 hours after a bar closes. | Existing evidence supports research on slower attention context. A retrospective completed bucket cannot establish what the 1m or 3m board knew at entry. [Metric](https://academy.santiment.net/metrics/social-volume/) · [Latency](https://academy.santiment.net/metrics/details/latency/) · [Access and revisions](https://academy.santiment.net/sanapi/historical-and-realtime-data-restrictions/) · [Plans](https://academy.santiment.net/products-and-plans/sanapi-plans/) |
| News and events | Coinbase names `@CoinbaseAssets` as its official asset-announcement channel. CoinMarketCal documents an authenticated calendar with scheduled or estimated dates. CryptoPanic documents authenticated HTTP polling and RSS. Tree News publishes a public news page. | Confirm a permitted ingestion route, canonical asset mapping, event count, coverage and local arrival time. Tree News free WebSocket access and latency, CryptoPanic Pro WebSocket access, and the claimed catalyst coverage and price reaction times remain unverified. [Coinbase](https://www.coinbase.com/blog/update-to-our-asset-listings-announcements) · [CoinMarketCal](https://coinmarketcal.com/developer/docs/events) · [CryptoPanic](https://cryptopanic.com/developers/api/) · [Tree News](https://news.treeofalpha.com/) |
| Hyperliquid positioning | The public batch probe above remains the strongest local access evidence. Funding is tied to the perp premium, and outstanding contracts count both sides. The app currently selects BTC and ETH from the batch. | Use the original OI units with an explicit contract map to test a five-minute change. Measure usable joins to original board entries, failure and stale runs. The earlier ticker overlap was 40.1% on 3m gainers, prior to identity checks and freshness filtering. [Context API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals) · [Funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) |

### What to measure

- **Attention.** The example ratio `(posts_60m + 1) / ((posts_24h -
  posts_60m) / 23 + 1)` gives 1.00 and 6.33 for the two synthetic rows.
  It requires the same counting unit and source population, aligned
  windows, and `0 <= posts_60m <= posts_24h`. Retain absolute counts and
  measure polarity separately. A vendor sentiment value weighted by
  engagement can react to the price move. Galaxy Score and AltRank
  already use market inputs. The daily BTC Fear & Greed index can
  describe market regime and its provider lists surveys as paused.
  [LunarCrush definitions](https://lunarcrush.com/api3) ·
  [AltRank methodology](https://lunarcrush.com/metrics/altrank) ·
  [Fear & Greed methodology](https://alternative.me/crypto/fear-and-greed-index/)
- **Catalysts.** Preserve the originating announcement ID, canonical asset
  and product IDs, announcement and effective times, vendor publication
  time where known, local receipt, and when the parsed record first becomes
  usable. Deduplicate syndication and revisions against that original
  event. Distinguish no event observed from feed or mapping unavailable.
  Use historical timestamps to inventory events and prospective receipt
  to test lead time.
- **Chart and volume.** The hourly Chart Read uses the last candle close,
  including the returned last row in its range. The route supplies no
  completed-bar check. A pre-impulse chart comparator needs its own
  completed-bar cutoff and explicit allowance for availability. Historical
  chart results cover specific level and volume-profile tests. Step 2
  tested candle features and supplies no result for market cap or
  community size. Running the pasted Live Strength example with no alerts,
  missing streak for A and streak 2 for B gives 78 and 87. A's reliability
  is 0.83. The example is synthetic and the score describes the tape.
- **Dollar activity.** Claude's independent Step 2 reported 3.94% sustained
  reversals versus 8.48% for the raw-move flags on 3m gainers in its check
  window, with 3.33% runners versus 3.77%. The score multiplied estimated
  three-minute dollar activity by observed candle density. The full-day
  flag quota and treatment of missing bars limit the inference. Coinbase
  documents both no-tick omissions and potentially incomplete history.
  Carry the result forward as a possible reversal filter.
  [Published Step 2 report](https://github.com/tgpetrie/moonwalking/blob/ade1694ec52cae31a8ef59f8e71d6755c82964e0/docs/research/RADAR_RUNNER_CANDLE_SCREEN_RESULTS_20261113.md)
  [Coinbase candle behavior](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)

### Before a confirmation freeze

1. Choose the candidate after an outcome-blind readiness pilot. Use the
   same eligibility, quote policy and cooldown in both arms. Compare the
   addition to a causal price-and-activity baseline, and report raw move
   separately. A rolling seven-day 75th percentile in each arm can produce
   unequal flag counts. Calibrate the live rule and specify the tolerated
   burden difference and how to handle it before opening the holdout.
   Treat score correlation with volume as a diagnostic.
2. Report natural and matched coverage, flag counts, sustained runner
   precision and recall, sustained reversal rate, and missing grades.
   Use the same outcome eligibility for both arms, including an explicit
   policy for the 30m leg, gaps and actual checkpoint offsets. Keep
   valid zero-runner days. Retain timestamps for quote age and compute
   spread from the stored bid and ask. Last-trade versus midpoint or
   sampled ask-to-bid sensitivity can quantify a spread effect. The
   sampled quotes provide no intrawindow quote path or realized fills.
3. Size the fixed window for the chosen policy and joint success criteria.
   The pasted power formula gives 27 days at a 1.5-point daily SD and
   48 days at a 2-point SD for a 1-point lift versus zero, using its
   dependence assumption. Neither calculation gives power for the
   full runner-plus-reversal rule. The proposed cap leaves 21–27 valid
   days, intermediate coverage and inconclusive intervals without a
   complete decision rule. Resolve those cases before freeze.

The research snapshot metadata lives at `080f124`. The opt-in
16-rank outcome recorder lives at `eaf5acf` and stores sampled quotes as
JSON. The runtime checkout still points to `ed3e231`. This review changed
documentation. The live recorder rollout, sustained external logging,
any purchases, and fresh confirmation remain open. The archive run was
still active at the November 13 check with 32,436 requests, 2,066,063
candles written, zero rate-limit responses and zero errors.
