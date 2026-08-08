"""Alert rule evaluation — pure logic, no database and no network.

Decides whether a single user rule should fire against a single market
observation. Every branch is deterministic so the whole surface is unit
testable without a DB, a clock, or a price feed.

Two trigger types ship in Phase 1:

``price_cross``   price crosses a fixed boundary in one direction.
``percent_move``  price moves by N% across a *rolling* window ending now.

Re-arming (hysteresis) is modelled as an explicit ``armed`` flag on the rule
rather than by remembering the previous price. A rule that fires becomes
disarmed and cannot fire again until the market retreats past a reset
boundary. Creation-time validation guarantees a rule never starts in an
already-satisfied state, so no "previous price" is needed to detect a genuine
crossing.

Language guardrails match the rest of the product: no buy/sell/hold, no
entry/exit, no predictions. Explanations state what happened and why the user
received it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Decision",
    "WINDOW_SECONDS",
    "WINDOW_LABELS",
    "DEFAULT_COOLDOWN_SECONDS",
    "DEFAULT_RESET_PCT",
    "DEFAULT_PERCENT_REARM_RATIO",
    "MAX_PRICE_AGE_SECONDS",
    "evaluate_rule",
    "validate_rule_params",
    "format_price",
]


# ─── supported windows ────────────────────────────────────────────────────────

WINDOW_SECONDS = {
    "1h": 3_600,
    "4h": 14_400,
    "24h": 86_400,
}

WINDOW_LABELS = {
    "1h": "a rolling 1-hour period",
    "4h": "a rolling 4-hour period",
    "24h": "a rolling 24-hour period",
}

VALID_DIRECTIONS = {
    "price_cross": {"above", "below"},
    "percent_move": {"up", "down", "either"},
}

# Per-type minimum cooldowns. Defined centrally so no caller hardcodes one
# universal value across rule types.
DEFAULT_COOLDOWN_SECONDS = {
    "price_cross": 3_600,
    "percent_move": 14_400,
}

MIN_COOLDOWN_SECONDS = {
    "price_cross": 900,
    "percent_move": 1_800,
}

# price_cross: price must retreat this % past the boundary before re-arming.
DEFAULT_RESET_PCT = 1.0

# percent_move: the rolling move must decay below this fraction of the
# threshold before re-arming. Cooldown alone is insufficient here because the
# same rolling window can stay true for hours.
DEFAULT_PERCENT_REARM_RATIO = 0.75

# Observations older than this are treated as stale and never trigger.
MAX_PRICE_AGE_SECONDS = 300

# Statuses that still get evaluated. 'cooling_down' is included so a recurring
# rule can observe its reset boundary; 'paused', 'triggered' and 'expired' are
# terminal or user-suspended and are skipped.
EVALUABLE_STATUSES = {"active", "cooling_down"}


# ─── decision ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Decision:
    """Outcome of evaluating one rule against one observation."""

    should_fire: bool = False
    suppression_reason: str | None = None
    event_type: str = ""
    explanation: str = ""
    observed_value: float | None = None
    boundary_value: float | None = None
    comparison_value: float | None = None
    window_label: str | None = None
    # Rule state the caller should persist after acting on this decision.
    next_armed: bool = True
    armed_changed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _suppressed(
    reason: str, *, next_armed: bool, armed_changed: bool = False
) -> Decision:
    return Decision(
        should_fire=False,
        suppression_reason=reason,
        next_armed=next_armed,
        armed_changed=armed_changed,
    )


# ─── helpers ─────────────────────────────────────────────────────────────────


def format_price(value: float) -> str:
    """Human-readable price with a sensible number of decimals."""
    v = abs(float(value))
    if v >= 10_000:
        return f"${value:,.0f}"
    if v >= 100:
        return f"${value:,.2f}"
    if v >= 1:
        return f"${value:,.3f}"
    return f"${value:,.6f}".rstrip("0").rstrip(".")


def _num(value: Any) -> float | None:
    """Strict numeric coercion. Rejects None, NaN, inf, and non-numerics."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _positive_price(value: Any) -> float | None:
    f = _num(value)
    if f is None or f <= 0:
        return None
    return f


# ─── validation ──────────────────────────────────────────────────────────────


