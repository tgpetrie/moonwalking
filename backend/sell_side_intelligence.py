"""Explainable sell-side and risk-level intelligence.

The inputs are descriptive candle levels produced by :mod:`position_levels`.
This module turns those inputs into a concrete risk map without pretending the
levels are guaranteed or outcome-validated.  It never places an order.
"""

from __future__ import annotations

import math
from typing import Any


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _round_price(value: float) -> float:
    """Keep useful precision for both BTC and sub-dollar assets."""
    if value >= 1000:
        digits = 2
    elif value >= 1:
        digits = 4
    elif value >= 0.01:
        digits = 6
    else:
        digits = 8
    return round(value, digits)


def _pct(current: float, level: float) -> float:
    return round(((level / current) - 1.0) * 100.0, 2)


def _risk_band(risk_pct: float) -> str:
    if risk_pct <= 2:
        return "tight"
    if risk_pct <= 6:
        return "standard"
    return "wide"


def _top_signal(
    *,
    current_price: float,
    support: float,
    resistance: float | None,
    levels: dict[str, Any],
    signal_context: dict[str, Any],
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    range_position = _number(levels.get("range_position_pct"))
    momentum = _number(levels.get("momentum_1h_pct"))
    volume_ratio = _number(levels.get("volume_ratio"))
    primary_state = str(signal_context.get("primary_state") or "").strip()
    read_label = str(signal_context.get("read_label") or "").strip()
    direction = str(signal_context.get("direction") or "").strip().lower()
    spot_pressure = str(signal_context.get("spot_pressure") or "").strip().lower()
    alert_types = {
        str(value or "").strip().lower()
        for value in signal_context.get("alert_types") or []
    }

    if current_price <= support:
        score += 5
        reasons.append("Price is at or below the recent structural support.")
    if range_position is not None and range_position >= 85:
        score += 2
        reasons.append("Price is in the top 15% of its recent candle range.")
    if resistance and resistance > 0:
        distance = ((resistance / current_price) - 1.0) * 100.0
        if 0 <= distance <= 1.5:
            score += 1
            reasons.append("Recent resistance is less than 1.5% overhead.")
    if momentum is not None and momentum < 0:
        score += 2
        reasons.append("The latest completed hourly candle lost momentum.")
    if (
        momentum is not None
        and momentum < 0
        and volume_ratio is not None
        and volume_ratio >= 1.5
    ):
        score += 1
        reasons.append("The momentum loss arrived on above-baseline volume.")

    risk_words = " ".join([primary_state, read_label, *alert_types]).lower()
    if any(
        word in risk_words
        for word in ("reversal", "fading", "fakeout", "exhaustion", "fragile")
    ):
        score += 2
        reasons.append("The live signal layer is carrying a reversal/fading warning.")
    if direction == "down":
        score += 1
        reasons.append("The latest grouped signal direction is down.")
    if spot_pressure == "selling":
        score += 1
        reasons.append("The sampled Coinbase tape is showing spot selling pressure.")

    if current_price <= support or score >= 5:
        label, status, tone, action = (
            "Protect now",
            "high",
            "negative",
            "The level stack is under pressure. Review exposure and the stop before adding risk.",
        )
    elif score >= 3:
        label, status, tone, action = (
            "Top watch",
            "watch",
            "caution",
            "Price is near an exit decision area. Watch for rejection or an hourly close back below support.",
        )
    else:
        label, status, tone, action = (
            "No top signal",
            "clear",
            "neutral",
            "No candle-and-signal combination currently meets the top-risk watch threshold.",
        )

    if not reasons:
        reasons.append(
            "Price is not near resistance and no reversal warning is active."
        )

    return {
        "label": label,
        "status": status,
        "tone": tone,
        "score": min(10, score),
        "action": action,
        "reasons": reasons,
    }


def build_sell_plan(
    *,
    product_id: str,
    current_price: Any,
    levels: dict[str, Any] | None,
    signal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an explainable stop-limit and exit map for a long spot position."""
    price = _number(current_price)
    source_levels = levels if isinstance(levels, dict) else {}
    if price is None or price <= 0:
        return {
            "available": False,
            "product_id": product_id,
            "reason": "A current positive price is required.",
        }

    support = _number(source_levels.get("support"))
    resistance = _number(source_levels.get("resistance"))
    atr = _number(source_levels.get("atr"))
    band_low = _number(source_levels.get("band_low"))
    if support is None or support <= 0 or atr is None or atr <= 0:
        return {
            "available": False,
            "product_id": product_id,
            "current_price": _round_price(price),
            "reason": "Enough completed candles are required to establish support and volatility.",
        }

    # If the old range low is now above the live price, structure has already
    # failed.  The ATR band becomes the only honest fallback reference.
    structure_support = support if support < price else band_low
    if structure_support is None or structure_support <= 0:
        structure_support = max(price - atr, price * 0.5)

    # A valid structural stop belongs below support and at least one ATR below
    # the current quote, so ordinary candle noise is less likely to trip it.
    support_buffer = max(atr * 0.20, price * 0.0015)
    stop_trigger = min(structure_support - support_buffer, price - atr)
    stop_trigger = max(stop_trigger, price * 0.01)

    # A sell stop-limit becomes a limit order after the trigger.  The lower
    # limit provides a bounded execution band.  Keep it within 75 bps so it is
    # portable across Coinbase surfaces whose precise validation differs.
    limit_gap = min(max(atr * 0.10, stop_trigger * 0.002), stop_trigger * 0.0075)
    stop_limit = max(stop_trigger - limit_gap, stop_trigger * 0.99)

    risk_amount = price - stop_trigger
    risk_pct = (risk_amount / price) * 100.0
    first_trim = resistance if resistance is not None and resistance > price else None
    first_reward_pct = _pct(price, first_trim) if first_trim else None
    reward_risk = (
        round((first_trim - price) / risk_amount, 2)
        if first_trim is not None and risk_amount > 0
        else None
    )
    measured_target = (
        first_trim if first_trim is not None else price + (2.0 * risk_amount)
    )

    support_zone_low = max(structure_support - atr * 0.10, 0)
    support_zone_high = structure_support + atr * 0.25
    if support_zone_high >= price:
        support_zone_high = max(structure_support, price - price * 0.001)

    rounded_support = _round_price(structure_support)
    rounded_trigger = _round_price(stop_trigger)
    rounded_limit = _round_price(stop_limit)
    top_signal = _top_signal(
        current_price=price,
        support=structure_support,
        resistance=resistance,
        levels=source_levels,
        signal_context=signal_context or {},
    )

    stop_warning = (
        "Wide structural risk: the stop is more than 6% below the current price. "
        "Reduce position size or wait for a closer support structure if that loss is unacceptable."
        if risk_pct > 6
        else "A stop-limit controls the worst acceptable limit price, but a fast gap can pass it without a fill."
    )

    return {
        "available": True,
        "product_id": product_id,
        "side": "long_spot",
        "current_price": _round_price(price),
        "top_signal": top_signal,
        "stop": {
            "trigger_price": rounded_trigger,
            "limit_price": rounded_limit,
            "distance_pct": round(-risk_pct, 2),
            "risk_band": _risk_band(risk_pct),
            "invalidation_price": rounded_support,
            "why": [
                f"Recent structural support is {rounded_support}.",
                "The trigger sits below support with a volatility buffer and at least one ATR of room from the current quote.",
                "The sell limit sits below the trigger to define a small execution band after activation.",
            ],
            "execution_warning": stop_warning,
        },
        "profit": {
            "first_trim_price": _round_price(first_trim) if first_trim else None,
            "reward_pct": first_reward_pct,
            "reward_risk_ratio": reward_risk,
            "measurement_target_price": _round_price(measured_target),
            "why": (
                "Recent resistance is the first area where prior sellers appeared."
                if first_trim
                else "Price is already above the observed range; the 2R extension is for measurement only, not a validated target."
            ),
        },
        "support_zone": {
            "low": _round_price(support_zone_low),
            "high": _round_price(support_zone_high),
            "label": "Support / re-entry watch",
            "why": "This zone brackets recent support with a small ATR buffer; require a hold or reclaim instead of treating it as an automatic buy.",
        },
        "market_structure": {
            "support": rounded_support,
            "resistance": _round_price(resistance) if resistance else None,
            "atr": _round_price(atr),
            "atr_pct": source_levels.get("volatility_pct"),
            "range_position_pct": source_levels.get("range_position_pct"),
            "range_zone": source_levels.get("range_zone"),
            "window_hours": source_levels.get("window_hours"),
            "candle_count": source_levels.get("candle_count"),
            "source": source_levels.get("source") or "coinbase_candles",
        },
        "methodology": {
            "version": "sell_levels_v1",
            "outcome_validated": False,
            "order_placement": False,
            "disclosure": "Descriptive decision support, not an order or a guarantee. Levels are recorded and measured forward.",
        },
    }


__all__ = ["build_sell_plan"]
