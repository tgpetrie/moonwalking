"""Chart Read — deterministic OHLCV analysis for basic-user summaries.

Math reads the chart. Language is assembled from templates.
No predictions, no advice, no buy/sell/hold/entry/exit language.

Candle shape (Coinbase Exchange): ``[time, low, high, open, close, volume]``,
returned descending by time from the API. Pass raw; this module sorts ascending.
"""

from __future__ import annotations

import logging
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

import requests

__all__ = [
    "analyze_candles",
    "chart_candle_series",
    "build_wave_analysis",
    "fetch_multi_year_daily_candles",
    "aggregate_weekly_candles",
    "cached_cycle_products",
    "CYCLE_HISTORY_YEARS",
]

# Daily history loaded for a cycle read. The cycle range and Fibonacci grids
# use the trailing three years (``cycle_analysis.CYCLE_WINDOW_DAYS``); the
# fourth year is warm-up, so the 200-week average and the monthly MACD have
# enough bars behind them.
CYCLE_HISTORY_YEARS = 4

_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
# Higher timeframe used for the wave read's trend check, built from the same candles.
_HIGHER_TIMEFRAME = {"1m": "15m", "5m": "1h", "15m": "4h", "1h": "4h", "4h": "1d", "1d": "1w"}
# Candles sent with the wave read: the whole window the swings were read from,
# so earlier higher lows and lower highs can be drawn, not just the last count.
_WAVE_CHART_BARS = 300


