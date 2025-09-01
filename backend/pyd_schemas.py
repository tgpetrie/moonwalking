"""Pydantic response models for selected API endpoints.

Initial slice: health, metrics (core + circuit breaker + one SWR cache entry shape),
gainers 1m table component. Additional endpoints can be added incrementally.
"""
from __future__ import annotations
from typing import List, Optional, Dict
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

class PriceFetchMetrics(BaseModel):
    total_calls: int
    snapshot_served: int
    products_cache_hits: int
    rate_limit_failures: int
    last_fetch_duration_ms: float
    last_success_time: float | None
    errors: int
    durations_ms: List[float] | None = None
    rate_failures: int
    rate_next_epoch: float | None
    has_snapshot: bool
    snapshot_age_sec: float | None = None
    p95_fetch_duration_ms: float | None = None
    error_rate_percent: float | None = None
    backoff_seconds_remaining: float | None = None
    circuit_breaker: Optional[CircuitBreakerModel] = None
    fetch_duration_hist_buckets: Optional[Dict[str, int]] = None
    fetch_duration_hist_overflow: Optional[int] = None
    fetch_duration_sum_ms: Optional[float] = None
    fetch_duration_count: Optional[int] = None

class MetricsResponse(BaseModel):
    status: str
    uptime_seconds: float
    errors_5xx: int
    price_fetch: Optional[PriceFetchMetrics] = None
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
    'HealthResponse','MetricsResponse','CircuitBreakerModel','SWRCacheStats','PriceFetchMetrics',
    'Gainers1mComponent','GainerRow1m'
]