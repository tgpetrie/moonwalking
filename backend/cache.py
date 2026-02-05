"""
Cache Module for Intelligence Reports
Implements Stale-While-Revalidate (SWR) semantics with Redis
"""
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def iso_now() -> str:
    """Returns current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(ts: str) -> float:
    """Converts ISO timestamp to epoch seconds. Safe fallback to now."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()


@dataclass
class CachePolicy:
    """
    Cache behavior configuration.

    - version: Cache key version for breaking changes
    - ttl_seconds: How long a report is considered "fresh"
    - stale_seconds: How long we serve stale while refreshing
    - building_lock_seconds: Lock duration to prevent refresh stampedes
    """
    version: str = "v1"
    ttl_seconds: int = 300  # 5 minutes fresh
    stale_seconds: int = 900  # serve stale for up to 15 minutes while refreshing
    building_lock_seconds: int = 30  # prevent duplicate refreshes


def _json_loads(raw: Optional[bytes]) -> Optional[Dict[str, Any]]:
    """Safe JSON decode from Redis bytes."""
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _json_dumps(obj: Dict[str, Any]) -> str:
    """Compact JSON encode for Redis storage."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def cache_key(symbol: str, policy: CachePolicy) -> str:
    """Returns Redis key for a symbol's intelligence report."""
    return f"intel:{policy.version}:{symbol.upper()}"


def lock_key(symbol: str, policy: CachePolicy) -> str:
    """Returns Redis key for refresh lock."""
    return f"intel_lock:{policy.version}:{symbol.upper()}"


def get_cached_report(
    rds,
    symbol: str,
    policy: CachePolicy
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Retrieves cached report and determines freshness.

    Returns:
        (payload, freshness) where freshness is:
        - "fresh": Within TTL, use immediately
        - "stale": Beyond TTL but within stale window, serve + refresh
        - "miss": No cache or expired, must build
    """
    key = cache_key(symbol, policy)
    payload = _json_loads(rds.get(key))

    if not payload:
        return None, "miss"

    generated_at = payload.get("generated_at")
    ttl_seconds = int(payload.get("ttl_seconds", policy.ttl_seconds))

    # Calculate age in seconds
    age = max(0.0, time.time() - parse_iso(generated_at)) if generated_at else 999999.0

    if age <= ttl_seconds:
        return payload, "fresh"
    if age <= (ttl_seconds + policy.stale_seconds):
        return payload, "stale"

    return None, "miss"


def set_cached_report(
    rds,
    symbol: str,
    payload: Dict[str, Any],
    policy: CachePolicy
) -> None:
    """
    Stores intelligence report in Redis.

    TTL is set to ttl_seconds + stale_seconds to allow stale serving.
    Actual freshness is computed at read-time based on generated_at.
    """
    ttl = int(payload.get("ttl_seconds", policy.ttl_seconds))
    redis_ttl = ttl + policy.stale_seconds
    key = cache_key(symbol, policy)
    rds.setex(key, redis_ttl, _json_dumps(payload))


def acquire_refresh_lock(rds, symbol: str, policy: CachePolicy) -> bool:
    """
    Attempts to acquire a refresh lock for the symbol.

    Uses Redis SETNX (set if not exists) with expiry to prevent
    multiple concurrent refreshes for the same symbol.

    Returns:
        True if lock acquired, False if already locked
    """
    lk = lock_key(symbol, policy)
    return bool(rds.set(lk, "1", nx=True, ex=policy.building_lock_seconds))


def release_refresh_lock(rds, symbol: str, policy: CachePolicy) -> None:
    """Releases the refresh lock for a symbol."""
    lk = lock_key(symbol, policy)
    try:
        rds.delete(lk)
    except Exception:
        pass


def building_stub(symbol: str, policy: CachePolicy) -> Dict[str, Any]:
    """
    Returns a placeholder report when cache is building.

    This is served immediately to avoid blocking the API while
    background refresh runs.
    """
    return {
        "symbol": symbol.upper(),
        "price": None,
        "metrics": {
            "finbert_score": 0.0,
            "finbert_label": "Neutral",
            "fear_greed_index": None,
            "social_volume": None,
            "confidence": 0.0,
            "divergence": "none",
        },
        "narrative": None,
        "raw_context": {"top_headlines": []},
        "generated_at": iso_now(),
        "ttl_seconds": policy.ttl_seconds,
        "freshness": "building",
        "model": {"name": "ProsusAI/finbert", "device": None, "quantized": False},
    }
