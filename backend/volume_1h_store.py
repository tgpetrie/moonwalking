import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "data" / "volume_1h.sqlite"


def _get_conn():
    # Ensure parent dir exists before connecting
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS volume_minute (
              product_id TEXT NOT NULL,
              minute_ts INTEGER NOT NULL,
              vol_base REAL NOT NULL,
              close REAL NULL,
              PRIMARY KEY (product_id, minute_ts)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def floor_minute(ts: int) -> int:
    return int(ts // 60 * 60)


def upsert_minute(product_id: str, minute_ts: int, vol_base: float, close: Optional[float] = None):
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO volume_minute (product_id, minute_ts, vol_base, close)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(product_id, minute_ts) DO UPDATE SET
              vol_base=excluded.vol_base,
              close=excluded.close
            """,
            (product_id, int(minute_ts), float(vol_base), close if close is not None else None),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_window(product_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT product_id, minute_ts, vol_base, close
            FROM volume_minute
            WHERE product_id = ?
              AND minute_ts >= ?
              AND minute_ts <= ?
            ORDER BY minute_ts ASC
            """,
            (product_id, int(start_ts), int(end_ts)),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def prune_older_than(cutoff_ts: int):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM volume_minute WHERE minute_ts < ?", (int(cutoff_ts),))
        conn.commit()
    finally:
        conn.close()
