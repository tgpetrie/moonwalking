import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(
    os.environ.get("MW_VOLUME_1H_DB")
    or Path(__file__).resolve().parent / "data" / "volume_1h.sqlite"
)


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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS volume_hour (
              product_id TEXT NOT NULL,
              hour_ts INTEGER NOT NULL,
              base_volume REAL NOT NULL,
              quote_volume_usd REAL NULL,
              minute_coverage INTEGER NOT NULL,
              open REAL NULL,
              high REAL NULL,
              low REAL NULL,
              close REAL NULL,
              source TEXT NOT NULL DEFAULT 'coinbase_minute_rollup',
              PRIMARY KEY (product_id, hour_ts)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def floor_minute(ts: int) -> int:
    return int(ts // 60 * 60)


def upsert_minute(
    product_id: str, minute_ts: int, vol_base: float, close: Optional[float] = None
):
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
            (
                product_id,
                int(minute_ts),
                float(vol_base),
                close if close is not None else None,
            ),
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


def upsert_hour(
    product_id: str,
    hour_ts: int,
    *,
    base_volume: float,
    quote_volume_usd: Optional[float],
    minute_coverage: int,
    open_price: Optional[float],
    high_price: Optional[float],
    low_price: Optional[float],
    close_price: Optional[float],
    source: str = "coinbase_minute_rollup",
):
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO volume_hour (
              product_id, hour_ts, base_volume, quote_volume_usd,
              minute_coverage, open, high, low, close, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, hour_ts) DO UPDATE SET
              base_volume=excluded.base_volume,
              quote_volume_usd=excluded.quote_volume_usd,
              minute_coverage=excluded.minute_coverage,
              open=excluded.open,
              high=excluded.high,
              low=excluded.low,
              close=excluded.close,
              source=excluded.source
            """,
            (
                product_id,
                int(hour_ts),
                float(base_volume),
                float(quote_volume_usd) if quote_volume_usd is not None else None,
                int(minute_coverage),
                open_price,
                high_price,
                low_price,
                close_price,
                str(source),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def rollup_product_hours(product_id: str, start_ts: int, end_ts: int) -> int:
    rows = fetch_window(product_id, int(start_ts), int(end_ts))
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        minute_ts = row.get("minute_ts")
        if minute_ts is None:
            continue
        hour_ts = int(minute_ts) // 3600 * 3600
        grouped.setdefault(hour_ts, []).append(row)

    written = 0
    for hour_ts, hour_rows in grouped.items():
        ordered = sorted(hour_rows, key=lambda row: int(row.get("minute_ts") or 0))
        closes = [
            float(row["close"])
            for row in ordered
            if row.get("close") is not None and float(row["close"]) > 0
        ]
        base_volume = sum(float(row.get("vol_base") or 0.0) for row in ordered)
        quote_values = [
            float(row.get("vol_base") or 0.0) * float(row.get("close"))
            for row in ordered
            if row.get("close") is not None and float(row.get("close")) > 0
        ]
        upsert_hour(
            product_id,
            hour_ts,
            base_volume=base_volume,
            quote_volume_usd=sum(quote_values) if quote_values else None,
            minute_coverage=len({int(row.get("minute_ts")) for row in ordered}),
            open_price=closes[0] if closes else None,
            high_price=max(closes) if closes else None,
            low_price=min(closes) if closes else None,
            close_price=closes[-1] if closes else None,
        )
        written += 1
    return written


def fetch_hours(product_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT product_id, hour_ts, base_volume, quote_volume_usd,
                   minute_coverage, open, high, low, close, source
            FROM volume_hour
            WHERE product_id = ? AND hour_ts >= ? AND hour_ts <= ?
            ORDER BY hour_ts ASC
            """,
            (product_id, int(start_ts), int(end_ts)),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def latest_quote_volume_by_product(
    now_ts: int,
    *,
    min_coverage: int = 50,
    max_age_seconds: int = 7200,
) -> Dict[str, Dict[str, Any]]:
    """Most recent qualifying hourly quote volume for every product, in one pass.

    This is the quantitative liquidity candidate. It is deliberately separate
    from the categorical ``thin/normal/wide`` bucket: the two have very
    different universe coverage, and which one can actually be used is a
    measured question, not an assumption.

    Only rows meeting ``min_coverage`` count — a partially-sampled hour
    understates volume, and an understated denominator would silently bias any
    liquidity matching built on it.
    """
    cutoff = int(now_ts) - int(max_age_seconds)
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT product_id, hour_ts, quote_volume_usd, base_volume, minute_coverage
            FROM volume_hour
            WHERE hour_ts >= ? AND hour_ts <= ?
              AND minute_coverage >= ?
              AND quote_volume_usd IS NOT NULL
            ORDER BY product_id, hour_ts ASC
            """,
            (cutoff, int(now_ts), int(min_coverage)),
        ).fetchall()
        # Ascending hour_ts means the last row per product wins.
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            out[str(row["product_id"])] = {
                "quote_volume_usd": float(row["quote_volume_usd"]),
                "base_volume": float(row["base_volume"] or 0),
                "minute_coverage": int(row["minute_coverage"]),
                "hour_ts": int(row["hour_ts"]),
                "age_seconds": int(now_ts) - int(row["hour_ts"]),
            }
        return out
    finally:
        conn.close()


def prune_hourly_older_than(cutoff_ts: int):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM volume_hour WHERE hour_ts < ?", (int(cutoff_ts),))
        conn.commit()
    finally:
        conn.close()
