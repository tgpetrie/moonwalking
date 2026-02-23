from __future__ import annotations

import time

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


def _assert_no_market_symbols(alerts: list[dict]) -> None:
    for a in alerts or []:
        sym = str(a.get("symbol") or "").upper()
        assert sym not in {"MARKET", "MARKET-USD"}


def test_coin_fomo_emits_coin_scoped_and_attaches_mood_context():
    prices = {
        "BTC-USD": {"price": 50000.0, "pct_1m": 1.4, "pct_3m": 3.4, "pct_1h": 5.1},
        "ETH-USD": {"price": 3100.0, "pct_1m": 0.7, "pct_3m": 2.3, "pct_1h": 3.0},
        "SOL-USD": {"price": 170.0, "pct_1m": 0.8, "pct_3m": 2.1, "pct_1h": 2.7},
        "ADA-USD": {"price": 0.61, "pct_1m": 0.5, "pct_3m": 1.7, "pct_1h": 2.2},
        "XRP-USD": {"price": 0.71, "pct_1m": 0.4, "pct_3m": 1.6, "pct_1h": 2.0},
        "AVAX-USD": {"price": 37.0, "pct_1m": 0.5, "pct_3m": 1.8, "pct_1h": 2.3},
    }
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 5200.0,
            "volume_1h_prev": 1800.0,
            "volume_change_1h_pct": 188.9,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 4000.0,
            "volume_1h_prev": 2100.0,
            "volume_change_1h_pct": 90.5,
            "baseline_ready": True,
        },
        "SOL-USD": {
            "volume_1h_now": 2400.0,
            "volume_1h_prev": 1300.0,
            "volume_change_1h_pct": 84.6,
            "baseline_ready": True,
        },
        "ADA-USD": {
            "volume_1h_now": 2000.0,
            "volume_1h_prev": 1400.0,
            "volume_change_1h_pct": 42.8,
            "baseline_ready": True,
        },
        "XRP-USD": {
            "volume_1h_now": 1700.0,
            "volume_1h_prev": 1300.0,
            "volume_change_1h_pct": 30.7,
            "baseline_ready": True,
        },
        "AVAX-USD": {
            "volume_1h_now": 1300.0,
            "volume_1h_prev": 900.0,
            "volume_change_1h_pct": 44.4,
            "baseline_ready": True,
        },
    }

    state = AlertEngineState()
    state.market_pressure_index_hist = [(time.time() - 70, 35.0)]

    alerts, _, pressure = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=state,
        include_impulse=False,
        thresholds={
            "coin_fomo_mpi_min": 40,
            "coin_fomo_d_mpi_60s": 2.0,
            "coin_fomo_pct3m_min": 2.0,
            "coin_fomo_pct1m_min": 0.5,
            "coin_fomo_accel_min": 0.8,
            "coin_thrust_breadth_min": 0.5,
            "coin_thrust_pct3m_min": 1.4,
            "coin_thrust_rs3m_min": 0.4,
            "coin_thrust_persist_min": 0.2,
        },
    )

    types = _types(alerts)
    assert "coin_fomo" in types
    _assert_no_market_symbols(alerts)

    for a in alerts:
        ev = a.get("evidence") or {}
        if str(a.get("symbol") or "").upper() in {"MARKET", "MARKET-USD"}:
            continue
        assert "mood_label" in ev
        assert "mood_index" in ev
        assert "mood_score01" in ev

    assert pressure.index >= 0


