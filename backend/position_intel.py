"""Position Intelligence — enriches portfolio holdings and open orders with
signal context, outcome history, and data-driven assessments.

This module does NOT give trading advice. It surfaces objective data from
the existing signal and outcome tracking systems so the operator can make
faster, more informed decisions.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from signal_outcomes import store as signal_outcome_store
from board_outcomes import store as board_outcome_store


def _symbol(value: Any) -> str:
    return str(value or "").split("-")[0].upper()


def _pct_distance(current: float, target: float) -> float | None:
    if not current or current <= 0:
        return None
    return round(((target / current) - 1.0) * 100.0, 2)


def _assess_order(
    order: dict[str, Any],
    current_price: float | None,
    signal: dict[str, Any] | None,
    outcome_stats: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a contextual assessment for a single open order."""
    assessment: dict[str, Any] = {}

    limit_price = order.get("limit_price")
    side = str(order.get("side") or "").upper()

    if current_price and limit_price and current_price > 0:
        distance_pct = _pct_distance(current_price, limit_price)
        assessment["distance_from_current_pct"] = distance_pct

        if side == "SELL" and distance_pct is not None and distance_pct < 0:
            assessment["order_type_hint"] = "stop_loss"
            assessment["buffer_pct"] = abs(distance_pct)
        elif side == "SELL" and distance_pct is not None and distance_pct > 0:
            assessment["order_type_hint"] = "take_profit"
            assessment["upside_to_target_pct"] = distance_pct
        elif side == "BUY" and distance_pct is not None and distance_pct < 0:
            assessment["order_type_hint"] = "limit_buy"
            assessment["discount_pct"] = abs(distance_pct)

    if signal:
        state = signal.get("primary_state", "")
        direction = str(signal.get("direction") or "").lower()
        confidence = int(signal.get("confidence") or 0)

        assessment["signal_state"] = state
        assessment["signal_direction"] = direction
        assessment["signal_confidence"] = confidence

        read = (
            signal.get("the_read") if isinstance(signal.get("the_read"), dict) else {}
        )
        if read.get("label"):
            assessment["signal_label"] = read["label"]

        if side == "SELL" and assessment.get("order_type_hint") == "stop_loss":
            if direction == "down" and confidence >= 60:
                assessment["context"] = (
                    "Active downside pressure detected — stop may be tested"
                )
            elif direction == "up" and state in ("Confirmed", "Strengthening"):
                assessment["context"] = (
                    "Upside momentum active — stop has breathing room"
                )
            elif state == "Weakening":
                assessment["context"] = "Signal weakening — consider tightening stop"
        elif side == "SELL" and assessment.get("order_type_hint") == "take_profit":
            if direction == "up" and state == "Confirmed":
                assessment["context"] = "Confirmed upside — target may be reachable"
            elif state in ("Weakening", "Fading"):
                assessment["context"] = "Momentum fading — target may not be reached"

    if outcome_stats and outcome_stats.get("sample_size", 0) >= 10:
        ftr = outcome_stats.get("follow_through_rate")
        if ftr is not None:
            assessment["historical_follow_through_pct"] = round(ftr * 100, 1)
            assessment["outcome_sample_size"] = outcome_stats["sample_size"]
        med_fav = outcome_stats.get("median_favorable_pct")
        med_adv = outcome_stats.get("median_adverse_pct")
        if med_fav is not None:
            assessment["median_favorable_move_pct"] = med_fav
        if med_adv is not None:
            assessment["median_adverse_move_pct"] = med_adv

    return assessment


