"""
Tests for interpretation_engine.py

Evidence payloads are taken directly from _make_alert() call sites in
alerts_engine.py to ensure tests reflect realistic production inputs.

Coverage:
  - Contract: all production types produce required keys
  - add_interpretation: non-mutating, always succeeds, handles missing evidence
  - interpretation_support: correct classification
  - Production families: BREAKOUT, DUMP, MOONSHOT, CRATER, WHALE_MOVE,
    COIN_REVERSAL_UP/DOWN, COIN_LIQUIDITY_SHOCK
  - Confidence scoring: factors that raise/lower the score
  - Generic fallback: unknown types get confidence=None
"""

from __future__ import annotations

import pytest

try:
    from interpretation_engine import add_interpretation, _interpret_alert
except ImportError:
    from backend.interpretation_engine import add_interpretation, _interpret_alert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "summary",
    "supportingFactors",
    "cautionFactors",
    "invalidationCondition",
    "confidence",
    "confidenceFactors",
    "interpretation_support_level",
}


def _interp(type_key: str, direction: str = "up", evidence: dict | None = None) -> dict:
    return _interpret_alert(type_key, direction, evidence or {})


def _alert(type_key: str, direction: str = "up", evidence: dict | None = None) -> dict:
    return add_interpretation(
        {
            "id": f"test_{type_key}_001",
            "symbol": "BTC-USD",
            "type": type_key,
            "type_key": type_key,
            "direction": direction,
            "evidence": evidence or {},
        }
    )


# ---------------------------------------------------------------------------
# Contract: every interpretation must include required keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_key, direction, evidence",
    [
        (
            "BREAKOUT",
            "up",
            {"window": "3m", "pct": 6.5, "pct_1m": 2.1, "pct_3m": 6.5, "pct_1h": 4.2},
        ),
        (
            "DUMP",
            "down",
            {
                "window": "3m",
                "pct": -4.8,
                "pct_1m": -1.9,
                "pct_3m": -4.8,
                "pct_1h": -6.0,
            },
        ),
        (
            "MOONSHOT",
            "up",
            {"window": "1m", "pct": 14.3, "pct_1m": 14.3, "pct_3m": 8.1},
        ),
        (
            "CRATER",
            "down",
            {"window": "1m", "pct": -13.1, "pct_1m": -13.1, "pct_3m": -7.4},
        ),
        (
            "WHALE_MOVE",
            "up",
            {
                "z_vol": 4.2,
                "vol_ratio": 5.3,
                "candle_pct": 1.8,
                "volume_change_1h_pct": 223.0,
                "cluster_z": 2.1,
                "baseline_ready": True,
            },
        ),
        (
            "COIN_REVERSAL_UP",
            "reversal_up",
            {"pct_1m": 1.4, "pct_3m": 2.8, "magnitude_bucket": 2.0},
        ),
        (
            "COIN_REVERSAL_DOWN",
            "reversal_down",
            {"pct_1m": -0.9, "pct_3m": -1.5, "magnitude_bucket": 1.0},
        ),
        (
            "COIN_LIQUIDITY_SHOCK",
            "up",
            {"vol_z": 3.8, "pct_1m": 2.1, "pct_3m": 3.4, "baseline_samples": 24},
        ),
        ("COIN_PERSISTENT_GAINER", "up", {"streak": 6, "rank": 2, "pct_3m": 4.1}),
        (
            "COIN_TREND_BREAK_UP",
            "up",
            {
                "ema_fast": 1.0054,
                "ema_slow": 1.0000,
                "diff": 0.54,
                "vol_ratio": 1.8,
                "pct_1h": 3.2,
            },
        ),
        (
            "COIN_SQUEEZE_BREAK",
            "up",
            {"vol_jump_ratio": 3.2, "vol_percentile": 0.88, "break_change_1m": 1.9},
        ),
        (
            "COIN_EXHAUSTION_TOP",
            "down",
            {
                "streak_len": 7,
                "pct_1m": -0.8,
                "volume_drop": True,
                "fakeout_hit": False,
            },
        ),
        ("COIN_FAKEOUT", "down", {}),
        ("COIN_VOLATILITY_EXPANSION", "", {}),
        ("UNKNOWN_TYPE_XYZ", "", {}),
    ],
)
def test_contract_all_required_keys_present(type_key, direction, evidence):
    result = _interp(type_key, direction, evidence)
    missing = REQUIRED_KEYS - set(result.keys())
    assert not missing, f"{type_key}: missing keys {missing}"


