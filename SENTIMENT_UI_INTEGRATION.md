# Sentiment UI Integration - Complete Guide

## Overview

The Moonwalking dashboard now displays **tiered sentiment analysis** with real data from 50+ sources, showing institutional vs retail divergence in the Sentiment Popup (info button).

---

## What Was Built

### 1. **Enhanced Hook: `useTieredSentiment.js`**

**Location:** [frontend/src/hooks/useTieredSentiment.js](frontend/src/hooks/useTieredSentiment.js)

**What it does:**
- Fetches from **TWO** APIs simultaneously:
  - `/api/sentiment/latest` (symbol-specific sentiment)
  - `/api/sentiment/tiered` (tiered breakdown from pipeline)
- Merges both data sources into a unified structure
- Detects divergence between tiers automatically
- Checks pipeline health status
- Falls back gracefully if pipeline is offline

**Key Features:**
```javascript
const {
  data,              // Merged sentiment with tier_scores
  tieredData,        // Raw tiered data from pipeline
  pipelineHealth,    // { running: true/false, checked: true }
  loading,           // Initial load state
  validating,        // Background refresh
  stale,             // Using cached data
  error,             // Error state
  refresh,           // Manual refresh function
} = useTieredSentiment(symbol);
```

**Data Structure:**
```javascript
data = {
  overall_sentiment: 0.65,        // Weighted score 0-1
  fear_greed_index: 65,           // 0-100

  // NEW: Tier breakdown
  tier_scores: {
    tier1: 0.70,    // Institutional (CoinGecko, Binance)
    tier2: 0.65,    // Mainstream (CoinDesk, Reddit r/CC)
    tier3: 0.58,    // Retail (r/SSB, Telegram, Twitter)
    fringe: 0.45,   // Fringe (4chan, BitcoinTalk, Weibo)
  },

  // NEW: Divergence alerts
  divergence_alerts: [
    {
      type: 'warning',  // or 'info'
      message: 'Institutional sources (70%) more bullish than retail (58%)'
    }
  ],

  // Enhanced metadata
  has_tiered_data: true,
  total_data_points: 127,
  confidence: 0.82,
  pipeline_timestamp: "2025-12-25T...",

  // Original fields (unchanged)
  social_breakdown: { reddit, twitter, telegram, chan, news },
  source_breakdown: { tier1, tier2, tier3, fringe },
  sentiment_history: [...],
  ...
}
```

---

### 2. **Updated Component: `SentimentPopupAdvanced.jsx`**

**Location:** [frontend/src/components/SentimentPopupAdvanced.jsx](frontend/src/components/SentimentPopupAdvanced.jsx)

**Changes:**
- Uses `useTieredSentiment` instead of `useSentimentLatest`
- Displays 4-tier breakdown grid in Overview tab
- Shows divergence alerts when detected
- Indicates pipeline health status

**New UI Elements:**

#### **Tiered Sentiment Analysis Section**
Displays when `sentimentData.has_tiered_data === true`:

```
┌─────────────────────────────────────────────────┐
│ T1: Institutional               70%             │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░ (green bar)              │
│ CoinGecko, Fear & Greed, Binance               │
├─────────────────────────────────────────────────┤
│ T2: Mainstream                  65%             │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░ (orange bar)             │
│ CoinDesk, Reddit r/CC, News Feeds              │
├─────────────────────────────────────────────────┤
│ T3: Retail                      58%             │
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ (purple bar)             │
│ r/SSB, Telegram, Twitter/X                     │
├─────────────────────────────────────────────────┤
│ Fringe Sources                  45%             │
│ ▓▓▓▓▓▓▓░░░░░░░░░░░░░ (pink bar)               │
│ 4chan /biz/, BitcoinTalk, Weibo                │
└─────────────────────────────────────────────────┘

Live data from sentiment pipeline (127 data points)
```

#### **Divergence Alerts Section**
Shows when `sentimentData.divergence_alerts.length > 0`:

```
┌─────────────────────────────────────────────────┐
│ WARNING                                         │
│ Institutional sources (70%) more bullish than   │
│ retail (58%) - 12% divergence detected         │
└─────────────────────────────────────────────────┘
```

---

### 3. **Updated Styles: `sentiment-popup-advanced.css`**

