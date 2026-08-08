"""HTTP surface for user-scoped alert rules, recommendations, and history.

Every route resolves the caller through ``watchlist.get_authenticated_user()``
and passes that ``user_id`` into the store. A rule id supplied by the browser
is never trusted on its own — the store scopes every read and write by owner.

Registered as a separate blueprint so the existing read-only ``/api/alerts``
contract in app.py is left completely untouched.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

import alert_rules
from alert_rules import RuleError
from watchlist import get_authenticated_user

alert_rules_bp = Blueprint("alert_rules_bp", __name__)

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "Alerts are informational only and are not financial advice. "
    "They cannot guarantee you will avoid a loss."
)


def _current_user_id() -> int | None:
    try:
        user = get_authenticated_user()
    except Exception:
        return None
    if not user:
        return None
    try:
        return int(user.get("id"))
    except (TypeError, ValueError):
        return None


def _unauthorized():
    return jsonify({"error": "Sign in to manage your alerts."}), 401


def _body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _envelope(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("not_financial_advice", True)
    payload.setdefault("disclaimer", _DISCLAIMER)
    return payload


# ─── rules ───────────────────────────────────────────────────────────────────


@alert_rules_bp.route("/api/alert-rules", methods=["GET"])
def list_alert_rules():
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    status = request.args.get("status") or None
    rules = alert_rules.list_rules(user_id, status=status)
    return jsonify(_envelope({"rules": rules, "count": len(rules)}))


@alert_rules_bp.route("/api/alert-rules", methods=["POST"])
def create_alert_rule():
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()

    data = _body()
    params = data.get("params")
    if not isinstance(params, dict):
        # Accept a flat body too, so the quick builder can post plainly.
        params = {
            k: data.get(k)
            for k in ("direction", "threshold", "window")
            if data.get(k) is not None
        }

    try:
        rule = alert_rules.create_rule(
            user_id,
            symbol=data.get("symbol"),
            trigger_type=data.get("trigger_type"),
            params=params,
            repeat_mode=data.get("repeat_mode", "once"),
            cooldown_seconds=data.get("cooldown_seconds"),
            expires_in_days=data.get(
                "expires_in_days", alert_rules.DEFAULT_RULE_TTL_DAYS
            ),
            delivery=data.get("delivery"),
            current_price=data.get("current_price"),
        )
    except RuleError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("[alert-rules] create failed")
        return jsonify({"error": "Could not create that alert."}), 500

    return jsonify(_envelope({"rule": rule})), 201


@alert_rules_bp.route("/api/alert-rules/<rule_id>", methods=["GET"])
def get_alert_rule(rule_id):
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    rule = alert_rules.get_rule(user_id, rule_id)
    if not rule:
        return jsonify({"error": "Alert not found."}), 404
    return jsonify(_envelope({"rule": rule}))


@alert_rules_bp.route("/api/alert-rules/<rule_id>", methods=["PATCH", "PUT"])
def update_alert_rule(rule_id):
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()

    data = _body()
    allowed = {
        k: data[k]
        for k in (
            "params",
            "trigger_type",
            "repeat_mode",
            "cooldown_seconds",
            "status",
            "current_price",
        )
        if k in data
    }
    if not allowed:
        return jsonify({"error": "Nothing to update."}), 400

    try:
        rule = alert_rules.update_rule(user_id, rule_id, **allowed)
    except RuleError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("[alert-rules] update failed")
        return jsonify({"error": "Could not update that alert."}), 500

    if not rule:
        return jsonify({"error": "Alert not found."}), 404
    return jsonify(_envelope({"rule": rule}))


@alert_rules_bp.route("/api/alert-rules/<rule_id>/pause", methods=["POST"])
def pause_alert_rule(rule_id):
    return _set_status(rule_id, "paused")


@alert_rules_bp.route("/api/alert-rules/<rule_id>/resume", methods=["POST"])
def resume_alert_rule(rule_id):
    return _set_status(rule_id, "active")


def _set_status(rule_id: str, status: str):
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    try:
        rule = alert_rules.set_rule_status(user_id, rule_id, status)
    except RuleError as exc:
        return jsonify({"error": str(exc)}), 400
    if not rule:
        return jsonify({"error": "Alert not found."}), 404
    return jsonify(_envelope({"rule": rule}))


@alert_rules_bp.route("/api/alert-rules/<rule_id>", methods=["DELETE"])
def delete_alert_rule(rule_id):
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    if not alert_rules.delete_rule(user_id, rule_id):
        return jsonify({"error": "Alert not found."}), 404
    return jsonify(_envelope({"deleted": True, "id": rule_id}))


# ─── recommendations ─────────────────────────────────────────────────────────


@alert_rules_bp.route("/api/alert-recommendations", methods=["GET"])
def list_alert_recommendations():
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    if request.args.get("refresh") == "1":
        try:
            alert_rules.build_recommendations(user_id)
        except Exception:
            logger.exception("[alert-rules] recommendation build failed")
    recs = alert_rules.list_recommendations(user_id)
    return jsonify(_envelope({"recommendations": recs, "count": len(recs)}))


@alert_rules_bp.route("/api/alert-recommendations/refresh", methods=["POST"])
def refresh_alert_recommendations():
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    try:
        recs = alert_rules.build_recommendations(user_id)
    except Exception:
        logger.exception("[alert-rules] recommendation build failed")
        return jsonify({"error": "Could not refresh suggestions."}), 500
    return jsonify(_envelope({"recommendations": recs, "count": len(recs)}))


@alert_rules_bp.route("/api/alert-recommendations/<rec_id>/accept", methods=["POST"])
def accept_alert_recommendation(rec_id):
    """Explicit consent is the ONLY path that activates a suggested alert."""
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    data = _body()
    try:
        rule = alert_rules.accept_recommendation(
            user_id,
            rec_id,
            current_price=data.get("current_price"),
            overrides=(
                data.get("params") if isinstance(data.get("params"), dict) else None
            ),
        )
    except RuleError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("[alert-rules] accept failed")
        return jsonify({"error": "Could not enable that suggestion."}), 500
    return jsonify(_envelope({"rule": rule})), 201


@alert_rules_bp.route("/api/alert-recommendations/<rec_id>/dismiss", methods=["POST"])
def dismiss_alert_recommendation(rec_id):
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    if not alert_rules.dismiss_recommendation(user_id, rec_id):
        return jsonify({"error": "Suggestion not found."}), 404
    return jsonify(_envelope({"dismissed": True, "id": rec_id}))


# ─── history ─────────────────────────────────────────────────────────────────


@alert_rules_bp.route("/api/alert-history", methods=["GET"])
def list_alert_history():
    user_id = _current_user_id()
    if not user_id:
        return _unauthorized()
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    events = alert_rules.list_events(
        user_id, limit=limit, symbol=request.args.get("symbol")
    )
    return jsonify(_envelope({"events": events, "count": len(events)}))
