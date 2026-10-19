# Sentiment System Architecture

Updated 2026-10-19 for the checked handoff. The runtime corrections below
supersede the old enhanced-aggregator and fabricated-fallback descriptions.
See [the checked review](MASTER_HANDOFF_REVIEW_2026-10-19.md),
[the consolidated handoff](MASTER_HANDOFF_FOR_CODEX_2026-10-19.md), and
[SENTIMENT_ONE_BOARD.md](SENTIMENT_ONE_BOARD.md). Provider quotas, performance
estimates, scoring examples, and migration notes retained later in this document
are historical design material, not verified current runtime or provider terms.

## Data Flow

```text
SentimentPopupAdvanced.jsx
  -> Flask GET /api/sentiment/latest?symbol=BTC (backend/app.py)
  -> FastAPI /sentiment/latest (backend/sentiment_api.py)
  -> real market-wide sources, provenance, freshness, and failure state

CoinPositioning.jsx
  -> Flask GET /api/positioning/<symbol>
  -> backend/derivatives_positioning.py
```

The requested symbol does not make market-wide mood coin-specific.
`backend/sentiment_aggregator_enhanced.py` is a four-line deprecated shim
re-exporting `sentiment_aggregator.get_sentiment_for_symbol`, not the active
proxy's calculation engine. Read `sentiment_aggregator.py` when investigating
that separate aggregation helper; do not infer its use from the shim's name.

## Component Details

### 1. Frontend (React)
**File:** `frontend/src/components/SentimentPopupAdvanced.jsx`

**Responsibilities:**
- Display ℹ️ icon on coin rows
- Handle click events
- Fetch sentiment data from API
- Render popup with charts/metrics
- Handle errors gracefully

### 2. Flask Backend
**File:** `backend/app.py`, function `api_sentiment_latest`

**Route:** `GET /api/sentiment/latest`

**Parameters:**
- `symbol` (query param): Coin symbol (e.g., BTC, ETH)

**Responsibilities:**
- Receive API requests
- Proxy the real sentiment service, preserving requested-symbol context
- Retain last-good real data with explicit stale/offline metadata on failure
- Return JSON response

### 3. Service and separate aggregation helper

The mounted proxy reads `backend/sentiment_api.py`. Its checked cache values are
300 seconds for Fear & Greed, 120 seconds for CoinGecko, and 30 seconds by default
for the combined response. These differ from historical helper settings below.

The separate `backend/sentiment_aggregator.py` helper and
`backend/sentiment_config.yaml` default to `divergence_threshold: 0.12`.
`_divergence_alerts` compares tier1 with tier3: medium at the configured threshold,
high at twice that threshold (0.24 by default). Missing tier scores produce no
alert. The salvage plan's 0.25/0.40 values are proposals, not this implementation.
Neither threshold family is validated against outcomes; this code inspection
is not a claim about a deployed process or a new trading signal.

### 4. External APIs

#### Fear & Greed Index
- **URL:** `https://api.alternative.me/fng/`
- **Rate Limit:** Generous (free)
- **Data:** Market-wide sentiment (0-100)
- **Update:** Daily

#### CoinGecko API
- **URL:** `https://api.coingecko.com/api/v3/coins/{id}`
- **Rate Limit:** 10-50 calls/min (free tier)
- **Data:**
  - Price changes (24h, 7d)
  - Community score
  - Developer activity
  - Social metrics
  - Volume data

#### Reddit API
- **URL:** `https://www.reddit.com/search.json`
- **Rate Limit:** ~60 requests/min
- **Data:**
  - Recent mentions (24h)
  - Upvote ratios (sentiment proxy)

## Scoring Algorithm

### Source Tier Weights

```python
TIER_WEIGHTS = {
    1: 0.85,  # Institutional (Fear & Greed, CoinGecko official)
    2: 0.70,  # Professional (CoinGecko community)
    3: 0.50,  # Retail/Social (Reddit, Twitter)
}
```

### Overall Sentiment Calculation

```
weighted_sum = 0
total_weight = 0

for source in sources:
    weight = TIER_WEIGHTS[source.tier] * source.reliability
    weighted_sum += source.score * weight
    total_weight += weight

overall_sentiment = (weighted_sum / total_weight) / 100
```

**Example:**
```
Fear & Greed:  score=65, tier=1, reliability=0.90 → weight=0.765
CoinGecko:     score=72, tier=1, reliability=0.85 → weight=0.723
Reddit:        score=58, tier=3, reliability=0.55 → weight=0.275

weighted_sum = (65 × 0.765) + (72 × 0.723) + (58 × 0.275)
             = 49.725 + 52.056 + 15.95
             = 117.731

total_weight = 0.765 + 0.723 + 0.275 = 1.763

overall_sentiment = 117.731 / 1.763 / 100 = 0.668
```

## Fallback Strategy

There is no MD5-seeded random sentiment fallback in current backend code.
The former unknown-coin diagram in this document described removed behavior.
Hashing used for cache identity is not a sentiment value generator.

- Timeout or rate limit: retain a valid last-good response with actual age,
  success/attempt timestamps, `ok=false`, an error, and stale/offline status.
- No valid cached response: return unavailable/null data and truthful failure
  metadata. Never synthesize a neutral score or other replacement measurements.
- Unknown symbol: leave missing coin-specific metrics unavailable. Any real
  market-wide data must retain its market-wide scope and source provenance.

