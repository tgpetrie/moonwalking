from __future__ import annotations

try:
    from alerts_engine import compute_alerts, AlertEngineState
except Exception:  # pragma: no cover - fallback import path
    from backend.alerts_engine import compute_alerts, AlertEngineState


def _types(alerts: list[dict]) -> set[str]:
    out: set[str] = set()
    for a in alerts or []:
        t = (a.get("type") or a.get("type_key") or "").strip().lower()
        if t:
            out.add(t)
    return out


def test_engine_impulse_toggle_off_produces_no_impulse_family():
    prices = {
        "BTC-USD": {
            "price": 50000.0,
            "pct_1m": 10.0,
            "pct_3m": 12.0,
            "pct_1h": 15.0,
        }
    }
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 0.0,
            "volume_1h_prev": 0.0,
            "volume_change_1h_pct": 0.0,
            "baseline_ready": True,
        }
    }

    alerts_off, _, _ = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=False,
    )
    types_off = _types(alerts_off)

    forbidden = {"impulse_1m", "impulse_3m", "moonshot", "crater", "breakout", "dump"}
    assert types_off.isdisjoint(forbidden)


def test_engine_impulse_toggle_on_can_produce_impulse_family():
    prices = {
        "BTC-USD": {
            "price": 50000.0,
            "pct_1m": 10.0,
            "pct_3m": 12.0,
            "pct_1h": 15.0,
        }
    }
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 0.0,
            "volume_1h_prev": 0.0,
            "volume_change_1h_pct": 0.0,
            "baseline_ready": True,
        }
    }

    alerts_on, _, _ = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=True,
    )
    types_on = _types(alerts_on)

    allowed = {"impulse_1m", "impulse_3m", "moonshot", "breakout", "dump", "crater"}
    assert bool(types_on.intersection(allowed))
