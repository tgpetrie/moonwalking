"""What outcome trackers do when collection had a gap.

The signal and board trackers grade each row by reading the price at fixed
marks (5, 15, 30, 60 minutes) on their next observe() call. If the backend
was stopped or the PC slept, that next call can come hours or days later,
and the tracker used to record the price at that moment as the "15-minute
return" and finish the row. Every stop between 2026-09-06 and 2026-10-12 did
this to the rows open at the time.

The rules now:

- A checkpoint is recorded only on time: within ``MW_OUTCOME_GAP_SECONDS``
  (default 300) of its mark. A missed checkpoint stays NULL for good.
- A row that was still inside its horizon when tracking went quiet for longer
  than that is finished as ``interrupted``. Stats never count it as a win, a
  loss, or noise; it's evidence that wasn't collected.

Normal tracking lag is far below the threshold: across 15,686 completed
signal rows the median lag past the 60-minute mark was 10s, the worst 140s.
"""

from __future__ import annotations

import os
import sqlite3

INTERRUPTED = "interrupted"

HEARTBEAT_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS tracker_heartbeat ("
    "tracker TEXT PRIMARY KEY, ts INTEGER NOT NULL)"
)


def gap_seconds() -> int:
    return max(60, int(os.getenv("MW_OUTCOME_GAP_SECONDS", "300")))


class GapDetector:
    """Remembers when a tracker last ran, across restarts, and reports the
    start of a gap when the silence since then is longer than ``seconds``."""

    def __init__(self, tracker: str, seconds: int | None = None):
        self.tracker = tracker
        self.seconds = gap_seconds() if seconds is None else seconds
        self._last: int | None = None

    def gap_start(
        self, conn: sqlite3.Connection, now_ts: int, fallback_sql: str
    ) -> int | None:
        """Call before the tracker writes anything this cycle.

        ``fallback_sql`` returns the tracker's latest activity time from its
        own rows, for stores written before the heartbeat existed."""
        last = self._last
        if last is None:
            row = conn.execute(
                "SELECT ts FROM tracker_heartbeat WHERE tracker = ?", (self.tracker,)
            ).fetchone()
            if row is None:
                row = conn.execute(fallback_sql).fetchone()
            last = row[0] if row and row[0] is not None else None
        if last is not None and now_ts - int(last) > self.seconds:
            return int(last)
        return None

    def beat(self, conn: sqlite3.Connection, now_ts: int) -> None:
        """Call in the same transaction as the tracker's updates."""
        conn.execute(
            "INSERT OR REPLACE INTO tracker_heartbeat (tracker, ts) VALUES (?, ?)",
            (self.tracker, int(now_ts)),
        )
        self._last = int(now_ts)


def open_across_gap(start_ts: int, horizon_seconds: int, gap_start: int | None) -> bool:
    """True if a row started before the gap and its horizon hadn't ended."""
    return gap_start is not None and start_ts < gap_start < start_ts + horizon_seconds
