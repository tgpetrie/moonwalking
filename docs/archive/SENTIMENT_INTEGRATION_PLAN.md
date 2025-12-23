# Sentiment System Integration Plan

## Current State Analysis

### System 1: Enhanced Aggregator (NEW - Just Added)
**File:** `backend/sentiment_aggregator_enhanced.py`
- ✅ Coin-specific data (BTC vs ETH get different results)
- ✅ Fear & Greed Index
- ✅ CoinGecko per-coin metrics
- ✅ Reddit mentions per coin
- ✅ Simple caching
- ✅ Deterministic fallbacks
- ❌ Limited to 3 sources
- ❌ No VADER sentiment analysis
- ❌ No RSS feeds
- ❌ No tier system

### System 2: Comprehensive Multi-Source (OLD - Fully Featured)
**Files:** `sentiment_data_sources.py`, `sentiment_api_full.py`
- ✅ VADER sentiment analysis with crypto lexicon
- ✅ Multiple RSS feeds (CoinDesk, CryptoSlate, Bitcoin Magazine, etc.)
- ✅ Reddit integration with 5+ subreddits
- ✅ Tier-based weighting (Tier 1: 0.85, Tier 2: 0.70, Tier 3: 0.50)
- ✅ Comprehensive configuration (sentiment_config.yaml)
- ✅ Divergence detection
- ✅ Trending topics extraction
- ✅ 50+ data sources capability
- ❌ Returns same sentiment for all coins
- ❌ Not integrated with current Flask app
- ❌ Uses FastAPI (different framework)

## Integration Strategy

### Approach: Hybrid Best-of-Both

Combine the coin-specific approach from System 1 with the comprehensive multi-source collection from System 2.

**Result:**
- Each coin gets unique sentiment based on coin-specific sources
- Market-wide sources (Fear & Greed, RSS feeds) shared across all coins
- VADER sentiment analysis on all text
- 50+ data sources capability
- Tier-based weighting
- Integrated into existing Flask app

## Implementation Plan

### Phase 1: Merge Data Sources (High Priority)
**Goal:** Create unified sentiment collector with both coin-specific and market-wide sources

**Tasks:**
1. Merge `sentiment_data_sources.py` into `backend/sentiment_aggregator_enhanced.py`
2. Add VADER sentiment analysis to all text processing
3. Add RSS feed collectors (CoinDesk, CryptoSlate, etc.)
4. Add Reddit collector with multiple subreddits
5. Implement tier-based weighting system
6. Add divergence detection

**Output:** `backend/sentiment_aggregator_unified.py`

### Phase 2: Configuration System (Medium Priority)
**Goal:** Make all sources configurable without code changes

**Tasks:**
1. Create `backend/sentiment_config.yaml` based on existing config
2. Add environment variable support (.env)
3. Make Reddit credentials optional (graceful degradation)
4. Allow enabling/disabling sources via config

**Output:** `backend/sentiment_config.yaml`, updated `.env.example`

### Phase 3: Flask Integration (High Priority)
**Goal:** Integrate unified system into existing Flask app

**Tasks:**
1. Update `/api/sentiment/latest` endpoint in `app.py`
2. Add query parameter: `?symbol=BTC` (coin-specific)
3. Add query parameter: `?market=crypto` (market-wide)
4. Maintain backwards compatibility
5. Add new endpoint: `/api/sentiment/sources` (list active sources)
6. Add new endpoint: `/api/sentiment/divergence` (tier analysis)

**Output:** Updated `backend/app.py`

### Phase 4: Dependencies & Setup (High Priority)
**Goal:** Ensure all dependencies are installable and documented

**Tasks:**
1. Merge dependency lists into `backend/requirements.txt`
2. Make optional deps truly optional (praw, feedparser, etc.)
3. Create setup script for easy installation
4. Document Reddit API setup process

**Output:** Updated `backend/requirements.txt`, `SETUP_SENTIMENT.md`

### Phase 5: Testing & Validation (Critical)
**Goal:** Verify everything works end-to-end

**Tasks:**
1. Test with no Reddit credentials (should work with reduced sources)
2. Test with Reddit credentials (full functionality)
3. Test coin-specific queries (BTC vs ETH different results)
4. Test market-wide queries (same across all coins)
5. Verify frontend integration
6. Load testing with multiple concurrent requests

**Output:** Test results, performance metrics

## Unified Architecture

