"""
Authoritative API contracts for sentiment + alerts payloads.

These Pydantic models define the JSON schemas used by the backend endpoints
so responses can be validated/shaped consistently.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class MetaHealth(BaseModel):
    """Health metadata for sentiment/pipeline payloads."""

    model_config = ConfigDict(extra="allow")

    ok: bool | None = None
    pipelineRunning: bool | None = None
    staleSeconds: int | None = None
    lastOkTs: str | None = None
    error: str | None = None
    source: str | None = None
    stale: bool | None = None


class MarketHeatComponents(BaseModel):
    model_config = ConfigDict(extra="allow")

    green_1m: int | float | None = None
    red_1m: int | float | None = None
    green_3m: int | float | None = None
    red_3m: int | float | None = None
    total_symbols: int | float | None = None
    avg_return_1m: int | float | None = None
    avg_return_3m: int | float | None = None
    volatility: int | float | None = None
    momentum_alignment: int | float | None = None
    breadth_1m: int | float | None = None
    breadth_3m: int | float | None = None


class MarketHeat(BaseModel):
    model_config = ConfigDict(extra="allow")

    score: int | float | None = None
    regime: str | None = None
    label: str | None = None
    confidence: int | float | None = None
    components: MarketHeatComponents = Field(default_factory=MarketHeatComponents)
    reasons: List[str] = Field(default_factory=list)


class FearGreed(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: int | float | None = None
    classification: str | None = ""


class BtcFunding(BaseModel):
    model_config = ConfigDict(extra="allow")

    rate_percentage: int | float | None = None


class SentimentBasicPayload(BaseModel):
    """Fast local SentimentCard payload."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    timestamp: str
    market_heat: MarketHeat
    fear_greed: FearGreed
    btc_funding: BtcFunding
    meta: MetaHealth


class AlertMetrics(BaseModel):
    """Typed numeric metrics for an alert — prefer over parsing message text."""

    model_config = ConfigDict(extra="allow")

    pct: int | float | None = None
    window_s: int | None = None
    price: int | float | None = None
    price_now: int | float | None = None
    price_then: int | float | None = None
    volume: int | float | None = None
    vol_change_pct: int | float | None = None


class AlertItem(BaseModel):
    """Normalized alert item payload for /api/alerts (and related feeds)."""

    model_config = ConfigDict(extra="allow")

    id: str
    ts: str
    type: str
    severity: str
    symbol: str | None = None
    window: str | None = None
    window_s: int | None = None
    pct: int | float | None = None  # legacy compat — prefer metrics.pct
    price: int | float | None = None
    price_now: int | float | None = None
    price_then: int | float | None = None
    vol_pct: int | float | None = None
    vol_now: int | float | None = None
    vol_then: int | float | None = None
    direction: str | None = None
    message: str | None = None
    title: str | None = None
    product_id: str | None = None
    ts_ms: int | None = None
    event_ts: str | None = None
    event_ts_ms: int | None = None
    expires_at: str | None = None
    score: int | float | None = None
    sources: List[str] | None = None
    trade_url: str | None = None
    meta: Dict[str, Any] | None = None
    extra: Dict[str, Any] | None = None
    metrics: AlertMetrics | None = None
    dedupe_key: str | None = None
    cooldown_s: int | None = None
    event_count: int | None = None


__all__ = ["MetaHealth", "SentimentBasicPayload", "AlertItem", "AlertMetrics"]