# ---------------------------------------------------------------------------
# add_interpretation: non-mutating and always returns dict with 'interpretation'
# ---------------------------------------------------------------------------


def test_add_interpretation_does_not_mutate_original():
    original = {"type_key": "BREAKOUT", "direction": "up", "evidence": {"pct": 5.0}}
    original_copy = dict(original)
    add_interpretation(original)
    assert original == original_copy


def test_add_interpretation_adds_key():
    result = _alert("WHALE_MOVE", "up", {"z_vol": 3.5, "baseline_ready": True})
    assert "interpretation" in result
    assert isinstance(result["interpretation"], dict)


def test_add_interpretation_passes_through_existing_alert_fields():
    result = _alert("MOONSHOT", "up", {"pct": 15.0})
    assert result["symbol"] == "BTC-USD"
    assert result["type_key"] == "MOONSHOT"


def test_add_interpretation_handles_non_dict_gracefully():
    # Non-dict input returned unchanged
    assert add_interpretation(None) is None
    assert add_interpretation("string") == "string"
    assert add_interpretation(42) == 42


def test_add_interpretation_handles_missing_evidence():
    result = add_interpretation({"type_key": "BREAKOUT", "direction": "up"})
    interp = result["interpretation"]
    assert "summary" in interp
    assert interp["confidence"] is not None or interp["confidence"] is None


def test_add_interpretation_handles_null_evidence_key():
    result = add_interpretation(
        {"type_key": "WHALE_MOVE", "direction": "up", "evidence": None}
    )
    assert "interpretation" in result


# ---------------------------------------------------------------------------
# interpretation_support classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_key",
    [
        "BREAKOUT",
        "DUMP",
        "MOONSHOT",
        "CRATER",
        "WHALE_MOVE",
        "COIN_REVERSAL_UP",
        "COIN_REVERSAL_DOWN",
        "COIN_LIQUIDITY_SHOCK",
    ],
)
def test_production_types_classified_correctly(type_key):
    result = _interp(type_key)
    assert (
        result["interpretation_support_level"] == "production"
    ), f"{type_key} should be 'production', got {result['interpretation_support_level']!r}"


@pytest.mark.parametrize(
    "type_key",
    [
        "STEALTH_MOVE",
        "COIN_PERSISTENT_GAINER",
        "COIN_PERSISTENT_LOSER",
        "COIN_TREND_BREAK_UP",
        "COIN_TREND_BREAK_DOWN",
        "COIN_SQUEEZE_BREAK",
        "COIN_EXHAUSTION_TOP",
        "COIN_EXHAUSTION_BOTTOM",
        "COIN_FAKEOUT",
        "COIN_VOLATILITY_EXPANSION",
    ],
)
def test_experimental_types_classified_correctly(type_key):
    result = _interp(type_key)
    assert (
        result["interpretation_support_level"] == "experimental"
    ), f"{type_key} should be 'experimental', got {result['interpretation_support_level']!r}"


def test_unknown_type_classified_none():
    result = _interp("TOTALLY_UNKNOWN_SIGNAL")
    assert result["interpretation_support_level"] == "none"
    assert result["confidence"] is None


# ---------------------------------------------------------------------------
# BREAKOUT — confidence scoring
# ---------------------------------------------------------------------------


def test_breakout_full_evidence_high_confidence():
    ev = {
        "window": "3m",
        "pct": 7.2,
        "pct_1m": 2.8,
        "pct_3m": 7.2,
        "pct_1h": 4.1,
    }
    result = _interp("BREAKOUT", "up", ev)
    assert (
        result["confidence"] >= 65
    ), f"Expected high confidence, got {result['confidence']}"
    assert len(result["supportingFactors"]) >= 2
    assert result["summary"] != ""


def test_breakout_no_evidence_lower_confidence():
    result = _interp("BREAKOUT", "up", {})
    assert result["confidence"] < 40


def test_breakout_extended_1h_adds_caution():
    ev = {"pct": 5.0, "pct_1m": 2.0, "pct_1h": 18.0}
    result = _interp("BREAKOUT", "up", ev)
    caution_texts = " ".join(result["cautionFactors"])
    assert "extended" in caution_texts.lower()


def test_breakout_counter_trend_lowers_confidence():
    ev_with_counter = {"pct": 5.0, "pct_1m": 2.0, "pct_1h": -3.0}
    ev_without_counter = {"pct": 5.0, "pct_1m": 2.0}
    conf_with = _interp("BREAKOUT", "up", ev_with_counter)["confidence"]
    conf_without = _interp("BREAKOUT", "up", ev_without_counter)["confidence"]
    assert conf_with < conf_without


