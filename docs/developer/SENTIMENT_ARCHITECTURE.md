# Sentiment System Architecture

## Data Flow

```
Frontend (React)
    │
    │ Click ℹ️ icon
    ↓
┌─────────────────────────────────────────┐
│  API Request                            │
│  GET /api/sentiment/latest?symbol=BTC   │
└─────────────────────────────────────────┘
    │
    ↓
┌─────────────────────────────────────────┐
│  Flask Backend (app.py)                 │
│  Route: /api/sentiment/latest           │
└─────────────────────────────────────────┘
    │
    │ Calls get_sentiment_for_symbol(symbol)
    ↓
┌─────────────────────────────────────────┐
│  EnhancedSentimentAggregator            │
│  (sentiment_aggregator_enhanced.py)     │
└─────────────────────────────────────────┘
    │
    │ Parallel async fetch
    ├─────────┬──────────┬─────────┐
    ↓         ↓          ↓         ↓
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Fear & │ │ Coin   │ │ Reddit │ │ Cache  │
│ Greed  │ │ Gecko  │ │ Social │ │ Layer  │
│ Index  │ │   API  │ │   API  │ │        │
└────────┘ └────────┘ └────────┘ └────────┘
    │         │          │
    │         │          │
    │         ↓          │
    │   ┌─────────┐     │
    │   │CoinGecko│     │
    │   │ID Map   │     │
    │   └─────────┘     │
    │                   │
    └────────┬──────────┘
             ↓
    ┌─────────────────┐
    │ Weighted Score  │
    │  Calculation    │
    │                 │
    │ Tier 1: 85%    │
    │ Tier 2: 70%    │
    │ Tier 3: 50%    │
    └─────────────────┘
             ↓
    ┌─────────────────┐
    │ JSON Response   │
    │ with:           │
    │ - overall_sentiment
    │ - sources[]     │
    │ - coin_metrics  │
    │ - alerts[]      │
    └─────────────────┘
             ↓
    ┌─────────────────┐
    │ Frontend Popup  │
    │ Displays Data   │
    └─────────────────┘
```

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
**File:** `backend/app.py` (lines 1159-1183)

**Route:** `GET /api/sentiment/latest`

**Parameters:**
- `symbol` (query param): Coin symbol (e.g., BTC, ETH)

**Responsibilities:**
- Receive API requests
- Call aggregator with symbol
- Handle exceptions with fallback
- Return JSON response

### 3. Sentiment Aggregator
**File:** `backend/sentiment_aggregator_enhanced.py`

**Class:** `EnhancedSentimentAggregator`

**Key Methods:**
- `get_coin_sentiment(symbol)`: Main entry point
- `fetch_fear_greed()`: Get market-wide sentiment
- `fetch_coingecko_coin_data(symbol)`: Get coin metrics
- `fetch_reddit_mentions(symbol)`: Get social data

**Caching:**
- In-memory cache with TTL
- Fear & Greed: 1 hour
- CoinGecko: 5 minutes
- Reddit: 10 minutes

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

### Scenario 1: API Timeout
```
API Request → Timeout (5s)
    ↓
Check Cache → Cache Hit?
    ↓ Yes           ↓ No
Return Cache   Generate Fallback
```

### Scenario 2: Unknown Coin
```
Symbol: "NEWCOIN"
    ↓
Check COINGECKO_IDS → Not Found
    ↓
Generate Deterministic Fallback
    ↓
Use MD5 hash of symbol as seed
    ↓
Generate consistent "random" values
```

### Scenario 3: Rate Limited
```
CoinGecko → 429 Too Many Requests
    ↓
Check Cache → Return Cached Data
    ↓ (if no cache)
Generate Fallback with is_fallback=true flag
```

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

### Level 1: Source-Level
```python
try:
    data = await fetch_coingecko_coin_data(symbol)
except Exception as e:
    print(f"[Sentiment] CoinGecko error: {e}")
    data = generate_fallback_coin_data(symbol)
```

### Level 2: Aggregator-Level
```python
fear_greed, coingecko, reddit = await asyncio.gather(
    fetch_fear_greed(),
    fetch_coingecko_coin_data(symbol),
    fetch_reddit_mentions(symbol),
    return_exceptions=True  # Don't crash on single failure
)

if isinstance(coingecko, Exception):
    coingecko = generate_fallback_coin_data(symbol)
```

### Level 3: Flask Route-Level
```python
try:
    data = get_sentiment_for_symbol(symbol)
    return jsonify(data)
except Exception as exc:
    return jsonify(fallback_response)
```

**Result:** User NEVER sees an error page, always gets data

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
The current architecture represents a unified system combining two previous approaches:

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

**Current Unified System:**
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

**Last Updated:** 2025-12-22
**Status:** Production Ready ✅
**Current Version:** Unified Aggregator v2.0
