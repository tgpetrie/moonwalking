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


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and abs(out) != float("inf") else None


def _symbol(value: Any) -> str | None:
    return str(value).upper().split("-")[0] if value else None


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
    if isinstance(scan, dict):
        return scan
    histories = context.get("cycle_histories")
    if isinstance(histories, dict) and histories:
        try:
            from macro_industry_scanner import scan_universe_cycles
        except ImportError:
            from backend.macro_industry_scanner import scan_universe_cycles
        return scan_universe_cycles(histories)
    return None


def _multi_year(context: Mapping[str, Any], symbol: str) -> dict[str, Any]:
    supplied = context.get("multi_year_contexts")
    if isinstance(supplied, dict):
        found = supplied.get(symbol) or supplied.get(f"{symbol}-USD")
        if isinstance(found, dict):
            return found
    histories = context.get("cycle_histories")
    candles = histories.get(f"{symbol}-USD") if isinstance(histories, dict) else None
    if candles:
        try:
            from chart_structure import multi_year_context
        except ImportError:
            from backend.chart_structure import multi_year_context
        return multi_year_context(candles)
    return {}


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


def _floor_for(context: Mapping[str, Any], position: Mapping[str, Any], symbol: str):
    explicit = _num(position.get("higher_low_floor"))
    if explicit is not None:
        return explicit
    floors = context.get("higher_low_floors")
    if isinstance(floors, dict):
        value = _num(floors.get(symbol))
        if value is not None:
            return value
    histories = context.get("cycle_histories")
    if isinstance(histories, dict):
        return daily_higher_low_floor(histories.get(f"{symbol}-USD"))
    return None