def test_coin_breadth_failure_emits_without_market_alerts():
    prices = {
        "DOGE-USD": {"price": 0.09, "pct_1m": -1.1, "pct_3m": -3.1, "pct_1h": -4.0},
        "BTC-USD": {"price": 48000.0, "pct_1m": -0.6, "pct_3m": -1.4, "pct_1h": -2.0},
        "ETH-USD": {"price": 2950.0, "pct_1m": -0.5, "pct_3m": -1.2, "pct_1h": -1.7},
        "SOL-USD": {"price": 160.0, "pct_1m": -0.8, "pct_3m": -1.6, "pct_1h": -2.3},
        "ADA-USD": {"price": 0.58, "pct_1m": -0.3, "pct_3m": -0.9, "pct_1h": -1.2},
    }
    volumes = {
        "DOGE-USD": {
            "volume_1h_now": 3200.0,
            "volume_1h_prev": 2000.0,
            "volume_change_1h_pct": 60.0,
            "baseline_ready": True,
        },
        "BTC-USD": {
            "volume_1h_now": 3000.0,
            "volume_1h_prev": 2600.0,
            "volume_change_1h_pct": 15.3,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 2200.0,
            "volume_1h_prev": 2100.0,
            "volume_change_1h_pct": 4.8,
            "baseline_ready": True,
        },
        "SOL-USD": {
            "volume_1h_now": 1700.0,
            "volume_1h_prev": 1500.0,
            "volume_change_1h_pct": 13.3,
            "baseline_ready": True,
        },
        "ADA-USD": {
            "volume_1h_now": 1300.0,
            "volume_1h_prev": 1200.0,
            "volume_change_1h_pct": 8.3,
            "baseline_ready": True,
        },
    }

    alerts, _, _ = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=False,
        thresholds={
            "coin_failure_breadth_max": 0.5,
            "coin_failure_pct3m_max": -1.4,
            "coin_failure_rs3m_max": -0.8,
        },
    )

    assert "coin_breadth_failure" in _types(alerts)
    _assert_no_market_symbols(alerts)


def test_coin_reversal_and_fakeout_emit_coin_scoped():
    prices = {
        "BTC-USD": {"price": 51000.0, "pct_1m": -1.3, "pct_3m": 3.4, "pct_1h": 4.1},
        "ETH-USD": {"price": 3150.0, "pct_1m": 0.1, "pct_3m": 0.5, "pct_1h": 1.2},
        "SOL-USD": {"price": 172.0, "pct_1m": 0.0, "pct_3m": 0.2, "pct_1h": 0.8},
    }
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2600.0,
            "volume_1h_prev": 1900.0,
            "volume_change_1h_pct": 36.8,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 2100.0,
            "volume_1h_prev": 2000.0,
            "volume_change_1h_pct": 5.0,
            "baseline_ready": True,
        },
        "SOL-USD": {
            "volume_1h_now": 1600.0,
            "volume_1h_prev": 1500.0,
            "volume_change_1h_pct": 6.6,
            "baseline_ready": True,
        },
    }

    alerts, _, _ = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=AlertEngineState(),
        include_impulse=False,
    )

    types = _types(alerts)
    assert "coin_reversal_down" in types
    assert "coin_fakeout" in types
    _assert_no_market_symbols(alerts)

    one_min = [
        a
        for a in alerts
        if (a.get("type") or "").startswith("coin_")
        and (a.get("type") or "") in {"coin_reversal_down", "coin_fakeout"}
    ]
    assert one_min
    for a in one_min:
        ev = a.get("evidence") or {}
        assert ev.get("window") == "1m"


def test_coin_persistence_gainer_emits_after_streak():
    state = AlertEngineState()
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 3000.0,
            "volume_1h_prev": 2400.0,
            "volume_change_1h_pct": 25.0,
            "baseline_ready": True,
        },
        "ETH-USD": {
            "volume_1h_now": 1800.0,
            "volume_1h_prev": 1700.0,
            "volume_change_1h_pct": 5.9,
            "baseline_ready": True,
        },
    }

    last_alerts: list[dict] = []
    for _ in range(4):
        prices = {
            "BTC-USD": {"price": 50000.0, "pct_1m": 0.3, "pct_3m": 2.2, "pct_1h": 3.5},
            "ETH-USD": {
                "price": 3000.0,
                "pct_1m": -0.2,
                "pct_3m": -1.8,
                "pct_1h": -2.1,
            },
        }
        last_alerts, state, _ = compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "cooldown_persist": 1,
                "persist_min_streak": 4,
                "persist_min_pct": 1.5,
                "coin_thrust_breadth_min": 0.9,  # suppress unrelated mood emits
            },
        )

    types = _types(last_alerts)
    assert "coin_persistent_gainer" in types
    assert "coin_persistent_loser" in types
    _assert_no_market_symbols(last_alerts)