```
Frontend Request: /api/sentiment/latest?symbol=BTC
                         ↓
              ┌──────────────────────┐
              │   Flask Endpoint     │
              │   (app.py)           │
              └──────────────────────┘
                         ↓
              ┌──────────────────────┐
              │ Unified Sentiment    │
              │ Aggregator           │
              └──────────────────────┘
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                  ↓
┌───────────────┐                ┌────────────────┐
│ Market-Wide   │                │ Coin-Specific  │
│ Sources       │                │ Sources        │
│ (All Coins)   │                │ (Per Symbol)   │
└───────────────┘                └────────────────┘
        ↓                                  ↓
┌──────────────────┐           ┌──────────────────┐
│ - Fear & Greed   │           │ - CoinGecko      │
│ - RSS Feeds      │           │   (BTC metrics)  │
│   • CoinDesk     │           │ - Reddit         │
│   • CryptoSlate  │           │   (BTC mentions) │
│   • BTC Magazine │           │ - Price Data     │
│ - Reddit Global  │           │                  │
│   • r/Crypto..   │           │                  │
│   • r/Bitcoin    │           │                  │
└──────────────────┘           └──────────────────┘
        ↓                                  ↓
        └────────────────┬─────────────────┘
                         ↓
              ┌──────────────────────┐
              │ VADER Sentiment      │
              │ Analysis             │
              │ (Crypto Lexicon)     │
              └──────────────────────┘
                         ↓
              ┌──────────────────────┐
              │ Tier-Based           │
              │ Weighted Aggregation │
              │                      │
              │ Tier 1: 0.85         │
              │ Tier 2: 0.70         │
              │ Tier 3: 0.50         │
              └──────────────────────┘
                         ↓
              ┌──────────────────────┐
              │ Coin-Specific        │
              │ Sentiment Response   │
              │                      │
              │ - overall_sentiment  │
              │ - fear_greed_index   │
              │ - sources[]          │
              │ - coin_metrics       │
              │ - social_breakdown   │
              │ - divergence_alerts  │
              └──────────────────────┘
```

## Data Source Categorization

### Market-Wide Sources (Same for All Coins)
| Source | Tier | Weight | Update Frequency |
|--------|------|--------|------------------|
| Fear & Greed Index | 1 | 0.90 | 1 hour |
| CoinDesk RSS | 2 | 0.80 | 10 minutes |
| CryptoSlate RSS | 2 | 0.70 | 15 minutes |
| Bitcoin Magazine RSS | 2 | 0.75 | 15 minutes |
| r/CryptoCurrency | 2 | 0.75 | 10 minutes |
| r/Bitcoin | 2 | 0.75 | 10 minutes |
| r/ethereum | 2 | 0.75 | 10 minutes |
| r/SatoshiStreetBets | 3 | 0.55 | 15 minutes |
| r/CryptoMoonShots | 3 | 0.50 | 15 minutes |

### Coin-Specific Sources (Unique Per Symbol)
| Source | Tier | Weight | Update Frequency |
|--------|------|--------|------------------|
| CoinGecko Metrics | 1 | 0.85 | 5 minutes |
| Reddit Symbol Mentions | 3 | 0.60 | 10 minutes |
| Price Momentum | 1 | 0.80 | 1 minute |
| Social Engagement | 2 | 0.70 | 10 minutes |

## Response Schema

### Unified Response Format
```json
{
  "symbol": "BTC",
  "overall_sentiment": 0.623,
  "fear_greed_index": 65,
  "fear_greed_label": "Greed",
  "total_sources": 12,
  "timestamp": "2025-12-22T10:30:00Z",

  "source_breakdown": {
    "tier1": 4,
    "tier2": 5,
    "tier3": 3,
    "fringe": 0
  },

  "tier_scores": {
    "tier1": 0.68,
    "tier2": 0.62,
    "tier3": 0.58
  },

  "sources": [
    {
      "name": "Fear & Greed Index",
      "score": 65,
      "tier": 1,
      "weight": 0.90,
      "reliability": 0.90,
      "status": "active",
      "description": "Market-wide: Greed",
      "last_update": "2025-12-22T10:00:00Z"
    },
    {
      "name": "CoinGecko (BTC)",
      "score": 72,
      "tier": 1,
      "weight": 0.85,
      "reliability": 0.85,
      "status": "active",
      "description": "Price: +3.2% (24h), Community: 82.3",
      "last_update": "2025-12-22T10:25:00Z"
    },
    {
      "name": "CoinDesk RSS",
      "score": 58,
      "tier": 2,
      "weight": 0.80,
      "reliability": 0.80,
      "status": "active",
      "description": "15 articles analyzed (VADER avg: 0.58)",
      "last_update": "2025-12-22T10:20:00Z"
    },
    {
      "name": "Reddit r/CryptoCurrency",
      "score": 62,
      "tier": 2,
      "weight": 0.75,
      "reliability": 0.75,
      "status": "active",
      "description": "100 posts analyzed (VADER avg: 0.62)",
      "last_update": "2025-12-22T10:20:00Z"
    },
    {
      "name": "Reddit BTC Mentions",
      "score": 55,
      "tier": 3,
      "weight": 0.60,
      "reliability": 0.60,
      "status": "active",
      "description": "45 mentions (24h), 67% positive",
      "last_update": "2025-12-22T10:20:00Z"
    }
  ],

  "coin_metrics": {
    "price_sentiment": 65.4,
    "price_change_24h": 3.2,
    "price_change_7d": 8.5,
    "community_score": 82.3,
    "developer_score": 75.0,
    "volume_sentiment": 68.2
  },

  "social_metrics": {
    "reddit_mentions": 45,
    "reddit_sentiment": 0.67,
    "twitter_followers": 5234567,
    "engagement_rate": 0.045,
    "trending_rank": 3
  },

  "social_breakdown": {
    "reddit": 0.65,
    "twitter": 0.72,
    "telegram": 0.50,
    "news": 0.68
  },

  "divergence_alerts": [
    {
      "type": "tier_divergence",
      "severity": "medium",
      "message": "Tier 1 (institutional) more bullish (0.68) than Tier 3 (retail) (0.58)",
      "difference": 0.10,
      "timestamp": "2025-12-22T10:30:00Z"
    }
  ],

  "trending_topics": [
    {"term": "halving", "mentions": 234, "sentiment": 0.78},
    {"term": "etf", "mentions": 189, "sentiment": 0.65},
    {"term": "$BTC", "mentions": 567, "sentiment": 0.62}
  ],

  "sentiment_history": [
    {"timestamp": "2025-12-22T09:30:00Z", "score": 61.2, "fear_greed": 63},
    {"timestamp": "2025-12-22T10:00:00Z", "score": 62.5, "fear_greed": 65},
    {"timestamp": "2025-12-22T10:30:00Z", "score": 62.3, "fear_greed": 65}
  ],

  "metadata": {
    "cache_hit": false,
    "processing_time_ms": 1234,
    "sources_queried": 12,
    "sources_successful": 11,
    "sources_cached": 8
  }
}
```

