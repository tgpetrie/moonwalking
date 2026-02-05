# CBMoovers Sentiment Popup - API Integration Guide

## 📡 API Endpoint Requirements

### Base Endpoint
```
GET /sentiment/latest
```

### Expected Response Format

```json
{
  "overall_sentiment": 0.68,
  "fear_greed_index": 62,
  "total_sources": 5,
  "timestamp": "2024-12-06T10:30:00Z",
  
  "source_breakdown": {
    "tier1": 2,
    "tier2": 3,
    "tier3": 0
  },
  
  "social_metrics": {
    "volume_change": 12.5,
    "engagement_rate": 0.73,
    "mentions_24h": 42150
  },
  
  "social_breakdown": {
    "reddit": 0.72,
    "twitter": 0.65,
    "telegram": 0.78,
    "news": 0.70
  },
  
  "sentiment_history": [
    {
      "timestamp": "2024-12-06T10:00:00Z",
      "score": 65,
      "fear_greed": 60
    },
    {
      "timestamp": "2024-12-06T09:00:00Z",
      "score": 63,
      "fear_greed": 58
    }
    // ... 24 hours of hourly data points
  ],
  
  "sources": [
    {
      "name": "Fear & Greed Index",
      "score": 62,
      "tier": 1,
      "last_update": "2024-12-06T10:30:00Z",
      "reliability": 0.90,
      "status": "active"
    },
    {
      "name": "CoinGecko",
      "score": 71,
      "tier": 1,
      "last_update": "2024-12-06T10:29:45Z",
      "reliability": 0.85,
      "status": "active"
    },
    {
      "name": "CoinDesk",
      "score": 68,
      "tier": 2,
      "last_update": "2024-12-06T10:28:30Z",
      "reliability": 0.80,
      "status": "active"
    }
  ],
  
  "divergence_alerts": [
    {
      "type": "tier_divergence",
      "severity": "medium",
      "message": "Tier 1 sources bullish (72) while Tier 3 bearish (45)",
      "timestamp": "2024-12-06T10:15:00Z"
    }
  ]
}
```

## 🔧 Python Backend Example

### FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from pydantic import BaseModel

app = FastAPI(title="CBMoovers Sentiment API")

# CORS configuration for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cbmoovers.com",
        "https://www.cbmoovers.com",
        "http://localhost:3000",  # Development
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Pydantic models
class SentimentHistoryPoint(BaseModel):
    timestamp: datetime
    score: float
    fear_greed: float

class SourceData(BaseModel):
    name: str
    score: int
    tier: int
    last_update: datetime
    reliability: float = 0.70
    status: str = "active"

class DivergenceAlert(BaseModel):
    type: str
    severity: str
    message: str
    timestamp: datetime

class SentimentResponse(BaseModel):
    overall_sentiment: float
    fear_greed_index: int
    total_sources: int
    timestamp: datetime
    source_breakdown: Dict[str, int]
    social_metrics: Dict[str, float]
    social_breakdown: Dict[str, float]
    sentiment_history: List[SentimentHistoryPoint]
    sources: List[SourceData]
    divergence_alerts: List[DivergenceAlert]

