"""The candle volume refresh must never block the price loop or cache readers."""

from pathlib import Path
import sys
import threading

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest

try:
    import app as backend_app
except Exception:  # pragma: no cover - fallback import path
    from backend import app as backend_app


VOLUME = (120.0, 60.0, 100.0, 2400.0, 1200.0, 100.0, "full", 60)


@pytest.fixture
def fresh_cache(monkeypatch):
    cache = {}
    monkeypatch.setattr(backend_app, "_CANDLE_VOLUME_CACHE", cache)
    monkeypatch.setattr(backend_app, "_CANDLE_REFRESH_INFLIGHT", set())
    monkeypatch.setattr(backend_app, "_CANDLE_REFRESH_THREAD", None)
    return cache


def test_candle_requests_run_without_holding_the_cache_lock(monkeypatch, fresh_cache):
    lock_free_during_fetch = []

    def fake_compute(product_id):
        # A reader such as the snapshot loop must be able to take the lock
        # while a candle request is in flight.
        acquired = backend_app._CANDLE_VOLUME_CACHE_LOCK.acquire(blocking=False)
        lock_free_during_fetch.append(acquired)
        if acquired:
            backend_app._CANDLE_VOLUME_CACHE_LOCK.release()
        return VOLUME

    monkeypatch.setattr(backend_app, "_compute_1h_volume_from_candles", fake_compute)

    backend_app._update_candle_volume_cache(["SOL-USD", "INJ-USD", "SOL-USD"])

    assert lock_free_during_fetch == [True, True]
    assert set(fresh_cache) == {"SOL-USD", "INJ-USD"}
    assert fresh_cache["SOL-USD"]["quote_vol1h"] == 2400.0
    assert fresh_cache["SOL-USD"]["last_error"] is None
    assert backend_app._CANDLE_REFRESH_INFLIGHT == set()


def test_recent_and_in_flight_products_are_skipped(monkeypatch, fresh_cache):
    fetched = []
    monkeypatch.setattr(
        backend_app,
        "_compute_1h_volume_from_candles",
        lambda product_id: fetched.append(product_id) or VOLUME,
    )
    fresh_cache["SOL-USD"] = {"ts_computed": backend_app.time.time(), "vol1h": 1.0}
    backend_app._CANDLE_REFRESH_INFLIGHT.add("INJ-USD")

    backend_app._update_candle_volume_cache(["SOL-USD", "INJ-USD", "TIA-USD"])

    assert fetched == ["TIA-USD"]
    # Another caller still owns INJ-USD, so it stays claimed.
    assert backend_app._CANDLE_REFRESH_INFLIGHT == {"INJ-USD"}


def test_failed_fetch_keeps_last_good_volume(monkeypatch, fresh_cache):
    def boom(product_id):
        raise TimeoutError("slow network")

    monkeypatch.setattr(backend_app, "_compute_1h_volume_from_candles", boom)
    fresh_cache["SOL-USD"] = {"ts_computed": 0, "vol1h": 5.0, "last_error": None}

    backend_app._update_candle_volume_cache(["SOL-USD"])

    assert fresh_cache["SOL-USD"]["vol1h"] == 5.0
    assert fresh_cache["SOL-USD"]["last_error"] == "fetch_failed"
    assert backend_app._CANDLE_REFRESH_INFLIGHT == set()


def test_price_loop_starts_one_background_refresh_at_a_time(monkeypatch, fresh_cache):
    release = threading.Event()
    started = threading.Event()

    def slow_compute(product_id):
        started.set()
        release.wait(timeout=5)
        return VOLUME

    monkeypatch.setattr(backend_app, "_compute_1h_volume_from_candles", slow_compute)

    assert backend_app._start_candle_volume_refresh(["SOL-USD"]) is True
    assert started.wait(timeout=5)
    # The caller is not blocked, and a second refresh does not pile up.
    assert backend_app._start_candle_volume_refresh(["INJ-USD"]) is False

    release.set()
    backend_app._CANDLE_REFRESH_THREAD.join(timeout=5)
    assert "SOL-USD" in fresh_cache
    assert "INJ-USD" not in fresh_cache
    assert backend_app._start_candle_volume_refresh([]) is False
