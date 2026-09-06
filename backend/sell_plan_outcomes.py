"""Durable forward measurement for generated sell-side risk plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import math
import os
import sqlite3
import threading
import time


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "sell_plan_outcomes.sqlite"
DEFAULT_HORIZON_SECONDS = 24 * 60 * 60
MEASUREMENT_MIN_COMPLETED = 20


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


class SellPlanOutcomeStore:
    """Record one plan per symbol/hour and grade the first boundary touched."""

    def __init__(self, db_path: str | Path | None = None):
        configured = os.getenv("MW_SELL_PLAN_OUTCOMES_DB")
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        self.horizon_seconds = max(
            3600,
            int(os.getenv("MW_SELL_PLAN_HORIZON_SECONDS", DEFAULT_HORIZON_SECONDS)),
        )
        self._init_lock = threading.Lock()
        self.ensure_db()

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_db(self):
        with self._init_lock:
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sell_plan_outcomes (
                        plan_id TEXT PRIMARY KEY,
                        product_id TEXT NOT NULL,
                        methodology_version TEXT NOT NULL,
                        created_ts INTEGER NOT NULL,
                        expires_ts INTEGER NOT NULL,
                        start_price REAL NOT NULL,
                        stop_trigger REAL NOT NULL,
                        stop_limit REAL NOT NULL,
                        target_price REAL NOT NULL,
                        support REAL,
                        resistance REAL,
                        plan_json TEXT NOT NULL,
                        last_ts INTEGER NOT NULL,
                        last_price REAL NOT NULL,
                        max_favorable_pct REAL NOT NULL DEFAULT 0,
                        max_adverse_pct REAL NOT NULL DEFAULT 0,
                        boundary_hit_ts INTEGER,
                        outcome TEXT,
                        complete INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_sell_plan_open "
                    "ON sell_plan_outcomes(complete, expires_ts)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_sell_plan_product "
                    "ON sell_plan_outcomes(product_id, created_ts DESC)"
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _product(value: Any) -> str:
        raw = str(value or "").strip().upper()
        return raw if "-" in raw else f"{raw}-USD"

    @staticmethod
    def _price_for(product_id: str, prices: dict[str, Any]) -> float | None:
        symbol = product_id.split("-")[0]
        value = prices.get(product_id) if product_id in prices else prices.get(symbol)
        parsed = _number(value)
        return parsed if parsed is not None and parsed > 0 else None

    def record_plan(
        self, plan: dict[str, Any], *, now_ts: int | None = None
    ) -> str | None:
        if not isinstance(plan, dict) or plan.get("available") is not True:
            return None
        now_ts = int(now_ts or time.time())
        product_id = self._product(plan.get("product_id"))
        start_price = _number(plan.get("current_price"))
        stop = plan.get("stop") if isinstance(plan.get("stop"), dict) else {}
        profit = plan.get("profit") if isinstance(plan.get("profit"), dict) else {}
        structure = (
            plan.get("market_structure")
            if isinstance(plan.get("market_structure"), dict)
            else {}
        )
        method = (
            plan.get("methodology") if isinstance(plan.get("methodology"), dict) else {}
        )
        stop_trigger = _number(stop.get("trigger_price"))
        stop_limit = _number(stop.get("limit_price"))
        target = _number(profit.get("measurement_target_price"))
        if not all(
            value is not None and value > 0
            for value in (start_price, stop_trigger, stop_limit, target)
        ):
            return None

        # A user reopening the popup should not manufacture more evidence.
        # The hour bucket yields at most one recorded plan per product/hour.
        bucket = now_ts // 3600
        identity = f"sell_levels_v1:{product_id}:{bucket}"
        plan_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO sell_plan_outcomes (
                    plan_id, product_id, methodology_version, created_ts, expires_ts,
                    start_price, stop_trigger, stop_limit, target_price, support,
                    resistance, plan_json, last_ts, last_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    product_id,
                    str(method.get("version") or "sell_levels_v1"),
                    now_ts,
                    now_ts + self.horizon_seconds,
                    start_price,
                    stop_trigger,
                    stop_limit,
                    target,
                    _number(structure.get("support")),
                    _number(structure.get("resistance")),
                    json.dumps(plan, separators=(",", ":"), sort_keys=True),
                    now_ts,
                    start_price,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return plan_id

    def observe(
        self,
        current_prices: dict[str, Any],
        *,
        now_ts: int | None = None,
    ) -> None:
        now_ts = int(now_ts or time.time())
        prices = current_prices if isinstance(current_prices, dict) else {}
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM sell_plan_outcomes WHERE complete = 0"
            ).fetchall()
            for row in rows:
                current = self._price_for(str(row["product_id"]), prices)
                if current is None:
                    if now_ts >= int(row["expires_ts"]):
                        conn.execute(
                            "UPDATE sell_plan_outcomes SET outcome = 'expired', "
                            "complete = 1 WHERE plan_id = ?",
                            (row["plan_id"],),
                        )
                    continue

                start = float(row["start_price"])
                move_pct = round(((current / start) - 1.0) * 100.0, 8)
                favorable = max(float(row["max_favorable_pct"] or 0), move_pct)
                adverse = min(float(row["max_adverse_pct"] or 0), move_pct)
                outcome = None
                complete = 0
                boundary_ts = None
                if current <= float(row["stop_trigger"]):
                    outcome, complete, boundary_ts = "stop_first", 1, now_ts
                elif current >= float(row["target_price"]):
                    outcome, complete, boundary_ts = "target_first", 1, now_ts
                elif now_ts >= int(row["expires_ts"]):
                    outcome, complete = "expired", 1

                conn.execute(
                    """
                    UPDATE sell_plan_outcomes
                    SET last_ts = ?, last_price = ?, max_favorable_pct = ?,
                        max_adverse_pct = ?, boundary_hit_ts = ?, outcome = ?, complete = ?
                    WHERE plan_id = ?
                    """,
                    (
                        now_ts,
                        current,
                        favorable,
                        adverse,
                        boundary_ts,
                        outcome,
                        complete,
                        row["plan_id"],
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def history(self, product_id: str, *, limit: int = 12) -> dict[str, Any]:
        normalized = self._product(product_id)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT plan_id, created_ts, expires_ts, start_price, stop_trigger,
                       stop_limit, target_price, support, resistance, last_price,
                       max_favorable_pct, max_adverse_pct, outcome, complete
                FROM sell_plan_outcomes
                WHERE product_id = ?
                ORDER BY created_ts DESC LIMIT ?
                """,
                (normalized, max(1, min(100, int(limit)))),
            ).fetchall()
            totals = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN complete = 0 THEN 1 ELSE 0 END) AS open_count,
                       SUM(CASE WHEN outcome = 'target_first' THEN 1 ELSE 0 END) AS target_count,
                       SUM(CASE WHEN outcome = 'stop_first' THEN 1 ELSE 0 END) AS stop_count,
                       SUM(CASE WHEN outcome = 'expired' THEN 1 ELSE 0 END) AS expired_count
                FROM sell_plan_outcomes WHERE product_id = ?
                """,
                (normalized,),
            ).fetchone()
        finally:
            conn.close()

        target_count = int(totals["target_count"] or 0)
        stop_count = int(totals["stop_count"] or 0)
        expired_count = int(totals["expired_count"] or 0)
        completed = target_count + stop_count + expired_count
        return {
            "product_id": normalized,
            "total_plans": int(totals["total"] or 0),
            "open_plans": int(totals["open_count"] or 0),
            "completed_plans": completed,
            "outcomes": {
                "target_first": target_count,
                "stop_first": stop_count,
                "expired": expired_count,
            },
            # Rates stay null until a future controlled methodology is built.
            # Raw boundary counts are useful and do not overstate predictiveness.
            "target_first_rate": None,
            "measurement_status": (
                "history_ready"
                if completed >= MEASUREMENT_MIN_COMPLETED
                else "collecting"
            ),
            "required_completed_plans": MEASUREMENT_MIN_COMPLETED,
            "history": [dict(row) for row in rows],
            "methodology_version": "sell_levels_v1",
            "disclosure": "Observed first boundary touched over 24 hours. Raw counts are shown; no predictive success rate is claimed.",
        }

    def status(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN complete = 0 THEN 1 ELSE 0 END) AS open_count,
                       SUM(CASE WHEN complete = 1 THEN 1 ELSE 0 END) AS completed_count
                FROM sell_plan_outcomes
                """
            ).fetchone()
        finally:
            conn.close()
        return {
            "total_plans": int(row["total"] or 0),
            "open_plans": int(row["open_count"] or 0),
            "completed_plans": int(row["completed_count"] or 0),
            "methodology_version": "sell_levels_v1",
        }


store = SellPlanOutcomeStore()


__all__ = ["SellPlanOutcomeStore", "store"]
