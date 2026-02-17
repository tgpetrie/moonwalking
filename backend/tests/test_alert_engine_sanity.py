from __future__ import annotations

try:
    from alerts_engine import (
        AlertEngineState,
        compute_alerts,
        compute_market_pressure,
        _prune_alerts,
    )
except Exception:  # pragma: no cover - fallback import path
    from backend.alerts_engine import (
        AlertEngineState,
        compute_alerts,
        compute_market_pressure,
        _prune_alerts,
    )


def _mk_alert(symbol: str, typ: str, sev: str, **evidence):
    return {
        "id": f"{typ}-{symbol}",
        "symbol": symbol,
        "type": typ,
        "severity": sev,
        "evidence": evidence or {},
    }


def test_fear_label_correctness_market_mode():
    # Force clear fear regime and allow market alerts.
    price_snapshot = {
        "AAA-USD": {"price": 1.0, "pct_1m": -1.2, "pct_3m": -2.4, "pct_1h": -4.0},
        "BBB-USD": {"price": 2.0, "pct_1m": -1.0, "pct_3m": -2.1, "pct_1h": -3.2},
        "CCC-USD": {"price": 3.0, "pct_1m": -0.8, "pct_3m": -1.8, "pct_1h": -2.8},
    }

    alerts, _state, _pressure = compute_alerts(
        price_snapshot=price_snapshot,
        volume_snapshot={},
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=False,
        include_market_mood=True,
        thresholds={"fear_heat_max": 40},
    )

    market_types = [
        str(a.get("type"))
        for a in alerts
        if str(a.get("symbol") or "").upper() in {"MARKET", "MARKET-USD"}
    ]
    assert "fear_alert" in market_types
    assert "fomo_alert" not in market_types


def test_market_alerts_do_not_leak_when_market_mode_off():
    price_snapshot = {
        "AAA-USD": {"price": 1.0, "pct_1m": 2.1, "pct_3m": 4.0, "pct_1h": 6.1},
    }
    volume_snapshot = {
        "AAA-USD": {
            "volume_1h_now": 5000.0,
            "volume_1h_prev": 900.0,
            "volume_change_1h_pct": 455.5,
            "baseline_ready": True,
        }
    }

    alerts, _state, _pressure = compute_alerts(
        price_snapshot=price_snapshot,
        volume_snapshot=volume_snapshot,
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=False,
        include_market_mood=False,
        thresholds={"fomo_heat_min": 60},
    )

    market_types = [
        str(a.get("type"))
        for a in alerts
        if str(a.get("symbol") or "").upper() in {"MARKET", "MARKET-USD"}
    ]
    assert market_types == []


def test_breadth_intensity_stays_positive_in_red_tape():
    price_snapshot = {
        f"S{i}-USD": {"price": 10 + i, "pct_1m": -0.9, "pct_3m": -1.8, "pct_1h": -2.6}
        for i in range(1, 21)
    }
    pressure = compute_market_pressure(
        price_snapshot=price_snapshot,
        volume_snapshot={},
        state=AlertEngineState(),
    )

    assert float(pressure.components.get("breadth", 0.0)) > 0.0
    assert pressure.bias == "down"
    assert pressure.label in {"Fear", "Cautious"}


def test_prune_is_deterministic_for_same_input():
    alerts = [
        _mk_alert("AAA-USD", "coin_reversal_down", "high", pct_1m=-1.2),
        _mk_alert("AAA-USD", "divergence", "high", magnitude=2.4),
        _mk_alert("AAA-USD", "whale_move", "high", vol_z=4.1),
        _mk_alert("AAA-USD", "breakout", "high", pct=3.0),
        _mk_alert("BBB-USD", "breakout", "high", pct=2.7),
        _mk_alert("CCC-USD", "divergence", "medium", magnitude=1.9),
    ]

    pruned_a = _prune_alerts(list(alerts), max_total=24, max_per_symbol=2)
    pruned_b = _prune_alerts(list(alerts), max_total=24, max_per_symbol=2)

    sig_a = [(a.get("symbol"), a.get("type"), a.get("severity")) for a in pruned_a]
    sig_b = [(a.get("symbol"), a.get("type"), a.get("severity")) for a in pruned_b]
    assert sig_a == sig_b


def test_cross_detector_same_coin_keeps_top_two():
    alerts = [
        _mk_alert("AAA-USD", "divergence", "high", magnitude=3.2),
        _mk_alert("AAA-USD", "breakout", "high", pct=3.1),
        _mk_alert("AAA-USD", "whale_move", "high", vol_z=3.8),
        _mk_alert("AAA-USD", "coin_reversal_down", "high", pct_1m=-1.3),
    ]

    pruned = _prune_alerts(alerts, max_total=24, max_per_symbol=2)
    kept_types = [
        str(a.get("type")) for a in pruned if str(a.get("symbol")) == "AAA-USD"
    ]

    # Hierarchy expectation under equal severity:
    # structure > whale/stealth > impulse > wake-up > divergence
    assert kept_types == ["coin_reversal_down", "whale_move"]


def test_return_history_is_bounded_under_long_run():
    state = AlertEngineState()
    for i in range(500):
        price_snapshot = {
            "AAA-USD": {
                "price": 1.0,
                "pct_1m": 0.4 if i % 2 == 0 else -0.35,
                "pct_3m": 1.2,
                "pct_1h": 2.0,
            }
        }
        volume_snapshot = {
            "AAA-USD": {
                "volume_1h_now": 1000.0,
                "volume_1h_prev": 900.0,
                "volume_change_1h_pct": 11.1,
                "baseline_ready": True,
            }
        }
        compute_alerts(
            price_snapshot=price_snapshot,
            volume_snapshot=volume_snapshot,
            minute_volumes={},
            state=state,
            include_impulse=False,
            include_market_mood=False,
        )

    assert len(state.coin_return_hist.get("AAA-USD", [])) <= 240