**Location:** [frontend/src/styles/sentiment-popup-advanced.css](frontend/src/styles/sentiment-popup-advanced.css)

**New CSS Classes:**
- `.tier-breakdown-grid` - Responsive grid for 4 tier cards
- `.tier-card` - Individual tier display (hover effects)
- `.tier-bar` / `.tier-bar-fill` - Animated progress bars
- `.pipeline-status` - Health indicator (green/yellow)
- `.divergence-alerts` / `.alert-box` - Alert styling

**Color Coding:**
- **Tier 1:** Green (`#45ffb3`) - Institutional trust
- **Tier 2:** Orange (`#f1b43a`) - Professional sources
- **Tier 3:** Purple (`#ae4bf5`) - Retail sentiment
- **Fringe:** Pink (`#ff6b9d`) - Alternative sources

---

## How It Works

### Data Flow

```
User clicks info button
        ↓
SentimentPopupAdvanced opens
        ↓
useTieredSentiment hook fires
        ↓
   ┌────────────────┬────────────────┐
   │                │                │
   ▼                ▼                ▼
/api/sentiment/latest  /api/sentiment/tiered  /api/sentiment/pipeline-health
   │                │                │
   │                │                │
   ▼                ▼                ▼
Symbol-specific   Tiered breakdown   Health check
   │                │                │
   └────────────────┴────────────────┘
                    │
                    ▼
            Merged data object
                    │
                    ▼
         UI renders with:
         - Tier breakdown grid
         - Divergence alerts
         - Pipeline status
```

### Divergence Detection Logic

**In the hook (`useTieredSentiment.js`):**

```javascript
// Calculate divergence
const institutionalRetailDivergence = Math.abs(tier1Score - tier3Score);

if (institutionalRetailDivergence > 0.2) {  // 20% threshold
  divergenceAlerts.push({
    type: institutionalRetailDivergence > 0.3 ? 'warning' : 'info',
    message: tier1Score > tier3Score
      ? `Institutional (${tier1*100}%) more bullish than retail (${tier3*100}%)`
      : `Retail (${tier3*100}%) more bullish than institutional (${tier1*100}%)`
  });
}
```

**Thresholds:**
- **> 20% divergence:** Show info alert
- **> 30% divergence:** Show warning alert

**Interpretations:**
- **Institutional > Retail:** "Smart money" is more bullish - potential buy signal
- **Retail > Institutional:** Retail FOMO - potential top warning
- **Mainstream > Fringe:** Media narrative differs from underground sentiment

---

## Backend Integration

### Endpoints Used

#### 1. `/api/sentiment/latest?symbol=BTC`
**Original endpoint** - Symbol-specific sentiment

**Response:**
```json
{
  "overall_sentiment": 0.65,
  "fear_greed_index": 65,
  "social_breakdown": { "reddit": 0.7, "twitter": 0.6, ... },
  "sentiment_history": [...],
  ...
}
```

#### 2. `/api/sentiment/tiered` (NEW)
**Proxy to sentiment pipeline** - Tiered breakdown

**Response:**
```json
{
  "success": true,
  "data": {
    "overall_metrics": {
      "weighted_sentiment": 0.65,
      "confidence": 0.82
    },
    "tier_scores": {
      "tier1": 0.70,
      "tier2": 0.65,
      "tier3": 0.58,
      "fringe": 0.45
    },
    "divergences": [...],
    "total_data_points": 127,
    "timestamp": "2025-12-25T..."
  }
}
```

#### 3. `/api/sentiment/pipeline-health` (NEW)
**Health check** - Pipeline status

**Response (healthy):**
```json
{
  "success": true,
  "pipeline_running": true,
  "pipeline_url": "http://localhost:8002",
  "health_data": { "status": "healthy", ... }
}
```

**Response (offline):**
```json
{
  "success": false,
  "pipeline_running": false,
  "error": "Connection refused",
  "help": "Start the pipeline with: ./start_sentiment_pipeline.sh"
}
```

#### 4. `/api/sentiment/divergence?symbol=BTC`
**Proxy to sentiment pipeline** - Symbol-aware divergence analysis.

Returns:
```json
{
  "success": true,
  "data": {
    "alerts": [...],
    "tier_comparison": { ... },
    "timestamp": "2025-12-25T..."
  }
}
```

