# Moonwalking Sentiment System - Complete Setup Guide

## 📦 Files You Need

```
moonwalking-sentiment/
├── sentiment_config.yaml           # Configuration
├── sentiment_data_sources.py       # Data collection engine
├── sentiment_api.py                # FastAPI server
├── requirements.txt                # Python dependencies
├── .env                           # Your credentials (create from .env.example)
└── .env.example                   # Template for environment variables
```

---

## 🚀 Quick Start (5 Steps)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Get Reddit API Credentials (Required)

Reddit is the main data source for Tier 2/3 sentiment.

1. **Go to**: https://www.reddit.com/prefs/apps
2. **Click**: "create another app..."
3. **Fill in**:
   - Name: `moonwalking-sentiment`
   - Type: Select **"script"**
   - Description: `Crypto sentiment analysis`
   - Redirect URI: `http://localhost:8080`
4. **Click**: "create app"
5. **Copy**:
   - **Client ID**: The string under "personal use script"
   - **Client Secret**: The longer string labeled "secret"

### Step 3: Create .env File

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env  # or use any text editor
```

Add your Reddit credentials:
```bash
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_secret_here
```

### Step 4: Run the API

```bash
python sentiment_api.py
```

You should see:
```
🌙 Moonwalking Sentiment API
============================================================
📊 Endpoints:
   GET  /sentiment/latest      - Latest sentiment data
   ...
🚀 Starting server on http://localhost:8001
```

### Step 5: Test It

```bash
# In another terminal
curl http://localhost:8001/sentiment/latest
```

You should get back JSON with real sentiment data!

---

## 🔧 Configuration Options

### Edit `sentiment_config.yaml` to:

#### 1. Enable/Disable Sources

```yaml
sources:
  tier1:
    - name: "Fear & Greed Index"
      enabled: true  # Set to false to disable
```

#### 2. Adjust Update Frequency

```yaml
sentiment:
  update_interval: 30  # Update every 30 seconds
  cache_ttl: 300      # Cache for 5 minutes
```

#### 3. Add/Remove Subreddits

```yaml
reddit:
  subreddits:
    tier2:
      - "CryptoCurrency"
      - "Bitcoin"
      - "ethereum"  # Add more
    tier3:
      - "SatoshiStreetBets"
      - "CryptoMoonShots"
```

#### 4. Adjust Tier Weights

```yaml
sentiment:
  tier_weights:
    tier1: 0.85  # Institutional sources
    tier2: 0.70  # Mainstream sources
    tier3: 0.50  # Retail sources
    fringe: 0.30 # Fringe sources
```

---

## 🌐 Frontend Integration

### Update your HTML/JavaScript:

```javascript
// In your sentiment popup JavaScript

const API_URL = 'http://localhost:8001';

// Fetch real sentiment data
async function loadSentimentData() {
    try {
        const response = await fetch(`${API_URL}/sentiment/latest`);
        const data = await response.json();
        
        console.log('Real sentiment data:', data);
        
        // Update UI
        updateSentimentUI(data);
        
    } catch (error) {
        console.error('Failed to load sentiment:', error);
    }
}

function updateSentimentUI(data) {
    // Overall sentiment score (0-1)
    const score = Math.round(data.overall_sentiment * 100);
    document.getElementById('overallScore').textContent = score;
    
    // Fear & Greed Index
    document.getElementById('fearGreed').textContent = 
        `${getFearGreedLabel(data.fear_greed_index)} (${data.fear_greed_index})`;
    
    // Social breakdown
    document.getElementById('redditScore').textContent = 
        Math.round(data.social_breakdown.reddit * 100) + '%';
    
    // Sentiment bar
    document.querySelector('.sentiment-fill').style.width = score + '%';
    
    // Update charts
    updateCharts(data.sentiment_history, data.social_history);
}

function getFearGreedLabel(index) {
    if (index >= 75) return 'Extreme Greed';
    if (index >= 55) return 'Greed';
    if (index >= 45) return 'Neutral';
    if (index >= 25) return 'Fear';
    return 'Extreme Fear';
}

// Call when popup opens
document.getElementById('infoIcon').addEventListener('click', () => {
    loadSentimentData();
});

// Auto-refresh every 30 seconds
setInterval(loadSentimentData, 30000);
```

### Or use WebSocket for Real-time Updates:

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/sentiment');

ws.onopen = () => {
    console.log('Connected to sentiment WebSocket');
    // Send ping every 30 seconds to keep alive
    setInterval(() => ws.send('ping'), 30000);
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'initial' || message.type === 'sentiment_update') {
        updateSentimentUI(message.data);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket closed');
    // Reconnect after 5 seconds
    setTimeout(() => location.reload(), 5000);
};
```

---

## 📊 API Endpoints Reference

### Main Endpoints

#### `GET /sentiment/latest`
**Complete sentiment data for the popup**

Response includes:
- `overall_sentiment`: 0-1 score
- `fear_greed_index`: 0-100
- `social_breakdown`: {reddit, twitter, telegram, chan}
- `source_breakdown`: {tier1, tier2, tier3, fringe}
- `sentiment_history`: Array of historical points
- `social_history`: Social platform history
- `trending_topics`: Popular hashtags/topics
- `divergence_alerts`: Tier divergence warnings

#### `GET /sentiment/sources`
**List all active data sources**

Returns array of sources with:
- name, tier, trust_weight
- current sentiment_score
- last_updated, status

#### `GET /sentiment/history/7`
**Get 7 days of historical data**

#### `GET /sentiment/divergence`
**Divergence analysis between tiers**

#### `GET /sentiment/refresh`
**Force refresh (bypass cache)**

#### `GET /stats`
**API statistics and metrics**

#### `WS /ws/sentiment`
**Real-time WebSocket updates**

