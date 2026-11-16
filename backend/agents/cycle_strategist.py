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

Proposals are stored in ``AgentStore``. In ``approval_queue`` mode every
proposal waits for approval. In ``auto_protect_exits`` mode, exit proposals
run through ``GuardedDryRunExitExecutor``; entries always wait for approval.
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
EXIT_ACTIONS = frozenset({TRIM_TO_USDC, PROTECTIVE_STOP})
ENTRY_ACTIONS = frozenset({ACCUMULATE_SUPPORT, BREAKOUT_ENTRY})

TRIM_STAGES = frozenset({"stage_1_macro_compression", "stage_2_btc_majors_lead"})
TRIM_MIN_PCT = 25.0
TRIM_MAX_PCT = 50.0
SMA_TOUCH_PCT = 2.0  # within this much of an overhead 50W/100W average
STOP_APPROACH_PCT = 3.0
ACCUMULATION_MIN_STREAK = 18
ACCUMULATION_MAX_STOP_PCT = 10.0
BREAKOUT_MIN_WEEKLY_RSI = 60.0

SEVERITY = {
    PROTECTIVE_STOP: "critical",
    TRIM_TO_USDC: "warning",
    ACCUMULATE_SUPPORT: "watch",
    BREAKOUT_ENTRY: "watch",
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
    ):
        age = _num(max_quote_age_ms)
        deviation, spread, slippage = map(_num, (max_quote_deviation_pct, max_spread_pct, slippage_bps))
        if (
            age is None or age <= 0 or deviation is None or not 0 <= deviation <= 100
            or spread is None or not 0 <= spread <= 100
            or slippage is None or not 0 <= slippage < 10_000
        ):
            raise ValueError("invalid dry-run guard parameters")
        self.max_quote_age_ms = age
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
        elif now is None or observed is None or exchange > observed or not 0 <= now - exchange <= self.max_quote_age_ms:
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
    model_version = "cycle-strategist-rule-v1"

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

    def bind_store(self, store: AgentStore) -> None:
        self.store = store

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
        proposals: list[TradeProposal] = []
        defended = set()
        for symbol in sorted(held):
            row = rows.get(symbol)
            price = _num(row.get("price")) if row else None
            if not row or price is None or price <= 0:
                continue
            position = held[symbol]
            multi_year = _multi_year(context, row, symbol)
            stop = evaluate_protective_stop(
                row, _floor_for(context, position, symbol, multi_year), price, position.get("stop_price")
            )
            if stop:
                proposals.append(stop)
                defended.add(symbol)
                continue  # defend first; a stop is no time to trim or add
            trim = evaluate_trim(row, multi_year, stage, price)
            if trim:
                proposals.append(trim)
        for symbol in sorted((watch | set(held)) - defended):
            row = rows.get(symbol)
            price = _num(row.get("price")) if row else None
            if not row or price is None or price <= 0:
                continue
            entry = evaluate_accumulate(row, price) or evaluate_breakout(row, price)
            if entry:
                entry.stage = stage
                proposals.append(entry)
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

    def run(self, context: dict | None) -> list[AgentObservation]:
        context = context or {}
        supplied_now = _num(context.get("now_ts"))
        clock = self.clock if supplied_now is None else lambda: supplied_now
        now = clock()
        proposals = self.evaluate({**context, "now_ts": now})
        self.last_proposals = []
        if not proposals:
            return []
        store = self.store or AgentStore()
        held = _positions(context)
        quotes = context.get("quotes") if isinstance(context.get("quotes"), dict) else {}
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
