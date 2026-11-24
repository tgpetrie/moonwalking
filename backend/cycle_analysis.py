"""Multi-timeframe cycle maths behind ``chart_structure.multi_year_context``.

Pure and deterministic; this module does no network or disk I/O. Every
function takes daily candles as ascending ``(ts, low, high, open, close,
volume)`` rows and returns plain dictionaries.

- ``momentum_stack`` resamples the daily series to closed weekly and monthly
  bars and reads Wilder RSI regimes, weekly Stochastic RSI, MACD signals, the
  monthly bear-cycle streak and the weekly SMA ladder.
- ``fib_structure`` anchors the cycle range with single-bar flash wicks
  filtered out, then builds the macro retracement grid, the secondary
  (Wave X) extension grid, the zones where the two grids overlap and the
  two-tier target sets.
- ``daily_structure`` and ``corrective_structure`` describe the recent daily
  swings (confirmation pivot, structural low) and the multi-year corrective
  shape (three-leg zigzag or five-leg channel).

Everything here is descriptive. None of it is outcome-validated.
"""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import datetime, timezone
from statistics import median
from typing import Any

__all__ = [
    "CYCLE_WINDOW_DAYS",
    "RETRACEMENT_RATIOS",
    "EXTENSION_RATIOS",
    "weekly_bars",
    "monthly_bars",
    "sma",
    "wilder_rsi",
    "stoch_rsi",
    "macd",
    "rsi_regime",
    "momentum_stack",
    "flash_filtered_extremes",
    "fib_structure",
    "daily_structure",
    "corrective_structure",
]

Row = tuple[float, float, float, float, float, float]
DAY = 86400

# The cycle range, grids and structure are read from this trailing window.
# Indicators warm up on every bar supplied, so a longer history only makes the
# weekly and monthly reads steadier.
CYCLE_WINDOW_DAYS = 1096

RSI_PERIOD = 14
RSI_OVERSOLD_MAX = 40.0
RSI_EXPANSION_MIN = 60.0
RSI_BULL_SUPPORT = (38.0, 44.0)
# (long average length, bars its slope is measured over) per timeframe.
TREND_SMA = {"1d": (100, 10), "1w": (30, 4), "1m": (10, 2)}

STOCH_RSI = (14, 14, 3, 3)
STOCH_OVERSOLD = 25.0
STOCH_OVERBOUGHT = 75.0

MACD_PERIODS = (12, 26, 9)
# A daily "kiss": the MACD line sits within this share of the largest recent
# histogram bar from its signal line while curling up from below.
MACD_KISS_TOLERANCE = 0.15
MACD_KISS_LOOKBACK = 60

MONTHLY_EXHAUSTION_STREAK = 18
WEEKLY_SMA_PERIODS = (50, 100, 200)

# Weekly bullish divergence: two lows at least DIVERGENCE_MIN_SEPARATION weeks
# apart with a real bounce between them.
DIVERGENCE_RECENT = 6
DIVERGENCE_LOOKBACK = 40
DIVERGENCE_MIN_SEPARATION = 4
DIVERGENCE_MIN_BOUNCE = 0.15
DIVERGENCE_RETEST_TOLERANCE = 0.05
DIVERGENCE_MIN_RSI_GAIN = 1.0

RETRACEMENT_RATIOS = (0.236, 0.309, 0.382, 0.5, 0.618, 0.702, 0.786, 0.886)
EXTENSION_RATIOS = (1.272, 1.618, 2.618, 3.618, 4.236)
CLUSTER_TOLERANCE = 0.06
ROLLOVER_RATIOS = (0.618, 0.702, 0.786)
FULL_EXTENSION_RATIOS = (1.618, 2.618, 3.618, 4.236)

FLASH_WICK_MULTIPLE = 3.5
FLASH_WICK_MIN_WEEKS = 8
MIN_MACRO_DRAWDOWN = 0.20  # a smaller pullback is not a macro drawdown
MIN_WAVE_X_REBOUND = 0.25  # the counter-rally that separates two legs down

STRUCTURE_LOOKBACK_DAYS = 180
BREAKOUT_RECENT_DAYS = 30
DOUBLE_BOTTOM_TOLERANCE = 0.08
DOUBLE_BOTTOM_MIN_GAP_DAYS = 20
STOP_BUFFER = 0.02

BASE_ZONE_WIDTH = 0.30  # the historic base is its low plus this much
BASE_OVERTHROW = 0.15  # a wick this far under the base still counts as a test
CHANNEL_OVERTHROW = 0.12
CHANNEL_NEAR = 0.10


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _merge(start: float, bars: list[Row]) -> Row:
    return (
        float(start),
        min(b[1] for b in bars),
        max(b[2] for b in bars),
        bars[0][3],
        bars[-1][4],
        sum(b[5] for b in bars),
    )


# ─── resampling ───────────────────────────────────────────────────────────────


def _complete_period(start: int, length: int, bars: list[Row]) -> bool:
    return len(bars) == length and all(
        bar[0] == start + offset * DAY for offset, bar in enumerate(bars)
    )


