"""Explainable entry-side (buy-side) reads built from the same candle levels.

This is the counterpart to :mod:`sell_side_intelligence`.  It answers the
questions a buyer actually has - is this building strength, is it breaking out
on real volume, is it reclaiming support after weakness, is it too extended to
chase, and where is invalidation if entering - without ever telling anyone to
buy, quoting a probability, or placing an order.

Every price this module reports is either a level :mod:`position_levels`
measured from completed Coinbase candles or an ATR buffer around one.  No entry
price is invented.  When the level math is missing, the read is unavailable.

Thresholds are deliberately borrowed from code that already ships, so this
module does not introduce a second, hand-tuned vocabulary:

* ``range_position_pct <= 15`` (near support) and ``>= 85`` (near resistance)
    are declared geometric location bands in :func:`position_levels._range_zone`,
    not empirical rarity or tail-probability thresholds.
* ``volume_ratio >= 1.5`` ("above baseline") is the cut
  :func:`sell_side_intelligence._top_signal` already uses.
* live-signal ``confidence >= 78`` ("confirmed") is the cut
  :func:`alert_events.derive_event_read` uses to call a breakout confirmed.
* ``risk_pct > 6`` ("wide") is :func:`sell_side_intelligence._risk_band`.

The declared thresholds are echoed back in ``methodology.thresholds`` so the UI
can disclose them the way the board legend discloses its cue thresholds.
"""

from __future__ import annotations

import math
from typing import Any

# Declared thresholds. Each one is reused from an existing shipped module; see
# the module docstring for where each comes from.
NEAR_SUPPORT_PCT = 15.0
NEAR_RESISTANCE_PCT = 85.0
LOWER_HALF_PCT = 60.0
VOLUME_BASELINE_RATIO = 1.5
CONFIRMED_CONFIDENCE = 78.0
WIDE_RISK_PCT = 6.0
STRONG_REWARD_RISK = 2.0

# The same warning vocabulary the sell side scans for, plus the two downside
# labels that "The Read" can publish.
_WARNING_WORDS = (
    "reversal",
    "fading",
    "fakeout",
    "exhaustion",
    "fragile",
    "breakdown",
    "downside",
)

_CONSTRUCTIVE_STATES = {"Building", "Breakout", "Moonwalking"}


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


