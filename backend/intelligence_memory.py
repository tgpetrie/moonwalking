"""Durable memory for portfolio snapshots and evidence packet history.

This module keeps the evidence schema unified while giving the backend a
minimal persistent memory layer:

- portfolio snapshots: what existed at a given capture point
- evidence packets: what Ask Bhabit used to explain a result
- intelligence events: future-ready scheduled observations

It intentionally stores raw JSON alongside a small normalized index so we can
compare states without inventing a second intelligence architecture.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import math
import os
import sqlite3
import threading
from uuid import uuid4


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent / "data" / "intelligence_memory.sqlite"
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str:
    return str(value or "").strip()


def _asset_key(row: dict[str, Any]) -> str:
    asset_id = _str(row.get("asset_id"))
    if asset_id:
        return asset_id.upper()
    symbol = _str(row.get("symbol") or row.get("asset_symbol"))
    return symbol.upper()


def _summary_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = snapshot.get("summary")
    return deepcopy(raw) if isinstance(raw, dict) else {}


def _summary_value(summary: dict[str, Any], key: str) -> float | None:
    return _number(summary.get(key))


def _normalize_holding(holding: dict[str, Any]) -> dict[str, Any]:
    cost_basis = holding.get("cost_basis")
    cost_basis_usd = None
    if isinstance(cost_basis, dict):
        cost_basis_usd = _number(cost_basis.get("known_cost_usd"))
        if cost_basis_usd is None:
            cost_basis_usd = _number(cost_basis.get("total_cost_basis"))
    return {
        "asset_id": _asset_key(holding),
        "asset_symbol": _str(
            holding.get("symbol") or holding.get("asset_symbol")
        ).upper(),
        "quantity": _number(holding.get("quantity")),
        "value_usd": _number(
            holding.get("market_value_usd")
            if holding.get("market_value_usd") is not None
            else holding.get("value_usd")
        ),
        "cost_basis_usd": cost_basis_usd,
        "price_usd": _number(holding.get("price_usd")),
        "allocation_pct": _number(holding.get("allocation_pct")),
        "is_cash": bool(holding.get("is_cash")),
        "raw": deepcopy(holding),
    }


def _portfolio_changes(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    if not previous:
        return {
            "status": "no_previous_snapshot",
            "categories": ["insufficient_history"],
            "summary_changes": [],
            "holdings_added": [],
            "holdings_removed": [],
            "holdings_changed": [],
        }

    prev_summary = _summary_snapshot(previous)
    curr_summary = _summary_snapshot(current)
    summary_changes = []
    for key in (
        "total_value_usd",
        "cash_value_usd",
        "crypto_value_usd",
        "holding_count",
        "open_order_count",
        "known_unrealized_pnl_usd",
        "cost_basis_coverage_pct",
    ):
        old = _summary_value(prev_summary, key)
        new = _summary_value(curr_summary, key)
        if old == new:
            continue
        item = {"field": key, "from": old, "to": new}
        if old is not None and new is not None:
            item["delta"] = round(new - old, 8)
        summary_changes.append(item)

    prev_holdings = {
        _asset_key(row): _normalize_holding(row)
        for row in (previous.get("holdings") or [])
        if isinstance(row, dict)
    }
    curr_holdings = {
        _asset_key(row): _normalize_holding(row)
        for row in (current.get("holdings") or [])
        if isinstance(row, dict)
    }

    holdings_added = []
    holdings_removed = []
    holdings_changed = []
    categories = set()

    for asset_key in sorted(curr_holdings.keys() - prev_holdings.keys()):
        holdings_added.append(curr_holdings[asset_key])
        categories.add("holdings_added")
    for asset_key in sorted(prev_holdings.keys() - curr_holdings.keys()):
        holdings_removed.append(prev_holdings[asset_key])
        categories.add("holdings_removed")

    for asset_key in sorted(curr_holdings.keys() & prev_holdings.keys()):
        previous_row = prev_holdings[asset_key]
        current_row = curr_holdings[asset_key]
        row_changes = []
        for field in (
            "quantity",
            "value_usd",
            "cost_basis_usd",
            "price_usd",
            "allocation_pct",
        ):
            old = previous_row.get(field)
            new = current_row.get(field)
            if old == new:
                continue
            entry = {"field": field, "from": old, "to": new}
            if old is not None and new is not None:
                entry["delta"] = round(float(new) - float(old), 8)
            row_changes.append(entry)
        if row_changes:
            categories.add("holdings_changed")
            holdings_changed.append(
                {
                    "asset_id": asset_key,
                    "asset_symbol": current_row.get("asset_symbol")
                    or previous_row.get("asset_symbol"),
                    "changes": row_changes,
                }
            )

    if summary_changes:
        categories.add("summary_changed")
    if not categories:
        categories.add("unchanged")

    return {
        "status": "compared",
        "categories": sorted(categories),
        "summary_changes": summary_changes,
        "holdings_added": holdings_added,
        "holdings_removed": holdings_removed,
        "holdings_changed": holdings_changed,
    }


class IntelligenceMemoryStore:
    def __init__(self, db_path: str | Path | None = None):
        configured = os.getenv("MW_INTELLIGENCE_MEMORY_DB")
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        self._init_lock = threading.Lock()
        self.ensure_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=8, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=8000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_db(self) -> None:
        with self._init_lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        scope TEXT NOT NULL DEFAULT 'portfolio',
                        source TEXT NOT NULL,
                        captured_at TEXT NOT NULL,
                        previous_snapshot_id INTEGER,
                        snapshot_hash TEXT,
                        summary_json TEXT NOT NULL,
                        change_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(previous_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
                    );

                    CREATE TABLE IF NOT EXISTS portfolio_snapshot_holdings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id INTEGER NOT NULL,
                        asset_id TEXT NOT NULL,
                        asset_symbol TEXT NOT NULL,
                        quantity REAL,
                        value_usd REAL,
                        cost_basis_usd REAL,
                        price_usd REAL,
                        allocation_pct REAL,
                        is_cash INTEGER NOT NULL DEFAULT 0,
                        raw_json TEXT NOT NULL,
                        FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
                        UNIQUE(snapshot_id, asset_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_scope_time
                        ON portfolio_snapshots(user_id, scope, captured_at);
                    CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_snapshot
                        ON portfolio_snapshot_holdings(snapshot_id, asset_symbol);

                    CREATE TABLE IF NOT EXISTS evidence_packets (
                        packet_id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL DEFAULT 'ask_bhabit',
                        user_id INTEGER,
                        series_key TEXT NOT NULL,
                        asset_id TEXT,
                        asset_symbol TEXT,
                        position_ref TEXT,
                        thesis_ref TEXT,
                        portfolio_snapshot_id INTEGER,
                        previous_packet_id TEXT,
                        schema_version TEXT NOT NULL,
                        origin TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        packet_json TEXT NOT NULL,
                        comparison_json TEXT,
                        analysis_json TEXT,
                        FOREIGN KEY(previous_packet_id) REFERENCES evidence_packets(packet_id) ON DELETE SET NULL,
                        FOREIGN KEY(portfolio_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_evidence_packets_series
                        ON evidence_packets(scope, user_id, series_key, created_at);
                    CREATE INDEX IF NOT EXISTS idx_evidence_packets_asset
                        ON evidence_packets(asset_id, created_at);
                    CREATE INDEX IF NOT EXISTS idx_evidence_packets_portfolio_snapshot
                        ON evidence_packets(portfolio_snapshot_id, created_at);

                    CREATE TABLE IF NOT EXISTS intelligence_events (
                        event_id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL DEFAULT 'future_engine',
                        user_id INTEGER,
                        asset_id TEXT,
                        asset_symbol TEXT,
                        event_type TEXT NOT NULL,
                        observed_at TEXT NOT NULL,
                        portfolio_snapshot_id INTEGER,
                        evidence_packet_id TEXT,
                        state_before_snapshot_id INTEGER,
                        state_after_snapshot_id INTEGER,
                        importance_score REAL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(portfolio_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL,
                        FOREIGN KEY(evidence_packet_id) REFERENCES evidence_packets(packet_id) ON DELETE SET NULL,
                        FOREIGN KEY(state_before_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL,
                        FOREIGN KEY(state_after_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_intelligence_events_user_time
                        ON intelligence_events(user_id, observed_at);
                    CREATE INDEX IF NOT EXISTS idx_intelligence_events_asset_time
                        ON intelligence_events(asset_id, observed_at);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def latest_portfolio_snapshot(
        self, user_id: int, *, scope: str = "portfolio"
    ) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM portfolio_snapshots
                WHERE user_id = ? AND scope = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (int(user_id), scope),
            ).fetchone()
            if not row:
                return None
            holdings = conn.execute(
                """
                SELECT asset_id, asset_symbol, quantity, value_usd, cost_basis_usd,
                       price_usd, allocation_pct, is_cash, raw_json
                FROM portfolio_snapshot_holdings
                WHERE snapshot_id = ?
                ORDER BY asset_symbol ASC, id ASC
                """,
                (row["id"],),
            ).fetchall()
            return {
                "snapshot_id": row["id"],
                "user_id": row["user_id"],
                "scope": row["scope"],
                "source": row["source"],
                "captured_at": row["captured_at"],
                "previous_snapshot_id": row["previous_snapshot_id"],
                "snapshot_hash": row["snapshot_hash"],
                "summary": _json_loads(row["summary_json"], {}),
                "change": _json_loads(row["change_json"], {}),
                "created_at": row["created_at"],
                "holdings": [
                    {
                        "asset_id": item["asset_id"],
                        "asset_symbol": item["asset_symbol"],
                        "quantity": item["quantity"],
                        "value_usd": item["value_usd"],
                        "cost_basis_usd": item["cost_basis_usd"],
                        "price_usd": item["price_usd"],
                        "allocation_pct": item["allocation_pct"],
                        "is_cash": bool(item["is_cash"]),
                        "raw": _json_loads(item["raw_json"], {}),
                    }
                    for item in holdings
                ],
            }
        finally:
            conn.close()

    def recent_portfolio_snapshots(
        self, user_id: int, *, scope: str = "portfolio", limit: int = 2
    ) -> list[dict[str, Any]]:
        """Return the most recent snapshots (newest first) with holdings.

        Reuses the same normalized shape as ``latest_portfolio_snapshot`` so the
        delta engine can consume history without a second query per row.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM portfolio_snapshots
                WHERE user_id = ? AND scope = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (int(user_id), scope, int(max(1, limit))),
            ).fetchall()
            snapshots: list[dict[str, Any]] = []
            for row in rows:
                holdings = conn.execute(
                    """
                    SELECT asset_id, asset_symbol, quantity, value_usd, cost_basis_usd,
                           price_usd, allocation_pct, is_cash, raw_json
                    FROM portfolio_snapshot_holdings
                    WHERE snapshot_id = ?
                    ORDER BY asset_symbol ASC, id ASC
                    """,
                    (row["id"],),
                ).fetchall()
                snapshots.append(
                    {
                        "snapshot_id": row["id"],
                        "user_id": row["user_id"],
                        "scope": row["scope"],
                        "source": row["source"],
                        "captured_at": row["captured_at"],
                        "previous_snapshot_id": row["previous_snapshot_id"],
                        "snapshot_hash": row["snapshot_hash"],
                        "summary": _json_loads(row["summary_json"], {}),
                        "change": _json_loads(row["change_json"], {}),
                        "created_at": row["created_at"],
                        "holdings": [
                            {
                                "asset_id": item["asset_id"],
                                "asset_symbol": item["asset_symbol"],
                                "quantity": item["quantity"],
                                "value_usd": item["value_usd"],
                                "cost_basis_usd": item["cost_basis_usd"],
                                "price_usd": item["price_usd"],
                                "allocation_pct": item["allocation_pct"],
                                "is_cash": bool(item["is_cash"]),
                                "raw": _json_loads(item["raw_json"], {}),
                            }
                            for item in holdings
                        ],
                    }
                )
            return snapshots
        finally:
            conn.close()

    def record_portfolio_snapshot(
        self,
        user_id: int,
        snapshot: dict[str, Any],
        *,
        scope: str = "portfolio",
        source: str = "portfolio_mode",
        captured_at: str | None = None,
    ) -> dict[str, Any]:
        safe_snapshot = deepcopy(snapshot) if isinstance(snapshot, dict) else {}
        summary = _summary_snapshot(safe_snapshot)
        holdings_raw = safe_snapshot.get("holdings") or []
        holdings = [
            _normalize_holding(row) for row in holdings_raw if isinstance(row, dict)
        ]
        captured_at = _str(captured_at or safe_snapshot.get("updated_at") or _utc_now())
        snapshot_hash = _json_dumps(
            {
                "summary": summary,
                "holdings": [
                    {
                        "asset_id": item["asset_id"],
                        "quantity": item["quantity"],
                        "value_usd": item["value_usd"],
                        "cost_basis_usd": item["cost_basis_usd"],
                        "price_usd": item["price_usd"],
                        "allocation_pct": item["allocation_pct"],
                        "is_cash": item["is_cash"],
                    }
                    for item in holdings
                ],
            }
        )

        conn = self._connect()
        try:
            previous = conn.execute(
                """
                SELECT id, summary_json, change_json
                FROM portfolio_snapshots
                WHERE user_id = ? AND scope = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (int(user_id), scope),
            ).fetchone()
            previous_snapshot = None
            if previous:
                previous_snapshot = {
                    "summary": _json_loads(previous["summary_json"], {}),
                    "holdings": [],
                }
                prev_holdings = conn.execute(
                    """
                    SELECT asset_id, asset_symbol, quantity, value_usd, cost_basis_usd,
                           price_usd, allocation_pct, is_cash, raw_json
                    FROM portfolio_snapshot_holdings
                    WHERE snapshot_id = ?
                    ORDER BY asset_symbol ASC, id ASC
                    """,
                    (previous["id"],),
                ).fetchall()
                previous_snapshot["holdings"] = [
                    {
                        "asset_id": row["asset_id"],
                        "asset_symbol": row["asset_symbol"],
                        "quantity": row["quantity"],
                        "value_usd": row["value_usd"],
                        "cost_basis_usd": row["cost_basis_usd"],
                        "price_usd": row["price_usd"],
                        "allocation_pct": row["allocation_pct"],
                        "is_cash": bool(row["is_cash"]),
                        "raw": _json_loads(row["raw_json"], {}),
                    }
                    for row in prev_holdings
                ]

            change = _portfolio_changes(previous_snapshot, safe_snapshot)
            cursor = conn.execute(
                """
                INSERT INTO portfolio_snapshots (
                    user_id, scope, source, captured_at, previous_snapshot_id,
                    snapshot_hash, summary_json, change_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    scope,
                    source,
                    captured_at,
                    previous["id"] if previous else None,
                    snapshot_hash,
                    _json_dumps(summary),
                    _json_dumps(change),
                    _utc_now(),
                ),
            )
            snapshot_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT INTO portfolio_snapshot_holdings (
                    snapshot_id, asset_id, asset_symbol, quantity, value_usd,
                    cost_basis_usd, price_usd, allocation_pct, is_cash, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id,
                        item["asset_id"],
                        item["asset_symbol"],
                        item["quantity"],
                        item["value_usd"],
                        item["cost_basis_usd"],
                        item["price_usd"],
                        item["allocation_pct"],
                        1 if item["is_cash"] else 0,
                        _json_dumps(item["raw"]),
                    )
                    for item in holdings
                ],
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "snapshot_id": snapshot_id,
            "user_id": int(user_id),
            "scope": scope,
            "source": source,
            "captured_at": captured_at,
            "previous_snapshot_id": previous["id"] if previous else None,
            "snapshot_hash": snapshot_hash,
            "summary": summary,
            "change": change,
            "holdings_count": len(holdings),
        }

    def latest_evidence_packet(
        self,
        *,
        scope: str = "ask_bhabit",
        user_id: int | None = None,
        series_key: str | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            filters = ["scope = ?"]
            params: list[Any] = [scope]
            if user_id is None:
                filters.append("user_id IS NULL")
            else:
                filters.append("user_id = ?")
                params.append(int(user_id))
            if series_key is not None:
                filters.append("series_key = ?")
                params.append(series_key)
            if asset_id is not None:
                filters.append("asset_id = ?")
                params.append(_str(asset_id).upper())
            where_clause = " AND ".join(filters)
            row = conn.execute(
                f"""
                SELECT *
                FROM evidence_packets
                WHERE {where_clause}
                ORDER BY created_at DESC, packet_id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            if not row:
                return None
            return {
                "packet_id": row["packet_id"],
                "scope": row["scope"],
                "user_id": row["user_id"],
                "series_key": row["series_key"],
                "asset_id": row["asset_id"],
                "asset_symbol": row["asset_symbol"],
                "position_ref": row["position_ref"],
                "thesis_ref": row["thesis_ref"],
                "portfolio_snapshot_id": row["portfolio_snapshot_id"],
                "previous_packet_id": row["previous_packet_id"],
                "schema_version": row["schema_version"],
                "origin": row["origin"],
                "created_at": row["created_at"],
                "packet": _json_loads(row["packet_json"], {}),
                "comparison": _json_loads(row["comparison_json"], {}),
                "analysis": _json_loads(row["analysis_json"], {}),
            }
        finally:
            conn.close()

    def record_evidence_packet(
        self,
        packet: dict[str, Any],
        *,
        scope: str = "ask_bhabit",
        user_id: int | None = None,
        series_key: str | None = None,
        asset_id: str | None = None,
        asset_symbol: str | None = None,
        position_ref: str | None = None,
        thesis_ref: str | None = None,
        portfolio_snapshot_id: int | None = None,
        comparison: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        origin: str = "ask_bhabit",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(packet, dict):
            raise TypeError("packet must be a dict")

        packet_id = _str(packet.get("packet_id")) or f"evidence-{uuid4().hex}"
        packet_asset_id = _str(asset_id or packet.get("asset_id")).upper()
        packet_asset_symbol = _str(asset_symbol or packet.get("asset_symbol")).upper()
        packet_series_key = (
            _str(series_key) or packet_asset_id or packet_asset_symbol or "global"
        )
        created_at = _str(created_at or packet.get("retrieved_at") or _utc_now())

        conn = self._connect()
        try:
            previous = conn.execute(
                """
                SELECT packet_id
                FROM evidence_packets
                WHERE scope = ?
                  AND (
                        (user_id IS NULL AND ? IS NULL)
                     OR user_id = ?
                  )
                  AND series_key = ?
                ORDER BY created_at DESC, packet_id DESC
                LIMIT 1
                """,
                (scope, user_id, user_id, packet_series_key),
            ).fetchone()
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_packets (
                    packet_id, scope, user_id, series_key, asset_id, asset_symbol,
                    position_ref, thesis_ref, portfolio_snapshot_id, previous_packet_id,
                    schema_version, origin, created_at, packet_json, comparison_json,
                    analysis_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    packet_id,
                    scope,
                    user_id,
                    packet_series_key,
                    packet_asset_id or None,
                    packet_asset_symbol or None,
                    position_ref,
                    thesis_ref,
                    portfolio_snapshot_id,
                    previous["packet_id"] if previous else None,
                    str(packet.get("schema_version") or "ask_bhabit.evidence.v1"),
                    origin,
                    created_at,
                    _json_dumps(packet),
                    _json_dumps(comparison or {}),
                    _json_dumps(analysis or {}),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "packet_id": packet_id,
            "scope": scope,
            "user_id": user_id,
            "series_key": packet_series_key,
            "asset_id": packet_asset_id or None,
            "asset_symbol": packet_asset_symbol or None,
            "position_ref": position_ref,
            "thesis_ref": thesis_ref,
            "portfolio_snapshot_id": portfolio_snapshot_id,
            "previous_packet_id": previous["packet_id"] if previous else None,
            "schema_version": str(
                packet.get("schema_version") or "ask_bhabit.evidence.v1"
            ),
            "origin": origin,
            "created_at": created_at,
            "packet": deepcopy(packet),
            "comparison": deepcopy(comparison or {}),
            "analysis": deepcopy(analysis or {}),
        }

    def list_intelligence_events(
        self,
        *,
        user_id: int | None = None,
        scope: str | None = None,
        event_type: str | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 20,
        include_packet: bool = True,
    ) -> list[dict[str, Any]]:
        """Return recent intelligence events (newest first), optionally joined
        to the evidence packet that explains each one.

        This is the read side of the proactive engine: the detector writes
        events, the feed reads them. The join is done here so callers get one
        already-assembled record instead of N+1 lookups.
        """
        filters: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            filters.append("e.user_id = ?")
            params.append(int(user_id))
        if scope is not None:
            filters.append("e.scope = ?")
            params.append(scope)
        if event_type is not None:
            filters.append("e.event_type = ?")
            params.append(event_type)
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            filters.append(f"e.status IN ({placeholders})")
            params.extend(statuses)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(int(max(1, limit)))

        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT e.*,
                       p.packet_json AS packet_json,
                       p.comparison_json AS packet_comparison_json,
                       p.schema_version AS packet_schema_version,
                       p.created_at AS packet_created_at
                FROM intelligence_events AS e
                LEFT JOIN evidence_packets AS p
                       ON p.packet_id = e.evidence_packet_id
                {where_clause}
                ORDER BY e.observed_at DESC, e.event_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                record = {
                    "event_id": row["event_id"],
                    "scope": row["scope"],
                    "user_id": row["user_id"],
                    "asset_id": row["asset_id"],
                    "asset_symbol": row["asset_symbol"],
                    "event_type": row["event_type"],
                    "observed_at": row["observed_at"],
                    "portfolio_snapshot_id": row["portfolio_snapshot_id"],
                    "evidence_packet_id": row["evidence_packet_id"],
                    "state_before_snapshot_id": row["state_before_snapshot_id"],
                    "state_after_snapshot_id": row["state_after_snapshot_id"],
                    "importance_score": row["importance_score"],
                    "status": row["status"],
                    "payload": _json_loads(row["payload_json"], {}),
                    "created_at": row["created_at"],
                }
                if include_packet:
                    record["evidence_packet"] = _json_loads(row["packet_json"], None)
                    record["evidence_comparison"] = _json_loads(
                        row["packet_comparison_json"], None
                    )
                    record["evidence_schema_version"] = row["packet_schema_version"]
                events.append(record)
            return events
        finally:
            conn.close()

    def update_intelligence_event_status(
        self, event_id: str, status: str, *, user_id: int | None = None
    ) -> bool:
        """Transition an event's lifecycle status (e.g. detected -> seen).

        Scoped by user_id when supplied so one member can never mutate another
        member's feed. Returns True when a row actually changed.
        """
        conn = self._connect()
        try:
            if user_id is None:
                cursor = conn.execute(
                    "UPDATE intelligence_events SET status = ? WHERE event_id = ?",
                    (status, _str(event_id)),
                )
            else:
                cursor = conn.execute(
                    "UPDATE intelligence_events SET status = ? WHERE event_id = ? AND user_id = ?",
                    (status, _str(event_id), int(user_id)),
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def record_intelligence_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        user_id: int | None = None,
        scope: str = "future_engine",
        asset_id: str | None = None,
        asset_symbol: str | None = None,
        observed_at: str | None = None,
        portfolio_snapshot_id: int | None = None,
        evidence_packet_id: str | None = None,
        state_before_snapshot_id: int | None = None,
        state_after_snapshot_id: int | None = None,
        importance_score: float | None = None,
        status: str = "pending",
        event_id: str | None = None,
    ) -> dict[str, Any]:
        event_id = _str(event_id) or f"event-{uuid4().hex}"
        observed_at = _str(observed_at or _utc_now())
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO intelligence_events (
                    event_id, scope, user_id, asset_id, asset_symbol, event_type,
                    observed_at, portfolio_snapshot_id, evidence_packet_id,
                    state_before_snapshot_id, state_after_snapshot_id,
                    importance_score, status, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    scope,
                    user_id,
                    _str(asset_id).upper() or None,
                    _str(asset_symbol).upper() or None,
                    event_type,
                    observed_at,
                    portfolio_snapshot_id,
                    evidence_packet_id,
                    state_before_snapshot_id,
                    state_after_snapshot_id,
                    importance_score,
                    status,
                    _json_dumps(payload or {}),
                    _utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "event_id": event_id,
            "scope": scope,
            "user_id": user_id,
            "asset_id": _str(asset_id).upper() or None,
            "asset_symbol": _str(asset_symbol).upper() or None,
            "event_type": event_type,
            "observed_at": observed_at,
            "portfolio_snapshot_id": portfolio_snapshot_id,
            "evidence_packet_id": evidence_packet_id,
            "state_before_snapshot_id": state_before_snapshot_id,
            "state_after_snapshot_id": state_after_snapshot_id,
            "importance_score": importance_score,
            "status": status,
            "payload": deepcopy(payload or {}),
        }


def get_intelligence_memory_store(
    db_path: str | Path | None = None,
) -> IntelligenceMemoryStore:
    return IntelligenceMemoryStore(db_path)


def record_portfolio_snapshot(
    user_id: int,
    snapshot: dict[str, Any],
    *,
    scope: str = "portfolio",
    source: str = "portfolio_mode",
    captured_at: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    return get_intelligence_memory_store(db_path).record_portfolio_snapshot(
        user_id,
        snapshot,
        scope=scope,
        source=source,
        captured_at=captured_at,
    )


def record_evidence_packet(
    packet: dict[str, Any],
    *,
    scope: str = "ask_bhabit",
    user_id: int | None = None,
    series_key: str | None = None,
    asset_id: str | None = None,
    asset_symbol: str | None = None,
    position_ref: str | None = None,
    thesis_ref: str | None = None,
    portfolio_snapshot_id: int | None = None,
    comparison: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    origin: str = "ask_bhabit",
    created_at: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    return get_intelligence_memory_store(db_path).record_evidence_packet(
        packet,
        scope=scope,
        user_id=user_id,
        series_key=series_key,
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        position_ref=position_ref,
        thesis_ref=thesis_ref,
        portfolio_snapshot_id=portfolio_snapshot_id,
        comparison=comparison,
        analysis=analysis,
        origin=origin,
        created_at=created_at,
    )


def record_intelligence_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    user_id: int | None = None,
    scope: str = "future_engine",
    asset_id: str | None = None,
    asset_symbol: str | None = None,
    observed_at: str | None = None,
    portfolio_snapshot_id: int | None = None,
    evidence_packet_id: str | None = None,
    state_before_snapshot_id: int | None = None,
    state_after_snapshot_id: int | None = None,
    importance_score: float | None = None,
    status: str = "pending",
    event_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    return get_intelligence_memory_store(db_path).record_intelligence_event(
        event_type=event_type,
        payload=payload,
        user_id=user_id,
        scope=scope,
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        observed_at=observed_at,
        portfolio_snapshot_id=portfolio_snapshot_id,
        evidence_packet_id=evidence_packet_id,
        state_before_snapshot_id=state_before_snapshot_id,
        state_after_snapshot_id=state_after_snapshot_id,
        importance_score=importance_score,
        status=status,
        event_id=event_id,
    )


__all__ = [
    "IntelligenceMemoryStore",
    "get_intelligence_memory_store",
    "record_evidence_packet",
    "record_intelligence_event",
    "record_portfolio_snapshot",
]
