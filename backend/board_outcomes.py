"""Persistent outcome measurement for the public mover boards.

An observation begins when a product enters one of the published board cohorts.
The same entry is then measured at 5, 15, 30, and 60 minutes using directional
returns (positive means the displayed move continued, negative means it
reversed).  This module intentionally reports samples and uncertainty instead
of turning a short-horizon mover into trading advice.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from statistics import median
import sqlite3
import threading
import time
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "signal_outcomes.sqlite"
CHECKPOINTS = (
    (300, "return_5m"),
    (900, "return_15m"),
    (1800, "return_30m"),
    (3600, "return_60m"),
)
BOARD_NAMES = ("ignition_1m", "confirmation_3m_up", "confirmation_3m_down")
MODEL_VERSION = "board-outcomes-v2"
TABLE_NAME = "board_outcomes_v2"
_STABLECOINS = {"USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDS", "EURC"}


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    for suffix in ("-USD", "-USDT", "-USDC", "-PERP"):
        if raw.endswith(suffix):
            return raw[: -len(suffix)]
    return raw


def _wilson_interval(
    successes: int, total: int, z: float = 1.96
) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    centre = proportion + (z * z / (2.0 * total))
    margin = z * math.sqrt(
        (proportion * (1.0 - proportion) / total) + (z * z / (4.0 * total * total))
    )
    return (centre - margin) / denominator, (centre + margin) / denominator


class BoardOutcomeStore:
    def __init__(self, db_path: str | Path | None = None):
        configured = os.getenv("MW_BOARD_OUTCOMES_DB") or os.getenv(
            "MW_SIGNAL_OUTCOMES_DB"
        )
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        self.move_threshold_pct = max(
            0.05, float(os.getenv("MW_BOARD_MOVE_THRESHOLD_PCT", "0.5"))
        )
        self.horizon_seconds = max(
            3600, int(os.getenv("MW_BOARD_OUTCOME_HORIZON_SECONDS", "3600"))
        )
        self.visible_limit = max(1, int(os.getenv("MW_BOARD_TRACKED_ROWS", "8")))
        self.cooldown_seconds = max(
            60, int(os.getenv("MW_BOARD_REENTRY_COOLDOWN_SECONDS", "3600"))
        )
        self.round_trip_cost_pct = max(
            0.0, float(os.getenv("MW_BOARD_ROUND_TRIP_COST_PCT", "0.20"))
        )
        self.minimum_samples = max(
            30, int(os.getenv("MW_BOARD_MIN_INDEPENDENT_SAMPLES", "100"))
        )
        self.minimum_span_days = max(1, int(os.getenv("MW_BOARD_MIN_SPAN_DAYS", "14")))
        self._init_lock = threading.Lock()
        self._summary_lock = threading.Lock()
        self._summary_cache: tuple[float, dict[str, Any]] | None = None
        self.ensure_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=8, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=8000")
        return conn

    def ensure_db(self) -> None:
        with self._init_lock:
            conn = self._connect()
            try:
                conn.executescript(
                    f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_version TEXT NOT NULL DEFAULT '{MODEL_VERSION}',
                        board TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entered_ts INTEGER NOT NULL,
                        last_seen_ts INTEGER NOT NULL,
                        exited_ts INTEGER,
                        start_price REAL NOT NULL,
                        entry_rank INTEGER,
                        start_change_pct REAL,
                        control_product_id TEXT,
                        control_start_price REAL,
                        control_change_pct REAL,
                        estimated_cost_pct REAL NOT NULL DEFAULT 0,
                        gross_return_5m REAL,
                        gross_return_15m REAL,
                        gross_return_30m REAL,
                        gross_return_60m REAL,
                        return_5m REAL,
                        return_15m REAL,
                        return_30m REAL,
                        return_60m REAL,
                        control_return_5m REAL,
                        control_return_15m REAL,
                        control_return_30m REAL,
                        control_return_60m REAL,
                        max_favorable_15m REAL NOT NULL DEFAULT 0,
                        max_adverse_15m REAL NOT NULL DEFAULT 0,
                        max_favorable_pct REAL NOT NULL DEFAULT 0,
                        max_adverse_pct REAL NOT NULL DEFAULT 0,
                        outcome_15m TEXT,
                        complete INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(board, product_id, entered_ts)
                    );
                    CREATE INDEX IF NOT EXISTS idx_board_outcomes_v2_history
                        ON {TABLE_NAME}(board, direction, outcome_15m, entered_ts);
                    CREATE INDEX IF NOT EXISTS idx_board_outcomes_v2_collecting
                        ON {TABLE_NAME}(complete, entered_ts);
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_board_outcomes_v2_active
                        ON {TABLE_NAME}(board, product_id)
                        WHERE exited_ts IS NULL;
                    """
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _directional_return(direction: str, start: float, current: float) -> float:
        raw = ((current / start) - 1.0) * 100.0
        return -raw if direction == "down" else raw

    @staticmethod
    def _row_product(row: dict[str, Any]) -> tuple[str, str]:
        product_id = (
            str(row.get("product_id") or row.get("productId") or "").strip().upper()
        )
        symbol = _symbol(row.get("symbol") or row.get("ticker") or product_id)
        if not product_id and symbol:
            product_id = f"{symbol}-USD"
        return product_id, symbol

    @staticmethod
    def _price_from_row(
        row: dict[str, Any], prices: dict[str, Any], product_id: str, symbol: str
    ) -> float | None:
        direct = _number(
            row.get("current_price")
            if row.get("current_price") is not None
            else row.get("price")
        )
        if direct is not None and direct > 0:
            return direct
        for key in (product_id, symbol):
            candidate = prices.get(key)
            if isinstance(candidate, dict):
                candidate = candidate.get("price") or candidate.get("current_price")
            parsed = _number(candidate)
            if parsed is not None and parsed > 0:
                return parsed
        return None

    @staticmethod
    def _current_price(
        prices: dict[str, Any], product_id: str, symbol: str
    ) -> float | None:
        for key in (product_id, symbol):
            candidate = prices.get(key)
            if isinstance(candidate, dict):
                candidate = candidate.get("price") or candidate.get("current_price")
            parsed = _number(candidate)
            if parsed is not None and parsed > 0:
                return parsed
        return None

    @staticmethod
    def _move_from_snapshot(row: dict[str, Any], board: str) -> float | None:
        if not isinstance(row, dict):
            return None
        if board == "ignition_1m":
            keys = ("pct_1m", "change_1m", "price_change_percentage_1min")
        else:
            keys = ("pct_3m", "change_3m", "price_change_percentage_3min")
        for key in keys:
            value = _number(row.get(key))
            if value is not None:
                return value
        return None

    def _select_control(
        self,
        *,
        board: str,
        item: dict[str, Any],
        prices: dict[str, Any],
        excluded_products: set[str],
    ) -> dict[str, Any] | None:
        """Pick the closest same-direction non-board mover as a live control."""
        target_move = _number(item.get("change"))
        direction = str(item.get("direction") or "")
        if target_move is None or not direction:
            return None

        best: tuple[float, str, dict[str, Any]] | None = None
        for raw_key, raw_row in prices.items():
            symbol = _symbol(raw_key)
            if not symbol or symbol in _STABLECOINS or symbol == item.get("symbol"):
                continue
            product_id = str(raw_key or "").strip().upper()
            if "-" not in product_id:
                product_id = f"{symbol}-USD"
            if product_id in excluded_products:
                continue
            row = raw_row if isinstance(raw_row, dict) else {"price": raw_row}
            price = _number(
                row.get("price")
                if row.get("price") is not None
                else row.get("current_price")
            )
            move = self._move_from_snapshot(row, board)
            if price is None or price <= 0 or move is None or move == 0:
                continue
            if (direction == "up" and move <= 0) or (direction == "down" and move >= 0):
                continue
            distance = abs(abs(move) - abs(target_move))
            candidate = {
                "product_id": product_id,
                "symbol": symbol,
                "price": price,
                "change": move,
            }
            ordering = (distance, symbol, candidate)
            if best is None or ordering[:2] < best[:2]:
                best = ordering
        return dict(best[2]) if best else None

    def _cooldown_ready(
        self, conn: sqlite3.Connection, board: str, product_id: str, now_ts: int
    ) -> bool:
        previous = conn.execute(
            f"SELECT exited_ts FROM {TABLE_NAME} WHERE board = ? AND product_id = ? "
            "ORDER BY entered_ts DESC LIMIT 1",
            (board, product_id),
        ).fetchone()
        if previous is None:
            return True
        exited_ts = previous["exited_ts"]
        return (
            exited_ts is not None and (now_ts - int(exited_ts)) >= self.cooldown_seconds
        )

    def _direction_for(self, board: str, row: dict[str, Any]) -> str | None:
        if board == "confirmation_3m_up":
            return "up"
        if board == "confirmation_3m_down":
            return "down"
        change = _number(
            row.get("change_1m")
            if row.get("change_1m") is not None
            else row.get("price_change_percentage_1min")
        )
        if change is None or change == 0:
            return None
        return "up" if change > 0 else "down"

    def _classify_15m(
        self, directional_return: float, favorable: float, adverse: float
    ) -> str:
        threshold = self.move_threshold_pct
        if favorable >= threshold and adverse <= -threshold:
            return "volatile"
        if directional_return >= threshold:
            return "continuation"
        if directional_return <= -threshold:
            return "reversal"
        return "noise"

    def observe(
        self,
        boards: dict[str, list[dict[str, Any]] | None],
        prices: dict[str, Any],
        *,
        now_ts: int | None = None,
    ) -> None:
        """Observe current top-eight board membership and advance open outcomes."""
        now_ts = int(now_ts or time.time())
        prices = prices if isinstance(prices, dict) else {}
        normalized: dict[str, dict[str, dict[str, Any]]] = {}

        for board in BOARD_NAMES:
            rows = boards.get(board)
            if rows is None:
                continue
            current: dict[str, dict[str, Any]] = {}
            for rank, row in enumerate((rows or [])[: self.visible_limit], start=1):
                if not isinstance(row, dict):
                    continue
                product_id, symbol = self._row_product(row)
                direction = self._direction_for(board, row)
                price = self._price_from_row(row, prices, product_id, symbol)
                if not product_id or not symbol or not direction or price is None:
                    continue
                change_key = "change_1m" if board == "ignition_1m" else "change_3m"
                change = _number(row.get(change_key))
                if change is None:
                    change = _number(
                        row.get("price_change_percentage_1min")
                        if board == "ignition_1m"
                        else row.get("price_change_percentage_3min")
                    )
                current[product_id] = {
                    "product_id": product_id,
                    "symbol": symbol,
                    "direction": direction,
                    "price": price,
                    "rank": rank,
                    "change": change,
                }
            normalized[board] = current

        excluded_products = {
            product_id for current in normalized.values() for product_id in current
        }

        conn = self._connect()
        try:
            with conn:
                for board, current in normalized.items():
                    active = {
                        row["product_id"]: row
                        for row in conn.execute(
                            f"SELECT id, product_id FROM {TABLE_NAME} WHERE board = ? AND exited_ts IS NULL",
                            (board,),
                        ).fetchall()
                    }
                    for product_id, row in active.items():
                        if product_id not in current:
                            conn.execute(
                                f"UPDATE {TABLE_NAME} SET exited_ts = ? WHERE id = ?",
                                (now_ts, row["id"]),
                            )
                    for product_id, item in current.items():
                        if product_id in active:
                            conn.execute(
                                f"UPDATE {TABLE_NAME} SET last_seen_ts = ? WHERE id = ?",
                                (now_ts, active[product_id]["id"]),
                            )
                            continue
                        if not self._cooldown_ready(conn, board, product_id, now_ts):
                            continue
                        control = self._select_control(
                            board=board,
                            item=item,
                            prices=prices,
                            excluded_products=excluded_products,
                        )
                        conn.execute(
                            f"""
                            INSERT INTO {TABLE_NAME} (
                                model_version,
                                board, product_id, symbol, direction, entered_ts,
                                last_seen_ts, start_price, entry_rank, start_change_pct,
                                control_product_id, control_start_price, control_change_pct,
                                estimated_cost_pct
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                MODEL_VERSION,
                                board,
                                product_id,
                                item["symbol"],
                                item["direction"],
                                now_ts,
                                now_ts,
                                item["price"],
                                item["rank"],
                                item["change"],
                                control.get("product_id") if control else None,
                                control.get("price") if control else None,
                                control.get("change") if control else None,
                                self.round_trip_cost_pct,
                            ),
                        )

                collecting = conn.execute(
                    f"SELECT * FROM {TABLE_NAME} WHERE complete = 0"
                ).fetchall()
                for row in collecting:
                    current = self._current_price(
                        prices, row["product_id"], row["symbol"]
                    )
                    if current is None:
                        continue
                    age = max(0, now_ts - int(row["entered_ts"]))
                    gross_directional = self._directional_return(
                        row["direction"], float(row["start_price"]), current
                    )
                    net_directional = gross_directional - float(
                        row["estimated_cost_pct"] or 0
                    )
                    control_directional = None
                    if row["control_product_id"] and row["control_start_price"]:
                        control_symbol = _symbol(row["control_product_id"])
                        control_current = self._current_price(
                            prices, row["control_product_id"], control_symbol
                        )
                        if control_current is not None:
                            control_directional = self._directional_return(
                                row["direction"],
                                float(row["control_start_price"]),
                                control_current,
                            ) - float(row["estimated_cost_pct"] or 0)
                    favorable = max(
                        float(row["max_favorable_pct"] or 0), gross_directional
                    )
                    adverse = min(float(row["max_adverse_pct"] or 0), gross_directional)
                    favorable_15m = float(row["max_favorable_15m"] or 0)
                    adverse_15m = float(row["max_adverse_15m"] or 0)
                    if age <= 900 or row["return_15m"] is None:
                        favorable_15m = max(favorable_15m, gross_directional)
                        adverse_15m = min(adverse_15m, gross_directional)

                    updates: dict[str, Any] = {
                        "max_favorable_pct": favorable,
                        "max_adverse_pct": adverse,
                        "max_favorable_15m": favorable_15m,
                        "max_adverse_15m": adverse_15m,
                    }
                    for seconds, column in CHECKPOINTS:
                        if age < seconds:
                            continue
                        gross_column = f"gross_{column}"
                        control_column = f"control_{column}"
                        if row[gross_column] is None:
                            updates[gross_column] = gross_directional
                        if row[column] is None:
                            updates[column] = net_directional
                        if (
                            row[control_column] is None
                            and control_directional is not None
                        ):
                            updates[control_column] = control_directional
                    return_15m = updates.get("return_15m", row["return_15m"])
                    if return_15m is not None and row["outcome_15m"] is None:
                        updates["outcome_15m"] = self._classify_15m(
                            float(return_15m), favorable_15m, adverse_15m
                        )
                    if age >= self.horizon_seconds:
                        updates["complete"] = 1

                    assignments = ", ".join(f"{key} = ?" for key in updates)
                    conn.execute(
                        f"UPDATE {TABLE_NAME} SET {assignments} WHERE id = ?",
                        (*updates.values(), row["id"]),
                    )

                retention_days = max(
                    30, int(os.getenv("MW_BOARD_OUTCOME_RETENTION_DAYS", "180"))
                )
                conn.execute(
                    f"DELETE FROM {TABLE_NAME} WHERE complete = 1 AND entered_ts < ?",
                    (now_ts - retention_days * 86400,),
                )
        finally:
            conn.close()
        # Outcome summaries are deliberately allowed to lag the scanner by at
        # most 30 seconds; re-querying thousands of historical rows every
        # eight-second price tick would add work without changing the read.

    def _summary_for(self, conn: sqlite3.Connection, board: str) -> dict[str, Any]:
        rows = conn.execute(
            f"""
            SELECT entered_ts, outcome_15m,
                   gross_return_5m, gross_return_15m, gross_return_30m, gross_return_60m,
                   return_5m, return_15m, return_30m, return_60m,
                   control_return_5m, control_return_15m, control_return_30m, control_return_60m
            FROM {TABLE_NAME}
            WHERE board = ? AND outcome_15m IS NOT NULL
            ORDER BY entered_ts DESC
            LIMIT 5000
            """,
            (board,),
        ).fetchall()
        counts = {name: 0 for name in ("continuation", "reversal", "volatile", "noise")}
        for row in rows:
            name = str(row["outcome_15m"] or "noise")
            counts[name if name in counts else "noise"] += 1
        total = len(rows)
        low, high = _wilson_interval(counts["continuation"], total)
        oldest_ts = min((int(row["entered_ts"]) for row in rows), default=None)
        newest_ts = max((int(row["entered_ts"]) for row in rows), default=None)
        span_seconds = (
            max(0, (newest_ts or 0) - (oldest_ts or 0)) if oldest_ts is not None else 0
        )
        span_days = span_seconds / 86400.0
        adequate = total >= self.minimum_samples and span_days >= self.minimum_span_days

        def median_for(column: str) -> float | None:
            values = [float(row[column]) for row in rows if row[column] is not None]
            return round(median(values), 3) if values else None

        def median_excess_for(column: str) -> float | None:
            control_column = f"control_{column}"
            values = [
                float(row[column]) - float(row[control_column])
                for row in rows
                if row[column] is not None and row[control_column] is not None
            ]
            return round(median(values), 3) if values else None

        matched_rows = [row for row in rows if row["control_return_15m"] is not None]
        control_counts = {name: 0 for name in ("continuation", "reversal", "noise")}
        for row in matched_rows:
            value = float(row["control_return_15m"])
            if value >= self.move_threshold_pct:
                control_counts["continuation"] += 1
            elif value <= -self.move_threshold_pct:
                control_counts["reversal"] += 1
            else:
                control_counts["noise"] += 1
        matched_total = len(matched_rows)
        continuation_rate = counts["continuation"] / total if total else None
        reversal_rate = counts["reversal"] / total if total else None
        control_continuation_rate = (
            control_counts["continuation"] / matched_total if matched_total else None
        )
        control_reversal_rate = (
            control_counts["reversal"] / matched_total if matched_total else None
        )
        continuation_lift = (
            continuation_rate - control_continuation_rate
            if continuation_rate is not None and control_continuation_rate is not None
            else None
        )
        reversal_lift = (
            reversal_rate - control_reversal_rate
            if reversal_rate is not None and control_reversal_rate is not None
            else None
        )
        excess_15m = median_excess_for("return_15m")

        if not adequate:
            read = "Learning"
        elif (
            continuation_lift is not None
            and continuation_lift >= 0.05
            and (excess_15m or 0) > 0
        ):
            read = "Continuation edge"
        elif reversal_lift is not None and reversal_lift >= 0.05:
            read = "Reversal tendency"
        else:
            read = "No clear edge"

        return {
            "board": board,
            "status": "measured" if adequate else "learning",
            "read": read,
            "sample_size": total,
            "matched_sample_size": matched_total,
            "minimum_samples": self.minimum_samples,
            "collection_span_days": round(span_days, 2),
            "minimum_span_days": self.minimum_span_days,
            "threshold_pct": self.move_threshold_pct,
            "estimated_round_trip_cost_pct": self.round_trip_cost_pct,
            "horizon_minutes": 15,
            "continuation_rate": (
                round(continuation_rate, 4) if continuation_rate is not None else None
            ),
            "reversal_rate": (
                round(reversal_rate, 4) if reversal_rate is not None else None
            ),
            "volatile_rate": round(counts["volatile"] / total, 4) if total else None,
            "noise_rate": round(counts["noise"] / total, 4) if total else None,
            "continuation_ci95": (
                [round(low, 4), round(high, 4)]
                if low is not None and high is not None
                else None
            ),
            "control": {
                "method": "nearest same-direction non-board mover",
                "sample_size": matched_total,
                "continuation_rate": (
                    round(control_continuation_rate, 4)
                    if control_continuation_rate is not None
                    else None
                ),
                "reversal_rate": (
                    round(control_reversal_rate, 4)
                    if control_reversal_rate is not None
                    else None
                ),
                "noise_rate": (
                    round(control_counts["noise"] / matched_total, 4)
                    if matched_total
                    else None
                ),
                "counts": control_counts,
            },
            "continuation_lift_vs_control": (
                round(continuation_lift, 4) if continuation_lift is not None else None
            ),
            "reversal_lift_vs_control": (
                round(reversal_lift, 4) if reversal_lift is not None else None
            ),
            "median_directional_return": {
                "5m": median_for("return_5m"),
                "15m": median_for("return_15m"),
                "30m": median_for("return_30m"),
                "60m": median_for("return_60m"),
            },
            "median_gross_directional_return": {
                "5m": median_for("gross_return_5m"),
                "15m": median_for("gross_return_15m"),
                "30m": median_for("gross_return_30m"),
                "60m": median_for("gross_return_60m"),
            },
            "median_excess_return_vs_control": {
                "5m": median_excess_for("return_5m"),
                "15m": excess_15m,
                "30m": median_excess_for("return_30m"),
                "60m": median_excess_for("return_60m"),
            },
            "counts": counts,
        }

    def status(self) -> dict[str, Any]:
        with self._summary_lock:
            if self._summary_cache and (time.monotonic() - self._summary_cache[0]) < 30:
                return dict(self._summary_cache[1])
        conn = self._connect()
        try:
            collecting = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE complete = 0"
                ).fetchone()[0]
            )
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
            )
            boards = {board: self._summary_for(conn, board) for board in BOARD_NAMES}
            legacy_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'board_outcomes'"
            ).fetchone()
            legacy_entries = (
                int(conn.execute("SELECT COUNT(*) FROM board_outcomes").fetchone()[0])
                if legacy_table
                else 0
            )
        finally:
            conn.close()
        result = {
            "model_version": MODEL_VERSION,
            "tracked_rows_per_board": self.visible_limit,
            "total_entries": total,
            "collecting": collecting,
            "legacy_entries_preserved": legacy_entries,
            "observation_policy": {
                "reentry_cooldown_minutes": int(self.cooldown_seconds / 60),
                "control": "nearest same-direction non-board mover",
                "estimated_round_trip_cost_pct": self.round_trip_cost_pct,
                "minimum_independent_samples": self.minimum_samples,
                "minimum_collection_days": self.minimum_span_days,
            },
            "boards": boards,
        }
        with self._summary_lock:
            self._summary_cache = (time.monotonic(), dict(result))
        return result


store = BoardOutcomeStore()


__all__ = ["BoardOutcomeStore", "BOARD_NAMES", "store"]