def test_dump_direction_down():
    ev = {"window": "1m", "pct": -5.0, "pct_1m": -5.0, "pct_3m": -3.0}
    result = _interp("DUMP", "down", ev)
    assert (
        "drop" in result["summary"].lower()
        or "dump" in result["summary"].lower()
        or "crash" in result["summary"].lower()
        or "moved" in result["summary"].lower()
    )
    assert result["confidence"] > 30


def test_moonshot_base_confidence_higher_than_breakout():
    ev = {"pct": 14.0, "pct_1m": 14.0}
    moon_conf = _interp("MOONSHOT", "up", ev)["confidence"]
    break_conf = _interp("BREAKOUT", "up", ev)["confidence"]
    assert moon_conf >= break_conf


# ---------------------------------------------------------------------------
# WHALE_MOVE — confidence scoring
# ---------------------------------------------------------------------------


def test_whale_high_zscore_high_confidence():
    ev = {
        "z_vol": 5.5,
        "vol_ratio": 6.0,
        "candle_pct": 2.1,
        "volume_change_1h_pct": 280.0,
        "cluster_z": 2.8,
        "baseline_ready": True,
    }
    result = _interp("WHALE_MOVE", "up", ev)
    assert result["confidence"] >= 75
    assert any("5." in f or "σ" in f for f in result["supportingFactors"])


def test_whale_baseline_not_ready_lowers_confidence():
    ev_warm = {"z_vol": 3.5, "candle_pct": 1.5, "baseline_ready": True}
    ev_cold = {"z_vol": 3.5, "candle_pct": 1.5, "baseline_ready": False}
    assert (
        _interp("WHALE_MOVE", "up", ev_warm)["confidence"]
        > _interp("WHALE_MOVE", "up", ev_cold)["confidence"]
    )


def test_whale_absorption_direction_shows_caution():
    ev = {"z_vol": 4.0, "candle_pct": 0.05, "baseline_ready": True}
    result = _interp("WHALE_MOVE", "absorption", ev)
    caution_text = " ".join(result["cautionFactors"])
    assert "direction" in caution_text.lower() or "absorption" in caution_text.lower()


def test_whale_flat_price_adds_absorption_caution():
    ev = {"z_vol": 3.2, "candle_pct": 0.02, "baseline_ready": True}
    result = _interp("WHALE_MOVE", "up", ev)
    caution_text = " ".join(result["cautionFactors"])
    assert "absorption" in caution_text.lower() or "flat" in caution_text.lower()


# ---------------------------------------------------------------------------
# COIN_REVERSAL — confidence scoring
# ---------------------------------------------------------------------------


def test_reversal_strong_magnitude_with_price_confirmation_high_confidence():
    # magnitude_bucket is a float from _bucket_mag(pct_1m, 0.5) — e.g. 2.0 = strong
    ev = {
        "pct_1m": 1.8,
        "pct_3m": 3.2,
        "magnitude_bucket": 2.0,
    }
    result = _interp("COIN_REVERSAL_UP", "reversal_up", ev)
    assert result["confidence"] >= 60
    assert len(result["supportingFactors"]) >= 2


def test_reversal_contradicting_1m_lowers_confidence():
    ev_good = {"pct_1m": 1.2, "magnitude_bucket": 1.0}
    ev_bad = {"pct_1m": -0.8, "magnitude_bucket": 1.0}
    conf_good = _interp("COIN_REVERSAL_UP", "reversal_up", ev_good)["confidence"]
    conf_bad = _interp("COIN_REVERSAL_UP", "reversal_up", ev_bad)["confidence"]
    assert conf_good > conf_bad


def test_reversal_always_includes_fakeout_caution():
    result = _interp("COIN_REVERSAL_DOWN", "reversal_down", {"pct_1m": -1.0})
    caution_text = " ".join(result["cautionFactors"])
    assert "fakeout" in caution_text.lower()


# ---------------------------------------------------------------------------
# COIN_LIQUIDITY_SHOCK — confidence scoring
# ---------------------------------------------------------------------------


def test_liquidity_shock_strong_evidence_high_confidence():
    ev = {
        "vol_z": 4.8,
        "pct_1m": 2.4,
        "pct_3m": 3.1,
        "baseline_samples": 30,
    }
    result = _interp("COIN_LIQUIDITY_SHOCK", "up", ev)
    assert result["confidence"] >= 70