def test_coin_volatility_expansion_emits_after_regime_shift():
    state = AlertEngineState()
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2200.0,
            "volume_1h_prev": 2000.0,
            "volume_change_1h_pct": 10.0,
            "baseline_ready": True,
        },
    }

    # Warm low-vol regime (small alternating 1m returns).
    for i in range(30):
        r = 0.05 if (i % 2 == 0) else -0.04
        prices = {
            "BTC-USD": {"price": 50000.0, "pct_1m": r, "pct_3m": 0.4, "pct_1h": 1.1},
        }
        _, state, _ = compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "coin_fomo_mpi_min": 101,  # keep mood rules quiet for this unit test
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
            },
        )

    # Shock sample: large 1m return causes vol expansion vs baseline.
    final_prices = {
        "BTC-USD": {"price": 50500.0, "pct_1m": 1.4, "pct_3m": 0.9, "pct_1h": 1.4},
    }
    alerts, _, _ = compute_alerts(
        price_snapshot=final_prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=state,
        include_impulse=False,
        thresholds={
            "coin_fomo_mpi_min": 101,
            "coin_thrust_breadth_min": 2.0,
            "coin_failure_breadth_max": -1.0,
        },
    )

    assert "coin_volatility_expansion" in _types(alerts)
    _assert_no_market_symbols(alerts)


def test_coin_liquidity_shock_emits_with_muted_price():
    prices = {
        "BTC-USD": {"price": 50010.0, "pct_1m": 0.05, "pct_3m": 0.2, "pct_1h": 0.7},
    }
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2100.0,
            "volume_1h_prev": 2000.0,
            "volume_change_1h_pct": 5.0,
            "baseline_ready": True,
        },
    }

    baseline = []
    for i in range(30):
        baseline.append(
            {
                "ts": 1700000000 - (i + 1) * 60,
                "vol": 100.0 + ((i % 5) - 2) * 3.0,  # 94..106 baseline variance
                "open": 50000.0,
                "close": 50000.0,
                "high": 50020.0,
                "low": 49980.0,
            }
        )
    minute_volumes = {
        "BTC-USD": [
            {
                "ts": 1700000000,
                "vol": 520.0,
                "open": 50000.0,
                "close": 50002.0,
                "high": 50010.0,
                "low": 49990.0,
            },
            *baseline,
        ]
    }

    alerts, _, _ = compute_alerts(
        price_snapshot=prices,
        volume_snapshot=volumes,
        minute_volumes=minute_volumes,
        state=AlertEngineState(),
        include_impulse=False,
        thresholds={
            "coin_fomo_mpi_min": 101,
            "coin_thrust_breadth_min": 2.0,
            "coin_failure_breadth_max": -1.0,
        },
    )

    assert "coin_liquidity_shock" in _types(alerts)
    _assert_no_market_symbols(alerts)


def test_coin_trend_break_up_emits_with_volume_support():
    state = AlertEngineState()
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2600.0,
            "volume_1h_prev": 1800.0,
            "volume_change_1h_pct": 44.4,
            "baseline_ready": True,
        },
    }

    seen: list[dict] = []
    # Decelerate from positive to negative to build a negative fast/slow diff,
    # then snap back up to force a crossover.
    seq = [0.8, 0.6, 0.4, 0.2, -0.2, -0.6, -1.0, -1.2, 0.8, 1.0, 1.2]
    for r in seq:
        prices = {
            "BTC-USD": {
                "price": 50000.0,
                "pct_1m": r,
                "pct_3m": r * 1.4,
                "pct_1h": r * 1.7,
            },
        }
        alerts, state, _ = compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "trend_break_fast_alpha": 0.55,
                "trend_break_slow_alpha": 0.10,
                "trend_break_min_abs_diff": 0.05,
                "trend_break_vol_confirm_pct": 10.0,
                "trend_break_vol_ratio_min": 1.1,
                "coin_fomo_mpi_min": 101,
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
                "persist_min_streak": 99,
            },
        )
        seen.extend(alerts)

    assert "coin_trend_break_up" in _types(seen)
    _assert_no_market_symbols(seen)


