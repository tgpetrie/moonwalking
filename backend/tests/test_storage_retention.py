"""Storage must stay bounded without changing any graded result.

These cover the disk-full failure: the outcome stores only ever grew, and on a
fixed volume that ends with writes failing and collection silently stopping.
The limits only ever remove write-only research JSON or expired observations;
a graded return is never altered.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

# The stores import their siblings by flat name, so make this file runnable
# on its own instead of depending on another test having set the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from board_outcomes import BoardOutcomeStore, TABLE_NAME as BOARD_TABLE
    from control_dry_run import ControlDryRunStore
    from signal_outcomes import SignalOutcomeStore
    import storage_retention as sr
except Exception:  # pragma: no cover
    from backend.board_outcomes import BoardOutcomeStore, TABLE_NAME as BOARD_TABLE  # type: ignore
    from backend.control_dry_run import ControlDryRunStore  # type: ignore
    from backend.signal_outcomes import SignalOutcomeStore  # type: ignore
    import backend.storage_retention as sr  # type: ignore

DAY = 86400
NOW = 1_800_000_000
SNAP = '{"live_score": 50}'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "MW_FEATURE_SNAPSHOT_RETENTION_DAYS",
        "MW_SIGNAL_OUTCOME_RETENTION_DAYS",
        "MW_CONTROL_DRY_RUN_RETENTION_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)


def _signal(store, sid, age_days, *, complete=1, snapshot=SNAP, ret=0.7):
    started = NOW - int(age_days * DAY)
    conn = sqlite3.connect(store.db_path)
    conn.execute(
        "INSERT INTO signal_outcomes (signal_id, event_id, product_id, primary_state,"
        " read_label, direction, confidence, started_ts, start_price, last_ts,"
        " last_price, return_15m, complete, feature_snapshot_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, sid, "BTC-USD", "Building", "X", "up", 50, started, 1.0, started, 1.0,
         ret, complete, snapshot),
    )
    conn.commit()
    conn.close()


def _signal_rows(store):
    conn = sqlite3.connect(store.db_path)
    rows = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT signal_id, feature_snapshot_json, return_15m FROM signal_outcomes"
        )
    }
    conn.close()
    return rows


# -- signal store -----------------------------------------------------------


def test_old_finished_signal_snapshots_are_cleared_but_returns_kept(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _signal(store, "old", 30)
    _signal(store, "recent", 2)
    store.prune_storage(NOW)
    rows = _signal_rows(store)
    assert rows["old"] == (None, 0.7)  # JSON gone, graded return untouched
    assert rows["recent"] == (SNAP, 0.7)


def test_unfinished_signals_are_never_touched(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _signal(store, "open", 30, complete=0)
    store.prune_storage(NOW)
    assert _signal_rows(store)["open"][0] == SNAP


def test_snapshot_limit_can_be_disabled_or_moved(tmp_path, monkeypatch):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _signal(store, "a", 30)
    monkeypatch.setenv("MW_FEATURE_SNAPSHOT_RETENTION_DAYS", "0")
    store.prune_storage(NOW)
    assert _signal_rows(store)["a"][0] == SNAP
    monkeypatch.setenv("MW_FEATURE_SNAPSHOT_RETENTION_DAYS", "60")
    store.prune_storage(NOW)
    assert _signal_rows(store)["a"][0] == SNAP
    monkeypatch.setenv("MW_FEATURE_SNAPSHOT_RETENTION_DAYS", "10")
    store.prune_storage(NOW)
    assert _signal_rows(store)["a"][0] is None


def test_signal_rows_are_only_deleted_when_explicitly_configured(tmp_path, monkeypatch):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _signal(store, "ancient", 200)
    _signal(store, "fresh", 5)
    store.prune_storage(NOW)
    assert set(_signal_rows(store)) == {"ancient", "fresh"}
    monkeypatch.setenv("MW_SIGNAL_OUTCOME_RETENTION_DAYS", "90")
    store.prune_storage(NOW)
    assert set(_signal_rows(store)) == {"fresh"}


def test_row_retention_has_a_30_day_floor(tmp_path, monkeypatch):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _signal(store, "mid", 10)
    monkeypatch.setenv("MW_SIGNAL_OUTCOME_RETENTION_DAYS", "1")
    store.prune_storage(NOW)
    assert "mid" in _signal_rows(store)


def test_pruning_works_in_small_batches(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    for i in range(7):
        _signal(store, f"old{i}", 30)
    conn = sqlite3.connect(store.db_path)
    assert sr.clear_old_feature_snapshots(conn, "signal_outcomes", "started_ts",
                                          NOW - 14 * DAY, batch=3) == 3
    left = conn.execute(
        "SELECT COUNT(*) FROM signal_outcomes WHERE feature_snapshot_json IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert left == 4


# -- board store ------------------------------------------------------------


def _board(store, ts_age_days, *, complete=1, snapshot=SNAP, sym="BTC"):
    entered = NOW - int(ts_age_days * DAY)
    conn = sqlite3.connect(store.db_path)
    conn.execute(
        f"INSERT INTO {BOARD_TABLE} (board, product_id, symbol, direction, entered_ts,"
        " last_seen_ts, exited_ts, start_price, return_15m, complete,"
        " feature_snapshot_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("ignition_1m", f"{sym}-USD", sym, "up", entered, entered, entered, 1.0, 0.4,
         complete, snapshot),
    )
    conn.commit()
    conn.close()


def test_board_snapshots_cleared_after_window_and_returns_kept(tmp_path):
    store = BoardOutcomeStore(tmp_path / "b.sqlite")
    _board(store, 30, sym="OLD")
    _board(store, 1, sym="NEW")
    _board(store, 30, complete=0, sym="OPEN")
    store.prune_storage(NOW)
    conn = sqlite3.connect(store.db_path)
    got = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            f"SELECT symbol, feature_snapshot_json, return_15m FROM {BOARD_TABLE}"
        )
    }
    conn.close()
    assert got["OLD"] == (None, 0.4)
    assert got["NEW"] == (SNAP, 0.4)
    assert got["OPEN"][0] == SNAP


# -- dry-run store ----------------------------------------------------------


def _dry(store, sid, age_days):
    ts = NOW - int(age_days * DAY)
    conn = sqlite3.connect(store.db_path)
    conn.execute(
        "INSERT INTO dry_run_observations (signal_id, observed_ts, config_version,"
        " product_id, has_volatility, has_move, has_quote_volume,"
        " has_categorical_liquidity, universe_size, universe_with_volatility,"
        " universe_with_quote_volume, horizon, rung, basket_size,"
        " basket_met_minimum) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, ts, "v", "BTC-USD", 1, 1, 1, 1, 10, 10, 10, "1m", "omitted", 3, 1),
    )
    conn.commit()
    conn.close()


def _dry_ids(store):
    conn = sqlite3.connect(store.db_path)
    ids = {r[0] for r in conn.execute("SELECT signal_id FROM dry_run_observations")}
    conn.close()
    return ids


def test_dry_run_expires_old_observations(tmp_path):
    store = ControlDryRunStore(tmp_path / "d.sqlite")
    _dry(store, "old", 90)
    _dry(store, "new", 3)
    assert store.expire_old(NOW) == 1
    assert _dry_ids(store) == {"new"}


def test_dry_run_expiry_can_be_disabled(tmp_path, monkeypatch):
    store = ControlDryRunStore(tmp_path / "d.sqlite")
    _dry(store, "old", 90)
    monkeypatch.setenv("MW_CONTROL_DRY_RUN_RETENTION_DAYS", "0")
    assert store.expire_old(NOW) == 0
    assert _dry_ids(store) == {"old"}


def test_new_dry_run_file_returns_freed_pages_but_existing_files_are_unchanged(tmp_path):
    fresh = ControlDryRunStore(tmp_path / "fresh.sqlite")
    conn = sqlite3.connect(fresh.db_path)
    assert conn.execute("PRAGMA auto_vacuum").fetchone()[0] == 2
    conn.close()

    legacy = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE keep (x)")
    conn.commit()
    conn.close()
    ControlDryRunStore(legacy)
    conn = sqlite3.connect(legacy)
    assert conn.execute("PRAGMA auto_vacuum").fetchone()[0] == 0
    conn.close()


def test_throttle_lets_one_job_through_per_interval():
    gate = sr.Throttle(60)
    assert gate.due(1000.0) is True
    assert gate.due(1030.0) is False
    assert gate.due(1061.0) is True


def test_retention_days_parsing(monkeypatch):
    monkeypatch.setenv("X_DAYS", "21")
    assert sr.retention_days("X_DAYS", 14) == 21
    monkeypatch.setenv("X_DAYS", "0")
    assert sr.retention_days("X_DAYS", 14) == 0
    monkeypatch.setenv("X_DAYS", "garbage")
    assert sr.retention_days("X_DAYS", 14) == 14
    monkeypatch.setenv("X_DAYS", "2")
    assert sr.retention_days("X_DAYS", 14, minimum=30) == 30
    monkeypatch.delenv("X_DAYS")
    assert sr.retention_days("X_DAYS", 14) == 14
