"""Lightweight SQLite-backed price snapshot store.

Stores (ts INTEGER, product_id TEXT, price REAL) with a compound PK and an
index on (product_id, ts). Designed for simple get-at-or-before queries and
periodic pruning. Uses WAL mode for safe concurrent reads/writes.
"""
from __future__ import annotations
import os
import sqlite3
import threading
from typing import List, Tuple, Optional

DB_PATH = os.environ.get('MOONWALKING_PRICE_DB', os.path.join(os.path.dirname(__file__), 'price_snapshots.db'))
_INIT_LOCK = threading.Lock()


def _get_conn():
    # Use check_same_thread=False so different threads can open connections
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_price_db() -> None:
    with _INIT_LOCK:
        created = False
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute('PRAGMA journal_mode=WAL;')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    ts INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    PRIMARY KEY(ts, product_id)
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS ix_price_snapshots_pid_ts ON price_snapshots(product_id, ts)')
            conn.commit()
            created = True
        finally:
            conn.close()
        return created


def insert_price_snapshot(ts: int, rows: List[Tuple[str, float]]) -> None:
    """Insert a batch of (product_id, price) for timestamp `ts`.

    Rows is a list of (product_id, price).
    """
    if not rows:
        return
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.executemany('INSERT OR REPLACE INTO price_snapshots (ts, product_id, price) VALUES (?, ?, ?)',
                        [(ts, pid, float(price)) for pid, price in rows])
        conn.commit()
    finally:
        conn.close()


def prune_old(ts_cutoff: int) -> None:
    """Delete rows older than ts_cutoff (exclusive)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM price_snapshots WHERE ts < ?', (int(ts_cutoff),))
        conn.commit()
    finally:
        conn.close()


def get_price_at_or_before(product_id: str, target_ts: int) -> Optional[Tuple[int, float]]:
    """Return (ts, price) for the nearest snapshot <= target_ts, or None."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT ts, price FROM price_snapshots
            WHERE product_id = ? AND ts <= ?
            ORDER BY ts DESC LIMIT 1
        ''', (product_id, int(target_ts)))
        row = cur.fetchone()
        if row:
            return int(row['ts']), float(row['price'])
        return None
    finally:
        conn.close()


def get_price_at_or_after(product_id: str, target_ts: int) -> Optional[Tuple[int, float]]:
    """Return (ts, price) for the nearest snapshot >= target_ts, or None."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT ts, price FROM price_snapshots
            WHERE product_id = ? AND ts >= ?
            ORDER BY ts ASC LIMIT 1
        ''', (product_id, int(target_ts)))
        row = cur.fetchone()
        if row:
            return int(row['ts']), float(row['price'])
        return None
    finally:
        conn.close()