These are the One-Board truth rules; consult the current route/service for its
exact response envelope. Last-good data is not a fresh successful observation.

## Cache Architecture

### In-Memory Cache Structure
```python
cache = {
    'fear_greed:global': {
        'data': {...},
        'timestamp': datetime(2025, 12, 22, 10, 0, 0)
    },
    'coingecko:BTC': {
        'data': {...},
        'timestamp': datetime(2025, 12, 22, 10, 25, 0)
    },
    'reddit:BTC': {
        'data': {...},
        'timestamp': datetime(2025, 12, 22, 10, 20, 0)
    }
}
```

### Cache TTL
```
Fear & Greed:  3600s (1 hour)
CoinGecko:      300s (5 minutes)
Reddit:         600s (10 minutes)
```

### Cache Hit Rate (Expected)
- First request: 0% (cold cache)
- Subsequent requests: 85-95% (warm cache)
- Reduces external API calls significantly

## Error Handling

Provider errors preserve missing values rather than invoking the historical
`generate_fallback_coin_data` examples removed from this document. The Flask
proxy returns stale last-good data when available, or an explicit offline
response when not. Frontend code must retain provenance and failure metadata;
never manufacture a successful response to hide a fetch error.

## Performance Characteristics

### Cold Start (No Cache)
- Fear & Greed: ~200-500ms
- CoinGecko: ~500-1000ms
- Reddit: ~300-800ms
- **Total: ~1-2 seconds** (parallel)

### Warm Cache (95% hit rate)
- Cache lookup: <1ms
- **Total: ~1-5ms**

### Memory Usage
- Cache size: ~10KB per symbol
- 100 symbols: ~1MB
- Negligible impact

## Security Considerations

### 1. No Authentication Required
- All APIs used are public
- No API keys in code
- No secrets to leak

### 2. Rate Limiting
- Caching prevents abuse
- Fallbacks prevent crashes
- No DOS risk to upstream APIs

### 3. Input Validation
```python
symbol = request.args.get('symbol', "BTC").upper()
# Always uppercase, default to BTC
# No SQL injection risk (no database)
```

### 4. Error Information Leakage
- Error messages sanitized
- Only generic errors returned to client
- Detailed logs server-side only

## Monitoring Points

### Key Metrics to Track
1. **Cache Hit Rate:** Should be >80%
2. **API Errors:** Should be <5%
3. **Fallback Usage:** Should be <10%
4. **Response Time:** Should be <100ms (cached), <2s (cold)

### Log Messages
```
[Sentiment] Fear & Greed fetch error: {reason}
[Sentiment] CoinGecko rate limited for {symbol}
[Sentiment] Reddit fetch error for {symbol}: {reason}
[Sentiment API] Error: {exception}
```

### Alerts to Set
- CoinGecko 429 rate: >20% of requests
- Fear & Greed failures: >50% of requests
- Overall API errors: >10% of requests

## Deployment Checklist

- [ ] Verify `aiohttp` in production requirements
- [ ] Test with production symbols (not just BTC/ETH)
- [ ] Verify rate limits don't exceed free tier
- [ ] Set up error monitoring (Sentry/similar)
- [ ] Document for team (this file!)
- [ ] Load test with concurrent requests
- [ ] Verify cache TTLs are appropriate
- [ ] Check memory usage under load

## Integration & Migration History

### System Evolution
The historical design combined two previous approaches; this section is not the current runtime contract:

**Previous System 1: Enhanced Aggregator**
- Coin-specific data (different results per symbol)
- Limited to 3 sources (Fear & Greed, CoinGecko, Reddit)
- Simple caching, deterministic fallbacks
- No VADER sentiment analysis

**Previous System 2: Comprehensive Multi-Source**
- VADER sentiment analysis with crypto lexicon
- 50+ data sources capability with RSS feeds
- Tier-based weighting system
- Returned same sentiment for all coins (market-wide only)

**Historical Unified System proposal:**
- Combines coin-specific AND market-wide sources
- VADER sentiment analysis on all text
- Tier-based weighting (Tier 1: 0.85, Tier 2: 0.70, Tier 3: 0.50)
- Divergence detection across tiers
- Trending topics extraction
- Fully integrated into Flask app

### Migration Path for Legacy Systems

**For System 1 Users:**
- ✅ No breaking changes
- ✅ API endpoint stays the same: `/api/sentiment/latest`
- ✅ Response format enhanced (backwards compatible)
- ✅ More sources = better data
- 📝 Optional: Add Reddit credentials for full functionality

**For System 2 Users:**
- 📝 Migrate from FastAPI to Flask endpoint
- 📝 All features preserved
- ✅ Gain coin-specific capability

## Future Enhancements

### Short Term
1. Add persistent cache (Redis)
2. Add more coins to CoinGecko mapping
3. Implement webhook updates
4. Add comprehensive test suite (>80% coverage)
5. Improve error handling and logging

### Medium Term
1. Twitter sentiment integration
2. Historical sentiment tracking
3. Sentiment-based alerts
4. Distributed caching with Redis
5. Circuit breaker pattern for source failures

### Long Term
1. Machine learning predictions (FinBERT/CryptoBERT)
2. Custom sentiment models
3. Real-time WebSocket updates
4. Per-symbol configuration overrides
5. Advanced analytics and correlation analysis

---

**Historical design date:** 2025-12-22
**Runtime corrections:** 2026-10-19
**Status:** Historical design with current routing and truth-rule corrections; use the checked handoff for implementation.