# Data aggregation service
class SentimentAggregator:
    def __init__(self):
        self.fear_greed_cache = None
        self.cache_timestamp = None
        self.CACHE_TTL = 3600  # 1 hour
    
    async def fetch_fear_greed(self) -> int:
        """Fetch Fear & Greed Index from Alternative.me"""
        # Check cache
        if (self.fear_greed_cache and self.cache_timestamp and 
            (datetime.utcnow() - self.cache_timestamp).seconds < self.CACHE_TTL):
            return self.fear_greed_cache
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.alternative.me/fng/",
                    timeout=5.0
                )
                data = response.json()
                value = int(data['data'][0]['value'])
                
                # Update cache
                self.fear_greed_cache = value
                self.cache_timestamp = datetime.utcnow()
                
                return value
        except Exception as e:
            print(f"Error fetching F&G: {e}")
            return self.fear_greed_cache or 50  # Fallback
    
    async def fetch_coingecko_sentiment(self) -> float:
        """Fetch market sentiment from CoinGecko"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.coingecko.com/api/v3/global",
                    timeout=5.0
                )
                data = response.json()
                
                # Use market cap dominance as sentiment proxy
                btc_dominance = data['data']['market_cap_percentage']['btc']
                
                # Convert to 0-100 sentiment score
                # Higher BTC dominance = more conservative/fearful market
                sentiment = 100 - btc_dominance
                return sentiment
        except Exception as e:
            print(f"Error fetching CoinGecko: {e}")
            return 65.0  # Fallback
    
    async def fetch_reddit_sentiment(self, subreddit: str) -> float:
        """
        Fetch Reddit sentiment (placeholder - requires PRAW setup)
        In production, this would use Reddit API to analyze post sentiment
        """
        # TODO: Implement actual Reddit sentiment analysis
        # For now, return mock data
        return 72.0
    
    def calculate_weighted_sentiment(self, sources: List[SourceData]) -> float:
        """Calculate weighted average sentiment based on tier weights"""
        tier_weights = {1: 0.85, 2: 0.70, 3: 0.50}
        
        total_weight = 0
        weighted_sum = 0
        
        for source in sources:
            weight = tier_weights.get(source.tier, 0.50)
            weighted_sum += source.score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.50
        
        # Return as 0-1 scale
        return (weighted_sum / total_weight) / 100
    
    def generate_history(self, current_score: float, hours: int = 24) -> List[SentimentHistoryPoint]:
        """Generate sentiment history (in production, fetch from database)"""
        history = []
        now = datetime.utcnow()
        
        for i in range(hours, -1, -1):
            timestamp = now - timedelta(hours=i)
            
            # Add some realistic variation
            import random
            variation = random.uniform(-5, 5)
            score = max(0, min(100, (current_score * 100) + variation))
            fg_score = max(0, min(100, score + random.uniform(-3, 3)))
            
            history.append(SentimentHistoryPoint(
                timestamp=timestamp,
                score=score,
                fear_greed=fg_score
            ))
        
        return history
    
    def detect_divergences(self, sources: List[SourceData]) -> List[DivergenceAlert]:
        """Detect divergences between tier sentiments"""
        alerts = []
        
        # Group by tier
        tier_scores = {1: [], 2: [], 3: []}
        for source in sources:
            tier_scores[source.tier].append(source.score)
        
        # Calculate averages
        tier_avgs = {}
        for tier, scores in tier_scores.items():
            if scores:
                tier_avgs[tier] = sum(scores) / len(scores)
        
        # Check for divergence between Tier 1 and Tier 3
        if 1 in tier_avgs and 3 in tier_avgs:
            diff = abs(tier_avgs[1] - tier_avgs[3])
            if diff > 20:
                severity = "high" if diff > 30 else "medium"
                direction = "bullish" if tier_avgs[1] > tier_avgs[3] else "bearish"
                
                alerts.append(DivergenceAlert(
                    type="tier_divergence",
                    severity=severity,
                    message=f"Tier 1 sources {direction} ({tier_avgs[1]:.0f}) while Tier 3 opposite ({tier_avgs[3]:.0f})",
                    timestamp=datetime.utcnow()
                ))
        
        return alerts

aggregator = SentimentAggregator()

@app.get("/sentiment/latest", response_model=SentimentResponse)
async def get_latest_sentiment():
    """
    Get latest aggregated sentiment data from all sources
    """
    try:
        # Fetch data from various sources
        fear_greed = await aggregator.fetch_fear_greed()
        coingecko_sentiment = await aggregator.fetch_coingecko_sentiment()
        reddit_crypto = await aggregator.fetch_reddit_sentiment("cryptocurrency")
        reddit_bitcoin = await aggregator.fetch_reddit_sentiment("bitcoin")
        
        # Build source data
        sources = [
            SourceData(
                name="Fear & Greed Index",
                score=fear_greed,
                tier=1,
                last_update=datetime.utcnow(),
                reliability=0.90
            ),
            SourceData(
                name="CoinGecko",
                score=int(coingecko_sentiment),
                tier=1,
                last_update=datetime.utcnow(),
                reliability=0.85
            ),
            SourceData(
                name="Reddit (r/cryptocurrency)",
                score=int(reddit_crypto),
                tier=3,
                last_update=datetime.utcnow(),
                reliability=0.60
            ),
            SourceData(
                name="Reddit (r/bitcoin)",
                score=int(reddit_bitcoin),
                tier=3,
                last_update=datetime.utcnow(),
                reliability=0.55
            ),
            # Add more sources as you integrate them
            SourceData(
                name="CoinDesk",
                score=68,  # TODO: Implement news sentiment analysis
                tier=2,
                last_update=datetime.utcnow(),
                reliability=0.80
            )
        ]
        
        # Calculate overall sentiment
        overall_sentiment = aggregator.calculate_weighted_sentiment(sources)
        
        # Count sources by tier
        source_breakdown = {
            "tier1": sum(1 for s in sources if s.tier == 1),
            "tier2": sum(1 for s in sources if s.tier == 2),
            "tier3": sum(1 for s in sources if s.tier == 3)
        }
        
        # Generate history
        history = aggregator.generate_history(overall_sentiment)
        
        # Detect divergences
        divergences = aggregator.detect_divergences(sources)
        
        # Build response
        return SentimentResponse(
            overall_sentiment=overall_sentiment,
            fear_greed_index=fear_greed,
            total_sources=len(sources),
            timestamp=datetime.utcnow(),
            source_breakdown=source_breakdown,
            social_metrics={
                "volume_change": 12.5,  # TODO: Calculate actual change
                "engagement_rate": 0.73,  # TODO: Calculate from social data
                "mentions_24h": 42150  # TODO: Sum from all social sources
            },
            social_breakdown={
                "reddit": reddit_crypto / 100,
                "twitter": 0.65,  # TODO: Implement Twitter sentiment
                "telegram": 0.78,  # TODO: Implement Telegram sentiment
                "news": 0.70  # TODO: Implement news sentiment
            },
            sentiment_history=history,
            sources=sources,
            divergence_alerts=divergences
        )
        
    except Exception as e:
        print(f"Error in get_latest_sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

## 🚀 Running the API

### Local Development
```bash
# Install dependencies
pip install fastapi uvicorn httpx pydantic

# Run the API
python sentiment_api.py

# API will be available at http://localhost:8001
```

### Production Deployment (Docker)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "sentiment_api:app", "--host", "0.0.0.0", "--port", "8001"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  sentiment-api:
    build: .
    ports:
      - "8001:8001"
    environment:
      - ENV=production
      - ALLOWED_ORIGINS=https://cbmoovers.com
    restart: unless-stopped
```

## 🔐 Security Considerations

1. **CORS**: Restrict origins to your domain
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **API Keys**: Consider adding API key authentication
4. **Caching**: Implement Redis caching for frequently accessed data
5. **Monitoring**: Add logging and error tracking (Sentry, etc.)

## 📊 Data Source Integration Checklist

- [x] Fear & Greed Index (Alternative.me)
- [x] CoinGecko API
- [ ] Binance Funding Rates
- [ ] Reddit (r/cryptocurrency, r/bitcoin)
- [ ] Twitter/X Sentiment
- [ ] CoinDesk News Sentiment
- [ ] LunarCrush Social Data
- [ ] Santiment On-chain Metrics

## 🧪 Testing the API

```bash
# Test endpoint
curl http://localhost:8001/sentiment/latest

# Expected response
{
  "overall_sentiment": 0.68,
  "fear_greed_index": 62,
  "total_sources": 5,
  ...
}
```

## 📈 Next Steps

1. Implement remaining data sources (Reddit, Twitter, News)
2. Add database for historical data persistence
3. Implement caching layer (Redis)
4. Add rate limiting middleware
5. Set up monitoring and alerting
6. Deploy to production (AWS, GCP, or Digital Ocean)
