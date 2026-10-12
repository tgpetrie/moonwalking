import sqlite3

import pytest

try:
    import candle_archive
except Exception:  # pragma: no cover
    from backend import candle_archive


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Serves 1-minute candles for every minute in the requested range,
    except minutes listed in ``silent`` (no trades)."""

    def __init__(self, statuses=None, silent=()):
        self.calls = []
        self.statuses = list(statuses or [])
        self.silent = set(silent)

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if self.statuses:
            status = self.statuses.pop(0)
            if status != 200:
                return FakeResponse(status)
        start = candle_archive_ts(params["start"])
        end = candle_archive_ts(params["end"])
        g = params["granularity"]
        rows = [
            [t, 1.0, 3.0, 2.0, 2.5, 10.0]  # time, low, high, open, close, volume
            for t in range(start, end + 1, g)
            if t not in self.silent
        ]
        return FakeResponse(200, list(reversed(rows)))  # Coinbase is newest-first


def candle_archive_ts(iso):
    import calendar
    import time

    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))


class NoWait(candle_archive.Pacer):
    def wait(self):
        pass

    def backoff(self):
        self._interval *= 2
        return self._interval


@pytest.fixture
def conn(tmp_path):
    c = candle_archive.connect(str(tmp_path / "archive.sqlite"))
    yield c
    c.close()


def test_windows_are_contiguous_300_candles_on_a_fixed_grid():
    ws = list(candle_archive.windows(0, 1000 * 60, 60))
    assert ws[0][0] == 0
    assert all((end - start) // 60 + 1 == 300 for start, end in ws)
    assert all(b[0] == a[1] + 60 for a, b in zip(ws, ws[1:]))
    assert ws[-1][0] <= 1000 * 60 <= ws[-1][1]
    # A range starting mid-window asks for the same grid windows.
    assert list(candle_archive.windows(450 * 60, 1000 * 60, 60)) == ws[1:]


def test_window_still_open_is_stored_but_fetched_again_next_run(conn):
    candle_archive.run(
        conn, ["BTC-USD"], 60, 0, 299 * 60, session=FakeSession(), pacer=NoWait(), now_ts=100 * 60
    )
    assert conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 300
    assert conn.execute("SELECT COUNT(*) FROM fetched_windows").fetchone()[0] == 0
    later = FakeSession()
    candle_archive.run(conn, ["BTC-USD"], 60, 0, 299 * 60, session=later, pacer=NoWait(), now_ts=400 * 60)
    assert len(later.calls) == 1
    assert conn.execute("SELECT COUNT(*) FROM fetched_windows").fetchone()[0] == 1


def test_archives_candles_with_coinbase_field_order(conn):
    session = FakeSession()
    stats = candle_archive.run(conn, ["BTC-USD"], 60, 0, 599 * 60, session=session, pacer=NoWait())
    assert stats.requests == 2
    assert stats.candles_written == 600
    o, h, l, c, v = conn.execute(
        "SELECT open, high, low, close, volume FROM candles WHERE ts = 0"
    ).fetchone()
    assert (o, h, l, c, v) == (2.0, 3.0, 1.0, 2.5, 10.0)


def test_rerun_skips_archived_windows(conn):
    candle_archive.run(conn, ["BTC-USD"], 60, 0, 599 * 60, session=FakeSession(), pacer=NoWait())
    again = FakeSession()
    stats = candle_archive.run(conn, ["BTC-USD"], 60, 0, 599 * 60, session=again, pacer=NoWait())
    assert again.calls == []
    assert stats.windows_skipped == 2


def test_minute_without_trades_is_absent_but_window_is_recorded(conn):
    candle_archive.run(conn, ["XYZ-USD"], 60, 0, 299 * 60, session=FakeSession(silent={120}), pacer=NoWait())
    assert conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 299
    window = conn.execute(
        "SELECT candles, status, source, methodology_version FROM fetched_windows"
    ).fetchone()
    assert window == (299, "ok", candle_archive.SOURCE, candle_archive.METHODOLOGY_VERSION)


def test_rate_limit_backs_off_and_retries(conn):
    pacer = NoWait(rate=2.0)
    stats = candle_archive.run(
        conn, ["BTC-USD"], 60, 0, 299 * 60, session=FakeSession(statuses=[429, 200]), pacer=pacer
    )
    assert stats.rate_limited == 1
    assert stats.candles_written == 300


def test_unknown_product_is_recorded_once_and_not_retried(conn):
    session = FakeSession(statuses=[404])
    candle_archive.run(conn, ["GONE-USD"], 60, 0, 900 * 60, session=session, pacer=NoWait())
    assert len(session.calls) == 1
    assert conn.execute("SELECT status FROM fetched_windows").fetchone()[0] == "not_found"


def test_archive_records_its_own_label(conn):
    meta = dict(conn.execute("SELECT key, value FROM archive_meta"))
    assert meta["methodology_version"] == candle_archive.METHODOLOGY_VERSION
    assert "Not live collection" in meta["purpose"]


def test_collection_gaps_from_board_outcomes(tmp_path):
    db = tmp_path / "outcomes.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE board_outcomes_v2 (entered_ts INTEGER)")
    c.executemany("INSERT INTO board_outcomes_v2 VALUES (?)", [(t,) for t in (0, 600, 1200, 9000, 9600)])
    c.commit()
    c.close()
    assert candle_archive.collection_gaps(str(db)) == [(1200, 9000)]
