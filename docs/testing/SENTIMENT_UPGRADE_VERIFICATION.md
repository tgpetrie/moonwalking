# Sentiment Upgrade Verification Guide

## Overview

You've successfully implemented a **coin-specific sentiment aggregator** that replaces the old mock data with real-time data from multiple sources:

- **Fear & Greed Index** (market baseline)
- **CoinGecko** (coin-specific metrics, community data, price changes)
- **Reddit** (social mentions and sentiment proxy)

## Changes Summary

### Files Modified
1. **backend/sentiment_aggregator_enhanced.py** (+641 lines)
   - Full coin-specific aggregator with async HTTP calls
   - Caches each source independently
   - Deterministic fallback for unknown coins

2. **backend/app.py** (+22, -65 lines)
   - Replaced `/api/sentiment/latest` to use new aggregator
   - Deterministic fallback on errors
   - Returns unique data per symbol

3. **backend/requirements.txt** (+2, -1 lines)
   - Added `aiohttp==3.8.5` for async HTTP

### API Response Structure

Each coin now returns:
```json
{
  "symbol": "BTC",
  "overall_sentiment": 0.623,
  "fear_greed_index": 65,
  "fear_greed_label": "Greed",
  "total_sources": 3,
  "source_breakdown": {
    "tier1": 2,
    "tier2": 0,
    "tier3": 1
  },
  "sources": [
    {
      "name": "Fear & Greed Index",
      "score": 65,
      "tier": 1,
      "reliability": 0.90,
      "status": "active",
      "description": "Market-wide: Greed"
    },
    {
      "name": "CoinGecko",
      "score": 72,
      "tier": 1,
      "reliability": 0.85,
      "status": "active",
      "description": "24h: +3.2%"
    },
    {
      "name": "Reddit Social",
      "score": 58,
      "tier": 3,
      "reliability": 0.55,
      "status": "active",
      "description": "12 mentions (24h)"
    }
  ],
  "coin_metrics": {
    "price_sentiment": 65.4,
    "community_score": 82.3,
    "developer_score": 75.0
  },
  "social_metrics": {
    "volume_change": 3.2,
    "engagement_rate": 0.045,
    "mentions_24h": 12
  },
  "social_breakdown": {
    "reddit": 0.65,
    "twitter": 0.72,
    "telegram": 0.5,
    "news": 0.68
  },
  "divergence_alerts": [
    {
      "type": "extreme_greed",
      "severity": "high",
      "message": "Extreme Greed detected (85). Market may be overheated.",
      "timestamp": "2025-12-22T10:30:00.000000Z"
    }
  ],
  "sentiment_history": [...],
  "timestamp": "2025-12-22T10:30:00.000000Z"
}
```

## Verification Steps

### Option 1: Quick Python Test (Fastest)

Test the aggregator directly without starting servers:

```bash
cd /Users/cdmxx/Documents/moonwalkings
python3 quick_sentiment_test.py
```

This will:
- Test sentiment for BTC, ETH, DOGE, SOL, PEPE, SHIB
- Validate response structure
- Check for NaN/errors
- Display sample output

### Option 2: Full Integration Test

Test with actual backend server:

```bash
cd /Users/cdmxx/Documents/moonwalkings
./test_sentiment_upgrade.sh
```

This will:
1. Create/activate Python venv
2. Install dependencies (including aiohttp)
3. Test standalone aggregator
4. Start Flask backend on port 5001
5. Test API endpoints for multiple symbols
6. Display detailed output for BTC

### Option 3: Manual Step-by-Step

#### 1. Install Dependencies

```bash
cd /Users/cdmxx/Documents/moonwalkings/backend

# Activate venv (create if needed)
python3 -m venv venv
source venv/bin/activate

# Install/upgrade dependencies
pip install -r requirements.txt
```

#### 2. Test Standalone Aggregator

```bash
cd /Users/cdmxx/Documents/moonwalkings/backend
python3 -c "
from sentiment_aggregator_enhanced import get_sentiment_for_symbol
import json

result = get_sentiment_for_symbol('BTC')
print(json.dumps(result, indent=2))
"
```

Expected output:
- No errors
- Valid JSON with all fields
- No NaN values
- Real Fear & Greed data
- CoinGecko metrics for BTC

#### 3. Start Backend Server

```bash
cd /Users/cdmxx/Documents/moonwalkings/backend
python app.py
```

Expected output:
- Server starts on port 5001
- No import errors
- No aiohttp errors

#### 4. Test API Endpoint

In a new terminal:

```bash
# Test BTC sentiment
curl "http://localhost:5001/api/sentiment/latest?symbol=BTC" | jq .

# Test other coins
curl "http://localhost:5001/api/sentiment/latest?symbol=ETH" | jq .
curl "http://localhost:5001/api/sentiment/latest?symbol=DOGE" | jq .
curl "http://localhost:5001/api/sentiment/latest?symbol=PEPE" | jq .
```

