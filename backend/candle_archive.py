"""Exchange candle archive for periods the collector did not see.

This is raw Coinbase Exchange market data, not a replay of Moonwalking's own
signals or boards. It lives in its own SQLite file (MW_CANDLE_ARCHIVE_DB) that
no live code path reads, so it can never be mixed silently with live
collection; the file's ``archive_meta`` table and every fetched window record
the source and methodology that produced the rows.

What it is good for: the price and volume tape for any minute, including the
minutes the live stores have already pruned (price snapshots keep 24h, minute
volume 48h). That is what you need to recompute a return checkpoint the live
tracker missed, or to add a matched-peer control to an old signal.

What it cannot restore: anything only the live app saw, such as which alerts
fired, board membership as ranked live, order-book state, or social inputs.

Coinbase returns no candle for a minute with no trades, so an absent minute
inside a fetched window means "no trades", not "missing data". The
``fetched_windows`` table is the record of what was actually fetched.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator

import requests

logger = logging.getLogger(__name__)

SOURCE = "coinbase-exchange-candles"
METHODOLOGY_VERSION = "exchange-candles-v1"
CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
MAX_CANDLES_PER_REQUEST = 300
GRANULARITIES = (60, 300, 900, 3600, 21600, 86400)

SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candles (
    product_id TEXT NOT NULL,
    granularity INTEGER NOT NULL,   -- seconds per candle
    ts INTEGER NOT NULL,            -- candle open time, unix seconds (UTC)
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,           -- base-currency volume
    PRIMARY KEY (product_id, granularity, ts)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS fetched_windows (
    product_id TEXT NOT NULL,
    granularity INTEGER NOT NULL,
    window_start INTEGER NOT NULL,
    window_end INTEGER NOT NULL,
    candles INTEGER NOT NULL,
    status TEXT NOT NULL,           -- ok | not_found
    source TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    fetched_ts INTEGER NOT NULL,
    PRIMARY KEY (product_id, granularity, window_start)
);
CREATE TABLE IF NOT EXISTS archive_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_ts INTEGER NOT NULL,
    finished_ts INTEGER,
    granularity INTEGER NOT NULL,
    range_start INTEGER NOT NULL,
    range_end INTEGER NOT NULL,
    products INTEGER NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    candles_written INTEGER NOT NULL DEFAULT 0,
    windows_skipped INTEGER NOT NULL DEFAULT 0,
    rate_limited INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    note TEXT
);
"""

META = {
    "purpose": (
        "Raw Coinbase Exchange candles for periods the live collector missed. "
        "Not live collection and not a replay of Moonwalking signals."
    ),
    "source": SOURCE,
    "methodology_version": METHODOLOGY_VERSION,
    "absent_minute_means": "no trades in that interval (inside a fetched window)",
}


def default_path() -> str:
    return os.getenv("MW_CANDLE_ARCHIVE_DB") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "candle_archive.sqlite"
    )


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or default_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR REPLACE INTO archive_meta (key, value) VALUES (?, ?)",
        META.items(),
    )
    conn.commit()
    return conn


def windows(start_ts: int, end_ts: int, granularity: int) -> Iterator[tuple[int, int]]:
    """Request windows of 300 candles covering [start_ts, end_ts].

    Windows sit on a fixed grid (multiples of 300 candles since the epoch), so
    runs over overlapping ranges ask for the same windows and a re-run can
    skip what's already archived. Coinbase treats start and end as
    inclusive, so a window is [s, s + 299 * g].
    """
    if granularity not in GRANULARITIES:
        raise ValueError(f"unsupported granularity {granularity}")
    step = MAX_CANDLES_PER_REQUEST * granularity
    s = start_ts - start_ts % step
    while s <= end_ts:
        yield s, s + step - granularity
        s += step


class RateLimited(Exception):
    pass


@dataclass
class Pacer:
    """Keeps requests at or under ``rate`` per second, and halves the rate for
    a while after a 429 so the live collector (same IP, same limit) is never
    the one that gets throttled."""

    rate: float = 2.0
    min_rate: float = 0.25
    _interval: float = field(init=False)
    _next: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._interval = 1.0 / self.rate

    def wait(self) -> None:
        now = time.monotonic()
        if now < self._next:
            time.sleep(self._next - now)
        self._next = max(now, self._next) + self._interval

    def backoff(self) -> float:
        self._interval = min(self._interval * 2, 1.0 / self.min_rate)
        self._next = time.monotonic() + self._interval * 4
        return self._interval

    def recover(self) -> None:
        self._interval = max(1.0 / self.rate, self._interval * 0.95)


