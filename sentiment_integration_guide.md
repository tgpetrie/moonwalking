# Python Backend Setup Guide
## Moonwalking Sentiment API

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### Step 2: Run the API
```bash
python sentiment_api.py
```

The API will start on **http://localhost:8001**

### Step 3: Test the API
```bash
# In another terminal
curl http://localhost:8001/sentiment/latest
```

---

## 📡 API Endpoints

### Main Endpoints

#### `GET /sentiment/latest`
Returns complete sentiment data for the popup card.

**Response:**
```json
{
  "overall_sentiment": 0.72,
  "fear_greed_index": 68,
  "social_metrics": {
    "volume_change": 15.2,
    "engagement_rate": 0.76,
    "mentions_24h": 35420
  },
  "social_breakdown": {
    "reddit": 0.82,
    "twitter": 0.68,
    "telegram": 0.88,
    "chan": 0.44
  },
  "source_breakdown": {
    "tier1": 30,
    "tier2": 35,
    "tier3": 25,
    "fringe": 10
  },
  "sentiment_history": [...],
  "social_history": [...],
  "trending_topics": [...],
  "divergence_alerts": [...]
}
```

#### `GET /sentiment/sources`
List all data sources with their tier and trust weights.

#### `GET /sentiment/history/{days}`
Get historical sentiment data (max 365 days).

#### `GET /sentiment/divergence`
Get current divergence alerts between source tiers.

#### `GET /sentiment/stats`
API statistics and metadata.

#### `WS /ws/sentiment`
WebSocket for real-time updates (every 30 seconds).

---

## 🔌 Frontend Integration

### Update your JavaScript to use the real API:

```javascript
// In your sentiment-popup.js or main script

const API_URL = 'http://localhost:8001';

async function loadSentimentData() {
    try {
        const response = await fetch(`${API_URL}/sentiment/latest`);
        const data = await response.json();
        
        // Update UI with real data
        updateSentimentUI(data);
    } catch (error) {
        console.error('Failed to load sentiment:', error);
    }
}

function updateSentimentUI(data) {
    // Overall score
    document.getElementById('overallScore').textContent = 
        Math.round(data.overall_sentiment * 100);
    
    // Fear & Greed
    document.getElementById('fearGreed').textContent = 
        `${getFearGreedLabel(data.fear_greed_index)} (${data.fear_greed_index})`;
    
    // Social volume
    document.getElementById('socialVolume').textContent = 
        `${data.social_metrics.volume_change > 0 ? '+' : ''}${data.social_metrics.volume_change}%`;
    
    // Sentiment bar
    document.querySelector('.sentiment-fill').style.width = 
        `${data.overall_sentiment * 100}%`;
    
    // Update charts with historical data
    updateCharts(data);
}

function getFearGreedLabel(index) {
    if (index >= 75) return 'Extreme Greed';
    if (index >= 55) return 'Greed';
    if (index >= 45) return 'Neutral';
    if (index >= 25) return 'Fear';
    return 'Extreme Fear';
}

// Load data on popup open
document.getElementById('infoIcon').addEventListener('click', () => {
    loadSentimentData();
});

// Auto-refresh every 30 seconds
setInterval(loadSentimentData, 30000);
```

---

## 🔄 WebSocket Integration (Real-time Updates)

```javascript
// Connect to WebSocket for live updates
const ws = new WebSocket('ws://localhost:8001/ws/sentiment');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'sentiment_update') {
        updateSentimentUI(data.data);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket closed, attempting reconnect...');
    setTimeout(() => {
        // Reconnect logic
    }, 5000);
};
```

---

## 🛠️ Connecting Real Data Sources

The API currently uses **mock data generators**. To connect real sources:

### 1. Reddit Integration (r/CryptoCurrency, r/Bitcoin, etc.)

```python
import praw

# Add to your API
reddit = praw.Reddit(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    user_agent="moonwalking-sentiment/1.0"
)

def get_reddit_sentiment(subreddit_name: str):
    subreddit = reddit.subreddit(subreddit_name)
    posts = subreddit.hot(limit=100)
    
    sentiment_scores = []
    for post in posts:
        # Analyze post title and body
        score = analyze_text_sentiment(post.title + " " + post.selftext)
        sentiment_scores.append(score)
    
    return sum(sentiment_scores) / len(sentiment_scores)
```

### 2. Fear & Greed Index (Real API)

```python
import requests

def get_fear_greed_index():
    response = requests.get('https://api.alternative.me/fng/')
    data = response.json()
    return int(data['data'][0]['value'])
```

### 3. LunarCrush API

```python
import requests

LUNARCRUSH_API_KEY = "your_api_key"

def get_lunarcrush_sentiment(symbol: str):
    url = f"https://api.lunarcrush.com/v2"
    params = {
        "data": "assets",
        "symbol": symbol,
        "key": LUNARCRUSH_API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data['data'][0]['sentiment']
```

