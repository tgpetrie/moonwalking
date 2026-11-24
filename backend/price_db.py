"""Lightweight SQLite-backed price snapshot store.

Stores (ts INTEGER, product_id TEXT, price REAL) with a compound PK and an
index on (product_id, ts). Designed for simple get-at-or-before queries and
periodic pruning. Uses WAL mode for safe concurrent reads/writes.
"""

from __future__ import annotations
import math
import os
import sqlite3
import threading
from statistics import stdev
from typing import List, Tuple, Optional

DB_PATH = os.environ.get(
    "MOONWALKING_PRICE_DB",
    os.path.join(os.path.dirname(__file__), "price_snapshots.db"),
)
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
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    ts INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    PRIMARY KEY(ts, product_id)
                )
            """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS ix_price_snapshots_pid_ts ON price_snapshots(product_id, ts)"
            )
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
        cur.executemany(
            "INSERT OR REPLACE INTO price_snapshots (ts, product_id, price) VALUES (?, ?, ?)",
            [(ts, pid, float(price)) for pid, price in rows],
        )
        conn.commit()
    finally:
        conn.close()


def prune_old(ts_cutoff: int) -> None:
    """Delete rows older than ts_cutoff (exclusive)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM price_snapshots WHERE ts < ?", (int(ts_cutoff),))
        conn.commit()
    finally:
        conn.close()