def fetch_multi_year_daily_candles(product_id: str, years: int = 3) -> list[list[float]]:
    """Fetch complete daily Coinbase bars, caching a completed UTC day's history."""
    product = str(product_id or "").upper()
    if not re.fullmatch(r"[A-Z0-9]{1,15}-USD", product):
        raise ValueError("Invalid Coinbase product ID")
    if isinstance(years, bool) or not isinstance(years, int) or not 1 <= years <= 4:
        raise ValueError("years must be an integer between 1 and 4")
    end = int(time.time() // 86400) * 86400
    start = end - math.ceil(years * 365.25) * 86400
    path = Path(os.environ.get("MW_CYCLE_HISTORY_DB") or Path(__file__).resolve().parent / "data" / "cycle_history.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=10)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS cycle_history (product TEXT, years INTEGER, day_end INTEGER, candles TEXT NOT NULL, PRIMARY KEY(product, years))")
        hit = conn.execute("SELECT candles FROM cycle_history WHERE product=? AND years=? AND day_end=?", (product, years, end)).fetchone()
        if hit:
            return json.loads(hit[0])

    collected = {}
    cursor = end
    while cursor > start:
        begin = max(start, cursor - 300 * 86400)
        params = {
            "granularity": 86400,
            "start": datetime.fromtimestamp(begin, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(cursor - 1, timezone.utc).isoformat(),
        }
        response = requests.get(
            f"https://api.exchange.coinbase.com/products/{product}/candles",
            params=params, timeout=15,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Coinbase returned an invalid candle page")
        for row in page:
            if not isinstance(row, list) or len(row) < 6:
                raise ValueError("Coinbase returned a malformed daily candle")
            try:
                bar = [float(value) for value in row[:6]]
            except (TypeError, ValueError) as exc:
                raise ValueError("Coinbase returned a malformed daily candle") from exc
            ts, low, high, opening, close, volume = bar
            if not all(math.isfinite(value) for value in bar) or ts % 86400 or low <= 0 or volume < 0 or not low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError("Coinbase returned an invalid daily candle")
            if begin <= ts < cursor:
                collected[int(ts)] = bar
        cursor = begin
    candles = [collected[ts] for ts in sorted(collected, reverse=True)]
    with closing(sqlite3.connect(path, timeout=10)) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO cycle_history VALUES (?, ?, ?, ?)",
            (product, years, end, json.dumps(candles, allow_nan=False)),
        )
    return candles


def cached_cycle_products(years: int = CYCLE_HISTORY_YEARS) -> list[str]:
    """Products with daily history already in the cycle cache, newest first."""
    path = Path(os.environ.get("MW_CYCLE_HISTORY_DB") or Path(__file__).resolve().parent / "data" / "cycle_history.sqlite")
    if not path.exists():
        return []
    try:
        with closing(sqlite3.connect(path, timeout=10)) as conn:
            rows = conn.execute(
                "SELECT product FROM cycle_history WHERE years=? ORDER BY day_end DESC, product",
                (years,),
            ).fetchall()
    except sqlite3.Error:
        return []
    return [str(row[0]) for row in rows]


def aggregate_weekly_candles(daily: list[list[Any]] | None) -> list[list[float]]:
    """Aggregate complete Monday–Sunday UTC weeks; omit weeks with missing days."""
    rows = _normalize_candles(daily or [])
    groups: dict[int, list[tuple]] = {}
    for row in rows:
        start = int((row[0] + 3 * 86400) // 604800) * 604800 - 3 * 86400
        groups.setdefault(start, []).append(row)
    result = []
    for start, week in sorted(groups.items()):
        if [row[0] for row in week] != [start + day * 86400 for day in range(7)]:
            continue
        result.append([float(start), min(r[1] for r in week), max(r[2] for r in week), week[0][3], week[-1][4], sum(r[5] for r in week)])
    return result


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


def chart_candle_series(
    raw: list[list[Any]], timeframe: str, *, as_of_ts: float
) -> list[dict[str, float]]:
    """Chronological OHLCV for the selected timeframe, even without a wave read."""
    step = _SECONDS[timeframe]
    bars = {}
    for ts, low, high, opening, close, volume in _normalize_candles(raw):
        if not all(math.isfinite(value) for value in (ts, low, high, opening, close, volume)):
            continue
        if (
            ts < 0 or ts + step > as_of_ts or volume < 0
            or not low <= min(opening, close) <= max(opening, close) <= high
        ):
            continue
        bars[ts] = {
            "timestamp": ts,
            "open": opening,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    return [bars[ts] for ts in sorted(bars)]


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


def _f(
    evidence: dict[str, Any], *keys: str, default: float | None = None
) -> float | None:
    """Return the first finite numeric value found across the given keys."""
    for key in keys:
        value = evidence.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and number not in (float("inf"), float("-inf")):
            return number
    return default


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
    event_price: float | None = None,
) -> list[str]:
    lo = lower_area[0]
    hi = upper_area[1]
    if event_price is not None:
        ref = f"${_price_fmt(event_price)}"
        if trend_label == "up":
            return [
                f"The read gets stronger if price holds above {ref} with higher trading activity.",
                f"The read gets weaker if price falls back below {ref} with rising trading activity.",
            ]
        if trend_label == "down":
            return [
                f"The read gets stronger if price stays below {ref} with higher trading activity.",
                f"The read gets weaker if price moves back above {ref} with rising trading activity.",
            ]
        return [
            f"Watch whether price accepts above {ref} with higher trading activity to suggest upward pressure.",
            f"Watch whether price rejects below {ref} with rising trading activity to suggest downward pressure.",
        ]
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


def _normalize_event_context(
    event_context: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Keep optional launch context narrow and deterministic."""
    if not isinstance(event_context, dict):
        return None

    raw_type = str(
        event_context.get("type_key") or event_context.get("type") or ""
    ).strip()
    evidence = event_context.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}

    normalized: dict[str, Any] = {}
    if raw_type:
        normalized["type_key"] = raw_type.upper()

    evidence_out: dict[str, Any] = {}
    raw_window = str(
        evidence.get("window") or event_context.get("window") or ""
    ).strip()
    if raw_window:
        evidence_out["window"] = raw_window

    price = _f(evidence, "price")
    if price is None:
        price = _f(event_context, "price")
    if price is not None:
        evidence_out["price"] = price

    pct = _f(evidence, "pct")
    if pct is None:
        pct = _f(event_context, "pct")
    if pct is not None:
        evidence_out["pct"] = pct

    if evidence_out:
        normalized["evidence"] = evidence_out

    return normalized or None


def _event_context_note(event_context: dict[str, Any] | None) -> str | None:
    """Turn trigger metadata into a spatial reminder, not a detector read."""
    ctx = _normalize_event_context(event_context)
    if not ctx:
        return None

    type_key = str(ctx.get("type_key") or "").strip()
    evidence = ctx.get("evidence") if isinstance(ctx.get("evidence"), dict) else {}
    window = str(evidence.get("window") or "").strip()
    price = _f(evidence, "price")

    if type_key and window and price is not None:
        return f"The triggering {type_key} alert came from the {window} window near ${_price_fmt(price)}."
    if type_key and price is not None:
        return f"The triggering {type_key} alert came near ${_price_fmt(price)}."
    if type_key and window:
        return f"The triggering {type_key} alert came from the {window} window."
    if price is not None:
        return f"The alert fired near ${_price_fmt(price)}."
    if window:
        return f"The alert came from the {window} window."
    return None


# ─── wave structure ───────────────────────────────────────────────────────────


def _structure_layer():
    try:
        from chart_structure import plain_story, short_headline, swing_history
    except ImportError:
        from backend.chart_structure import (
            plain_story,
            short_headline,
            swing_history,
        )
    return plain_story, swing_history, short_headline


def _wave_fallback(reason: str) -> dict[str, Any]:
    """Same shape as an engine result, saying no wave read is available."""
    plain_story, swing_history, _ = _structure_layer()
    return {
        "available": False,
        "reason": reason,
        "active_pattern": "none",
        "status": "none",
        "bias": "neutral",
        "pivots": [],
        "wave_points": [],
        "projected_c_zone": None,
        "invalidation_price": None,
        "target_price": None,
        "fib_ratios": {},
        "confluence_factors": [],
        "confluence_score": 0.0,
        "confluence_confirmed": False,
        "confidence": 0.0,
        "confidence_label": "low",
        "summary": "Wave structure is not available for this chart.",
        "swing_history": swing_history([]),
        "story": plain_story(None),
        "short_headline": None,
        "outcome_validated": False,
    }


def build_wave_analysis(
    raw_candles: list[list[Any]] | None,
    timeframe: str = "1h",
    higher_tf_candles: list[list[Any]] | None = None,
    *,
    as_of_ts: float | None = None,
) -> dict[str, Any]:
    """Elliott wave read for the chart payload. Never raises.

    ``as_of_ts`` drops candles that have not closed by that time, so a forming
    bar cannot confirm or move a swing. Without ``higher_tf_candles`` the
    trend check is resampled from the same candles when there are enough.
    Returns the fallback shape when history is short or the engine fails.

    Plain-English layers ride along with every read: ``swing_history`` (each
    confirmed swing labeled as a higher or lower high or low), ``story`` (the
    read restated as numbered steps) and ``short_headline`` (one line for a
    header, or ``None``).
    """
    try:
        try:
            from elliott_wave_engine import analyze_wave_structure, resample_candles
        except ImportError:
            from backend.elliott_wave_engine import (
                analyze_wave_structure,
                resample_candles,
            )

        step = _SECONDS.get(timeframe)
        rows = _normalize_candles(raw_candles or [])
        if as_of_ts is not None and step:
            rows = [r for r in rows if r[0] + step <= as_of_ts]
        candles = [list(r) for r in rows]
        higher_name = _HIGHER_TIMEFRAME.get(timeframe)
        if higher_tf_candles is None:
            if higher_name:
                higher_tf_candles = aggregate_weekly_candles(candles) if timeframe == "1d" else resample_candles(candles, _SECONDS[higher_name])
        elif not higher_tf_candles:
            higher_name = None  # the caller supplied no higher-timeframe bars
        result = dict(
            analyze_wave_structure(candles, higher_tf_candles=higher_tf_candles)
        )
        result["timeframe"] = timeframe
        result["higher_timeframe"] = higher_name
        plain_story, swing_history, short_headline = _structure_layer()
        result["swing_history"] = swing_history(
            result.get("pivots"), candles[-1][4] if candles else None
        )
        result["story"] = plain_story(result)
        result["short_headline"] = short_headline(result)
        if result.get("available"):
            result["chart"] = {
                "candles": candles if timeframe == "1d" else candles[-_WAVE_CHART_BARS:],
                "granularity_seconds": step,
            }
        return result
    except Exception as exc:  # the chart read must survive a wave failure
        logging.warning("[ChartRead] wave analysis failed: %s", exc)
        fallback = _wave_fallback("engine_error")
        fallback["timeframe"] = timeframe
        return fallback


# ─── public API ───────────────────────────────────────────────────────────────


def analyze_candles(
    raw_candles: list[list[Any]],
    symbol: str,
    timeframe: str = "1h",
    event_context: dict[str, Any] | None = None,
    *,
    wave_candles: list[list[Any]] | None = None,
    higher_tf_candles: list[list[Any]] | None = None,
) -> dict | None:
    """Analyze raw OHLCV candles and return a basic-user-friendly read.

    Returns ``None`` when there are not enough candles to produce an honest read.
    Caller is responsible for fetching candles; this module does no network I/O.

    ``wave_analysis`` is always present. It reads ``wave_candles`` (a longer
    history of completed bars) when given, else the same candles, and falls
    back to an unavailable result when the history is too short.
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
    ctx = _normalize_event_context(event_context)
    ctx_note = _event_context_note(ctx)
    ctx_price = None
    if ctx and isinstance(ctx.get("evidence"), dict):
        ctx_price = _f(ctx["evidence"], "price")

    summary = _build_summary(
        sym,
        trend["label"],
        volume["label"],
        rpos["zone"],
        lower_area,
        upper_area,
    )
    if ctx_note:
        summary = f"{summary} {ctx_note}"

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "summary": summary,
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
        "watch_next": _watch_next(trend["label"], lower_area, upper_area, ctx_price),
        "not_financial_advice": True,
        "candle_count": len(rows),
        "window_hours": round(len(rows) * _hours_per_candle(timeframe), 1),
        "wave_analysis": build_wave_analysis(
            wave_candles if wave_candles is not None else raw_candles,
            timeframe,
            higher_tf_candles,
        ),
    }
