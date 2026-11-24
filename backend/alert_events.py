"""Group raw detector alerts into fast-moving, explainable signal events."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable
import hashlib
import math
import time


EVENT_RULE_VERSION = "event-evolution-v1-2026-07-14"
DEFAULT_EVENT_GAP_SECONDS = 10 * 60
DEFAULT_EVENT_RETENTION_SECONDS = 20 * 60

_SEVERITY_RANK = {"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}
_STATE_BASE = {
    "Building": 48,
    "Breakout": 66,
    "Moonwalking": 82,
    "Reversal Risk": 72,
}

_MOONWALKING = ("moonshot", "coin_fomo", "market_fomo_siren")
_BREAKOUT = (
    "breakout",
    "coin_breadth_thrust",
    "coin_squeeze_break",
    "coin_trend_break_up",
    "coin_persistent_gainer",
    "coin_reversal_up",
)
_RISK = (
    "crater",
    "dump",
    "coin_reversal_down",
    "coin_fakeout",
    "coin_exhaustion_top",
    "coin_breadth_failure",
    "coin_trend_break_down",
    "coin_persistent_loser",
    "market_fear_siren",
)
_BUILDING = (
    "whale",
    "stealth",
    "liquidity_shock",
    "volatility_expansion",
    "divergence",
    "exhaustion_bottom",
)


def _as_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except Exception:
        return None


def _ts_ms(alert: dict[str, Any]) -> int | None:
    for key in ("event_ts_ms", "ts_ms", "event_ts", "ts"):
        value = alert.get(key)
        if value is None:
            continue
        number = _as_float(value)
        if number is not None:
            if number < 10_000_000_000:
                number *= 1000.0
            return int(number)
        try:
            return int(
                datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
                * 1000
            )
        except Exception:
            continue
    return None


def _product_id(alert: dict[str, Any]) -> str:
    raw = str(alert.get("product_id") or alert.get("symbol") or "").strip().upper()
    if not raw or raw in {"MARKET", "MARKET-USD"}:
        return ""
    return raw if "-" in raw else f"{raw}-USD"


def _type_key(alert: dict[str, Any]) -> str:
    return str(alert.get("type_key") or alert.get("type") or "unknown").strip().lower()


def _direction(alert: dict[str, Any]) -> str:
    raw = str(alert.get("direction") or "").strip().lower()
    if raw in {"up", "bullish", "accumulation", "euphoria"}:
        return "up"
    if raw in {"down", "bearish", "distribution", "fear"}:
        return "down"
    evidence = alert.get("evidence") if isinstance(alert.get("evidence"), dict) else {}
    for key in ("pct_1m", "pct", "pct_3m", "candle_pct"):
        value = _as_float(evidence.get(key) if key in evidence else alert.get(key))
        if value is not None and value != 0:
            return "up" if value > 0 else "down"
    return "neutral"


def classify_alert_state(alert: dict[str, Any]) -> str:
    """Map one detector alert to its user-facing event state."""
    key = _type_key(alert)
    if any(token in key for token in _RISK):
        return "Reversal Risk"
    if any(token in key for token in _MOONWALKING):
        return "Moonwalking"
    if any(token in key for token in _BREAKOUT):
        return "Breakout"
    if any(token in key for token in _BUILDING):
        return "Building"
    return "Building"


def _family(alert: dict[str, Any]) -> str:
    key = _type_key(alert)
    if "whale" in key or "stealth" in key or "liquidity_shock" in key:
        return "flow"
    if "social" in key or "sentiment" in key or "engagement" in key:
        return "social"
    if any(
        token in key
        for token in ("funding", "open_interest", "liquidation", "derivative", "taker")
    ):
        return "derivatives"
    if any(
        token in key for token in ("reversal", "fakeout", "exhaustion", "divergence")
    ):
        return "structure"
    if any(
        token in key
        for token in ("fomo", "breadth", "squeeze", "persistent", "trend_break")
    ):
        return "momentum"
    if any(
        token in key for token in ("moonshot", "crater", "breakout", "dump", "impulse")
    ):
        return "price"
    return key or "unknown"


def _modifiers(alerts: list[dict[str, Any]]) -> list[str]:
    families = {_family(alert) for alert in alerts}
    types = {_type_key(alert) for alert in alerts}
    out: list[str] = []
    if "flow" in families:
        out.append("Flow")
    if "social" in families:
        out.append("Social")
    if "derivatives" in families:
        out.append("Derivatives")
    if any(
        any(
            token in key
            for token in (
                "fomo",
                "breadth_thrust",
                "squeeze",
                "persistent_gainer",
                "trend_break_up",
            )
        )
        for key in types
    ):
        out.append("Heating")
    return out


def _next_state(current: str | None, candidate: str, alert: dict[str, Any]) -> str:
    if current is None:
        return candidate
    if candidate == "Reversal Risk":
        return candidate
    if current == "Reversal Risk":
        # Only an explicit bullish reversal begins recovery inside the same event.
        return "Building" if "reversal_up" in _type_key(alert) else current
    rank = {"Building": 1, "Breakout": 2, "Moonwalking": 3}
    return candidate if rank.get(candidate, 0) > rank.get(current, 0) else current


def _event_id(symbol: str, first_ts_ms: int) -> str:
    seed = f"{symbol}|{first_ts_ms}".encode("utf-8")
    return f"event_{symbol.replace('-', '_')}_{hashlib.sha1(seed).hexdigest()[:10]}"


def _event_confidence(
    state: str, alerts: list[dict[str, Any]], modifiers: list[str]
) -> tuple[int, dict[str, int]]:
    families = {_family(alert) for alert in alerts}
    highest_severity = max(
        (
            _SEVERITY_RANK.get(str(alert.get("severity") or "info").lower(), 1)
            for alert in alerts
        ),
        default=1,
    )
    severity_points = {1: 0, 2: 1, 3: 3, 4: 6, 5: 9}[highest_severity]
    confirmation_points = min(12, max(0, len(families) - 1) * 4)
    modifier_points = min(6, len(modifiers) * 3)
    persistence_points = min(6, max(0, len(alerts) - 1) * 2)
    components = {
        "state": _STATE_BASE.get(state, 45),
        "severity": severity_points,
        "independent_families": confirmation_points,
        "modifiers": modifier_points,
        "persistence": persistence_points,
    }
    return min(99, sum(components.values())), components


def _severity_for(confidence: int, state: str) -> str:
    if confidence >= 90 or (state == "Reversal Risk" and confidence >= 84):
        return "critical"
    if confidence >= 78:
        return "high"
    if confidence >= 62:
        return "medium"
    return "low"


def _read_pct(evidence: dict[str, Any]) -> float | None:
    for key in ("pct_1m", "pct_3m", "pct", "candle_pct"):
        value = _as_float(evidence.get(key))
        if value is not None:
            return value
    return None


def _format_read_price(value: float) -> str:
    if abs(value) >= 100:
        return f"${value:,.2f}"
    if abs(value) >= 1:
        return f"${value:,.3f}".rstrip("0").rstrip(".")
    return f"${value:.8f}".rstrip("0").rstrip(".")


def _read_history(evidence: dict[str, Any]) -> dict[str, Any]:
    raw = evidence.get("historical_result")
    history = raw if isinstance(raw, dict) else {}
    sample_size = int(_as_float(history.get("sample_size")) or 0)
    rate = _as_float(history.get("follow_through_rate"))
    if rate is None:
        rate = _as_float(history.get("continuation_rate"))
    if rate is not None and 0 <= rate <= 1:
        rate *= 100
    # Readiness is the store's decision, not this module's.  A local sample-size
    # threshold here would be a second, competing evidence bar — and would keep
    # quoting a rate the store had already withdrawn.
    # Defaults to learning: a payload that omits readiness has not asserted it,
    # and absence must never be read as permission to publish.
    measured = str(history.get("measurement_status") or "learning") == "measured"
    if measured and rate is not None and 0 <= rate <= 100:
        target_pct = _as_float(history.get("target_pct"))
        adverse_pct = _as_float(history.get("adverse_pct"))
        if target_pct is not None and adverse_pct is not None:
            label = (
                f"{rate:.0f}% of {sample_size} reached +{target_pct:g}% "
                f"before -{adverse_pct:g}%"
            )
        else:
            label = f"{rate:.0f}% of {sample_size} comparable events followed through"
        return {
            "status": "measured",
            "sample_size": sample_size,
            "follow_through_rate": round(rate, 1),
            "label": label,
        }
    collecting_label = "Comparable-event history is still being collected"
    required = history.get("required_market_periods")
    if required:
        periods = int(_as_float(history.get("market_periods")) or 0)
        collecting_label = (
            f"Track record still collecting — {periods} of {required} market periods"
        )
    return {
        "status": "collecting",
        "sample_size": sample_size,
        "follow_through_rate": None,
        "label": collecting_label,
    }


def derive_event_read(
    *,
    state: str,
    confidence: int,
    direction: str,
    families: Iterable[str],
    modifiers: Iterable[str],
    evidence: dict[str, Any] | None = None,
    conflicting_directions: bool = False,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a concise market interpretation without issuing a trade command."""
    evidence = evidence if isinstance(evidence, dict) else {}
    context = context if isinstance(context, dict) else {}
    family_set = {str(item).lower() for item in families or []}
    modifier_set = {str(item).lower() for item in modifiers or []}
    family_count = len(family_set)
    pct = _read_pct(evidence)
    resolved_direction = str(direction or "neutral").lower()
    if pct is not None and abs(pct) >= 0.25:
        resolved_direction = "up" if float(pct) > 0 else "down"
    elif resolved_direction == "neutral" and pct not in (None, 0):
        resolved_direction = "up" if float(pct) > 0 else "down"

    spot_pressure = str(context.get("spot_pressure") or "neutral").lower()
    spot_aligned = (spot_pressure == "buying" and resolved_direction == "up") or (
        spot_pressure == "selling" and resolved_direction == "down"
    )
    spot_opposed = (spot_pressure == "buying" and resolved_direction == "down") or (
        spot_pressure == "selling" and resolved_direction == "up"
    )
    effective_family_count = family_count + (1 if spot_aligned else 0)
    conflicting_directions = bool(conflicting_directions or spot_opposed)

    if state == "Reversal Risk":
        if (
            resolved_direction == "down"
            and confidence >= 88
            and effective_family_count >= 2
        ):
            label = "BREAKDOWN CONFIRMED"
            tone = "risk"
            summary = "Selling pressure has multiple confirmations and the earlier move is failing."
        elif resolved_direction == "down":
            label = "DOWNSIDE PRESSURE BUILDING"
            tone = "risk"
            summary = (
                "Selling pressure is strengthening and the earlier move may be failing."
            )
        else:
            label = "REVERSAL RISK RISING"
            tone = "caution"
            summary = "The original move is losing confirmation and may be reversing."
        condition = "until the move regains independent confirmation"
    elif conflicting_directions:
        label = "MIXED — NO CLEAR EDGE"
        tone = "neutral"
        condition = "until the independent signals agree"
        summary = "The available evidence is pointing in different directions."
    elif state == "Moonwalking":
        if confidence >= 85 and effective_family_count >= 2:
            label = "CONTINUATION FAVORED"
            tone = "favorable"
            condition = "while the move keeps independent confirmation"
            summary = (
                "The move is unusually strong and more than one signal source agrees."
            )
        else:
            label = "STRONG · STILL UNPROVEN"
            tone = "watch"
            condition = "until another independent signal confirms it"
            summary = "The price move is strong, but confirmation is still limited."
    elif state == "Breakout":
        if confidence >= 78 and effective_family_count >= 2:
            label = "CONTINUATION FAVORED"
            tone = "favorable"
            condition = "while the breakout remains confirmed"
            summary = "Price momentum and independent activity are confirming the move."
        else:
            label = "EARLY — WATCH FOR CONFIRMATION"
            tone = "watch"
            condition = "until another independent signal confirms the breakout"
            summary = (
                "The move has broken out, but supporting evidence is still limited."
            )
    elif ("flow" in family_set or "flow" in modifier_set) and (
        pct is None or abs(pct) < 0.25
    ):
        label = "QUIET FLOW BUILDING"
        tone = "watch"
        condition = "until price confirms the direction of the unusual flow"
        summary = "Unusually heavy trading is appearing before a confirmed price move."
    elif resolved_direction == "down":
        label = "DOWNSIDE PRESSURE BUILDING"
        tone = "risk"
        condition = "until selling pressure eases"
        summary = (
            "Early downside activity is appearing, but the move is not fully confirmed."
        )
    elif "flow" in family_set or "flow" in modifier_set:
        label = "QUIET STRENGTH BUILDING"
        tone = "watch"
        condition = "until price activity confirms the unusual flow"
        summary = "Unusually heavy trading is appearing before a confirmed price move."
    else:
        label = "EARLY — WATCH FOR CONFIRMATION"
        tone = "watch"
        condition = "until another independent signal confirms the move"
        summary = "Something unusual is developing, but it remains early."

    invalidation_price = _as_float(evidence.get("invalidation_price"))
    if invalidation_price is not None and invalidation_price > 0:
        formatted_price = _format_read_price(invalidation_price)
        if resolved_direction == "down":
            condition = f"while price stays below {formatted_price}"
        else:
            condition = f"while price holds above {formatted_price}"

    confirmations: list[str] = []
    if "flow" in family_set or "flow" in modifier_set:
        confirmations.append("heavy flow")
    if "social" in family_set or "social" in modifier_set:
        confirmations.append("social attention")
    if "derivatives" in family_set or "derivatives" in modifier_set:
        confirmations.append("derivatives activity")
    if "momentum" in family_set:
        confirmations.append("price momentum")
    if spot_pressure == "buying":
        confirmations.append("Coinbase spot buying")
    elif spot_pressure == "selling":
        confirmations.append("Coinbase spot selling")

    market_relation = str(context.get("market_relation") or "neutral")
    if state != "Reversal Risk" and market_relation == "market_carried":
        label = "MARKET-LED MOVE"
        tone = "watch"
        condition = "until the coin shows strength beyond the wider market"
        summary = "The move is real, but most of it is also happening across the wider market."
    elif market_relation == "breaking_away":
        relation_summary = str(context.get("market_relation_summary") or "").strip()
        if relation_summary and relation_summary.lower() not in summary.lower():
            summary = f"{summary} {relation_summary}"

    risk_note = None
    liquidity = str(context.get("liquidity") or "normal")
    if liquidity == "thin":
        risk_note = (
            "Thin liquidity can make both continuation and reversal unusually sharp."
        )
    elif liquidity == "wide":
        risk_note = "The wider spread raises slippage and execution risk."

    return {
        "label": label,
        "tone": tone,
        "condition": condition,
        "summary": summary,
        "confirmation_count": effective_family_count,
        "confirmations": confirmations[:3],
        "history": _read_history(evidence),
        "risk_note": risk_note,
        "is_directional_advice": False,
    }


