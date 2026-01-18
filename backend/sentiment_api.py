#!/usr/bin/env python3
"""FastAPI service that powers the Moonwalking sentiment surfaces."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import math
import os
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import requests
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
FNG_URL = "https://api.alternative.me/fng/?limit=1&format=json"
CG_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"

DATA_SOURCES: List["DataSource"] = []
SOURCE_COUNTS = {"tier1": 0, "tier2": 0, "tier3": 0, "fringe": 0}
_SENTIMENT_CACHE: Optional["SentimentResponse"] = None
_SENTIMENT_CACHE_TS: Optional[datetime] = None
# Fear & Greed cache (alt.me)
_FNG_CACHE: Optional[Dict[str, Any]] = None
_FNG_CACHE_TS: Optional[datetime] = None
FNG_CACHE_TTL_SEC = 300  # 5 minutes
FNG_STALE_SEC = 6 * 60 * 60  # 6 hours
# CoinGecko global cache
_CG_CACHE: Optional[Dict[str, Any]] = None
_CG_CACHE_TS: Optional[datetime] = None
CG_CACHE_TTL_SEC = 120  # 2 minutes
CG_STALE_SEC = 10 * 60  # 10 minutes


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
    fear_greed_index: Optional[int] = None
    social_metrics: Dict[str, Any]
    social_breakdown: SocialBreakdown
    source_breakdown: SourceBreakdown
    sentiment_history: List[HistoricalPoint]
    social_history: List[SocialHistoryPoint]
    trending_topics: List[Dict[str, str]]
    divergence_alerts: List[Dict[str, str]]
    fear_greed: Optional[Dict[str, Any]] = None
    market_pulse: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    confidence: Optional[float] = None
    regime: Optional[str] = None
    reasons: Optional[List[str]] = None


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
    base_payload: Dict[str, Any] = {}

    if USE_REAL_SENTIMENT:
        provider = get_provider(SENTIMENT_PROVIDER_NAME)
        if provider:
            try:
                data = await provider.fetch_latest()
                base_payload = dict(data or {})
            except Exception:
                logger.exception("Sentiment provider '%s' failed; falling back to mocks", provider.name)
        else:
            logger.warning("USE_REAL_SENTIMENT=1 but no provider is registered")

    if not base_payload:
        base_payload = {
            "overall_sentiment": generate_sentiment_score(),
            "social_metrics": {
                "volume_change": round(random.uniform(-20, 30), 1),
                "engagement_rate": round(random.uniform(0.5, 0.9), 2),
                "mentions_24h": random.randint(10000, 50000),
            },
            "social_breakdown": generate_social_breakdown(),
            "source_breakdown": _current_source_breakdown(),
            "sentiment_history": generate_sentiment_history(7),
            "social_history": generate_social_history(7),
            "trending_topics": generate_trending_topics(),
            "divergence_alerts": generate_divergence_alerts(),
        }

    # Canonical fear & greed
    fear_greed_payload = await _get_fear_greed_payload()
    if fear_greed_payload is not None:
        base_payload["fear_greed"] = fear_greed_payload
        base_payload["fear_greed_index"] = fear_greed_payload.get("value")
    else:
        base_payload["fear_greed"] = None
        base_payload["fear_greed_index"] = None

    # Canonical market pulse
    market_pulse_payload = await _get_market_pulse_payload()
    base_payload["market_pulse"] = market_pulse_payload

    # Always stamp current response time
    base_payload["timestamp"] = datetime.utcnow().replace(tzinfo=timezone.utc)

    # Confidence, regime, reasons (deterministic, no new sources)
    confidence = _compute_confidence(base_payload)
    # Need stability_gate and breadth_gate reused for reasons/regime
    sb_raw = base_payload.get("source_breakdown") or {}
    if hasattr(sb_raw, "dict"):
        sb = sb_raw.dict()
    else:
        sb = sb_raw if isinstance(sb_raw, dict) else {}
    total_sources = 0
    for k in ("tier1", "tier2", "tier3", "fringe"):
        try:
            total_sources += int((sb.get(k) if isinstance(sb, dict) else getattr(sb, k, 0)) or 0)
        except Exception:
            continue
    if total_sources >= 10:
        breadth_gate = 1.0
    elif total_sources >= 6:
        breadth_gate = 0.85
    elif total_sources >= 3:
        breadth_gate = 0.70
    elif total_sources >= 1:
        breadth_gate = 0.55
    else:
        breadth_gate = 0.40

    sentiments = []
    for p in base_payload.get("sentiment_history") or []:
        try:
            v = p.get("sentiment")
            if v is None:
                continue
            f = float(v)
            if math.isfinite(f):
                sentiments.append(f)
        except Exception:
            continue
    if len(sentiments) < 5:
        stability_gate = 0.75
    else:
        sd = _stddev(sentiments) or 0.0
        if sd <= 0.05:
            stability_gate = 1.0
        elif sd <= 0.10:
            stability_gate = 0.85
        elif sd <= 0.18:
            stability_gate = 0.70
        else:
            stability_gate = 0.55

    base_payload["confidence"] = confidence
    base_payload["regime"] = _compute_regime(base_payload, confidence, stability_gate)
    base_payload["reasons"] = _build_reasons(base_payload, confidence, stability_gate, breadth_gate)

    return SentimentResponse(**base_payload)


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


def _iso_utc(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        if math.isfinite(f):
            return f
    except Exception:
        return None
    return None


def _age_seconds(ts: Optional[datetime]) -> Optional[float]:
    if ts is None:
        return None
    return (datetime.utcnow() - ts).total_seconds()


def _fear_greed_label(value: int) -> str:
    if value <= 24:
        return "Extreme Fear"
    if value <= 44:
        return "Fear"
    if value <= 55:
        return "Neutral"
    if value <= 75:
        return "Greed"
    return "Extreme Greed"


async def _fetch_json(url: str, timeout: float) -> Any:
    def _req():
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(_req)


def _stamp_payload(payload: Dict[str, Any], cache_ts: datetime, ttl: int) -> Dict[str, Any]:
    age = _age_seconds(cache_ts) or 0
    out = dict(payload)
    out["stale"] = age > ttl
    out["stale_age_seconds"] = int(age)
    return out


async def _get_fear_greed_payload() -> Optional[Dict[str, Any]]:
    global _FNG_CACHE, _FNG_CACHE_TS
    now = datetime.utcnow()

    if _FNG_CACHE and _FNG_CACHE_TS:
        age = _age_seconds(_FNG_CACHE_TS) or 0
        if age <= FNG_CACHE_TTL_SEC:
            return _stamp_payload(_FNG_CACHE, _FNG_CACHE_TS, FNG_CACHE_TTL_SEC)

    try:
        raw = await _fetch_json(FNG_URL, timeout=1.0)
        data_list = (raw or {}).get("data") or []
        item = data_list[0] if data_list else {}
        value = item.get("value")
        value_int = int(value) if value is not None else None
        if value_int is None:
            raise ValueError("missing value")
        ts_raw = item.get("timestamp")
        try:
            ts_dt = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
        except Exception:
            ts_dt = now.replace(tzinfo=timezone.utc)
        payload = {
            "value": value_int,
            "label": _fear_greed_label(value_int),
            "source": "alternative_me",
            "source_url": FNG_URL,
            "updated_at": _iso_utc(ts_dt),
        }
        _FNG_CACHE = payload
        _FNG_CACHE_TS = now
        return _stamp_payload(payload, now, FNG_CACHE_TTL_SEC)
    except Exception as exc:
        logger.warning("Fear & Greed fetch failed: %s", exc)

    if _FNG_CACHE and _FNG_CACHE_TS:
        return _stamp_payload(_FNG_CACHE, _FNG_CACHE_TS, FNG_CACHE_TTL_SEC)
    return None


async def _get_market_pulse_payload() -> Optional[Dict[str, Any]]:
    global _CG_CACHE, _CG_CACHE_TS
    now = datetime.utcnow()

    if _CG_CACHE and _CG_CACHE_TS:
        age = _age_seconds(_CG_CACHE_TS) or 0
        if age <= CG_CACHE_TTL_SEC:
            return _stamp_payload(_CG_CACHE, _CG_CACHE_TS, CG_CACHE_TTL_SEC)

    try:
        raw = await _fetch_json(CG_GLOBAL_URL, timeout=1.0)
        data = (raw or {}).get("data") or {}
        payload = {
            "total_market_cap_usd": _safe_float((data.get("total_market_cap") or {}).get("usd")),
            "total_volume_usd": _safe_float((data.get("total_volume") or {}).get("usd")),
            "btc_dominance": _safe_float((data.get("market_cap_percentage") or {}).get("btc")),
            "mcap_change_24h_pct": _safe_float(data.get("market_cap_change_percentage_24h_usd")),
            "source": "coingecko_global",
            "source_url": CG_GLOBAL_URL,
            "updated_at": _iso_utc(now),
        }
        _CG_CACHE = payload
        _CG_CACHE_TS = now
        return _stamp_payload(payload, now, CG_CACHE_TTL_SEC)
    except Exception as exc:
        logger.warning("CoinGecko global fetch failed: %s", exc)

    if _CG_CACHE and _CG_CACHE_TS:
        return _stamp_payload(_CG_CACHE, _CG_CACHE_TS, CG_CACHE_TTL_SEC)
    return None


def _clamp01(val: Optional[float]) -> float:
    try:
        f = float(val)
    except Exception:
        return 0.0
    if not math.isfinite(f):
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _stddev(values: List[float]) -> Optional[float]:
    if not values:
        return None
    try:
        n = len(values)
        if n == 1:
            return 0.0
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        sd = math.sqrt(var)
        return sd if math.isfinite(sd) else None
    except Exception:
        return None


def _compute_confidence(payload: Dict[str, Any]) -> float:
    fg = payload.get("fear_greed")
    mp = payload.get("market_pulse")
    sb_raw = payload.get("source_breakdown") or {}
    if hasattr(sb_raw, "dict"):
        sb = sb_raw.dict()
    else:
        sb = sb_raw if isinstance(sb_raw, dict) else {}
    history = payload.get("sentiment_history") or []
    divergence = payload.get("divergence_alerts") or []

    # Freshness gate
    freshness_gate = 1.0
    if fg is None and mp is None:
        freshness_gate *= 0.60
    else:
        if isinstance(fg, dict) and fg.get("stale"):
            freshness_gate *= 0.75
        if isinstance(mp, dict) and mp.get("stale"):
            freshness_gate *= 0.85

    # Breadth gate
    total_sources = 0
    for k in ("tier1", "tier2", "tier3", "fringe"):
        try:
            v = sb[k] if isinstance(sb, dict) else getattr(sb, k, 0)
            total_sources += int(v or 0)
        except Exception:
            continue
    if total_sources >= 10:
        breadth_gate = 1.0
    elif total_sources >= 6:
        breadth_gate = 0.85
    elif total_sources >= 3:
        breadth_gate = 0.70
    elif total_sources >= 1:
        breadth_gate = 0.55
    else:
        breadth_gate = 0.40

    # Stability gate
    sentiments = []
    for p in history:
        try:
            if isinstance(p, dict):
                v = p.get("sentiment")
            else:
                v = getattr(p, "sentiment", None)
            if v is None:
                continue
            f = float(v)
            if math.isfinite(f):
                sentiments.append(f)
        except Exception:
            continue
    if len(sentiments) < 5:
        stability_gate = 0.75
    else:
        sd = _stddev(sentiments) or 0.0
        if sd <= 0.05:
            stability_gate = 1.0
        elif sd <= 0.10:
            stability_gate = 0.85
        elif sd <= 0.18:
            stability_gate = 0.70
        else:
            stability_gate = 0.55

    # Divergence gate
    div_count = len(divergence) if isinstance(divergence, list) else 0
    if div_count == 0:
        divergence_gate = 1.0
    elif div_count <= 2:
        divergence_gate = 0.80
    else:
        divergence_gate = 0.65

    conf = freshness_gate * breadth_gate * stability_gate * divergence_gate
    return _clamp01(conf)


def _compute_regime(payload: Dict[str, Any], confidence: float, stability_gate: float) -> str:
    overall = payload.get("overall_sentiment")
    fg = payload.get("fear_greed")
    fg_value = None
    try:
        fg_value = int(fg.get("value")) if isinstance(fg, dict) and fg.get("value") is not None else None
    except Exception:
        fg_value = None
    div_count = len(payload.get("divergence_alerts") or []) if isinstance(payload.get("divergence_alerts"), list) else 0

    overall_f = None
    try:
        overall_f = float(overall)
        if not math.isfinite(overall_f):
            overall_f = None
    except Exception:
        overall_f = None

    if (fg_value is None and overall_f is None and payload.get("market_pulse") is None) or confidence <= 0.40:
        return "offline"

    if fg_value is not None and fg_value <= 25:
        return "panic"
    if div_count >= 3 and (overall_f is not None and overall_f <= 0.35):
        return "panic"

    if fg_value is not None and fg_value >= 75 and (overall_f is not None and overall_f >= 0.70) and stability_gate <= 0.70:
        return "mania"

    if stability_gate >= 0.85 and confidence >= 0.70 and (overall_f is not None and overall_f >= 0.55):
        return "trend"

    if stability_gate <= 0.70 and confidence >= 0.55 and div_count >= 1:
        return "chop"

    return "unknown"


def _build_reasons(payload: Dict[str, Any], confidence: float, stability_gate: float, breadth_gate: float) -> List[str]:
    reasons: List[str] = []
    fg = payload.get("fear_greed")
    mp = payload.get("market_pulse")
    divs = payload.get("divergence_alerts") or []
    sb_raw = payload.get("source_breakdown") or {}
    if hasattr(sb_raw, "dict"):
        sb = sb_raw.dict()
    else:
        sb = sb_raw if isinstance(sb_raw, dict) else {}
    total_sources = 0
    for k in ("tier1", "tier2", "tier3", "fringe"):
        try:
            total_sources += int((sb.get(k) if isinstance(sb, dict) else getattr(sb, k, 0)) or 0)
        except Exception:
            continue

    if isinstance(fg, dict):
        stale = fg.get("stale")
        reasons.append(f"Fear & Greed is {fg.get('label', 'Unknown')} ({fg.get('value')}){' (stale)' if stale else ''}.")

    if isinstance(mp, dict):
        stale = mp.get("stale")
        dom = mp.get("btc_dominance")
        if dom is not None:
            try:
                dom_str = f"{float(dom):.1f}%"
            except Exception:
                dom_str = "N/A"
            reasons.append(f"Market pulse is {'stale' if stale else 'live'}; BTC dominance {dom_str}.")
        else:
            reasons.append(f"Market pulse is {'stale' if stale else 'live'}.")

    if total_sources >= 10:
        reasons.append(f"Source breadth is strong ({total_sources} active sources).")
    elif total_sources <= 2:
        reasons.append("Source breadth is thin; confidence reduced.")

    if divs:
        reasons.append(f"Divergence alerts detected ({len(divs)}); confidence reduced.")

    if len(reasons) < 4:
        if stability_gate >= 0.85:
            reasons.append("Sentiment history is stable.")
        elif stability_gate <= 0.70:
            reasons.append("Sentiment history is volatile; stability reduced.")

    if len(reasons) < 2:
        reasons.append("Confidence based on available sentiment signals.")

    return reasons[:4]


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
    parser.add_argument("--port", type=int, default=int(os.getenv("SENTIMENT_PORT", "5004")))
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
