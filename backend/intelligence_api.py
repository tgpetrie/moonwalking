"""
Intelligence API Module
Provides batch and single intelligence report endpoints with Redis SWR caching
"""
import os
import logging
from typing import Dict, List

from flask import Blueprint, jsonify, request
import redis

from cache import CachePolicy, get_cached_report, building_stub, iso_now
from sentiment_intelligence import load_engine
from refresh import Refresher

logger = logging.getLogger(__name__)

# Create blueprint
intelligence_bp = Blueprint('intelligence', __name__)

# Initialize once at module load
policy = CachePolicy(
    version=os.getenv("INTEL_VERSION", "v1"),
    ttl_seconds=int(os.getenv("INTEL_TTL_SECONDS", "300")),
    stale_seconds=int(os.getenv("INTEL_STALE_SECONDS", "900")),
    building_lock_seconds=int(os.getenv("INTEL_BUILDING_LOCK_SECONDS", "30")),
)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    rds = redis.Redis.from_url(redis_url, decode_responses=False)
    rds.ping()
    logger.info(f"✅ Redis connected: {redis_url}")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    rds = None

# Load FinBERT engine once
try:
    engine = load_engine()
    refresher = Refresher(
        rds=rds,
        engine=engine,
        policy=policy,
        max_workers=int(os.getenv("INTEL_REFRESH_WORKERS", "4")),
    ) if rds else None
    logger.info(f"✅ Intelligence engine loaded on {engine.device}")
except Exception as e:
    logger.error(f"❌ Failed to load intelligence engine: {e}")
    engine = None
    refresher = None


def ok(data):
    """Success response wrapper."""
    return jsonify({"success": True, "version": policy.version, "data": data})


def err(code: str, message: str, details=None, status: int = 400):
    """Error response wrapper."""
    payload = {
        "success": False,
        "version": policy.version,
        "error": {"code": code, "message": message}
    }
    if details is not None:
        payload["error"]["details"] = details
    return jsonify(payload), status


def parse_symbols_param() -> List[str]:
    """Parse and validate symbols query parameter."""
    raw = request.args.get("symbols", "")
    syms = [s.strip().upper() for s in raw.split(",") if s.strip()]
    # Clamp to protect the server
    max_syms = int(os.getenv("INTEL_MAX_SYMBOLS", "50"))
    return syms[:max_syms]


@intelligence_bp.route('/api/health-intelligence')
def health_intelligence():
    """Health check for intelligence subsystem."""
    redis_ok = False
    if rds:
        try:
            rds.ping()
            redis_ok = True
        except Exception:
            pass

    return ok({
        "status": "ok",
        "time": iso_now(),
        "redis_ok": redis_ok,
        "engine_loaded": engine is not None,
        "model": {
            "name": "ProsusAI/finbert",
            "device": engine.device if engine else None,
            "quantized": False,
        } if engine else None,
    })


@intelligence_bp.route('/api/intelligence-reports')
def intelligence_reports():
    """
    Batch intelligence reports endpoint.

    Query params:
        symbols: Comma-separated list of symbols (e.g., ?symbols=BTC,ETH,SOL)

    Returns:
        {
            "success": true,
            "version": "v1",
            "data": {
                "BTC": { ...report... },
                "ETH": { ...report... },
                ...
            }
        }
    """
    if not engine or not rds or not refresher:
        return err("service_unavailable", "Intelligence service not available", status=503)

    symbols = parse_symbols_param()
    if not symbols:
        return err(
            "bad_request",
            "Query param 'symbols' is required, e.g. ?symbols=BTC,ETH",
            status=400
        )

    out: Dict[str, dict] = {}

    for sym in symbols:
        cached, freshness = get_cached_report(rds, sym, policy)

        if cached:
            # If stale, serve it and trigger a refresh in background
            cached["freshness"] = freshness
            out[sym] = cached
            if freshness == "stale":
                refresher.trigger_refresh(sym)
            continue

        # Cache miss: return building stub, trigger refresh
        stub = building_stub(sym, policy)
        stub["model"]["device"] = engine.device
        out[sym] = stub
        refresher.trigger_refresh(sym)

    return ok(out)


@intelligence_bp.route('/api/intelligence-report/<symbol>')
def intelligence_report(symbol: str):
    """
    Single intelligence report endpoint.

    Path params:
        symbol: The crypto symbol (e.g., BTC, ETH)

    Returns:
        {
            "success": true,
            "version": "v1",
            "data": { ...report... }
        }
    """
    if not engine or not rds or not refresher:
        return err("service_unavailable", "Intelligence service not available", status=503)

    sym = symbol.strip().upper()
    if not sym:
        return err("bad_request", "Symbol is required", status=400)

    cached, freshness = get_cached_report(rds, sym, policy)

    if cached:
        cached["freshness"] = freshness
        if freshness == "stale":
            refresher.trigger_refresh(sym)
        return ok(cached)

    # Cache miss: return building stub, trigger refresh
    stub = building_stub(sym, policy)
    stub["model"]["device"] = engine.device
    refresher.trigger_refresh(sym)
    return ok(stub)
