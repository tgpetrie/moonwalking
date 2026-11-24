"""Historical cycle compounding replay.

Pure and deterministic: no network, no disk, no clock. ``simulate_cycle_compounding``
walks daily candles oldest to newest and decides each bar from that bar and
the bars before it only, so appending later bars can never change an earlier
event.

The replay is self-contained. It uses a rolling cycle box (the lowest low and
highest high of the trailing ``lookback_bars``), log-scale Fibonacci levels
inside that box and a Stochastic RSI computed incrementally. It does not call
``cycle_analysis``; the rules below are a simplified stand-in for the live
strategist's and have not been tested against outcomes.

Rules, checked in this order on every bar:

1. Reload rungs. After a trim, the freed USDC is split across three rungs at
   the 0.382, 0.50 and 0.618 log pullbacks of the cycle box. A rung fills when
   a later bar's low touches it, at the rung price or at the open if the bar
   gapped below it.
2. Protective stop. While coins are held, a close more than
   ``stop_buffer_pct`` below an established cycle low (one at least
   ``support_min_age_bars`` old) sells everything to USDC.
3. Re-entry. After a stop, the first close above the highest high of the prior
   ``breakout_bars`` bars buys back with all USDC.
4. Trim. With no ladder open and the cooldown elapsed, a close in the upper
   zone of the box (0.618 of the log range or higher) while the Stochastic RSI
   turns down from 80 or above sells ``trim_fraction`` of the coins.

No outside cash is ever added.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["simulate_cycle_compounding", "RUNG_RETRACEMENTS"]

RUNG_RETRACEMENTS = (0.382, 0.5, 0.618)
TRIM_ZONE_MIN = 0.618
RSI_PERIOD = 14
STOCH_PERIOD = 14
STOCH_SMOOTH = 3
ROLLOVER_FROM = 80.0
ROLLOVER_MEMORY_BARS = 5


def _clean(candles: Any) -> list[tuple[float, float, float, float, float]]:
    """Valid ``(ts, low, high, open, close)`` bars, oldest first, one per timestamp."""
    by_ts: dict[float, tuple[float, float, float, float, float]] = {}
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


class _StochRsi:
    """Wilder RSI and a smoothed Stochastic RSI, fed one close at a time."""

    def __init__(self) -> None:
        self.prior: float | None = None
        self.count = 0
        self.gain = 0.0
        self.loss = 0.0
        self.rsis: list[float] = []
        self.raw: list[float] = []

    def push(self, close: float) -> float | None:
        """The smoothed %K after this close, or ``None`` during warm-up."""
        if self.prior is None:
            self.prior = close
            return None
        change = close - self.prior
        self.prior = close
        gain, loss = max(change, 0.0), max(-change, 0.0)
        self.count += 1
        if self.count <= RSI_PERIOD:
            self.gain += gain / RSI_PERIOD
            self.loss += loss / RSI_PERIOD
            if self.count < RSI_PERIOD:
                return None
        else:
            self.gain = (self.gain * (RSI_PERIOD - 1) + gain) / RSI_PERIOD
            self.loss = (self.loss * (RSI_PERIOD - 1) + loss) / RSI_PERIOD
        if self.gain == 0 and self.loss == 0:
            rsi = 50.0
        elif self.loss == 0:
            rsi = 100.0
        else:
            rsi = 100.0 - 100.0 / (1.0 + self.gain / self.loss)
        self.rsis = (self.rsis + [rsi])[-STOCH_PERIOD:]
        low, high = min(self.rsis), max(self.rsis)
        # A flat RSI has no range: read it as pinned high or low by its level.
        stoch = (100.0 if rsi >= 50 else 0.0) if high == low else (rsi - low) / (high - low) * 100.0
        self.raw = (self.raw + [stoch])[-STOCH_SMOOTH:]
        if len(self.rsis) < STOCH_PERIOD or len(self.raw) < STOCH_SMOOTH:
            return None
        return sum(self.raw) / STOCH_SMOOTH


def _max_drawdown_pct(equity: list[float]) -> float:
    peak, worst = 0.0, 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100.0)
    return round(worst, 4)


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def simulate_cycle_compounding(
    daily_candles: Any,
    *,
    initial_coins: float = 100.0,
    trim_fraction: float = 0.35,
    ladder_weights: tuple[float, ...] = (0.40, 0.35, 0.25),
    lookback_bars: int = 365,
    warmup_bars: int = 60,
    cooldown_bars: int = 30,
    stop_buffer_pct: float = 2.0,
    support_min_age_bars: int = 30,
    breakout_bars: int = 20,
) -> dict[str, Any]:
    """Replay trim, reload and stop rules over daily candles with no lookahead.

    ``daily_candles`` rows are ``[ts, low, high, open, close, ...]`` in any
    order; invalid rows are dropped. ``drawdown_reduction_pct`` is the buy and
    hold maximum drawdown minus the strategy's, in percentage points.
    ``compounded_final_coins`` is the coins actually held at the end, so it is
    zero if the run ends stopped out in USDC; ``strategy_final_value_usd``
    always includes the USDC.
    """
    try:
        initial_coins, trim_fraction, stop_buffer_pct = (
            float(initial_coins), float(trim_fraction), float(stop_buffer_pct)
        )
        weights = [float(w) for w in ladder_weights]
    except (TypeError, ValueError) as exc:
        raise ValueError("numeric parameters must be numbers") from exc
    if not math.isfinite(initial_coins) or initial_coins <= 0:
        raise ValueError("initial_coins must be positive")
    if not 0 < trim_fraction < 1:
        raise ValueError("trim_fraction must be between 0 and 1")
    if len(weights) != len(RUNG_RETRACEMENTS) or any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError("ladder_weights must be three positive numbers")
    if not math.isfinite(stop_buffer_pct) or not 0 <= stop_buffer_pct < 100:
        raise ValueError("stop_buffer_pct must be from 0 to under 100")
    lookback_bars = _positive_int("lookback_bars", lookback_bars)
    warmup_bars = _positive_int("warmup_bars", warmup_bars)
    cooldown_bars = _positive_int("cooldown_bars", cooldown_bars)
    support_min_age_bars = _positive_int("support_min_age_bars", support_min_age_bars)
    breakout_bars = _positive_int("breakout_bars", breakout_bars)
    weights = [w / sum(weights) for w in weights]

    bars = _clean(daily_candles)
    if len(bars) < 2:
        raise ValueError("at least two valid daily candles are required")

    coins, usdc = initial_coins, 0.0
    ladder: dict[str, Any] | None = None
    stopped = False
    last_trim = -cooldown_bars
    completed = 0
    events: list[dict[str, Any]] = []
    momentum = _StochRsi()
    recent_k: list[float] = []
    hodl_equity: list[float] = []
    strategy_equity: list[float] = []

    def record(kind: str, index: int, ts: float, price: float, coins_delta: float, usdc_delta: float, **extra: Any) -> None:
        events.append({
            "type": kind, "index": index, "ts": ts, "price": round(price, 10),
            "coins_delta": round(coins_delta, 10), "usdc_delta": round(usdc_delta, 6),
            "coins_after": round(coins, 10), "usdc_after": round(usdc, 6), **extra,
        })

    for i, (ts, low, high, open_, close) in enumerate(bars):
        k = momentum.push(close)
        prior_k = recent_k[-1] if recent_k else None
        ready = i >= warmup_bars
        start = max(0, i - lookback_bars + 1)

        # 1. Reload rungs touched by this bar.
        if ladder is not None:
            for rung in ladder["rungs"]:
                if rung["filled"] or low > rung["price"]:
                    continue
                fill = min(open_, rung["price"])
                bought = rung["usdc"] / fill
                coins += bought
                usdc -= rung["usdc"]
                rung["filled"] = True
                record(
                    "RELOAD_ACCUMULATE", i, ts, fill, bought, -rung["usdc"],
                    reason="fib_reload_rung", rung=rung["index"], retracement=rung["retracement"],
                    trim_index=ladder["trim_index"],
                )
            if all(rung["filled"] for rung in ladder["rungs"]):
                ladder = None
                completed += 1
                usdc = 0.0 if abs(usdc) < 1e-9 else usdc

        # 2. Protective stop below an established cycle low.
        if ready and coins > 0 and i > 0:
            prior_lows = [bar[1] for bar in bars[max(0, i - lookback_bars):i]]
            support = min(prior_lows)
            age = len(prior_lows) - prior_lows.index(support)  # bars since it was first set
            if age >= support_min_age_bars and close < support * (1 - stop_buffer_pct / 100.0):
                sold, proceeds = coins, coins * close
                usdc += proceeds
                coins = 0.0
                ladder = None  # unfilled rungs are cancelled; their USDC stays in cash
                stopped = True
                record(
                    "PROTECTIVE_STOP", i, ts, close, -sold, proceeds,
                    reason="structural_support_break", support=round(support, 10),
                )

        # 3. Re-entry after a stop, on a confirmed breakout.
        elif stopped and coins == 0 and usdc > 0 and i >= breakout_bars:
            ceiling = max(bar[2] for bar in bars[i - breakout_bars:i])
            if close > ceiling:
                spent, bought = usdc, usdc / close
                coins, usdc, stopped = bought, 0.0, False
                record(
                    "RELOAD_ACCUMULATE", i, ts, close, bought, -spent,
                    reason="low_confirmation_breakout", breakout_above=round(ceiling, 10),
                )

        # 4. Trim into the upper zone when momentum rolls over.
        if (
            ready and coins > 0 and ladder is None and not stopped
            and i - last_trim >= cooldown_bars
            and k is not None and prior_k is not None and k < prior_k
            and max(recent_k[-ROLLOVER_MEMORY_BARS:]) >= ROLLOVER_FROM
        ):
            window = bars[start:i + 1]
            box_low, box_high = min(bar[1] for bar in window), max(bar[2] for bar in window)
            if box_high > box_low and math.log(close / box_low) / math.log(box_high / box_low) >= TRIM_ZONE_MIN:
                sold = coins * trim_fraction
                freed = sold * close
                coins -= sold
                usdc += freed
                last_trim = i
                span = math.log(box_low / box_high)
                ladder = {
                    "trim_index": i,
                    "rungs": [
                        {
                            "index": n + 1, "retracement": ratio,
                            # Never above the sale price, so a fill always adds coins.
                            "price": min(close, box_high * math.exp(span * ratio)),
                            "usdc": freed * weight, "filled": False,
                        }
                        for n, (ratio, weight) in enumerate(zip(RUNG_RETRACEMENTS, weights))
                    ],
                }
                record(
                    "TRIM_TO_USDC", i, ts, close, -sold, freed,
                    reason="upper_zone_momentum_rollover",
                    box_low=round(box_low, 10), box_high=round(box_high, 10),
                    rung_prices=[round(rung["price"], 10) for rung in ladder["rungs"]],
                )

        if k is not None:
            recent_k.append(k)
        hodl_equity.append(initial_coins * close)
        strategy_equity.append(coins * close + usdc)

    last_close = bars[-1][4]
    hodl_dd, strategy_dd = _max_drawdown_pct(hodl_equity), _max_drawdown_pct(strategy_equity)
    extra = coins - initial_coins
    return {
        "initial_coins": initial_coins,
        "hodl_final_coins": initial_coins,
        "compounded_final_coins": round(coins, 8),
        "extra_coins_gained": round(extra, 8),
        "extra_coins_pct": round(extra / initial_coins * 100.0, 4),
        "freed_usdc_remaining": round(usdc, 2),
        "hodl_final_value_usd": round(hodl_equity[-1], 2),
        "strategy_final_value_usd": round(strategy_equity[-1], 2),
        "strategy_final_coin_equivalent": round(strategy_equity[-1] / last_close, 8),
        "max_drawdown_hodl_pct": hodl_dd,
        "max_drawdown_strategy_pct": strategy_dd,
        "drawdown_reduction_pct": round(hodl_dd - strategy_dd, 4),
        "completed_trim_reload_cycles": completed,
        "open_ladder": None if ladder is None else {
            "trim_index": ladder["trim_index"],
            "unfilled_rungs": [
                {"index": rung["index"], "price": round(rung["price"], 10), "usdc": round(rung["usdc"], 2)}
                for rung in ladder["rungs"] if not rung["filled"]
            ],
        },
        "ended_stopped_out": stopped,
        "bars": len(bars),
        "first_timestamp": bars[0][0],
        "last_timestamp": bars[-1][0],
        "events": events,
        "fresh_cash_added_usd": 0.0,
        "outcome_validated": False,
    }