def _assess_holding(
    holding: dict[str, Any],
    signal: dict[str, Any] | None,
    outcome_stats: dict[str, Any] | None,
    active_alerts: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build intelligence context for a single portfolio holding."""
    intel: dict[str, Any] = {}

    if signal:
        state = signal.get("primary_state", "")
        direction = str(signal.get("direction") or "").lower()
        confidence = int(signal.get("confidence") or 0)

        intel["signal"] = {
            "state": state,
            "direction": direction,
            "confidence": confidence,
            "severity": signal.get("severity"),
        }

        read = (
            signal.get("the_read") if isinstance(signal.get("the_read"), dict) else {}
        )
        if read.get("label"):
            intel["signal"]["label"] = read["label"]
        if read.get("short"):
            intel["signal"]["short_read"] = read["short"]

        if direction == "up" and state in ("Confirmed", "Strengthening"):
            intel["posture"] = "momentum_favorable"
        elif direction == "down" and confidence >= 60:
            intel["posture"] = "pressure_adverse"
        elif state in ("Weakening", "Fading"):
            intel["posture"] = "momentum_fading"
        elif state == "Building":
            intel["posture"] = "developing"
        else:
            intel["posture"] = "neutral"
    else:
        intel["posture"] = "no_signal"

    if outcome_stats and outcome_stats.get("sample_size", 0) >= 5:
        intel["history"] = {
            "follow_through_pct": (
                round(outcome_stats["follow_through_rate"] * 100, 1)
                if outcome_stats.get("follow_through_rate") is not None
                else None
            ),
            "sample_size": outcome_stats["sample_size"],
            "median_favorable_pct": outcome_stats.get("median_favorable_pct"),
            "median_adverse_pct": outcome_stats.get("median_adverse_pct"),
            "horizon_minutes": outcome_stats.get("horizon_minutes"),
        }

    if active_alerts:
        intel["active_alert_count"] = len(active_alerts)
        families = set()
        for alert in active_alerts:
            fam = alert.get("family") or alert.get("type") or ""
            if fam:
                families.add(str(fam))
        if families:
            intel["alert_families"] = sorted(families)

    return intel


def enrich_portfolio(
    snapshot: dict[str, Any],
    *,
    signals: list[dict[str, Any]] | None = None,
    active_alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add position intelligence to every holding and open order in a portfolio snapshot.

    Modifies snapshot in place and returns it.
    """
    signal_by_symbol: dict[str, dict[str, Any]] = {}
    for sig in signals or []:
        sym = _symbol(sig.get("symbol"))
        if sym:
            signal_by_symbol[sym] = sig

    alerts_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for alert in active_alerts or []:
        sym = _symbol(alert.get("symbol") or alert.get("product_id"))
        if sym:
            alerts_by_symbol.setdefault(sym, []).append(alert)

    for holding in snapshot.get("holdings") or []:
        sym = _symbol(holding.get("symbol"))
        if not sym or holding.get("is_cash"):
            continue

        signal = signal_by_symbol.get(sym)
        outcome_stats = None
        if signal:
            try:
                outcome_stats = signal_outcome_store.history_for(signal)
            except Exception:
                pass

        holding["intel"] = _assess_holding(
            holding,
            signal,
            outcome_stats,
            alerts_by_symbol.get(sym),
        )

    for order in snapshot.get("open_orders") or []:
        sym = _symbol(order.get("symbol") or order.get("product_id"))
        signal = signal_by_symbol.get(sym)
        outcome_stats = None
        if signal:
            try:
                outcome_stats = signal_outcome_store.history_for(signal)
            except Exception:
                pass

        current_price = None
        for h in snapshot.get("holdings") or []:
            if _symbol(h.get("symbol")) == sym:
                current_price = h.get("price_usd")
                break

        order["intel"] = _assess_order(order, current_price, signal, outcome_stats)

    held_with_signals = sum(
        1
        for h in snapshot.get("holdings") or []
        if h.get("intel", {}).get("posture") != "no_signal" and not h.get("is_cash")
    )
    snapshot["intel_summary"] = {
        "holdings_with_signals": held_with_signals,
        "total_holdings": snapshot.get("summary", {}).get("holding_count", 0),
        "signal_coverage_pct": (
            round(
                held_with_signals
                / max(1, snapshot.get("summary", {}).get("holding_count", 1))
                * 100,
                1,
            )
        ),
        "outcome_db_size": signal_outcome_store.status().get("complete", 0),
    }

    return snapshot