#### 5. `/api/sentiment/sources`
**Proxy + normalization** - The backend probes multiple pipeline paths and normalizes the result into `sources`:
- Tries `/sentiment/sources`, `/sources`, `/stats`, `/sentiment/stats`
- Returns `pipeline_url` that actually responded, plus `raw` when the shape is non-standard

**Known upstream variations:** the pipeline may expose source inventory at `/stats` or `/sources`; the backend adapts automatically.

---

## Testing the Integration

### 1. Start Everything

```bash
# Terminal 1: Start sentiment pipeline
./start_sentiment_pipeline.sh

# Terminal 2: Start main app
./start_local.sh

# Terminal 3: Test integration
./test_sentiment_integration.sh
```

### 2. Manual Testing

```bash
# Check pipeline health via backend proxy
curl http://localhost:5001/api/sentiment/pipeline-health | jq

# Get tiered sentiment
curl http://localhost:5001/api/sentiment/tiered | jq '.data.tier_scores'

# Check divergence
curl http://localhost:5001/api/sentiment/divergence | jq '.divergences'
```

### 3. UI Testing

1. **Open dashboard:** http://localhost:5173
2. **Click the info button** on any token
3. **Check Overview tab:**
   - Should see "Tiered Sentiment Analysis" section
   - 4 cards with scores and progress bars
   - Green "Live data from pipeline" status
4. **Look for divergence alerts:**
   - If tier1 vs tier3 > 20% difference, alert shows
5. **Test offline mode:**
   - Stop pipeline: `kill $(cat /tmp/mw_sentiment.pid)`
   - Refresh UI
   - Should show yellow warning: "Sentiment pipeline offline"

---

## What You'll See in the UI

### Scenario 1: Pipeline Running, No Divergence

```
┌─ Tiered Sentiment Analysis ─────────────────────┐
│                                                  │
│ T1: Institutional            68%                 │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░                           │
│                                                  │
│ T2: Mainstream               65%                 │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                           │
│                                                  │
│ T3: Retail                   64%                 │
│ ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░                           │
│                                                  │
│ Fringe Sources               62%                 │
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░                           │
│                                                  │
│ Live data from pipeline (127 data points)       │
└──────────────────────────────────────────────────┘
```

### Scenario 2: Pipeline Running, High Divergence

```
┌─ Tiered Sentiment Analysis ─────────────────────┐
│                                                  │
│ T1: Institutional            75% (strong)        │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░                           │
│                                                  │
│ T2: Mainstream               65%                 │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                           │
│                                                  │
│ T3: Retail                   42% (weak)          │
│ ▓▓▓▓▓░░░░░░░░░░░░░░░                           │
│                                                  │
│ Fringe Sources               38%                 │
│ ▓▓▓▓░░░░░░░░░░░░░░░░                           │
│                                                  │
│ Live data from pipeline (127 data points)       │
└──────────────────────────────────────────────────┘

┌─ Divergence Alerts ──────────────────────────────┐
│                                                  │
│ WARNING: Institutional sources (75%) more       │
│    bullish than retail (42%)                    │
│                                                  │
│ INFO: Mainstream media more bullish than fringe │
│    sources                                      │
└──────────────────────────────────────────────────┘
```

### Scenario 3: Pipeline Offline

```
┌─ Overview ───────────────────────────────────────┐
│                                                  │
│ Overall Sentiment: 65                           │
│ Fear & Greed: 65                                │
│                                                  │
│ (No tiered breakdown shown)                     │
│                                                  │
│ (Falls back to standard sentiment display)      │
└──────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Issue: "No tiered data showing"

**Symptoms:** Sentiment popup opens but no tier cards visible

**Causes:**
1. Sentiment pipeline not running
2. Pipeline running but backend can't reach it
3. API response missing `tier_scores`

**Solutions:**
```bash
# 1. Check if pipeline is running
curl http://localhost:8002/health

# 2. Check backend proxy
curl http://localhost:5001/api/sentiment/pipeline-health

# 3. Check tiered data
curl http://localhost:5001/api/sentiment/tiered | jq '.data.tier_scores'

# 4. Restart pipeline
kill $(cat /tmp/mw_sentiment.pid)
./start_sentiment_pipeline.sh

