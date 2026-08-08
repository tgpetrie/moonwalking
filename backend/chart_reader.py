"""Chart Read — deterministic OHLCV analysis for basic-user summaries.

Math reads the chart. Language is assembled from templates.
No predictions, no advice, no buy/sell/hold/entry/exit language.

Candle shape (Coinbase Exchange): ``[time, low, high, open, close, volume]``,
returned descending by time from the API. Pass raw; this module sorts ascending.
"""

from __future__ import annotations

from typing import Any

__all__ = ["analyze_candles"]


# ─── normalise ────────────────────────────────────────────────────────────────


def _normalize_candles(
    raw: list[list[Any]],
) -> list[tuple[float, float, float, float, float, float]]:
    """Parse + sort raw Coinbase candles ascending by timestamp."""
    rows: list[tuple[float, float, float, float, float, float]] = []
    for c in raw or []:
        if not c or len(c) < 6:
            continue
        try:
            ts, low, high, open_, close, vol = (
                float(c[0]),
                float(c[1]),
                float(c[2]),
                float(c[3]),
                float(c[4]),
                float(c[5]),
            )
        except (TypeError, ValueError):
            continue
        if high <= 0 or low <= 0 or close <= 0:
            continue
        rows.append((ts, low, high, open_, close, vol))
    rows.sort(key=lambda r: r[0])
    return rows


def _price_fmt(value: float) -> float:
    """Round a price to a visually clean number of decimal places."""
    if value >= 10_000:
        return round(value, 0)
    if value >= 1_000:
        return round(value, 1)
    if value >= 100:
        return round(value, 1)
    if value >= 10:
        return round(value, 2)
    if value >= 1:
        return round(value, 3)
    return round(value, 6)


