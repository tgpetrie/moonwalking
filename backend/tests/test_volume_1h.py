import time
from pathlib import Path

import pytest

import backend.volume_1h_store as store
import backend.volume_1h_compute as compute


def _insert_minutes(product_id: str, now_floor: int, minutes: int, prev_val: float, now_val: float):
    start_ts = now_floor - (minutes - 1) * 60
    half = minutes // 2
    for i in range(minutes):
        minute_ts = start_ts + i * 60
        vol = prev_val if i < half else now_val
        store.upsert_minute(product_id, minute_ts, float(vol), close=100.0 + i)


def test_compute_volume_not_ready_when_insufficient_minutes(tmp_path: Path):
    # point compute at a temp sqlite
    tmp_db = tmp_path / "volume_1h.sqlite"
    store.DB_PATH = tmp_db
    store.ensure_db()

    now_floor = store.floor_minute(int(time.time()))
    # insert only 50 minutes (below 110 threshold)
    _insert_minutes("TEST-USD", now_floor, 50, prev_val=100.0, now_val=200.0)

    res = compute.compute_volume_1h("TEST-USD", now_floor)
    assert res is None


def test_compute_volume_ready_and_values(tmp_path: Path):
    tmp_db = tmp_path / "volume_1h.sqlite"
    store.DB_PATH = tmp_db
    store.ensure_db()

    now_floor = store.floor_minute(int(time.time()))
    # insert 120 minutes so compute has enough distinct minutes
    minutes = 120
    # derive the prev_cut and insert values aligned with compute's grouping
    prev_cut = now_floor - 60 * 60
    start_ts = now_floor - (minutes - 1) * 60
    # insert values so minute_ts < prev_cut have prev_val and others now_val
    for i in range(minutes):
        minute_ts = start_ts + i * 60
        vol = 100.0 if minute_ts < prev_cut else 200.0
        store.upsert_minute("READ-USD", minute_ts, float(vol), close=100.0 + i)

    res = compute.compute_volume_1h("READ-USD", now_floor)
    assert isinstance(res, dict)
    # compute's prev window uses `ts < prev_cut` (strict), so derive counts
    prev_cut = now_floor - 60 * 60
    # inserted timestamps run from start_ts .. now_floor inclusive
    start_ts = now_floor - (minutes - 1) * 60
    prev_count = sum(1 for i in range(minutes) if (start_ts + i * 60) < prev_cut)
    now_count = minutes - prev_count
    expected_prev = prev_count * 100.0
    expected_now = now_count * 200.0
    assert pytest.approx(res["volume_1h_prev"], rel=1e-6) == expected_prev
    assert pytest.approx(res["volume_1h_now"], rel=1e-6) == expected_now
    # pct change should match derived values
    if expected_prev > 0:
        expected_pct = ((expected_now - expected_prev) / expected_prev) * 100.0
        assert pytest.approx(res["volume_change_1h_pct"], rel=1e-6) == expected_pct

    # Tripwires: minute_ts should be second-bucketed (multiple of 60) and not in ms
    rows = store.fetch_window("READ-USD", start_ts, now_floor)
    assert rows, "no rows found for tripwire check"
    assert all(int(r.get("minute_ts", 0)) % 60 == 0 for r in rows), "minute_ts not bucket-aligned"
    assert max(int(r.get("minute_ts", 0)) for r in rows) < 10 ** 12, "timestamps look like milliseconds"
