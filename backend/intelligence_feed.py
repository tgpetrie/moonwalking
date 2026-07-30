"""Delivery path for proactive portfolio change intelligence events.

The detector (``portfolio_change_intelligence``) writes events into the existing
``intelligence_events`` table. Without a read surface those events scream in a
locked room. This module is the door: it serves stored events, joined to the
evidence packet that explains them, as structured JSON.

Deliberately minimal:

- read-only over the detector's output; no detection logic lives here
- no LLM generation — the ``explanation`` field is reserved and returns null
- reuses the Ask Bhabit ``{"success", "data"}`` envelope so the frontend client
  layer is shared, and does not touch any existing Ask Bhabit route
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

try:
    from intelligence_memory import get_intelligence_memory_store
except ImportError:  # package imports under pytest
    from backend.intelligence_memory import get_intelligence_memory_store

try:
    from portfolio_change_intelligence import (
        EVENT_TYPE as PORTFOLIO_CHANGE_INTELLIGENCE,
    )
except ImportError:  # package imports under pytest
    from backend.portfolio_change_intelligence import (
        EVENT_TYPE as PORTFOLIO_CHANGE_INTELLIGENCE,
    )

try:
    from watchlist import get_authenticated_user
except ImportError:  # package imports under pytest
    from backend.watchlist import get_authenticated_user


intelligence_feed_bp = Blueprint("intelligence_feed", __name__)

# Events the user has not dismissed. "detected" is what the detector writes;
# "seen" stays active so re-opening the app does not blank the feed.
ACTIVE_STATUSES = ("detected", "seen")
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _json_ok(data: Any, status: int = 200):
    return jsonify({"success": True, "data": data}), status


def _json_err(code: str, message: str, status: int = 400):
    return (
        jsonify({"success": False, "error": {"code": code, "message": message}}),
        status,
    )


def _headline(event: dict[str, Any]) -> str:
    """Deterministic, factual one-liner. This is NOT an interpretation — it is a
    literal restatement of the recorded numbers, so the feed is readable before
    the LLM explanation layer exists."""
    payload = event.get("payload") or {}
    if event.get("event_type") != PORTFOLIO_CHANGE_INTELLIGENCE:
        return event.get("event_type") or "Intelligence event"

    pct = payload.get("total_change_pct")
    assets = payload.get("affected_assets") or []
    window_label = payload.get("comparison_window_label") or "selected window"
    if isinstance(pct, (int, float)):
        direction = "up" if pct > 0 else "down"
        headline = f"Portfolio {direction} {abs(pct):.2f}% over the {window_label}"
    else:
        headline = f"Portfolio changed over the {window_label}"
    if assets:
        headline += f" — driven by {', '.join(assets)}"
    return headline


def serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Shape one stored event into the feed's view contract.

    Everything here is derived from stored facts. ``explanation`` is reserved
    for the future LLM layer and is intentionally null today.
    """
    packet = event.get("evidence_packet") or {}
    payload = event.get("payload") or {}
    supporting = packet.get("supporting_metrics") or {}
    previous_state = packet.get("previous_state") or {}
    current_state = packet.get("current_state") or {}

    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "status": event.get("status"),
        "observed_at": event.get("observed_at"),
        "importance_score": event.get("importance_score"),
        "headline": _headline(event),
        "what_changed": {
            "reasons": payload.get("reasons") or [],
            "total_change_pct": payload.get("total_change_pct"),
            "total_change_usd": payload.get("total_change_usd"),
        },
        "affected_assets": payload.get("affected_assets") or [],
        "portfolio_impact": {
            "previous_total_usd": previous_state.get("total_value_usd"),
            "current_total_usd": current_state.get("total_value_usd"),
            "change_usd": payload.get("total_change_usd"),
            "change_pct": payload.get("total_change_pct"),
        },
        "previous_state": previous_state,
        "current_state": current_state,
        "supporting_metrics": {
            "biggest_movers": supporting.get("biggest_movers") or [],
            "biggest_positive_contributors": supporting.get(
                "biggest_positive_contributors"
            )
            or [],
            "biggest_negative_contributors": supporting.get(
                "biggest_negative_contributors"
            )
            or [],
            "allocation_changes": supporting.get("allocation_changes") or [],
            "new_positions": supporting.get("new_positions") or [],
            "removed_positions": supporting.get("removed_positions") or [],
            "asset_contributions": supporting.get("asset_contributions") or [],
        },
        "confidence": packet.get("confidence")
        or {"level": "unknown", "source": None, "notes": None},
        "evidence": {
            "packet_id": event.get("evidence_packet_id"),
            "schema_version": event.get("evidence_schema_version"),
            "available": bool(packet),
        },
        # Reserved for the LLM explanation layer; no generation happens yet.
        "explanation": None,
    }


@intelligence_feed_bp.route("/api/intelligence/events", methods=["GET"])
def intelligence_events_route():
    user = get_authenticated_user()
    if not user:
        return _json_err("unauthorized", "Authentication required.", 401)

    try:
        limit = int(request.args.get("limit") or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    limit = max(1, min(limit, MAX_LIMIT))

    include_dismissed = str(request.args.get("include_dismissed") or "").lower() in {
        "1",
        "true",
        "yes",
    }

    try:
        events = get_intelligence_memory_store().list_intelligence_events(
            user_id=user.get("id"),
            statuses=None if include_dismissed else ACTIVE_STATUSES,
            limit=limit,
        )
    except Exception:
        return _json_err(
            "intelligence_unavailable",
            "Intelligence memory is temporarily unavailable.",
            503,
        )

    return _json_ok(
        {
            "events": [serialize_event(event) for event in events],
            "count": len(events),
            "generated_at": request.headers.get("Date"),
        }
    )


@intelligence_feed_bp.route(
    "/api/intelligence/events/<event_id>/status", methods=["POST"]
)
def intelligence_event_status_route(event_id: str):
    """Mark an event ``seen`` or ``dismissed``. This is the minimum the feed
    needs to not repeat itself forever; it is not feedback telemetry."""
    user = get_authenticated_user()
    if not user:
        return _json_err("unauthorized", "Authentication required.", 401)

    body = request.get_json(silent=True) or {}
    status = str(body.get("status") or "").strip().lower()
    if status not in {"seen", "dismissed"}:
        return _json_err(
            "invalid_status", "status must be one of: seen, dismissed.", 400
        )

    try:
        updated = get_intelligence_memory_store().update_intelligence_event_status(
            event_id, status, user_id=user.get("id")
        )
    except Exception:
        return _json_err(
            "intelligence_unavailable",
            "Intelligence memory is temporarily unavailable.",
            503,
        )

    if not updated:
        return _json_err("event_not_found", "No such intelligence event.", 404)
    return _json_ok({"event_id": event_id, "status": status})


__all__ = ["intelligence_feed_bp", "serialize_event"]