### 4. Twitter/X Sentiment

```python
import tweepy

# Setup Twitter API
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

def get_twitter_sentiment(query: str):
    tweets = api.search_tweets(q=query, count=100)
    
    sentiment_scores = []
    for tweet in tweets:
        score = analyze_text_sentiment(tweet.text)
        sentiment_scores.append(score)
    
    return sum(sentiment_scores) / len(sentiment_scores)
```

---

## 📊 Replace Mock Data with Real Data

In `sentiment_api.py`, replace the mock generators:

```python
@app.get("/sentiment/latest", response_model=SentimentResponse)
async def get_latest_sentiment():
    """Get real sentiment data"""
    
    # Real data from sources
    overall_sentiment = calculate_weighted_sentiment([
        (get_coindesk_sentiment(), 0.9),      # Tier 1
        (get_reddit_sentiment(), 0.7),         # Tier 2
        (get_telegram_sentiment(), 0.5),       # Tier 3
    ])
    
    fear_greed = get_fear_greed_index()  # Real API
    
    social_breakdown = SocialBreakdown(
        reddit=get_reddit_sentiment(),
        twitter=get_twitter_sentiment("#Bitcoin"),
        telegram=get_telegram_sentiment(),
        chan=get_4chan_sentiment()
    )
    
    return SentimentResponse(
        overall_sentiment=overall_sentiment,
        fear_greed_index=fear_greed,
        social_breakdown=social_breakdown,
        # ... rest of data
    )
```

---

## 🗄️ Database Integration (Optional)

To store historical data:

```python
from sqlalchemy import create_engine, Column, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class SentimentRecord(Base):
    __tablename__ = 'sentiment_history'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    overall_sentiment = Column(Float)
    fear_greed_index = Column(Integer)
    reddit_sentiment = Column(Float)
    twitter_sentiment = Column(Float)

# Create engine
engine = create_engine('postgresql://user:pass@localhost/moonwalking')
Base.metadata.create_all(engine)

# Use in your API
def save_sentiment_snapshot(data: SentimentResponse):
    Session = sessionmaker(bind=engine)
    session = Session()
    
    record = SentimentRecord(
        overall_sentiment=data.overall_sentiment,
        fear_greed_index=data.fear_greed_index,
        reddit_sentiment=data.social_breakdown.reddit,
        twitter_sentiment=data.social_breakdown.twitter
    )
    
    session.add(record)
    session.commit()
    session.close()
```

---

## 🔐 Environment Variables (.env)

Create a `.env` file:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8001

# Reddit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret

# Twitter/X
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret

# LunarCrush
LUNARCRUSH_API_KEY=your_api_key

# CoinGecko
COINGECKO_API_KEY=your_api_key

# Database
DATABASE_URL=postgresql://user:pass@localhost/moonwalking
REDIS_URL=redis://localhost:6379/0
```

Load in your API:

```python
from dotenv import load_dotenv
import os

load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
```

---

## 🧪 Testing

```bash
# Run tests
pytest test_sentiment_api.py

# Test specific endpoint
pytest test_sentiment_api.py::test_latest_sentiment

# With coverage
pytest --cov=sentiment_api
```

---

## 🚀 Production Deployment

### Using Docker:

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sentiment_api.py .

CMD ["uvicorn", "sentiment_api:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# Build and run
docker build -t moonwalking-sentiment .
docker run -p 8001:8001 moonwalking-sentiment
```

### Using systemd (Linux):

```ini
# /etc/systemd/system/moonwalking-sentiment.service
[Unit]
Description=Moonwalking Sentiment API
After=network.target

[Service]
User=moonwalking
WorkingDirectory=/opt/moonwalking
ExecStart=/opt/moonwalking/venv/bin/uvicorn sentiment_api:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable moonwalking-sentiment
sudo systemctl start moonwalking-sentiment
```

---

## 📈 Next Steps

1. ✅ Start the API with mock data
2. ✅ Connect your frontend to the API
3. ✅ Test all endpoints
4. ⚙️ Replace mock data with real sources (one at a time)
5. 💾 Add database for historical data
6. 🔄 Implement caching (Redis) for performance
7. 🚀 Deploy to production

---

## 🆘 Troubleshooting

**CORS errors:**
```python
# Update CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Port already in use:**
```bash
# Kill process on port 8001
lsof -ti:8001 | xargs kill -9

# Or use a different port
uvicorn sentiment_api:app --port 8002
```

**API not responding:**
```bash
# Check if server is running
curl http://localhost:8001/health

# Check logs
tail -f sentiment_api.log
```

---

Ready to go! Start with the mock data API, then gradually integrate real data sources. 🌙🚀
