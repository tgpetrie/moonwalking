"""Dry-run Coinbase trade-intent evaluation and order previews.

This module creates and classifies order tickets only. It never authenticates
with Coinbase or submits, cancels, or edits a live order.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import math
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from .agents.contracts import AgentObservation


VALID_MODES = ("advisory", "guardian", "autonomous")

DEFAULT_ACCOUNT_EQUITY_USD = 1000.0
DEFAULT_RISK_PER_TRADE_PCT = 1.0
DEFAULT_MAX_ORDER_USD = 250.0
DEFAULT_MAX_OPEN_POSITIONS = 4
DEFAULT_MAX_DAILY_LOSS_R = 2.0
DEFAULT_MIN_RR = 1.5

_TRIGGER_BUFFER_PCT = 0.0015
_LIMIT_BUFFER_PCT = 0.0035
_BLOCKED_SENTIMENT_POSTURES = {
    "negative_catalyst_risk",
    "crowded_euphoria_top",
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _round_price(value: float) -> float:
    if value >= 1000:
        digits = 2
    elif value >= 1:
        digits = 4
    elif value >= 0.01:
        digits = 6
    else:
        digits = 8
    return round(value, digits)


def _format_decimal(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _input(context: Mapping[str, Any] | None, values: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(context or {})
    result.update(values)
    return result


def _product_and_symbol(data: Mapping[str, Any]) -> tuple[str | None, str | None]:
    product_id = str(data.get("product_id") or data.get("productId") or "").upper()
    symbol = str(data.get("symbol") or "").upper().split("-")[0]
    if not symbol and product_id:
        symbol = product_id.split("-")[0]
    if not product_id and symbol:
        product_id = f"{symbol}-USD"
    return product_id or None, symbol or None


def _bar_value(bar: Any, field: str) -> float | None:
    row = _mapping(bar)
    if row:
        return _number(row.get(field))
    if isinstance(bar, (list, tuple)):
        index = {"low": 1, "open": 3, "close": 4}.get(field)
        if index is not None and len(bar) > index:
            return _number(bar[index])
    return None


def _wave_for_timeframe(
    wave_analysis: Mapping[str, Any], timeframe: str
) -> Mapping[str, Any]:
    direct = wave_analysis.get(timeframe)
    if isinstance(direct, Mapping):
        return direct
    if wave_analysis.get("timeframe") == timeframe or timeframe == "1h":
        return wave_analysis
    return {}


def _factor_state(wave: Mapping[str, Any], name: str) -> str | None:
    for factor in wave.get("confluence_factors") or []:
        if isinstance(factor, Mapping) and factor.get("name") == name:
            return str(factor.get("state") or "").lower()
    return None


def _c_price(wave: Mapping[str, Any]) -> float | None:
    direct = _number(wave.get("c_price") or wave.get("wave_c_low"))
    if direct is not None:
        return direct
    for point in wave.get("wave_points") or []:
        if isinstance(point, Mapping) and str(point.get("label") or "").upper() == "C":
            value = _number(point.get("price"))
            if value is not None:
                return value
    return None


def _target_price(wave: Mapping[str, Any]) -> float | None:
    direct = _number(wave.get("target_price"))
    if direct is not None:
        return direct
    for point in wave.get("wave_points") or []:
        if isinstance(point, Mapping) and str(point.get("label") or "").upper() == "B":
            value = _number(point.get("price"))
            if value is not None:
                return value
    return None


def compute_position_size(
    *,
    entry_price: Any,
    stop_limit_price: Any,
    account_equity_usd: Any = DEFAULT_ACCOUNT_EQUITY_USD,
    risk_per_trade_pct: Any = DEFAULT_RISK_PER_TRADE_PCT,
    max_order_usd: Any = DEFAULT_MAX_ORDER_USD,
) -> dict[str, float]:
    """Size a long spot entry by stop-limit risk, then apply the notional cap."""
    entry = _number(entry_price)
    stop = _number(stop_limit_price)
    equity = _number(account_equity_usd)
    risk_pct = _number(risk_per_trade_pct)
    order_cap = _number(max_order_usd)
    if entry is None or entry <= 0:
        raise ValueError("entry_price must be a positive finite number")
    if stop is None or stop <= 0 or stop >= entry:
        raise ValueError("stop_limit_price must be positive and below entry")
    if equity is None or equity <= 0:
        raise ValueError("account_equity_usd must be a positive finite number")
    if risk_pct is None or risk_pct <= 0:
        raise ValueError("risk_per_trade_pct must be a positive finite number")
    if order_cap is None or order_cap <= 0:
        raise ValueError("max_order_usd must be a positive finite number")

    risk_budget = equity * risk_pct / 100.0
    risk_based_size = risk_budget / (entry - stop)
    base_size = min(risk_based_size, order_cap / entry)
    notional = base_size * entry
    actual_risk = base_size * (entry - stop)
    return {
        "risk_budget_usd": round(risk_budget, 8),
        "risk_based_size": round(risk_based_size, 12),
        "base_size": round(base_size, 12),
        "size": round(base_size, 12),
        "notional_usd": round(notional, 8),
        "actual_risk_usd": round(actual_risk, 8),
    }


def build_coinbase_v3_order_preview(
    ticket: Mapping[str, Any] | None = None, **values: Any
) -> dict[str, Any]:
    """Build a clearly marked, non-submittable preview of an Advanced Trade v3 order."""
    data = _input(ticket, values)
    product_id, _ = _product_and_symbol(data)
    side = str(data.get("side") or "").strip().lower()
    intent_type = str(data.get("intent_type") or "").strip().lower()
    base_size = _number(data.get("base_size") or data.get("size") or data.get("quantity"))
    if not product_id:
        raise ValueError("product_id or symbol is required for an order preview")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    if base_size is None or base_size <= 0:
        raise ValueError("base_size must be a positive finite number")

    if intent_type == "protective_stop_limit":
        if side != "sell":
            raise ValueError("protective stop-limit previews must be sell orders")
        stop_price = _number(data.get("stop_trigger_price"))
        limit_price = _number(data.get("stop_limit_price"))
        if stop_price is None or stop_price <= 0:
            raise ValueError("stop_trigger_price must be positive")
        if limit_price is None or limit_price <= 0 or limit_price >= stop_price:
            raise ValueError("stop_limit_price must be positive and below the stop trigger")
        order_configuration = {
            "stop_limit_stop_limit_gtc": {
                "base_size": _format_decimal(base_size),
                "limit_price": _format_decimal(limit_price),
                "stop_price": _format_decimal(stop_price),
                "stop_direction": "STOP_DIRECTION_STOP_DOWN",
            }
        }
    else:
        if side != "buy":
            raise ValueError("entry previews must be buy orders")
        limit_price = _number(data.get("entry_price"))
        if limit_price is None or limit_price <= 0:
            raise ValueError("entry_price must be positive")
        order_configuration = {
            "limit_limit_gtc": {
                "base_size": _format_decimal(base_size),
                "limit_price": _format_decimal(limit_price),
                "post_only": False,
            }
        }

    return {
        "dry_run": True,
        "exchange": "coinbase_advanced_trade_v3",
        "payload": {
            "client_order_id": str(data.get("client_order_id") or uuid4()),
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_configuration,
        },
    }


def _circuit_breaker_reasons(
    ticket: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    max_open_positions: int,
    max_daily_loss_r: float,
    max_order_usd: float,
    min_rr: float,
) -> list[str]:
    reasons: list[str] = []
    open_positions = _number(context.get("open_positions"))
    if open_positions is None or open_positions < 0 or not open_positions.is_integer():
        reasons.append("open_positions_unavailable")
    elif open_positions >= max_open_positions:
        reasons.append("max_open_positions_reached")

    daily_realized_r = _number(context.get("daily_realized_r"))
    if daily_realized_r is None:
        reasons.append("daily_realized_r_unavailable")
    elif daily_realized_r <= -max_daily_loss_r:
        reasons.append("max_daily_loss_reached")

    notional = _number(ticket.get("notional_usd"))
    if notional is None:
        size = _number(ticket.get("base_size") or ticket.get("size"))
        reference_price = _number(
            ticket.get("entry_price") or ticket.get("current_price")
        )
        notional = size * reference_price if size is not None and reference_price else None
    if notional is None or notional <= 0:
        reasons.append("order_notional_unavailable")
    elif notional > max_order_usd:
        reasons.append("max_order_usd_exceeded")

    rr_planned = _number(ticket.get("rr_planned"))
    if rr_planned is None:
        reasons.append("planned_reward_risk_unavailable")
    elif rr_planned < min_rr:
        reasons.append("minimum_reward_risk_not_met")

    posture = context.get("sentiment_posture")
    if isinstance(posture, Mapping):
        posture = posture.get("key") or posture.get("posture")
    if not str(posture or "").strip():
        reasons.append("sentiment_posture_unavailable")
    elif str(posture).strip().lower() in _BLOCKED_SENTIMENT_POSTURES:
        reasons.append("sentiment_posture_blocked")
    return reasons


def _classify_ticket(
    ticket: Mapping[str, Any],
    mode: str,
    context: Mapping[str, Any],
    *,
    max_open_positions: int,
    max_daily_loss_r: float,
    max_order_usd: float,
    min_rr: float,
) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}")
    result = dict(ticket)
    result["status"] = "staged_for_approval"
    result.pop("block_reasons", None)
    if mode == "guardian":
        held = bool(result.get("position_held") or result.get("held_position"))
        if (
            held
            and result.get("side") == "sell"
            and result.get("intent_type") == "protective_stop_limit"
        ):
            result["status"] = "auto_approved_guardian"
    elif mode == "autonomous":
        reasons = _circuit_breaker_reasons(
            result,
            context,
            max_open_positions=max_open_positions,
            max_daily_loss_r=max_daily_loss_r,
            max_order_usd=max_order_usd,
            min_rr=min_rr,
        )
        if reasons:
            result["status"] = "blocked_by_circuit_breaker"
            result["block_reasons"] = reasons
        else:
            result["status"] = "auto_approved_autonomous"
    return result


def _setup_ticket(
    *,
    data: Mapping[str, Any],
    intent_type: str,
    entry_price: float,
    stop_trigger_price: float,
    stop_limit_price: float,
    target_price: float,
) -> dict[str, Any]:
    product_id, symbol = _product_and_symbol(data)
    risk_distance = entry_price - stop_limit_price
    if (
        not product_id
        or entry_price <= 0
        or stop_trigger_price <= 0
        or stop_limit_price <= 0
        or stop_trigger_price >= entry_price
        or stop_limit_price >= stop_trigger_price
        or risk_distance <= 0
        or target_price <= entry_price
    ):
        return {}
    sizing = compute_position_size(
        entry_price=entry_price,
        stop_limit_price=stop_limit_price,
        account_equity_usd=data.get("account_equity_usd", DEFAULT_ACCOUNT_EQUITY_USD),
        risk_per_trade_pct=data.get("risk_per_trade_pct", DEFAULT_RISK_PER_TRADE_PCT),
        max_order_usd=data.get("max_order_usd", DEFAULT_MAX_ORDER_USD),
    )
    ticket = {
        "product_id": product_id,
        "symbol": symbol,
        "side": "buy",
        "intent_type": intent_type,
        "order_type": "limit",
        "entry_price": _round_price(entry_price),
        "stop_trigger_price": _round_price(stop_trigger_price),
        "stop_limit_price": _round_price(stop_limit_price),
        "target_price": _round_price(target_price),
        "rr_planned": round((target_price - entry_price) / risk_distance, 2),
        **sizing,
        "position_held": False,
        "status": "staged_for_approval",
    }
    ticket["payload_preview"] = build_coinbase_v3_order_preview(ticket)
    return ticket


def evaluate_1h_reclaim_ticket(
    context: Mapping[str, Any] | None = None, **values: Any
) -> dict[str, Any] | None:
    """Create an entry ticket only for a confirmed bullish 1h Wave-C reclaim."""
    data = _input(context, values)
    wave = _wave_for_timeframe(_mapping(data.get("wave_analysis")), "1h")
    if (
        not wave
        or wave.get("available") is False
        or wave.get("bias") != "bullish"
        or wave.get("active_pattern") != "abc_in_progress"
        or wave.get("status") != "in_c_zone"
        or str(wave.get("higher_tf_trend") or "").lower() == "opposed"
        or _factor_state(wave, "higher_tf_trend") == "opposed"
    ):
        return None

    chart = _mapping(wave.get("chart"))
    candles = data.get("candles_1h") or data.get("bars_1h") or chart.get("candles") or []
    turn_bar = data.get("turn_bar") or data.get("current_bar")
    prior_bar = data.get("previous_bar")
    if turn_bar is None and isinstance(candles, (list, tuple)) and candles:
        turn_bar = candles[-1]
    if prior_bar is None and isinstance(candles, (list, tuple)) and len(candles) >= 2:
        prior_bar = candles[-2]

    current_open = _bar_value(turn_bar, "open")
    current_close = _number(data.get("current_close"))
    if current_close is None:
        current_close = _bar_value(turn_bar, "close")
    previous_close = _number(data.get("prev_close"))
    if previous_close is None:
        previous_close = _bar_value(prior_bar, "close")
    c_price = _c_price(wave)
    target = _target_price(wave)
    if (
        current_open is None
        or current_close is None
        or previous_close is None
        or c_price is None
        or target is None
        or current_close <= current_open
        or current_close <= previous_close
    ):
        return None

    prior_cue = data.get("prior_bar_c_low") is True or wave.get("prior_bar_c_low") is True
    previous_low = _bar_value(prior_bar, "low")
    if previous_low is not None and math.isclose(previous_low, c_price, rel_tol=1e-8):
        prior_cue = True
    has_reclaim = (
        _factor_state(wave, "ema_reclaim") == "present"
        or _factor_state(wave, "bollinger_reclaim") == "present"
        or data.get("ema_reclaim") is True
        or data.get("bollinger_reclaim") is True
        or prior_cue
    )
    if not has_reclaim:
        return None

    entry = _round_price(current_close)
    trigger = _round_price(c_price * 0.9985)
    limit = _round_price(c_price * 0.9965)
    target = _round_price(target)
    if entry <= limit or target <= entry:
        return None
    ticket = _setup_ticket(
        data=data,
        intent_type="entry",
        entry_price=entry,
        stop_trigger_price=trigger,
        stop_limit_price=limit,
        target_price=target,
    )
    return ticket or None


def _a1_gate_passed(data: Mapping[str, Any]) -> bool:
    for key in ("a1_gate_pass", "a1_pass", "dollar_volume_gate_pass"):
        if data.get(key) is True:
            return True
    for key in ("a1", "dollar_volume_gate", "a1_gate"):
        value = data.get(key)
        if value is True:
            return True
        if isinstance(value, Mapping) and (
            value.get("passed") is True
            or value.get("pass") is True
            or str(value.get("status") or "").lower() == "pass"
        ):
            return True
    return False


def _posture_key(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("key") or value.get("posture") or value.get("status")
    return str(value or "").strip().lower()


def _is_completed_impulse(read: Mapping[str, Any]) -> bool:
    return read.get("active_pattern") == "impulse_complete"


def evaluate_a1_momentum_ticket(
    context: Mapping[str, Any] | None = None, **values: Any
) -> dict[str, Any] | None:
    """Create an entry ticket from a passed A1 gate and clean 1h ABC posture."""
    data = _input(context, values)
    if not _a1_gate_passed(data):
        return None
    if _posture_key(
        data.get("structure_posture") or data.get("structure_posture_key")
    ) != "1h_abc_clean":
        return None

    waves = _mapping(data.get("wave_analysis"))
    for timeframe in ("15m", "1h", "4h"):
        if _is_completed_impulse(_wave_for_timeframe(waves, timeframe)):
            return None

    entry = _number(
        data.get("entry_price")
        or data.get("current_price")
        or data.get("price")
        or data.get("current_close")
    )
    levels = _mapping(data.get("levels") or data.get("position_levels"))
    entry_read = _mapping(data.get("entry_read"))
    entry_structure = _mapping(entry_read.get("market_structure"))
    support_values = [
        _number(data.get("support")),
        _number(levels.get("support")),
        _number(entry_structure.get("support")),
    ]
    base_values = support_values + [
        _number(data.get("ignition_base")),
        _number(levels.get("ignition_base")),
    ]
    bases = [value for value in base_values if value is not None and value > 0]
    resistance = _number(
        data.get("resistance")
        or levels.get("resistance")
        or entry_structure.get("resistance")
    )
    if entry is None or entry <= 0 or not bases:
        return None
    base = min(bases)
    trigger = _round_price(base * (1.0 - _TRIGGER_BUFFER_PCT))
    limit = _round_price(base * (1.0 - _LIMIT_BUFFER_PCT))
    if trigger <= limit:
        return None
    target = (
        resistance
        if resistance is not None and resistance > entry
        else entry + 2.0 * (entry - limit)
    )
    target = _round_price(target)
    if entry <= limit or target <= entry:
        return None
    ticket = _setup_ticket(
        data=data,
        intent_type="entry",
        entry_price=_round_price(entry),
        stop_trigger_price=trigger,
        stop_limit_price=limit,
        target_price=target,
    )
    return ticket or None


def _find_higher_low(wave: Mapping[str, Any]) -> float | None:
    direct = _number(wave.get("higher_low") or wave.get("higher_low_price"))
    if direct is not None:
        return direct
    for swing in reversed(wave.get("swing_history") or []):
        if not isinstance(swing, Mapping):
            continue
        label = " ".join(
            str(swing.get(key) or "").lower()
            for key in ("label", "relationship", "kind", "type")
        )
        if "higher low" in label:
            price = _number(swing.get("price") or swing.get("value"))
            if price is not None:
                return price
    return None


def evaluate_position_defense_ticket(
    context: Mapping[str, Any] | None = None, **values: Any
) -> dict[str, Any] | None:
    """Create a protective held-position stop-limit ticket from current risk levels."""
    data = _input(context, values)
    position = _mapping(data.get("position"))
    if not position:
        position = data
    quantity = _number(
        position.get("quantity")
        or position.get("base_size")
        or position.get("size")
    )
    if quantity is None or quantity <= 0:
        return None
    if position.get("held") is False or position.get("is_held") is False:
        return None

    levels = _mapping(
        data.get("sell_plan")
        or data.get("sell_side_intelligence")
        or data.get("levels")
    ) or data
    stop_levels = _mapping(levels.get("stop"))
    profit_levels = _mapping(levels.get("profit"))
    structure_levels = _mapping(levels.get("market_structure"))
    current = _number(
        position.get("current_price")
        or position.get("price")
        or data.get("current_price")
    )
    stop_trigger = _number(
        levels.get("stop_trigger")
        or data.get("stop_trigger")
        or stop_levels.get("trigger_price")
        or stop_levels.get("stop_trigger")
    )
    stop_limit = _number(
        levels.get("sell_limit")
        or data.get("sell_limit")
        or stop_levels.get("limit_price")
        or stop_levels.get("sell_limit")
    )
    support_fails = levels.get("support_fails", data.get("support_fails"))
    if isinstance(support_fails, Mapping):
        support_fails = support_fails.get("price") or support_fails.get("level")
    support_fail_price = _number(support_fails)
    support = _number(structure_levels.get("support") or levels.get("support"))
    if support_fail_price is None and support_fails is True and support is not None:
        support_fail_price = support * (1.0 - _TRIGGER_BUFFER_PCT)

    wave = _mapping(data.get("wave_analysis"))
    higher_low = _find_higher_low(wave)
    if stop_trigger is None or stop_limit is None or current is None or current <= 0:
        return None
    candidates = [stop_trigger]
    if support_fail_price is not None:
        candidates.append(support_fail_price)
    if higher_low is not None:
        candidates.append(higher_low)
    candidates_below_current = [value for value in candidates if 0 < value < current]
    if not candidates_below_current:
        return None
    stop_trigger = max(candidates_below_current)
    limit_gap = min(
        max(stop_trigger - stop_limit, stop_trigger * 0.002),
        stop_trigger * 0.0075,
    )
    stop_limit = stop_trigger - limit_gap
    stop_trigger = _round_price(stop_trigger)
    stop_limit = _round_price(stop_limit)
    if stop_limit >= stop_trigger:
        return None

    first_trim = _number(
        profit_levels.get("first_trim_price")
        or levels.get("first_trim")
        or levels.get("first_trim_price")
        or data.get("first_trim")
    )
    posture = _posture_key(data.get("sentiment_posture"))
    crowded = posture in _BLOCKED_SENTIMENT_POSTURES or posture == "crowded_euphoria"
    target = first_trim if first_trim is not None and first_trim > current else None
    rr_planned = (
        round((target - current) / (current - stop_limit), 2)
        if target is not None and current > stop_limit
        else None
    )
    product_id, symbol = _product_and_symbol({**position, **data})
    if not product_id:
        return None

    ticket: dict[str, Any] = {
        "product_id": product_id,
        "symbol": symbol,
        "side": "sell",
        "intent_type": "protective_stop_limit",
        "order_type": "stop_limit",
        "position_held": True,
        "base_size": round(quantity, 12),
        "current_price": _round_price(current),
        "stop_trigger_price": _round_price(stop_trigger),
        "stop_limit_price": _round_price(stop_limit),
        "target_price": _round_price(target) if target is not None else None,
        "first_trim_price": _round_price(first_trim) if first_trim is not None else None,
        "support_fails": support_fail_price,
        "higher_low_trail": higher_low,
        "crowded_euphoria_top": crowded,
        "rr_planned": rr_planned,
        "notional_usd": round(quantity * current, 8),
        "status": "staged_for_approval",
    }
    ticket["payload_preview"] = build_coinbase_v3_order_preview(ticket)
    return ticket


class CoinbaseExecutionAgent:
    """Rule-based intent agent that records paper previews, never live orders."""

    name = "coinbase_execution"
    model_version = "coinbase-trade-intent-v1"

    def __init__(
        self,
        *,
        mode: str = "advisory",
        account_equity_usd: float = DEFAULT_ACCOUNT_EQUITY_USD,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
        max_order_usd: float = DEFAULT_MAX_ORDER_USD,
        max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS,
        max_daily_loss_r: float = DEFAULT_MAX_DAILY_LOSS_R,
        min_rr: float = DEFAULT_MIN_RR,
    ) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        self.mode = mode
        self.account_equity_usd = account_equity_usd
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_order_usd = max_order_usd
        self.max_open_positions = max_open_positions
        self.max_daily_loss_r = max_daily_loss_r
        self.min_rr = min_rr

    def _configured(self, data: Mapping[str, Any]) -> dict[str, Any]:
        mode = data.get("mode", self.mode)
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        return {
            "mode": mode,
            "max_open_positions": int(
                data.get("max_open_positions", self.max_open_positions)
            ),
            "max_daily_loss_r": float(
                data.get("max_daily_loss_r", self.max_daily_loss_r)
            ),
            "max_order_usd": float(data.get("max_order_usd", self.max_order_usd)),
            "min_rr": float(data.get("min_rr", self.min_rr)),
        }

    def _observation(
        self, ticket: Mapping[str, Any], mode: str
    ) -> AgentObservation:
        try:
            from .agents.contracts import AgentObservation
        except ImportError:
            from agents.contracts import AgentObservation

        status = ticket["status"]
        severity = "warning" if status == "blocked_by_circuit_breaker" else "info"
        symbol = ticket.get("symbol")
        side = str(ticket.get("side") or "").upper()
        intent = str(ticket.get("intent_type") or "order")
        return AgentObservation(
            agent=self.name,
            kind="order_ticket_preview",
            severity=severity,
            symbol=str(symbol) if symbol else None,
            product_id=ticket.get("product_id"),
            summary=(
                f"{symbol or ticket.get('product_id') or 'Coinbase'} {side} "
                f"{intent.replace('_', ' ')} ticket: {status}. Preview only; "
                "no Coinbase order was submitted."
            ),
            evidence={"mode": mode, "ticket": dict(ticket)},
            source={
                "surface": "coinbase_execution_agent",
                "execution": "dry_run_only",
            },
        )

    def run(self, context: dict | None) -> list[AgentObservation]:
        outer = _mapping(context)
        nested = _mapping(outer.get("coinbase_execution"))
        data = dict(outer)
        data.update(nested)
        risk_context = _mapping(data.get("risk_controls"))
        data.update(risk_context)
        data.setdefault("account_equity_usd", self.account_equity_usd)
        data.setdefault("risk_per_trade_pct", self.risk_per_trade_pct)
        data.setdefault("max_order_usd", self.max_order_usd)
        config = self._configured(data)
        mode = config["mode"]
        tickets: list[dict[str, Any]] = []

        candidates = (
            data.get("trade_intents")
            or data.get("execution_candidates")
            or data.get("tickets")
            or []
        )
        if isinstance(candidates, Mapping):
            candidates = [candidates]
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, Mapping):
                    tickets.append(dict(candidate))

        if isinstance(data.get("wave_analysis"), Mapping):
            reclaim = evaluate_1h_reclaim_ticket(data)
            if reclaim:
                tickets.append(reclaim)
            momentum = evaluate_a1_momentum_ticket(data)
            if momentum:
                tickets.append(momentum)

        positions = data.get("held_positions")
        if isinstance(positions, list):
            for position in positions:
                if not isinstance(position, Mapping):
                    continue
                position_data = dict(data)
                position_data["position"] = position
                plan_map = _mapping(data.get("sell_plans"))
                symbol = _product_and_symbol(position)[1]
                if symbol and isinstance(plan_map.get(symbol), Mapping):
                    position_data["sell_plan"] = plan_map[symbol]
                defense = evaluate_position_defense_ticket(position_data)
                if defense:
                    tickets.append(defense)
        elif isinstance(data.get("position"), Mapping):
            defense = evaluate_position_defense_ticket(data)
            if defense:
                tickets.append(defense)

        observations = []
        for ticket in tickets:
            cycle = data.get("multi_year_context")
            if isinstance(cycle, Mapping) and cycle.get("available"):
                ticket["multi_year_context"] = dict(cycle)
            product_id, symbol = _product_and_symbol(ticket)
            ticket["product_id"] = product_id
            ticket["symbol"] = symbol
            ticket["side"] = str(ticket.get("side") or "").lower()
            if ticket["side"] not in {"buy", "sell"}:
                raise ValueError("each trade intent must have side buy or sell")
            if not _number(ticket.get("base_size") or ticket.get("size")):
                if ticket.get("quantity") is not None:
                    ticket["base_size"] = ticket["quantity"]

            entry = _number(ticket.get("entry_price"))
            stop_limit = _number(ticket.get("stop_limit_price"))
            if ticket["side"] == "buy" and entry is not None:
                existing_size = _number(
                    ticket.get("base_size") or ticket.get("size")
                )
                existing_notional = _number(ticket.get("notional_usd"))
                if existing_size is None and existing_notional is not None:
                    existing_size = existing_notional / entry
                if existing_size is None and stop_limit is not None:
                    sizing = compute_position_size(
                        entry_price=entry,
                        stop_limit_price=stop_limit,
                        account_equity_usd=data.get(
                            "account_equity_usd", self.account_equity_usd
                        ),
                        risk_per_trade_pct=data.get(
                            "risk_per_trade_pct", self.risk_per_trade_pct
                        ),
                        max_order_usd=config["max_order_usd"],
                    )
                    ticket.update(sizing)
                elif existing_size is not None:
                    ticket.setdefault("base_size", round(existing_size, 12))
                    ticket.setdefault("size", round(existing_size, 12))
                    if existing_notional is None:
                        ticket["notional_usd"] = round(existing_size * entry, 8)
                    if stop_limit is not None and stop_limit < entry:
                        ticket.setdefault(
                            "actual_risk_usd",
                            round(existing_size * (entry - stop_limit), 8),
                        )
            elif ticket["side"] == "sell" and not _number(ticket.get("notional_usd")):
                size = _number(ticket.get("base_size") or ticket.get("size"))
                reference = _number(
                    ticket.get("current_price") or ticket.get("entry_price")
                )
                if size is not None and reference is not None:
                    ticket["notional_usd"] = round(size * reference, 8)

            ticket["payload_preview"] = build_coinbase_v3_order_preview(ticket)
            ticket = _classify_ticket(
                ticket,
                mode,
                data,
                max_open_positions=config["max_open_positions"],
                max_daily_loss_r=config["max_daily_loss_r"],
                max_order_usd=config["max_order_usd"],
                min_rr=config["min_rr"],
            )
            observations.append(self._observation(ticket, mode))
        return observations


__all__ = [
    "VALID_MODES",
    "CoinbaseExecutionAgent",
    "build_coinbase_v3_order_preview",
    "compute_position_size",
    "evaluate_1h_reclaim_ticket",
    "evaluate_a1_momentum_ticket",
    "evaluate_position_defense_ticket",
]
