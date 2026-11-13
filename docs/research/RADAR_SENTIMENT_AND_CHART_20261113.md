# Sentiment and Chart Read in Radar · November 13

## What the app uses

- **Mover boards** rank gainers and losers by their displayed percentage
  change. The 1m gainers component shows eight by default and can expand to
  16. Its sort consumes the 1m change. The 3m lists split by return sign
  and sort by the 3m change. The dashboard also has a separate Live Strength
  rail. See `backend/app.py`, `DashboardShell.jsx`, and
  `GainersTable1Min.jsx`.
- **Live Strength** scores price, volume, streaks, directional local alerts,
  sampled Coinbase spot pressure, market-relative movement and liquidity.
  It takes no external sentiment input. The local flow fields describe
  trades and liquidity. Their appearance in a sentiment or context panel
  does not make them independent social evidence. See `backend/live_ranking.py`
  and `backend/signal_context.py`.
- **Sentiment** is served separately. `backend/sentiment_api.py` aggregates
  market-wide context including Alternative.me and CoinGecko global data.
  Alternative.me publishes a daily BTC-based index that partly uses price and
  volume. It can be tested as a regime filter shared by the whole board.
  Coin-specific context in `backend/coin_intel_external.py` can include
  CoinPaprika events or official timeline items, CoinGecko community proxies,
  and an optional keyed LunarCrush adapter. Code presence supplies no
  evidence of current credentials, freshness, or historical 1–3m coverage.
  [Alternative.me methodology](https://alternative.me/crypto/fear-and-greed-index/)
- **Chart Read** is wired into the coin popup through `/api/chart-read/<symbol>`.
  The route fetches roughly 50 hourly Coinbase candles and the deterministic
  reader returns trend, price zones, volume context, confidence in the read,
  and conditions to watch. This is useful context for inspecting a coin.
  It has no validated continuation probability and does not feed mover
  ordering. The separate October chart research found weekly levels and
  Fibonacci lines comparable to distance-matched placebo lines, and the
  volume-profile study found no discovery survivor. The large-move study's
  giveback result is at daily horizons. [Chart research handoff](https://github.com/tgpetrie/moonwalking/blob/74c1cf4eab17a6c1b4d57d81e4f5db0690619513/docs/developer/HANDOFF_FOR_CODEX_2026-10-18.md)
  [Volume-profile result](https://github.com/tgpetrie/moonwalking/blob/bc8a887/docs/developer/VOLUME_PROFILE_STUDY.md)

The simplest plausible external input is abnormal coin-specific attention,
measured against the same coin's earlier observations with separate event
and receipt clocks. Attention can rise in either direction. A separate
signed catalyst or social-polarity field would need evidence of incremental
runner precision at the same flag budget and an adverse-outcome check.
Until such a source has measurable latency and coverage, retain these
features as research candidates. The
[Carbon or Gemini assignment](../ai/CARBON_SENTIMENT_RADAR_ASSIGNMENT_20261113.md)
requests a documented shortlist and a causal test with the observed base rate.

## Forward data work

The runner branch already contains the v3 feature-snapshot retention wiring
for numeric quote volume and volatility from `080f124`. The checked Windows
collector remains on `ed3e231`, which predates that wiring.
The separate opt-in `MW_BOARD_OUTCOME_RESEARCH_V3=1` recorder writes
`board_outcomes_v3` and maintains its own membership, cooldown and gap
heartbeat. It includes ranks up to 16 from each supplied board snapshot,
retains the existing v2 statistics and stores sampled ticker bid/ask
at entry and each first observed return checkpoint. A quote includes its
age at observation and product identity. An absent or over-15s quote stays
null. The v3 15m extrema stop at 900s and include a count of post-entry price
observations. This count measures tracker samples and does not count
distinct trades. Promotion within ranks 1–16 is not a new v3 episode.
The original v2 ledger separately records top-eight entry transitions.
The opt-in recorder has not been deployed to the running collector.

The resumable public candle backfill writes a separate research SQLite
file under `~/.moonwalking/analysis/radar_candle_backfill_20261113`. Its
497-product roster is the union of archived, observed, and currently
listed Coinbase USD products. This is a coverage inventory with possible
omissions in the historical listing record. The BTC pilot recorded
45,898 1m candles, 153 requests and no errors. The wider run was launched
at the existing two-requests-per-second ceiling. The final manifest records
completed, empty, 404 and unrecorded windows by product and hashes the
closed archive. Date bounds use the most recent completed archive grid
window and can be extended by rerunning the same command. A 404 or empty
response leaves availability explicit. [Coinbase candle API](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
