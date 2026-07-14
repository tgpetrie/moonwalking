# Moonwalkings Sentiment Sources

Last reviewed: 2026-07-14

Moonwalkings uses a limited, truthful sentiment model. It should report what is available, label the source and freshness, and leave unsupported fields null or empty. It must not invent social sentiment, historical series, topic lists, or neutral fallback values.

## Active free/public sources

| Source | Used for | Endpoint | Access | Product treatment |
|---|---|---|---|---|
| Alternative.me Crypto Fear & Greed Index | Market-wide sentiment gauge | `https://api.alternative.me/fng/?limit=1&format=json` | Free/public | Active in `backend.sentiment_api`; reported as `fear_greed`, `fear_greed_index`, and a tier-1 source. |
| CoinGecko Global Market Data | Market cap, volume, BTC dominance, 24h market-cap change | `https://api.coingecko.com/api/v3/global` | Public demo endpoint / Pro key available | Active in `backend.sentiment_api`; reported as `market_pulse`. |
| Coinbase Exchange market data | Local price tape, movers, baselines, volume context | `https://api.exchange.coinbase.com/products` and related product market-data endpoints | Public market data | Active in the Flask backend; used as local tape/context, not external social sentiment. |
| CoinPaprika coin events / timeline | Coin-context events and timeline items | `https://api.coinpaprika.com/v1/coins/{coin_id}/events`, `/twitter` | Public API | Active in `/api/coin-intel`; treated as coin context, not precise social sentiment. |
| CoinGecko coin community data | Coin-context community/attention proxy | `https://api.coingecko.com/api/v3/coins/{coin_id}` | Public demo endpoint / Pro key available | Active as a fallback in `/api/coin-intel`; labels metrics as proxy context. |

Primary documentation:

- Alternative.me Fear & Greed API: https://alternative.me/crypto/fear-and-greed-index/
- CoinGecko `/global`: https://docs.coingecko.com/reference/crypto-global
- Coinbase Exchange market data: https://docs.cdp.coinbase.com/exchange/introduction/welcome
- Coinbase product ticker: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker
- CoinPaprika API: https://coinpaprika.com/api/

## Optional/credentialed sources

| Source | Status | Required setup | Product treatment |
|---|---|---|---|
| LunarCrush | Implemented as optional, disabled without credentials | `LUNARCRUSH_API_KEY` or `LUNARCRUSH_KEY` | Coin-scoped social metrics only. If absent, response stays unavailable/offline. |
| Santiment SanAPI | Candidate provider, not implemented yet | Santiment account/API access | Strong alternative to Reddit/X direct APIs because it aggregates social, developer, and on-chain metrics. |
| Messari Signal Sentiment | Candidate provider, not implemented yet | Messari API access | Direct sentiment API for social conversations; likely paid/plan-gated. |
| Kaito | Candidate provider, not implemented yet | Kaito API/commercial access | Useful for mindshare/narrative intelligence instead of hand-picking X accounts. |
| The Tie | Candidate provider, not implemented yet | Commercial access | Institutional-grade news/social sentiment; likely too expensive unless the product matures. |
| Perception | Candidate provider, not implemented yet | API access | Narrative/news sentiment option for Bitcoin/digital-asset coverage. |
| CoinMarketCap Fear & Greed | Not implemented | CoinMarketCap API key | Candidate alternative to Alternative.me, but would add account/key management. |
| Reddit, X/Twitter, Telegram, Discord | Not implemented | Official APIs, OAuth/app credentials, platform policy review, rate-limit handling | Must remain unavailable until a compliant provider is built. Do not scrape or synthesize. |

## Position on individual X/Reddit accounts

Moonwalkings should not hard-code or scrape individual “low-key” crypto accounts as a data source. If creator-level signals are needed, use a provider that exposes creator metrics and has clear credentials, rate limits, and terms. A future allowlist can be layered on top of an official provider key, but the product should still label it as curated social context rather than broad market sentiment.

## Contract

- `data_status` is `live`, `stale`, or `offline`.
- `scope` is `market_wide` unless a future provider has real coin-scoped sentiment.
- Populated external blocks include `source`, `source_url`, `updated_at`, and stale markers.
- Missing social, history, topic, or divergence data stays null or empty.
- Cached fallback data may be served as `stale`; it must never be relabeled as live.
- Configured catalog entries are metadata only; they do not count as active coverage unless the backend contributed them to `sources`.
