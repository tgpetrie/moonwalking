"""Developer testing wrapper for portfolio change intelligence.

This module is intentionally thin. It does not add new intelligence logic; it
reuses the reusable comparison engine and just exposes a manual testing surface
for developers.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from flask import Blueprint, jsonify, request

try:
    from intelligence_memory import get_intelligence_memory_store
except ImportError:  # package imports under pytest
    from backend.intelligence_memory import get_intelligence_memory_store

try:
    from portfolio_change_intelligence import (
        EVENT_TYPE,
        PortfolioChangeThresholds,
        build_portfolio_change_packet,
        compare_portfolio_state,
        detect_portfolio_change,
        portfolio_change_fingerprint,
    )
except ImportError:  # package imports under pytest
    from backend.portfolio_change_intelligence import (
        EVENT_TYPE,
        PortfolioChangeThresholds,
        build_portfolio_change_packet,
        compare_portfolio_state,
        detect_portfolio_change,
        portfolio_change_fingerprint,
    )

try:
    from watchlist import get_authenticated_user
except ImportError:  # package imports under pytest
    from backend.watchlist import get_authenticated_user


intelligence_test_bp = Blueprint("intelligence_test", __name__)

ENV_ALLOW_ANY_USER = "MW_INTELLIGENCE_TEST_ALLOW_ANY_USER"


def _json_ok(data: Any, status: int = 200):
    return jsonify({"success": True, "data": data}), status


def _json_err(code: str, message: str, status: int = 400):
    return (
        jsonify({"success": False, "error": {"code": code, "message": message}}),
        status,
    )


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _float(value: Any, *, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _credentials_module():
    try:
        import portfolio_credentials as module
    except ImportError:  # package imports under pytest
        from backend import portfolio_credentials as module
    return module


def _resolve_user_service(user_id: int):
    try:
        service, resolved = _credentials_module().resolve_portfolio_service(user_id)
    except Exception:
        return None, {
            "status": "auth_error",
            "detail": "Credential resolution failed.",
        }

    if service is None:
        return None, {
            "status": "auth_unavailable",
            "detail": getattr(resolved, "detail", None)
            or "Portfolio service unavailable.",
            "credential_status": getattr(resolved, "status", None),
        }
    return service, {
        "status": getattr(resolved, "status", "injected"),
        "detail": getattr(resolved, "detail", None),
        "credential_status": getattr(resolved, "status", "injected"),
    }


def _simplify_contributors(
    rows: list[dict[str, Any]], label: str
) -> list[dict[str, Any]]:
    simplified = []
    for row in rows[:3]:
        simplified.append(
            {
                "asset": row.get("asset_symbol"),
                "impact_pct": row.get("contribution_pct"),
                "impact_usd": row.get("value_delta_usd"),
                "reason": label,
            }
        )
    return simplified


def _event_summary(
    *,
    packet: dict[str, Any],
    detection: dict[str, Any],
    persisted: bool,
    event_id: str | None = None,
    evidence_packet_id: str | None = None,
) -> dict[str, Any]:
    return {
        "type": packet.get("event_type") or EVENT_TYPE,
        "importance": detection.get("importance_score"),
        "triggered": bool(detection.get("triggered")),
        "persisted": persisted,
        "event_id": event_id,
        "evidence_packet_id": evidence_packet_id,
        "reason_count": len(detection.get("reasons") or []),
    }


def run_portfolio_intelligence_test(
    user_id: int,
    hours: float | None = 24,
    *,
    dry_run: bool = False,
    store: Any = None,
    service: Any = None,
    current_snapshot: dict[str, Any] | None = None,
    thresholds: PortfolioChangeThresholds | None = None,
    scope: str = "portfolio",
) -> dict[str, Any]:
    """Run the comparison engine manually, with an optional no-write mode."""
    store = store or get_intelligence_memory_store()
    thresholds = thresholds or PortfolioChangeThresholds.from_env()

    resolved_service = service
    credential_info: dict[str, Any] | None = None
    if resolved_service is None and current_snapshot is None:
        resolved_service, credential_info = _resolve_user_service(user_id)
        if resolved_service is None:
            return {
                "status": (
                    credential_info.get("status") if credential_info else "auth_error"
                ),
                "triggered": False,
                "detail": credential_info.get("detail") if credential_info else None,
                "window_hours": hours,
                "dry_run": dry_run,
                "portfolio_change": {},
                "top_positive_contributors": [],
                "top_negative_contributors": [],
                "events_created": [],
                "evidence_packet_ids": [],
                "proposed_event": None,
            }

    compared = compare_portfolio_state(
        user_id,
        hours,
        store=store,
        service=resolved_service,
        current_snapshot=current_snapshot,
        scope=scope,
        persist_current_snapshot=not dry_run,
    )
    if compared.get("status") != "compared":
        change = compared.get("change") or {}
        return {
            "status": compared.get("status"),
            "triggered": False,
            "window_hours": hours,
            "dry_run": dry_run,
            "current_snapshot_time": (compared.get("current_snapshot") or {}).get(
                "captured_at"
            ),
            "previous_snapshot_time": (compared.get("previous_snapshot") or {}).get(
                "captured_at"
            ),
            "portfolio_change": {
                "status": change.get("status"),
                "value_change_usd": change.get("total_change_usd"),
                "portfolio_change_pct": change.get("total_change_pct"),
                "previous_total_usd": change.get("previous_total_usd"),
                "current_total_usd": change.get("current_total_usd"),
            },
            "top_positive_contributors": _simplify_contributors(
                change.get("positive_contributors") or [],
                "largest portfolio contributor",
            ),
            "top_negative_contributors": _simplify_contributors(
                change.get("negative_contributors") or [], "largest portfolio detractor"
            ),
            "events_created": [],
            "evidence_packet_ids": [],
            "proposed_event": None,
        }

    current = compared["current_snapshot"]
    previous = compared["previous_snapshot"]
    change = compared["change"]
    detection = detect_portfolio_change(change, thresholds)

    base_result = {
        "status": "evaluated",
        "triggered": detection["triggered"],
        "window_hours": hours,
        "dry_run": dry_run,
        "current_snapshot_time": current.get("captured_at"),
        "previous_snapshot_time": previous.get("captured_at") if previous else None,
        "comparison_window_label": compared.get("comparison_window_label"),
        "portfolio_change": {
            "status": change.get("status"),
            "value_change_usd": change.get("total_change_usd"),
            "portfolio_change_pct": change.get("total_change_pct"),
            "previous_total_usd": change.get("previous_total_usd"),
            "current_total_usd": change.get("current_total_usd"),
        },
        "top_positive_contributors": _simplify_contributors(
            change.get("positive_contributors") or [], "largest portfolio contributor"
        ),
        "top_negative_contributors": _simplify_contributors(
            change.get("negative_contributors") or [], "largest portfolio detractor"
        ),
        "events_created": [],
        "evidence_packet_ids": [],
        "proposed_event": None,
    }

    if not detection["triggered"]:
        return base_result

    packet = build_portfolio_change_packet(
        change,
        detection,
        previous=previous,
        current=current,
        comparison_window_hours=hours,
    )
    proposed_event = _event_summary(
        packet=packet,
        detection=detection,
        persisted=not dry_run,
    )
    base_result["proposed_event"] = proposed_event

    if dry_run:
        return base_result

    affected_symbol = (
        packet["affected_assets"][0] if packet["affected_assets"] else None
    )
    stored_packet = store.record_evidence_packet(
        packet,
        scope="portfolio_change_intelligence",
        user_id=user_id,
        series_key=f"portfolio_change_intelligence:{user_id}",
        asset_symbol=affected_symbol,
        portfolio_snapshot_id=current.get("snapshot_id"),
        comparison=change,
        analysis=detection,
        origin="portfolio_change_intelligence_test",
    )
    event = store.record_intelligence_event(
        event_type=EVENT_TYPE,
        payload={
            "reasons": detection["reasons"],
            "total_change_pct": change.get("total_change_pct"),
            "total_change_usd": change.get("total_change_usd"),
            "affected_assets": packet["affected_assets"],
            "fingerprint": portfolio_change_fingerprint(change, detection),
            "comparison_window_hours": hours,
            "comparison_window_label": compared.get("comparison_window_label"),
        },
        user_id=user_id,
        scope="portfolio_change_intelligence",
        asset_symbol=affected_symbol,
        portfolio_snapshot_id=current.get("snapshot_id"),
        evidence_packet_id=stored_packet["packet_id"],
        state_before_snapshot_id=previous.get("snapshot_id") if previous else None,
        state_after_snapshot_id=current.get("snapshot_id"),
        importance_score=detection["importance_score"],
        status="detected",
    )
    base_result["events_created"] = [
        _event_summary(
            packet=packet,
            detection=detection,
            persisted=True,
            event_id=event["event_id"],
            evidence_packet_id=stored_packet["packet_id"],
        )
    ]
    base_result["evidence_packet_ids"] = [stored_packet["packet_id"]]
    base_result["proposed_event"] = base_result["events_created"][0]
    return base_result


@intelligence_test_bp.route("/api/intelligence/test-run", methods=["POST"])
def intelligence_test_run_route():
    user = get_authenticated_user()
    if not user:
        return _json_err("unauthorized", "Authentication required.", 401)

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id", user.get("id"))
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _json_err("invalid_user_id", "user_id must be an integer.", 400)

    if not _bool(os.getenv(ENV_ALLOW_ANY_USER)):
        try:
            current_user_id = int(user.get("id"))
        except (TypeError, ValueError):
            current_user_id = None
        if current_user_id is None or user_id != current_user_id:
            return _json_err(
                "forbidden",
                "Developer test run can only target the authenticated user.",
                403,
            )

    hours = _float(body.get("hours"), default=24.0)
    if hours is None:
        return _json_err("invalid_hours", "hours must be numeric.", 400)

    dry_run = _bool(body.get("dry_run"))

    try:
        result = run_portfolio_intelligence_test(
            user_id,
            hours,
            dry_run=dry_run,
        )
    except Exception:
        return _json_err(
            "intelligence_unavailable",
            "Portfolio intelligence is temporarily unavailable.",
            503,
        )

    return _json_ok(result)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a live or dry-run portfolio intelligence check"
    )
    parser.add_argument("--user", required=True, type=int, help="User ID to test")
    parser.add_argument(
        "--hours", default=24.0, type=float, help="Comparison window in hours"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and compare live portfolio state without persisting anything",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    result = run_portfolio_intelligence_test(
        args.user,
        args.hours,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "intelligence_test_bp",
    "main",
    "run_portfolio_intelligence_test",
]
