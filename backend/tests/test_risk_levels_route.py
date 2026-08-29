from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app
from sell_plan_outcomes import SellPlanOutcomeStore


LEVELS = {
    "support": 95,
    "resistance": 112,
    "atr": 2,
    "band_low": 98,
    "band_high": 102,
    "range_position_pct": 60,
    "range_zone": "mid_range",
    "volatility_pct": 2,
    "momentum_1h_pct": 1,
    "volume_ratio": 1,
    "window_hours": 50,
    "candle_count": 50,
    "source": "coinbase_candles",
}


@pytest.fixture(autouse=True)
def disable_request_background_bootstrap(monkeypatch):
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)


def test_risk_levels_route_returns_plan_and_forward_history(tmp_path, monkeypatch):
    store = SellPlanOutcomeStore(tmp_path / "risk.sqlite")
    monkeypatch.setattr(backend_app, "sell_plan_outcome_store", store)
    monkeypatch.setattr(
        backend_app,
        "last_current_prices",
        {"data": {"BTC-USD": 100}, "timestamp": 1_800_000_000},
    )
    monkeypatch.setattr(
        backend_app,
        "_gather_levels_for_symbols",
        lambda symbols, prices: {"BTC": LEVELS},
    )
    monkeypatch.setattr(
        backend_app,
        "_risk_level_signal_context",
        lambda symbol: {"primary_state": "Building", "direction": "up"},
    )

    response = backend_app.app.test_client().get("/api/risk-levels/BTC")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "live"
    assert data["plan"]["available"] is True
    assert data["plan"]["stop"]["trigger_price"] < LEVELS["support"]
    assert data["plan"]["stop"]["limit_price"] < data["plan"]["stop"]["trigger_price"]
    assert data["history"]["total_plans"] == 1
    assert data["history"]["target_first_rate"] is None


def test_risk_levels_route_refuses_to_invent_levels_while_warming(
    tmp_path, monkeypatch
):
    store = SellPlanOutcomeStore(tmp_path / "risk.sqlite")
    monkeypatch.setattr(backend_app, "sell_plan_outcome_store", store)
    monkeypatch.setattr(
        backend_app,
        "last_current_prices",
        {"data": {"ETH": 50}, "timestamp": 1_800_000_000},
    )
    monkeypatch.setattr(
        backend_app,
        "_gather_levels_for_symbols",
        lambda symbols, prices: {},
    )
    monkeypatch.setattr(backend_app, "_risk_level_signal_context", lambda symbol: {})

    response = backend_app.app.test_client().get("/api/risk-levels/ETH")
    data = response.get_json()

    assert response.status_code == 200
    assert data["plan"]["available"] is False
    assert data["history"]["total_plans"] == 0