def _zone_n(total: int) -> int:
    """Candles used to define a support/resistance zone (~20%, min 3)."""
    return max(3, total // 5)


# ─── calculation helpers ───────────────────────────────────────────────────────


def _calculate_trend(rows: list[tuple]) -> dict:
    """Compare avg close of second half vs first half to derive direction."""
    closes = [r[4] for r in rows]
    n = len(closes)
    if n < 4:
        return {"label": "sideways", "slope_pct": 0.0}
    half = n // 2
    first_avg = sum(closes[:half]) / half
    second_avg = sum(closes[half:]) / (n - half)
    if first_avg <= 0:
        return {"label": "sideways", "slope_pct": 0.0}
    slope_pct = ((second_avg - first_avg) / first_avg) * 100.0
    if slope_pct > 2.0:
        label = "up"
    elif slope_pct < -2.0:
        label = "down"
    else:
        label = "sideways"
    return {"label": label, "slope_pct": round(slope_pct, 2)}


def _find_support_zone(rows: list[tuple]) -> list[float]:
    """Lowest ~20% of candle lows define the support zone."""
    lows = sorted(r[1] for r in rows)
    n = _zone_n(len(lows))
    zone = lows[:n]
    lo = _price_fmt(zone[0])
    hi = _price_fmt(zone[-1])
    if lo >= hi:
        hi = _price_fmt(lo * 1.005)
    return [lo, hi]


def _find_resistance_zone(rows: list[tuple]) -> list[float]:
    """Highest ~20% of candle highs define the resistance zone."""
    highs = sorted((r[2] for r in rows), reverse=True)
    n = _zone_n(len(highs))
    zone = highs[:n]
    lo = _price_fmt(zone[-1])
    hi = _price_fmt(zone[0])
    if lo >= hi:
        lo = _price_fmt(hi * 0.995)
    return [lo, hi]


def _compare_volume(rows: list[tuple]) -> dict:
    """Recent 5 candles vs the baseline of the rest."""
    volumes = [r[5] for r in rows]
    if len(volumes) < 4:
        return {"label": "normal", "ratio": 1.0}
    recent = volumes[-5:]
    baseline = volumes[:-5] or volumes[:-1]
    recent_avg = sum(recent) / len(recent)
    base_avg = sum(baseline) / len(baseline)
    if base_avg <= 0:
        return {"label": "normal", "ratio": 1.0}
    ratio = recent_avg / base_avg
    if ratio > 1.5:
        label = "high"
    elif ratio < 0.6:
        label = "low"
    else:
        label = "normal"
    return {"label": label, "ratio": round(ratio, 2)}


def _range_position(rows: list[tuple]) -> dict:
    """Where the last close sits in the full recent high-low range."""
    lows = [r[1] for r in rows]
    highs = [r[2] for r in rows]
    price = rows[-1][4]
    support = min(lows)
    resistance = max(highs)
    span = resistance - support
    if span <= 0:
        pct = 50.0
    else:
        pct = max(0.0, min(100.0, ((price - support) / span) * 100.0))
    if pct <= 15:
        zone = "near_support"
    elif pct < 40:
        zone = "lower_range"
    elif pct <= 60:
        zone = "mid_range"
    elif pct < 85:
        zone = "upper_range"
    else:
        zone = "near_resistance"
    return {"pct": round(pct, 1), "zone": zone}


def _score_confidence(
    trend_label: str,
    volume_label: str,
    candle_count: int,
) -> str:
    score = 0
    if candle_count >= 20:
        score += 1
    if candle_count >= 40:
        score += 1
    if trend_label in ("up", "down"):
        score += 1
    # Volume behind the trend adds conviction
    if volume_label == "high" and trend_label in ("up", "down"):
        score += 1
    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ─── text builders ────────────────────────────────────────────────────────────

_DIRECTION_TEXT = {
    "up": "The price has generally been moving higher.",
    "down": "The price has generally been moving lower.",
    "sideways": "The price has been moving sideways without a clear direction.",
}

_VOLUME_TEXT = {
    "high": "Trading activity is above normal, suggesting more participants are involved in the move.",
    "normal": "Trading activity is not unusually strong or weak.",
    "low": "Trading activity is below normal, which makes the move harder to trust.",
}


def _vol_phrase(label: str) -> str:
    return {
        "high": "trading activity is above normal",
        "normal": "trading activity is normal",
        "low": "trading activity is below normal",
    }[label]


def _fmt_zone(lo: float, hi: float) -> str:
    return f"${lo}–${hi}"


def _build_summary(
    symbol: str,
    trend_label: str,
    volume_label: str,
    range_zone: str,
    lower_area: list[float],
    upper_area: list[float],
) -> str:
    vol = _vol_phrase(volume_label)
    lo_lo, lo_hi = lower_area
    up_lo, up_hi = upper_area
    lo_z = _fmt_zone(lo_lo, lo_hi)
    up_z = _fmt_zone(up_lo, up_hi)

    if trend_label == "up":
        if range_zone == "near_resistance":
            return (
                f"{symbol} has been moving up, but it is getting close to a price area "
                f"({up_z}) where sellers recently pushed it back. "
                f"The move is notable, but {vol}, so it is not strongly confirmed yet."
            )
        if range_zone in ("mid_range", "lower_range"):
            return (
                f"{symbol} has been moving higher through its recent range. "
                f"It has room before reaching the upper area around {up_z}, "
                f"and {vol}."
            )
        if range_zone == "upper_range":
            return (
                f"{symbol} has been moving up and is now in the upper part of its recent range, "
                f"approaching the area around {up_z} where sellers have pushed back before. "
                f"Notably, {vol}."
            )
        # near_support
        return (
            f"{symbol} has been moving up from near the lower area around {lo_z} "
            f"where buyers recently showed up. "
            f"Notably, {vol}."
        )

    if trend_label == "down":
        if range_zone == "near_support":
            return (
                f"{symbol} has been moving down and is approaching the lower area "
                f"({lo_z}) where buyers have shown up before. "
                f"Whether buyers step in again is unclear, and {vol}."
            )
        if range_zone in ("mid_range", "upper_range"):
            return (
                f"{symbol} has been moving lower through its recent range. "
                f"The lower area around {lo_z} is further below, "
                f"and {vol}."
            )
        if range_zone == "lower_range":
            return (
                f"{symbol} has been moving lower and is now in the lower part of its recent range. "
                f"The lower area around {lo_z} is nearby, and {vol}."
            )
        # near_resistance
        return (
            f"{symbol} has been moving down from near the upper area around {up_z} "
            f"where sellers recently pushed it back. "
            f"Notably, {vol}."
        )

    # sideways
    return (
        f"{symbol} has been moving sideways without a clear direction, "
        f"trading between the lower area around {lo_z} "
        f"and the upper area around {up_z}. "
        f"Notably, {vol}."
    )


def _watch_next(
    trend_label: str,
    lower_area: list[float],
    upper_area: list[float],
) -> list[str]:
    lo = lower_area[0]
    hi = upper_area[1]
    if trend_label == "up":
        return [
            f"The read gets stronger if price pushes above ${hi} with higher trading activity.",
            f"The read gets weaker if price falls below ${lo} with rising trading activity.",
        ]
    if trend_label == "down":
        return [
            f"The read gets stronger if price falls through ${lo} with higher trading activity.",
            f"The read gets weaker if price bounces above ${hi} with rising trading activity.",
        ]
    return [
        f"Watch for a move above ${hi} with higher trading activity to suggest upward momentum.",
        f"Watch for a move below ${lo} with rising trading activity to suggest downward pressure.",
    ]


# ─── granularity helper ───────────────────────────────────────────────────────


def _hours_per_candle(timeframe: str) -> float:
    return {
        "1m": 1 / 60,
        "5m": 5 / 60,
        "15m": 0.25,
        "1h": 1.0,
        "4h": 4.0,
        "1d": 24.0,
    }.get(timeframe, 1.0)


# ─── public API ───────────────────────────────────────────────────────────────


def analyze_candles(
    raw_candles: list[list[Any]],
    symbol: str,
    timeframe: str = "1h",
) -> dict | None:
    """Analyze raw OHLCV candles and return a basic-user-friendly read.

    Returns ``None`` when there are not enough candles to produce an honest read.
    Caller is responsible for fetching candles; this module does no network I/O.
    """
    rows = _normalize_candles(raw_candles)
    if len(rows) < 5:
        return None

    sym = str(symbol or "").upper().strip()
    trend = _calculate_trend(rows)
    lower_area = _find_support_zone(rows)
    upper_area = _find_resistance_zone(rows)
    volume = _compare_volume(rows)
    rpos = _range_position(rows)
    confidence = _score_confidence(trend["label"], volume["label"], len(rows))

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "summary": _build_summary(
            sym,
            trend["label"],
            volume["label"],
            rpos["zone"],
            lower_area,
            upper_area,
        ),
        "direction": {
            "label": trend["label"],
            "basic_text": _DIRECTION_TEXT[trend["label"]],
        },
        "lower_area": {
            "zone": lower_area,
            "basic_text": "Buyers recently showed up around this area.",
            "technical_label": "support",
        },
        "upper_area": {
            "zone": upper_area,
            "basic_text": "Sellers recently pushed price back around this area.",
            "technical_label": "resistance",
        },
        "trading_activity": {
            "label": volume["label"],
            "basic_text": _VOLUME_TEXT[volume["label"]],
        },
        "confidence": confidence,
        "watch_next": _watch_next(trend["label"], lower_area, upper_area),
        "not_financial_advice": True,
        "candle_count": len(rows),
        "window_hours": round(len(rows) * _hours_per_candle(timeframe), 1),
    }