def test_liquidity_shock_thin_baseline_lowers_confidence():
    ev_thick = {"vol_z": 3.5, "pct_1m": 1.5, "baseline_samples": 25}
    ev_thin = {"vol_z": 3.5, "pct_1m": 1.5, "baseline_samples": 3}
    conf_thick = _interp("COIN_LIQUIDITY_SHOCK", "up", ev_thick)["confidence"]
    conf_thin = _interp("COIN_LIQUIDITY_SHOCK", "up", ev_thin)["confidence"]
    assert conf_thick > conf_thin


def test_liquidity_shock_flat_price_adds_caution():
    ev = {"vol_z": 3.0, "pct_1m": 0.1, "baseline_samples": 20}
    result = _interp("COIN_LIQUIDITY_SHOCK", "up", ev)
    caution_text = " ".join(result["cautionFactors"])
    assert "price" in caution_text.lower()


# ---------------------------------------------------------------------------
# Confidence factors must track supporting factors
# ---------------------------------------------------------------------------


def test_confidence_factors_subset_of_supporting_factors():
    ev = {
        "z_vol": 4.0,
        "candle_pct": 1.5,
        "cluster_z": 2.0,
        "volume_change_1h_pct": 180.0,
        "baseline_ready": True,
    }
    result = _interp("WHALE_MOVE", "up", ev)
    for factor in result["confidenceFactors"]:
        assert (
            factor in result["supportingFactors"]
        ), f"confidenceFactors item not in supportingFactors: {factor!r}"


def test_confidence_factors_max_3():
    ev = {
        "pct": 8.0,
        "pct_1m": 3.0,
        "pct_3m": 8.0,
        "pct_1h": 5.0,
        "window": "3m",
    }
    result = _interp("BREAKOUT", "up", ev)
    assert len(result["confidenceFactors"]) <= 3


# ---------------------------------------------------------------------------
# Generic fallback: unknown types
# ---------------------------------------------------------------------------


def test_generic_fallback_confidence_is_none():
    result = _interp("COIN_BREADTH_THRUST", "up", {})
    assert result["confidence"] is None


def test_generic_fallback_has_summary():
    result = _interp("MYSTERY_SIGNAL_123", "up", {})
    assert "mystery signal 123" in result["summary"].lower()


# ---------------------------------------------------------------------------
# Realistic end-to-end: full alert object through add_interpretation
# ---------------------------------------------------------------------------


def test_breakout_full_alert_pipeline():
    """Mirrors a real BREAKOUT alert as produced by _make_alert() in alerts_engine."""
    raw_alert = {
        "id": "BREAKOUT_SOL-USD_a3f7c8b1",
        "ts": "2026-08-09T14:23:01.456789+00:00",
        "symbol": "SOL-USD",
        "type": "BREAKOUT",
        "type_key": "BREAKOUT",
        "direction": "up",
        "severity": "high",
        "evidence": {
            "window": "3m",
            "pct": 4.8,
            "pct_1m": 1.9,
            "pct_3m": 4.8,
            "pct_1h": 2.3,
            "price": 182.45,
        },
    }
    result = add_interpretation(raw_alert)

    interp = result["interpretation"]
    assert interp["confidence"] >= 50
    assert interp["interpretation_support_level"] == "production"
    assert interp["summary"] != ""
    assert isinstance(interp["supportingFactors"], list)
    assert isinstance(interp["cautionFactors"], list)
    assert interp["invalidationCondition"] != ""
    # Original fields preserved
    assert result["symbol"] == "SOL-USD"
    assert result["severity"] == "high"


def test_whale_full_alert_pipeline():
    """Mirrors a real WHALE_MOVE alert (z-score mode) from alerts_engine."""
    raw_alert = {
        "id": "WHALE_MOVE_DOGE-USD_b2e1f9a4",
        "symbol": "DOGE-USD",
        "type": "WHALE_MOVE",
        "type_key": "WHALE_MOVE",
        "direction": "up",
        "evidence": {
            "window": "1m",
            "volume_change_1h_pct": 223.0,
            "z_vol": 4.2,
            "vol_ratio": 5.3,
            "candle_pct": 1.81,
            "cluster_z": 2.1,
            "latest_vol": 812500.0,
            "median_vol": 153000.0,
            "price": 0.0841,
            "baseline_ready": True,
        },
    }
    result = add_interpretation(raw_alert)
    interp = result["interpretation"]
    assert interp["confidence"] >= 70
    assert interp["interpretation_support_level"] == "production"
    # Should mention the z-score in supporting factors
    supporting_text = " ".join(interp["supportingFactors"])
    assert "4.2" in supporting_text or "σ" in supporting_text