def realized_volatility_by_product(
    now_ts: int,
    *,
    window_seconds: int = 3600,
    bucket_seconds: int = 60,
    min_observations: int = 45,
    max_gap_buckets: int = 5,
) -> dict:
    """Trailing realized volatility for every product, in one pass.

    Returns ``{product_id: {...}}`` with volatility as **percent per hour**:
    the stdev of consecutive 1-minute log returns scaled by sqrt(buckets/hour).

    Batched deliberately — a per-coin query on each ranking pass would mean
    hundreds of round trips per tick. Entries whose data is too sparse or too
    gappy carry ``volatility_pct_hour = None`` and a ``reason``, so an
    ineligible coin is distinguishable from one that was never seen; a caller
    cannot mistake missing data for low volatility.

    ``staleness_seconds`` is reported rather than applied: the freshness cutoff
    belongs to the caller, which knows the timestamp the decision was dated to.
    """
    start_ts = int(now_ts) - int(window_seconds)
    expected = max(1, int(window_seconds // bucket_seconds))
    conn = _get_conn()
    try:
        cur = conn.cursor()
        # Last price within each bucket = that bucket's close.
        cur.execute(
            """
            SELECT product_id,
                   ts / ? AS bucket,
                   price,
                   ts
            FROM price_snapshots
            WHERE ts > ? AND ts <= ?
            ORDER BY product_id, ts
            """,
            (int(bucket_seconds), start_ts, int(now_ts)),
        )
        closes: dict = {}
        for row in cur.fetchall():
            pid = str(row["product_id"])
            # Rows arrive ts-ascending, so a later row in the same bucket
            # overwrites the earlier one and the close is the last price.
            closes.setdefault(pid, {})[int(row["bucket"])] = (
                float(row["price"]),
                int(row["ts"]),
            )
    finally:
        conn.close()

    # The tape carries both "AAVE" and "AAVE-USD" as separate product_ids, one
    # densely sampled and one nearly empty. Keep the denser series per symbol
    # rather than merging them: two independent sampling series interleaved
    # would manufacture returns between points that were never consecutive.
    by_symbol: dict = {}
    for pid, buckets in closes.items():
        symbol = pid.split("-")[0].upper()
        existing = by_symbol.get(symbol)
        if existing is None or len(buckets) > len(existing[1]):
            by_symbol[symbol] = (pid, buckets)
    closes = {symbol: buckets for symbol, (_, buckets) in by_symbol.items()}

    out: dict = {}
    for pid, buckets in closes.items():
        ordered = sorted(buckets.items())
        observations = len(ordered)
        last_ts = ordered[-1][1][1] if ordered else None
        staleness = (int(now_ts) - last_ts) if last_ts is not None else None
        # Every diagnostic key is present on every branch. A payload whose
        # shape depends on which check failed forces callers to guess, and a
        # missing key reads as "not applicable" rather than "zero".
        base = {
            "observations": observations,
            "expected_observations": expected,
            "staleness_seconds": staleness,
            "volatility_pct_hour": None,
            "reason": None,
            "max_gap_buckets": None,
            "consecutive_returns": 0,
            "skipped_gap_pairs": 0,
        }
        if observations < min_observations:
            base["reason"] = "insufficient_observations"
            out[pid] = base
            continue

        # Only genuinely consecutive buckets contribute a return. A pair three
        # minutes apart is a three-minute return; counting it as a one-minute
        # return and scaling the whole series by sqrt(buckets_per_hour)
        # overstates volatility exactly for the sparsely-sampled coins, which
        # would then be matched against densely-sampled peers as if they were
        # equally volatile.
        widest_gap = 0
        returns = []
        skipped_gaps = 0
        for (prev_bucket, (prev_price, _)), (bucket, (price, _)) in zip(
            ordered, ordered[1:]
        ):
            gap = bucket - prev_bucket
            widest_gap = max(widest_gap, gap)
            if gap != 1:
                skipped_gaps += 1
                continue
            if prev_price > 0 and price > 0:
                returns.append(math.log(price / prev_price))
        base["max_gap_buckets"] = widest_gap
        base["consecutive_returns"] = len(returns)
        base["skipped_gap_pairs"] = skipped_gaps
        if widest_gap > max_gap_buckets:
            base["reason"] = "gap_exceeded"
            out[pid] = base
            continue
        # Requiring most of the window to be consecutive keeps a coin with 45
        # scattered observations from qualifying on a handful of adjacent pairs.
        if len(returns) < max(2, int(min_observations * 0.8)):
            base["reason"] = "insufficient_consecutive_returns"
            out[pid] = base
            continue

        per_bucket = stdev(returns)
        buckets_per_hour = 3600.0 / float(bucket_seconds)
        base["volatility_pct_hour"] = round(
            per_bucket * math.sqrt(buckets_per_hour) * 100.0, 6
        )
        out[pid] = base
    return out


def get_price_at_or_before(
    product_id: str, target_ts: int
) -> Optional[Tuple[int, float]]:
    """Return (ts, price) for the nearest snapshot <= target_ts, or None."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ts, price FROM price_snapshots
            WHERE product_id = ? AND ts <= ?
            ORDER BY ts DESC LIMIT 1
        """,
            (product_id, int(target_ts)),
        )
        row = cur.fetchone()
        if row:
            return int(row["ts"]), float(row["price"])
        return None
    finally:
        conn.close()


def get_price_at_or_after(
    product_id: str, target_ts: int
) -> Optional[Tuple[int, float]]:
    """Return (ts, price) for the nearest snapshot >= target_ts, or None."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ts, price FROM price_snapshots
            WHERE product_id = ? AND ts >= ?
            ORDER BY ts ASC LIMIT 1
        """,
            (product_id, int(target_ts)),
        )
        row = cur.fetchone()
        if row:
            return int(row["ts"]), float(row["price"])
        return None
    finally:
        conn.close()


def get_recent_price_snapshots(
    product_id: str,
    *,
    limit: int = 60,
    since_ts: Optional[int] = None,
) -> List[Tuple[int, float]]:
    """Return recent persisted tape in chronological order.

    The dashboard writes one price snapshot per fetch cycle. Reading this
    history lets coin-scoped views resume immediately after a process restart
    instead of rebuilding their tape only in browser memory.
    """
    safe_limit = max(1, min(int(limit or 60), 500))
    conn = _get_conn()
    try:
        if since_ts is None:
            rows = conn.execute(
                """
                SELECT ts, price FROM price_snapshots
                WHERE product_id = ?
                ORDER BY ts DESC LIMIT ?
                """,
                (str(product_id), safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT ts, price FROM price_snapshots
                WHERE product_id = ? AND ts >= ?
                ORDER BY ts DESC LIMIT ?
                """,
                (str(product_id), int(since_ts), safe_limit),
            ).fetchall()
        return [(int(row["ts"]), float(row["price"])) for row in reversed(rows)]
    finally:
        conn.close()
