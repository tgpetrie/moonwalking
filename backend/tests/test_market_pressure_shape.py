from __future__ import annotations

try:
    from alerts_engine import AlertEngineState, compute_market_pressure
except Exception:  # pragma: no cover - fallback import path
    from backend.alerts_engine import AlertEngineState, compute_market_pressure


def _price_snapshot_hot() -> dict[str, dict]:
    return {
        "BTC-USD": {"price": 50000.0, "pct_1m": 1.8, "pct_3m": 3.2, "pct_1h": 4.5},
        "ETH-USD": {"price": 3200.0, "pct_1m": 1.2, "pct_3m": 2.4, "pct_1h": 3.1},
        "SOL-USD": {"price": 180.0, "pct_1m": 1.6, "pct_3m": 2.9, "pct_1h": 5.0},
        "LINK-USD": {"price": 20.0, "pct_1m": 0.9, "pct_3m": 1.7, "pct_1h": 2.2},
    }


def _price_snapshot_cold() -> dict[str, dict]:
    return {
        "BTC-USD": {"price": 50000.0, "pct_1m": -1.5, "pct_3m": -2.8, "pct_1h": -4.0},
        "ETH-USD": {"price": 3200.0, "pct_1m": -1.0, "pct_3m": -2.1, "pct_1h": -3.0},
        "SOL-USD": {"price": 180.0, "pct_1m": -1.9, "pct_3m": -3.1, "pct_1h": -4.9},
        "LINK-USD": {"price": 20.0, "pct_1m": -0.7, "pct_3m": -1.2, "pct_1h": -2.0},
    }


def _volume_snapshot_hot() -> dict[str, dict]:
    return {
        "BTC-USD": {
            "volume_1h_now": 5200.0,
            "volume_1h_prev": 1200.0,
            "volume_change_1h_pct": 333.3,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 3900.0,
            "volume_1h_prev": 1100.0,
            "volume_change_1h_pct": 254.5,
            "baseline_ready": True,
        },
        "SOL-USD": {
            "volume_1h_now": 2100.0,
            "volume_1h_prev": 700.0,
            "volume_change_1h_pct": 200.0,
            "baseline_ready": True,
        },
        "LINK-USD": {
            "volume_1h_now": 1200.0,
            "volume_1h_prev": 500.0,
            "volume_change_1h_pct": 140.0,
            "baseline_ready": True,
        },
    }


def _volume_snapshot_cold() -> dict[str, dict]:
    return {
        "BTC-USD": {
            "volume_1h_now": 1000.0,
            "volume_1h_prev": 1800.0,
            "volume_change_1h_pct": -44.4,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 900.0,
            "volume_1h_prev": 1700.0,
            "volume_change_1h_pct": -47.1,
            "baseline_ready": True,
        },
        "SOL-USD": {
            "volume_1h_now": 500.0,
            "volume_1h_prev": 1200.0,
            "volume_change_1h_pct": -58.3,
            "baseline_ready": True,
        },
        "LINK-USD": {
            "volume_1h_now": 300.0,
            "volume_1h_prev": 900.0,
            "volume_change_1h_pct": -66.7,
            "baseline_ready": True,
        },
    }


def test_market_pressure_returns_canonical_shape():
    pressure = compute_market_pressure(
        price_snapshot=_price_snapshot_hot(),
        volume_snapshot=_volume_snapshot_hot(),
        state=AlertEngineState(),
    )

    assert isinstance(pressure.index, int)
    assert 0 <= pressure.index <= 100
    assert 0.0 <= pressure.score01 <= 1.0
    assert isinstance(pressure.ts, int) and pressure.ts > 0
    assert pressure.label in {"Fear", "Cautious", "Neutral", "Risk-On", "Euphoria"}

    assert isinstance(pressure.components, dict)
    for key in (
        "breadth",
        "impulse_density",
        "volume_anomaly",
        "vol_regime",
        "persistence",
    ):
        assert key in pressure.components
        assert 0.0 <= float(pressure.components[key]) <= 1.0

    # Backward-compatible aliases still available.
    assert 0.0 <= pressure.heat <= 100.0
    assert pressure.bias in {"up", "down", "neutral"}
    assert 0.0 <= pressure.breadth_up <= 1.0
    assert 0.0 <= pressure.breadth_down <= 1.0


def test_market_pressure_ema_smoothing_uses_state():
    shared_state = AlertEngineState()
    _ = compute_market_pressure(
        price_snapshot=_price_snapshot_hot(),
        volume_snapshot=_volume_snapshot_hot(),
        state=shared_state,
    )

    cold_smoothed = compute_market_pressure(
        price_snapshot=_price_snapshot_cold(),
        volume_snapshot=_volume_snapshot_cold(),
        state=shared_state,
    )
    cold_fresh = compute_market_pressure(
        price_snapshot=_price_snapshot_cold(),
        volume_snapshot=_volume_snapshot_cold(),
        state=AlertEngineState(),
    )

    # EMA should retain some prior momentum vs a fresh cold-only compute.
    assert cold_smoothed.score01 > cold_fresh.score01
