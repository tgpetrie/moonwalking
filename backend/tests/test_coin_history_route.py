from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app
import signal_outcomes as so_module


def _make_temp_store(tmp_path):
    store = so_module.SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    return store


def _insert_row(store, product_id, state, direction, label, n_wins, n_losses):
    conn = store._connect()
    try:
        for i in range(n_wins + n_losses):
            outcome = "followed_through" if i < n_wins else "did_not_follow_through"
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, event_id, product_id, primary_state, read_label,
                    direction, confidence, started_ts, start_price, last_ts, last_price,
                    max_favorable_pct, max_adverse_pct, outcome, complete
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    f"{product_id}-{state}-{i}",
                    f"evt-{i}",
                    product_id,
                    state,
                    label,
                    direction,
                    80,
                    1700000000 + i * 60,
                    50000.0,
                    1700000000 + i * 60 + 3600,
                    50000.0,
                    2.5 if outcome == "followed_through" else 0.3,
                    -0.5 if outcome == "followed_through" else -2.0,
                    outcome,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_coin_history_route_returns_live_status(tmp_path, monkeypatch):
    store = _make_temp_store(tmp_path)
    _insert_row(store, "BTC-USD", "Confirmed", "up", "STRONG_BUY", 10, 5)
    monkeypatch.setattr(backend_app, "signal_outcome_store", store)

    client = backend_app.app.test_client()
    resp = client.get("/api/coin-history/BTC-USD")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "live"
    assert data["product_id"] == "BTC-USD"
    assert data["total_outcomes"] == 15


def test_coin_history_route_normalizes_bare_symbol(tmp_path, monkeypatch):
    store = _make_temp_store(tmp_path)
    _insert_row(store, "ETH-USD", "Confirmed", "up", "STRONG_BUY", 10, 5)
    monkeypatch.setattr(backend_app, "signal_outcome_store", store)

    client = backend_app.app.test_client()
    resp = client.get("/api/coin-history/ETH")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["product_id"] == "ETH-USD"
    assert data["total_outcomes"] == 15


def test_coin_history_route_no_history(tmp_path, monkeypatch):
    store = _make_temp_store(tmp_path)
    monkeypatch.setattr(backend_app, "signal_outcome_store", store)

    client = backend_app.app.test_client()
    resp = client.get("/api/coin-history/UNKNOWN")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "live"
    assert data["total_outcomes"] == 0
    assert data["signal_types"] == []


def test_coin_history_route_degraded_on_exception(monkeypatch):
    def boom(product_id, **kwargs):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(backend_app.signal_outcome_store, "coin_scorecard", boom)

    client = backend_app.app.test_client()
    resp = client.get("/api/coin-history/BTC")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "degraded"
    assert "error" in data
