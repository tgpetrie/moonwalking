"""Bounded storage for the append-only research stores.

The outcome stores only ever grew. On a fixed-size volume that ends with a full
disk, at which point every write fails and collection silently stops. These
helpers keep growth bounded without discarding anything a published statistic
depends on:

* ``clear_old_feature_snapshots`` blanks the per-row feature JSON of *finished*
  rows after a window. The JSON is write-only research context (nothing in the
  app reads it back); the graded returns and outcomes stay, so every score and
  rate is unchanged.
* ``delete_old_rows`` removes finished rows past a hard age limit. Callers
  decide whether to use it; for the signal store it is off unless configured.

Work is done in small batches on a throttle so a catch-up never holds the
write lock for long. Table and column names are constants supplied by the
calling store, never user input.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time

log = logging.getLogger(__name__)

DEFAULT_PRUNE_INTERVAL_SECONDS = 60
DEFAULT_PRUNE_BATCH = 20000


def retention_days(name: str, default: int, minimum: int = 0) -> int:
    """Days from an environment variable. ``0`` disables the limit."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        days = int(float(str(raw).strip()))
    except ValueError:
        log.warning("%s=%r is not a number; using %s", name, raw, default)
        return default
    if days <= 0:
        return 0
    return max(minimum, days)


class Throttle:
    """Lets a job through at most once per interval, across threads."""

    def __init__(self, interval_seconds: float = DEFAULT_PRUNE_INTERVAL_SECONDS):
        self.interval_seconds = float(interval_seconds)
        self._last = 0.0
        self._lock = threading.Lock()

    def due(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            if current - self._last < self.interval_seconds:
                return False
            self._last = current
            return True


def clear_old_feature_snapshots(
    conn: sqlite3.Connection,
    table: str,
    ts_column: str,
    cutoff_ts: float,
    batch: int = DEFAULT_PRUNE_BATCH,
) -> int:
    """Blank ``feature_snapshot_json`` on finished rows older than the cutoff."""
    cursor = conn.execute(
        f"UPDATE {table} SET feature_snapshot_json = NULL WHERE rowid IN ("
        f"SELECT rowid FROM {table} "
        f"WHERE complete = 1 AND {ts_column} < ? "
        "AND feature_snapshot_json IS NOT NULL LIMIT ?)",
        (cutoff_ts, int(batch)),
    )
    return max(int(cursor.rowcount or 0), 0)


def delete_old_rows(
    conn: sqlite3.Connection,
    table: str,
    ts_column: str,
    cutoff_ts: float,
    batch: int = DEFAULT_PRUNE_BATCH,
    where: str = "complete = 1",
) -> int:
    """Delete up to ``batch`` rows older than the cutoff matching ``where``."""
    cursor = conn.execute(
        f"DELETE FROM {table} WHERE rowid IN ("
        f"SELECT rowid FROM {table} WHERE {where} AND {ts_column} < ? LIMIT ?)",
        (cutoff_ts, int(batch)),
    )
    return max(int(cursor.rowcount or 0), 0)


def enable_incremental_vacuum_if_new(conn: sqlite3.Connection) -> bool:
    """Make a brand-new database return freed pages to the filesystem.

    SQLite only honours ``auto_vacuum`` before the first table exists, so an
    existing file is left exactly as it is. Returns True when it was applied.
    """
    if conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
        return False
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
    return True


def release_free_pages(conn: sqlite3.Connection, pages: int = 2000) -> None:
    """Hand freed pages back to the filesystem, if the database allows it."""
    if int(conn.execute("PRAGMA auto_vacuum").fetchone()[0]) == 2:
        conn.execute(f"PRAGMA incremental_vacuum({int(pages)})").fetchall()
