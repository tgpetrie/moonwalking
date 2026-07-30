#!/usr/bin/env python3
"""FastAPI service that powers the Moonwalking sentiment surfaces."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import math
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
import requests
from pydantic import BaseModel, Field

from backend.sentiment.providers import get_provider
from backend.sentiment.source_loader import load_sources, SentimentSourceLoaderError

logger = logging.getLogger("sentiment_api")


@contextlib.asynccontextmanager
async def _lifespan(application: FastAPI):
    task = None
    if SENTIMENT_CACHE_TTL > 0:
        task = asyncio.create_task(_cache_refresher_loop())
        application.state.sentiment_cache_task = task
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Moonwalking Sentiment API", lifespan=_lifespan)

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
BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"
BINANCE_DERIVATIVES_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}
OKX_BASE_URL = "https://www.okx.com"
OKX_DERIVATIVES_SYMBOLS = {"BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP"}
BYBIT_BASE_URL = "https://api.bybit.com"
BYBIT_DERIVATIVES_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}
# Hyperliquid — on-chain perp DEX, keyless public API. Funding settles hourly.
HYPERLIQUID_BASE_URL = "https://api.hyperliquid.xyz"
HYPERLIQUID_DERIVATIVES_ASSETS = {"BTC": "BTC", "ETH": "ETH"}
HYPERLIQUID_FUNDING_INTERVAL_HOURS = 1.0
# Coinalyze — free CEX-aggregated derivatives API (funding/OI/liquidations).
# Requires a free API key; the leg stays inert (unconfigured) when unset.
COINALYZE_BASE_URL = "https://api.coinalyze.net/v1"
COINALYZE_API_KEY = os.getenv("COINALYZE_API_KEY", "").strip()
# Coinalyze market symbols use a per-exchange suffix (".A" = Binance). Averaging
# a couple of representative Binance perps gives a CEX-aggregated funding/OI read.
COINALYZE_DERIVATIVES_SYMBOLS = {"BTC": "BTCUSDT_PERP.A", "ETH": "ETHUSDT_PERP.A"}
# Default funding interval (hours) for the CEX venues that settle every 8h.
DEFAULT_FUNDING_INTERVAL_HOURS = 8.0

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
# Binance USD-M futures public market-positioning cache
_BINANCE_DERIVATIVES_CACHE: Optional[Dict[str, Any]] = None
_BINANCE_DERIVATIVES_CACHE_TS: Optional[datetime] = None
BINANCE_DERIVATIVES_CACHE_TTL_SEC = 120  # 2 minutes
BINANCE_DERIVATIVES_STALE_SEC = 10 * 60  # 10 minutes


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
    overall_sentiment: Optional[float] = None
    fear_greed_index: Optional[int] = None
    social_volume_change: Optional[float] = None
    trend: Optional[str] = None


class SocialBreakdown(BaseModel):
    reddit: Optional[float] = None
    twitter: Optional[float] = None
    telegram: Optional[float] = None
    chan: Optional[float] = None


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
    overall_sentiment: Optional[float] = None
    fear_greed_index: Optional[int] = None
    social_metrics: Dict[str, Any] = Field(default_factory=dict)
    social_breakdown: SocialBreakdown = Field(default_factory=SocialBreakdown)
    source_breakdown: SourceBreakdown = Field(
        default_factory=lambda: SourceBreakdown(tier1=0, tier2=0, tier3=0, fringe=0)
    )
    sentiment_history: List[HistoricalPoint] = Field(default_factory=list)
    social_history: List[SocialHistoryPoint] = Field(default_factory=list)
    trending_topics: List[Dict[str, str]] = Field(default_factory=list)
    divergence_alerts: List[Dict[str, str]] = Field(default_factory=list)
    fear_greed: Optional[Dict[str, Any]] = None
    market_pulse: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    confidence: Optional[float] = None
    regime: Optional[str] = None
    reasons: Optional[List[str]] = None
    scope: str = "market_wide"
    data_status: str = "offline"
    sources: List[Dict[str, Any]] = Field(default_factory=list)


_STATIC_DATA_SOURCES = [
    DataSource(
        name="Bloomberg Crypto",
        description="Institutional news & analysis",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="CoinDesk",
        description="Leading crypto journalism",
        tier=SentimentTier.TIER_1,
        trust_weight=0.85,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="Fear & Greed Index",
        description="Market sentiment gauge",
        tier=SentimentTier.TIER_1,
        trust_weight=0.9,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="r/CryptoCurrency",
        description="Main crypto community (5M+ members)",
        tier=SentimentTier.TIER_2,
        trust_weight=0.7,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="LunarCrush",
        description="Social intelligence platform",
        tier=SentimentTier.TIER_2,
        trust_weight=0.75,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="CryptoSlate",
        description="Community-driven news",
        tier=SentimentTier.TIER_2,
        trust_weight=0.65,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="r/SatoshiStreetBets",
        description="Retail trading community",
        tier=SentimentTier.TIER_3,
        trust_weight=0.5,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="Telegram Channels",
        description="Early retail signals",
        tier=SentimentTier.TIER_3,
        trust_weight=0.45,
        last_updated=datetime.now(timezone.utc),
    ),
    DataSource(
        name="4chan /biz/",
        description="Fringe discussion board",
        tier=SentimentTier.FRINGE,
        trust_weight=0.3,
        last_updated=datetime.now(timezone.utc),
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
                last_dt = datetime.now(timezone.utc)
        else:
            last_dt = datetime.now(timezone.utc)

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

    now = datetime.now(timezone.utc)
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
    """Build a real-only market-wide sentiment snapshot.

    Missing providers stay missing. The service never manufactures social
    scores, histories, topics, or divergence alerts to fill UI space.
    """
    provider_payload: Dict[str, Any] = {}

    if USE_REAL_SENTIMENT:
        provider = get_provider(SENTIMENT_PROVIDER_NAME)
        if provider:
            try:
                data = await provider.fetch_latest()
                provider_payload = dict(data or {})
            except Exception:
                logger.exception(
                    "Sentiment provider '%s' failed; continuing with public sources",
                    provider.name,
                )
        else:
            logger.warning("USE_REAL_SENTIMENT=1 but no provider is registered")

    fear_greed_payload, market_pulse_payload, derivatives_payload = (
        await asyncio.gather(
            _get_fear_greed_payload(),
            _get_market_pulse_payload(),
            _get_derivatives_positioning_payload(),
        )
    )

    sources: List[Dict[str, Any]] = []
    for name, source_payload in (
        ("alternative_me", fear_greed_payload),
        ("coingecko_global", market_pulse_payload),
        ("derivatives_positioning", derivatives_payload),
    ):
        if not source_payload:
            continue
        sources.append(
            {
                "name": name,
                "status": "stale" if source_payload.get("stale") else "live",
                "tier": "tier1",
                "scope": source_payload.get("scope", "market_wide"),
                "updated_at": source_payload.get("updated_at"),
                "source_url": source_payload.get("source_url"),
            }
        )

    provider_sources = provider_payload.get("sources")
    if isinstance(provider_sources, list):
        sources.extend(item for item in provider_sources if isinstance(item, dict))

    if not sources:
        data_status = "offline"
    elif any(source.get("status") == "live" for source in sources):
        data_status = "live"
    else:
        data_status = "stale"

    fear_greed_index = (
        fear_greed_payload.get("value") if fear_greed_payload is not None else None
    )
    overall_sentiment = _safe_float(provider_payload.get("overall_sentiment"))
    if overall_sentiment is None and fear_greed_index is not None:
        overall_sentiment = max(0.0, min(1.0, fear_greed_index / 100.0))

    active_source_count = len(sources)
    live_source_count = sum(source.get("status") == "live" for source in sources)
    confidence = 0.0
    if active_source_count:
        confidence = min(1.0, (active_source_count / 2.0) * 0.8)
        confidence *= 0.7 + (0.3 * live_source_count / active_source_count)
        confidence = round(confidence, 3)

    if data_status == "offline":
        regime = "offline"
    elif fear_greed_index is not None and fear_greed_index <= 25:
        regime = "stressed"
    elif fear_greed_index is not None and fear_greed_index >= 75:
        regime = "heated"
    else:
        regime = "steady" if data_status == "live" else "unknown"

    reasons: List[str] = []
    if fear_greed_payload:
        reasons.append(
            f"Fear & Greed is {fear_greed_payload.get('label', 'Unknown')} "
            f"({fear_greed_index})"
            f"{' and stale' if fear_greed_payload.get('stale') else ''}."
        )
    if market_pulse_payload:
        reasons.append(
            "CoinGecko global market data is "
            f"{'stale' if market_pulse_payload.get('stale') else 'live'}."
        )
    if derivatives_payload:
        reasons.append(
            "Binance futures positioning is "
            f"{'stale' if derivatives_payload.get('stale') else 'live'} "
            f"across {len(derivatives_payload.get('exchanges') or [])} exchange(s)."
        )
    if not reasons:
        reasons.append("No external sentiment source is currently available.")
    if not provider_payload.get("social_metrics"):
        reasons.append(
            "Social sentiment is unavailable; no social provider is configured."
        )

    return SentimentResponse(
        overall_sentiment=overall_sentiment,
        fear_greed_index=fear_greed_index,
        social_breakdown=provider_payload.get("social_breakdown") or {},
        source_breakdown={
            "tier1": active_source_count,
            "tier2": 0,
            "tier3": 0,
            "fringe": 0,
        },
        sentiment_history=provider_payload.get("sentiment_history") or [],
        social_history=provider_payload.get("social_history") or [],
        trending_topics=provider_payload.get("trending_topics") or [],
        divergence_alerts=provider_payload.get("divergence_alerts") or [],
        fear_greed=fear_greed_payload,
        market_pulse=market_pulse_payload,
        social_metrics={
            **(provider_payload.get("social_metrics") or {}),
            **(
                {"derivatives_positioning": derivatives_payload}
                if derivatives_payload
                else {}
            ),
        },
        timestamp=datetime.now(timezone.utc),
        confidence=confidence,
        regime=regime,
        reasons=reasons,
        scope="market_wide",
        data_status=data_status,
        sources=sources,
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


def _iso_utc(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
    normalized_ts = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return (now - normalized_ts).total_seconds()


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


def _stamp_payload(
    payload: Dict[str, Any], cache_ts: datetime, ttl: int
) -> Dict[str, Any]:
    age = _age_seconds(cache_ts) or 0
    out = dict(payload)
    out["stale"] = age > ttl
    out["stale_age_seconds"] = int(age)
    return out


async def _get_fear_greed_payload() -> Optional[Dict[str, Any]]:
    global _FNG_CACHE, _FNG_CACHE_TS
    now = datetime.now(timezone.utc)

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
        age = _age_seconds(_FNG_CACHE_TS) or 0
        if age <= FNG_STALE_SEC:
            return _stamp_payload(_FNG_CACHE, _FNG_CACHE_TS, FNG_CACHE_TTL_SEC)
    return None


async def _get_market_pulse_payload() -> Optional[Dict[str, Any]]:
    global _CG_CACHE, _CG_CACHE_TS
    now = datetime.now(timezone.utc)

    if _CG_CACHE and _CG_CACHE_TS:
        age = _age_seconds(_CG_CACHE_TS) or 0
        if age <= CG_CACHE_TTL_SEC:
            return _stamp_payload(_CG_CACHE, _CG_CACHE_TS, CG_CACHE_TTL_SEC)

    try:
        raw = await _fetch_json(CG_GLOBAL_URL, timeout=1.0)
        data = (raw or {}).get("data") or {}
        payload = {
            "total_market_cap_usd": _safe_float(
                (data.get("total_market_cap") or {}).get("usd")
            ),
            "total_volume_usd": _safe_float(
                (data.get("total_volume") or {}).get("usd")
            ),
            "btc_dominance": _safe_float(
                (data.get("market_cap_percentage") or {}).get("btc")
            ),
            "mcap_change_24h_pct": _safe_float(
                data.get("market_cap_change_percentage_24h_usd")
            ),
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
        age = _age_seconds(_CG_CACHE_TS) or 0
        if age <= CG_STALE_SEC:
            return _stamp_payload(_CG_CACHE, _CG_CACHE_TS, CG_CACHE_TTL_SEC)
    return None


async def _get_binance_json(path: str, params: Dict[str, str]) -> Any:
    def _req():
        resp = requests.get(
            f"{BINANCE_FAPI_BASE_URL}{path}", params=params, timeout=1.2
        )
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(_req)


async def _get_binance_symbol_positioning(
    symbol: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        premium, open_interest = await asyncio.gather(
            _get_binance_json("/fapi/v1/premiumIndex", {"symbol": symbol}),
            _get_binance_json("/fapi/v1/openInterest", {"symbol": symbol}),
        )
        return {
            "exchange": "binance",
            "symbol": symbol,
            "base_asset": symbol.removesuffix("USDT"),
            "mark_price": _safe_float(premium.get("markPrice")),
            "index_price": _safe_float(premium.get("indexPrice")),
            "funding_rate": _safe_float(premium.get("lastFundingRate")),
            "next_funding_time": premium.get("nextFundingTime"),
            "open_interest": _safe_float(open_interest.get("openInterest")),
            "open_interest_time": open_interest.get("time"),
        }, None
    except Exception as exc:
        logger.warning("Binance derivatives fetch failed for %s: %s", symbol, exc)
        return None, _source_error("binance", symbol, exc)


async def _get_okx_json(path: str, params: Dict[str, str]) -> Any:
    def _req():
        resp = requests.get(f"{OKX_BASE_URL}{path}", params=params, timeout=1.2)
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(_req)


async def _get_okx_symbol_positioning(
    base_asset: str, instrument_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        funding, open_interest = await asyncio.gather(
            _get_okx_json("/api/v5/public/funding-rate", {"instId": instrument_id}),
            _get_okx_json("/api/v5/public/open-interest", {"instId": instrument_id}),
        )
        funding_item = ((funding or {}).get("data") or [{}])[0]
        oi_item = ((open_interest or {}).get("data") or [{}])[0]
        return {
            "exchange": "okx",
            "symbol": instrument_id,
            "base_asset": base_asset,
            "mark_price": None,
            "index_price": None,
            "funding_rate": _safe_float(funding_item.get("fundingRate")),
            "next_funding_time": funding_item.get("nextFundingTime"),
            "open_interest": _safe_float(oi_item.get("oi")),
            "open_interest_currency": _safe_float(oi_item.get("oiCcy")),
            "open_interest_time": oi_item.get("ts"),
        }, None
    except Exception as exc:
        logger.warning("OKX derivatives fetch failed for %s: %s", instrument_id, exc)
        return None, _source_error("okx", instrument_id, exc)


async def _get_bybit_json(path: str, params: Dict[str, str]) -> Any:
    def _req():
        resp = requests.get(f"{BYBIT_BASE_URL}{path}", params=params, timeout=1.2)
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(_req)


async def _get_bybit_symbol_positioning(
    base_asset: str, symbol: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        ticker, open_interest = await asyncio.gather(
            _get_bybit_json(
                "/v5/market/tickers", {"category": "linear", "symbol": symbol}
            ),
            _get_bybit_json(
                "/v5/market/open-interest",
                {
                    "category": "linear",
                    "symbol": symbol,
                    "intervalTime": "5min",
                    "limit": "1",
                },
            ),
        )
        ticker_item = (((ticker or {}).get("result") or {}).get("list") or [{}])[0]
        oi_item = (((open_interest or {}).get("result") or {}).get("list") or [{}])[0]
        return {
            "exchange": "bybit",
            "symbol": symbol,
            "base_asset": base_asset,
            "mark_price": _safe_float(ticker_item.get("markPrice")),
            "index_price": _safe_float(ticker_item.get("indexPrice")),
            "funding_rate": _safe_float(ticker_item.get("fundingRate")),
            "next_funding_time": ticker_item.get("nextFundingTime"),
            "open_interest": _safe_float(oi_item.get("openInterest")),
            "open_interest_time": oi_item.get("timestamp"),
        }, None
    except Exception as exc:
        logger.warning("Bybit derivatives fetch failed for %s: %s", symbol, exc)
        return None, _source_error("bybit", symbol, exc)


async def _get_hyperliquid_positioning() -> (
    List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]
):
    """Fetch on-chain perp positioning from Hyperliquid (keyless public API).

    A single POST returns every asset's context in parallel arrays
    (`universe[i]` <-> `assetCtxs[i]`), so one request covers BTC and ETH.
    Funding on Hyperliquid settles hourly — tagged so the summary can normalize
    it against the 8h CEX venues.
    """

    def _req():
        resp = requests.post(
            f"{HYPERLIQUID_BASE_URL}/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=1.5,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        data = await asyncio.to_thread(_req)
        meta, asset_ctxs = data[0], data[1]
        universe = meta.get("universe") or []
        index_by_name = {asset.get("name"): i for i, asset in enumerate(universe)}
        results: List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = []
        for base_asset, hl_name in HYPERLIQUID_DERIVATIVES_ASSETS.items():
            idx = index_by_name.get(hl_name)
            if idx is None or idx >= len(asset_ctxs):
                results.append(
                    (None, _source_error("hyperliquid", hl_name, KeyError(hl_name)))
                )
                continue
            ctx = asset_ctxs[idx] or {}
            mark_price = _safe_float(ctx.get("markPx"))
            open_interest = _safe_float(ctx.get("openInterest"))
            results.append(
                (
                    {
                        "exchange": "hyperliquid",
                        "symbol": hl_name,
                        "base_asset": base_asset,
                        "mark_price": mark_price,
                        "index_price": _safe_float(ctx.get("oraclePx")),
                        "funding_rate": _safe_float(ctx.get("funding")),
                        "funding_interval_hours": HYPERLIQUID_FUNDING_INTERVAL_HOURS,
                        "open_interest": open_interest,
                        "open_interest_usd": (
                            open_interest * mark_price
                            if open_interest is not None and mark_price is not None
                            else None
                        ),
                    },
                    None,
                )
            )
        return results
    except Exception as exc:
        logger.warning("Hyperliquid derivatives fetch failed: %s", exc)
        return [(None, _source_error("hyperliquid", "metaAndAssetCtxs", exc))]


async def _get_coinalyze_json(path: str, params: Dict[str, str]) -> Any:
    def _req():
        resp = requests.get(
            f"{COINALYZE_BASE_URL}{path}",
            params={**params, "api_key": COINALYZE_API_KEY},
            timeout=1.5,
        )
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(_req)


async def _get_coinalyze_positioning() -> (
    List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]
):
    """Fetch CEX-aggregated funding/OI from Coinalyze.

    Requires a free API key (`COINALYZE_API_KEY`). Without it the leg stays inert
    and Coinalyze is simply not counted among configured exchanges — it never
    surfaces as a blocked/failed source.
    """
    if not COINALYZE_API_KEY:
        return []
    symbols = ",".join(COINALYZE_DERIVATIVES_SYMBOLS.values())
    try:
        funding, open_interest = await asyncio.gather(
            _get_coinalyze_json("/funding-rate", {"symbols": symbols}),
            _get_coinalyze_json("/open-interest", {"symbols": symbols}),
        )
        funding_by_symbol = {
            row.get("symbol"): _safe_float(row.get("value")) for row in (funding or [])
        }
        oi_by_symbol = {
            row.get("symbol"): _safe_float(row.get("value"))
            for row in (open_interest or [])
        }
        return [
            (
                {
                    "exchange": "coinalyze",
                    "symbol": market_symbol,
                    "base_asset": base_asset,
                    "mark_price": None,
                    "index_price": None,
                    "funding_rate": funding_by_symbol.get(market_symbol),
                    "funding_interval_hours": DEFAULT_FUNDING_INTERVAL_HOURS,
                    "open_interest": oi_by_symbol.get(market_symbol),
                },
                None,
            )
            for base_asset, market_symbol in COINALYZE_DERIVATIVES_SYMBOLS.items()
        ]
    except Exception as exc:
        logger.warning("Coinalyze derivatives fetch failed: %s", exc)
        return [(None, _source_error("coinalyze", symbols, exc))]


def _source_error(exchange: str, symbol: str, exc: Exception) -> Dict[str, Any]:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code in (401, 403, 451):
        status = "blocked"
    else:
        status = "failed"
    return {
        "exchange": exchange,
        "symbol": symbol,
        "status": status,
        "status_code": status_code,
        "message": str(exc),
    }


def _summarize_derivatives_positioning(
    symbols: List[Dict[str, Any]], configured_exchange_count: int
) -> Dict[str, Any]:
    # Funding settles on different cadences per venue (CEX = 8h, Hyperliquid =
    # 1h). Normalize each rate to an 8h-equivalent before averaging so mixing
    # venues doesn't skew the bias. Symbols without an interval default to 8h,
    # so existing CEX-only callers are unaffected.
    funding_rates = []
    for item in symbols:
        rate = item.get("funding_rate")
        if rate is None or not math.isfinite(float(rate)):
            continue
        interval = float(
            item.get("funding_interval_hours") or DEFAULT_FUNDING_INTERVAL_HOURS
        )
        if interval <= 0:
            interval = DEFAULT_FUNDING_INTERVAL_HOURS
        funding_rates.append(float(rate) * (DEFAULT_FUNDING_INTERVAL_HOURS / interval))
    avg_funding = sum(funding_rates) / len(funding_rates) if funding_rates else None
    if avg_funding is None:
        funding_bias = "unknown"
    elif avg_funding > 0.00005:
        funding_bias = "longs_pay"
    elif avg_funding < -0.00005:
        funding_bias = "shorts_pay"
    else:
        funding_bias = "neutral"

    live_exchange_count = len({item["exchange"] for item in symbols})
    coverage_ratio = (
        live_exchange_count / configured_exchange_count
        if configured_exchange_count
        else 0.0
    )
    return {
        "average_funding_rate": avg_funding,
        "funding_bias": funding_bias,
        "live_exchange_count": live_exchange_count,
        "configured_exchange_count": configured_exchange_count,
        "coverage_ratio": round(coverage_ratio, 3),
        "confidence_penalty": round(1.0 - coverage_ratio, 3),
    }


async def _get_derivatives_positioning_payload() -> Optional[Dict[str, Any]]:
    global _BINANCE_DERIVATIVES_CACHE, _BINANCE_DERIVATIVES_CACHE_TS
    now = datetime.now(timezone.utc)

    if _BINANCE_DERIVATIVES_CACHE and _BINANCE_DERIVATIVES_CACHE_TS:
        age = _age_seconds(_BINANCE_DERIVATIVES_CACHE_TS) or 0
        if age <= BINANCE_DERIVATIVES_CACHE_TTL_SEC:
            return _stamp_payload(
                _BINANCE_DERIVATIVES_CACHE,
                _BINANCE_DERIVATIVES_CACHE_TS,
                BINANCE_DERIVATIVES_CACHE_TTL_SEC,
            )

    binance_symbols = await asyncio.gather(
        *(
            _get_binance_symbol_positioning(symbol)
            for symbol in BINANCE_DERIVATIVES_SYMBOLS.values()
        )
    )
    okx_symbols = await asyncio.gather(
        *(
            _get_okx_symbol_positioning(base_asset, instrument_id)
            for base_asset, instrument_id in OKX_DERIVATIVES_SYMBOLS.items()
        )
    )
    bybit_symbols = await asyncio.gather(
        *(
            _get_bybit_symbol_positioning(base_asset, symbol)
            for base_asset, symbol in BYBIT_DERIVATIVES_SYMBOLS.items()
        )
    )
    # Hyperliquid (on-chain, keyless) and Coinalyze (CEX-aggregated, key-gated)
    # each return a ready list of (item, error) tuples.
    hyperliquid_symbols = await _get_hyperliquid_positioning()
    coinalyze_symbols = await _get_coinalyze_positioning()
    results = [
        *binance_symbols,
        *okx_symbols,
        *bybit_symbols,
        *hyperliquid_symbols,
        *coinalyze_symbols,
    ]
    source_errors = [error for _, error in results if error]
    valid_symbols = [item for item, _ in results if item]
    if valid_symbols:
        # Coinalyze is only "configured" when a key is present, so coverage math
        # stays honest (e.g. 4/4 without a key, 5/5 with one).
        configured_exchanges = ["binance", "bybit", "hyperliquid", "okx"]
        if COINALYZE_API_KEY:
            configured_exchanges.append("coinalyze")
        configured_exchanges = sorted(configured_exchanges)
        live_exchanges = sorted({item["exchange"] for item in valid_symbols})
        blocked_exchanges = sorted(
            {
                error["exchange"]
                for error in source_errors
                if error["status"] == "blocked"
            }
        )
        failed_exchanges = sorted(
            {
                error["exchange"]
                for error in source_errors
                if error["status"] == "failed"
            }
        )
        payload = {
            "source": "derivatives_positioning",
            "source_url": f"{BINANCE_FAPI_BASE_URL}/fapi/v1/premiumIndex",
            "documentation": [
                "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api",
                "https://www.okx.com/docs-v5/en/",
                "https://bybit-exchange.github.io/docs/v5/market/tickers",
                "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint",
                "https://api.coinalyze.net/v1/doc/",
            ],
            "scope": "market_positioning",
            "updated_at": _iso_utc(now),
            "configured_exchanges": configured_exchanges,
            "exchanges": live_exchanges,
            "live_exchanges": live_exchanges,
            "blocked_exchanges": blocked_exchanges,
            "failed_exchanges": failed_exchanges,
            "errors": source_errors,
            "summary": _summarize_derivatives_positioning(
                valid_symbols, len(configured_exchanges)
            ),
            "symbols": valid_symbols,
        }
        _BINANCE_DERIVATIVES_CACHE = payload
        _BINANCE_DERIVATIVES_CACHE_TS = now
        return _stamp_payload(payload, now, BINANCE_DERIVATIVES_CACHE_TTL_SEC)

    if _BINANCE_DERIVATIVES_CACHE and _BINANCE_DERIVATIVES_CACHE_TS:
        age = _age_seconds(_BINANCE_DERIVATIVES_CACHE_TS) or 0
        if age <= BINANCE_DERIVATIVES_STALE_SEC:
            return _stamp_payload(
                _BINANCE_DERIVATIVES_CACHE,
                _BINANCE_DERIVATIVES_CACHE_TS,
                BINANCE_DERIVATIVES_CACHE_TTL_SEC,
            )
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


def _compute_regime(
    payload: Dict[str, Any], confidence: float, stability_gate: float
) -> str:
    allowed = {"steady", "mixed", "heated", "stressed", "offline", "unknown"}
    overall = payload.get("overall_sentiment")
    fg = payload.get("fear_greed")
    fg_value = None
    try:
        fg_value = (
            int(fg.get("value"))
            if isinstance(fg, dict) and fg.get("value") is not None
            else None
        )
    except Exception:
        fg_value = None
    divs = payload.get("divergence_alerts")
    div_count = len(divs) if isinstance(divs, list) else 0

    overall_f = None
    try:
        overall_f = float(overall)
        if not math.isfinite(overall_f):
            overall_f = None
    except Exception:
        overall_f = None

    volatility_high = False
    if stability_gate is not None:
        volatility_high = stability_gate <= 0.70
    else:
        sentiments = []
        for p in payload.get("sentiment_history") or []:
            try:
                v = (
                    p.get("sentiment")
                    if isinstance(p, dict)
                    else getattr(p, "sentiment", None)
                )
                if v is None:
                    continue
                f = float(v)
                if math.isfinite(f):
                    sentiments.append(f)
            except Exception:
                continue
        if len(sentiments) >= 5:
            sd = _stddev(sentiments) or 0.0
            volatility_high = sd > 0.10

    # a) offline
    if (
        not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or confidence <= 0.40
        or (
            overall_f is None
            and fg_value is None
            and payload.get("market_pulse") is None
        )
    ):
        regime = "offline"
    # b) stressed
    elif (
        (fg_value is not None and fg_value <= 25)
        or div_count >= 3
        or (div_count >= 1 and confidence < 0.60 and volatility_high)
    ):
        regime = "stressed"
    # c) heated
    elif (fg_value is not None and fg_value >= 75) or (
        confidence >= 0.55 and volatility_high and div_count <= 1
    ):
        regime = "heated"
    # d) steady
    elif confidence >= 0.75 and not volatility_high and div_count == 0:
        regime = "steady"
    # e) mixed
    elif confidence >= 0.50 and (div_count >= 1 or volatility_high):
        regime = "mixed"
    else:
        regime = "unknown"

    return regime if regime in allowed else "unknown"


def _build_reasons(
    payload: Dict[str, Any],
    confidence: float,
    stability_gate: float,
    breadth_gate: float,
) -> List[str]:
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
            total_sources += int(
                (sb.get(k) if isinstance(sb, dict) else getattr(sb, k, 0)) or 0
            )
        except Exception:
            continue

    if isinstance(fg, dict):
        stale = fg.get("stale")
        reasons.append(
            f"Fear & Greed is {fg.get('label', 'Unknown')} ({fg.get('value')}){' (stale)' if stale else ''}."
        )

    if isinstance(mp, dict):
        stale = mp.get("stale")
        dom = mp.get("btc_dominance")
        if dom is not None:
            try:
                dom_str = f"{float(dom):.1f}%"
            except Exception:
                dom_str = "N/A"
            reasons.append(
                f"Market pulse is {'stale' if stale else 'live'}; BTC dominance {dom_str}."
            )
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


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "status": "online",
        "service": "Moonwalking Sentiment API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    active_sources = len(_SENTIMENT_CACHE.sources) if _SENTIMENT_CACHE else 0
    data_status = _SENTIMENT_CACHE.data_status if _SENTIMENT_CACHE else "warming"
    configured_sources = 2
    if USE_REAL_SENTIMENT and get_provider(SENTIMENT_PROVIDER_NAME):
        configured_sources += 1
    return {
        "status": "healthy",
        "uptime": "running",
        "active_sources": active_sources,
        "configured_sources": configured_sources,
        "data_status": data_status,
        "last_update": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/sentiment-basic", response_model=SentimentResponse)
@app.get("/sentiment/latest", response_model=SentimentResponse)
async def get_latest_sentiment() -> SentimentResponse:
    return await _hydrate_sentiment_cache()


@app.get("/sentiment/sources")
async def get_data_sources() -> List[Dict[str, Any]]:
    """Return only providers that contributed to the current real snapshot."""
    payload = await _hydrate_sentiment_cache()
    return payload.sources


@app.get("/sentiment/sources/{tier}")
async def get_sources_by_tier(tier: SentimentTier) -> List[Dict[str, Any]]:
    sources = await get_data_sources()
    return [source for source in sources if source.get("tier") == tier.value]


@app.get("/sentiment/history/{days}")
async def get_sentiment_history(days: int = 30) -> Dict[str, Any]:
    if days > 365:
        raise HTTPException(status_code=400, detail="Maximum 365 days of history")
    return {
        "days": days,
        "available": False,
        "reason": "No historical sentiment provider is configured.",
        "sentiment_history": [],
        "social_history": [],
    }


@app.get("/sentiment/social/{platform}")
async def get_platform_sentiment(platform: SocialPlatform) -> Dict[str, Any]:
    return {
        "platform": platform,
        "available": False,
        "reason": "No social sentiment provider is configured.",
        "sentiment_score": None,
        "volume_change": None,
        "trending_topics": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/sentiment/divergence")
async def get_divergence_endpoint() -> Dict[str, Any]:
    return {
        "available": False,
        "reason": "Divergence requires multiple real sentiment providers.",
        "alerts": [],
        "tier_comparison": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/sentiment/stats")
async def get_statistics() -> Dict[str, Any]:
    sources = await get_data_sources()
    total_sources = len(sources)
    sources_by_tier = {"tier1": 0, "tier2": 0, "tier3": 0, "fringe": 0}
    for source in sources:
        tier = source.get("tier")
        if tier in sources_by_tier:
            sources_by_tier[tier] += 1
    return {
        "total_sources": total_sources,
        "sources_by_tier": sources_by_tier,
        "average_trust_weight": None,
        "last_update": datetime.now(timezone.utc).isoformat(),
    }


active_connections: Set[WebSocket] = set()


@app.websocket("/ws/sentiment")
async def websocket_sentiment(websocket: WebSocket) -> None:
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            payload = await _hydrate_sentiment_cache()
            await websocket.send_json(
                {
                    "type": "sentiment_update",
                    "data": jsonable_encoder(payload),
                }
            )
    finally:
        active_connections.discard(websocket)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Moonwalking Sentiment API service"
    )
    parser.add_argument("--host", default=os.getenv("SENTIMENT_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SENTIMENT_PORT", "8003"))
    )
    parser.add_argument("--log-level", default=os.getenv("SENTIMENT_LOG_LEVEL", "info"))
    parser.add_argument(
        "--reload", action="store_true", help="Enable uvicorn autoreload (dev only)"
    )
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
