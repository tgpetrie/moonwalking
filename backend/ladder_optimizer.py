"""Adaptive weights for the three-rung reload ladder.

Pure and deterministic: no network, no disk, no clock.

``optimize_reload_ladder`` places three rungs at the 0.382, 0.50 and 0.618
depths of a support box and splits the freed USDC across them. With enough
daily history it measures how deep lower wicks have pushed below body support
before reversing and tilts the split: toward the shallow rung when deep wicks
are rare, toward the deep rung when they are common. The tilt is a rule of
thumb and has not been tested against outcomes.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["optimize_reload_ladder", "measure_wick_penetration", "DEFAULT_WEIGHTS", "RUNG_DEPTHS"]

RUNG_DEPTHS = (0.382, 0.5, 0.618)
DEFAULT_WEIGHTS = (0.40, 0.35, 0.25)
FLAT_WEIGHTS = (1 / 3, 1 / 3, 1 / 3)
DEFAULT_FILL_PROBABILITIES = (0.70, 0.50, 0.30)
MIN_WEIGHT = 0.15
MIN_EVENTS = 8
BOX_BARS = 20
SWING_BARS = 3
# Share of wick events reaching the deep rung at which the default split is kept.
NEUTRAL_DEEP_SHARE = DEFAULT_FILL_PROBABILITIES[2]
TILT_STRENGTH = 0.5
PROBABILITY_BOUNDS = (0.05, 0.95)


def _positive(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) and out > 0 else None


def _bars(candles: Any) -> list[tuple[float, float, float, float, float]]:
    by_ts = {}
    for bar in candles or []:
        if not isinstance(bar, (list, tuple)) or len(bar) < 5:
            continue
        try:
            ts, low, high, open_, close = (float(bar[i]) for i in range(5))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (ts, low, high, open_, close)):
            continue
        if low <= 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            continue
        by_ts[ts] = (ts, low, high, open_, close)
    return [by_ts[ts] for ts in sorted(by_ts)]


def measure_wick_penetration(daily_candles: Any) -> dict[str, Any]:
    """How deep swing-low wicks pushed below body support, as a share of the box.

    For each swing low (a low strictly under the three bars either side), the
    box is the prior 20 bars: its floor is the lowest candle body and its top
    the highest high. Depth is how far the low went under the floor divided by
    the box height. Looking at the bars after a low is fine here: this measures
    past behaviour and makes no trading decision.
    """
    bars = _bars(daily_candles)
    depths = []
    for i in range(BOX_BARS, len(bars) - SWING_BARS):
        low = bars[i][1]
        neighbours = bars[i - SWING_BARS:i] + bars[i + 1:i + 1 + SWING_BARS]
        if not all(low < other[1] for other in neighbours):
            continue
        box = bars[i - BOX_BARS:i]
        floor = min(min(bar[3], bar[4]) for bar in box)
        height = max(bar[2] for bar in box) - floor
        if height <= 0 or low >= floor:
            continue
        depths.append(min((floor - low) / height, 2.0))
    shares = [
        round(sum(1 for depth in depths if depth >= level) / len(depths), 4) if depths else None
        for level in RUNG_DEPTHS
    ]
    return {
        "events": len(depths),
        "enough_history": len(depths) >= MIN_EVENTS,
        "touch_share_by_rung": shares,
        "median_depth": round(sorted(depths)[len(depths) // 2], 4) if depths else None,
        "bars": len(bars),
    }


def _clamped_weights(raw: list[float]) -> list[float]:
    """Each weight at least ``MIN_WEIGHT`` and the three summing to 1."""
    weights = [max(MIN_WEIGHT, value) for value in raw]
    excess = sum(weights) - 1.0
    room = [value - MIN_WEIGHT for value in weights]
    if excess > 0 and sum(room) > 0:
        weights = [value - excess * r / sum(room) for value, r in zip(weights, room)]
    total = sum(weights)
    return [value / total for value in weights]


def optimize_reload_ladder(
    support_low: float,
    support_high: float,
    current_price: float,
    freed_usdc: float,
    *,
    daily_candles: Any = None,
    spread_bps: float = 15.0,
) -> dict[str, Any]:
    """Three reload rungs with history-adapted weights and spread-aware coin counts.

    Rungs sit 38.2%, 50% and 61.8% of the way down from ``support_high`` to
    ``support_low`` and never above ``current_price``. A buy is assumed to pay
    half of ``spread_bps`` over the rung price. ``net_extra_coins_vs_flat_weights``
    compares the coins bought if every rung fills against an equal three-way
    split; ``expected_extra_coins_vs_flat_weights`` weights each rung by its
    fill probability. Fill probabilities come from past wick depths when there
    are at least eight swing-low events, else from fixed defaults.
    """
    low, high, price, usdc = map(_positive, (support_low, support_high, current_price, freed_usdc))
    if None in (low, high, price, usdc):
        raise ValueError("support_low, support_high, current_price and freed_usdc must be positive numbers")
    if low >= high:
        raise ValueError("support_low must be below support_high")
    try:
        spread = float(spread_bps)
    except (TypeError, ValueError) as exc:
        raise ValueError("spread_bps must be a number") from exc
    if isinstance(spread_bps, bool) or not math.isfinite(spread) or not 0 <= spread < 10_000:
        raise ValueError("spread_bps must be from 0 to under 10000")

    history = measure_wick_penetration(daily_candles)
    if history["enough_history"]:
        shares = history["touch_share_by_rung"]
        tilt = (shares[2] - NEUTRAL_DEEP_SHARE) * TILT_STRENGTH
        weights = _clamped_weights([DEFAULT_WEIGHTS[0] - tilt, DEFAULT_WEIGHTS[1], DEFAULT_WEIGHTS[2] + tilt])
        probabilities = [min(max(share, PROBABILITY_BOUNDS[0]), PROBABILITY_BOUNDS[1]) for share in shares]
        regime = "deep_wick" if tilt > 0.02 else "fast_rebound" if tilt < -0.02 else "neutral"
    else:
        weights, probabilities, regime = list(DEFAULT_WEIGHTS), list(DEFAULT_FILL_PROBABILITIES), "default"

    cost = 1.0 + spread / 20_000.0  # half the spread is paid on a buy
    prices = [min(price, high - depth * (high - low)) for depth in RUNG_DEPTHS]
    net_prices = [value * cost for value in prices]

    def coins(split, chance=(1.0, 1.0, 1.0)) -> float:
        return sum(usdc * w / net * p for w, net, p in zip(split, net_prices, chance))

    rungs = [
        {
            "index": n + 1,
            "depth": depth,
            "price": round(prices[n], 10),
            "net_fill_price": round(net_prices[n], 10),
            "weight": round(weights[n], 6),
            "usdc_allocation": round(usdc * weights[n], 2),
            "projected_coins": round(usdc * weights[n] / net_prices[n], 8),
            "fill_probability": round(probabilities[n], 4),
        }
        for n, depth in enumerate(RUNG_DEPTHS)
    ]
    return {
        "rungs": rungs,
        "weights": [rung["weight"] for rung in rungs],
        "expected_fill_probability_by_rung": [rung["fill_probability"] for rung in rungs],
        "projected_coins_if_all_fill": round(coins(weights), 8),
        "expected_coins": round(coins(weights, probabilities), 8),
        "net_extra_coins_vs_flat_weights": round(coins(weights) - coins(FLAT_WEIGHTS), 8),
        "expected_extra_coins_vs_flat_weights": round(
            coins(weights, probabilities) - coins(FLAT_WEIGHTS, probabilities), 8
        ),
        "regime": regime,
        "history": history,
        "spread_bps": spread,
        "freed_usdc": usdc,
        "outcome_validated": False,
    }
