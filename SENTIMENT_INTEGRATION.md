# Sentiment Pipeline Integration

This document describes how the tiered sentiment pipeline is integrated into the Moonwalking dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  TieredSentimentPanel Component                      │  │
│  │  - Displays tier breakdown (Tier1, Tier2, Tier3)     │  │
│  │  - Shows divergence alerts                           │  │
│  │  - Real-time updates                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP GET /api/sentiment/tiered
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Backend (Flask) - Port 5001                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Proxy Endpoints (app.py)                            │  │
│  │  - /api/sentiment/tiered                             │  │
│  │  - /api/sentiment/pipeline-health                    │  │
│  │  - /api/sentiment/divergence                         │  │
│  │  - /api/sentiment/sources                            │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP GET localhost:8002
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         Sentiment Pipeline (FastAPI) - Port 8002             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  main_runner.py (FastAPI server)                     │  │
│  │  - sentiment_orchestrator.py                         │  │
│  │  - reddit_handler.py                                 │  │
│  │  - telegram_handler.py                               │  │
│  │  - custom_scrapers.py (4chan, BitcoinTalk, etc.)    │  │
│  │  - chinese_sources.py (Weibo, 8btc)                 │  │
│  │  - rss_handler.py                                    │  │
│  │  - data_aggregator.py (tiered analysis)             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Sentiment Pipeline (Port 8002)

**Location:** `backend/main_runner.py`

The sentiment pipeline is a standalone FastAPI service that:
- Collects sentiment from 50+ sources across 4 tiers
- Aggregates and weights data by source credibility
- Detects divergence between institutional and retail sentiment
- Runs continuously in the background

**Tiers:**
- **Tier 1** (Institutional): CoinGecko, Binance, Fear & Greed Index
- **Tier 2** (Mainstream): CoinDesk RSS, Reddit r/CryptoCurrency, r/Bitcoin
- **Tier 3** (Retail): r/SatoshiStreetBets, r/CryptoMoonShots, Telegram
- **Fringe**: 4chan /biz/, BitcoinTalk, Chinese forums (Weibo, 8btc)

**Endpoints:**
- `GET /health` - Health check
- `GET /sentiment/latest` - Latest aggregated sentiment
- `GET /sentiment/history` - Historical data
- `GET /stats` - System statistics

### 2. Backend Proxy (Port 5001)

**Location:** `backend/app.py` (lines 1258-1425)

Flask proxy endpoints that forward requests to the sentiment pipeline:

#### `/api/sentiment/tiered`
Returns tiered sentiment data with breakdown by source tier.

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
    "timestamp": "2025-12-25T..."
  }
}
```

#### `/api/sentiment/pipeline-health`
Checks if the sentiment pipeline is running.

**Response (healthy):**
```json
{
  "success": true,
  "pipeline_running": true,
  "pipeline_url": "http://localhost:8002",
  "health_data": {...}
}
```

**Response (offline):**
```json
{
  "success": false,
  "pipeline_running": false,
  "error": "Connection refused - pipeline not running",
  "help": "Start the pipeline with: ./start_sentiment_pipeline.sh"
}
```

#### `/api/sentiment/divergence`
Analyzes divergence between different sentiment tiers.

**Response:**
```json
{
  "success": true,
  "divergences": [
    {
      "type": "institutional_vs_retail",
      "tier1_score": 0.75,
      "tier3_score": 0.45,
      "divergence": 0.30,
      "severity": "high",
      "message": "Institutional sentiment (0.75) diverges from retail (0.45)"
    }
  ],
  "tier_scores": {...},
  "overall_sentiment": 0.65
}
```

#### `/api/sentiment/sources`
Returns statistics about all data sources.

### 3. Frontend Components

#### Hook: `useTieredSentiment.js`

**Location:** `frontend/src/hooks/useTieredSentiment.js` (to be created)

Custom React hook that:
- Fetches tiered sentiment data
- Checks pipeline health
- Auto-refreshes every 30 seconds
- Handles errors gracefully

**Usage:**
```javascript
const { data, loading, error, pipelineHealth } = useTieredSentiment();
```

#### Component: `TieredSentimentPanel.jsx`

**Location:** `frontend/src/components/TieredSentimentPanel.jsx` (to be created)

Displays:
- Overall sentiment score
- Tier breakdown with visual bars
- Divergence alerts (when tiers disagree)
- Data freshness timestamp
- Warning if pipeline is offline

## Setup Instructions

### 1. Start the Sentiment Pipeline

```bash
./start_sentiment_pipeline.sh
```

This script:
- Starts the sentiment pipeline on port 8002
- Activates the Python virtual environment
- Runs `main_runner.py` in API mode
- Stores PID in `/tmp/mw_sentiment.pid`
- Logs to `/tmp/mw_sentiment.log`

### 2. Start the Main Backend

```bash
./start_local.sh
```

This starts both the Flask backend (port 5001) and frontend (port 5173).

### 3. Verify Integration

```bash
./test_sentiment_integration.sh
```

This test script checks:
1. Sentiment pipeline health
2. Backend health
3. Proxy endpoint functionality
4. Tiered sentiment data
5. Divergence analysis
6. Sources endpoint

## Usage

### Manual API Testing

```bash
# Check pipeline health
curl http://localhost:5001/api/sentiment/pipeline-health | jq

