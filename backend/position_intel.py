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


# Threshold bands (absolute 24h % move) for the descriptive fallback read used
# when a holding has no live Event Evolution signal. Crypto alts wiggle a few
# percent as baseline noise, so <2% reads as "quiet" and >8% as a "big move".
_DESCRIPTIVE_QUIET_PCT = 2.0
_DESCRIPTIVE_BIG_PCT = 8.0


def _descriptive_read(change_24h_pct: float | None) -> dict[str, Any] | None:
    """Derive a plain-language 24h read from a holding's price change alone.

    Returns a posture + short read for coins that have no BHABIT signal, so the
    card shows real content instead of "no live signal". This is descriptive
    only — it reports what price did, it does NOT predict or grade. The
    ``source: "descriptive"`` marker lets the UI (and the coverage stat) keep
    these distinct from real Event Evolution signals.
    """
    if change_24h_pct is None:
        return None

    pct = round(float(change_24h_pct), 2)
    magnitude = abs(pct)
    signed = f"{pct:+.2f}%"

    if magnitude < _DESCRIPTIVE_QUIET_PCT:
        posture, tone, label = "descriptive_flat", "muted", "Quiet today"
        short = f"Trading flat over 24h ({signed})."
    elif magnitude < _DESCRIPTIVE_BIG_PCT:
        if pct > 0:
            posture, tone, label = "descriptive_up", "positive", "Up today"
            short = f"Up {signed} over 24h."
        else:
            posture, tone, label = "descriptive_down", "warning", "Down today"
            short = f"Down {signed} over 24h."
    else:
        if pct > 0:
            posture, tone, label = "descriptive_up_strong", "positive", "Up big today"
            short = f"Big 24h move up ({signed})."
        else:
            posture, tone, label = (
                "descriptive_down_strong",
                "danger",
                "Down big today",
            )
            short = f"Big 24h move down ({signed})."

    return {
        "posture": posture,
        "tone": tone,
        "label": label,
        "short": short,
        "change_24h_pct": pct,
        "horizon": "24h",
        "source": "descriptive",
    }


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
    board_row: dict[str, Any] | None = None,
    positioning: dict[str, Any] | None = None,
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
        intel["read_source"] = "signal"
    else:
        # No live BHABIT signal — fall back to a descriptive read built from the
        # 24h price change every holding already carries, so board non-movers
        # still show real content. Marked read_source="descriptive" so the
        # signal-coverage stat (below) does NOT count these as real signals.
        descriptive = _descriptive_read(holding.get("price_change_24h_pct"))
        if descriptive:
            intel["posture"] = descriptive["posture"]
            intel["read_source"] = "descriptive"
            intel["read"] = {
                "short": descriptive["short"],
                "label": descriptive["label"],
                "tone": descriptive["tone"],
                "change_24h_pct": descriptive["change_24h_pct"],
                "horizon": descriptive["horizon"],
                "source": "descriptive",
            }
        else:
            intel["posture"] = "no_signal"
            intel["read_source"] = "none"

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

    if board_row:
        board_intel: dict[str, Any] = {}
        for key in (
            "change_1m",
            "change_3m",
            "price_change_1m",
            "price_change_3m",
            "volume_1h_now",
            "volume_1h_prev",
            "volume_change_1h_pct",
            "momentum",
        ):
            val = board_row.get(key)
            if val is not None:
                board_intel[key] = val
        change_1m = board_intel.get("change_1m") or board_intel.get("price_change_1m")
        change_3m = board_intel.get("change_3m") or board_intel.get("price_change_3m")
        if change_1m is not None:
            board_intel["change_1m"] = change_1m
        if change_3m is not None:
            board_intel["change_3m"] = change_3m

        vol_now = board_intel.get("volume_1h_now")
        vol_prev = board_intel.get("volume_1h_prev")
        if vol_now and vol_prev and vol_prev > 0:
            board_intel["volume_change_1h_pct"] = round(
                ((vol_now - vol_prev) / vol_prev) * 100, 1
            )

        sentiment = board_row.get("sentiment")
        if isinstance(sentiment, dict):
            board_intel["sentiment"] = sentiment
        elif isinstance(sentiment, (int, float)):
            board_intel["sentiment_score"] = sentiment

        if board_intel:
            intel["board"] = board_intel

    # Derivatives positioning is *context* that qualifies the price case. It is
    # intentionally a distinct key and is NOT a real signal — the signal-coverage
    # stat keys off read_source/signal only, so this never inflates coverage.
    if positioning and positioning.get("available"):
        intel["positioning"] = positioning

    return intel


def _range_zone_phrase(zone: str) -> str:
    return {
        "near_support": "sitting near recent support",
        "lower_range": "in the lower part of its recent range",
        "mid_range": "mid-range",
        "upper_range": "in the upper part of its recent range",
        "near_resistance": "pressing recent resistance",
    }.get(zone, "")


def enrich_portfolio(
    snapshot: dict[str, Any],
    *,
    signals: list[dict[str, Any]] | None = None,
    active_alerts: list[dict[str, Any]] | None = None,
    board_data: dict[str, dict[str, Any]] | None = None,
    levels_data: dict[str, dict[str, Any]] | None = None,
    positioning_data: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add position intelligence to every holding and open order in a portfolio snapshot.

    board_data: symbol → row dict with keys like change_1m, change_3m,
    volume_1h_now, volume_1h_prev, sentiment, momentum.

    levels_data: symbol → descriptive levels dict from position_levels.compute_levels
    (support/resistance, ATR band, range position). Attached as holding["levels"]
    and used to enrich the descriptive read with recent-range context.

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

    board_by_symbol = board_data or {}
    levels_by_symbol = levels_data or {}
    positioning_by_symbol = positioning_data or {}

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
            board_row=board_by_symbol.get(sym),
            positioning=positioning_by_symbol.get(sym),
        )

        levels = levels_by_symbol.get(sym)
        if levels:
            holding["levels"] = levels
            # Fold recent-range context into a descriptive-only read so the
            # extra candle sources reach the card even without a live signal.
            intel = holding["intel"]
            if intel.get("read_source") == "descriptive" and isinstance(
                intel.get("read"), dict
            ):
                phrase = _range_zone_phrase(levels.get("range_zone", ""))
                if phrase:
                    intel["read"][
                        "short"
                    ] = f"{intel['read']['short']} Currently {phrase}."

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

    non_cash = [h for h in snapshot.get("holdings") or [] if not h.get("is_cash")]
    # "Signal coverage" stays pure: only holdings with a real Event Evolution
    # signal count. Descriptive 24h reads are tracked separately so the headline
    # stat keeps meaning "has a predictive BHABIT signal", not "has any content".
    held_with_signals = sum(
        1 for h in non_cash if h.get("intel", {}).get("read_source") == "signal"
    )
    held_with_read = sum(
        1
        for h in non_cash
        if h.get("intel", {}).get("read_source") in ("signal", "descriptive")
    )
    holding_count = snapshot.get("summary", {}).get("holding_count", 0)
    denom = max(1, holding_count or len(non_cash))
    snapshot["intel_summary"] = {
        "holdings_with_signals": held_with_signals,
        "holdings_with_read": held_with_read,
        "total_holdings": holding_count,
        "signal_coverage_pct": round(held_with_signals / denom * 100, 1),
        "read_coverage_pct": round(held_with_read / denom * 100, 1),
        "outcome_db_size": signal_outcome_store.status().get("complete", 0),
    }

    return snapshot
