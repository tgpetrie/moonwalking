"""Cycle Strategist: turns the multi-year cycle read into trade proposals.

Each run reads the universe cycle scan (``scan_universe_cycles``), any
per-coin ``multi_year_context`` reads and the held positions, then emits
deterministic proposals:

- ``TRIM_TO_USDC``        held coin inside its 0.618-0.786 rollover box, or
                          pressing an overhead 50W/100W average, while the
                          liquidity rotation is still Stage 1 or 2
- ``PROTECTIVE_STOP``     held coin has lost its daily higher-low floor, or is
                          close to its accumulation invalidation stop
- ``ACCUMULATE_SUPPORT``  deep accumulation exhaustion (18+ bearish months,
                          weekly StochRSI turning up under 25, daily MACD kiss
                          or divergence) with a stop no more than 10% away
- ``BREAKOUT_ENTRY``      recent close above the low-confirmation pivot with
                          weekly RSI above 60
- ``RELOAD_ACCUMULATE``   a coin with an approved or dry-run executed trim has
                          fallen to an unfilled rung of that trim's reload
                          ladder, with weekly StochRSI turning up under 25 or
                          a daily MACD kiss
- ``ROTATE_TO_LEADER``    a weak held coin paired with a top-ranked
                          accumulation or breakout candidate whose reward to
                          risk is at least 3

Every ``TRIM_TO_USDC`` carries a ``reload_plan``: the USDC the trim frees, split
25/35/40 across lower support levels, and the coins that ladder would buy back.
Entries need a reward-to-risk ratio of at least 2 against the active target
midpoint and carry a suggested size from the stage-scaled risk budget, capped
by the open-risk (portfolio heat) limit.

Proposals are stored in ``AgentStore``. In ``approval_queue`` mode every
proposal waits for approval. In ``auto_protect_exits`` mode, trims and
protective stops run through ``GuardedDryRunExitExecutor``; entries, reloads
and rotations always wait for approval.
Nothing here can submit an exchange order: ``live_guarded`` is recorded as a
setting but blocks automatic execution because no live route exists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import time
from typing import Any, Callable, Mapping

from .contracts import AgentObservation, json_safe
from .cycle_context import (
    _finite as _num,
    normalize_positions,
    normalize_watchlist,
    usable_cycle_scan,
)
from .store import AgentStore


TRIM_TO_USDC = "TRIM_TO_USDC"
PROTECTIVE_STOP = "PROTECTIVE_STOP"
ACCUMULATE_SUPPORT = "ACCUMULATE_SUPPORT"
BREAKOUT_ENTRY = "BREAKOUT_ENTRY"
RELOAD_ACCUMULATE = "RELOAD_ACCUMULATE"
ROTATE_TO_LEADER = "ROTATE_TO_LEADER"
# Only these can reach the dry-run executor. A rotation sells too, but it also
# buys, so it always waits for approval.
EXIT_ACTIONS = frozenset({TRIM_TO_USDC, PROTECTIVE_STOP})
ENTRY_ACTIONS = frozenset({ACCUMULATE_SUPPORT, BREAKOUT_ENTRY, RELOAD_ACCUMULATE})

TRIM_STAGES = frozenset({"stage_1_macro_compression", "stage_2_btc_majors_lead"})
TRIM_MIN_PCT = 25.0
TRIM_MAX_PCT = 50.0
SMA_TOUCH_PCT = 2.0  # within this much of an overhead 50W/100W average
STOP_APPROACH_PCT = 3.0
ACCUMULATION_MIN_STREAK = 18
ACCUMULATION_MAX_STOP_PCT = 10.0
BREAKOUT_MIN_WEEKLY_RSI = 60.0

# Reload ladder: share of the freed USDC per rung, shallowest rung first.
RELOAD_WEIGHTS = (0.25, 0.35, 0.40)
RELOAD_FIB_RATIOS = ("0.618", "0.702", "0.786")
RELOAD_MIN_DISCOUNT_PCT = 1.0  # a rung sits at least this far under the trim price
RELOAD_LEVEL_MERGE_PCT = 1.0  # candidate levels closer than this count as one rung
CYCLE_LOW_BUFFER_PCT = 2.0  # same buffer the scanner puts under a structural low

# Reward to risk, sizing and heat.
MIN_ENTRY_RR = 2.0
ROTATION_MIN_RR = 3.0
BASE_RISK_PCT = 1.0  # equity risked per entry before the stage multiplier
MAX_OPEN_RISK_PCT = 5.0
MAX_POSITION_PCT = 25.0  # one entry never exceeds this share of equity
HEAT_ASSUMED_STOP_PCT = 10.0  # risk assumed for a held coin with no usable stop
STAGE_RISK_MULTIPLIER = {
    "stage_1_macro_compression": 0.5,
    "stage_2_btc_majors_lead": 0.75,
    "stage_3_alt_index_breakout": 1.0,
    "stage_4_alt_season_expansion": 1.0,
}
UNKNOWN_STAGE_RISK_MULTIPLIER = 0.5

# Rotation.
ROTATION_TRIM_PCT = 25.0
LAGGARD_MAX_WEEKLY_RSI = 45.0
LEADER_BUCKETS = ("deep_accumulation_exhaustion", "low_confirmation_breakout")
LEADER_TOP_N = 3

SEVERITY = {
    PROTECTIVE_STOP: "critical",
    TRIM_TO_USDC: "warning",
    RELOAD_ACCUMULATE: "warning",
    ACCUMULATE_SUPPORT: "watch",
    BREAKOUT_ENTRY: "watch",
    ROTATE_TO_LEADER: "watch",
}


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


@dataclass
class TradeProposal:
    action: str
    symbol: str
    side: str
    reference_price: float
    reasons: list[str]
    proposal_id: str = ""
    agent: str = "cycle_strategist"
    status: str = "pending_approval"
    trim_pct: float | None = None
    stop_price: float | None = None
    stage: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    target_price: float | None = None
    reward_to_risk_ratio: float | None = None
    sizing: dict[str, Any] | None = None
    reload_plan: dict[str, Any] | None = None
    pair: dict[str, Any] | None = None

    @property
    def product_id(self) -> str:
        return f"{self.symbol}-USD"

    def to_record(self) -> dict[str, Any]:
        record = json_safe(asdict(self))
        record["product_id"] = self.product_id
        return record


def proposal_id(action: str, symbol: str, now_ts: float) -> str:
    """Same action, coin and UTC day always map to the same proposal."""
    day = datetime.fromtimestamp(now_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha1(f"{action}|{symbol}|{day}".encode()).hexdigest()[:16]


# ─── inputs ──────────────────────────────────────────────────────────────────


def _scan_from_context(context: Mapping[str, Any]) -> dict[str, Any] | None:
    scan = context.get("cycle_scan")
    if scan is not None:
        return scan if usable_cycle_scan(scan, now=_num(context.get("now_ts"))) else None
    histories = context.get("cycle_histories")
    if isinstance(histories, dict) and histories:
        try:
            from macro_industry_scanner import scan_universe_cycles
        except ImportError:
            from backend.macro_industry_scanner import scan_universe_cycles
        scan = scan_universe_cycles(histories)
        return scan if usable_cycle_scan(scan) else None
    return None


def _multi_year(context: Mapping[str, Any], row: dict, symbol: str) -> dict[str, Any]:
    scan_fields = row.get("multi_year_context")
    scan_fields = scan_fields if isinstance(scan_fields, dict) else {}
    supplied = context.get("multi_year_contexts")
    if isinstance(supplied, dict):
        found = supplied.get(symbol) or supplied.get(f"{symbol}-USD")
        if isinstance(found, dict):
            return {**scan_fields, **found}
    return scan_fields


def daily_higher_low_floor(candles: list[list[Any]] | None) -> float | None:
    """Latest point of the daily rising-floor chain, if the chart has one."""
    if not candles:
        return None
    try:
        from chart_structure import swing_history
        from elliott_wave_engine import detect_pivots
    except ImportError:
        from backend.chart_structure import swing_history
        from backend.elliott_wave_engine import detect_pivots
    bars = sorted((list(bar) for bar in candles), key=lambda bar: bar[0])
    pivots = [
        {"ts": p.ts, "price": p.price, "kind": p.kind} for p in detect_pivots(bars)
    ]
    floor = swing_history(pivots, _num(bars[-1][4])).get("floor")
    if not floor or not floor.get("points"):
        return None
    return _num(floor["points"][-1]["price"])


def _floor_for(context: Mapping[str, Any], position: Mapping[str, Any], symbol: str, multi_year: dict):
    explicit = _num(position.get("higher_low_floor"))
    if explicit is not None and explicit > 0:
        return explicit
    floors = context.get("higher_low_floors")
    if isinstance(floors, dict):
        value = _num(floors.get(symbol))
        if value is not None and value > 0:
            return value
    daily = multi_year.get("daily_structure")
    if isinstance(daily, dict):
        floor = _num(daily.get("higher_low_floor"))
        if floor is not None and floor > 0:
            return floor
    histories = context.get("cycle_histories")
    if isinstance(histories, dict) and "daily_structure" not in multi_year:
        return daily_higher_low_floor(histories.get(f"{symbol}-USD"))
    return None


def _positions(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["symbol"]: row for row in normalize_positions(context.get("positions"))}


# ─── rules ───────────────────────────────────────────────────────────────────


def _overhead_sma(ladder: Mapping[str, Any], price: float) -> dict[str, Any] | None:
    for period in (50, 100):
        value = _num(ladder.get(f"sma_{period}w"))
        if value is None or value <= 0:
            continue
        gap = (value / price - 1.0) * 100.0
        if 0 <= gap <= SMA_TOUCH_PCT:
            return {"key": f"sma_{period}w", "value": value, "gap_pct": _round(gap)}
    return None


def evaluate_trim(row, multi_year, stage, price) -> TradeProposal | None:
    if stage not in TRIM_STAGES:
        return None
    reasons, evidence = [], {}
    trim = None
    box = row.get("rollover_target_box") or multi_year.get("rollover_target_box") or {}
    low, high = _num(box.get("low")), _num(box.get("high"))
    if low is not None and high is not None and 0 < low < high and low <= price <= high:
        depth = (price - low) / (high - low)
        trim = TRIM_MIN_PCT + (TRIM_MAX_PCT - TRIM_MIN_PCT) * depth
        reasons.append("Price is inside the 0.618-0.786 rollover target box.")
        evidence["rollover_target_box"] = {"low": low, "high": high}
    sma = _overhead_sma(multi_year.get("weekly_sma_ladder") or {}, price)
    if sma:
        trim = TRIM_MAX_PCT if trim is not None else TRIM_MIN_PCT
        reasons.append(f"Price is pressing the overhead {sma['key']}.")
        evidence["overhead_sma"] = sma
    if trim is None:
        return None
    reasons.append(f"Liquidity rotation is {stage}; trim to USDC to rebuy lower.")
    return TradeProposal(
        action=TRIM_TO_USDC,
        symbol=row["symbol"],
        side="sell",
        reference_price=price,
        trim_pct=round(trim, 1),
        stage=stage,
        reasons=reasons,
        evidence=evidence,
    )


def evaluate_protective_stop(row, floor, price, position_stop=None) -> TradeProposal | None:
    stop = row.get("accumulation_invalidation_stop") or {}
    stop_price = _num(position_stop)
    position_guard = stop_price is not None and stop_price > 0
    if not position_guard:
        stop_price = _num(stop.get("stop_price"))
    if floor is not None and price < floor and (stop_price is None or floor >= stop_price):
        trigger, level = "higher_low_floor_breached", floor
        message = "Price closed below the daily higher-low floor."
    elif stop_price is not None and 0 < stop_price and price <= stop_price:
        trigger, level = "invalidation_stop_breached", stop_price
        detail = "the position stop" if position_guard else "the accumulation invalidation stop"
        message = f"Price closed at or below {detail}."
    elif stop_price is not None and price * (1 - STOP_APPROACH_PCT / 100) <= stop_price:
        trigger, level = "invalidation_stop_near", stop_price
        detail = "the position stop" if position_guard else "the accumulation invalidation stop"
        distance = (price - stop_price) / price * 100
        message = f"Price is {distance:.2f}% above {detail}."
    else:
        return None
    return TradeProposal(
        action=PROTECTIVE_STOP,
        symbol=row["symbol"],
        side="sell",
        reference_price=price,
        trim_pct=100.0,
        stop_price=level,
        reasons=[message],
        evidence={
            "trigger": trigger,
            "stop_distance_pct": _round((price - level) / price * 100),
            "floor": floor,
        },
    )


def evaluate_accumulate(row, price) -> TradeProposal | None:
    stop = row.get("accumulation_invalidation_stop") or {}
    stop_price = _num(stop.get("stop_price"))
    streak = _num(row.get("monthly_bearish_streak"))
    daily_divergence = row.get("daily_bullish_divergence")
    macro_divergence = row.get("macro_bullish_divergence")
    if not (
        row.get("bucket") == "deep_accumulation_exhaustion"
        and row.get("multi_year_oversold_exhaustion") is True
        and streak is not None and streak.is_integer() and streak >= ACCUMULATION_MIN_STREAK
        and row.get("weekly_stoch_direction") == "oversold_turn_up"
        and (row.get("daily_macd_kiss") or daily_divergence or macro_divergence)
        and stop_price is not None and price * (1 - ACCUMULATION_MAX_STOP_PCT / 100) <= stop_price < price
    ):
        return None
    streak = int(streak)
    distance = (price - stop_price) / price * 100
    momentum = (
        "daily MACD kiss" if row.get("daily_macd_kiss")
        else "daily bullish divergence" if daily_divergence
        else "macro bullish divergence"
    )
    return TradeProposal(
        action=ACCUMULATE_SUPPORT,
        symbol=row["symbol"],
        side="buy",
        reference_price=price,
        stop_price=stop_price,
        reasons=[
            f"{streak} bearish months with weekly StochRSI turning up under 25.",
            f"Momentum confirmation: {momentum}.",
            f"Invalidation stop is {distance:.2f}% away.",
        ],
        evidence={
            "monthly_bearish_streak": streak,
            "stop_distance_pct": _round(distance),
            "daily_bullish_divergence": bool(daily_divergence),
            "daily_macd_kiss": bool(row.get("daily_macd_kiss")),
            "macro_bullish_divergence": bool(row.get("macro_bullish_divergence")),
        },
    )


def evaluate_breakout(row, price) -> TradeProposal | None:
    rsi = _num(row.get("weekly_rsi"))
    if not (row.get("breaking_confirmation_pivot") and rsi is not None):
        return None
    regime = row.get("weekly_rsi_regime")
    expanding = regime == "growth_expansion" if regime is not None else rsi > BREAKOUT_MIN_WEEKLY_RSI
    if not expanding:
        return None
    stop = row.get("accumulation_invalidation_stop") or {}
    return TradeProposal(
        action=BREAKOUT_ENTRY,
        symbol=row["symbol"],
        side="buy",
        reference_price=price,
        stop_price=_num(stop.get("stop_price")),
        reasons=[
            "Recent daily close above the low-confirmation pivot.",
            f"Weekly RSI {rsi:.1f} is in growth expansion.",
        ],
        evidence={"weekly_rsi": rsi, "low_confirmation_pivot": row.get("low_confirmation_pivot")},
    )


# ─── reload ladder ───────────────────────────────────────────────────────────


def _reload_candidates(row, multi_year, floor) -> list[tuple[float, str]]:
    """Support levels in preference order: Fib box, daily floor, clusters."""
    out: list[tuple[float, str]] = []
    levels = row.get("support_levels")
    levels = levels if isinstance(levels, Mapping) else {}
    for ratio in RELOAD_FIB_RATIOS:
        level = _num(levels.get(ratio))
        if level is not None:
            out.append((level, f"log_fib_{ratio}"))
    if floor is not None:
        out.append((floor, "daily_higher_low_floor"))
    mids = row.get("fib_cluster_mids")
    if not isinstance(mids, list):
        clusters = multi_year.get("fib_confluence_clusters")
        mids = (
            [c.get("mid") for c in clusters if isinstance(c, Mapping)]
            if isinstance(clusters, list) else []
        )
    nearest_first = sorted((m for m in map(_num, mids) if m is not None), reverse=True)
    out.extend((mid, "fib_confluence_cluster") for mid in nearest_first)
    return out


def build_reload_plan(row, multi_year, price, trim_quantity, held_quantity, floor=None) -> dict[str, Any]:
    """Split a trim's USDC across lower support levels and count the coins bought back.

    The figures assume each rung fills at its level and leave out fees and
    slippage. They describe a plan; nothing is ordered.
    """
    freed = trim_quantity * price
    stop = _num((row.get("accumulation_invalidation_stop") or {}).get("stop_price"))
    cycle_low = _num(row.get("cycle_low"))
    if stop is not None and 0 < stop < price:
        invalidation, basis = stop, "accumulation_invalidation_stop"
    elif cycle_low is not None and 0 < cycle_low < price:
        invalidation, basis = cycle_low * (1 - CYCLE_LOW_BUFFER_PCT / 100), "cycle_low"
    else:
        invalidation, basis = None, None
    ceiling = price * (1 - RELOAD_MIN_DISCOUNT_PCT / 100)
    chosen: list[tuple[float, str]] = []
    for level, source in _reload_candidates(row, multi_year, floor):
        if not (invalidation or 0) < level <= ceiling:
            continue
        if any(abs(level / kept - 1) * 100 < RELOAD_LEVEL_MERGE_PCT for kept, _ in chosen):
            continue
        chosen.append((level, source))
        if len(chosen) == len(RELOAD_WEIGHTS):
            break
    plan: dict[str, Any] = {
        "available": bool(chosen),
        "reference_price": price,
        "trim_quantity": trim_quantity,
        "freed_usdc": _round(freed, 2),
        "invalidation_stop": invalidation,
        "invalidation_basis": basis,
        "fresh_cash_usd": 0.0,
        "assumptions": "Each rung fills at its level. Fees and slippage are not included.",
    }
    if not chosen:
        plan["reason"] = "no_support_level_between_stop_and_price"
        return plan
    chosen.sort(reverse=True)
    weights = RELOAD_WEIGHTS[: len(chosen)]
    total = sum(weights)
    tranches, coins = [], 0.0
    for index, ((level, source), weight) in enumerate(zip(chosen, weights), start=1):
        usdc = freed * weight / total
        coins += usdc / level
        tranches.append({
            "index": index,
            "weight_pct": _round(weight / total * 100),
            "level": level,
            "basis": source,
            "usdc": _round(usdc, 2),
            "coins": usdc / level,
            "discount_pct": _round((1 - level / price) * 100),
        })
    gain = coins - trim_quantity
    plan.update(
        tranches=tranches,
        average_reload_price=freed / coins,
        projected_reloaded_coins=coins,
        net_coin_gain_qty=gain,
        # Growth of the whole stack: coins held after the round trip against before.
        net_coin_gain_pct=_round(gain / held_quantity * 100),
        reloaded_vs_trimmed_pct=_round(gain / trim_quantity * 100),
    )
    return plan


def evaluate_reload(row, price, plans) -> TradeProposal | None:
    """A rebuy for unfilled reload rungs that price has reached, on a momentum turn."""
    stoch_turn = row.get("weekly_stoch_direction") == "oversold_turn_up"
    kiss = row.get("daily_macd_kiss") is True
    if not (stoch_turn or kiss):
        return None
    fills, pool, remaining, invalidations = [], 0.0, 0.0, []
    for plan in plans or []:
        invalidation = _num(plan.get("invalidation_stop"))
        if invalidation is not None and price <= invalidation:
            continue  # this plan's support has failed
        for tranche in plan.get("tranches") or []:
            level, usdc = _num(tranche.get("level")), _num(tranche.get("usdc"))
            if tranche.get("filled") or level is None or usdc is None or usdc <= 0:
                continue
            remaining += usdc
            if price <= level:
                fills.append({
                    "plan_id": plan.get("plan_id"),
                    "tranche": tranche.get("index"),
                    "level": level,
                    "usdc": usdc,
                })
                pool += usdc
                if invalidation is not None:
                    invalidations.append(invalidation)
    if not fills:
        return None
    stop = _num((row.get("accumulation_invalidation_stop") or {}).get("stop_price"))
    if stop is None or not 0 < stop < price:
        stop = max(invalidations) if invalidations else None
    trigger = "weekly StochRSI turning up under 25" if stoch_turn else "daily MACD kiss"
    return TradeProposal(
        action=RELOAD_ACCUMULATE,
        symbol=row["symbol"],
        side="buy",
        reference_price=price,
        stop_price=stop,
        reasons=[
            f"Price has reached {len(fills)} unfilled reload rung(s) from an earlier trim.",
            f"Momentum confirmation: {trigger}.",
            f"Funded by ${pool:,.2f} of USDC that trim freed; no fresh cash.",
        ],
        evidence={
            "reload_fills": fills,
            "reload_pool_usdc": _round(pool, 2),
            "reload_pool_remaining_usdc": _round(remaining, 2),
            "weekly_stoch_turning_up": stoch_turn,
            "daily_macd_kiss": kiss,
        },
    )


# ─── reward to risk, sizing and heat ─────────────────────────────────────────


def active_target(row) -> dict[str, Any] | None:
    """The tier the industry stage selects, falling back to the rollover box."""
    tiers = (row.get("active_target_tier"), "rollover_target_box")
    for tier in dict.fromkeys(tiers):
        if tier not in ("rollover_target_box", "full_extension_targets"):
            continue
        box = row.get(tier)
        if not isinstance(box, Mapping):
            continue
        low, high = _num(box.get("low")), _num(box.get("high"))
        if low is not None and high is not None and 0 < low <= high:
            return {"tier": tier, "low": low, "high": high, "mid": (low + high) / 2}
    return None


def reward_to_risk(price, stop, target) -> float | None:
    """Distance up to the target midpoint over distance down to the stop."""
    price, stop, target = _num(price), _num(stop), _num(target)
    if price is None or stop is None or target is None or not 0 < stop < price < target:
        return None
    return (target - price) / (price - stop)


def _setting(context, key, default) -> float:
    value = _num(context.get(key))
    return value if value is not None and 0 < value <= 100 else default


def portfolio_heat(context, held, rows, floors) -> dict[str, Any]:
    """Open risk across held coins: the loss if every stop is hit.

    A held coin with no stop under its price is counted at
    ``HEAT_ASSUMED_STOP_PCT``. Equity is the supplied figure, or the marked
    value of the held coins when none is given; that leaves cash out and so
    overstates heat.
    """
    risk = value = 0.0
    assumed, unpriced = [], []
    for symbol in sorted(held):
        position, row = held[symbol], rows.get(symbol) or {}
        price = _num(row.get("price"))
        if price is None or price <= 0:
            unpriced.append(symbol)
            continue
        quantity = position["quantity"]
        value += quantity * price
        stops = (
            _num(position.get("stop_price")),
            floors.get(symbol),
            _num((row.get("accumulation_invalidation_stop") or {}).get("stop_price")),
        )
        usable = [stop for stop in stops if stop is not None and 0 < stop < price]
        if usable:
            risk += quantity * (price - max(usable))
        else:
            assumed.append(symbol)
            risk += quantity * price * HEAT_ASSUMED_STOP_PCT / 100
    supplied = _num(context.get("portfolio_equity_usd"))
    if supplied is not None and supplied > 0:
        equity, basis = supplied, "supplied"
    elif value > 0:
        equity, basis = value, "held_positions_mark"
    else:
        equity, basis = None, None
    return {
        "equity_usd": _round(equity, 2),
        "equity_basis": basis,
        "open_risk_usd": _round(risk, 2),
        "open_risk_pct": _round(risk / equity * 100) if equity else None,
        "max_open_risk_pct": _setting(context, "max_open_risk_pct", MAX_OPEN_RISK_PCT),
        "assumed_stop_symbols": assumed,
        "unpriced_symbols": unpriced,
        "reserved_pct": 0.0,
    }


def size_entry(price, stop, stage, heat, base_risk_pct, *, funded_usd=None) -> dict[str, Any]:
    """Suggested size from the stage-scaled risk budget, inside the heat cap.

    ``heat["reserved_pct"]`` accumulates the risk of entries already sized in
    this pass, so several proposals cannot each claim the same headroom.
    ``funded_usd`` caps the size at money a trim already freed.
    """
    multiplier = STAGE_RISK_MULTIPLIER.get(stage, UNKNOWN_STAGE_RISK_MULTIPLIER)
    budget = base_risk_pct * multiplier
    stop_fraction = (price - stop) / price
    out: dict[str, Any] = {
        "base_risk_pct": base_risk_pct,
        "stage_multiplier": multiplier,
        "risk_budget_pct": _round(budget, 3),
        "stop_distance_pct": _round(stop_fraction * 100),
        "max_open_risk_pct": heat["max_open_risk_pct"],
        "open_risk_pct": heat["open_risk_pct"],
        "equity_basis": heat["equity_basis"],
        "heat_capped": False,
        "position_capped": False,
        "suggested_notional_usd": None,
        "suggested_quantity": None,
        "risk_at_stop_usd": None,
    }
    equity = heat["equity_usd"]
    if equity is None:
        out["note"] = "equity_unknown"
        notional = funded_usd
    else:
        headroom = max(
            0.0, heat["max_open_risk_pct"] - heat["open_risk_pct"] - heat["reserved_pct"]
        )
        if budget > headroom:
            budget, out["heat_capped"] = headroom, True
        notional = equity * budget / 100 / stop_fraction
        ceiling = equity * MAX_POSITION_PCT / 100
        if notional > ceiling:
            notional, out["position_capped"] = ceiling, True
        if funded_usd is not None:
            notional = min(notional, funded_usd)
        used = notional * stop_fraction / equity * 100
        heat["reserved_pct"] += used
        out["risk_budget_pct"] = _round(used, 3)
    if funded_usd is not None:
        out["funded_usd"] = _round(funded_usd, 2)
    if notional is not None:
        out.update(
            suggested_notional_usd=_round(notional, 2),
            suggested_quantity=notional / price,
            risk_at_stop_usd=_round(notional * stop_fraction, 2),
        )
    return out


# ─── pair rotation ───────────────────────────────────────────────────────────


def is_laggard(row) -> bool:
    """Below the 50-week average with weak weekly RSI and nothing turning up."""
    rsi = _num(row.get("weekly_rsi"))
    return bool(
        row.get("above_50w_sma") is False
        and rsi is not None and rsi < LAGGARD_MAX_WEEKLY_RSI
        and not row.get("daily_bullish_divergence")
        and not row.get("macro_bullish_divergence")
        and not row.get("at_multi_year_support")
        and row.get("bucket") != "deep_accumulation_exhaustion"
    )


def rank_leaders(rows, stop_for, excluded=()) -> list[dict[str, Any]]:
    """Top-ranked accumulation and breakout coins with reward to risk of 3 or more.

    ``stop_for(symbol, price)`` supplies each candidate's stop, or ``None``.
    """
    leaders = []
    for bucket in LEADER_BUCKETS:
        ranked = sorted(
            (row for row in rows.values() if row.get("bucket") == bucket),
            key=lambda row: (-(_num(row.get("score")) or 0.0), row["symbol"]),
        )
        for rank, row in enumerate(ranked[:LEADER_TOP_N], start=1):
            symbol, price = row["symbol"], _num(row.get("price"))
            if symbol in excluded or price is None or price <= 0:
                continue
            target, stop = active_target(row), stop_for(symbol, price)
            ratio = reward_to_risk(price, stop, target["mid"] if target else None)
            if ratio is None or ratio < ROTATION_MIN_RR:
                continue
            leaders.append({
                "symbol": symbol,
                "product_id": f"{symbol}-USD",
                "bucket": bucket,
                "bucket_rank": rank,
                "reference_price": price,
                "stop_price": stop,
                "target_price": target["mid"],
                "target_tier": target["tier"],
                "reward_to_risk_ratio": _round(ratio),
            })
    leaders.sort(
        key=lambda lead: (lead["bucket_rank"], -lead["reward_to_risk_ratio"], lead["symbol"])
    )
    return leaders


def evaluate_rotation(row, price, quantity, leader) -> TradeProposal:
    freed = quantity * ROTATION_TRIM_PCT / 100 * price
    return TradeProposal(
        action=ROTATE_TO_LEADER,
        symbol=row["symbol"],
        side="sell",
        reference_price=price,
        trim_pct=ROTATION_TRIM_PCT,
        target_price=leader["target_price"],
        reward_to_risk_ratio=leader["reward_to_risk_ratio"],
        reasons=[
            f"{row['symbol']} is under its 50-week average with weekly RSI "
            f"{_num(row.get('weekly_rsi')):.1f} and no bullish divergence.",
            f"{leader['symbol']} ranks #{leader['bucket_rank']} in {leader['bucket']} "
            f"with reward to risk {leader['reward_to_risk_ratio']:.2f}.",
            f"Rotate {ROTATION_TRIM_PCT:g}% of {row['symbol']} into {leader['symbol']}.",
        ],
        evidence={"weekly_rsi": _num(row.get("weekly_rsi")), "above_50w_sma": False},
        pair={
            "sell_symbol": row["symbol"],
            "sell_product_id": f"{row['symbol']}-USD",
            "buy_symbol": leader["symbol"],
            "buy_product_id": leader["product_id"],
            "freed_usd": _round(freed, 2),
            "leader": leader,
        },
    )


# ─── guarded dry-run exits ───────────────────────────────────────────────────


class GuardedDryRunExitExecutor:
    """Model a sell using a recent, uncrossed two-sided book. Never submits orders."""

    def __init__(
        self,
        *,
        max_quote_age_ms: int = 15_000,
        max_quote_deviation_pct: float = 2.0,
        max_spread_pct: float = 1.0,
        slippage_bps: float = 10.0,
        max_clock_skew_ms: int = 2_000,
    ):
        """``max_clock_skew_ms`` is how far Coinbase's book time may run ahead
        of this machine's clock. Live books arrive stamped up to about half a
        second after local receipt on an ordinary PC clock; with 0 every one of
        them is refused. A book further ahead than this is still refused."""
        age = _num(max_quote_age_ms)
        skew = _num(max_clock_skew_ms)
        deviation, spread, slippage = map(_num, (max_quote_deviation_pct, max_spread_pct, slippage_bps))
        if (
            age is None or age <= 0 or deviation is None or not 0 <= deviation <= 100
            or spread is None or not 0 <= spread <= 100
            or slippage is None or not 0 <= slippage < 10_000
            or skew is None or not 0 <= skew <= age
        ):
            raise ValueError("invalid dry-run guard parameters")
        self.max_quote_age_ms = age
        self.max_clock_skew_ms = skew
        self.max_quote_deviation_pct = deviation
        self.max_spread_pct = spread
        self.slippage_bps = slippage

    def quote_guard(self, quote, reference_price, quantity, now_ms) -> list[str]:
        if not isinstance(quote, dict) or quote.get("quote_status") not in (None, "AVAILABLE"):
            return ["quote_unavailable"]
        bid = _num(quote.get("bid_usd"))
        ask = _num(quote.get("ask_usd"))
        observed = _num(quote.get("observed_at_ms"))
        exchange = _num(quote.get("exchange_time_ms"))
        now = _num(now_ms)
        reasons = []
        if bid is None or bid <= 0:
            reasons.append("quote_missing_bid")
        if ask is None or ask <= 0:
            reasons.append("quote_missing_ask")
        if bid is not None and bid > 0 and ask is not None and ask > 0:
            if ask < bid:
                reasons.append("quote_crossed_book")
            elif (ask - bid) / (bid + (ask - bid) / 2) * 100 > self.max_spread_pct:
                reasons.append("quote_spread_too_wide")
        if observed is None or now is None or not 0 <= now - observed <= self.max_quote_age_ms:
            reasons.append("quote_stale")
        if exchange is None:
            reasons.append("quote_missing_exchange_timestamp")
        elif (
            now is None or observed is None
            or exchange > observed + self.max_clock_skew_ms
            or not -self.max_clock_skew_ms <= now - exchange <= self.max_quote_age_ms
        ):
            reasons.append("exchange_book_stale")
        reference = _num(reference_price)
        if reference is None or reference <= 0:
            reasons.append("invalid_reference_price")
        elif bid is not None and bid > 0 and abs(bid / reference - 1.0) * 100 > self.max_quote_deviation_pct:
            reasons.append("quote_deviates_from_reference")
        quantity = _num(quantity)
        size = _num(quote.get("bid_size"))
        if quantity is None or quantity <= 0:
            reasons.append("invalid_exit_quantity")
        if size is None:
            reasons.append("quote_missing_bid_size")
        elif quantity is not None and size < quantity:
            reasons.append("insufficient_top_of_book_size")
        return reasons

    def execute(self, proposal: TradeProposal, position, quote, now_ms) -> dict:
        def blocked(*reasons):
            return {"status": "blocked_by_guard", "block_reasons": list(reasons)}

        if proposal.action not in EXIT_ACTIONS or proposal.side != "sell":
            return blocked("exit_only")
        held_quantity = _num(position.get("quantity"))
        trim = _num(proposal.trim_pct)
        if held_quantity is None or held_quantity <= 0 or trim is None or not 0 < trim <= 100:
            return blocked("invalid_exit_quantity")
        quantity = held_quantity * (trim / 100)
        if isinstance(quote, dict) and quote.get("product_id") not in (None, proposal.product_id):
            return blocked("quote_product_mismatch")
        blocks = self.quote_guard(quote, proposal.reference_price, quantity, now_ms)
        if blocks:
            return blocked(*blocks)
        bid = float(quote["bid_usd"])
        if proposal.action == PROTECTIVE_STOP:
            stop = _num(proposal.stop_price)
            if stop is None or stop <= 0:
                return blocked("invalid_stop_price")
            if proposal.evidence.get("trigger") == "invalidation_stop_near":
                if bid <= stop:
                    return blocked("quote_at_or_below_stop")
                return {
                    "status": "auto_armed_dry_run",
                    "dry_run": True,
                    "order_submitted": False,
                    "order_type": "stop_limit_stop_limit_gtc",
                    "stop_price": stop,
                    "base_size": quantity,
                }
            if proposal.evidence.get("trigger") not in {
                "higher_low_floor_breached", "invalidation_stop_breached"
            } or bid > stop:
                return blocked("quote_does_not_confirm_stop_breach")
        fill = bid * (1.0 - self.slippage_bps / 10_000.0)
        proceeds = _num(fill * quantity)
        if proceeds is None or fill <= 0 or proceeds <= 0:
            return blocked("invalid_fill")
        return {
            "status": "auto_executed_dry_run",
            "dry_run": True,
            "order_submitted": False,
            "order_type": "simulated_sell_at_bid",
            "base_size": quantity,
            "bid_usd": bid,
            "fill_price": fill,
            "proceeds_usd": _round(proceeds, 2),
            "slippage_bps": self.slippage_bps,
            "quote_observed_at_ms": quote.get("observed_at_ms"),
        }


# ─── agent ───────────────────────────────────────────────────────────────────


class CycleStrategistAgent:
    """Emits cycle-driven trade proposals and routes guarded dry-run exits."""

    name = "cycle_strategist"
    model_version = "cycle-strategist-rule-v2"

    def __init__(
        self,
        store: AgentStore | None = None,
        *,
        executor: GuardedDryRunExitExecutor | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.store = store
        self.executor = executor or GuardedDryRunExitExecutor()
        self.clock = clock
        self.last_proposals: list[dict] = []
        # Entries the last ``evaluate`` dropped at the reward-to-risk gate, and
        # the open-risk read it sized against.
        self.last_skipped: list[dict] = []
        self.last_heat: dict[str, Any] | None = None

    def bind_store(self, store: AgentStore) -> None:
        self.store = store

    def _reload_plans(self, context: Mapping[str, Any]) -> dict[str, list[dict]]:
        """Open reload plans by symbol, from the context or the ledger."""
        plans = context.get("reload_plans")
        if not isinstance(plans, list):
            plans = self.store.active_reload_plans() if self.store is not None else []
        by_symbol: dict[str, list[dict]] = {}
        for plan in plans:
            symbols = normalize_watchlist([plan.get("symbol")]) if isinstance(plan, dict) else []
            if symbols:
                by_symbol.setdefault(symbols[0], []).append(plan)
        return by_symbol

    def evaluate(self, context: Mapping[str, Any]) -> list[TradeProposal]:
        """Proposals for the current inputs, without routing or persistence."""
        scan = _scan_from_context(context)
        if not scan:
            return []
        industry = scan.get("industry")
        stage = industry.get("liquidity_rotation_stage") if isinstance(industry, dict) else None
        rows = {}
        for row in scan["coins"]:
            if not isinstance(row, dict) or row.get("available") is not True:
                continue
            symbols = normalize_watchlist([row.get("symbol") or row.get("product_id")])
            if symbols:
                rows[symbols[0]] = {**row, "symbol": symbols[0]}
        held = _positions(context)
        watch = set(normalize_watchlist(context.get("watchlist")))
        plans = self._reload_plans(context)
        floors: dict[str, float | None] = {}

        def floor_of(symbol: str) -> float | None:
            if symbol not in floors:
                row = rows[symbol]
                floors[symbol] = _floor_for(
                    context, held.get(symbol, {}), symbol, _multi_year(context, row, symbol)
                )
            return floors[symbol]

        def entry_stop(symbol: str, price: float, preferred: float | None = None) -> float | None:
            """The proposal's own stop, else the scanner's, else the daily floor."""
            scanner = _num((rows[symbol].get("accumulation_invalidation_stop") or {}).get("stop_price"))
            for candidate in (preferred, scanner):
                if candidate is not None and 0 < candidate < price:
                    return candidate
            floor = floor_of(symbol)
            return floor if floor is not None and 0 < floor < price else None

        proposals: list[TradeProposal] = []
        defended = set()
        for symbol in sorted(held):
            row = rows.get(symbol)
            price = _num(row.get("price")) if row else None
            if not row or price is None or price <= 0:
                continue
            position = held[symbol]
            multi_year = _multi_year(context, row, symbol)
            floor = floor_of(symbol)
            stop = evaluate_protective_stop(row, floor, price, position.get("stop_price"))
            if stop:
                proposals.append(stop)
                defended.add(symbol)
                continue  # defend first; a stop is no time to trim or add
            trim = evaluate_trim(row, multi_year, stage, price)
            if trim:
                quantity = position["quantity"]
                trim.reload_plan = build_reload_plan(
                    row, multi_year, price, quantity * trim.trim_pct / 100, quantity, floor
                )
                proposals.append(trim)

        heat = portfolio_heat(
            context, held, rows, {symbol: floor_of(symbol) for symbol in held if symbol in rows}
        )
        base_risk = _setting(context, "base_risk_pct", BASE_RISK_PCT)
        self.last_skipped = []

        entries = []
        for symbol in sorted((watch | set(held) | set(plans)) - defended):
            row = rows.get(symbol)
            price = _num(row.get("price")) if row else None
            if not row or price is None or price <= 0:
                continue
            entry = (
                evaluate_reload(row, price, plans.get(symbol))
                or evaluate_accumulate(row, price)
                or evaluate_breakout(row, price)
            )
            if entry:
                entries.append((entry, row, price))
        # Reloads are already funded, so they take heat headroom first.
        entries.sort(key=lambda item: (item[0].action != RELOAD_ACCUMULATE, item[0].symbol))
        for entry, row, price in entries:
            stop = entry_stop(entry.symbol, price, entry.stop_price)
            target = active_target(row)
            ratio = reward_to_risk(price, stop, target["mid"] if target else None)
            if ratio is None or ratio < MIN_ENTRY_RR:
                self.last_skipped.append({
                    "symbol": entry.symbol,
                    "action": entry.action,
                    "reason": "no_stop_below_price" if stop is None
                    else "no_target_above_price" if ratio is None
                    else "reward_to_risk_below_minimum",
                    "reward_to_risk_ratio": _round(ratio),
                })
                continue
            entry.stage = stage
            entry.stop_price = stop
            entry.target_price = target["mid"]
            entry.reward_to_risk_ratio = _round(ratio)
            entry.evidence["target"] = target
            entry.reasons.append(
                f"Reward to risk {ratio:.2f} to the {target['tier']} midpoint."
            )
            entry.sizing = size_entry(
                price, stop, stage, heat, base_risk,
                funded_usd=entry.evidence.get("reload_pool_usdc")
                if entry.action == RELOAD_ACCUMULATE else None,
            )
            proposals.append(entry)

        laggards = [
            symbol for symbol in sorted(held)
            if symbol not in defended and symbol in rows and is_laggard(rows[symbol])
            and (_num(rows[symbol].get("price")) or 0) > 0
        ]
        if laggards:
            leaders = rank_leaders(rows, entry_stop, excluded=defended)
            for symbol in laggards:
                leader = next((lead for lead in leaders if lead["symbol"] != symbol), None)
                if leader is None:
                    continue
                row = rows[symbol]
                rotation = evaluate_rotation(row, _num(row["price"]), held[symbol]["quantity"], leader)
                rotation.stage = stage
                rotation.sizing = size_entry(
                    leader["reference_price"], leader["stop_price"], stage, heat, base_risk,
                    funded_usd=rotation.pair["freed_usd"],
                )
                proposals.append(rotation)
        self.last_heat = {key: value for key, value in heat.items() if key != "reserved_pct"}
        return proposals

    def _route(self, proposal, settings, held, quotes, now_ms, orders_today):
        if proposal.action not in EXIT_ACTIONS or proposal.side != "sell":
            return "pending_approval", None
        if settings["autonomy_mode"] != "auto_protect_exits":
            return "pending_approval", None
        if settings["emergency_pause"]:
            return "pending_approval", {"held_reason": "emergency_pause"}
        if settings["execution_mode"] != "dry_run":
            return "blocked_by_guard", {"block_reasons": ["live_order_route_unavailable"]}
        if orders_today >= settings["daily_order_cap"]:
            return "blocked_by_guard", {"block_reasons": ["daily_order_cap_reached"]}
        result = self.executor.execute(
            proposal, held[proposal.symbol], quotes.get(proposal.product_id), now_ms
        )
        return result["status"], result

    @staticmethod
    def _fetch_exit_quotes(context, store, proposals, quotes) -> dict[str, Any]:
        """Top-of-book quotes for exits Mode B is about to simulate.

        The context's ``quote_fetcher`` is called here, straight before
        routing, so quotes are seconds old when the guard reads them, and only
        when dry-run auto-exits are switched on. A failed fetch leaves the
        product without a quote, which the guard blocks.
        """
        fetcher = context.get("quote_fetcher")
        if not callable(fetcher):
            return {}
        settings = store.get_autonomy_settings()
        if (
            settings["autonomy_mode"] != "auto_protect_exits"
            or settings["execution_mode"] != "dry_run"
            or settings["emergency_pause"]
        ):
            return {}
        wanted = sorted({
            p.product_id for p in proposals
            if p.action in EXIT_ACTIONS and p.product_id not in quotes
        })
        if not wanted:
            return {}
        try:
            fetched = fetcher(wanted)
        except Exception:
            return {}
        if not isinstance(fetched, Mapping):
            return {}
        return {
            product: quote for product, quote in fetched.items()
            if product in wanted and isinstance(quote, dict)
        }

    def run(self, context: dict | None) -> list[AgentObservation]:
        context = context or {}
        supplied_now = _num(context.get("now_ts"))
        clock = self.clock if supplied_now is None else lambda: supplied_now
        now = clock()
        store = self.store or AgentStore()
        plans = context.get("reload_plans")
        if not isinstance(plans, list):
            # Read open ladders from the ledger this run writes to, bound or not.
            plans = store.active_reload_plans()
        proposals = self.evaluate({**context, "now_ts": now, "reload_plans": plans})
        self.last_proposals = []
        if not proposals:
            return []
        held = _positions(context)
        quotes = dict(context["quotes"]) if isinstance(context.get("quotes"), dict) else {}
        quotes.update(self._fetch_exit_quotes(context, store, proposals, quotes))
        observations = []
        for proposal in proposals:
            proposal.proposal_id = proposal_id(proposal.action, proposal.symbol, now)
            saved, settings = store.route_proposal(
                proposal.to_record(),
                lambda settings, count, decision_ms: self._route(
                    proposal, settings, held, quotes, decision_ms, count
                ),
                clock=clock,
            )
            self.last_proposals.append(saved)
            observations.append(
                AgentObservation(
                    agent=self.name,
                    kind=f"trade_proposal_{proposal.action.lower()}",
                    severity=SEVERITY[proposal.action],
                    symbol=proposal.symbol,
                    summary=f"{proposal.symbol} {proposal.action} · {saved['status']}",
                    evidence={
                        "proposal_id": saved["proposal_id"],
                        "status": saved["status"],
                        "reasons": saved["reasons"],
                        "trim_pct": saved.get("trim_pct"),
                        "stop_price": saved.get("stop_price"),
                        "reference_price": saved["reference_price"],
                        "target_price": saved.get("target_price"),
                        "reward_to_risk_ratio": saved.get("reward_to_risk_ratio"),
                        "sizing": saved.get("sizing"),
                        "reload_plan": saved.get("reload_plan"),
                        "pair": saved.get("pair"),
                        "execution": saved.get("execution"),
                        "autonomy": {
                            k: settings[k]
                            for k in ("autonomy_mode", "execution_mode", "emergency_pause")
                        },
                    },
                    source={"surface": "macro_cycle_scan", "dry_run_only": True},
                    created_ts=int(now),
                )
            )
        return observations