def validate_rule_params(
    trigger_type: str,
    params: dict[str, Any],
    *,
    current_price: float | None = None,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Validate + normalize trigger params before a rule is stored.

    Returns ``(ok, error_message, normalized_params)``. Rejects rules that
    would be logically broken — most importantly a boundary the market has
    already satisfied, which would otherwise fire the instant it is saved.
    """
    ttype = str(trigger_type or "").strip().lower()
    if ttype not in VALID_DIRECTIONS:
        return False, f"Unsupported trigger type: {trigger_type}", {}

    direction = str(params.get("direction") or "").strip().lower()
    if direction not in VALID_DIRECTIONS[ttype]:
        allowed = ", ".join(sorted(VALID_DIRECTIONS[ttype]))
        return False, f"Direction must be one of: {allowed}", {}

    if ttype == "price_cross":
        threshold = _positive_price(params.get("threshold"))
        if threshold is None:
            return False, "Price target must be a positive number.", {}

        price = _positive_price(current_price)
        if price is not None:
            if direction == "above" and threshold <= price:
                return (
                    False,
                    f"That target is already at or below the current price "
                    f"({format_price(price)}). Choose a target above it, or use "
                    f"'goes below' instead.",
                    {},
                )
            if direction == "below" and threshold >= price:
                return (
                    False,
                    f"That target is already at or above the current price "
                    f"({format_price(price)}). Choose a target below it, or use "
                    f"'goes above' instead.",
                    {},
                )
        return True, None, {"direction": direction, "threshold": threshold}

    # percent_move
    threshold = _num(params.get("threshold"))
    if threshold is None or threshold <= 0:
        return False, "Percentage must be a positive number.", {}
    if threshold > 100:
        return False, "Percentage must be 100 or less.", {}
    if threshold < 0.1:
        return False, "Percentage must be at least 0.1.", {}

    window = str(params.get("window") or "").strip().lower()
    if window not in WINDOW_SECONDS:
        allowed = ", ".join(WINDOW_SECONDS)
        return False, f"Time window must be one of: {allowed}", {}

    return (
        True,
        None,
        {
            "direction": direction,
            "threshold": float(threshold),
            "window": window,
        },
    )


# ─── explanations ────────────────────────────────────────────────────────────


def _source_clause(rule: dict[str, Any]) -> str:
    """Why this user is seeing the alert at all."""
    source = str(rule.get("source") or "manual").strip().lower()
    basis = str(rule.get("recommendation_basis") or "").strip().lower()
    if source == "recommended":
        if basis == "portfolio":
            return "You accepted this suggested alert for a portfolio holding."
        if basis == "watchlist":
            return "You accepted this suggested alert for a watchlist asset."
        return "You accepted this suggested alert."
    return "You created this alert."


def _repeat_clause(rule: dict[str, Any], next_armed: bool) -> str:
    """What happens to the rule now that it fired."""
    if str(rule.get("repeat_mode") or "once").lower() == "once":
        return "This was a one-time alert and is now complete."
    if next_armed:
        return "This alert stays active."
    return (
        "This alert is now cooling down and will become active again only "
        "after the market moves back past its reset area."
    )


def _explain_price_cross(
    rule: dict[str, Any], symbol: str, price: float, boundary: float, direction: str
) -> str:
    verb = "rose above" if direction == "above" else "fell below"
    return (
        f"{symbol} {verb} {format_price(boundary)}, reaching "
        f"{format_price(price)}. {_source_clause(rule)} "
        f"{_repeat_clause(rule, next_armed=False)}"
    )


def _explain_percent_move(
    rule: dict[str, Any],
    symbol: str,
    move_pct: float,
    threshold: float,
    window: str,
    price: float,
    past_price: float,
) -> str:
    motion = "up" if move_pct > 0 else "down"
    return (
        f"{symbol} moved {motion} {abs(move_pct):.1f}% during "
        f"{WINDOW_LABELS[window]}, passing your {threshold:g}% mark. "
        f"It went from {format_price(past_price)} to {format_price(price)}. "
        f"{_source_clause(rule)} {_repeat_clause(rule, next_armed=False)}"
    )


# ─── evaluators ──────────────────────────────────────────────────────────────


def _evaluate_price_cross(
    rule: dict[str, Any], params: dict[str, Any], obs: dict[str, Any], armed: bool
) -> Decision:
    price = _positive_price(obs.get("price"))
    if price is None:
        return _suppressed("no_price", next_armed=armed)

    boundary = _positive_price(params.get("threshold"))
    if boundary is None:
        return _suppressed("invalid_rule_params", next_armed=armed)

    direction = str(params.get("direction") or "").lower()
    symbol = str(rule.get("symbol") or "").upper()
    reset_pct = _num(rule.get("reset_pct"))
    if reset_pct is None or reset_pct < 0:
        reset_pct = DEFAULT_RESET_PCT

    condition_met = price > boundary if direction == "above" else price < boundary

    if not armed:
        # Re-arm only after price retreats past the reset boundary.
        if direction == "above":
            rearm_at = boundary * (1.0 - reset_pct / 100.0)
            recovered = price <= rearm_at
        else:
            rearm_at = boundary * (1.0 + reset_pct / 100.0)
            recovered = price >= rearm_at
        if recovered:
            return _suppressed("rearmed", next_armed=True, armed_changed=True)
        return _suppressed("awaiting_reset", next_armed=False)

    if not condition_met:
        return _suppressed("condition_not_met", next_armed=True)

    return Decision(
        should_fire=True,
        event_type="price_cross",
        explanation=_explain_price_cross(rule, symbol, price, boundary, direction),
        observed_value=price,
        boundary_value=boundary,
        comparison_value=None,
        window_label=None,
        next_armed=False,
        armed_changed=True,
        extra={"direction": direction},
    )


def _evaluate_percent_move(
    rule: dict[str, Any], params: dict[str, Any], obs: dict[str, Any], armed: bool
) -> Decision:
    price = _positive_price(obs.get("price"))
    if price is None:
        return _suppressed("no_price", next_armed=armed)

    past_price = _positive_price(obs.get("past_price"))
    if past_price is None:
        # Genuinely missing comparison data — record, never fabricate.
        return _suppressed("no_comparison_price", next_armed=armed)

    threshold = _num(params.get("threshold"))
    window = str(params.get("window") or "").lower()
    if threshold is None or threshold <= 0 or window not in WINDOW_SECONDS:
        return _suppressed("invalid_rule_params", next_armed=armed)

    direction = str(params.get("direction") or "").lower()
    symbol = str(rule.get("symbol") or "").upper()

    move_pct = ((price - past_price) / past_price) * 100.0

    if direction == "up":
        magnitude = move_pct
    elif direction == "down":
        magnitude = -move_pct
    else:
        magnitude = abs(move_pct)

    rearm_ratio = _num(rule.get("percent_rearm_ratio"))
    if rearm_ratio is None or not (0 < rearm_ratio < 1):
        rearm_ratio = DEFAULT_PERCENT_REARM_RATIO

    if not armed:
        # The same rolling window stays true for a long time, so cooldown
        # alone would re-fire the identical move. Require decay first.
        if magnitude < threshold * rearm_ratio:
            return _suppressed("rearmed", next_armed=True, armed_changed=True)
        return _suppressed("awaiting_reset", next_armed=False)

    if magnitude < threshold:
        return _suppressed("condition_not_met", next_armed=True)

    return Decision(
        should_fire=True,
        event_type="percent_move",
        explanation=_explain_percent_move(
            rule, symbol, move_pct, threshold, window, price, past_price
        ),
        observed_value=price,
        boundary_value=threshold,
        comparison_value=past_price,
        window_label=window,
        next_armed=False,
        armed_changed=True,
        extra={"direction": direction, "move_pct": round(move_pct, 4)},
    )


_EVALUATORS = {
    "price_cross": _evaluate_price_cross,
    "percent_move": _evaluate_percent_move,
}


def evaluate_rule(
    rule: dict[str, Any],
    obs: dict[str, Any],
    *,
    now_ts: float,
) -> Decision:
    """Evaluate one rule against one observation.

    ``rule`` carries persisted state (``status``, ``armed``, ``cooldown_seconds``,
    ``last_triggered_ts``, ``expires_ts``). ``obs`` carries market data
    (``price``, ``price_ts``, and ``past_price`` for rolling windows).

    Ordering matters: lifecycle gates run before market conditions so a paused
    or expired rule never touches price data, and stale data never fires.
    """
    status = str(rule.get("status") or "active").strip().lower()
    armed = bool(rule.get("armed", True))

    # A cooling-down rule must still be evaluated — that is the only path by
    # which it observes the reset boundary and re-arms. Short-circuiting it
    # here would strand every recurring rule permanently after its first fire.
    if status not in EVALUABLE_STATUSES:
        return _suppressed(f"rule_{status}", next_armed=armed)

    expires_ts = _num(rule.get("expires_ts"))
    if expires_ts is not None and now_ts >= expires_ts:
        return _suppressed("rule_expired", next_armed=armed)

    trigger_type = str(rule.get("trigger_type") or "").strip().lower()
    evaluator = _EVALUATORS.get(trigger_type)
    if evaluator is None:
        return _suppressed("unsupported_trigger_type", next_armed=armed)

    params = rule.get("params")
    if not isinstance(params, dict):
        return _suppressed("invalid_rule_params", next_armed=armed)

    # Stale market data must never trigger an alert.
    price_ts = _num(obs.get("price_ts"))
    max_age = _num(rule.get("max_price_age_seconds")) or MAX_PRICE_AGE_SECONDS
    if price_ts is not None and (now_ts - price_ts) > max_age:
        return _suppressed("stale_price", next_armed=armed)

    decision = evaluator(rule, params, obs, armed)

    # Cooldown applies only to an otherwise-firing decision, so re-arm
    # bookkeeping still happens while a rule is cooling down.
    if decision.should_fire:
        cooldown = _num(rule.get("cooldown_seconds"))
        if cooldown is None or cooldown < 0:
            cooldown = DEFAULT_COOLDOWN_SECONDS.get(trigger_type, 3_600)
        floor = MIN_COOLDOWN_SECONDS.get(trigger_type, 0)
        cooldown = max(cooldown, floor)

        last_ts = _num(rule.get("last_triggered_ts"))
        if last_ts is not None and (now_ts - last_ts) < cooldown:
            return _suppressed(
                "cooldown",
                next_armed=decision.next_armed,
                armed_changed=decision.armed_changed,
            )

    return decision
