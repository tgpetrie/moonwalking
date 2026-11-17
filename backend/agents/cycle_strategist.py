"""Cycle Strategist: turns the multi-year cycle read into trade proposals.

Each run reads the universe cycle scan (``scan_universe_cycles``), any
per-coin ``multi_year_context`` reads and the held positions, then emits
deterministic proposals:

- ``TRIM_TO_USDC``        held coin inside its 0.618-0.786 rollover box, or
                          pressing an overhead 50W/100W average, while the
                          liquidity rotation is still Stage 1 or 2
- ``PROTECTIVE_STOP``     held coin has lost its daily higher-low floor, or is
                          close to its accumulation invalidation stop. A fresh
                          break (at most 5% under the floor) exits at market;
                          a deeper, stale break keeps the floor as reclaim
                          resistance, guards the cycle-low stop below price
                          and always waits for approval
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
protective stops run through ``GuardedDryRunExitExecutor``, except stale floor
breaks; entries, reloads and rotations always wait for approval.
Nothing here can submit an exchange order: ``live_guarded`` is recorded as a
setting but blocks automatic execution because no live route exists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import math
import time
from typing import Any, Callable, Mapping

from .contracts import AgentObservation, json_safe
from .cycle_context import (
    _finite as _num,
    normalize_positions,
    normalize_watchlist,
    usable_cycle_scan,
)
from .store import AgentStore, OPEN_PROPOSAL_STATUSES, split_reload_cents, usdc_cents


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
# A close this far under the daily higher-low floor is a fresh break; deeper
# is a stale break that waits for an operator.
FRESH_FLOOR_BREAK_PCT = 5.0
STALE_FLOOR_BREAK = "stale_floor_break_reassess"
MAX_QUOTE_CLOCK_SKEW_MS = 2_000
ACCUMULATION_MIN_STREAK = 18
ACCUMULATION_MAX_STOP_PCT = 10.0
BREAKOUT_MIN_WEEKLY_RSI = 60.0

# Reload ladder: share of the freed USDC per rung, shallowest rung first.
RELOAD_WEIGHTS = (25, 35, 40)
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
    breach_state: str | None = None
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


def _fmt_price(value: float) -> str:
    return f"${value:,.2f}" if value >= 1 else f"${value:.4g}"


def _stale_break(price, level) -> bool:
    return price < level * (1 - FRESH_FLOOR_BREAK_PCT / 100)


def _floor_break(row, floor, price, scanner_stop, position_stop) -> TradeProposal:
    """A close below the daily higher-low floor, fresh or long since broken.

    A fresh break (at most ``FRESH_FLOOR_BREAK_PCT`` below) is still a live
    structural failure, so the exit stop sits at the market, never above it.
    A deeper break is stale: selling there dumps the low, so the old floor
    becomes reclaim resistance, the stop falls back to the cycle invalidation
    below price, and the proposal always waits for an operator.
    """
    below = (floor - price) / floor * 100
    evidence = {"floor": floor, "broken_floor_price": floor, "distance_below_floor_pct": _round(below)}
    if not _stale_break(price, floor):
        return TradeProposal(
            action=PROTECTIVE_STOP,
            symbol=row["symbol"],
            side="sell",
            reference_price=price,
            trim_pct=100.0,
            stop_price=price,
            breach_state="fresh_floor_break",
            reasons=[f"Just closed {below:.1f}% below {_fmt_price(floor)} floor."],
            evidence={**evidence, "trigger": "higher_low_floor_breached", "stop_distance_pct": 0.0},
        )
    stop, basis = next(
        ((level, basis) for level, basis in (
            (scanner_stop, "accumulation_invalidation_stop"), (position_stop, "position_stop")
        ) if level is not None and 0 < level < price),
        (None, "floor_already_broken_reassess"),
    )
    reasons = [f"Floor {_fmt_price(floor)} already broken by {below:.0f}%."]
    if stop is None:
        reasons.append(
            f"Reassess on a bounce to {_fmt_price(floor)}; no cycle-low stop sits below price."
        )
    else:
        reasons.append(
            f"Reassess on a bounce to {_fmt_price(floor)} or guard the cycle-low stop at {_fmt_price(stop)}."
        )
    return TradeProposal(
        action=PROTECTIVE_STOP,
        symbol=row["symbol"],
        side="sell",
        reference_price=price,
        trim_pct=100.0,
        stop_price=stop,
        breach_state=STALE_FLOOR_BREAK,
        reasons=reasons,
        evidence={
            **evidence,
            "trigger": "stale_floor_break",
            "reclaim_resistance": floor,
            "stop_basis": basis,
            "stop_distance_pct": _round((price - stop) / price * 100) if stop is not None else None,
        },
    )


def _stop_break(row, floor, price, broken_stop, position_guard) -> TradeProposal:
    """A close at or below the position or cycle invalidation stop.

    Mirrors ``_floor_break``: a fresh break exits at the market, a deep one
    turns the broken stop into reclaim resistance and waits for an operator.
    """
    detail = "position stop" if position_guard else "accumulation invalidation stop"
    basis = "position_stop" if position_guard else "accumulation_invalidation_stop"
    below = (broken_stop - price) / broken_stop * 100
    evidence = {
        "floor": floor,
        "broken_stop_price": broken_stop,
        "broken_stop_basis": basis,
        "distance_below_stop_pct": _round(below),
    }
    if not _stale_break(price, broken_stop):
        return TradeProposal(
            action=PROTECTIVE_STOP,
            symbol=row["symbol"],
            side="sell",
            reference_price=price,
            trim_pct=100.0,
            stop_price=min(broken_stop, price),
            breach_state="fresh_stop_break",
            reasons=[f"Price closed {below:.1f}% below the {detail} at {_fmt_price(broken_stop)}."],
            evidence={**evidence, "trigger": "invalidation_stop_breached", "stop_distance_pct": 0.0},
        )
    return TradeProposal(
        action=PROTECTIVE_STOP,
        symbol=row["symbol"],
        side="sell",
        reference_price=price,
        trim_pct=100.0,
        stop_price=None,
        breach_state=STALE_FLOOR_BREAK,
        reasons=[
            f"The {detail} at {_fmt_price(broken_stop)} is already broken by {below:.0f}%.",
            f"Reassess on a bounce to {_fmt_price(broken_stop)}; do not sell into the low.",
        ],
        evidence={
            **evidence,
            "trigger": "stale_stop_break",
            "reclaim_resistance": broken_stop,
            "stop_basis": "stop_already_broken_reassess",
            "stop_distance_pct": None,
        },
    )


def evaluate_protective_stop(row, floor, price, position_stop=None) -> TradeProposal | None:
    stop = row.get("accumulation_invalidation_stop") or {}
    scanner_stop = _num(stop.get("stop_price"))
    position_stop = _num(position_stop)
    floor = _num(floor)
    price = _num(price)
    if price is None or price <= 0:
        return None
    # Use the deepest breached guard before checking legacy near-stop precedence.
    broken = [
        (level, kind) for level, kind in (
            (floor, "floor"), (position_stop, "position"), (scanner_stop, "scanner")
        )
        if level is not None and (level > price or (level == price and kind != "floor"))
    ]
    if broken:
        level, kind = max(broken, key=lambda item: item[0])
        if kind == "floor":
            return _floor_break(row, level, price, scanner_stop, position_stop)
        return _stop_break(row, floor, price, level, kind == "position")
    stop_price = position_stop
    position_guard = stop_price is not None and stop_price > 0
    if not position_guard:
        stop_price = scanner_stop
    if stop_price is not None and 0 < stop_price and price * (1 - STOP_APPROACH_PCT / 100) <= stop_price:
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


def _quant_module(name: str):
    """A backend quant module, importable from either working directory."""
    import importlib

    try:
        return importlib.import_module(name)
    except ImportError:
        return importlib.import_module(f"backend.{name}")


def _ladder_advice(low, high, price, freed_usdc, daily_candles) -> dict[str, Any]:
    """Adaptive three-rung read from ``ladder_optimizer``.

    The box runs from the invalidation stop (``low``) up to the plan's highest
    rung (``high``). The optimizer starts from the plan's own tranche weights
    and tilts them by past wick depth. Its fill probabilities belong to its own
    rungs at fixed box depths, not to the plan's tranche levels.
    """
    low, high = _num(low), _num(high)
    if low is None or high is None or not 0 < low < high:
        return {"available": False, "reason": "no_support_box"}
    try:
        advice = _quant_module("ladder_optimizer").optimize_reload_ladder(
            low, high, price, freed_usdc, daily_candles=daily_candles,
            base_weights=RELOAD_WEIGHTS,
        )
    except Exception as exc:  # advice must never sink the trim proposal
        return {"available": False, "reason": f"optimizer_failed:{type(exc).__name__}"}
    return {
        "available": True,
        "support_box": {"low": low, "high": high},
        "regime": advice["regime"],
        "rungs": advice["rungs"],
        "weights": advice["weights"],
        "expected_fill_probability_by_rung": advice["expected_fill_probability_by_rung"],
        "net_extra_coins_vs_flat_weights": advice["net_extra_coins_vs_flat_weights"],
        "expected_extra_coins_vs_flat_weights": advice["expected_extra_coins_vs_flat_weights"],
        "wick_events": advice["history"]["events"],
        "spread_bps": advice["spread_bps"],
    }


def build_reload_plan(
    row, multi_year, price, trim_quantity, held_quantity, floor=None, daily_candles=None
) -> dict[str, Any]:
    """Split a trim's USDC across lower support levels and count the coins bought back.

    The figures assume each rung fills at its level and leave out fees and
    slippage. They describe a plan; nothing is ordered. An available plan also
    carries ``ladder_optimizer``: rung weights tilted by past wick depth in
    ``daily_candles``. With three rungs and enough history those weights split
    the USDC (``weight_source: "ladder_optimizer"``); otherwise the fixed
    25/35/40 split is used.
    """
    price, trim_quantity, held_quantity = map(_num, (price, trim_quantity, held_quantity))
    if price is None or trim_quantity is None or held_quantity is None or not (
        price > 0 and 0 < trim_quantity <= held_quantity
    ):
        return {"available": False, "reason": "invalid_trim_size"}
    freed_cents = usdc_cents(trim_quantity * price, round_down=True)
    freed = freed_cents / 100
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
    for level, source in _reload_candidates(row, multi_year, _num(floor)):
        if invalidation is None or not 0 < invalidation < level <= ceiling:
            continue
        if any(abs(level / kept - 1) * 100 < RELOAD_LEVEL_MERGE_PCT for kept, _ in chosen):
            continue
        chosen.append((level, source))
        if len(chosen) == min(len(RELOAD_WEIGHTS), freed_cents):
            break
    plan: dict[str, Any] = {
        "available": bool(chosen and freed_cents),
        "reference_price": price,
        "trim_quantity": trim_quantity,
        "freed_usdc": _round(freed, 2),
        "invalidation_stop": invalidation,
        "invalidation_basis": basis,
        "fresh_cash_usd": 0.0,
        "assumptions": "Each rung fills at its level. Fees and slippage are not included.",
    }
    if not chosen or not freed_cents:
        plan["reason"] = "no_support_level_between_stop_and_price" if freed_cents else "insufficient_trim_proceeds"
        return plan
    chosen.sort(reverse=True)
    advice = _ladder_advice(invalidation, chosen[0][0], price, freed, daily_candles)
    weights = RELOAD_WEIGHTS[: len(chosen)]
    # A full three-rung ladder takes the history-tilted split. Without enough
    # wick history the optimizer returns the plan's own 25/35/40 unchanged.
    applied = bool(
        advice.get("available") and advice["regime"] != "default" and len(chosen) == len(RELOAD_WEIGHTS)
    )
    if applied:
        weights = tuple(max(1, round(weight * 10_000)) for weight in advice["weights"])
    advice["applied_to_tranches"] = applied
    total = sum(weights)
    tranches, coins = [], 0.0
    allocation = split_reload_cents(freed_cents, list(weights))
    for index, ((level, source), weight, cents) in enumerate(zip(chosen, weights, allocation), start=1):
        usdc = cents / 100
        coins += usdc / level
        tranches.append({
            "index": index,
            "weight_pct": _round(weight / total * 100),
            "level": level,
            "basis": source,
            "usdc": usdc,
            "coins": usdc / level,
            "discount_pct": _round((1 - level / price) * 100),
        })
    gain = coins - trim_quantity
    if not math.isfinite(coins) or coins <= 0 or not math.isfinite(gain / held_quantity * 100):
        return {**plan, "available": False, "reason": "invalid_reload_projection"}
    plan.update(
        tranches=tranches,
        average_reload_price=freed / coins,
        projected_reloaded_coins=coins,
        net_coin_gain_qty=gain,
        # Growth of the whole stack: coins held after the round trip against before.
        net_coin_gain_pct=_round(gain / held_quantity * 100),
        reloaded_vs_trimmed_pct=_round(gain / trim_quantity * 100),
        weight_source="ladder_optimizer" if applied else "default",
        ladder_optimizer=advice,
    )
    return plan


def evaluate_reload(row, price, plans) -> TradeProposal | None:
    """A rebuy for unfilled reload rungs that price has reached, on a momentum turn."""
    stoch_turn = row.get("weekly_stoch_direction") == "oversold_turn_up"
    kiss = row.get("daily_macd_kiss") is True
    if not (stoch_turn or kiss):
        return None
    fills, pool, remaining, invalidations = [], 0, 0, []
    for plan in plans or []:
        invalidation = _num(plan.get("invalidation_stop"))
        if invalidation is None or not 0 < invalidation < price:
            continue  # this plan's support has failed
        for tranche in plan.get("tranches") or []:
            level = _num(tranche.get("level"))
            cents = usdc_cents(tranche.get("remaining_usdc", tranche.get("usdc")))
            if tranche.get("filled") or level is None or level <= invalidation or not cents:
                continue
            remaining += cents
            if price <= level:
                fills.append({
                    "plan_id": plan.get("plan_id"),
                    "tranche": tranche.get("index"),
                    "level": level,
                    "usdc": cents / 100,
                })
                pool += cents
                invalidations.append(invalidation)
    if not fills:
        return None
    stop = _num((row.get("accumulation_invalidation_stop") or {}).get("stop_price"))
    stop = max([*invalidations, stop] if stop is not None and 0 < stop < price else invalidations)
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
        ],
        evidence={
            "reload_fills": fills,
            "reload_pool_usdc": pool / 100,
            "reload_pool_remaining_usdc": remaining / 100,
            "weekly_stoch_turning_up": stoch_turn,
            "daily_macd_kiss": kiss,
        },
    )


# ─── reward to risk, sizing and heat ─────────────────────────────────────────


def active_target(row) -> dict[str, Any] | None:
    """The tier the industry stage selects, falling back to the rollover box."""
    tiers = (row.get("active_target_tier"), "rollover_target_box")
    for tier in tiers:
        if tier not in ("rollover_target_box", "full_extension_targets"):
            continue
        box = row.get(tier)
        if not isinstance(box, Mapping):
            continue
        low, high = _num(box.get("low")), _num(box.get("high"))
        if low is not None and high is not None and 0 < low <= high:
            return {"tier": tier, "low": low, "high": high, "mid": low + (high - low) / 2}
    return None


def reward_to_risk(price, stop, target) -> float | None:
    """Distance up to the target midpoint over distance down to the stop."""
    price, stop, target = _num(price), _num(stop), _num(target)
    if price is None or stop is None or target is None or not 0 < stop < price < target:
        return None
    price_decimal, stop_decimal, target_decimal = map(lambda value: Decimal(str(value)), (price, stop, target))
    return _num((target_decimal - price_decimal) / (price_decimal - stop_decimal))


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
    by_symbol: dict[str, float] = {}
    for symbol in sorted(held):
        position, row = held[symbol], rows.get(symbol) or {}
        price = _num(row.get("price"))
        if price is None or price <= 0:
            unpriced.append(symbol)
            continue
        quantity = position["quantity"]
        marked = _num(quantity * price)
        if marked is None or not math.isfinite(value + marked):
            unpriced.append(symbol)
            continue
        value += marked
        stops = (
            _num(position.get("stop_price")),
            floors.get(symbol),
            _num((row.get("accumulation_invalidation_stop") or {}).get("stop_price")),
        )
        usable = [stop for stop in stops if stop is not None and 0 < stop < price]
        if usable:
            by_symbol[symbol] = quantity * (price - max(usable))
        else:
            assumed.append(symbol)
            by_symbol[symbol] = marked * (HEAT_ASSUMED_STOP_PCT / 100)
        risk += by_symbol[symbol]
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
        "max_open_risk_pct": min(
            _setting(context, "max_open_risk_pct", MAX_OPEN_RISK_PCT), MAX_OPEN_RISK_PCT
        ),
        "assumed_stop_symbols": assumed,
        "unpriced_symbols": unpriced,
        "_equity": equity,
        "_risk": risk,
        "_reserved_risk": 0.0,
        "_position_risk": by_symbol,
    }


def size_entry(price, stop, stage, heat, base_risk_pct, *, funded_usd=None) -> dict[str, Any]:
    """Suggested size from the stage-scaled risk budget, inside the heat cap.

    ``heat["_reserved_risk"]`` accumulates the risk of entries already sized in
    this pass, so several proposals cannot each claim the same headroom.
    ``funded_usd`` caps the size at money a trim already freed.
    """
    stage = stage if isinstance(stage, str) else None
    multiplier = STAGE_RISK_MULTIPLIER.get(stage, UNKNOWN_STAGE_RISK_MULTIPLIER)
    budget = base_risk_pct * multiplier
    price, stop = _num(price), _num(stop)
    stop_fraction = None
    if price is not None and stop is not None and 0 < stop < price:
        price_decimal = Decimal(str(price))
        stop_fraction = float((price_decimal - Decimal(str(stop))) / price_decimal)
    out: dict[str, Any] = {
        "base_risk_pct": base_risk_pct,
        "stage_multiplier": multiplier,
        "risk_budget_pct": _round(budget, 3),
        "stop_distance_pct": _round(stop_fraction * 100) if stop_fraction is not None else None,
        "max_open_risk_pct": heat["max_open_risk_pct"],
        "open_risk_pct": heat["open_risk_pct"],
        "equity_basis": heat["equity_basis"],
        "heat_capped": False,
        "position_capped": False,
        "suggested_notional_usd": None,
        "suggested_quantity": None,
        "risk_at_stop_usd": None,
    }
    if funded_usd is not None:
        out["funded_usd"] = _round(funded_usd, 2)
    equity = heat["_equity"]
    if stop_fraction is None or stop_fraction <= 0:
        out["note"] = "invalid_stop"
    elif heat["unpriced_symbols"]:
        out["note"] = "positions_unpriced"
    elif equity is None:
        out["note"] = "equity_unknown"
    else:
        headroom = max(0.0, equity * (heat["max_open_risk_pct"] / 100) - heat["_risk"] - heat["_reserved_risk"])
        risk_budget = equity * (budget / 100)
        out["heat_capped"] = risk_budget > headroom
        risk_budget = min(risk_budget, headroom)
        ceiling = equity * (MAX_POSITION_PCT / 100)
        out["position_capped"] = risk_budget > ceiling * stop_fraction
        notional = ceiling if out["position_capped"] else risk_budget / stop_fraction
        if funded_usd is not None:
            notional = min(notional, max(0.0, funded_usd))
        notional = usdc_cents(notional, round_down=True) / 100
        used = notional * stop_fraction
        quantity = notional / price
        if not math.isfinite(quantity):
            return {**out, "note": "invalid_sized_quantity"}
        heat["_reserved_risk"] += used
        out.update(
            risk_budget_pct=_round(used / equity * 100, 3),
            suggested_notional_usd=notional,
            suggested_quantity=quantity,
            risk_at_stop_usd=_round(used, 2),
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
    freed = usdc_cents(quantity * (ROTATION_TRIM_PCT / 100) * price, round_down=True) / 100
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
            "freed_usd": freed,
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
        max_clock_skew_ms: int = MAX_QUOTE_CLOCK_SKEW_MS,
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
            or skew is None or not 0 <= skew <= min(age, MAX_QUOTE_CLOCK_SKEW_MS)
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
        if observed is None or observed <= 0 or now is None or not 0 <= now - observed <= self.max_quote_age_ms:
            reasons.append("quote_stale")
        if exchange is None:
            reasons.append("quote_missing_exchange_timestamp")
        elif (
            exchange <= 0 or now is None or observed is None
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
        if proposal.breach_state == STALE_FLOOR_BREAK:
            return blocked(STALE_FLOOR_BREAK)
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
            if stop is None or not 0 < stop <= float(proposal.reference_price):
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
            trigger = proposal.evidence.get("trigger")
            if trigger == "higher_low_floor_breached":
                # The stop sits at the market; the bid must still be under the floor.
                level = _num(proposal.evidence.get("broken_floor_price")) or stop
            elif trigger == "invalidation_stop_breached":
                level = _num(proposal.evidence.get("broken_stop_price")) or stop
            else:
                level = None
            if level is None or bid > level:
                return blocked("quote_does_not_confirm_stop_breach")
            if _stale_break(bid, level):
                return blocked(STALE_FLOOR_BREAK)
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


CLUSTER_GUARD_LIMITS = {
    "max_total_heat_pct": 5.0,
    "max_cluster_heat_pct": 2.0,
    "max_positions_per_cluster": 2,
}


class _ClusterGuard:
    """Checks each sized entry against cluster and beta-adjusted heat, in rank order.

    Wraps ``portfolio_cluster_guard.evaluate_cluster_and_beta_heat``. A coin's
    cluster comes from its scan row (``category_id`` / ``cluster`` /
    ``narrative_cluster`` / ``sector``) or ``context["symbol_clusters"]``, and
    its downside beta from the row or ``context["downside_betas"]``. A coin
    with neither stands alone with a beta of 1. Entries with no sized risk
    (equity unknown, or no heat left) pass through: they buy nothing.
    """

    def __init__(self, context, rows, held, heat) -> None:
        self.module = None
        self.equity = heat.get("_equity")
        clusters = context.get("symbol_clusters")
        betas = context.get("downside_betas")
        self.clusters = clusters if isinstance(clusters, Mapping) else {}
        self.betas = betas if isinstance(betas, Mapping) else {}
        self.rows = rows
        self.accepted: list[dict[str, Any]] = []
        self.suppressed: list[dict[str, Any]] = []
        self.reason = None
        if not self.equity:
            self.reason = "equity_unknown"
            return
        try:
            self.module = _quant_module("portfolio_cluster_guard")
        except ImportError:
            self.reason = "guard_unavailable"
            return
        self.existing = [
            self._item(symbol, risk) for symbol, risk in sorted(heat["_position_risk"].items()) if risk > 0
        ]

    def _item(self, symbol: str, risk_usd: float | None) -> dict[str, Any]:
        row = self.rows.get(symbol) or {}
        item: dict[str, Any] = {"symbol": symbol, "risk_usd": risk_usd}
        for key in ("category_id", "cluster", "narrative_cluster", "sector"):
            if isinstance(row.get(key), str) and row[key].strip():
                item[key] = row[key]
                break
        else:
            named = self.clusters.get(symbol)
            if isinstance(named, str) and named.strip():
                item["category_id"] = named
        beta = row.get("downside_beta", self.betas.get(symbol))
        if beta is not None:
            item["downside_beta"] = beta
        return item

    def admit(self, entry: TradeProposal) -> bool:
        if self.module is None:
            return True
        risk = _num((entry.sizing or {}).get("risk_at_stop_usd"))
        if risk is None or risk <= 0:
            return True
        candidate = self._item(entry.symbol, risk)
        verdict = self.module.evaluate_cluster_and_beta_heat(
            self.existing + self.accepted, [candidate], equity_usd=self.equity, **CLUSTER_GUARD_LIMITS
        )
        if verdict["accepted_proposals"]:
            self.accepted.append(candidate)
            entry.evidence["cluster_guard"] = verdict["accepted_proposals"][0]["cluster_guard"]
            return True
        blocked = verdict["suppressed_proposals"][0]
        self.suppressed.append({
            "symbol": entry.symbol,
            "action": entry.action,
            "reference_price": entry.reference_price,
            "suppression_reason": blocked["suppression_reason"],
            "cluster_guard": blocked["cluster_guard"],
            "suggested_notional_usd": (entry.sizing or {}).get("suggested_notional_usd"),
        })
        return False

    def summary(self) -> dict[str, Any]:
        if self.module is None:
            return {"available": False, "reason": self.reason, "suppressed_proposals": []}
        totals = self.module.evaluate_cluster_and_beta_heat(
            self.existing + self.accepted, [], equity_usd=self.equity, **CLUSTER_GUARD_LIMITS
        )
        return {
            "available": True,
            "limits": totals["limits"],
            "clusters": totals["clusters"],
            "total_risk_pct": totals["total_risk_pct"],
            "total_beta_adjusted_risk_pct": totals["total_beta_adjusted_risk_pct"],
            "accepted_symbols": [item["symbol"] for item in self.accepted],
            "suppressed_proposals": list(self.suppressed),
        }


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
        # Cluster and beta heat read for the last ``evaluate``, with the
        # entries it suppressed and why.
        self.last_cluster_guard: dict[str, Any] | None = None

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
        trimming = set()
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
                # The size defended, so the ledger can value the exit later.
                held_quantity = _num(position.get("quantity"))
                if held_quantity is not None and held_quantity > 0:
                    stop.evidence["held_quantity"] = held_quantity
                    stop.evidence["quantity"] = held_quantity
                    stop.evidence["notional_usd"] = _round(held_quantity * price, 2)
                proposals.append(stop)
                defended.add(symbol)
                continue  # defend first; a stop is no time to trim or add
            trim = evaluate_trim(row, multi_year, stage, price)
            if trim:
                quantity = position["quantity"]
                trim.evidence["held_quantity"] = quantity
                histories = context.get("cycle_histories")
                trim.reload_plan = build_reload_plan(
                    row, multi_year, price, quantity * trim.trim_pct / 100, quantity, floor,
                    daily_candles=histories.get(f"{symbol}-USD") if isinstance(histories, dict) else None,
                )
                proposals.append(trim)
                trimming.add(symbol)

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
        guard = _ClusterGuard(context, rows, held, heat)
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
            reserved_before = heat["_reserved_risk"]
            entry.sizing = size_entry(
                price, stop, stage, heat, base_risk,
                funded_usd=entry.evidence.get("reload_pool_usdc")
                if entry.action == RELOAD_ACCUMULATE else None,
            )
            if not guard.admit(entry):
                # Give the suppressed entry's heat back to the entries after it.
                heat["_reserved_risk"] = reserved_before
                continue
            if entry.action == RELOAD_ACCUMULATE:
                remaining = usdc_cents(entry.sizing["suggested_notional_usd"])
                allocations = []
                for fill in entry.evidence["reload_fills"]:
                    amount = min(remaining, usdc_cents(fill["usdc"]))
                    if not amount:
                        break
                    allocations.append({**fill, "usdc": amount / 100})
                    remaining -= amount
                entry.evidence["reload_fills"] = allocations
                entry.evidence["reload_allocation_version"] = 1
                entry.reasons.append(
                    "The buy uses the allocated reload funds."
                    if allocations else "Sizing is unavailable at the current portfolio risk."
                )
            proposals.append(entry)

        laggards = [
            symbol for symbol in sorted(held)
            if symbol not in defended and symbol not in trimming and symbol in rows and is_laggard(rows[symbol])
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
                notional = rotation.sizing["suggested_notional_usd"]
                if not notional:
                    continue
                if notional < rotation.pair["freed_usd"]:
                    rotation.trim_pct *= notional / rotation.pair["freed_usd"]
                    rotation.pair["freed_usd"] = notional
                    rotation.reasons[-1] = (
                        f"Rotate ${notional:,.2f} of {symbol} into {leader['symbol']} within the risk budget."
                    )
                proposals.append(rotation)
        self.last_heat = {key: value for key, value in heat.items() if not key.startswith("_")}
        self.last_cluster_guard = guard.summary()
        return proposals

    def _route(self, proposal, settings, held, quotes, now_ms, orders_today):
        if proposal.action not in EXIT_ACTIONS or proposal.side != "sell":
            return "pending_approval", None
        if settings["autonomy_mode"] != "auto_protect_exits":
            return "pending_approval", None
        if proposal.breach_state == STALE_FLOOR_BREAK:
            return "pending_approval", {"held_reason": STALE_FLOOR_BREAK}
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
    def _fetch_exit_quotes(context, store, proposals, quotes, now) -> dict[str, Any]:
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
            or store.count_auto_orders_since(int(now // 86_400) * 86_400)
                >= settings["daily_order_cap"]
        ):
            return {}
        wanted = []
        for proposal in proposals:
            if (
                proposal.action not in EXIT_ACTIONS or proposal.product_id in quotes
                or proposal.breach_state == STALE_FLOOR_BREAK
            ):
                continue
            saved = store.get_proposal(proposal.proposal_id)
            if saved is None or saved["status"] in OPEN_PROPOSAL_STATUSES:
                wanted.append(proposal.product_id)
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
        for proposal in proposals:
            proposal.proposal_id = proposal_id(proposal.action, proposal.symbol, now)
        quotes = dict(context["quotes"]) if isinstance(context.get("quotes"), dict) else {}
        quotes.update(self._fetch_exit_quotes(context, store, proposals, quotes, now))
        observations = []
        for proposal in proposals:
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
                        "breach_state": saved.get("breach_state"),
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
