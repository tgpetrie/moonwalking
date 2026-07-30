# Sentiment Source Salvage Plan

This is the compact salvage map for older Moonwalking sentiment research. The goal is to preserve the useful thinking without reintroducing the old overloaded all-source pipeline.

## Current Principle

Keep the board truth clean:

- Price/volume board data remains primary truth.
- Signal coverage only counts real signals.
- Sentiment, news, derivatives, and social data are context unless they become validated signal inputs.
- Every source must expose provenance, freshness, and failure state.

## Salvage Now

These ideas are worth carrying forward immediately.

### Source Classes

Use four explicit source roles instead of one generic sentiment bucket:

- `market_mood`: Fear & Greed, global market data.
- `market_positioning`: funding rate, open interest, derivatives exchange context.
- `news_context`: RSS/news headlines used for explanation and narrative context.
- `social_chatter`: Reddit/X/Telegram/forum chatter, treated as noisy until validated.

### Trust Weights

The old tier weights are still useful as defaults:

- `tier1`: `0.85`
- `tier2`: `0.70`
- `tier3`: `0.50`
- `fringe`: `0.30`

Do not use these weights alone as a buy/sell signal. They should affect confidence and explanation priority.

### Freshness and Decay

Carry forward the old time-decay idea, but apply it per source role:

- `market_positioning`: stale after 10 minutes.
- `market_mood`: stale after 6 hours.
- `news_context`: stale after 24 hours for display, 2 hours for breaking-news context.
- `social_chatter`: stale after 30-60 minutes.

When a source is stale, keep it visible as stale rather than silently replacing it with mock data.

### Divergence

The old divergence idea is high value. Start with simple pairwise gaps:

- Positioning bullish while Fear & Greed is fearful: possible accumulation context.
- Retail/social euphoric while positioning is neutral/negative: possible local-top context.
- Regional news/social diverges from global mood: context only until validated.

Suggested thresholds:

- Warning: `0.25`
- Critical: `0.40`

### Crypto Lexicon

The crypto-specific lexicon is useful later for Reddit/news/social scoring, but not needed for V1 derivatives work.

Keep it as a future `lexicon` module with:

- bullish terms: `breakout`, `rally`, `accumulate`, `golden cross`, `adoption`.
- bearish terms: `rug pull`, `hack`, `liquidation`, `death cross`, `bankruptcy`.
- neutral/noise terms: `dyor`, `nfa`, `gm`, `wen`.

Avoid slang-heavy UI copy in the main app. Use plain labels first; keep slang only for optional advanced/debug language.

## Keep But Do Not Build Yet

These are valuable but too noisy or expensive for the next step.

- Reddit sentiment: useful with OAuth, anti-spam scoring, and subreddit weighting.
- X/Twitter: useful only if paid access is available and volume is high enough.
- LunarCrush/Santiment/Messari: useful paid/enriched sources after core signal plumbing is stable.
- CryptoPanic/news aggregators: useful later for deduped headline context.
- Spanish/LATAM sources: useful for regional context, not first-pass global signal.
- Chinese/forum/Telegram/custom scraping: research backlog only.

## Retire Unless Reverified

These should not be used as active sources without endpoint and data-quality revalidation:

- SentiCrypt legacy API.
- CoinyBubble Fear & Greed API.
- CryptoMeter Trend Indicator, unless treated as a black-box vendor signal with clear labeling.
- Old Twitter/X free-tier assumptions.
- Old Binance/OKX authenticated examples for public-only market data.

## Current V1 Implementation

The current branch starts with a narrow source stack:

- Alternative.me Fear & Greed as `market_mood`.
- CoinGecko global market data as `market_mood`.
- Binance/OKX/Bybit derivatives as `market_positioning`, normalized into one payload.

Live smoke result from this environment:

- OKX returned BTC/ETH funding and open interest.
- Binance returned a regional `451`.
- Bybit returned `403`.
- The implementation degrades to available exchanges instead of failing the full sentiment payload.

## Next Code Steps

1. Add source health details to the payload:
   - configured exchanges
   - live exchanges
   - blocked exchanges
   - last error by exchange

2. Add derivative summary math:
   - average funding by base asset
   - positive/negative funding bias
   - exchange coverage count
   - confidence penalty when only one exchange is live

3. Keep the UI simple:
   - `Market positioning: OKX live, Binance blocked, Bybit blocked`
   - `Funding bias: positive/neutral/negative`
   - `Coverage: 1/3 exchanges`

4. Add news RSS only after derivatives health is clear:
   - CoinDesk
   - The Block
   - CoinTelegraph
   - Decrypt

5. Add Reddit only after there is a lightweight persistence layer and spam/noise filtering.