def _signal_flags(signal_context: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce the live Event Evolution context to declared booleans."""
    context = signal_context if isinstance(signal_context, dict) else {}
    primary_state = str(context.get("primary_state") or "").strip()
    read_label = str(context.get("read_label") or "").strip()
    direction = str(context.get("direction") or "").strip().lower()
    spot_pressure = str(context.get("spot_pressure") or "").strip().lower()
    confidence = _number(context.get("confidence"))
    alert_types = {
        str(value or "").strip().lower()
        for value in context.get("alert_types") or []
    }
    words = " ".join([primary_state, read_label, *sorted(alert_types)]).lower()
    return {
        "primary_state": primary_state,
        "read_label": read_label,
        "direction": direction,
        "spot_pressure": spot_pressure,
        "confidence": confidence,
        "warned": any(word in words for word in _WARNING_WORDS),
        "direction_down": direction == "down",
        "selling_pressure": spot_pressure == "selling",
        "buying_pressure": spot_pressure == "buying",
        "confirmed_up": (
            direction == "up"
            and confidence is not None
            and confidence >= CONFIRMED_CONFIDENCE
        ),
        "constructive": primary_state in _CONSTRUCTIVE_STATES and direction != "down",
    }


def _unavailable(product_id: str, price: float | None, reason: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "product_id": product_id,
        "reason": reason,
        "entry_signal": {
            "label": "Not ready",
            "status": "unavailable",
            "tone": "neutral",
            "score": 0,
            "reasons": [reason],
        },
    }
    if price is not None:
        payload["current_price"] = _round_price(price)
    return payload


def build_entry_read(
    *,
    product_id: str,
    current_price: Any,
    levels: dict[str, Any] | None,
    signal_context: dict[str, Any] | None = None,
    sell_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an explainable entry-side read for a long spot position.

    ``sell_plan`` is the matching :func:`sell_side_intelligence.build_sell_plan`
    output.  When it is supplied, its structural support and support zone are
    reused verbatim so the protection read and the entry read never name two
    different levels for the same coin.
    """
    price = _number(current_price)
    source_levels = levels if isinstance(levels, dict) else {}
    plan = sell_plan if isinstance(sell_plan, dict) else {}
    if price is None or price <= 0:
        return _unavailable(
            product_id, None, "A current positive price is required."
        )

    support = _number(source_levels.get("support"))
    resistance = _number(source_levels.get("resistance"))
    atr = _number(source_levels.get("atr"))
    if (
        support is None
        or support <= 0
        or resistance is None
        or resistance <= 0
        or atr is None
        or atr <= 0
    ):
        return _unavailable(
            product_id,
            price,
            "Enough completed candles are required to establish support, "
            "resistance, and volatility.",
        )

    # Prefer the structural reference the protection plan already published so
    # both reads invalidate on the same level.
    plan_stop = plan.get("stop") if isinstance(plan.get("stop"), dict) else {}
    structure_support = _number(plan_stop.get("invalidation_price"))
    if structure_support is None or structure_support <= 0:
        structure_support = support

    range_position = _number(source_levels.get("range_position_pct"))
    if range_position is None:
        span = resistance - support
        range_position = (
            max(0.0, min(100.0, ((price - support) / span) * 100.0))
            if span > 0
            else 50.0
        )
    momentum = _number(source_levels.get("momentum_1h_pct"))
    volume_ratio = _number(source_levels.get("volume_ratio"))
    flags = _signal_flags(signal_context)

    above_baseline_volume = (
        volume_ratio is not None and volume_ratio >= VOLUME_BASELINE_RATIO
    )
    momentum_up = momentum is not None and momentum > 0
    momentum_down = momentum is not None and momentum < 0
    at_or_above_resistance = price >= resistance
    near_resistance = range_position >= NEAR_RESISTANCE_PCT
    near_support = range_position <= NEAR_SUPPORT_PCT
    structure_broken = price <= support
    entry_invalidation_reference = support if structure_broken else structure_support

    # Provisional risk leg: the structural support, which is where this read
    # stops being true. Used for reward/risk before the label is chosen.
    risk_amount = price - structure_support
    risk_pct = (risk_amount / price) * 100.0 if risk_amount > 0 else None
    first_resistance = resistance if resistance > price else None
    reward_pct = _pct(price, resistance) if first_resistance is not None else None
    reward_risk = (
        round((resistance - price) / risk_amount, 2)
        if first_resistance is not None and risk_amount > 0
        else None
    )

    # Evidence score, 0-10. Every point maps to one declared, real field.
    score = 0
    if momentum_up:
        score += 2
    if above_baseline_volume:
        score += 2
    if flags["confirmed_up"]:
        score += 2
    if flags["constructive"]:
        score += 1
    if flags["buying_pressure"]:
        score += 1
    if near_support and not structure_broken:
        score += 2
    if reward_risk is not None and reward_risk >= STRONG_REWARD_RISK:
        score += 1
    score = min(10, score)

    reasons: list[str] = []
    rounded_support = _round_price(structure_support)
    rounded_resistance = _round_price(resistance)

    if structure_broken or flags["warned"] or flags["direction_down"]:
        label, status, tone = "Invalidated - wait", "invalidated", "negative"
        score = 0
        if structure_broken:
            reasons.append(
                f"Price is at or below the measured support at {_round_price(support)}."
            )
        if flags["warned"]:
            reasons.append(
                "The live signal layer is carrying a reversal or fading warning."
            )
        if flags["direction_down"]:
            reasons.append("The latest grouped signal direction is down.")
        if flags["selling_pressure"]:
            reasons.append(
                "The sampled Coinbase tape is showing spot selling pressure."
            )
        action = (
            "The structure or the live signal is against an entry here. Wait for "
            "the level to be reclaimed or the warning to clear."
        )
    elif (at_or_above_resistance or near_resistance) and above_baseline_volume and momentum_up:
        label, status, tone = "Breakout watch", "breakout", "positive"
        if at_or_above_resistance:
            reasons.append(
                f"Price is at or above the measured resistance at {rounded_resistance}."
            )
        else:
            reasons.append(
                "Price is in the top 15% of its recent candle range and pushing "
                f"at the measured resistance at {rounded_resistance}."
            )
        reasons.append(
            f"The latest completed candle carried {volume_ratio}x the median "
            "volume of the measured window."
        )
        reasons.append(
            f"The latest completed hourly candle gained {momentum}%."
        )
        if flags["confirmed_up"]:
            reasons.append(
                f"The live signal layer reads {flags['primary_state'] or 'up'} "
                f"at confidence {int(flags['confidence'])}."
            )
        if flags["buying_pressure"]:
            reasons.append(
                "The sampled Coinbase tape is showing spot buying pressure."
            )
        action = (
            "Watch whether the breakout holds the level it cleared. A breakout "
            "without follow-through returns into the range."
        )
    elif near_support and momentum_up:
        label, status, tone = "Support reclaim", "entry_watch", "positive"
        reasons.append(
            "Price is in the bottom 15% of its recent candle range, just above "
            f"the structural support at {rounded_support}."
        )
        reasons.append(
            f"The latest completed hourly candle turned up by {momentum}%."
        )
        if above_baseline_volume:
            reasons.append(
                f"The turn arrived on {volume_ratio}x the median volume of the "
                "measured window."
            )
        if flags["constructive"]:
            reasons.append(
                f"The live signal layer still reads {flags['primary_state']}."
            )
        action = (
            "Watch for the reclaim to hold on a completed candle. Invalidation "
            "is close, which is what makes this area readable at all."
        )
    elif momentum_down and range_position < LOWER_HALF_PCT and flags["constructive"]:
        label, status, tone = "Pullback watch", "pullback", "caution"
        reasons.append(
            f"Price has eased back to {round(range_position, 1)}% of its recent "
            "candle range."
        )
        reasons.append(
            f"The latest completed hourly candle gave back {abs(momentum)}%."
        )
        reasons.append(
            f"The live signal layer still reads {flags['primary_state']} rather "
            "than a reversal."
        )
        action = (
            "This is a pullback inside a live signal, not a confirmed entry. "
            "Watch for the pullback to stop before the structural support."
        )
    elif (
        at_or_above_resistance
        or near_resistance
        or (reward_risk is not None and reward_risk < 1.0)
    ):
        # Both cases say "do not chase from here", but for different reasons, so
        # the label has to match the reason the reader is about to be given.
        # Near the top of the range price is extended; in the middle of it the
        # problem is only that the measured reward no longer covers the risk.
        label = (
            "Too extended"
            if at_or_above_resistance or near_resistance
            else "Poor reward from here"
        )
        status, tone = "extended", "caution"
        reward_reason = (
            f"Reward to the measured resistance is {reward_risk}x the "
            "structural risk down to invalidation."
            if reward_risk is not None and reward_risk < 1.0
            else None
        )
        # The reason that decided the label is always stated first, because the
        # card shows only the first one when it is not expanded.
        if label == "Too extended":
            if at_or_above_resistance:
                reasons.append(
                    f"Price is at or above the measured resistance at "
                    f"{rounded_resistance} with no overhead reference left in this window."
                )
            else:
                reasons.append("Price is in the top 15% of its recent candle range.")
            if not above_baseline_volume:
                reasons.append(
                    "The latest completed candle did not carry above-baseline "
                    "volume, so the push is unconfirmed."
                )
            if reward_reason:
                reasons.append(reward_reason)
        else:
            if reward_reason:
                reasons.append(reward_reason)
            reasons.append(
                f"Price sits at {round(range_position, 1)}% of its recent candle "
                "range, so the measured resistance is closer than the structural "
                "support it would have to hold."
            )
        if risk_pct is not None and risk_pct > WIDE_RISK_PCT:
            reasons.append(
                f"Invalidation sits {round(risk_pct, 2)}% below price, which is a "
                "wide structural risk for a new entry."
            )
        action = (
            "Entering here pays the top of the measured range. Wait for a "
            "pullback or a confirmed hold above resistance."
            if label == "Too extended"
            else "The measured reward no longer covers the structural risk from "
            "this price. Wait for a lower entry or a higher measured resistance."
        )
    else:
        label, status, tone = "No entry signal", "clear", "neutral"
        reasons.append(
            f"Price sits at {round(range_position, 1)}% of its recent candle "
            "range with no entry pattern in the measured levels."
        )
        if not momentum_up:
            reasons.append(
                "The latest completed hourly candle did not turn up."
                if momentum is not None
                else "Short-term momentum is unavailable for this window."
            )
        if not above_baseline_volume:
            reasons.append(
                "The latest completed candle did not carry above-baseline volume."
                if volume_ratio is not None
                else "A volume baseline is unavailable for this window."
            )
        action = (
            "No candle-and-signal combination currently meets an entry-watch "
            "condition."
        )

    # Invalidation. A breakout that has actually cleared resistance invalidates
    # on losing that level; everything else invalidates on the structure.
    if status == "breakout" and price > resistance:
        invalidation_price = resistance
        invalidation_why = (
            "A completed candle back below the measured resistance means the "
            "breakout did not hold."
        )
    else:
        invalidation_price = entry_invalidation_reference
        invalidation_why = (
            (
                "Price is at or below the measured support; that broken level "
                "is the entry invalidation reference."
                if structure_broken
                else "A completed candle below the measured structural support "
                "removes the level structure this read is built on."
            )
        )

    # Entry zone. Only the two structural reads get a band, and both bands are
    # built from levels that already exist.
    if status == "breakout":
        zone_low = max(resistance - atr * 0.25, 0.0)
        zone_high = resistance + atr * 0.25
        zone = {
            "low": _round_price(zone_low),
            "high": _round_price(zone_high),
            "label": "Breakout retest band",
            "why": (
                "This band brackets the measured resistance with a quarter-ATR "
                "buffer. It is where a breakout either holds or fails, not a "
                "validated buy price."
            ),
        }
    elif status in {"entry_watch", "pullback"}:
        plan_zone = (
            plan.get("support_zone")
            if isinstance(plan.get("support_zone"), dict)
            else {}
        )
        zone_low = _number(plan_zone.get("low"))
        zone_high = _number(plan_zone.get("high"))
        if zone_low is None or zone_high is None or zone_high < zone_low:
            zone_low = max(structure_support - atr * 0.10, 0.0)
            zone_high = structure_support + atr * 0.25
        zone = {
            "low": _round_price(zone_low),
            "high": _round_price(zone_high),
            "label": "Support / reclaim watch zone",
            "why": (
                "This zone brackets the measured support with a small ATR "
                "buffer. Require a hold or a reclaim on a completed candle "
                "instead of treating it as an automatic buy."
            ),
        }
    else:
        zone = {
            "low": None,
            "high": None,
            "label": "No entry zone",
            "why": (
                "Naming an entry band here would invent a level the completed "
                "candles do not support."
            ),
        }

    return {
        "available": True,
        "product_id": product_id,
        "side": "long_spot",
        "current_price": _round_price(price),
        "entry_signal": {
            "label": label,
            "status": status,
            "tone": tone,
            "score": score,
            "action": action,
            "reasons": reasons,
        },
        "entry_zone": zone,
        "invalidation": {
            "price": _round_price(invalidation_price),
            "distance_pct": _pct(price, invalidation_price),
            "why": invalidation_why,
        },
        "target_reference": {
            "first_resistance": (
                _round_price(first_resistance) if first_resistance is not None else None
            ),
            "reward_pct": reward_pct,
            "reward_risk_ratio": None if status == "invalidated" else reward_risk,
            "why": (
                (
                    "The setup is invalidated, so reward-to-risk is withheld "
                    "rather than presented as an actionable entry metric."
                    if status == "invalidated"
                    else "Recent resistance is the first area where prior sellers "
                    "appeared. Reward and reward-to-risk are measured to that "
                    "level and to the invalidation level; neither is a forecast."
                )
                if first_resistance is not None
                else "Price is already above the measured range, so this window "
                "holds no overhead reference and reward cannot be measured."
            ),
        },
        "market_structure": {
            "support": rounded_support,
            "resistance": rounded_resistance,
            "atr": _round_price(atr),
            "atr_pct": source_levels.get("volatility_pct"),
            "range_position_pct": round(range_position, 1),
            "range_zone": source_levels.get("range_zone"),
            "window_hours": source_levels.get("window_hours"),
            "candle_count": source_levels.get("candle_count"),
            "source": source_levels.get("source") or "coinbase_candles",
        },
        "methodology": {
            "version": "entry_levels_v1",
            "outcome_validated": False,
            "order_placement": False,
            "history_available": False,
            "disclosure": (
                "Descriptive entry-side decision support, not a buy instruction, "
                "a target, or a guarantee. Every price shown is a measured "
                "candle level or an ATR buffer around one. No forward "
                "probability is claimed because comparable entry outcomes have "
                "not been measured yet. The 15/85 bands are location bands for "
                "the recent measured range only; tail quantiles are unavailable."
            ),
            "range_bands": {
                "range_band_status": "declared_convention",
                "range_band_meaning": "recent_range_location",
                "range_band_lower_pct": NEAR_SUPPORT_PCT,
                "range_band_upper_pct": NEAR_RESISTANCE_PCT,
                "empirical_tail_quantiles": "unavailable",
            },
            "thresholds": {
                "near_support_range_pct": NEAR_SUPPORT_PCT,
                "near_resistance_range_pct": NEAR_RESISTANCE_PCT,
                "lower_half_range_pct": LOWER_HALF_PCT,
                "above_baseline_volume_ratio": VOLUME_BASELINE_RATIO,
                "confirmed_signal_confidence": CONFIRMED_CONFIDENCE,
                "wide_risk_pct": WIDE_RISK_PCT,
                "strong_reward_risk_ratio": STRONG_REWARD_RISK,
            },
        },
    }


__all__ = ["build_entry_read"]
