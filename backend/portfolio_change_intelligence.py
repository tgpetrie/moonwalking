"""Portfolio Change Intelligence.

This is the reusable portfolio comparison engine.

Deterministic layer:
- capture the current portfolio snapshot
- locate the closest previous snapshot within a requested window
- compute portfolio movement, contributor ranking, allocation changes,
  new/removed positions, and evidence packet facts

LLM layer:
- reserved for later explanation only

The same ``ask_bhabit.evidence.v1`` packet history and ``intelligence_events``
table remain the durable history layer.

Legacy overnight names are retained only as compatibility aliases below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import os
from typing import Any
from uuid import uuid4

try:
    from intelligence_memory import (
        IntelligenceMemoryStore,
        get_intelligence_memory_store,
    )
except ImportError:  # package imports under pytest
    from backend.intelligence_memory import (
        IntelligenceMemoryStore,
        get_intelligence_memory_store,
    )


logger = logging.getLogger(__name__)

PORTFOLIO_CHANGE_INTELLIGENCE = "PORTFOLIO_CHANGE_INTELLIGENCE"
EVENT_TYPE = PORTFOLIO_CHANGE_INTELLIGENCE
SCHEMA_VERSION = "ask_bhabit.evidence.v1"

ENV_PORTFOLIO_PCT = "MW_PORTFOLIO_CHANGE_INTELLIGENCE_PORTFOLIO_PCT"
ENV_ASSET_PCT = "MW_PORTFOLIO_CHANGE_INTELLIGENCE_ASSET_PCT"
ENV_PORTFOLIO_PCT_LEGACY = "MW_OVERNIGHT_DELTA_PORTFOLIO_PCT"
ENV_ASSET_PCT_LEGACY = "MW_OVERNIGHT_DELTA_ASSET_PCT"

DEFAULT_PORTFOLIO_PCT = 5.0
DEFAULT_ASSET_PCT = 3.0
DEFAULT_OVERNIGHT_HOURS = 12.0


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _round(value: float | None, places: int = 4) -> float | None:
    return round(value, places) if value is not None else None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _snapshot_sort_key(snapshot: dict[str, Any]) -> tuple[datetime, int]:
    ts = _parse_iso(snapshot.get("captured_at") or snapshot.get("created_at"))
    if ts is None:
        ts = datetime.min.replace(tzinfo=timezone.utc)
    sid = int(snapshot.get("snapshot_id") or 0)
    return ts, sid


def _asset_key(row: dict[str, Any]) -> str:
    raw = str(
        row.get("asset_id")
        or row.get("asset_symbol")
        or row.get("symbol")
        or row.get("currency")
        or ""
    ).strip()
    return raw.upper()


def _normalize_holding(row: dict[str, Any]) -> dict[str, Any]:
    cost_basis = (
        row.get("cost_basis") if isinstance(row.get("cost_basis"), dict) else {}
    )
    cost_basis_usd = _number(cost_basis.get("known_cost_usd"))
    if cost_basis_usd is None:
        cost_basis_usd = _number(cost_basis.get("total_cost_basis"))
    value_usd = _number(
        row.get("market_value_usd")
        if row.get("market_value_usd") is not None
        else row.get("value_usd")
    )
    return {
        "asset_id": _asset_key(row),
        "asset_symbol": str(
            row.get("symbol") or row.get("asset_symbol") or row.get("currency") or ""
        )
        .strip()
        .upper(),
        "quantity": _number(row.get("quantity")),
        "value_usd": value_usd,
        "cost_basis_usd": cost_basis_usd,
        "price_usd": _number(row.get("price_usd")),
        "allocation_pct": _number(row.get("allocation_pct")),
        "is_cash": bool(row.get("is_cash")),
        "raw": dict(row),
    }


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    holdings = {}
    for row in snapshot.get("holdings") or []:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_holding(row)
        if not normalized["asset_id"]:
            continue
        holdings[normalized["asset_id"]] = normalized

    summary = (
        snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    )
    total = _number(summary.get("total_value_usd"))
    if total is None:
        total = sum(
            (h["value_usd"] or 0.0)
            for h in holdings.values()
            if h["value_usd"] is not None
        )

    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "captured_at": snapshot.get("captured_at")
        or snapshot.get("created_at")
        or snapshot.get("updated_at"),
        "total_value_usd": total,
        "summary": dict(summary),
        "holdings": holdings,
    }


def _sort_by_abs_delta(
    items: list[dict[str, Any]], *, reverse: bool = True
) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda row: (
            abs(float(row.get("value_delta_usd") or 0.0)),
            abs(float(row.get("contribution_pct") or 0.0)),
            str(row.get("asset_symbol") or ""),
        ),
        reverse=reverse,
    )


def _comparison_window_label(comparison_window_hours: float | None) -> str:
    if comparison_window_hours is None:
        return "since last check"
    hours = float(comparison_window_hours)
    if hours == 1:
        return "1 hour"
    if hours.is_integer():
        return f"{int(hours)} hours"
    return f"{hours:g} hours"


def _select_previous_snapshot(
    snapshots: list[dict[str, Any]],
    current_snapshot: dict[str, Any],
    comparison_window_hours: float | None,
) -> dict[str, Any] | None:
    current_ts = _parse_iso(
        current_snapshot.get("captured_at") or current_snapshot.get("created_at")
    )
    if current_ts is None:
        return None

    candidates: list[dict[str, Any]] = []
    for snapshot in snapshots:
        if snapshot.get("snapshot_id") == current_snapshot.get("snapshot_id"):
            continue
        candidate_ts = _parse_iso(
            snapshot.get("captured_at") or snapshot.get("created_at")
        )
        if candidate_ts is None or candidate_ts > current_ts:
            continue
        age_seconds = (current_ts - candidate_ts).total_seconds()
        if (
            comparison_window_hours is not None
            and age_seconds > float(comparison_window_hours) * 3600.0
        ):
            continue
        candidate = dict(snapshot)
        candidate["_age_seconds"] = age_seconds
        candidates.append(candidate)

    if not candidates:
        return None

    if comparison_window_hours is None:
        # Since last check -> the most recent prior snapshot.
        return max(
            candidates,
            key=lambda s: (_snapshot_sort_key(s)[0], int(s.get("snapshot_id") or 0)),
        )

    # For a numeric window, choose the oldest snapshot still inside the window so
    # the comparison approximates the requested boundary rather than the most
    # recent tick.
    return max(
        candidates,
        key=lambda s: (
            float(s.get("_age_seconds") or 0.0),
            _snapshot_sort_key(s)[0],
            int(s.get("snapshot_id") or 0),
        ),
    )


def compute_portfolio_change(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    curr = _normalize_snapshot(current)
    if not previous:
        return {
            "status": "no_previous_snapshot",
            "previous_snapshot_id": None,
            "current_snapshot_id": curr["snapshot_id"],
            "previous_total_usd": None,
            "current_total_usd": _round(curr["total_value_usd"], 2),
            "total_change_usd": None,
            "total_change_pct": None,
            "asset_contributions": [],
            "positive_contributors": [],
            "negative_contributors": [],
            "biggest_movers": [],
            "allocation_changes": [],
            "new_positions": [],
            "removed_positions": [],
        }

    prev = _normalize_snapshot(previous)
    prev_total = prev["total_value_usd"] or 0.0
    curr_total = curr["total_value_usd"] or 0.0
    total_change_usd = curr_total - prev_total
    total_change_pct = (
        (total_change_usd / prev_total * 100.0) if prev_total > 0 else None
    )

    symbols = sorted(set(prev["holdings"].keys()) | set(curr["holdings"].keys()))
    contributions: list[dict[str, Any]] = []
    allocation_changes: list[dict[str, Any]] = []
    new_positions: list[dict[str, Any]] = []
    removed_positions: list[dict[str, Any]] = []

    for symbol in symbols:
        before = prev["holdings"].get(symbol, {})
        after = curr["holdings"].get(symbol, {})
        is_cash = bool(before.get("is_cash") or after.get("is_cash"))
        value_from = before.get("value_usd")
        value_to = after.get("value_usd")
        value_delta = (value_to or 0.0) - (value_from or 0.0)
        contribution_pct = (
            (value_delta / prev_total * 100.0) if prev_total > 0 else None
        )
        alloc_from = before.get("allocation_pct")
        alloc_to = after.get("allocation_pct")
        alloc_delta = (
            (alloc_to - alloc_from)
            if alloc_from is not None and alloc_to is not None
            else None
        )
        row = {
            "asset_id": symbol,
            "asset_symbol": after.get("asset_symbol")
            or before.get("asset_symbol")
            or symbol,
            "is_cash": is_cash,
            "value_from_usd": _round(value_from, 2),
            "value_to_usd": _round(value_to, 2),
            "value_delta_usd": _round(value_delta, 2),
            "contribution_pct": _round(contribution_pct),
            "allocation_from_pct": _round(alloc_from),
            "allocation_to_pct": _round(alloc_to),
            "allocation_delta_pct": _round(alloc_delta),
            "state": (
                "added"
                if value_from is None
                else "removed" if value_to is None else "held"
            ),
        }
        contributions.append(row)

        if not is_cash and row["state"] == "added" and (value_to or 0) > 0:
            new_positions.append(row)
        elif not is_cash and row["state"] == "removed" and (value_from or 0) > 0:
            removed_positions.append(row)

        if alloc_delta is not None and abs(alloc_delta) > 0:
            allocation_changes.append(
                {
                    "asset_symbol": row["asset_symbol"],
                    "from_pct": _round(alloc_from),
                    "to_pct": _round(alloc_to),
                    "delta_pct": _round(alloc_delta),
                }
            )

    positive_contributors = sorted(
        (
            row
            for row in contributions
            if not row["is_cash"] and (row["value_delta_usd"] or 0) > 0
        ),
        key=lambda row: (
            float(row.get("value_delta_usd") or 0.0),
            float(row.get("contribution_pct") or 0.0),
        ),
        reverse=True,
    )
    negative_contributors = sorted(
        (
            row
            for row in contributions
            if not row["is_cash"] and (row["value_delta_usd"] or 0) < 0
        ),
        key=lambda row: (
            float(row.get("value_delta_usd") or 0.0),
            float(row.get("contribution_pct") or 0.0),
        ),
    )
    biggest_movers = _sort_by_abs_delta(
        [
            row
            for row in contributions
            if not row["is_cash"] and row["value_delta_usd"] is not None
        ]
    )
    allocation_changes.sort(
        key=lambda row: abs(row.get("delta_pct") or 0.0), reverse=True
    )

    return {
        "status": "compared",
        "previous_snapshot_id": prev["snapshot_id"],
        "current_snapshot_id": curr["snapshot_id"],
        "previous_total_usd": _round(prev_total, 2),
        "current_total_usd": _round(curr_total, 2),
        "total_change_usd": _round(total_change_usd, 2),
        "total_change_pct": _round(total_change_pct),
        "asset_contributions": contributions,
        "positive_contributors": positive_contributors,
        "negative_contributors": negative_contributors,
        "biggest_movers": biggest_movers,
        "allocation_changes": allocation_changes,
        "new_positions": new_positions,
        "removed_positions": removed_positions,
    }


def detect_portfolio_change(
    change: dict[str, Any],
    thresholds: "PortfolioChangeThresholds" | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or PortfolioChangeThresholds.from_env()
    if change.get("status") != "compared":
        return {
            "triggered": False,
            "reasons": [],
            "importance_score": 0.0,
            "thresholds": {
                "portfolio_pct": thresholds.portfolio_pct,
                "asset_contribution_pct": thresholds.asset_contribution_pct,
            },
        }

    reasons: list[dict[str, Any]] = []
    total_pct = change.get("total_change_pct")
    if total_pct is not None and abs(total_pct) >= thresholds.portfolio_pct:
        reasons.append(
            {
                "type": "portfolio_move",
                "magnitude_pct": abs(round(total_pct, 4)),
                "threshold_pct": thresholds.portfolio_pct,
                "direction": "up" if total_pct > 0 else "down",
            }
        )

    for asset in change.get("asset_contributions") or []:
        if asset.get("is_cash"):
            continue
        contribution = asset.get("contribution_pct")
        if (
            contribution is not None
            and abs(contribution) >= thresholds.asset_contribution_pct
        ):
            reasons.append(
                {
                    "type": "asset_contribution",
                    "asset_symbol": asset.get("asset_symbol"),
                    "magnitude_pct": abs(round(contribution, 4)),
                    "threshold_pct": thresholds.asset_contribution_pct,
                    "direction": "up" if contribution > 0 else "down",
                }
            )

    importance = max((reason["magnitude_pct"] for reason in reasons), default=0.0)
    return {
        "triggered": bool(reasons),
        "reasons": reasons,
        "importance_score": importance,
        "thresholds": {
            "portfolio_pct": thresholds.portfolio_pct,
            "asset_contribution_pct": thresholds.asset_contribution_pct,
        },
    }


def build_portfolio_change_packet(
    change: dict[str, Any],
    detection: dict[str, Any],
    *,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    comparison_window_hours: float | None,
) -> dict[str, Any]:
    prev_norm = _normalize_snapshot(previous) if previous else None
    curr_norm = _normalize_snapshot(current)

    affected_assets = sorted(
        {
            row["asset_symbol"]
            for row in (change.get("asset_contributions") or [])
            if row.get("asset_symbol") and not row.get("is_cash")
        }
        | {
            row["asset_symbol"]
            for row in (change.get("new_positions") or [])
            if row.get("asset_symbol")
        }
        | {
            row["asset_symbol"]
            for row in (change.get("removed_positions") or [])
            if row.get("asset_symbol")
        }
    )

    window_label = _comparison_window_label(comparison_window_hours)
    return {
        "packet_id": f"portfolio-change-{uuid4().hex}",
        "schema_version": SCHEMA_VERSION,
        "event_type": PORTFOLIO_CHANGE_INTELLIGENCE,
        "comparison_window_hours": comparison_window_hours,
        "comparison_window_label": window_label,
        "retrieved_at": curr_norm.get("captured_at"),
        "what_changed": {
            "triggered": detection.get("triggered", False),
            "reasons": detection.get("reasons", []),
            "total_change_usd": change.get("total_change_usd"),
            "total_change_pct": change.get("total_change_pct"),
            "comparison_window_hours": comparison_window_hours,
            "comparison_window_label": window_label,
        },
        "affected_assets": affected_assets,
        "previous_state": {
            "captured_at": prev_norm.get("captured_at") if prev_norm else None,
            "snapshot_id": prev_norm.get("snapshot_id") if prev_norm else None,
            "total_value_usd": change.get("previous_total_usd"),
        },
        "current_state": {
            "captured_at": curr_norm.get("captured_at"),
            "snapshot_id": curr_norm.get("snapshot_id"),
            "total_value_usd": change.get("current_total_usd"),
        },
        "supporting_metrics": {
            "biggest_movers": change.get("biggest_movers", []),
            "biggest_positive_contributors": change.get("positive_contributors", []),
            "biggest_negative_contributors": change.get("negative_contributors", []),
            "allocation_changes": change.get("allocation_changes", []),
            "new_positions": change.get("new_positions", []),
            "removed_positions": change.get("removed_positions", []),
            "asset_contributions": change.get("asset_contributions", []),
        },
        "attention": {
            "top_positive_contributors": change.get("positive_contributors", [])[:3],
            "top_negative_contributors": change.get("negative_contributors", [])[:3],
            "largest_allocation_shifts": change.get("allocation_changes", [])[:3],
            "new_positions": change.get("new_positions", []),
            "removed_positions": change.get("removed_positions", []),
        },
        "confidence": {
            "level": "deterministic",
            "source": "portfolio_change_intelligence",
            "notes": "Facts derived from stored portfolio snapshots; no prediction or advice.",
        },
    }


def capture_portfolio_snapshot(
    user_id: int,
    *,
    snapshot: dict[str, Any] | None = None,
    service: Any = None,
    store: IntelligenceMemoryStore | None = None,
    source: str = "portfolio_change_intelligence_capture",
    scope: str = "portfolio",
) -> dict[str, Any] | None:
    store = store or get_intelligence_memory_store()
    if snapshot is None:
        if service is None:
            try:
                from portfolio_mode import get_portfolio_service
            except ImportError:
                from backend.portfolio_mode import get_portfolio_service
            try:
                service = get_portfolio_service()
            except Exception:
                logger.debug(
                    "[PortfolioChange] portfolio service unavailable", exc_info=True
                )
                return None
        try:
            snapshot = service.snapshot()
        except Exception:
            logger.debug(
                "[PortfolioChange] portfolio snapshot fetch failed", exc_info=True
            )
            return None

    if not isinstance(snapshot, dict) or not (snapshot.get("holdings")):
        logger.debug(
            "[PortfolioChange] empty/invalid portfolio snapshot; skipping capture"
        )
        return None

    try:
        return store.record_portfolio_snapshot(
            user_id,
            snapshot,
            scope=scope,
            source=source,
        )
    except Exception:
        logger.debug("[PortfolioChange] snapshot persistence failed", exc_info=True)
        return None


def _resolve_current_snapshot(
    *,
    snapshot: dict[str, Any] | None = None,
    service: Any = None,
) -> dict[str, Any] | None:
    if snapshot is not None:
        return snapshot if isinstance(snapshot, dict) else None
    if service is None:
        try:
            from portfolio_mode import get_portfolio_service
        except ImportError:
            from backend.portfolio_mode import get_portfolio_service
        try:
            service = get_portfolio_service()
        except Exception:
            logger.debug(
                "[PortfolioChange] portfolio service unavailable", exc_info=True
            )
            return None
    try:
        live_snapshot = service.snapshot()
    except Exception:
        logger.debug("[PortfolioChange] portfolio snapshot fetch failed", exc_info=True)
        return None
    return live_snapshot if isinstance(live_snapshot, dict) else None


def compare_portfolio_state(
    user_id: int,
    comparison_window_hours: float | None,
    *,
    store: IntelligenceMemoryStore | None = None,
    service: Any = None,
    current_snapshot: dict[str, Any] | None = None,
    scope: str = "portfolio",
    persist_current_snapshot: bool = True,
) -> dict[str, Any]:
    """Capture the current state, then compare it to a prior snapshot."""
    store = store or get_intelligence_memory_store()
    if persist_current_snapshot:
        current_record = capture_portfolio_snapshot(
            user_id,
            snapshot=current_snapshot,
            service=service,
            store=store,
            scope=scope,
            source="portfolio_change_intelligence_capture",
        )
        if current_record is None:
            return {"status": "portfolio_unavailable", "triggered": False}
        current = current_record
    else:
        live_snapshot = _resolve_current_snapshot(
            snapshot=current_snapshot, service=service
        )
        if live_snapshot is None:
            return {"status": "portfolio_unavailable", "triggered": False}
        current = _normalize_snapshot(live_snapshot)

    try:
        recent = store.recent_portfolio_snapshots(user_id, scope=scope, limit=200)
    except Exception:
        logger.debug("[PortfolioChange] snapshot history lookup failed", exc_info=True)
        return {"status": "history_unavailable", "triggered": False}

    if persist_current_snapshot:
        current = next(
            (
                row
                for row in recent
                if row.get("snapshot_id") == current_record.get("snapshot_id")
            ),
            current_record,
        )
    previous = _select_previous_snapshot(recent, current, comparison_window_hours)

    if previous is None:
        status = (
            "no_previous_snapshot"
            if comparison_window_hours is None
            else "no_previous_snapshot_in_window"
        )
        return {
            "status": status,
            "triggered": False,
            "comparison_window_hours": comparison_window_hours,
            "comparison_window_label": _comparison_window_label(
                comparison_window_hours
            ),
            "current_snapshot": current,
            "previous_snapshot": None,
            "change": compute_portfolio_change(None, current),
        }

    change = compute_portfolio_change(previous, current)
    return {
        "status": "compared",
        "triggered": True,
        "comparison_window_hours": comparison_window_hours,
        "comparison_window_label": _comparison_window_label(comparison_window_hours),
        "current_snapshot": current,
        "previous_snapshot": previous,
        "change": change,
    }


def run_portfolio_intelligence_check(
    user_id: int,
    hours: float | None = 24,
    *,
    store: IntelligenceMemoryStore | None = None,
    service: Any = None,
    current_snapshot: dict[str, Any] | None = None,
    thresholds: "PortfolioChangeThresholds" | None = None,
    scope: str = "portfolio",
    emit_guard: Any = None,
) -> dict[str, Any]:
    """Developer / scheduler entry point.

    ``hours=None`` means compare since the last check. Otherwise the engine
    finds the closest previous snapshot inside the requested window.
    """
    store = store or get_intelligence_memory_store()
    thresholds = thresholds or PortfolioChangeThresholds.from_env()

    compared = compare_portfolio_state(
        user_id,
        hours,
        store=store,
        service=service,
        current_snapshot=current_snapshot,
        scope=scope,
    )
    if compared.get("status") != "compared":
        return compared

    current = compared["current_snapshot"]
    previous = compared["previous_snapshot"]
    change = compared["change"]
    detection = detect_portfolio_change(change, thresholds)

    result: dict[str, Any] = {
        "status": "evaluated",
        "triggered": detection["triggered"],
        "comparison_window_hours": hours,
        "comparison_window_label": compared.get("comparison_window_label"),
        "snapshot_id": current.get("snapshot_id"),
        "previous_snapshot_id": previous.get("snapshot_id") if previous else None,
        "change": change,
        "detection": detection,
    }
    fingerprint = portfolio_change_fingerprint(change, detection)
    result["fingerprint"] = fingerprint

    if not detection["triggered"]:
        return result

    if emit_guard is not None:
        try:
            allowed = bool(emit_guard(fingerprint, change, detection))
        except Exception:
            logger.debug("[PortfolioChange] emit guard failed; emitting", exc_info=True)
            allowed = True
        if not allowed:
            result["status"] = "suppressed"
            result["triggered"] = False
            result["suppressed_reason"] = "duplicate_condition"
            return result

    packet = build_portfolio_change_packet(
        change,
        detection,
        previous=previous,
        current=current,
        comparison_window_hours=hours,
    )
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
        origin="portfolio_change_intelligence",
    )

    event = store.record_intelligence_event(
        event_type=EVENT_TYPE,
        payload={
            "reasons": detection["reasons"],
            "total_change_pct": change.get("total_change_pct"),
            "total_change_usd": change.get("total_change_usd"),
            "affected_assets": packet["affected_assets"],
            "fingerprint": fingerprint,
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

    result["evidence_packet_id"] = stored_packet["packet_id"]
    result["event_id"] = event["event_id"]
    return result


def portfolio_change_fingerprint(
    change: dict[str, Any], detection: dict[str, Any]
) -> str:
    parts = [str(change.get("status"))]
    total_pct = change.get("total_change_pct")
    parts.append(f"total={round(total_pct, 2) if total_pct is not None else 'na'}")
    for reason in sorted(
        detection.get("reasons") or [],
        key=lambda row: (str(row.get("type")), str(row.get("asset_symbol") or "")),
    ):
        parts.append(
            f"{reason.get('type')}:{reason.get('asset_symbol') or '-'}:"
            f"{round(reason.get('magnitude_pct') or 0.0, 2)}:{reason.get('direction')}"
        )
    return "|".join(parts)


@dataclass(frozen=True)
class PortfolioChangeThresholds:
    portfolio_pct: float = DEFAULT_PORTFOLIO_PCT
    asset_contribution_pct: float = DEFAULT_ASSET_PCT

    @classmethod
    def from_env(cls) -> "PortfolioChangeThresholds":
        return cls(
            portfolio_pct=_env_float(
                ENV_PORTFOLIO_PCT,
                _env_float(ENV_PORTFOLIO_PCT_LEGACY, cls.portfolio_pct),
            ),
            asset_contribution_pct=_env_float(
                ENV_ASSET_PCT,
                _env_float(ENV_ASSET_PCT_LEGACY, cls.asset_contribution_pct),
            ),
        )


# Compatibility aliases for callers that still import the old overnight names.
DeltaThresholds = PortfolioChangeThresholds
compute_portfolio_delta = compute_portfolio_change
detect_portfolio_change_intelligence = detect_portfolio_change
detect_overnight_delta = detect_portfolio_change
build_overnight_delta_packet = build_portfolio_change_packet


def run_overnight_portfolio_delta(
    user_id: int,
    *,
    store: IntelligenceMemoryStore | None = None,
    service: Any = None,
    current_snapshot: dict[str, Any] | None = None,
    thresholds: PortfolioChangeThresholds | None = None,
    scope: str = "portfolio",
    emit_guard: Any = None,
) -> dict[str, Any]:
    return run_portfolio_intelligence_check(
        user_id,
        DEFAULT_OVERNIGHT_HOURS,
        store=store,
        service=service,
        current_snapshot=current_snapshot,
        thresholds=thresholds,
        scope=scope,
        emit_guard=emit_guard,
    )


def compare_portfolio_delta(
    user_id: int,
    comparison_window_hours: float | None,
    *,
    store: IntelligenceMemoryStore | None = None,
    service: Any = None,
    current_snapshot: dict[str, Any] | None = None,
    scope: str = "portfolio",
) -> dict[str, Any]:
    return compare_portfolio_state(
        user_id,
        comparison_window_hours,
        store=store,
        service=service,
        current_snapshot=current_snapshot,
        scope=scope,
    )


__all__ = [
    "PORTFOLIO_CHANGE_INTELLIGENCE",
    "EVENT_TYPE",
    "SCHEMA_VERSION",
    "PortfolioChangeThresholds",
    "DeltaThresholds",
    "capture_portfolio_snapshot",
    "compare_portfolio_state",
    "compare_portfolio_delta",
    "compute_portfolio_change",
    "compute_portfolio_delta",
    "detect_portfolio_change",
    "detect_portfolio_change_intelligence",
    "detect_overnight_delta",
    "build_portfolio_change_packet",
    "build_overnight_delta_packet",
    "portfolio_change_fingerprint",
    "run_portfolio_intelligence_check",
    "run_overnight_portfolio_delta",
]
