"""Build compact, layman-friendly context from data Moonwalkings already owns."""

from __future__ import annotations

from statistics import median
from typing import Any
import math


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None


def _robust_scale(values: list[float]) -> float:
    if not values:
        return 0.0
    center = median(values)
    deviations = [abs(value - center) for value in values]
    return 1.4826 * median(deviations) if deviations else 0.0


def _window_context(
    price_snapshot: dict[str, dict], key: str
) -> tuple[dict[str, float], float, float]:
    returns: dict[str, float] = {}
    for symbol, row in (price_snapshot or {}).items():
        value = _number((row or {}).get(key))
        if value is not None:
            returns[str(symbol).upper()] = value
    values = list(returns.values())
    return returns, (median(values) if values else 0.0), _robust_scale(values)


def build_signal_context(
    price_snapshot: dict[str, dict],
    tape_snapshot: dict[str, dict] | None = None,
) -> dict[str, dict[str, Any]]:
    """Describe market-relative movement and honest Coinbase tape observations.

    This function creates context only. It does not publish raw alerts, so it
    cannot increase notification volume by itself.
    """
    tape_snapshot = tape_snapshot or {}
    returns_1m, median_1m, scale_1m = _window_context(price_snapshot, "pct_1m")
    returns_3m, median_3m, scale_3m = _window_context(price_snapshot, "pct_3m")
    btc_1m = returns_1m.get("BTC")
    btc_3m = returns_3m.get("BTC")
    symbols = set(price_snapshot or {}) | set(tape_snapshot or {})
    out: dict[str, dict[str, Any]] = {}

    for raw_symbol in symbols:
        symbol = str(raw_symbol).upper().replace("-USD", "")
        row = (
            (price_snapshot or {}).get(raw_symbol)
            or (price_snapshot or {}).get(symbol)
            or {}
        )
        tape = (
            (tape_snapshot or {}).get(raw_symbol)
            or (tape_snapshot or {}).get(symbol)
            or {}
        )
        pct_3m = _number(row.get("pct_3m"))
        pct_1m = _number(row.get("pct_1m"))
        if pct_3m is not None:
            move = pct_3m
            market_move = median_3m
            btc_move = btc_3m
            scale = scale_3m
            window = "3m"
        else:
            move = pct_1m
            market_move = median_1m
            btc_move = btc_1m
            scale = scale_1m
            window = "1m"

        relative = (move - market_move) if move is not None else None
        btc_relative = (
            (move - btc_move) if move is not None and btc_move is not None else None
        )
        unusual_floor = max(0.35, scale * 1.5)
        relation = "neutral"
        relation_label = None
        relation_summary = None
        if move is not None and relative is not None:
            same_as_market = move * market_move > 0
            if abs(move) >= 0.45 and abs(relative) >= unusual_floor:
                relation = "breaking_away"
                relation_label = "BREAKING AWAY"
                relation_summary = (
                    "Moving independently above the wider market."
                    if move > 0
                    else "Falling independently below the wider market."
                )
            elif (
                same_as_market
                and abs(market_move) >= 0.25
                and abs(relative) <= max(0.18, scale * 0.65)
            ):
                relation = "market_carried"
                relation_label = "MARKET CARRIED"
                relation_summary = (
                    "Most of this move is also happening across the wider market."
                )

        trade_imbalance = _number(tape.get("trade_imbalance"))
        observed_quote = _number(tape.get("observed_quote_usd")) or 0.0
        trade_count = int(_number(tape.get("trade_count")) or 0)
        spot_pressure = "neutral"
        spot_label = None
        if (
            trade_count >= 5
            and observed_quote >= 10_000
            and trade_imbalance is not None
        ):
            if trade_imbalance >= 0.35:
                spot_pressure = "buying"
                spot_label = "SPOT BUYING"
            elif trade_imbalance <= -0.35:
                spot_pressure = "selling"
                spot_label = "SPOT SELLING"

        spread_bps = _number(tape.get("spread_bps"))
        liquidity = "normal"
        liquidity_label = None
        if spread_bps is not None and spread_bps >= 80:
            liquidity = "thin"
            liquidity_label = "THIN AIR"
        elif spread_bps is not None and spread_bps >= 30:
            liquidity = "wide"
            liquidity_label = "WIDE SPREAD"

        badges: list[dict[str, str]] = []
        # Keep the row glanceable. Independent movement is the strongest
        # relation tag; ordinary market-following context comes after flow and
        # execution risk so it cannot hide something more actionable.
        if relation_label and relation == "breaking_away":
            badges.append({"label": relation_label, "tone": "context"})
        if spot_label:
            badges.append({"label": spot_label, "tone": "flow"})
        if liquidity_label:
            badges.append({"label": liquidity_label, "tone": "risk"})
        if relation_label and relation == "market_carried":
            badges.append({"label": relation_label, "tone": "context"})

        out[symbol] = {
            "window": window,
            "move_pct": move,
            "market_median_pct": round(market_move, 6),
            "relative_pct": round(relative, 6) if relative is not None else None,
            "btc_relative_pct": (
                round(btc_relative, 6) if btc_relative is not None else None
            ),
            "market_relation": relation,
            "market_relation_label": relation_label,
            "market_relation_summary": relation_summary,
            "spot_pressure": spot_pressure,
            "spot_pressure_label": spot_label,
            "trade_imbalance": trade_imbalance,
            "observed_quote_usd": observed_quote,
            "trade_count": trade_count,
            "spread_bps": spread_bps,
            "liquidity": liquidity,
            "liquidity_label": liquidity_label,
            "badges": badges[:2],
            "source": "coinbase_and_full_universe",
        }
    return out
