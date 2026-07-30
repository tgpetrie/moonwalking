"""Per-coin derivatives positioning (funding + open interest).

Market context for a single coin, built from Hyperliquid's keyless on-chain perp
data. This is *context* that supports or qualifies a coin's price/volume case —
never a standalone buy/sell signal, and it is never counted as a real signal in
signal-coverage math.

Truthfulness rules mirrored from the sentiment service:
- No perp market for the coin -> return None (caller shows "no derivatives market").
- Keyless Hyperliquid gives instant funding + OI but not historical OI, so the
  OI-change read only appears once the in-memory snapshot store has ≥2 samples
  over a real span. Until then we fall back to a funding×price read.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("derivatives_positioning")

HYPERLIQUID_BASE_URL = "https://api.hyperliquid.xyz"
HYPERLIQUID_FUNDING_INTERVAL_HOURS = 1.0

_CTX_CACHE: Optional[Dict[str, Any]] = None
_CTX_CACHE_TS: Optional[datetime] = None
_CTX_CACHE_TTL_SEC = 60.0

# symbol -> list of (timestamp, open_interest). Bounded to ~24h so the OI-change
# read reflects a real, honestly-labelled span rather than a fabricated 24h.
_OI_HISTORY: Dict[str, List[Tuple[datetime, float]]] = {}
_OI_HISTORY_WINDOW_SEC = 24 * 60 * 60
_OI_MIN_SPAN_SEC = 20 * 60  # need ≥20 min of history before reporting a change

# Price move considered directional (percent). Below this, treat as flat.
_PRICE_FLAT_PCT = 1.0
# Open-interest move considered directional (percent).
_OI_FLAT_PCT = 3.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(val: Any) -> Optional[float]:
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def classify_funding(funding_hourly: Optional[float]) -> Tuple[str, str]:
    """Map an hourly funding rate to a crowding key + human label.

    Thresholds are on the annualized rate (hourly × 24 × 365) so they read in
    familiar terms: a persistently positive rate means longs are paying to hold,
    i.e. the long side is crowded.
    """
    if funding_hourly is None:
        return "unknown", "Unknown"
    annualized = funding_hourly * 24 * 365
    if annualized >= 0.20:
        return "crowded_long", "Longs paying (crowded)"
    if annualized > 0.03:
        return "long", "Longs paying"
    if annualized <= -0.20:
        return "crowded_short", "Shorts paying (crowded)"
    if annualized < -0.03:
        return "short", "Shorts paying"
    return "neutral", "Neutral"


def positioning_read(
    price_change_pct: Optional[float],
    funding_hourly: Optional[float],
    oi_change_pct: Optional[float],
) -> Tuple[str, str]:
    """Return (read, tone) describing how positioning relates to the price move.

    Prefer the OI×price read (new money vs. covering) when OI history exists;
    otherwise fall back to a funding×price read (crowding vs. move). Tone is one
    of: favorable, caution, adverse, neutral.
    """
    price_up = price_change_pct is not None and price_change_pct >= _PRICE_FLAT_PCT
    price_down = price_change_pct is not None and price_change_pct <= -_PRICE_FLAT_PCT

    if oi_change_pct is not None:
        oi_up = oi_change_pct >= _OI_FLAT_PCT
        oi_down = oi_change_pct <= -_OI_FLAT_PCT
        if price_up and oi_up:
            return "OI rising with price — new money, conviction", "favorable"
        if price_up and oi_down:
            return "Rally on falling OI — short-covering, fragile", "caution"
        if price_down and oi_up:
            return "OI rising as price falls — shorts pressing", "adverse"
        if price_down and oi_down:
            return "OI falling with price — long unwind, exhaustion", "neutral"
        return "Positioning steady", "neutral"

    # No OI history yet — read funding against the move instead.
    bias, _ = classify_funding(funding_hourly)
    if price_up and bias == "crowded_long":
        return "Rally with crowded longs — squeeze risk", "caution"
    if price_up and bias in ("neutral", "short", "crowded_short"):
        return "Rally, funding not crowded — healthier", "favorable"
    if price_down and bias in ("short", "crowded_short"):
        return "Dip with shorts paying — squeeze fuel", "favorable"
    if price_down and bias in ("long", "crowded_long"):
        return "Falling with longs still crowded — more downside risk", "adverse"
    return {
        "crowded_long": "Longs crowded",
        "long": "Longs paying",
        "crowded_short": "Shorts crowded",
        "short": "Shorts paying",
        "neutral": "Funding neutral",
        "unknown": "Funding unavailable",
    }[bias], "neutral"


def _record_oi(symbol: str, open_interest: Optional[float], ts: datetime) -> None:
    if open_interest is None:
        return
    history = _OI_HISTORY.setdefault(symbol, [])
    history.append((ts, open_interest))
    cutoff = ts.timestamp() - _OI_HISTORY_WINDOW_SEC
    _OI_HISTORY[symbol] = [(t, oi) for (t, oi) in history if t.timestamp() >= cutoff]


def _oi_change(symbol: str) -> Optional[Tuple[float, float]]:
    """Return (percent_change, span_hours) over the oldest sample we hold, or None."""
    history = _OI_HISTORY.get(symbol) or []
    if len(history) < 2:
        return None
    oldest_ts, oldest_oi = history[0]
    newest_ts, newest_oi = history[-1]
    span_sec = newest_ts.timestamp() - oldest_ts.timestamp()
    if span_sec < _OI_MIN_SPAN_SEC or not oldest_oi:
        return None
    pct = ((newest_oi - oldest_oi) / oldest_oi) * 100
    return round(pct, 1), round(span_sec / 3600, 1)


async def _fetch_hyperliquid_ctxs() -> Optional[Dict[str, Dict[str, Any]]]:
    """Return {asset_name: ctx} from Hyperliquid, cached briefly. None on failure."""
    global _CTX_CACHE, _CTX_CACHE_TS
    if _CTX_CACHE is not None and _CTX_CACHE_TS is not None:
        if (_now().timestamp() - _CTX_CACHE_TS.timestamp()) <= _CTX_CACHE_TTL_SEC:
            return _CTX_CACHE

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
        by_name = {
            asset.get("name"): asset_ctxs[i]
            for i, asset in enumerate(universe)
            if i < len(asset_ctxs)
        }
        _CTX_CACHE = by_name
        _CTX_CACHE_TS = _now()
        return by_name
    except Exception as exc:
        logger.warning("Hyperliquid ctx fetch failed: %s", exc)
        return None


async def get_symbol_positioning(
    base_asset: str, *, price_change_pct: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Per-coin positioning context, or None if the coin has no Hyperliquid perp."""
    asset = (base_asset or "").upper().strip()
    if not asset:
        return None

    ctxs = await _fetch_hyperliquid_ctxs()
    if ctxs is None:
        return None
    ctx = ctxs.get(asset)
    if not ctx:
        return None  # no perp market for this coin

    now = _now()
    funding = _safe_float(ctx.get("funding"))
    open_interest = _safe_float(ctx.get("openInterest"))
    mark_price = _safe_float(ctx.get("markPx"))
    _record_oi(asset, open_interest, now)

    oi_change = _oi_change(asset)
    oi_change_pct = oi_change[0] if oi_change else None
    oi_window_hours = oi_change[1] if oi_change else None

    bias_key, funding_label = classify_funding(funding)
    read, tone = positioning_read(price_change_pct, funding, oi_change_pct)

    return {
        "available": True,
        "base_asset": asset,
        "venue": "hyperliquid",
        "funding_rate": funding,
        "funding_interval_hours": HYPERLIQUID_FUNDING_INTERVAL_HOURS,
        "funding_bias": bias_key,
        "funding_label": funding_label,
        "open_interest": open_interest,
        "open_interest_usd": (
            open_interest * mark_price
            if open_interest is not None and mark_price is not None
            else None
        ),
        "oi_change_pct": oi_change_pct,
        "oi_window_hours": oi_window_hours,
        "mark_price": mark_price,
        "read": read,
        "read_tone": tone,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
    }