def _positions(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    held: dict[str, dict[str, Any]] = {}
    for row in context.get("positions") or []:
        if not isinstance(row, dict):
            continue
        symbol = _symbol(row.get("symbol") or row.get("product_id"))
        quantity = _num(row.get("quantity"))
        if symbol and quantity and quantity > 0:
            held[symbol] = {**row, "symbol": symbol, "quantity": quantity}
    return held


# ─── rules ───────────────────────────────────────────────────────────────────


def _overhead_sma(ladder: Mapping[str, Any], price: float) -> dict[str, Any] | None:
    for period in (50, 100):
        value = _num(ladder.get(f"sma_{period}w"))
        if value is None or value <= 0:
            continue
        gap = (value / price - 1.0) * 100.0
        if -SMA_TOUCH_PCT <= gap <= SMA_TOUCH_PCT:
            return {"key": f"sma_{period}w", "value": value, "gap_pct": _round(gap)}
    return None


def evaluate_trim(row, multi_year, stage, price) -> TradeProposal | None:
    if stage not in TRIM_STAGES:
        return None
    reasons, evidence = [], {}
    trim = None
    box = row.get("rollover_target_box") or multi_year.get("rollover_target_box") or {}
    low, high = _num(box.get("low")), _num(box.get("high"))
    if low is not None and high is not None and high > low and low <= price <= high:
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


def evaluate_protective_stop(row, floor, price) -> TradeProposal | None:
    stop = row.get("accumulation_invalidation_stop") or {}
    stop_price = _num(stop.get("stop_price"))
    distance = _num(stop.get("stop_distance_pct"))
    if floor is not None and price < floor:
        return TradeProposal(
            action=PROTECTIVE_STOP,
            symbol=row["symbol"],
            side="sell",
            reference_price=price,
            trim_pct=100.0,
            stop_price=floor,
            reasons=["Price closed below the daily higher-low floor."],
            evidence={"trigger": "higher_low_floor_breached", "floor": floor},
        )
    if stop_price is not None and distance is not None and distance <= STOP_APPROACH_PCT:
        return TradeProposal(
            action=PROTECTIVE_STOP,
            symbol=row["symbol"],
            side="sell",
            reference_price=price,
            trim_pct=100.0,
            stop_price=stop_price,
            reasons=[
                f"Price is {distance:.2f}% above the accumulation invalidation stop."
            ],
            evidence={
                "trigger": "invalidation_stop_near",
                "stop_distance_pct": distance,
                "floor": floor,
            },
        )
    return None


def evaluate_accumulate(row, price) -> TradeProposal | None:
    stop = row.get("accumulation_invalidation_stop") or {}
    distance = _num(stop.get("stop_distance_pct"))
    streak = int(row.get("monthly_bearish_streak") or 0)
    if not (
        row.get("bucket") == "deep_accumulation_exhaustion"
        and streak >= ACCUMULATION_MIN_STREAK
        and row.get("weekly_stoch_direction") == "oversold_turn_up"
        and (row.get("daily_macd_kiss") or row.get("macro_bullish_divergence"))
        and distance is not None
        and 0 < distance <= ACCUMULATION_MAX_STOP_PCT
    ):
        return None
    momentum = "daily MACD kiss" if row.get("daily_macd_kiss") else "bullish divergence"
    return TradeProposal(
        action=ACCUMULATE_SUPPORT,
        symbol=row["symbol"],
        side="buy",
        reference_price=price,
        stop_price=_num(stop.get("stop_price")),
        reasons=[
            f"{streak} bearish months with weekly StochRSI turning up under 25.",
            f"Momentum confirmation: {momentum}.",
            f"Invalidation stop is {distance:.2f}% away.",
        ],
        evidence={
            "monthly_bearish_streak": streak,
            "stop_distance_pct": distance,
            "daily_macd_kiss": bool(row.get("daily_macd_kiss")),
            "macro_bullish_divergence": bool(row.get("macro_bullish_divergence")),
        },
    )


def evaluate_breakout(row, price) -> TradeProposal | None:
    rsi = _num(row.get("weekly_rsi"))
    if not (row.get("breaking_confirmation_pivot") and rsi is not None):
        return None
    if rsi <= BREAKOUT_MIN_WEEKLY_RSI:
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
    """Simulates exits against a top-of-book quote; never contacts an exchange.

    Quotes use the ``paper_exit_adapter.poll_top_of_book`` shape:
    ``observed_at_ms``, ``bid_usd``, optional ``bid_size`` and
    ``exchange_time_ms``, or ``quote_status: UNAVAILABLE``.
    """

    def __init__(
        self,
        *,
        max_quote_age_ms: int = 15_000,
        max_quote_deviation_pct: float = 2.0,
        slippage_bps: float = 10.0,
    ):
        self.max_quote_age_ms = max_quote_age_ms
        self.max_quote_deviation_pct = max_quote_deviation_pct
        self.slippage_bps = slippage_bps

    def quote_guard(self, quote, reference_price, quantity, now_ms) -> list[str]:
        if not isinstance(quote, dict) or quote.get("quote_status") == "UNAVAILABLE":
            return ["quote_unavailable"]
        bid = _num(quote.get("bid_usd"))
        observed = _num(quote.get("observed_at_ms"))
        reasons = []
        if bid is None or bid <= 0:
            reasons.append("quote_missing_bid")
        if observed is None or now_ms - observed > self.max_quote_age_ms:
            reasons.append("quote_stale")
        exchange = _num(quote.get("exchange_time_ms"))
        if exchange is not None and now_ms - exchange > self.max_quote_age_ms:
            reasons.append("exchange_book_stale")
        if bid and reference_price:
            gap = abs(bid / reference_price - 1.0) * 100.0
            if gap > self.max_quote_deviation_pct:
                reasons.append("quote_deviates_from_reference")
        size = _num(quote.get("bid_size"))
        if size is not None and quantity and size < quantity:
            reasons.append("insufficient_top_of_book_size")
        return reasons

    def execute(self, proposal: TradeProposal, position, quote, now_ms) -> dict:
        quantity = position["quantity"] * (proposal.trim_pct or 0.0) / 100.0
        breached = proposal.evidence.get("trigger") == "higher_low_floor_breached"
        if proposal.action == PROTECTIVE_STOP and not breached:
            # Price is still above the stop: arm it rather than sell now.
            return {
                "status": "auto_armed_dry_run",
                "dry_run": True,
                "order_submitted": False,
                "order_type": "stop_limit_stop_limit_gtc",
                "stop_price": proposal.stop_price,
                "base_size": _round(quantity, 8),
            }
        blocks = self.quote_guard(quote, proposal.reference_price, quantity, now_ms)
        if blocks:
            return {"status": "blocked_by_guard", "block_reasons": blocks}
        bid = float(quote["bid_usd"])
        fill = bid * (1.0 - self.slippage_bps / 10_000.0)
        return {
            "status": "auto_executed_dry_run",
            "dry_run": True,
            "order_submitted": False,
            "order_type": "simulated_sell_at_bid",
            "base_size": _round(quantity, 8),
            "bid_usd": bid,
            "fill_price": _round(fill, 8),
            "proceeds_usd": _round(fill * quantity, 2),
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
        stage = (scan.get("industry") or {}).get("liquidity_rotation_stage")
        rows = {
            _symbol(row.get("symbol")): row
            for row in scan.get("coins") or []
            if isinstance(row, dict) and row.get("available")
        }
        held = _positions(context)
        watch = {_symbol(s) for s in context.get("watchlist") or [] if _symbol(s)}
        proposals: list[TradeProposal] = []
        for symbol in sorted(held):
            row = rows.get(symbol)
            price = _num(row.get("price")) if row else None
            if not row or price is None or price <= 0:
                continue
            stop = evaluate_protective_stop(
                row, _floor_for(context, held[symbol], symbol), price
            )
            if stop:
                proposals.append(stop)
                continue  # defend first; a broken floor is no time to trim
            trim = evaluate_trim(row, _multi_year(context, symbol), stage, price)
            if trim:
                proposals.append(trim)
        for symbol in sorted(watch | set(held)):
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
        if proposal.action in ENTRY_ACTIONS:
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
        now = float(context.get("now_ts") or self.clock())
        proposals = self.evaluate(context)
        self.last_proposals = []
        if not proposals:
            return []
        store = self.store or AgentStore()
        settings = store.get_autonomy_settings()
        held = _positions(context)
        quotes = context.get("quotes") if isinstance(context.get("quotes"), dict) else {}
        day_start = int(now // 86_400 * 86_400)
        now_ms = int(now * 1000)
        observations = []
        for proposal in proposals:
            proposal.proposal_id = proposal_id(proposal.action, proposal.symbol, now)
            existing = store.get_proposal(proposal.proposal_id)
            if existing and existing["status"] not in {"pending_approval", "blocked_by_guard"}:
                saved = store.save_proposal(proposal.to_record(), now=int(now))
            else:
                status, execution = self._route(
                    proposal,
                    settings,
                    held,
                    quotes,
                    now_ms,
                    store.count_auto_orders_since(day_start),
                )
                proposal.status = status
                saved = store.save_proposal(
                    proposal.to_record(), execution=execution, now=int(now)
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
                        "reasons": proposal.reasons,
                        "trim_pct": proposal.trim_pct,
                        "stop_price": proposal.stop_price,
                        "reference_price": proposal.reference_price,
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