## Migration Path

### For Users Currently Using System 1 (Enhanced Aggregator)
1. ✅ No breaking changes
2. ✅ API endpoint stays the same: `/api/sentiment/latest`
3. ✅ Response format enhanced (backwards compatible)
4. ✅ More sources = better data
5. 📝 Optional: Add Reddit credentials for full functionality

### For Users Currently Using System 2 (Comprehensive)
1. 📝 Migrate from FastAPI to Flask endpoint
2. 📝 Change API base URL from `:8001` to `:5001`
3. 📝 Update frontend API calls
4. ✅ All features preserved
5. ✅ Gain coin-specific capability

## Timeline

| Phase | Time Estimate | Priority |
|-------|---------------|----------|
| Phase 1: Merge Data Sources | 2-3 hours | HIGH |
| Phase 2: Configuration System | 1 hour | MEDIUM |
| Phase 3: Flask Integration | 1-2 hours | HIGH |
| Phase 4: Dependencies & Setup | 30 mins | HIGH |
| Phase 5: Testing & Validation | 1-2 hours | CRITICAL |
| **Total** | **5-8 hours** | - |

## Dependencies to Add

```txt
# Sentiment Analysis
vaderSentiment==3.3.2

# Reddit API
praw==7.7.1

# RSS Feeds
feedparser==6.0.10

# Already have:
# - aiohttp (for async HTTP)
# - requests (for sync HTTP)
# - python-dotenv (for .env)
```

## Configuration Changes

### .env (Add to existing)
```bash
# Sentiment System
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here

# Optional: Twitter/X (future)
# TWITTER_API_KEY=
# TWITTER_API_SECRET=
```

### backend/requirements.txt
Add:
- vaderSentiment
- praw
- feedparser

## Success Criteria

✅ **Functionality:**
- BTC and ETH return different sentiment scores
- Fear & Greed Index data appears in all responses
- RSS feeds contribute to market-wide sentiment
- Reddit posts analyzed with VADER
- Tier weighting applied correctly

✅ **Performance:**
- Response time < 2s (cold cache)
- Response time < 100ms (warm cache)
- Cache hit rate > 80%
- No memory leaks

✅ **Reliability:**
- Works without Reddit credentials (degraded mode)
- Works with Reddit credentials (full mode)
- Handles API failures gracefully
- No crashes on malformed data

✅ **Integration:**
- Frontend popups display data correctly
- No breaking changes to existing API
- All tests pass
- Documentation updated

## Next Steps

**Immediate Actions:**
1. Review this integration plan
2. Approve approach
3. Begin Phase 1 implementation
4. Get Reddit API credentials (5 minutes)
5. Test integration

**After Integration:**
1. Monitor API performance
2. Tune tier weights based on accuracy
3. Add more RSS feeds as needed
4. Consider Twitter integration (optional)
5. Add historical trending analysis

---

**Status:** Ready for implementation
**Estimated Completion:** Same day
**Risk Level:** Low (backwards compatible)