def _iso(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def fetch(session, product_id: str, granularity: int, start_ts: int, end_ts: int):
    """One request. Returns candle tuples (ts, open, high, low, close, volume),
    or None if Coinbase doesn't know the product."""
    resp = session.get(
        CANDLES_URL.format(product_id=product_id),
        params={"granularity": granularity, "start": _iso(start_ts), "end": _iso(end_ts)},
        timeout=15,
    )
    if resp.status_code == 429:
        raise RateLimited(product_id)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    rows = []
    for entry in resp.json():
        # Coinbase order: [time, low, high, open, close, volume]
        ts, low, high, open_, close, volume = entry
        ts = int(ts)
        if start_ts <= ts <= end_ts:
            rows.append((ts, float(open_), float(high), float(low), float(close), float(volume)))
    return rows


@dataclass
class RunStats:
    requests: int = 0
    candles_written: int = 0
    windows_skipped: int = 0
    rate_limited: int = 0
    errors: int = 0


def archive_product(
    conn: sqlite3.Connection,
    session,
    pacer: Pacer,
    product_id: str,
    granularity: int,
    start_ts: int,
    end_ts: int,
    stats: RunStats,
    max_attempts: int = 6,
    now_ts: int | None = None,
) -> None:
    """Fetch every window for one product that isn't already archived.
    Re-running is cheap: fetched windows are skipped."""
    done = {
        row[0]
        for row in conn.execute(
            "SELECT window_start FROM fetched_windows WHERE product_id = ? AND granularity = ?",
            (product_id, granularity),
        )
    }
    for w_start, w_end in windows(start_ts, end_ts, granularity):
        if w_start in done:
            stats.windows_skipped += 1
            continue
        for attempt in range(max_attempts):
            pacer.wait()
            stats.requests += 1
            try:
                rows = fetch(session, product_id, granularity, w_start, w_end)
                pacer.recover()
                break
            except RateLimited:
                stats.rate_limited += 1
                interval = pacer.backoff()
                logger.warning("429 on %s; slowing to one request per %.1fs", product_id, interval)
            except (requests.RequestException, ValueError) as exc:
                stats.errors += 1
                logger.warning("fetch failed %s %s: %s", product_id, _iso(w_start), exc)
                time.sleep(min(30, 2 ** attempt))
        else:
            # Leave the window unrecorded so the next run retries it.
            logger.error("giving up on %s window %s for this run", product_id, _iso(w_start))
            continue
        now = int(time.time()) if now_ts is None else now_ts
        status = "not_found" if rows is None else "ok"
        rows = rows or []
        # A window still open (its last candle isn't closed yet) is stored but
        # not marked fetched, so the next run completes it.
        closed = w_end + granularity <= now
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO candles "
                "(product_id, granularity, ts, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(product_id, granularity, *r) for r in rows],
            )
            if closed or status == "not_found":
                conn.execute(
                    "INSERT OR REPLACE INTO fetched_windows "
                    "(product_id, granularity, window_start, window_end, candles, status, "
                    "source, methodology_version, fetched_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (product_id, granularity, w_start, w_end, len(rows), status,
                     SOURCE, METHODOLOGY_VERSION, now),
                )
        stats.candles_written += len(rows)
        if status == "not_found":
            return  # every later window would 404 too


def run(
    conn: sqlite3.Connection,
    products: Iterable[str],
    granularity: int,
    start_ts: int,
    end_ts: int,
    *,
    session=None,
    pacer: Pacer | None = None,
    note: str | None = None,
    progress=None,
    now_ts: int | None = None,
) -> RunStats:
    products = list(products)
    session = session or requests.Session()
    pacer = pacer or Pacer()
    stats = RunStats()
    with conn:
        run_id = conn.execute(
            "INSERT INTO archive_runs (started_ts, granularity, range_start, range_end, products, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(time.time()), granularity, start_ts, end_ts, len(products), note),
        ).lastrowid
    status = "error"
    try:
        for i, product_id in enumerate(products, 1):
            archive_product(
                conn, session, pacer, product_id, granularity, start_ts, end_ts, stats, now_ts=now_ts
            )
            if progress:
                progress(i, len(products), product_id, stats)
            _save_run(conn, run_id, stats, "running")
        status = "ok" if stats.errors == 0 else "ok_with_errors"
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        _save_run(conn, run_id, stats, status, finished=True)
    return stats


def _save_run(conn, run_id, stats: RunStats, status: str, finished: bool = False) -> None:
    with conn:
        conn.execute(
            "UPDATE archive_runs SET requests = ?, candles_written = ?, windows_skipped = ?, "
            "rate_limited = ?, errors = ?, status = ?, finished_ts = ? WHERE id = ?",
            (stats.requests, stats.candles_written, stats.windows_skipped, stats.rate_limited,
             stats.errors, status, int(time.time()) if finished else None, run_id),
        )


def usd_products(session=None) -> list[str]:
    """Every USD-quoted product Coinbase Exchange lists right now."""
    session = session or requests.Session()
    resp = session.get(PRODUCTS_URL, timeout=15)
    resp.raise_for_status()
    return sorted(
        p["id"] for p in resp.json() if str(p.get("quote_currency")).upper() == "USD"
    )


def collection_gaps(
    outcomes_db: str, min_gap_seconds: int = 3600
) -> list[tuple[int, int]]:
    """Periods with no live board activity, from the board outcome store.
    Board entries arrive every few minutes while the collector runs, so a
    silence longer than ``min_gap_seconds`` means it wasn't running."""
    conn = sqlite3.connect(f"file:{outcomes_db}?mode=ro", uri=True)
    try:
        ts = [r[0] for r in conn.execute(
            "SELECT DISTINCT entered_ts FROM board_outcomes_v2 ORDER BY entered_ts")]
    finally:
        conn.close()
    return [(a, b) for a, b in zip(ts, ts[1:]) if b - a > min_gap_seconds]