def weekly_bars(rows: list[Row]) -> list[Row]:
    """Aggregate exactly seven closed daily candles per Monday–Sunday UTC week."""
    groups: dict[int, list[Row]] = {}
    for row in rows:
        start = int((row[0] + 3 * DAY) // (7 * DAY)) * 7 * DAY - 3 * DAY
        groups.setdefault(start, []).append(row)
    return [
        _merge(start, bars)
        for start, bars in sorted(groups.items())
        if _complete_period(start, 7, bars)
    ]


def monthly_bars(rows: list[Row]) -> list[Row]:
    """Aggregate only UTC months with every closed daily candle present."""
    groups: dict[tuple[int, int], list[Row]] = {}
    for row in rows:
        stamp = datetime.fromtimestamp(row[0], timezone.utc)
        groups.setdefault((stamp.year, stamp.month), []).append(row)
    out = []
    for (year, month), bars in sorted(groups.items()):
        start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
        if _complete_period(start, monthrange(year, month)[1], bars):
            out.append(_merge(start, bars))
    return out


def _contiguous_tail(rows: list[Row], interval) -> list[Row]:
    """Keep missing periods from counting as neighboring indicator bars."""
    for i in range(len(rows) - 1, 0, -1):
        if rows[i][0] - rows[i - 1][0] != interval(rows[i - 1][0]):
            return rows[i:]
    return rows


def _month_seconds(timestamp: float) -> int:
    stamp = datetime.fromtimestamp(timestamp, timezone.utc)
    return monthrange(stamp.year, stamp.month)[1] * DAY


# ─── indicators ───────────────────────────────────────────────────────────────


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= period:
            total -= values[i - period]
        if i >= period - 1:
            out[i] = total / period
    return out


def _sma_optional(values: list[float | None], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        if all(v is not None for v in window):
            out[i] = sum(window) / period  # type: ignore[arg-type]
    return out


def wilder_rsi(closes: list[float], period: int = RSI_PERIOD) -> list[float | None]:
    """Wilder's RSI. ``None`` until ``period`` changes have been seen."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gain = loss = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gain += max(change, 0.0)
        loss += max(-change, 0.0)
    gain, loss = gain / period, loss / period

    def value() -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    out[period] = value()
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = (gain * (period - 1) + max(change, 0.0)) / period
        loss = (loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = value()
    return out


def stoch_rsi(
    closes: list[float],
    rsi_period: int = STOCH_RSI[0],
    stoch_period: int = STOCH_RSI[1],
    k_smooth: int = STOCH_RSI[2],
    d_smooth: int = STOCH_RSI[3],
) -> tuple[list[float | None], list[float | None]]:
    """Stochastic RSI ``%K`` and ``%D`` on a 0–100 scale."""
    rsi = wilder_rsi(closes, rsi_period)
    raw: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        window = rsi[max(0, i - stoch_period + 1) : i + 1]
        if len(window) < stoch_period or any(v is None for v in window):
            continue
        low, high = min(window), max(window)  # type: ignore[type-var]
        # A flat RSI window has no position inside its own range.
        raw[i] = 50.0 if high == low else (rsi[i] - low) / (high - low) * 100.0  # type: ignore[operator]
    k = _sma_optional(raw, k_smooth)
    return k, _sma_optional(k, d_smooth)


def _ema_seeded(values: list[float | None], period: int) -> list[float | None]:
    """EMA seeded with the SMA of the first ``period`` usable values."""
    out: list[float | None] = [None] * len(values)
    start = next((i for i, v in enumerate(values) if v is not None), None)
    if start is None or len(values) - start < period:
        return out
    seed = values[start : start + period]
    if any(v is None for v in seed):
        return out
    level = sum(seed) / period  # type: ignore[arg-type]
    out[start + period - 1] = level
    alpha = 2.0 / (period + 1.0)
    for i in range(start + period, len(values)):
        if values[i] is None:
            return out
        level += alpha * (values[i] - level)  # type: ignore[operator]
        out[i] = level
    return out


def macd(
    closes: list[float],
    fast: int = MACD_PERIODS[0],
    slow: int = MACD_PERIODS[1],
    signal: int = MACD_PERIODS[2],
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD line, signal line and histogram. ``None`` while warming up."""
    values: list[float | None] = list(closes)
    quick, slower = _ema_seeded(values, fast), _ema_seeded(values, slow)
    line = [
        None if a is None or b is None else a - b for a, b in zip(quick, slower)
    ]
    signal_line = _ema_seeded(line, signal)
    hist = [
        None if a is None or b is None else a - b for a, b in zip(line, signal_line)
    ]
    return line, signal_line, hist


def rsi_regime(value: float | None, uptrend: bool = False) -> dict[str, Any]:
    """Name the RSI regime. 40 and 60 themselves belong to no-man's-land."""
    if value is None:
        return {"regime": "unavailable", "near_bull_support": False}
    if value < RSI_OVERSOLD_MAX:
        regime = "oversold_compression"
    elif value > RSI_EXPANSION_MIN:
        regime = "growth_expansion"
    else:
        regime = "no_mans_land"
    near = bool(uptrend and RSI_BULL_SUPPORT[0] <= value <= RSI_BULL_SUPPORT[1])
    return {"regime": regime, "near_bull_support": near}


def _trend(closes: list[float], timeframe: str) -> str:
    """``up`` or ``down`` from the slope of the timeframe's long average."""
    period, slope_bars = TREND_SMA[timeframe]
    average = sma(closes, period)
    if len(closes) < period + slope_bars or average[-1 - slope_bars] is None:
        return "unknown"
    now, before = average[-1], average[-1 - slope_bars]
    if now > before:  # type: ignore[operator]
        return "up"
    return "down" if now < before else "flat"  # type: ignore[operator]


def _rsi_block(closes: list[float], timeframe: str) -> dict[str, Any]:
    series = wilder_rsi(closes)
    value = series[-1] if series else None
    previous = series[-2] if len(series) >= 2 else None
    trend = _trend(closes, timeframe)
    period, _ = TREND_SMA[timeframe]
    return {
        "timeframe": timeframe,
        "value": _round(value),
        "previous": _round(previous),
        **rsi_regime(value, uptrend=trend == "up"),
        "trend": trend,
        "trend_basis": f"slope of the {period}-bar average",
        "bars": len(closes),
    }


def _stoch_block(closes: list[float]) -> dict[str, Any]:
    k, d = stoch_rsi(closes)
    now_k = k[-1] if k else None
    now_d = d[-1] if d else None
    if now_k is None or now_d is None:
        return {
            "available": False,
            "reason": "needs_more_weekly_history",
            "weekly_stoch_rsi_k": None,
            "weekly_stoch_rsi_d": None,
            "direction": None,
            "bars": len(closes),
        }
    previous = k[-2] if len(k) >= 2 else None
    if now_k < STOCH_OVERSOLD and now_k > now_d:
        direction = "oversold_turn_up"
    elif now_k > STOCH_OVERBOUGHT and now_k < now_d:
        direction = "overbought_turn_down"
    elif now_k > now_d or (
        now_k == now_d and previous is not None and now_k >= previous
    ):
        direction = "bullish_expansion"
    else:
        direction = "high_to_low_drift"
    return {
        "available": True,
        "weekly_stoch_rsi_k": _round(now_k),
        "weekly_stoch_rsi_d": _round(now_d),
        "previous_k": _round(previous),
        "direction": direction,
        "bars": len(closes),
    }


def _macd_block(closes: list[float]) -> dict[str, Any]:
    line, signal_line, hist = macd(closes)
    return {
        "macd": line[-1] if line else None,
        "signal": signal_line[-1] if signal_line else None,
        "histogram": hist[-1] if hist else None,
        "previous_histogram": hist[-2] if len(hist) >= 2 else None,
        "bars": len(closes),
    }


def _daily_kiss(closes: list[float]) -> bool:
    line, _signal, hist = macd(closes)
    if len(hist) < 3 or hist[-1] is None or hist[-2] is None:
        return False
    if line[-1] is None or line[-2] is None:
        return False
    recent = [abs(h) for h in hist[-MACD_KISS_LOOKBACK:] if h is not None]
    scale = max(recent, default=0.0)
    if scale <= 0:
        return False
    return (
        hist[-2] < hist[-1] <= 0  # closes the gap without crossing above
        and line[-1] > line[-2]  # while curling up
        and abs(hist[-1]) <= MACD_KISS_TOLERANCE * scale
    )


def _weekly_cross(closes: list[float]) -> dict[str, Any]:
    _line, _signal, hist = macd(closes)
    usable = [h for h in hist if h is not None]
    above = bool(usable) and usable[-1] > 0
    crossed = len(usable) >= 2 and usable[-1] > 0 >= usable[-2]
    since = None
    if above:
        since = 0
        for value in reversed(usable[:-1]):
            if value <= 0:
                break
            since += 1
        else:
            since = None  # above the signal for the whole warmed-up history
    return {
        "weekly_macd_bullish_cross": bool(crossed),
        "weekly_macd_above_signal": above,
        "weeks_since_weekly_bullish_cross": since,
    }


def _near(series: list[float | None], index: int) -> float | None:
    window = [v for v in series[max(0, index - 1) : index + 2] if v is not None]
    return min(window) if window else None


def _bullish_divergence(bars: list[Row], timeframe: str = "1w") -> dict[str, Any] | None:
    """A lower or retested low on a higher momentum low, or ``None``."""
    count = len(bars)
    if count < RSI_PERIOD + DIVERGENCE_MIN_SEPARATION + DIVERGENCE_RECENT:
        return None
    lows = [w[1] for w in bars]
    closes = [w[4] for w in bars]
    rsi = wilder_rsi(closes)
    _line, _signal, hist = macd(closes)
    second = min(range(count - DIVERGENCE_RECENT, count), key=lambda i: (lows[i], -i))
    start = max(0, second - DIVERGENCE_LOOKBACK)
    end = second - DIVERGENCE_MIN_SEPARATION
    if end <= start:
        return None
    first = min(range(start, end + 1), key=lambda i: (lows[i], -i))
    # The earlier low has to be a swing low, not a point on the way down.
    if lows[first] > min(lows[max(0, first - 2) : first + 3]):
        return None
    bounce = max(w[2] for w in bars[first + 1 : second])
    if bounce < max(lows[first], lows[second]) * (1.0 + DIVERGENCE_MIN_BOUNCE):
        return None
    if lows[second] > lows[first] * (1.0 + DIVERGENCE_RETEST_TOLERANCE):
        return None
    rsi_first, rsi_second = _near(rsi, first), _near(rsi, second)
    hist_first, hist_second = _near(hist, first), _near(hist, second)
    by_rsi = (
        rsi_first is not None
        and rsi_second is not None
        and rsi_second >= rsi_first + DIVERGENCE_MIN_RSI_GAIN
    )
    by_hist = (
        hist_first is not None
        and hist_second is not None
        and hist_first < 0
        and hist_second > hist_first
    )
    if not (by_rsi or by_hist):
        return None
    return {
        "timeframe": timeframe,
        "kind": "lower_low" if lows[second] < lows[first] else "double_bottom_retest",
        "first_low": {"price": lows[first], "timestamp": bars[first][0]},
        "second_low": {"price": lows[second], "timestamp": bars[second][0]},
        "price_change_pct": _round((lows[second] / lows[first] - 1.0) * 100.0),
        "rsi": {"first": _round(rsi_first), "second": _round(rsi_second)},
        "macd_histogram": {"first": hist_first, "second": hist_second},
        "confirmed_by": [
            name for name, hit in (("rsi", by_rsi), ("macd_histogram", by_hist)) if hit
        ],
    }


def _monthly_exhaustion(months: list[Row]) -> dict[str, Any]:
    closes = [m[4] for m in months]
    rsi = wilder_rsi(closes)
    line, _signal, hist = macd(closes)
    streak = 0
    for i in range(len(months) - 1, -1, -1):
        month_rsi, month_macd = rsi[i], line[i]
        if month_rsi is None and month_macd is None:
            break
        bearish = (month_rsi is not None and month_rsi < 50) or (
            month_macd is not None and month_macd < 0
        )
        if not bearish:
            break
        streak += 1
    last = hist[-1] if hist else None
    prior = hist[-2] if len(hist) >= 2 else None
    shrinking = None if last is None or prior is None else bool(prior < last < 0)
    out: dict[str, Any] = {
        "available": bool(months) and rsi[-1] is not None,
        "monthly_bearish_streak": streak,
        "streak_threshold": MONTHLY_EXHAUSTION_STREAK,
        "multi_year_oversold_exhaustion": bool(
            streak >= MONTHLY_EXHAUSTION_STREAK and shrinking
        ),
        "histogram_shrinking": shrinking,
        "monthly_rsi": _round(rsi[-1] if rsi else None),
        "monthly_macd": line[-1] if line else None,
        "monthly_macd_histogram": last,
        "previous_monthly_macd_histogram": prior,
        "monthly_bars": len(months),
    }
    if not out["available"]:
        out["reason"] = "needs_more_monthly_history"
    elif shrinking is None:
        out["reason"] = "monthly_macd_histogram_warming_up"
    return out


def _sma_ladder(weeks: list[Row], price: float | None) -> dict[str, Any]:
    closes = [w[4] for w in weeks]
    levels, overhead, reclaimed = [], [], []
    out: dict[str, Any] = {"price": price, "weekly_bars": len(weeks)}
    for period in WEEKLY_SMA_PERIODS:
        key = f"sma_{period}w"
        series = sma(closes, period)
        value = series[-1] if series else None
        role = None
        if value is not None and price is not None:
            role = "resistance" if value > price else "support"
            (overhead if role == "resistance" else reclaimed).append(key)
        out[key] = value
        levels.append(
            {
                "key": key,
                "period": period,
                "value": value,
                "available": value is not None,
                "role": role,
                "distance_pct": _round((value / price - 1.0) * 100.0)
                if value is not None and price
                else None,
                "bars_needed": period,
            }
        )
    out.update(
        levels=levels, overhead_resistance=overhead, reclaimed_support=reclaimed
    )
    return out


def momentum_stack(rows: list[Row]) -> dict[str, Any]:
    """Momentum from consecutive closed bars, with gaps treated as warmup."""
    weeks = _contiguous_tail(weekly_bars(rows), lambda _: 7 * DAY)
    months = _contiguous_tail(monthly_bars(rows), _month_seconds)
    rows = _contiguous_tail(rows, lambda _: DAY)
    daily_closes = [r[4] for r in rows]
    weekly_closes = [w[4] for w in weeks]
    monthly_closes = [m[4] for m in months]
    divergence = _bullish_divergence(weeks)
    daily_divergence = _bullish_divergence(rows, "1d")
    return {
        "rsi_regimes": {
            "1d": _rsi_block(daily_closes, "1d"),
            "1w": _rsi_block(weekly_closes, "1w"),
            "1m": _rsi_block(monthly_closes, "1m"),
        },
        "weekly_stoch_rsi": _stoch_block(weekly_closes),
        "monthly_cycle_exhaustion": _monthly_exhaustion(months),
        "macd_signals": {
            "daily_macd_kiss": _daily_kiss(daily_closes),
            "daily_bullish_divergence": daily_divergence is not None,
            "daily_divergence": daily_divergence,
            **_weekly_cross(weekly_closes),
            "macro_bullish_divergence": divergence is not None,
            "divergence": divergence,
            "1d": _macd_block(daily_closes),
            "1w": _macd_block(weekly_closes),
            "1m": _macd_block(monthly_closes),
        },
        "weekly_sma_ladder": _sma_ladder(weeks, rows[-1][4] if rows else None),
        "timeframe_bars": {"1d": len(rows), "1w": len(weeks), "1m": len(months)},
    }


# ─── flash-wick filter and Fibonacci grids ────────────────────────────────────


def flash_filtered_extremes(
    rows: list[Row],
) -> tuple[list[float], list[float], dict[str, Any]]:
    """Lows and highs with single-bar flash wicks cut back to the candle body.

    A wick counts when it is longer than ``FLASH_WICK_MULTIPLE`` times the
    median weekly range (both measured as log ratios, so the test does not
    depend on price level), the bar closes back at the body, and neither
    neighbouring bar trades into the outer half of the wick.
    """
    lows, highs = [r[1] for r in rows], [r[2] for r in rows]
    weeks = weekly_bars(rows)
    info: dict[str, Any] = {
        "threshold_multiple": FLASH_WICK_MULTIPLE,
        "median_weekly_range_pct": None,
        "filtered": [],
        "method": (
            "a single daily wick longer than 3.5x the median weekly range that "
            "closes back at the candle body and is not revisited by the bars "
            "either side; the anchor uses the body instead"
        ),
    }
    if len(weeks) < FLASH_WICK_MIN_WEEKS:
        return lows, highs, info
    typical = median(math.log(w[2] / w[1]) for w in weeks)
    info["median_weekly_range_pct"] = _round((math.exp(typical) - 1.0) * 100.0)
    if typical <= 0:
        return lows, highs, info
    limit = FLASH_WICK_MULTIPLE * typical
    events = []
    for i in range(1, len(rows) - 1):
        ts, low, high, open_, close, _volume = rows[i]
        beside = (rows[i - 1], rows[i + 1])
        if beside[0][0] != ts - DAY or beside[1][0] != ts + DAY:
            continue  # can't confirm isolation at either boundary or across a gap
        body_low, body_high = min(open_, close), max(open_, close)
        down = math.log(body_low / low)
        if down > limit and all(n[1] > math.sqrt(low * body_low) for n in beside):
            lows[i] = body_low
            events.append(("low", ts, low, body_low, down / typical))
        up = math.log(high / body_high)
        if up > limit and all(n[2] < math.sqrt(high * body_high) for n in beside):
            highs[i] = body_high
            events.append(("high", ts, high, body_high, up / typical))
    events.sort(key=lambda event: -event[4])
    info["filtered"] = [
        {
            "side": side,
            "timestamp": ts,
            "raw_price": raw,
            "filtered_price": kept,
            "wick_multiple": _round(multiple),
        }
        for side, ts, raw, kept, multiple in events[:6]
    ]
    return lows, highs, info


def _grid(low: float, high: float, ratios: tuple[float, ...]) -> dict[str, float]:
    """Log-scale levels ``ratio`` of the way from ``low`` up to ``high``."""
    return {str(ratio): low * (high / low) ** ratio for ratio in ratios}


def _wave_x(
    lows: list[float], highs: list[float], rows: list[Row], top: int, bottom: int
) -> dict[str, Any] | None:
    """The largest counter-rally between the cycle high and the drawdown low."""
    best: tuple[float, int, int] | None = None
    floor_index = None
    for j in range(top + 1, bottom):
        if floor_index is not None:
            rebound = highs[j] / lows[floor_index]
            if highs[j] < highs[top] and (best is None or rebound > best[0]):
                best = (rebound, j, floor_index)
        if floor_index is None or lows[j] < lows[floor_index]:
            floor_index = j
    if best is None or best[0] < 1.0 + MIN_WAVE_X_REBOUND:
        return None
    rebound, peak, floor_index = best
    return {
        "price": highs[peak],
        "timestamp": rows[peak][0],
        "kind": "wave_x",
        "rebound_pct": _round((rebound - 1.0) * 100.0),
        "first_leg_low": {"price": lows[floor_index], "timestamp": rows[floor_index][0]},
    }


def fib_structure(rows: list[Row]) -> dict[str, Any]:
    """Cycle anchors, both Fibonacci grids, their overlaps and the target tiers.

    ``rows`` is the analysis window. ``_index`` (positions in it) and ``_rows``
    (the same bars with flash wicks cut back) are for the caller and are
    removed before serialising.
    """
    lows, highs, wick_info = flash_filtered_extremes(rows)
    low_i = min(range(len(rows)), key=lambda i: lows[i])
    high_i = max(range(len(rows)), key=lambda i: highs[i])
    raw_low_i = min(range(len(rows)), key=lambda i: rows[i][1])
    raw_high_i = max(range(len(rows)), key=lambda i: rows[i][2])
    low, high = lows[low_i], highs[high_i]
    price = rows[-1][4]
    wick_info["applied"] = bool(
        rows[raw_low_i][1] != low or rows[raw_high_i][2] != high
    )
    out: dict[str, Any] = {
        "cycle_low": {"price": low, "timestamp": rows[low_i][0]},
        "cycle_high": {"price": high, "timestamp": rows[high_i][0]},
        "raw_cycle_low": {"price": rows[raw_low_i][1], "timestamp": rows[raw_low_i][0]},
        "raw_cycle_high": {
            "price": rows[raw_high_i][2],
            "timestamp": rows[raw_high_i][0],
        },
        "flash_wick_filter": wick_info,
        "macro_drawdown": {"available": False, "reason": "cycle_high_is_latest_bar"},
        "drawdown_log_retracements": {},
        "secondary_wave_x_high": None,
        "secondary_log_extensions": {},
        "fib_confluence_clusters": [],
        "rollover_target_box": {"available": False, "reason": "no_macro_drawdown"},
        "full_extension_targets": {"available": False, "reason": "no_macro_drawdown"},
        "_index": {"low": low_i, "high": high_i, "drawdown_low": None},
        "_rows": [
            (r[0], lows[i], highs[i], r[3], r[4], r[5]) for i, r in enumerate(rows)
        ],
    }
    if high_i >= len(rows) - 1:
        return out
    bottom = min(range(high_i + 1, len(rows)), key=lambda i: lows[i])
    floor = lows[bottom]
    depth = floor / high - 1.0
    out["_index"]["drawdown_low"] = bottom
    drawdown = {
        "available": depth <= -MIN_MACRO_DRAWDOWN,
        "high": dict(out["cycle_high"]),
        "low": {"price": floor, "timestamp": rows[bottom][0]},
        "depth_pct": _round(depth * 100.0),
        "recovered_pct": _round(
            math.log(price / floor) / math.log(high / floor) * 100.0
        )
        if high > floor and price > 0
        else None,
    }
    out["macro_drawdown"] = drawdown
    if not drawdown["available"]:
        drawdown["reason"] = "drawdown_under_20_pct"
        return out

    retracements = _grid(floor, high, RETRACEMENT_RATIOS)
    out["drawdown_log_retracements"] = retracements
    box_levels = {str(r): retracements[str(r)] for r in ROLLOVER_RATIOS}
    box = {
        "available": True,
        "label": "Conservative / High-Probability Rollover Zone",
        "low": box_levels[str(ROLLOVER_RATIOS[0])],
        "high": box_levels[str(ROLLOVER_RATIOS[-1])],
        "levels": box_levels,
        "basis": "log-scale 0.618, 0.702 and 0.786 retracement of the macro drawdown",
        "extension_confluence": [],
        "price_position": "below"
        if price < box_levels[str(ROLLOVER_RATIOS[0])]
        else "above"
        if price > box_levels[str(ROLLOVER_RATIOS[-1])]
        else "inside",
    }
    out["rollover_target_box"] = box

    def near_box(level: float) -> bool:
        return (
            box["low"] / (1.0 + CLUSTER_TOLERANCE)
            <= level
            <= box["high"] * (1.0 + CLUSTER_TOLERANCE)
        )

    # The local base: from the drawdown low to the highest price since it.
    if bottom < len(rows) - 3:
        base_high = max(highs[bottom + 1 :])
        if base_high > floor:
            level = floor * (base_high / floor) ** 1.618
            box["local_base_extension"] = {
                "ratio": 1.618,
                "price": level,
                "base_high": base_high,
                "in_box": near_box(level),
            }
            if near_box(level):
                box["extension_confluence"].append(
                    {"source": "local_base", "ratio": 1.618, "price": level}
                )

    wave_x = _wave_x(lows, highs, rows, high_i, bottom)
    out["secondary_wave_x_high"] = wave_x
    if wave_x is None:
        out["full_extension_targets"] = {
            "available": False,
            "reason": "no_secondary_range",
        }
        return out
    extensions = _grid(floor, wave_x["price"], EXTENSION_RATIOS)
    out["secondary_log_extensions"] = extensions
    if near_box(extensions["1.618"]):
        box["extension_confluence"].append(
            {"source": "secondary_range", "ratio": 1.618, "price": extensions["1.618"]}
        )

    clusters = []
    for r in RETRACEMENT_RATIOS:
        for e in EXTENSION_RATIOS:
            a, b = retracements[str(r)], extensions[str(e)]
            spread = max(a, b) / min(a, b) - 1.0
            if spread > CLUSTER_TOLERANCE:
                continue
            mid = math.sqrt(a * b)
            clusters.append(
                {
                    "low": min(a, b),
                    "high": max(a, b),
                    "mid": mid,
                    "retracement_ratio": r,
                    "retracement_price": a,
                    "extension_ratio": e,
                    "extension_price": b,
                    "spread_pct": _round(spread * 100.0),
                    "score": _round(1.0 - spread / CLUSTER_TOLERANCE, 3),
                    "conviction": "high",
                    "position": "above_price" if min(a, b) > price else "below_price"
                    if max(a, b) < price
                    else "at_price",
                    "distance_pct": _round((mid / price - 1.0) * 100.0),
                }
            )
    clusters.sort(key=lambda c: c["mid"])
    out["fib_confluence_clusters"] = clusters
    box["clusters"] = [
        c for c in clusters if c["high"] >= box["low"] and c["low"] <= box["high"]
    ]
    clustered = {c["extension_ratio"] for c in clusters}
    out["full_extension_targets"] = {
        "available": True,
        "label": "Full Alt-Season Extension Confluence",
        "levels": {str(e): extensions[str(e)] for e in FULL_EXTENSION_RATIOS},
        "targets": [
            {
                "ratio": e,
                "price": extensions[str(e)],
                "confluence": e in clustered,
                "distance_pct": _round((extensions[str(e)] / price - 1.0) * 100.0),
            }
            for e in FULL_EXTENSION_RATIOS
        ],
        "clusters": clusters,
        "basis": "log-scale extensions of the range from the drawdown low to the Wave X high",
    }
    return out


# ─── structure ────────────────────────────────────────────────────────────────


def _pivots(rows: list[Row]) -> list[Any]:
    try:
        from elliott_wave_engine import detect_pivots
    except ImportError:
        from backend.elliott_wave_engine import detect_pivots
    return detect_pivots([list(r) for r in rows])


def daily_structure(rows: list[Row]) -> dict[str, Any]:
    """The recent structural low, the swing high above price and any break of it.

    ``rows`` are the window's daily bars with flash wicks already cut back.
    """
    count = len(rows)
    price = rows[-1][4]
    start = max(0, count - STRUCTURE_LOOKBACK_DAYS)
    low_i = min(range(start, count), key=lambda i: (rows[i][1], -i))
    low = rows[low_i][1]
    pivots = _pivots(rows)
    recent = [p for p in pivots if p.index >= start]
    try:
        from chart_structure import swing_history
    except ImportError:
        from backend.chart_structure import swing_history
    floor = swing_history(
        [{"ts": p.ts, "price": p.price, "kind": p.kind} for p in recent], price
    ).get("floor")
    recent_highs = [p for p in recent if p.kind == "high"]
    out: dict[str, Any] = {
        "structural_low": {"price": low, "timestamp": rows[low_i][0]},
        "higher_low_floor": floor["points"][-1]["price"] if floor else None,
        "bars_since_structural_low": count - 1 - low_i,
        "low_confirmation_pivot": None,
        "confirmation_breakout": {"broken": False},
        "double_bottom": None,
        "final_leg_down_swings": 0,
    }
    above = [p for p in recent_highs if p.price > price]
    if above:
        pivot = above[-1]
        out["low_confirmation_pivot"] = {
            "price": pivot.price,
            "timestamp": pivot.ts,
            "kind": "wave_4_swing_high" if pivot.index < low_i else "swing_high",
            "distance_pct": _round((pivot.price / price - 1.0) * 100.0),
        }
    before_low = [p for p in recent_highs if p.index < low_i]
    if before_low:
        gate = before_low[-1]
        out["confirmation_breakout"].update(pivot_price=gate.price, pivot_timestamp=gate.ts)
        broke = next(
            (i for i in range(low_i + 1, count) if rows[i][4] > gate.price), None
        )
        if broke is not None:
            out["confirmation_breakout"] = {
                "broken": True,
                "pivot_price": gate.price,
                "pivot_timestamp": gate.ts,
                "broke_at": rows[broke][0],
                "bars_since_break": count - 1 - broke,
                "recent": rows[-1][0] - rows[broke][0] <= BREAKOUT_RECENT_DAYS * DAY,
                "holding_above": price > gate.price,
            }
        # Swing lows between the highest recent swing high and the structural
        # low: three or more is the stair-step a finishing leg usually shows.
        leg_top = max(before_low, key=lambda p: (p.price, p.index))
        out["final_leg_down_swings"] = 1 + sum(
            1 for p in pivots if p.kind == "low" and leg_top.index < p.index < low_i
        )
    earlier = [
        p
        for p in pivots
        if p.kind == "low"
        and p.index <= low_i - DOUBLE_BOTTOM_MIN_GAP_DAYS
        and abs(math.log(p.price / low)) <= math.log(1.0 + DOUBLE_BOTTOM_TOLERANCE)
        and max(r[2] for r in rows[p.index + 1 : low_i])
        >= max(p.price, low) * (1.0 + DIVERGENCE_MIN_BOUNCE)
    ]
    if earlier:
        first = earlier[-1]
        out["double_bottom"] = {
            "first": {"price": first.price, "timestamp": first.ts},
            "second": dict(out["structural_low"]),
            "gap_pct": _round((low / first.price - 1.0) * 100.0),
            "bars_apart": low_i - first.index,
        }
    return out


def corrective_structure(
    rows: list[Row], high_index: int, history_rows: list[Row] | None = None
) -> dict[str, Any]:
    """Name the multi-year corrective shape since the cycle high.

    Counts weekly swing legs after the cycle high. Two lows separated by one
    rally is a three-leg zigzag (5-3-5, or W-X-Y); three lows separated by two
    rallies is a five-leg A-B-C-D-E channel, tested against the trendline
    through the first two of those lows. ``rows`` are the window's daily bars
    with flash wicks cut back. ``history_rows`` (optional, reaching further
    back) is searched for the base the advance started from.
    """
    price = rows[-1][4]
    top_ts = rows[high_index][0]
    out: dict[str, Any] = {
        "kind": "none",
        "legs": 0,
        "swings": [],
        "historic_base": None,
        "at_historic_base": False,
        "channel": None,
        "double_bottom_retest": False,
        "testing_support": False,
    }
    # The base: the lowest low before the cycle high, on all history supplied.
    if history_rows and history_rows[0][0] < rows[0][0]:
        base_lows, _highs, _info = flash_filtered_extremes(history_rows)
        earlier = [
            (base_lows[i], r[0]) for i, r in enumerate(history_rows) if r[0] < top_ts
        ]
    else:
        earlier = [(r[1], r[0]) for r in rows if r[0] < top_ts]
    if len(earlier) >= 30:
        base_low, base_ts = min(earlier)
        zone_high = base_low * (1.0 + BASE_ZONE_WIDTH)
        out["historic_base"] = {
            "low": base_low,
            "high": zone_high,
            "timestamp": base_ts,
        }
        out["at_historic_base"] = bool(
            base_low * (1.0 - BASE_OVERTHROW) <= price <= zone_high
        )

    weeks = weekly_bars(rows)
    points: list[dict[str, Any]] = []
    for p in _pivots(weeks):
        if p.ts <= top_ts or (not points and p.kind != "low"):
            continue
        if points and points[-1]["kind"] == p.kind:
            continue
        points.append({"kind": p.kind, "price": p.price, "timestamp": p.ts})
    last_ts = points[-1]["timestamp"] if points else top_ts
    tail = [w for w in weeks if w[0] > last_ts]
    if tail and (not points or points[-1]["kind"] == "high"):
        low_week = min(tail, key=lambda w: w[1])
        points.append(
            {
                "kind": "low",
                "price": low_week[1],
                "timestamp": low_week[0],
                "forming": True,
            }
        )
    swing_lows = [p for p in points if p["kind"] == "low"]
    swing_highs = [p for p in points if p["kind"] == "high"]
    out["swings"] = points
    out["legs"] = len(points)
    if not swing_lows:
        return out
    last_low = swing_lows[-1]
    ends_on_low = points[-1]["kind"] == "low"

    if len(swing_lows) >= 3 and len(swing_highs) >= 2:
        a, c, e = swing_lows[-3], swing_lows[-2], swing_lows[-1]
        slope = math.log(c["price"] / a["price"]) / (c["timestamp"] - a["timestamp"])

        def line(ts: float) -> float:
            return a["price"] * math.exp(slope * (ts - a["timestamp"]))

        at_e, now = line(e["timestamp"]), line(rows[-1][0])
        deviation = e["price"] / at_e - 1.0
        holds = -CHANNEL_OVERTHROW <= deviation <= CHANNEL_NEAR
        out["kind"] = "abcde_channel"
        out["channel"] = {
            "lower_line_at_e": at_e,
            "lower_line_now": now,
            "e_low": e["price"],
            "e_deviation_pct": _round(deviation * 100.0),
            "overthrow": deviation < 0,
            "holds": bool(holds),
            "testing_now": bool(
                holds
                and now * (1.0 - CHANNEL_OVERTHROW)
                <= price
                <= now * (1.0 + CHANNEL_NEAR)
            ),
            "points": {"A": a, "C": c, "E": e},
        }
    elif len(swing_lows) == 2 and swing_highs:
        lower = last_low["price"] < swing_lows[0]["price"]
        out["kind"] = "wxy_zigzag" if lower else "flat_retest"
    else:
        out["kind"] = "single_leg"

    if len(swing_lows) >= 2:
        prior = min(
            swing_lows[:-1],
            key=lambda p: abs(math.log(p["price"] / last_low["price"])),
        )
        gap = last_low["price"] / prior["price"] - 1.0
        out["double_bottom_retest"] = bool(
            ends_on_low and abs(gap) <= DOUBLE_BOTTOM_TOLERANCE
        )
        out["double_bottom_gap_pct"] = _round(gap * 100.0)
    near_low = price <= last_low["price"] * (1.0 + BASE_ZONE_WIDTH)
    out["testing_support"] = bool(
        (out["channel"] or {}).get("testing_now")
        or (out["double_bottom_retest"] and near_low)
        or out["at_historic_base"]
    )
    return out
