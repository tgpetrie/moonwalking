"""Descriptive price levels for portfolio holdings.

Computes recent support/resistance, an ATR volatility band, range position,
short-term momentum, and a volume trend from raw OHLC candles. These are
*descriptive* — they report where price has been and how it is behaving, and
are explicitly NOT outcome-validated (BHABIT does not yet claim these levels
predict anything). The route layer fetches candles; this module is pure math so
it can be unit-tested without network access.

Candle shape (Coinbase Exchange): ``[time, low, high, open, close, volume]``.
"""

from __future__ import annotations

from statistics import median
from typing import Any

_ATR_PERIOD = 14


def _to_rows(
    candles: list[list[Any]],
) -> list[tuple[float, float, float, float, float, float]]:
    rows: list[tuple[float, float, float, float, float, float]] = []
    for candle in candles or []:
        if not candle or len(candle) < 6:
            continue
        try:
            ts, low, high, open_, close, volume = (
                float(candle[0]),
                float(candle[1]),
                float(candle[2]),
                float(candle[3]),
                float(candle[4]),
                float(candle[5]),
            )
        except (TypeError, ValueError):
            continue
        if high <= 0 or low <= 0 or close <= 0:
            continue
        rows.append((ts, low, high, open_, close, volume))
    # Ascending by timestamp so true-range sequencing is correct.
    rows.sort(key=lambda r: r[0])
    return rows


def _atr(rows: list[tuple[float, ...]], period: int = _ATR_PERIOD) -> float | None:
    """Average True Range over the most recent ``period`` candles."""
    if len(rows) < 2:
        return None
    true_ranges: list[float] = []
    for idx in range(1, len(rows)):
        _, low, high, _open, _close, _vol = rows[idx]
        prev_close = rows[idx - 1][4]
        true_ranges.append(
            max(high - low, abs(high - prev_close), abs(low - prev_close))
        )
    window = true_ranges[-period:]
    if not window:
        return None
    return sum(window) / len(window)


def _range_zone(position_pct: float) -> str:
    if position_pct <= 15:
        return "near_support"
    if position_pct < 40:
        return "lower_range"
    if position_pct <= 60:
        return "mid_range"
    if position_pct < 85:
        return "upper_range"
    return "near_resistance"


def compute_levels(
    candles: list[list[Any]],
    current_price: float | None,
    *,
    granularity_seconds: int = 3600,
) -> dict[str, Any] | None:
    """Derive descriptive levels + behavior from OHLC candles.

    Returns ``None`` when there aren't enough candles to say anything honest.
    """
    rows = _to_rows(candles)
    if len(rows) < 3:
        return None

    price = None
    try:
        price = float(current_price) if current_price is not None else None
    except (TypeError, ValueError):
        price = None
    if not price or price <= 0:
        price = rows[-1][4]  # fall back to last close

    lows = [r[1] for r in rows]
    highs = [r[2] for r in rows]
    volumes = [r[5] for r in rows]

    support = min(lows)
    resistance = max(highs)
    span = resistance - support

    # Where price sits in the recent range (clamped 0..100).
    if span > 0:
        raw_pos = ((price - support) / span) * 100.0
        range_position = max(0.0, min(100.0, raw_pos))
    else:
        range_position = 50.0

    atr = _atr(rows)
    band_low = band_high = volatility_pct = None
    if atr is not None and atr > 0:
        band_low = max(0.0, price - atr)
        band_high = price + atr
        volatility_pct = (atr / price) * 100.0

    # Short-term momentum: change across the two most recent candles.
    momentum_pct = None
    if len(rows) >= 2:
        prev_close = rows[-2][4]
        if prev_close > 0:
            momentum_pct = ((rows[-1][4] - prev_close) / prev_close) * 100.0

    # Volume trend: most recent candle vs the median of the prior window.
    volume_ratio = None
    if len(volumes) >= 4:
        baseline = median(volumes[:-1])
        if baseline > 0:
            volume_ratio = volumes[-1] / baseline

    window_hours = round((len(rows) * granularity_seconds) / 3600.0, 1)

    def _r(value: float | None) -> float | None:
        return round(value, 8) if value is not None else None

    return {
        "support": _r(support),
        "resistance": _r(resistance),
        "atr": _r(atr),
        "band_low": _r(band_low),
        "band_high": _r(band_high),
        "range_position_pct": round(range_position, 1),
        "range_zone": _range_zone(range_position),
        "volatility_pct": (
            round(volatility_pct, 2) if volatility_pct is not None else None
        ),
        "momentum_1h_pct": round(momentum_pct, 2) if momentum_pct is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "window_hours": window_hours,
        "candle_count": len(rows),
        "outcome_validated": False,
        "source": "coinbase_candles",
    }


__all__ = ["compute_levels"]
