"""Ask Bhabit backend validation loop.

This module keeps the beta deliberately small: one manual position, optional
thesis, provider-independent evidence packets, persisted snapshots, and a
deterministic "what changed" comparison. It does not trade, search the web, or
infer social sentiment from price action.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Blueprint, jsonify, request

try:
    from derivatives_positioning import get_symbol_positioning
except ImportError:  # package imports under pytest
    from backend.derivatives_positioning import get_symbol_positioning


ask_bhabit_bp = Blueprint("ask_bhabit", __name__)

VALID_STATUSES = {
    "available",
    "unavailable",
    "unsupported",
    "not_configured",
    "stale",
    "provider_error",
    "conflicting",
}
CONFIDENCE_LEVELS = ("high", "medium", "low", "insufficient_evidence")


ASSET_REGISTRY: dict[str, dict[str, Any]] = {
    "BTC": {
        "asset_id": "bitcoin:btc",
        "symbol": "BTC",
        "name": "Bitcoin",
        "chain": "bitcoin",
        "provider_ids": {
            "coingecko": "bitcoin",
            "coinbase_product": "BTC-USD",
            "hyperliquid": "BTC",
        },
        "identifiers": {"native_asset": "BTC"},
    },
    "SOL": {
        "asset_id": "solana:So11111111111111111111111111111111111111112",
        "symbol": "SOL",
        "name": "Solana",
        "chain": "solana",
        "contract_address": "So11111111111111111111111111111111111111112",
        "provider_ids": {
            "coingecko": "solana",
            "coinbase_product": "SOL-USD",
            "hyperliquid": "SOL",
        },
        "identifiers": {"native_asset": "SOL"},
    },
    "SHDW": {
        "asset_id": "solana:SHDWyBxihqiC1b7C5hGaqRpzUT6XQv8x9xqvnYgKPump",  # pragma: allowlist secret
        "symbol": "SHDW",
        "name": "Shadow Token",
        "chain": "solana",
        "contract_address": "SHDWyBxihqiC1b7C5hGaqRpzUT6XQv8x9xqvnYgKPump",  # pragma: allowlist secret
        "provider_ids": {
            "coingecko": "genesysgo-shadow",
            "jupiter_mint": "SHDWyBxihqiC1b7C5hGaqRpzUT6XQv8x9xqvnYgKPump",  # pragma: allowlist secret
        },
        "identifiers": {"note": "SHDW is Shadow Token on Solana, not Shadow Exchange."},
    },
    "HYPE": {
        "asset_id": "hyperliquid:HYPE",
        "symbol": "HYPE",
        "name": "Hyperliquid",
        "chain": "hyperliquid",
        "provider_ids": {"hyperliquid": "HYPE", "coingecko": "hyperliquid"},
        "identifiers": {"exchange_product_id": "HYPE-PERP"},
    },
    "UNSUPPORTED": {
        "asset_id": "unsupported:UNSUPPORTED",
        "symbol": "UNSUPPORTED",
        "name": "Intentionally Unsupported Asset",
        "chain": None,
        "provider_ids": {},
        "unsupported": True,
        "identifiers": {"reason": "Fixture asset for unsupported-path handling."},
    },
}


@dataclass
class AskBhabitProviders:
    market: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None
    sentiment: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None
    derivatives: (
        Callable[[dict[str, Any], float | None], dict[str, Any] | None] | None
    ) = None
    llm: Callable[[str], str] | None = None


PROVIDERS = AskBhabitProviders()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _state(
    status: str,
    *,
    value: Any = None,
    source: str | None = None,
    timestamp: str | None = None,
    reason: str | None = None,
    freshness: str | None = None,
    error: str | None = None,
    conflicts: list[str] | None = None,
    confidence_reasons: list[str] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid evidence status: {status}")
    return {
        "status": status,
        "value": value,
        "source": source,
        "retrieved_at": timestamp,
        "freshness": freshness or ("fresh" if status == "available" else status),
        "missing_data_reason": reason,
        "provider_error": error,
        "conflicts": conflicts or [],
        "confidence_reasons": confidence_reasons or [],
    }


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _asset_key(asset_id: str) -> str:
    raw = str(asset_id or "").strip()
    if raw in ASSET_REGISTRY:
        return raw
    upper = raw.upper()
    for key, asset in ASSET_REGISTRY.items():
        if upper == asset.get("symbol") or raw == asset.get("asset_id"):
            return key
    return upper


def resolve_asset(asset_id: str) -> dict[str, Any]:
    key = _asset_key(asset_id)
    asset = deepcopy(ASSET_REGISTRY.get(key))
    if not asset:
        return {
            "asset_id": str(asset_id or "").strip(),
            "symbol": key,
            "name": None,
            "chain": None,
            "provider_ids": {},
            "identifiers": {},
            "unsupported": True,
        }
    return asset


class SnapshotStore:
    def __init__(self, path: str | Path | None = None):
        root = Path(
            path
            or os.getenv(
                "ASK_BHABIT_STORE_PATH", "backend/data/ask_bhabit_snapshots.json"
            )
        )
        if root.is_absolute():
            self.path = root
        elif path or os.getenv("ASK_BHABIT_STORE_PATH"):
            self.path = Path.cwd() / root
        else:
            self.path = (
                Path(__file__).resolve().parent / "data" / "ask_bhabit_snapshots.json"
            )

    def _empty(self) -> dict[str, Any]:
        return {"position": None, "thesis": None, "snapshots": []}

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty()
        return data if isinstance(data, dict) else self._empty()

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def upsert_position(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        position = normalize_position(payload, existing=data.get("position"))
        data["position"] = position
        self.save(data)
        return position

    def upsert_thesis(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        thesis = normalize_thesis(payload, existing=data.get("thesis"))
        data["thesis"] = thesis
        self.save(data)
        return thesis

    def append_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        snapshots = data.setdefault("snapshots", [])
        snapshots.append(snapshot)
        self.save(data)
        return snapshot


def get_store() -> SnapshotStore:
    return SnapshotStore()


def normalize_position(
    payload: dict[str, Any], *, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    merged = {**(existing or {}), **(payload or {})}
    asset_id = merged.get("asset_id") or merged.get("symbol")
    asset = resolve_asset(asset_id)
    quantity = _decimal(merged.get("quantity"))
    entry_price = _decimal(merged.get("entry_price"))
    total_cost_basis = _decimal(merged.get("total_cost_basis"))
    if (
        entry_price is None
        and total_cost_basis is not None
        and quantity
        and quantity > 0
    ):
        entry_price = total_cost_basis / quantity
    if total_cost_basis is None and entry_price is not None and quantity is not None:
        total_cost_basis = entry_price * quantity
    return {
        "position_id": merged.get("position_id") or "manual-position-1",
        "asset_id": asset["asset_id"],
        "asset_symbol": asset["symbol"],
        "quantity": _float(quantity),
        "entry_price": _float(entry_price),
        "total_cost_basis": _float(total_cost_basis),
        "acquisition_date": merged.get("acquisition_date"),
        "note": merged.get("note"),
        "source": "manual_entry",
        "updated_at": _utc_now(),
    }


def normalize_thesis(
    payload: dict[str, Any], *, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    merged = {**(existing or {}), **(payload or {})}
    return {
        "thesis_id": merged.get("thesis_id") or "manual-thesis-1",
        "why_entered": merged.get("why_entered"),
        "reconsider_if": merged.get("reconsider_if"),
        "time_horizon": merged.get("time_horizon"),
        "tags": [str(tag) for tag in (merged.get("tags") or [])],
        "updated_at": _utc_now(),
    }


def _default_market(asset: dict[str, Any]) -> dict[str, Any] | None:
    return None


def _default_sentiment(asset: dict[str, Any]) -> dict[str, Any] | None:
    return None


def _default_derivatives(
    asset: dict[str, Any], price_change_pct: float | None
) -> dict[str, Any] | None:
    return None


def _signal_from_provider(
    raw: dict[str, Any] | None, key: str, source: str, *, unsupported: bool = False
) -> dict[str, Any]:
    if unsupported:
        return _state(
            "unsupported", source=source, reason=f"{key} is unsupported for this asset"
        )
    if raw is None:
        return _state(
            "not_configured",
            source=source,
            reason=f"{source} provider is not configured",
        )
    status = raw.get("status") or (
        "available" if raw.get("value") is not None else "unavailable"
    )
    return _state(
        status,
        value=raw.get("value"),
        source=raw.get("source") or source,
        timestamp=raw.get("retrieved_at") or raw.get("updated_at") or _utc_now(),
        reason=raw.get("missing_data_reason") or raw.get("reason"),
        freshness=raw.get("freshness"),
        error=raw.get("provider_error") or raw.get("error"),
        conflicts=raw.get("conflicts") or [],
        confidence_reasons=raw.get("confidence_reasons") or [],
    )


def _derivative_signal(
    derivatives: dict[str, Any],
    key: str,
    *,
    provider_configured: bool,
    unsupported: bool,
) -> dict[str, Any]:
    raw = derivatives.get(key)
    if raw is None and provider_configured and not unsupported:
        return _state(
            "unavailable",
            source="derivatives_provider",
            reason=f"{key} is unavailable for this asset",
        )
    return _signal_from_provider(
        raw, key, "derivatives_provider", unsupported=unsupported
    )


def build_evidence_packet(
    position: dict[str, Any],
    thesis: dict[str, Any] | None = None,
    *,
    providers: AskBhabitProviders | None = None,
) -> dict[str, Any]:
    providers = providers or PROVIDERS
    asset = resolve_asset(position.get("asset_id") or position.get("asset_symbol"))
    unsupported = bool(asset.get("unsupported"))
    retrieved_at = _utc_now()

    market_raw = (providers.market or _default_market)(asset)
    sentiment_raw = (providers.sentiment or _default_sentiment)(asset)
    market = market_raw or {}
    price = _signal_from_provider(
        market.get("current_price"),
        "current_price",
        "market_provider",
        unsupported=unsupported,
    )
    short_move = _signal_from_provider(
        market.get("short_window_movement"),
        "short_window_movement",
        "market_provider",
        unsupported=unsupported,
    )
    longer_move = _signal_from_provider(
        market.get("longer_window_movement"),
        "longer_window_movement",
        "market_provider",
        unsupported=unsupported,
    )
    volume = _signal_from_provider(
        market.get("volume"), "volume", "market_provider", unsupported=unsupported
    )
    liquidity = _signal_from_provider(
        market.get("liquidity"), "liquidity", "market_provider", unsupported=unsupported
    )

    price_change_pct = (
        short_move.get("value")
        if isinstance(short_move.get("value"), (int, float))
        else None
    )
    derivatives_raw = None
    if unsupported:
        derivatives_raw = None
    elif providers.derivatives:
        derivatives_raw = providers.derivatives(asset, price_change_pct)
    derivatives = derivatives_raw or {}

    quantity = _decimal(position.get("quantity"))
    entry = _decimal(position.get("entry_price"))
    current = (
        _decimal(price.get("value")) if price.get("status") == "available" else None
    )
    current_value = (
        (quantity * current) if quantity is not None and current is not None else None
    )
    cost_basis = _decimal(position.get("total_cost_basis"))
    unrealized = (
        (current_value - cost_basis)
        if current_value is not None and cost_basis is not None
        else None
    )
    unrealized_pct = (
        (unrealized / cost_basis * Decimal("100"))
        if unrealized is not None and cost_basis and cost_basis > 0
        else None
    )

    sections = {
        "asset_identity": _state(
            "unsupported" if unsupported else "available",
            value=asset,
            source="ask_bhabit_asset_registry",
            timestamp=retrieved_at,
            reason=asset.get("identifiers", {}).get("reason"),
        ),
        "price": price,
        "movement": {
            "short_window": short_move,
            "longer_window": longer_move,
        },
        "volume_liquidity": {
            "volume": volume,
            "liquidity": liquidity,
        },
        "derivatives": {
            "funding": _derivative_signal(
                derivatives,
                "funding",
                provider_configured=providers.derivatives is not None,
                unsupported=unsupported,
            ),
            "open_interest": _derivative_signal(
                derivatives,
                "open_interest",
                provider_configured=providers.derivatives is not None,
                unsupported=unsupported,
            ),
            "liquidations": _derivative_signal(
                derivatives,
                "liquidations",
                provider_configured=providers.derivatives is not None,
                unsupported=unsupported,
            ),
            "trader_positioning": _derivative_signal(
                derivatives,
                "trader_positioning",
                provider_configured=providers.derivatives is not None,
                unsupported=unsupported,
            ),
        },
        "sentiment": _signal_from_provider(
            sentiment_raw, "sentiment", "sentiment_provider", unsupported=unsupported
        ),
        "position_context": {
            "status": "available",
            "source": "manual_entry",
            "retrieved_at": position.get("updated_at") or retrieved_at,
            "value": {
                "position_id": position.get("position_id"),
                "quantity": position.get("quantity"),
                "entry_price": position.get("entry_price"),
                "total_cost_basis": position.get("total_cost_basis"),
                "current_value": _float(current_value),
                "unrealized_pnl": _float(unrealized),
                "unrealized_pnl_pct": _float(unrealized_pct),
            },
            "freshness": "fresh",
            "missing_data_reason": None,
            "provider_error": None,
            "conflicts": [],
            "confidence_reasons": [],
        },
        "thesis": {
            "status": "available" if thesis else "unavailable",
            "source": "manual_entry" if thesis else None,
            "retrieved_at": thesis.get("updated_at") if thesis else None,
            "value": thesis,
            "freshness": "fresh" if thesis else "unavailable",
            "missing_data_reason": None if thesis else "No thesis supplied",
            "provider_error": None,
            "conflicts": [],
            "confidence_reasons": [],
        },
    }
    confidence = classify_confidence(sections)
    return {
        "packet_id": f"evidence-{uuid4().hex}",
        "schema_version": "ask_bhabit.evidence.v1",
        "retrieved_at": retrieved_at,
        "asset_id": asset["asset_id"],
        "asset_symbol": asset["symbol"],
        "public_market_evidence": {
            k: v for k, v in sections.items() if k not in ("position_context", "thesis")
        },
        "private_context": {
            "position": sections["position_context"],
            "thesis": sections["thesis"],
        },
        "confidence": confidence,
    }


def _iter_states(value: Any):
    if isinstance(value, dict):
        if "status" in value and value.get("status") in VALID_STATUSES:
            yield value
        for child in value.values():
            yield from _iter_states(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_states(item)


def classify_confidence(sections: dict[str, Any]) -> dict[str, Any]:
    states = list(_iter_states(sections))
    available = [s for s in states if s.get("status") == "available"]
    bad = [
        s
        for s in states
        if s.get("status") in {"provider_error", "conflicting", "stale"}
    ]
    required = [
        sections["asset_identity"],
        sections["price"],
        sections["position_context"],
    ]
    if any(s.get("status") != "available" for s in required):
        level = "insufficient_evidence"
    elif bad:
        level = "low"
    elif len(available) >= 8:
        level = "high"
    elif len(available) >= 4:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "reasons": [
            f"{len(available)} evidence fields available",
            f"{len(bad)} stale/error/conflicting fields",
            "asset identity, price, and position are required for sufficient evidence",
        ],
    }


def _get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


COMPARE_FIELDS = {
    "price": ("public_market_evidence", "price"),
    "volume": ("public_market_evidence", "volume_liquidity", "volume"),
    "momentum": ("public_market_evidence", "movement", "short_window"),
    "funding": ("public_market_evidence", "derivatives", "funding"),
    "open_interest": ("public_market_evidence", "derivatives", "open_interest"),
    "liquidations": ("public_market_evidence", "derivatives", "liquidations"),
    "sentiment": ("public_market_evidence", "sentiment"),
}


def compare_packets(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    if not previous:
        return {
            "status": "no_previous_snapshot",
            "categories": ["insufficient_evidence"],
            "changes": [],
            "thesis_support": {
                "direction": "unknown",
                "reasons": ["No previous snapshot to compare."],
            },
        }
    changes: list[dict[str, Any]] = []
    categories = set()
    for name, path in COMPARE_FIELDS.items():
        old = _get_path(previous, path) or {}
        new = _get_path(current, path) or {}
        if old.get("status") != new.get("status"):
            changes.append(
                {
                    "field": name,
                    "type": "status_change",
                    "from": old.get("status"),
                    "to": new.get("status"),
                }
            )
            categories.add("evidence_quality_changed")
        old_value = old.get("value")
        new_value = new.get("value")
        if (
            isinstance(old_value, (int, float))
            and isinstance(new_value, (int, float))
            and old_value != new_value
        ):
            pct = ((new_value - old_value) / old_value * 100) if old_value else None
            changes.append(
                {
                    "field": name,
                    "type": "numeric_change",
                    "from": old_value,
                    "to": new_value,
                    "absolute_change": new_value - old_value,
                    "percent_change": round(pct, 4) if pct is not None else None,
                }
            )
            if name == "price":
                categories.add("only_price_changed")
            elif name in {"funding", "open_interest", "liquidations", "momentum"}:
                categories.add("market_structure_changed")
    old_conf = previous.get("confidence", {}).get("level")
    new_conf = current.get("confidence", {}).get("level")
    if old_conf != new_conf:
        changes.append(
            {
                "field": "confidence",
                "type": "evidence_quality_change",
                "from": old_conf,
                "to": new_conf,
            }
        )
        categories.add("evidence_quality_changed")
    thesis = current.get("private_context", {}).get("thesis", {})
    thesis_direction = "unknown"
    thesis_reasons = ["No thesis supplied."]
    if thesis.get("status") == "available":
        thesis_direction = "unchanged"
        thesis_reasons = [
            "Thesis exists, but beta comparison uses deterministic market/status changes only."
        ]
        if any(
            c.get("field") in {"momentum", "funding", "open_interest", "sentiment"}
            for c in changes
        ):
            thesis_direction = "unknown"
            thesis_reasons = [
                "Relevant evidence changed; LLM must assess thesis support from supplied packet only."
            ]
            categories.add("thesis_evidence_changed")
    meaningful_categories = categories - {"only_price_changed"}
    if "only_price_changed" in categories and meaningful_categories:
        categories.remove("only_price_changed")
    if not changes:
        categories.add("insufficient_evidence")
    return {
        "status": "compared",
        "categories": sorted(categories),
        "changes": changes,
        "thesis_support": {"direction": thesis_direction, "reasons": thesis_reasons},
    }


def build_analysis_prompt(
    packet: dict[str, Any], comparison: dict[str, Any] | None = None
) -> str:
    allowed = {"evidence_packet": packet, "prior_snapshot_comparison": comparison or {}}
    return (
        "You are Ask Bhabit. Use only the JSON below. Do not invent absent data. "
        "Never treat missing sentiment as neutral and never convert missing values to zero. "
        "Return sections: Direct assessment; What changed; Position impact; Thesis check; "
        "Missing or uncertain evidence; Risks and catalysts; Sources and timestamps; "
        "Confidence and reasons.\n\n"
        + json.dumps(allowed, sort_keys=True, separators=(",", ":"))
    )


def generate_analysis(
    packet: dict[str, Any], comparison: dict[str, Any]
) -> dict[str, Any]:
    prompt = build_analysis_prompt(packet, comparison)
    if not os.getenv("ASK_BHABIT_SERVER_KEY") or not PROVIDERS.llm:
        text = "Analysis generation unavailable: founder/server key or LLM provider is not configured."
        status = "not_configured"
    else:
        text = PROVIDERS.llm(prompt)
        status = "available"
    return {
        "analysis_id": f"analysis-{uuid4().hex}",
        "created_at": _utc_now(),
        "status": status,
        "sections": {
            "direct_assessment": text,
            "what_changed": comparison,
            "position_impact": None,
            "thesis_check": comparison.get("thesis_support"),
            "missing_or_uncertain_evidence": [
                {
                    "source": s.get("source"),
                    "status": s.get("status"),
                    "reason": s.get("missing_data_reason") or s.get("provider_error"),
                }
                for s in _iter_states(packet)
                if s.get("status") != "available"
            ],
            "risks_and_catalysts": [],
            "sources_and_timestamps": [
                {
                    "source": s.get("source"),
                    "retrieved_at": s.get("retrieved_at"),
                    "freshness": s.get("freshness"),
                }
                for s in _iter_states(packet)
                if s.get("source")
            ],
            "confidence_and_reasons": packet.get("confidence"),
        },
    }


def _json_ok(data: Any, status: int = 200):
    return jsonify({"success": True, "data": data}), status


def _json_err(code: str, message: str, status: int = 400):
    return (
        jsonify({"success": False, "error": {"code": code, "message": message}}),
        status,
    )


@ask_bhabit_bp.route(
    "/api/ask-bhabit/position", methods=["GET", "POST", "PUT", "PATCH"]
)
def position_route():
    store = get_store()
    if request.method == "GET":
        return _json_ok(store.load().get("position"))
    return _json_ok(store.upsert_position(request.get_json(silent=True) or {}))


@ask_bhabit_bp.route("/api/ask-bhabit/thesis", methods=["GET", "POST", "PUT", "PATCH"])
def thesis_route():
    store = get_store()
    if request.method == "GET":
        return _json_ok(store.load().get("thesis"))
    return _json_ok(store.upsert_thesis(request.get_json(silent=True) or {}))


@ask_bhabit_bp.route("/api/ask-bhabit/evidence", methods=["GET"])
def evidence_route():
    data = get_store().load()
    position = data.get("position")
    if not position:
        return _json_err("position_required", "Create a manual position first.", 409)
    return _json_ok(build_evidence_packet(position, data.get("thesis")))


@ask_bhabit_bp.route("/api/ask-bhabit/analyze", methods=["POST"])
def analyze_route():
    store = get_store()
    data = store.load()
    position = data.get("position")
    if not position:
        return _json_err("position_required", "Create a manual position first.", 409)
    packet = build_evidence_packet(position, data.get("thesis"))
    previous = (data.get("snapshots") or [])[-1] if data.get("snapshots") else None
    comparison = compare_packets(
        previous.get("evidence_packet") if previous else None, packet
    )
    analysis = generate_analysis(packet, comparison)
    snapshot = {
        "snapshot_id": f"snapshot-{uuid4().hex}",
        "created_at": _utc_now(),
        "evidence_packet": packet,
        "comparison": comparison,
        "analysis": analysis,
        "position_ref": position.get("position_id"),
        "thesis_ref": (data.get("thesis") or {}).get("thesis_id"),
    }
    store.append_snapshot(snapshot)
    return _json_ok(snapshot, 201)


@ask_bhabit_bp.route("/api/ask-bhabit/analysis/latest", methods=["GET"])
def latest_analysis_route():
    snapshots = get_store().load().get("snapshots") or []
    return _json_ok(snapshots[-1] if snapshots else None)


@ask_bhabit_bp.route("/api/ask-bhabit/snapshots", methods=["GET"])
def snapshots_route():
    return _json_ok(get_store().load().get("snapshots") or [])


@ask_bhabit_bp.route("/api/ask-bhabit/what-changed", methods=["GET"])
def what_changed_route():
    snapshots = get_store().load().get("snapshots") or []
    if len(snapshots) < 2:
        current = snapshots[-1]["evidence_packet"] if snapshots else None
        return _json_ok(
            compare_packets(None, current)
            if current
            else {
                "status": "no_snapshot",
                "categories": ["insufficient_evidence"],
                "changes": [],
            }
        )
    return _json_ok(
        compare_packets(
            snapshots[-2]["evidence_packet"], snapshots[-1]["evidence_packet"]
        )
    )


__all__ = [
    "ASSET_REGISTRY",
    "AskBhabitProviders",
    "SnapshotStore",
    "ask_bhabit_bp",
    "build_analysis_prompt",
    "build_evidence_packet",
    "classify_confidence",
    "compare_packets",
    "generate_analysis",
    "normalize_position",
    "normalize_thesis",
    "resolve_asset",
]