# Get tiered sentiment
curl http://localhost:5001/api/sentiment/tiered | jq

# Check divergence
curl http://localhost:5001/api/sentiment/divergence | jq

# Get source statistics
curl http://localhost:5001/api/sentiment/sources | jq
```

### Frontend Integration

Add the `TieredSentimentPanel` component to your dashboard:

```jsx
import { TieredSentimentPanel } from './components/TieredSentimentPanel';

function Dashboard() {
  return (
    <div className="dashboard">
      {/* Existing components */}

      <div className="sentiment-panel">
        <TieredSentimentPanel />
      </div>
    </div>
  );
}
```

## Monitoring

### Logs

- **Sentiment Pipeline:** `/tmp/mw_sentiment.log`
- **Backend:** `/tmp/mw_backend.log`
- **Frontend:** `/tmp/mw_frontend.log`

### Check Status

```bash
# View running processes
./start_local.sh status

# Check sentiment pipeline PID
cat /tmp/mw_sentiment.pid

# Check sentiment pipeline port
cat /tmp/mw_sentiment.port

# Tail sentiment logs
tail -f /tmp/mw_sentiment.log
```

### Stop Services

```bash
# Stop sentiment pipeline
kill $(cat /tmp/mw_sentiment.pid)

# Or kill by port
lsof -ti:8002 | xargs kill
```

## Configuration

### Environment Variables

```bash
# Customize sentiment pipeline URL (default: http://localhost:8002)
export SENTIMENT_PIPELINE_URL=http://localhost:8002

# Customize ports
export SENTIMENT_PORT=8002
export BACKEND_PORT=5001
```

### Pipeline Configuration

The sentiment pipeline uses `backend/config/sentiment_config.yaml` for:
- Source weights by tier
- API credentials (Reddit, Telegram, etc.)
- Collection intervals
- Cache settings

## Troubleshooting

### Pipeline Won't Start

**Issue:** `./start_sentiment_pipeline.sh` fails

**Solution:**
1. Check logs: `tail -50 /tmp/mw_sentiment.log`
2. Verify Python environment: `which python3`
3. Check dependencies: `pip list | grep -E "fastapi|uvicorn"`
4. Ensure port 8002 is free: `lsof -i:8002`

### 503 Error on `/api/sentiment/tiered`

**Issue:** Backend returns 503 Service Unavailable

**Cause:** Sentiment pipeline is not running

**Solution:**
```bash
# Start the pipeline
./start_sentiment_pipeline.sh

# Verify it's running
curl http://localhost:8002/health
```

### Missing Data in Frontend

**Issue:** `TieredSentimentPanel` shows "Pipeline Offline"

**Cause:** Either:
1. Pipeline not started
2. Backend can't reach pipeline
3. Port mismatch

**Solution:**
```bash
# Test pipeline health via backend
curl http://localhost:5001/api/sentiment/pipeline-health

# Check if pipeline is accessible
curl http://localhost:8002/health
```

### Divergence Alerts Not Showing

**Issue:** No divergence alerts despite tier differences

**Cause:** Divergence threshold not met (default: 20%)

**Solution:** Check raw tier scores:
```bash
curl http://localhost:5001/api/sentiment/tiered | jq '.data.tier_scores'
```

## Development

### Adding New Data Sources

1. Add handler in `backend/` (e.g., `new_source_handler.py`)
2. Register in `sentiment_orchestrator.py`
3. Configure in `config/sentiment_config.yaml`
4. Restart pipeline: `kill $(cat /tmp/mw_sentiment.pid) && ./start_sentiment_pipeline.sh`

### Modifying Tier Weights

Edit `backend/config/sentiment_config.yaml`:

```yaml
tier_weights:
  tier1: 0.85  # Institutional (highest trust)
  tier2: 0.70  # Mainstream
  tier3: 0.50  # Retail
  fringe: 0.30 # Fringe sources
```

## Next Steps

1. **Create Frontend Components:**
   - `frontend/src/hooks/useTieredSentiment.js`
   - `frontend/src/components/TieredSentimentPanel.jsx`

2. **Integrate into Dashboard:**
   - Add `<TieredSentimentPanel />` to main dashboard

3. **Optional Enhancements:**
   - Add WebSocket support for real-time updates
   - Create historical charts for tier trends
   - Add source-specific drill-down views
   - Implement alert notifications for high divergence

## API Reference

See the complete API documentation at:
- Sentiment Pipeline: `http://localhost:8002/docs` (FastAPI auto-generated)
- Backend endpoints: See `backend/app.py` lines 1258-1425

## Performance

- **Pipeline Collection:** Runs every 30 minutes (configurable)
- **API Response Time:** < 100ms (cached), < 5s (fresh data)
- **Memory Usage:** ~200MB for pipeline, ~150MB for backend
- **Data Freshness:** Updated every 30 minutes

## Security

- No authentication required for local development
- For production:
  - Add API key authentication
  - Use HTTPS for all endpoints
  - Rate limit proxy endpoints
  - Sanitize all external data sources

---

**Created:** 2025-12-25
**Last Updated:** 2025-12-25
**Maintainer:** Moonwalking Team
