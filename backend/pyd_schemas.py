"""Pydantic response models for selected API endpoints.

Initial slice: health, metrics (core + circuit breaker + one SWR cache entry shape),
gainers 1m table component. Additional endpoints can be added incrementally.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(pattern='^ok$')
    uptime_seconds: float
    errors_5xx: int

class CircuitBreakerModel(BaseModel):
    state: str
    failures: int
    open_until: float
    is_open: bool
    is_half_open: bool

class SWRCacheStats(BaseModel):
    cache_age_seconds: Optional[float]
    served_cached_last: bool
    ttl: float
    stale_window: float
    total_calls: int
    served_cached: int
    served_fresh: int
    background_refreshes: int
    last_refresh_duration_sec: Optional[float]

class MetricsResponse(BaseModel):
    status: str
    uptime_seconds: float
    errors_5xx: int
    price_fetch: Optional[Dict[str, Any]] = None  # keep raw for now
    circuit_breaker: Optional[CircuitBreakerModel] = None
    swr_caches: Optional[Dict[str, SWRCacheStats]] = None

class GainerRow1m(BaseModel):
    rank: int
    symbol: str
    current_price: float
    price_change_percentage_1min: float
    initial_price_1min: float
    actual_interval_minutes: int
    peak_gain: float
    trend_direction: str
    trend_streak: int
    trend_score: float
    trend_delta: float
    momentum: str
    alert_level: str

class Gainers1mComponent(BaseModel):
    component: str
    data: List[GainerRow1m]
    count: int
    table_type: str
    time_frame: str
    update_interval: int
    last_updated: str

__all__ = [
    'HealthResponse','MetricsResponse','CircuitBreakerModel','SWRCacheStats',
    'Gainers1mComponent','GainerRow1m'
]