def enrich_event(
    event: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    historical_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach context/history and rebuild The Read from canonical inputs."""
    out = dict(event or {})
    evidence = dict(out.get("evidence") or {})
    if isinstance(historical_result, dict):
        evidence["historical_result"] = dict(historical_result)
    context = dict(context or {})
    out["evidence"] = evidence
    out["market_context"] = context
    out["context_badges"] = list(context.get("badges") or [])[:2]
    out["the_read"] = derive_event_read(
        state=str(out.get("primary_state") or "Building"),
        confidence=int(_as_float(out.get("confidence")) or 0),
        direction=str(out.get("direction") or "neutral"),
        families=list(out.get("families") or []),
        modifiers=list(out.get("modifiers") or []),
        evidence=evidence,
        conflicting_directions=bool(evidence.get("conflicting_directions")),
        context=context,
    )
    return out


def _transition_path(transitions: list[dict[str, Any]]) -> str:
    states = [str(item.get("to") or "") for item in transitions if item.get("to")]
    return " -> ".join(states)


def _build_event(
    symbol: str, alerts: list[dict[str, Any]], retention_seconds: int
) -> dict[str, Any]:
    alerts = sorted(alerts, key=lambda item: _ts_ms(item) or 0)
    first_ts = _ts_ms(alerts[0]) or int(time.time() * 1000)
    last_ts = _ts_ms(alerts[-1]) or first_ts
    current_state: str | None = None
    transitions: list[dict[str, Any]] = []
    for alert in alerts:
        candidate = classify_alert_state(alert)
        next_state = _next_state(current_state, candidate, alert)
        if next_state != current_state:
            transitions.append(
                {
                    "from": current_state,
                    "to": next_state,
                    "ts_ms": _ts_ms(alert) or last_ts,
                    "trigger": _type_key(alert),
                    "alert_id": str(alert.get("id") or ""),
                }
            )
            current_state = next_state

    state = current_state or "Building"
    modifiers = _modifiers(alerts)
    confidence, confidence_components = _event_confidence(state, alerts, modifiers)
    event_id = _event_id(symbol, first_ts)
    transition_ts = int(transitions[-1]["ts_ms"] if transitions else last_ts)
    primary_alert = alerts[-1]
    latest_evidence = (
        primary_alert.get("evidence")
        if isinstance(primary_alert.get("evidence"), dict)
        else {}
    )
    families = sorted({_family(alert) for alert in alerts})
    detector_types = sorted({_type_key(alert) for alert in alerts})
    direction = _direction(primary_alert)
    if state == "Reversal Risk" and direction == "neutral":
        direction = "down"
    path = _transition_path(transitions)
    modifier = modifiers[0] if modifiers else None
    latest_direction_by_family: dict[str, str] = {}
    for alert in alerts:
        alert_direction = _direction(alert)
        if alert_direction in {"up", "down"}:
            latest_direction_by_family[_family(alert)] = alert_direction
    conflicting_directions = len(set(latest_direction_by_family.values())) > 1
    event_read = derive_event_read(
        state=state,
        confidence=confidence,
        direction=direction,
        families=families,
        modifiers=modifiers,
        evidence=latest_evidence,
        conflicting_directions=conflicting_directions,
    )
    base_symbol = symbol.split("-")[0]
    message = f"{base_symbol} {path or state}"
    if modifier:
        message += f" with {modifier.lower()} confirmation"
    message += f" ({len(alerts)} detection{'s' if len(alerts) != 1 else ''}, confidence {confidence})"

    notify_eligible = confidence >= 85 or (
        state == "Reversal Risk" and confidence >= 80
    )
    expires_ms = last_ts + (int(retention_seconds) * 1000)
    expires_at = datetime.fromtimestamp(
        expires_ms / 1000.0, tz=timezone.utc
    ).isoformat()
    return {
        "id": f"{event_id}:{transition_ts}",
        "event_id": event_id,
        "event_rule_version": EVENT_RULE_VERSION,
        "rule_version": primary_alert.get("rule_version"),
        "symbol": symbol,
        "product_id": symbol,
        "type": "signal_event",
        "type_key": _type_key(primary_alert),
        "primary_state": state,
        "modifier": modifier,
        "modifiers": modifiers,
        "confidence": confidence,
        "confidence_components": confidence_components,
        "severity": _severity_for(confidence, state),
        "direction": direction,
        "title": f"{state.upper()}: {base_symbol}",
        "message": message,
        "event_ts_ms": last_ts,
        "ts_ms": last_ts,
        "first_seen_ts_ms": first_ts,
        "last_seen_ts_ms": last_ts,
        "latest_transition_ts_ms": transition_ts,
        "expires_at": expires_at,
        "alert_count": len(alerts),
        "families": families,
        "detector_types": detector_types,
        "contributing_alert_ids": [
            str(alert.get("id") or "") for alert in alerts if alert.get("id")
        ],
        "evolution": transitions,
        "evidence": {
            **latest_evidence,
            "event_state": state,
            "event_modifier": modifier,
            "event_path": path,
            "detector_count": len(alerts),
            "independent_families": len(families),
            "conflicting_directions": conflicting_directions,
        },
        "trade_url": primary_alert.get("trade_url")
        or f"https://www.coinbase.com/advanced-trade/spot/{symbol}",
        "delivery_tier": "notify" if notify_eligible else "signal",
        "notify_eligible": notify_eligible,
        "the_read": event_read,
    }


def build_event_evolution(
    alerts: Iterable[dict[str, Any]],
    *,
    now_ms: int | None = None,
    gap_seconds: int = DEFAULT_EVENT_GAP_SECONDS,
    retention_seconds: int = DEFAULT_EVENT_RETENTION_SECONDS,
) -> list[dict[str, Any]]:
    """Build the latest grouped event for each symbol from raw alert history."""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    cutoff_ms = now_ms - (max(60, int(retention_seconds)) * 1000)
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in alerts or []:
        if not isinstance(raw, dict):
            continue
        ts = _ts_ms(raw)
        symbol = _product_id(raw)
        if ts is None or ts < cutoff_ms or not symbol:
            continue
        by_symbol[symbol].append(raw)

    events: list[dict[str, Any]] = []
    gap_ms = max(60, int(gap_seconds)) * 1000
    for symbol, rows in by_symbol.items():
        ordered = sorted(rows, key=lambda item: _ts_ms(item) or 0)
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        previous_ts: int | None = None
        for alert in ordered:
            ts = _ts_ms(alert) or now_ms
            if previous_ts is not None and (ts - previous_ts) > gap_ms:
                if current:
                    groups.append(current)
                current = []
            current.append(alert)
            previous_ts = ts
        if current:
            groups.append(current)
        if groups:
            events.append(_build_event(symbol, groups[-1], retention_seconds))

    events.sort(
        key=lambda item: (
            int(item.get("confidence") or 0),
            int(item.get("last_seen_ts_ms") or 0),
        ),
        reverse=True,
    )
    return events


def notification_candidates(
    events: Iterable[dict[str, Any]],
    *,
    priority_symbols: Iterable[str] | None = None,
    priority_min_confidence: int = 65,
) -> list[dict[str, Any]]:
    """Filter events to deliverable notifications.

    Symbols in priority_symbols (user's portfolio holdings and watchlist)
    qualify at the lower Alerts-Center confidence bar instead of the
    standard notify bar, and are tagged so delivery/UI can surface that the
    event concerns something the user actually holds.
    """
    priority = {
        str(sym).split("-")[0].upper() for sym in (priority_symbols or []) if sym
    }
    out: list[dict[str, Any]] = []
    for event in events or []:
        row = dict(event)
        base = str(row.get("symbol") or "").split("-")[0].upper()
        is_priority = base in priority
        if is_priority:
            row["priority"] = "holding"
        standard = bool(row.get("notify_eligible"))
        elevated = (
            is_priority
            and not standard
            and int(row.get("confidence") or 0) >= int(priority_min_confidence)
        )
        if not (standard or elevated):
            continue
        if elevated:
            row["notify_eligible"] = True
            row["delivery_tier"] = "notify"
            row["notify_reason"] = "holding_priority"
        out.append(row)
    return out
