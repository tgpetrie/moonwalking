#!/usr/bin/env python3
"""FastAPI service that powers the Moonwalking sentiment surfaces."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import random
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.sentiment.providers import get_provider
from backend.sentiment.source_loader import load_sources, SentimentSourceLoaderError

logger = logging.getLogger("sentiment_api")
app = FastAPI(title="Moonwalking Sentiment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SENTIMENT_CACHE_TTL = int(os.getenv("SENTIMENT_CACHE_TTL", "30"))
DEV_RELOAD_SOURCES = os.getenv("DEV_RELOAD_SOURCES") == "1"
USE_REAL_SENTIMENT = os.getenv("USE_REAL_SENTIMENT") == "1"
SENTIMENT_PROVIDER_NAME = os.getenv("SENTIMENT_PROVIDER", "").strip() or None

DATA_SOURCES: List["DataSource"] = []
SOURCE_COUNTS = {"tier1": 0, "tier2": 0, "tier3": 0, "fringe": 0}
_SENTIMENT_CACHE: Optional["SentimentResponse"] = None
_SENTIMENT_CACHE_TS: Optional[datetime] = None


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
    overall_sentiment: float
    fear_greed_index: int
    social_volume_change: float
    trend: str


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
    social_metrics: Dict[str, Any]
    social_breakdown: SocialBreakdown
    source_breakdown: SourceBreakdown
    sentiment_history: List[HistoricalPoint]
    social_history: List[SocialHistoryPoint]
    trending_topics: List[Dict[str, str]]
    divergence_alerts: List[Dict[str, str]]


_STATIC_DATA_SOURCES = [
    DataSource(
        name="Bloomberg Crypto",
        description="Institutional news & analysis",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="CoinDesk",
        description="Leading crypto journalism",
        tier=SentimentTier.TIER_1,
        trust_weight=0.85,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="Fear & Greed Index",
        description="Market sentiment gauge",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="r/CryptoCurrency",
        description="Main crypto community (5M+ members)",
        tier=SentimentTier.TIER_2,
        trust_weight=0.7,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="LunarCrush",
        description="Social intelligence platform",
        tier=SentimentTier.TIER_2,
        trust_weight=0.75,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="CryptoSlate",
        description="Community-driven news",
        tier=SentimentTier.TIER_2,
        trust_weight=0.65,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="r/SatoshiStreetBets",
        description="Retail trading community",
        tier=SentimentTier.TIER_3,
        trust_weight=0.5,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="Telegram Channels",
        description="Early retail signals",
        tier=SentimentTier.TIER_3,
        trust_weight=0.45,
        last_updated=datetime.utcnow(),
    ),
    DataSource(
        name="4chan /biz/",
        description="Fringe discussion board",
        tier=SentimentTier.FRINGE,
        trust_weight=0.3,
        last_updated=datetime.utcnow(),
    ),
]


def _hydrate_data_sources(entries: List[Dict[str, Any]]) -> List[DataSource]:
    hydrated: List[DataSource] = []
    for entry in entries:
        name = (entry.get("name") or "").strip()
        if not name:
            continue

        tier_value = entry.get("tier", "tier2")
        try:
            tier = SentimentTier(tier_value)
        except ValueError:
            tier = SentimentTier.TIER_2

        last_updated = entry.get("last_updated")
        if isinstance(last_updated, str):
            try:
                last_dt = datetime.fromisoformat(last_updated)
            except ValueError:
                last_dt = datetime.utcnow()
        else:
            last_dt = datetime.utcnow()

        hydrated.append(
            DataSource(
                name=name,
                description=entry.get("description", ""),
                tier=tier,
                trust_weight=float(entry.get("weight", entry.get("trust_weight", 0.7))),
                last_updated=last_dt,
            )
        )

    return hydrated or list(_STATIC_DATA_SOURCES)


def _refresh_data_sources(force: bool = False) -> List[DataSource]:
    global DATA_SOURCES, SOURCE_COUNTS

    if DATA_SOURCES and not force and not DEV_RELOAD_SOURCES:
        return DATA_SOURCES

    try:
        catalog = load_sources(force_reload=force or DEV_RELOAD_SOURCES)
        hydrated = _hydrate_data_sources(catalog.serialized())
        DATA_SOURCES = hydrated or list(_STATIC_DATA_SOURCES)
    except SentimentSourceLoaderError as exc:
        logger.warning("Falling back to baked-in sentiment sources: %s", exc)
        if not DATA_SOURCES:
            DATA_SOURCES = list(_STATIC_DATA_SOURCES)

    counts = {"tier1": 0, "tier2": 0, "tier3": 0, "fringe": 0}
    for src in DATA_SOURCES:
        counts[src.tier.value] = counts.get(src.tier.value, 0) + 1
    SOURCE_COUNTS = counts
    return DATA_SOURCES


async def _hydrate_sentiment_cache(force: bool = False) -> SentimentResponse:
    global _SENTIMENT_CACHE, _SENTIMENT_CACHE_TS

    if SENTIMENT_CACHE_TTL <= 0 and not force:
        return await _build_sentiment_payload()

    now = datetime.utcnow()
    if (
        not force
        and _SENTIMENT_CACHE
        and _SENTIMENT_CACHE_TS
        and (now - _SENTIMENT_CACHE_TS).total_seconds() < SENTIMENT_CACHE_TTL
    ):
        return _SENTIMENT_CACHE

    payload = await _build_sentiment_payload()
    _SENTIMENT_CACHE = payload
    _SENTIMENT_CACHE_TS = now
    return payload


async def _build_sentiment_payload() -> SentimentResponse:
    if USE_REAL_SENTIMENT:
        provider = get_provider(SENTIMENT_PROVIDER_NAME)
        if provider:
            try:
                data = await provider.fetch_latest()
                return SentimentResponse(**data)
            except Exception:
                logger.exception("Sentiment provider '%s' failed; falling back to mocks", provider.name)
        else:
            logger.warning("USE_REAL_SENTIMENT=1 but no provider is registered")

    overall_sentiment = generate_sentiment_score()
    fear_greed = generate_fear_greed_index()

    return SentimentResponse(
        overall_sentiment=overall_sentiment,
        fear_greed_index=fear_greed,
        social_metrics={
            "volume_change": round(random.uniform(-20, 30), 1),
            "engagement_rate": round(random.uniform(0.5, 0.9), 2),
            "mentions_24h": random.randint(10000, 50000),
        },
        social_breakdown=generate_social_breakdown(),
        source_breakdown=_current_source_breakdown(),
        sentiment_history=generate_sentiment_history(7),
        social_history=generate_social_history(7),
        trending_topics=generate_trending_topics(),
        divergence_alerts=generate_divergence_alerts(),
    )


async def _cache_refresher_loop() -> None:
    interval = max(SENTIMENT_CACHE_TTL, 15)
    while True:
        try:
            await _hydrate_sentiment_cache(force=True)
        except Exception:
            logger.exception("Failed to refresh cached sentiment payload")
        await asyncio.sleep(interval)


def _current_source_breakdown() -> SourceBreakdown:
    if not any(SOURCE_COUNTS.values()):
        _refresh_data_sources()
    return SourceBreakdown(**SOURCE_COUNTS)


def generate_sentiment_score() -> float:
    return round(0.5 + random.uniform(-0.3, 0.3), 2)


def generate_fear_greed_index() -> int:
    return random.randint(45, 85)


def generate_social_breakdown() -> SocialBreakdown:
    return SocialBreakdown(
        reddit=round(random.uniform(0.6, 0.9), 2),
        twitter=round(random.uniform(0.5, 0.8), 2),
        telegram=round(random.uniform(0.7, 0.95), 2),
        chan=round(random.uniform(0.3, 0.6), 2),
    )


def generate_source_breakdown() -> SourceBreakdown:
    return _current_source_breakdown()


def generate_sentiment_history(days: int = 7) -> List[HistoricalPoint]:
    history: List[HistoricalPoint] = []
    base_time = datetime.utcnow() - timedelta(days=days)
    for i in range(days):
        timestamp = base_time + timedelta(days=i)
        sentiment = round(0.5 + (i * 0.05) + random.uniform(-0.1, 0.1), 2)
        price = round(60 + (i * 2) + random.uniform(-3, 3), 2)
        history.append(
            HistoricalPoint(
                timestamp=timestamp,
                sentiment=sentiment,
                price_normalized=price,
            )
        )
    return history


def generate_social_history(days: int = 7) -> List[SocialHistoryPoint]:
    history: List[SocialHistoryPoint] = []
    base_time = datetime.utcnow() - timedelta(days=days)
    for i in range(days):
        timestamp = base_time + timedelta(days=i)
        history.append(
            SocialHistoryPoint(
                timestamp=timestamp,
                reddit=round(0.65 + (i * 0.03) + random.uniform(-0.05, 0.05), 2),
                twitter=round(0.58 + (i * 0.02) + random.uniform(-0.05, 0.05), 2),
                telegram=round(0.70 + (i * 0.04) + random.uniform(-0.05, 0.05), 2),
                chan=round(0.45 + random.uniform(-0.1, 0.1), 2),
            )
        )
    return history


def generate_trending_topics() -> List[Dict[str, str]]:
    return [
        {"tag": "#Bitcoin", "sentiment": "bullish", "volume": "+124%"},
        {"tag": "#HODL", "sentiment": "bullish", "volume": "+89%"},
        {"tag": "#Lightning", "sentiment": "bullish", "volume": "+45%"},
        {"tag": "#ToTheMoon", "sentiment": "neutral", "volume": "+12%"},
        {"tag": "#Correction", "sentiment": "bearish", "volume": "+67%"},
    ]


def generate_divergence_alerts() -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    if random.random() > 0.5:
        alerts.append(
            {
                "type": "warning",
                "message": "Divergence Detected: Fringe sources showing extreme bullishness (+45%) while Tier 1 sources remain neutral.",
            }
        )
    if random.random() > 0.7:
        alerts.append(
            {
                "type": "success",
                "message": "Alignment: Chinese sources and Western sources are aligned, reducing regional risk.",
            }
        )
    return alerts


@app.on_event("startup")
async def _startup_event() -> None:
    _refresh_data_sources(force=True)
    if SENTIMENT_CACHE_TTL > 0:
        app.state.sentiment_cache_task = asyncio.create_task(_cache_refresher_loop())


@app.on_event("shutdown")
async def _shutdown_event() -> None:
    task = getattr(app.state, "sentiment_cache_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "status": "online",
        "service": "Moonwalking Sentiment API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "uptime": "running",
        "active_sources": len(_refresh_data_sources()),
        "last_update": datetime.utcnow().isoformat(),
    }


@app.get("/api/sentiment-basic", response_model=SentimentResponse)
@app.get("/sentiment/latest", response_model=SentimentResponse)
async def get_latest_sentiment() -> SentimentResponse:
    return await _hydrate_sentiment_cache()


@app.get("/sentiment/sources", response_model=List[DataSource])
async def get_data_sources() -> List[DataSource]:
    return _refresh_data_sources()


@app.get("/sentiment/sources/{tier}")
async def get_sources_by_tier(tier: SentimentTier) -> List[DataSource]:
    sources = _refresh_data_sources()
    return [s for s in sources if s.tier == tier]


@app.get("/sentiment/history/{days}")
async def get_sentiment_history(days: int = 30) -> Dict[str, Any]:
    if days > 365:
        raise HTTPException(status_code=400, detail="Maximum 365 days of history")
    return {
        "days": days,
        "sentiment_history": generate_sentiment_history(days),
        "social_history": generate_social_history(days),
    }


@app.get("/sentiment/social/{platform}")
async def get_platform_sentiment(platform: SocialPlatform) -> Dict[str, Any]:
    breakdown = generate_social_breakdown()
    platform_scores = {
        SocialPlatform.REDDIT: breakdown.reddit,
        SocialPlatform.TWITTER: breakdown.twitter,
        SocialPlatform.TELEGRAM: breakdown.telegram,
        SocialPlatform.CHAN: breakdown.chan,
    }
    return {
        "platform": platform,
        "sentiment_score": platform_scores[platform],
        "volume_change": round(random.uniform(-30, 50), 1),
        "trending_topics": generate_trending_topics()[:3],
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/sentiment/divergence")
async def get_divergence_endpoint() -> Dict[str, Any]:
    return {
        "alerts": generate_divergence_alerts(),
        "tier_comparison": {
            "tier1_sentiment": round(random.uniform(0.4, 0.6), 2),
            "tier2_sentiment": round(random.uniform(0.5, 0.7), 2),
            "tier3_sentiment": round(random.uniform(0.6, 0.9), 2),
            "divergence_score": round(random.uniform(0, 0.5), 2),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/sentiment/stats")
async def get_statistics() -> Dict[str, Any]:
    sources = _refresh_data_sources()
    total_sources = len(sources)
    avg_weight = 0.0
    if total_sources:
        avg_weight = sum(s.trust_weight for s in sources) / total_sources
    return {
        "total_sources": total_sources,
        "sources_by_tier": SOURCE_COUNTS,
        "average_trust_weight": round(avg_weight, 2),
        "last_update": datetime.utcnow().isoformat(),
    }


active_connections: Set[WebSocket] = set()


@app.websocket("/ws/sentiment")
async def websocket_sentiment(websocket: WebSocket) -> None:
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json(
                {
                    "type": "sentiment_update",
                    "data": {
                        "overall_sentiment": generate_sentiment_score(),
                        "fear_greed_index": generate_fear_greed_index(),
                        "social_breakdown": generate_social_breakdown().dict(),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )
    finally:
        active_connections.discard(websocket)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Moonwalking Sentiment API service")
    parser.add_argument("--host", default=os.getenv("SENTIMENT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SENTIMENT_PORT", "8001")))
    parser.add_argument("--log-level", default=os.getenv("SENTIMENT_LOG_LEVEL", "info"))
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn autoreload (dev only)")
    args = parser.parse_args()

    import uvicorn  # Imported lazily so cli tools don't require it

    uvicorn.run(
        "backend.sentiment_api:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
