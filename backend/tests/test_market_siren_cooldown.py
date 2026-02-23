from __future__ import annotations

try:
    from alerts_engine import (
        AlertEngineState,
        MarketPressure,
        _detect_market_siren_alerts,
    )
except Exception:  # pragma: no cover - fallback import path
    from backend.alerts_engine import (
        AlertEngineState,
        MarketPressure,
        _detect_market_siren_alerts,
    )


def test_market_siren_cooldown_blocks_repeats() -> None:
    """MARKET siren should not re-fire during cooldown under identical conditions."""
    state = AlertEngineState()
    pressure = MarketPressure(
        heat=95.0,
        bias="up",
        breadth_up=1.0,
        breadth_down=0.0,
        impulse_count=5,
        symbol_count=5,
        label="FOMO",
        index=95,
        score01=0.95,
        components={"breadth_bias": 1.0, "vol_regime": 0.8},
    )

    thresholds = {
        "market_siren_score_min": 80.0,
        "market_siren_min_legs": 3,
        "market_siren_persist_polls": 1,
        "market_siren_cooldown_s": 9999,
        "market_siren_extreme_heat_min": 0.75,
    }

    first = _detect_market_siren_alerts(
        pressure=pressure,
        fg_value=90,
        state=state,
        t=thresholds,
    )
    first_types = {str(a.get("type") or "").lower() for a in first}
    assert "market_fomo_siren" in first_types

    second = _detect_market_siren_alerts(
        pressure=pressure,
        fg_value=90,
        state=state,
        t=thresholds,
    )
    second_types = {str(a.get("type") or "").lower() for a in second}
    assert "market_fomo_siren" not in second_types
    assert not second