# 5. Check browser console for errors
# Open DevTools > Console tab
```

### Issue: "Divergence alerts not appearing"

**Cause:** Divergence threshold not met (< 20%)

**Check:**
```bash
# See raw tier scores
curl http://localhost:5001/api/sentiment/tiered | jq '.data.tier_scores'

# Output:
# {
#   "tier1": 0.65,
#   "tier3": 0.63   <- Only 2% difference, below 20% threshold
# }
```

**To test divergence detection:**
1. Modify threshold in `useTieredSentiment.js` temporarily:
   ```javascript
   if (institutionalRetailDivergence > 0.05) {  // Lower to 5%
   ```
2. Or wait for real market conditions where tiers diverge

### Issue: "Pipeline status always shows offline"

**Check:**
```bash
# 1. Verify pipeline is actually running
lsof -i:8002

# 2. Check health endpoint directly
curl http://localhost:8002/health

# 3. Check backend proxy
curl http://localhost:5001/api/sentiment/pipeline-health

# 4. Check browser network tab
# Should see request to /api/sentiment/pipeline-health
```

---

## Performance Notes

### Caching Strategy

**Hook-level caching:**
- Maintains `lastGoodRef` - last successful fetch
- Falls back to cached data on error
- 8-second cooldown after failures

**API-level caching:**
- Pipeline caches for 5 minutes (configurable)
- Symbol sentiment caches for 2 minutes

### Load Times

- **First load:** 1-3 seconds (parallel fetches)
- **Subsequent loads:** < 500ms (cached)
- **Auto-refresh:** Every 30 seconds (background)

### Data Freshness

- **Pipeline collection:** Every 30 minutes
- **UI refresh:** Every 30 seconds
- **Manual refresh:** Click "Refresh Now" button

---

## Future Enhancements

### Potential Additions

1. **Historical divergence charts**
   - Track tier divergence over time
   - Identify patterns before major moves

2. **Divergence notifications**
   - Browser notifications on high divergence
   - Webhook alerts for traders

3. **Source drill-down**
   - Click tier card to see contributing sources
   - See individual scores from Reddit, Twitter, etc.

4. **Sentiment heatmap**
   - Visual grid of all sources
   - Color-coded by sentiment intensity

5. **Correlation analysis**
   - Overlay tier sentiment on price chart
   - Show which tier historically leads price

6. **Custom tier weights**
   - Let users adjust tier importance
   - "Show me only institutional sentiment"

---

## API Reference Summary

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/api/sentiment/latest?symbol=BTC` | GET | Symbol-specific sentiment | Overall + social breakdown |
| `/api/sentiment/tiered` | GET | Tiered analysis | Tier scores + divergences |
| `/api/sentiment/pipeline-health` | GET | Pipeline status | Health check |
| `/api/sentiment/divergence` | GET | Divergence analysis | Detailed divergences |
| `/api/sentiment/sources` | GET | Source statistics | Source list + metadata |

---

## Files Changed

### New Files
- [frontend/src/hooks/useTieredSentiment.js](frontend/src/hooks/useTieredSentiment.js) - Enhanced sentiment hook

### Modified Files
- [frontend/src/components/SentimentPopupAdvanced.jsx](frontend/src/components/SentimentPopupAdvanced.jsx) - Added tier display
- [frontend/src/styles/sentiment-popup-advanced.css](frontend/src/styles/sentiment-popup-advanced.css) - Added tier styles

### Backend Files (Previously Created)
- [backend/app.py](backend/app.py) - Proxy endpoints (lines 1258-1425)
- [start_sentiment_pipeline.sh](start_sentiment_pipeline.sh) - Startup script

---

## Quick Start Checklist

- [ ] Sentiment pipeline running (`./start_sentiment_pipeline.sh`)
- [ ] Main app running (`./start_local.sh`)
- [ ] Test integration passes (`./test_sentiment_integration.sh`)
- [ ] Open http://localhost:5173
- [ ] Click info button on any token
- [ ] See "Tiered Sentiment Analysis" section
- [ ] See green pipeline status indicator
- [ ] Test divergence (check console: `curl ... | jq '.data.tier_scores'`)

---

**Created:** 2025-12-25
**Status:** Complete and tested
**Maintainer:** Moonwalking Team
