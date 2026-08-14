"""Durable forward-outcome measurement for Event Evolution transitions."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any, Iterable
import math
import os
import sqlite3
import threading
import time

from live_ranking import build_feature_snapshot


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "signal_outcomes.sqlite"
CHECKPOINTS = (
    (300, "return_5m"),
    (900, "return_15m"),
    (1800, "return_30m"),
    (3600, "return_60m"),
)


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None


class SignalOutcomeStore:
    """Record each published event transition and grade its next hour."""

    def __init__(self, db_path: str | Path | None = None):
        configured = os.getenv("MW_SIGNAL_OUTCOMES_DB")
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        self.target_pct = max(0.1, float(os.getenv("MW_OUTCOME_TARGET_PCT", "2.0")))
        self.adverse_pct = max(0.1, float(os.getenv("MW_OUTCOME_ADVERSE_PCT", "1.0")))
        self.horizon_seconds = max(
            300, int(os.getenv("MW_OUTCOME_HORIZON_SECONDS", "3600"))
        )
        self._init_lock = threading.Lock()
        self._history_lock = threading.Lock()
        self._history_cache: dict[
            tuple[str, str, str], tuple[float, dict[str, Any]]
        ] = {}
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
                    CREATE TABLE IF NOT EXISTS signal_outcomes (
                        signal_id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        primary_state TEXT NOT NULL,
                        read_label TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        confidence INTEGER NOT NULL,
                        started_ts INTEGER NOT NULL,
                        start_price REAL NOT NULL,
                        last_ts INTEGER NOT NULL,
                        last_price REAL NOT NULL,
                        return_5m REAL,
                        return_15m REAL,
                        return_30m REAL,
                        return_60m REAL,
                        max_favorable_pct REAL NOT NULL DEFAULT 0,
                        max_adverse_pct REAL NOT NULL DEFAULT 0,
                        target_hit_ts INTEGER,
                        adverse_hit_ts INTEGER,
                        outcome TEXT,
                        complete INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_compare "
                    "ON signal_outcomes(primary_state, direction, read_label, complete)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_open "
                    "ON signal_outcomes(complete, started_ts)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_product "
                    "ON signal_outcomes(product_id, complete)"
                )
                # Safe additive migration: no-op on a fresh DB; adds columns to
                # existing DBs without disturbing current rows (they remain NULL).
                existing = {
                    row[1] for row in conn.execute("PRAGMA table_info(signal_outcomes)")
                }
                for col_def in (
                    "feature_schema_version TEXT",
                    "feature_snapshot_json TEXT",
                ):
                    if col_def.split()[0] not in existing:
                        conn.execute(
                            f"ALTER TABLE signal_outcomes ADD COLUMN {col_def}"
                        )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _product(event: dict[str, Any]) -> str:
        raw = str(event.get("product_id") or event.get("symbol") or "").upper()
        return raw if "-" in raw else f"{raw}-USD"

    @staticmethod
    def _event_price(event: dict[str, Any], prices: dict[str, Any]) -> float | None:
        evidence = (
            event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        )
        for key in ("price", "price_now", "current_price"):
            parsed = _number(evidence.get(key))
            if parsed is not None and parsed > 0:
                return parsed
        product_id = SignalOutcomeStore._product(event)
        symbol = product_id.split("-")[0]
        parsed = _number(
            prices.get(product_id) if product_id in prices else prices.get(symbol)
        )
        return parsed if parsed is not None and parsed > 0 else None

    @staticmethod
    def _directional_return(direction: str, start: float, current: float) -> float:
        raw = ((current / start) - 1.0) * 100.0
        return -raw if str(direction).lower() == "down" else raw

    def observe(
        self,
        events: Iterable[dict[str, Any]],
        current_prices: dict[str, Any],
        *,
        now_ts: int | None = None,
        ranking_snapshot: dict[str, dict[str, Any]] | None = None,
        ranking_captured_ts: int | None = None,
    ) -> None:
        """Record new transitions and advance grading for open ones.

        ``ranking_snapshot`` maps bare symbol -> a build_live_rankings() row
        built with include_internal_features=True.  ``ranking_captured_ts`` is
        the instant that ranking calculation started; both are required
        together, because a snapshot dated by this method's own clock would
        misdate the state it claims to describe.  Snapshots are attached only
        to rows created by this call — the INSERT OR IGNORE below leaves an
        existing row, and its original snapshot, untouched.
        """
        now_ts = int(now_ts or time.time())
        prices = current_prices if isinstance(current_prices, dict) else {}
        rankings = ranking_snapshot if isinstance(ranking_snapshot, dict) else {}
        if ranking_captured_ts is None:
            rankings = {}
        conn = self._connect()
        try:
            for event in events or []:
                if not isinstance(event, dict) or not event.get("id"):
                    continue
                price = self._event_price(event, prices)
                if price is None:
                    continue
                started_ts = now_ts
                read = (
                    event.get("the_read")
                    if isinstance(event.get("the_read"), dict)
                    else {}
                )
                product_id = self._product(event)
                symbol = product_id.split("-")[0]
                ranking_row = rankings.get(symbol)
                if ranking_row is not None:
                    feat_ver, feat_json = build_feature_snapshot(
                        ranking_row, int(ranking_captured_ts)
                    )
                else:
                    feat_ver, feat_json = None, None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO signal_outcomes (
                        signal_id, event_id, product_id, primary_state, read_label,
                        direction, confidence, started_ts, start_price, last_ts, last_price,
                        feature_schema_version, feature_snapshot_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(event["id"]),
                        str(event.get("event_id") or event["id"]),
                        product_id,
                        str(event.get("primary_state") or "Building"),
                        str(read.get("label") or "UNCLASSIFIED"),
                        str(event.get("direction") or "neutral"),
                        int(_number(event.get("confidence")) or 0),
                        started_ts,
                        price,
                        now_ts,
                        price,
                        feat_ver,
                        feat_json,
                    ),
                )

            open_rows = conn.execute(
                "SELECT * FROM signal_outcomes WHERE complete = 0 AND started_ts <= ?",
                (now_ts,),
            ).fetchall()
            for row in open_rows:
                product_id = str(row["product_id"])
                symbol = product_id.split("-")[0]
                current = _number(
                    prices.get(product_id)
                    if product_id in prices
                    else prices.get(symbol)
                )
                if current is None or current <= 0:
                    continue
                directional = self._directional_return(
                    row["direction"], float(row["start_price"]), current
                )
                age = max(0, now_ts - int(row["started_ts"]))
                max_favorable = float(row["max_favorable_pct"] or 0)
                max_adverse = float(row["max_adverse_pct"] or 0)
                target_hit = row["target_hit_ts"]
                adverse_hit = row["adverse_hit_ts"]
                if age <= self.horizon_seconds:
                    max_favorable = max(max_favorable, directional)
                    max_adverse = min(max_adverse, directional)
                    if target_hit is None and directional >= self.target_pct:
                        target_hit = now_ts
                    if adverse_hit is None and directional <= -self.adverse_pct:
                        adverse_hit = now_ts

                updates: dict[str, Any] = {
                    "last_ts": now_ts,
                    "last_price": current,
                    "max_favorable_pct": max_favorable,
                    "max_adverse_pct": max_adverse,
                    "target_hit_ts": target_hit,
                    "adverse_hit_ts": adverse_hit,
                }
                checkpoint = next(
                    (
                        (seconds, column)
                        for seconds, column in reversed(CHECKPOINTS)
                        if age >= seconds
                    ),
                    None,
                )
                if checkpoint is not None:
                    _, column = checkpoint
                    if row[column] is None:
                        updates[column] = directional
                if age >= self.horizon_seconds:
                    won = target_hit is not None and (
                        adverse_hit is None or int(target_hit) < int(adverse_hit)
                    )
                    updates["outcome"] = (
                        "followed_through" if won else "did_not_follow_through"
                    )
                    updates["complete"] = 1

                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(
                    f"UPDATE signal_outcomes SET {assignments} WHERE signal_id = ?",
                    [*updates.values(), row["signal_id"]],
                )
            conn.commit()
        finally:
            conn.close()
        with self._history_lock:
            self._history_cache.clear()

    def history_for(self, event: dict[str, Any]) -> dict[str, Any]:
        read = event.get("the_read") if isinstance(event.get("the_read"), dict) else {}
        state = str(event.get("primary_state") or "Building")
        direction = str(event.get("direction") or "neutral")
        read_label = str(read.get("label") or "UNCLASSIFIED")
        cache_key = (state, direction, read_label)
        with self._history_lock:
            cached = self._history_cache.get(cache_key)
            if cached and (time.monotonic() - cached[0]) < 30:
                return dict(cached[1])
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT outcome, max_favorable_pct, max_adverse_pct
                FROM signal_outcomes
                WHERE complete = 1 AND primary_state = ? AND direction = ? AND read_label = ?
                ORDER BY started_ts DESC LIMIT 500
                """,
                (state, direction, read_label),
            ).fetchall()
            if len(rows) < 5:
                rows = conn.execute(
                    """
                    SELECT outcome, max_favorable_pct, max_adverse_pct
                    FROM signal_outcomes
                    WHERE complete = 1 AND primary_state = ? AND direction = ?
                    ORDER BY started_ts DESC LIMIT 500
                    """,
                    (state, direction),
                ).fetchall()
        finally:
            conn.close()

        sample_size = len(rows)
        wins = sum(1 for row in rows if row["outcome"] == "followed_through")
        favorable = [float(row["max_favorable_pct"] or 0) for row in rows]
        adverse = [float(row["max_adverse_pct"] or 0) for row in rows]
        result = {
            "sample_size": sample_size,
            "follow_through_rate": (wins / sample_size) if sample_size else None,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "median_favorable_pct": round(median(favorable), 3) if favorable else None,
            "median_adverse_pct": round(median(adverse), 3) if adverse else None,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "rule": "target_before_adverse_within_horizon",
        }
        with self._history_lock:
            self._history_cache[cache_key] = (time.monotonic(), dict(result))
        return result

    def status(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            total = int(
                conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0]
            )
            complete = int(
                conn.execute(
                    "SELECT COUNT(*) FROM signal_outcomes WHERE complete = 1"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        return {
            "total": total,
            "complete": complete,
            "collecting": total - complete,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
        }

    @staticmethod
    def _med(entries: list[dict[str, Any]], col: str) -> float | None:
        vals = [float(e[col]) for e in entries if e[col] is not None]
        return round(median(vals), 3) if vals else None

    @staticmethod
    def _build_signal_card(
        state: str, direction: str, label: str, entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        n = len(entries)
        wins = sum(1 for e in entries if e["outcome"] == "followed_through")
        recent = entries[:50]
        recent_n = len(recent)
        recent_wins = sum(1 for e in recent if e["outcome"] == "followed_through")
        med = SignalOutcomeStore._med
        return {
            "state": state,
            "direction": direction,
            "label": label,
            "sample_size": n,
            "win_rate": round(wins / n, 4),
            "recent_win_rate": round(recent_wins / recent_n, 4) if recent_n else None,
            "recent_sample": recent_n,
            "median_favorable_pct": med(entries, "max_favorable_pct"),
            "median_adverse_pct": med(entries, "max_adverse_pct"),
            "median_return": {
                "5m": med(entries, "return_5m"),
                "15m": med(entries, "return_15m"),
                "30m": med(entries, "return_30m"),
                "60m": med(entries, "return_60m"),
            },
            "oldest_ts": min((e["started_ts"] for e in entries), default=None),
            "newest_ts": max((e["started_ts"] for e in entries), default=None),
        }

    @staticmethod
    def _cards_from_rows(rows: list[Any], min_samples: int) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for row in rows:
            key = (row["primary_state"], row["direction"], row["read_label"])
            groups.setdefault(key, []).append(dict(row))
        cards = [
            SignalOutcomeStore._build_signal_card(state, direction, label, entries)
            for (state, direction, label), entries in groups.items()
            if len(entries) >= min_samples
        ]
        cards.sort(key=lambda c: c["sample_size"], reverse=True)
        return cards

    def scorecard(self, *, min_samples: int = 5) -> dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT primary_state, direction, read_label, outcome,
                       return_5m, return_15m, return_30m, return_60m,
                       max_favorable_pct, max_adverse_pct, started_ts
                FROM signal_outcomes
                WHERE complete = 1
                ORDER BY started_ts DESC
                """
            ).fetchall()
        finally:
            conn.close()

        total = len(rows)
        total_wins = sum(1 for r in rows if r["outcome"] == "followed_through")

        return {
            "total_graded": total,
            "overall_win_rate": round(total_wins / total, 4) if total else None,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "signal_types": self._cards_from_rows(rows, min_samples),
        }

    def coin_scorecard(
        self, product_id: str, *, min_samples: int = 5
    ) -> dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT primary_state, direction, read_label, outcome,
                       return_5m, return_15m, return_30m, return_60m,
                       max_favorable_pct, max_adverse_pct, started_ts
                FROM signal_outcomes
                WHERE complete = 1 AND product_id = ?
                ORDER BY started_ts DESC
                """,
                (product_id,),
            ).fetchall()
        finally:
            conn.close()

        return {
            "product_id": product_id,
            "total_outcomes": len(rows),
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "signal_types": self._cards_from_rows(rows, min_samples),
        }


store = SignalOutcomeStore()