---

## 🔍 Data Sources Explained

### Tier 1 (High Trust 0.85)
**Sources**: Fear & Greed Index, CoinGecko, Binance RSS

These are institutional and high-quality data sources. They're heavily weighted in the final sentiment score.

**No API keys needed** - these are free public APIs.

### Tier 2 (Medium Trust 0.70)
**Sources**: Reddit (r/CryptoCurrency, r/Bitcoin), CoinDesk RSS, CryptoSlate RSS

Mainstream crypto community sources. Requires Reddit API for subreddit data.

**Reddit API required** (free).

### Tier 3 (Lower Trust 0.50)
**Sources**: Reddit (r/SatoshiStreetBets, r/CryptoMoonShots)

Retail/speculative communities. Good for early sentiment signals but noisy.

**Uses same Reddit API** as Tier 2.

### Fringe (Low Trust 0.30)
**Sources**: 4chan /biz/ (optional)

Very early signals but extremely noisy. Not included by default.

---

## ⚙️ Advanced Configuration

### Adding More RSS Feeds

Edit `sentiment_config.yaml`:

```yaml
sources:
  tier2:
    - name: "Bitcoin Magazine RSS"
      enabled: true
      url: "https://bitcoinmagazine.com/.rss/full/"
      weight: 0.75
      update_frequency: 900
```

### Custom Sentiment Lexicon

Edit in `sentiment_data_sources.py`:

```python
crypto_terms = {
    'your_bullish_term': 2.0,
    'your_bearish_term': -2.0,
}
```

### Time Decay

Adjust how quickly old data loses relevance:

```yaml
sentiment:
  time_decay:
    enabled: true
    half_life_hours: 6  # Data loses half its weight every 6 hours
```

---

## 🧪 Testing

### Test Individual Sources

```python
# Test Fear & Greed
python -c "
import asyncio
from sentiment_data_sources import FearGreedCollector

async def test():
    collector = FearGreedCollector()
    data = await collector.fetch()
    print(data)

asyncio.run(test())
"
```

### Test Reddit

```python
# Test Reddit (requires .env with credentials)
python -c "
import asyncio
from sentiment_data_sources import RedditCollector
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    collector = RedditCollector(
        os.getenv('REDDIT_CLIENT_ID'),
        os.getenv('REDDIT_CLIENT_SECRET'),
        'moonwalking-test/1.0'
    )
    data = await collector.fetch_subreddit('CryptoCurrency', 'tier2', 10)
    print(f'Collected {len(data)} posts')
    for d in data[:3]:
        print(f'- {d.text}: {d.sentiment_score}')

asyncio.run(test())
"
```

### Run All Tests

```bash
pytest tests/
```

---

## 🐛 Troubleshooting

### Reddit API Issues

**Error**: `praw.exceptions.ResponseException: received 401 HTTP response`

**Solution**: Check your Reddit credentials in `.env`:
```bash
# Make sure these are correct
echo $REDDIT_CLIENT_ID
echo $REDDIT_CLIENT_SECRET
```

Re-create your Reddit app if needed: https://www.reddit.com/prefs/apps

---

### No Data Collected

**Check logs**:
```bash
tail -f logs/sentiment.log
```

**Enable debug logging**:
```python
# In sentiment_api.py, change:
logging.basicConfig(level=logging.DEBUG)
```

---

### CORS Errors

**Update** `sentiment_api.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    ...
)
```

---

### Port Already in Use

```bash
# Kill process on port 8001
lsof -ti:8001 | xargs kill -9

# Or use different port
uvicorn sentiment_api:app --port 8002
```

---

## 🚀 Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "sentiment_api:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
docker build -t moonwalking-sentiment .
docker run -p 8001:8001 --env-file .env moonwalking-sentiment
```

### Using systemd

```ini
# /etc/systemd/system/moonwalking-sentiment.service
[Unit]
Description=Moonwalking Sentiment API
After=network.target

[Service]
User=moonwalking
WorkingDirectory=/opt/moonwalking
Environment="PATH=/opt/moonwalking/venv/bin"
EnvironmentFile=/opt/moonwalking/.env
ExecStart=/opt/moonwalking/venv/bin/python sentiment_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable moonwalking-sentiment
sudo systemctl start moonwalking-sentiment
sudo systemctl status moonwalking-sentiment
```

---

## 📈 Monitoring

### Check Health

```bash
curl http://localhost:8001/health
```

### View Stats

```bash
curl http://localhost:8001/stats
```

### Monitor Logs

```bash
tail -f logs/sentiment.log
```

---

## 🎯 Next Steps

1. ✅ Get Reddit API credentials
2. ✅ Install dependencies
3. ✅ Create .env file
4. ✅ Run the API
5. ✅ Test with curl
6. ✅ Connect your frontend
7. ⚙️ Customize sources in config
8. 📊 Add more data sources (Twitter, Telegram, etc.)
9. 🚀 Deploy to production

---

## 💡 Tips

- **Start simple**: Begin with just Reddit + Fear & Greed, then add more sources
- **Monitor costs**: Most APIs have free tiers - track your usage
- **Cache wisely**: 5-minute cache is good for most use cases
- **Rate limiting**: Be respectful of API rate limits
- **Quality over quantity**: Better to have 5 good sources than 50 noisy ones

---

## 🆘 Need Help?

1. Check logs: `tail -f logs/sentiment.log`
2. Enable debug mode: `LOG_LEVEL=DEBUG` in `.env`
3. Test individual components (see Testing section)
4. Check Reddit API status: https://www.redditstatus.com/

---

Ready to go! 🌙🚀

Your sentiment system will now collect real data from multiple sources and provide comprehensive sentiment analysis for your moonwalking dashboard.