def test_coin_squeeze_break_emits_after_compression_then_break():
    state = AlertEngineState()
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2400.0,
            "volume_1h_prev": 1900.0,
            "volume_change_1h_pct": 26.3,
            "baseline_ready": True,
        },
    }

    # Higher-vol history.
    for i in range(90):
        r = [0.4, -0.35, 0.3, -0.45][i % 4]
        prices = {
            "BTC-USD": {
                "price": 50000.0,
                "pct_1m": r,
                "pct_3m": r * 0.8,
                "pct_1h": r * 1.0,
            }
        }
        compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "coin_fomo_mpi_min": 101,
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
                "persist_min_streak": 99,
            },
        )

    # Compression regime.
    for i in range(20):
        r = 0.03 if (i % 2 == 0) else -0.02
        prices = {
            "BTC-USD": {"price": 50000.0, "pct_1m": r, "pct_3m": 0.08, "pct_1h": 0.2}
        }
        compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "coin_fomo_mpi_min": 101,
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
                "persist_min_streak": 99,
            },
        )

    # Break window.
    final_alerts: list[dict] = []
    for i in range(10):
        r = 1.2 if i == 9 else (0.02 if (i % 2 == 0) else -0.02)
        prices = {
            "BTC-USD": {"price": 50000.0, "pct_1m": r, "pct_3m": 0.5, "pct_1h": 0.8}
        }
        final_alerts, state, _ = compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "squeeze_window_n": 8,
                "squeeze_hist_n": 80,
                "squeeze_compress_percentile": 0.35,
                "squeeze_break_pct_1m_min": 0.6,
                "squeeze_break_vol_ratio_min": 1.4,
                "coin_fomo_mpi_min": 101,
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
                "persist_min_streak": 99,
            },
        )

    assert "coin_squeeze_break" in _types(final_alerts)
    _assert_no_market_symbols(final_alerts)


def test_coin_exhaustion_top_emits_after_persistent_run_and_flip():
    state = AlertEngineState()
    volumes = {
        "BTC-USD": {
            "volume_1h_now": 2600.0,
            "volume_1h_prev": 2000.0,
            "volume_change_1h_pct": 30.0,
            "baseline_ready": True,
        },
    }

    # Build persistent upside streak.
    for _ in range(4):
        prices = {
            "BTC-USD": {"price": 50000.0, "pct_1m": 0.35, "pct_3m": 2.3, "pct_1h": 2.8}
        }
        compute_alerts(
            price_snapshot=prices,
            volume_snapshot=volumes,
            minute_volumes={},
            state=state,
            include_impulse=False,
            thresholds={
                "coin_fomo_mpi_min": 101,
                "coin_thrust_breadth_min": 2.0,
                "coin_failure_breadth_max": -1.0,
            },
        )

    # Flip down while 3m context still up -> fakeout + exhaustion top.
    flip_prices = {
        "BTC-USD": {"price": 49900.0, "pct_1m": -1.25, "pct_3m": 2.4, "pct_1h": 2.5}
    }
    alerts, _, _ = compute_alerts(
        price_snapshot=flip_prices,
        volume_snapshot=volumes,
        minute_volumes={},
        state=state,
        include_impulse=False,
        thresholds={
            "coin_fomo_mpi_min": 101,
            "coin_thrust_breadth_min": 2.0,
            "coin_failure_breadth_max": -1.0,
            "exhaustion_min_streak": 4,
            "exhaustion_flip_pct_1m": 0.6,
            "exhaustion_context_pct_3m": 1.0,
        },
    )

    assert "coin_exhaustion_top" in _types(alerts)
    _assert_no_market_symbols(alerts)