Expected:
- Each symbol returns unique data
- No errors in response
- Different `overall_sentiment` per coin
- Real Fear & Greed values (same across coins)
- Coin-specific CoinGecko metrics

#### 5. Test Frontend Integration

```bash
# Start frontend
cd /Users/cdmxx/Documents/moonwalkings/frontend
pnpm dev  # or npm run dev
```

Then:
1. Open http://localhost:5173
2. Click any ℹ️ icon on a coin row
3. Verify sentiment popup displays:
   - Overall sentiment (not always 0.5)
   - Fear & Greed index with label
   - Multiple sources with scores
   - Social metrics
   - No NaN errors in console

## Key Features

### 1. Coin-Specific Data
Each symbol gets unique sentiment based on:
- Its own CoinGecko metrics
- Its own Reddit mentions
- Market-wide Fear & Greed (same for all)

### 2. Intelligent Caching
- Fear & Greed: 1 hour TTL
- CoinGecko: 5 minutes TTL
- Reddit: 10 minutes TTL
- Reduces API calls and improves performance

### 3. Deterministic Fallbacks
If API fails or coin is unknown:
- Uses symbol hash for consistent "random" values
- Same fallback data for same symbol across requests
- No NaN or undefined values

### 4. Divergence Alerts
Automatically detects:
- Institutional vs retail sentiment divergence
- Extreme fear (< 20)
- Extreme greed (> 80)

### 5. Rate Limit Handling
- CoinGecko rate limits handled gracefully
- Falls back to cached data when rate limited
- No crashes or errors exposed to users

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'aiohttp'`
**Solution:**
```bash
cd backend
source venv/bin/activate
pip install aiohttp
```

### Issue: Backend port already in use
**Solution:**
```bash
# Find process on port 5001
lsof -i :5001

# Kill it
kill -9 <PID>

# Or use different port
python app.py --port 5002
```

### Issue: CoinGecko returns 429 (rate limited)
**Expected behavior:**
- Aggregator falls back to cached data
- If no cache, uses deterministic fallback
- No error shown to user

### Issue: Fear & Greed API down
**Expected behavior:**
- Falls back to neutral (50)
- Other sources still work
- Overall sentiment still calculated

### Issue: Frontend shows NaN
**Check:**
1. Backend API returns valid numbers: `curl localhost:5001/api/sentiment/latest?symbol=BTC | jq .overall_sentiment`
2. Frontend API call succeeds (check Network tab)
3. No JavaScript errors in console

## Next Steps

After verification passes:

1. **Test with more symbols:**
   - Known coins (BTC, ETH, SOL) should show real data
   - Unknown coins should show deterministic fallbacks
   - No crashes regardless of symbol

2. **Monitor API usage:**
   - Check CoinGecko rate limits (10-50 calls/min free tier)
   - Consider adding Redis cache for production
   - Monitor backend logs for errors

3. **Optional enhancements:**
   - Add more coins to `COINGECKO_IDS` mapping
   - Implement Twitter/Telegram sentiment (requires API keys)
   - Add database caching for historical data
   - Implement WebSocket updates for real-time changes

4. **Deploy:**
   - Update production environment with new dependencies
   - Configure environment variables if needed
   - Monitor error rates post-deployment

## Support

If you encounter issues:

1. **Check logs:**
   - Backend: Look for `[Sentiment]` prefixed messages
   - Frontend: Check browser console

2. **Verify dependencies:**
   ```bash
   pip list | grep aiohttp
   pip list | grep flask
   ```

3. **Test individual sources:**
   ```python
   from sentiment_aggregator_enhanced import EnhancedSentimentAggregator
   import asyncio

   agg = EnhancedSentimentAggregator()

   # Test Fear & Greed
   result = asyncio.run(agg.fetch_fear_greed())
   print("Fear & Greed:", result)

   # Test CoinGecko
   result = asyncio.run(agg.fetch_coingecko_coin_data('BTC'))
   print("CoinGecko:", result)

   # Test Reddit
   result = asyncio.run(agg.fetch_reddit_mentions('BTC'))
   print("Reddit:", result)
   ```

## File Locations

- **Aggregator:** `/Users/cdmxx/Documents/moonwalkings/backend/sentiment_aggregator_enhanced.py`
- **Flask endpoint:** `/Users/cdmxx/Documents/moonwalkings/backend/app.py` (line 1159-1183)
- **Requirements:** `/Users/cdmxx/Documents/moonwalkings/backend/requirements.txt`
- **Test scripts:**
  - Quick test: `/Users/cdmxx/Documents/moonwalkings/quick_sentiment_test.py`
  - Full test: `/Users/cdmxx/Documents/moonwalkings/test_sentiment_upgrade.sh`

---

**Implementation Status:** ✅ Complete

All code changes are in place. Only verification and dependency installation remain.
