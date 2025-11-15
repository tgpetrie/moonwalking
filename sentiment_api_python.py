#!/usr/bin/env python3
"""
Sentiment API Backend for Moonwalking Dashboard
Provides endpoints for the sentiment info popup
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from enum import Enum
import random

app = FastAPI(title="Moonwalking Sentiment API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# DATA MODELS
# ============================================================================

class SentimentTier(str, Enum):
    TIER_1 = "tier1"
    TIER_2 = "tier2"
    TIER_3 = "tier3"
    FRINGE = "fringe"


class SocialPlatform(str, Enum):
    REDDIT = "reddit"
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    CHAN = "4chan"


class SentimentMetric(BaseModel):
    overall_sentiment: float  # 0.0 to 1.0
    fear_greed_index: int  # 0 to 100
    social_volume_change: float  # percentage
    trend: str  # "bullish", "bearish", "neutral"


class SocialBreakdown(BaseModel):
    reddit: float
    twitter: float
    telegram: float
    chan: float


class SourceBreakdown(BaseModel):
    tier1: int
    tier2: int
    tier3: int
    fringe: int


class HistoricalPoint(BaseModel):
    timestamp: datetime
    sentiment: float
    price_normalized: float


class SocialHistoryPoint(BaseModel):
    timestamp: datetime
    reddit: float
    twitter: float
    telegram: float
    chan: float


class DataSource(BaseModel):
    name: str
    description: str
    tier: SentimentTier
    trust_weight: float
    last_updated: datetime


class SentimentResponse(BaseModel):
    overall_sentiment: float
    fear_greed_index: int
    social_metrics: Dict
    social_breakdown: SocialBreakdown
    source_breakdown: SourceBreakdown
    sentiment_history: List[HistoricalPoint]
    social_history: List[SocialHistoryPoint]
    trending_topics: List[Dict[str, str]]
    divergence_alerts: List[Dict[str, str]]


# ============================================================================
# MOCK DATA GENERATORS (Replace with real data sources)
# ============================================================================

def generate_sentiment_score() -> float:
    """Generate realistic sentiment score"""
    return round(0.5 + random.uniform(-0.3, 0.3), 2)


def generate_fear_greed_index() -> int:
    """Generate Fear & Greed Index (0-100)"""
    return random.randint(45, 85)


def generate_social_breakdown() -> SocialBreakdown:
    """Generate social media sentiment breakdown"""
    return SocialBreakdown(
        reddit=round(random.uniform(0.6, 0.9), 2),
        twitter=round(random.uniform(0.5, 0.8), 2),
        telegram=round(random.uniform(0.7, 0.95), 2),
        chan=round(random.uniform(0.3, 0.6), 2)
    )


def generate_source_breakdown() -> SourceBreakdown:
    """Generate source distribution"""
    return SourceBreakdown(
        tier1=30,
        tier2=35,
        tier3=25,
        fringe=10
    )


def generate_sentiment_history(days: int = 7) -> List[HistoricalPoint]:
    """Generate historical sentiment data"""
    history = []
    base_time = datetime.now() - timedelta(days=days)
    
    for i in range(days):
        timestamp = base_time + timedelta(days=i)
        sentiment = round(0.5 + (i * 0.05) + random.uniform(-0.1, 0.1), 2)
        price = round(60 + (i * 2) + random.uniform(-3, 3), 2)
        
        history.append(HistoricalPoint(
            timestamp=timestamp,
            sentiment=sentiment,
            price_normalized=price
        ))
    
    return history


def generate_social_history(days: int = 7) -> List[SocialHistoryPoint]:
    """Generate social media history"""
    history = []
    base_time = datetime.now() - timedelta(days=days)
    
    for i in range(days):
        timestamp = base_time + timedelta(days=i)
        
        history.append(SocialHistoryPoint(
            timestamp=timestamp,
            reddit=round(0.65 + (i * 0.03) + random.uniform(-0.05, 0.05), 2),
            twitter=round(0.58 + (i * 0.02) + random.uniform(-0.05, 0.05), 2),
            telegram=round(0.70 + (i * 0.04) + random.uniform(-0.05, 0.05), 2),
            chan=round(0.45 + random.uniform(-0.1, 0.1), 2)
        ))
    
    return history


def generate_trending_topics() -> List[Dict[str, str]]:
    """Generate trending topics"""
    topics = [
        {"tag": "#Bitcoin", "sentiment": "bullish", "volume": "+124%"},
        {"tag": "#HODL", "sentiment": "bullish", "volume": "+89%"},
        {"tag": "#Lightning", "sentiment": "bullish", "volume": "+45%"},
        {"tag": "#ToTheMoon", "sentiment": "neutral", "volume": "+12%"},
        {"tag": "#Correction", "sentiment": "bearish", "volume": "+67%"}
    ]
    return topics


def generate_divergence_alerts() -> List[Dict[str, str]]:
    """Generate divergence alerts"""
    alerts = []
    
    # Random chance of divergence
    if random.random() > 0.5:
        alerts.append({
            "type": "warning",
            "message": "Divergence Detected: Fringe sources showing extreme bullishness (+45%) while Tier 1 sources remain neutral."
        })
    
    if random.random() > 0.7:
        alerts.append({
            "type": "success",
            "message": "Alignment: Chinese sources and Western sources are aligned, reducing regional risk."
        })
    
    return alerts


# ============================================================================
# DATA SOURCES
# ============================================================================

DATA_SOURCES = [
    DataSource(
        name="Bloomberg Crypto",
        description="Institutional news & analysis",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.now()
    ),
    DataSource(
        name="CoinDesk",
        description="Leading crypto journalism",
        tier=SentimentTier.TIER_1,
        trust_weight=0.85,
        last_updated=datetime.now()
    ),
    DataSource(
        name="Fear & Greed Index",
        description="Market sentiment gauge",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.now()
    ),
    DataSource(
        name="r/CryptoCurrency",
        description="Main crypto community (5M+ members)",
        tier=SentimentTier.TIER_2,
        trust_weight=0.7,
        last_updated=datetime.now()
    ),
    DataSource(
        name="LunarCrush",
        description="Social intelligence platform",
        tier=SentimentTier.TIER_2,
        trust_weight=0.75,
        last_updated=datetime.now()
    ),
    DataSource(
        name="CryptoSlate",
        description="Community-driven news",
        tier=SentimentTier.TIER_2,
        trust_weight=0.65,
        last_updated=datetime.now()
    ),
    DataSource(
        name="r/SatoshiStreetBets",
        description="Retail trading community",
        tier=SentimentTier.TIER_3,
        trust_weight=0.5,
        last_updated=datetime.now()
    ),
    DataSource(
        name="Telegram Channels",
        description="Early retail signals",
        tier=SentimentTier.TIER_3,
        trust_weight=0.45,
        last_updated=datetime.now()
    ),
    DataSource(
        name="4chan /biz/",
        description="Fringe discussion board",
        tier=SentimentTier.FRINGE,
        trust_weight=0.3,
        last_updated=datetime.now()
    )
]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Moonwalking Sentiment API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "uptime": "running",
        "active_sources": len(DATA_SOURCES),
        "last_update": datetime.now().isoformat()
    }


@app.get("/sentiment/latest", response_model=SentimentResponse)
async def get_latest_sentiment():
    """
    Get the latest sentiment data for the popup card
    
    Returns:
        Complete sentiment analysis including:
        - Overall sentiment score
        - Fear & Greed Index
        - Social media breakdown
        - Historical data
        - Trending topics
        - Divergence alerts
    """
    
    overall_sentiment = generate_sentiment_score()
    fear_greed = generate_fear_greed_index()
    
    return SentimentResponse(
        overall_sentiment=overall_sentiment,
        fear_greed_index=fear_greed,
        social_metrics={
            "volume_change": round(random.uniform(-20, 30), 1),
            "engagement_rate": round(random.uniform(0.5, 0.9), 2),
            "mentions_24h": random.randint(10000, 50000)
        },
        social_breakdown=generate_social_breakdown(),
        source_breakdown=generate_source_breakdown(),
        sentiment_history=generate_sentiment_history(7),
        social_history=generate_social_history(7),
        trending_topics=generate_trending_topics(),
        divergence_alerts=generate_divergence_alerts()
    )


@app.get("/sentiment/sources", response_model=List[DataSource])
async def get_data_sources():
    """
    Get list of all data sources with their tier and trust weights
    """
    return DATA_SOURCES


@app.get("/sentiment/sources/{tier}")
async def get_sources_by_tier(tier: SentimentTier):
    """Get data sources filtered by tier"""
    filtered = [s for s in DATA_SOURCES if s.tier == tier]
    return filtered


@app.get("/sentiment/history/{days}")
async def get_sentiment_history(days: int = 30):
    """
    Get historical sentiment data
    
    Args:
        days: Number of days of history (default: 30, max: 365)
    """
    if days > 365:
        raise HTTPException(status_code=400, detail="Maximum 365 days of history")
    
    return {
        "days": days,
        "sentiment_history": generate_sentiment_history(days),
        "social_history": generate_social_history(days)
    }


@app.get("/sentiment/social/{platform}")
async def get_platform_sentiment(platform: SocialPlatform):
    """Get sentiment for specific social platform"""
    breakdown = generate_social_breakdown()
    
    platform_scores = {
        SocialPlatform.REDDIT: breakdown.reddit,
        SocialPlatform.TWITTER: breakdown.twitter,
        SocialPlatform.TELEGRAM: breakdown.telegram,
        SocialPlatform.CHAN: breakdown.chan
    }
    
    return {
        "platform": platform,
        "sentiment_score": platform_scores[platform],
        "volume_change": round(random.uniform(-30, 50), 1),
        "trending_topics": generate_trending_topics()[:3],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/sentiment/divergence")
async def get_divergence_alerts():
    """Get current divergence alerts between source tiers"""
    return {
        "alerts": generate_divergence_alerts(),
        "tier_comparison": {
            "tier1_sentiment": round(random.uniform(0.4, 0.6), 2),
            "tier2_sentiment": round(random.uniform(0.5, 0.7), 2),
            "tier3_sentiment": round(random.uniform(0.6, 0.9), 2),
            "divergence_score": round(random.uniform(0, 0.5), 2)
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/sentiment/stats")
async def get_statistics():
    """Get API statistics and metadata"""
    return {
        "total_sources": len(DATA_SOURCES),
        "sources_by_tier": {
            "tier1": len([s for s in DATA_SOURCES if s.tier == SentimentTier.TIER_1]),
            "tier2": len([s for s in DATA_SOURCES if s.tier == SentimentTier.TIER_2]),
            "tier3": len([s for s in DATA_SOURCES if s.tier == SentimentTier.TIER_3]),
            "fringe": len([s for s in DATA_SOURCES if s.tier == SentimentTier.FRINGE])
        },
        "average_trust_weight": round(sum(s.trust_weight for s in DATA_SOURCES) / len(DATA_SOURCES), 2),
        "last_update": datetime.now().isoformat()
    }


# ============================================================================
# WEBSOCKET SUPPORT (Optional - for real-time updates)
# ============================================================================

from fastapi import WebSocket
from typing import Set

active_connections: Set[WebSocket] = set()


@app.websocket("/ws/sentiment")
async def websocket_sentiment(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sentiment updates
    
    Connect to this endpoint to receive live sentiment updates every 30 seconds
    """
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        while True:
            # Send update every 30 seconds
            await asyncio.sleep(30)
            
            sentiment_data = {
                "type": "sentiment_update",
                "data": {
                    "overall_sentiment": generate_sentiment_score(),
                    "fear_greed_index": generate_fear_greed_index(),
                    "social_breakdown": generate_social_breakdown().dict(),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            await websocket.send_json(sentiment_data)
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)


# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("🌙 Starting Moonwalking Sentiment API...")
    print("📊 Endpoints:")
    print("   - GET  /sentiment/latest")
    print("   - GET  /sentiment/sources")
    print("   - GET  /sentiment/history/{days}")
    print("   - GET  /sentiment/divergence")
    print("   - WS   /ws/sentiment")
    print("\n🚀 Server starting on http://localhost:8001")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
