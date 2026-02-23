from __future__ import annotations

try:
    import alerts_engine as engine
    from alerts_engine import AlertEngineState, DEFAULT_THRESHOLDS
except Exception:  # pragma: no cover - fallback import path
    import backend.alerts_engine as engine
    from backend.alerts_engine import AlertEngineState, DEFAULT_THRESHOLDS


def _mk_alert(symbol: str, typ: str, idx: int) -> dict:
    return {
        "id": f"{typ}_{symbol}_{idx}",
        "symbol": symbol,
        "type": typ,
        "severity": "high",
        "evidence": {"vol_z": 5.0},
    }


def test_whale_symbol_cooldown_blocks_repeats_and_allows_after_expiry(monkeypatch):
    state = AlertEngineState()
    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(engine.time, "time", lambda: fake_now["t"])

    t = {
        **DEFAULT_THRESHOLDS,
        "whale_symbol_cooldown_s": 180,
        "family_global_cooldown_s": 0,
        "family_recent_max": 999,
    }

    burst = [_mk_alert("BTC-USD", "whale_move", i) for i in range(10)]
    first = engine._shape_alert_stream(burst, state, t)
    assert len(first) == 1

    fake_now["t"] = 1_100.0
    blocked = engine._shape_alert_stream(
        [_mk_alert("BTC-USD", "whale_move", 11)], state, t
    )
    assert blocked == []

    fake_now["t"] = 1_181.0
    allowed = engine._shape_alert_stream(
        [_mk_alert("BTC-USD", "whale_move", 12)], state, t
    )
    assert len(allowed) == 1


def test_family_global_cooldown_prevents_same_family_burst(monkeypatch):
    state = AlertEngineState()
    fake_now = {"t": 2_000.0}
    monkeypatch.setattr(engine.time, "time", lambda: fake_now["t"])

    t = {
        **DEFAULT_THRESHOLDS,
        "whale_symbol_cooldown_s": 0,
        "family_global_cooldown_s": 20,
        "family_recent_max": 999,
    }

    alerts = [
        _mk_alert("BTC-USD", "whale_move", 1),
        _mk_alert("ETH-USD", "whale_move", 2),
    ]
    first = engine._shape_alert_stream(alerts, state, t)
    assert len(first) == 1

    fake_now["t"] = 2_021.0
    second = engine._shape_alert_stream(
        [_mk_alert("ETH-USD", "whale_move", 3)], state, t
    )
    assert len(second) == 1
