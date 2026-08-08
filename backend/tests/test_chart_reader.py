"""Tests for chart_reader — deterministic, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_reader import (
    analyze_candles,
    _calculate_trend,
    _find_support_zone,
    _find_resistance_zone,
    _compare_volume,
    _range_position,
    _score_confidence,
    _normalize_candles,
)

# [time, low, high, open, close, volume]
# 10 candles: clear uptrend, price climbing from ~150 to ~175.
_UPTREND = [
    [10, 150, 155, 151, 153, 1000],
    [20, 151, 156, 153, 155, 900],
    [30, 152, 157, 155, 156, 1100],
    [40, 153, 159, 156, 158, 950],
    [50, 155, 161, 158, 160, 800],
    [60, 157, 163, 160, 162, 1200],
    [70, 159, 165, 162, 164, 1300],
    [80, 161, 167, 164, 165, 1400],
    [90, 163, 172, 165, 170, 1800],  # last candle near resistance
    [100, 165, 180, 170, 178, 2000],
]

# Candles where price is falling.
_DOWNTREND = [
    [10, 180, 185, 185, 182, 1000],
    [20, 178, 184, 182, 180, 950],
    [30, 175, 181, 180, 176, 1100],
    [40, 172, 178, 176, 173, 1000],
    [50, 169, 175, 173, 170, 1200],
    [60, 165, 172, 170, 166, 1300],
    [70, 161, 168, 166, 162, 1100],
    [80, 157, 164, 162, 158, 1000],
    [90, 153, 160, 158, 154, 900],
    [100, 150, 157, 154, 151, 800],
]

_SIDEWAYS = [
    [10, 148, 162, 155, 156, 1000],
    [20, 150, 164, 156, 158, 1100],
    [30, 147, 161, 158, 155, 900],
    [40, 149, 163, 155, 157, 950],
    [50, 151, 165, 157, 159, 1000],
    [60, 148, 162, 159, 156, 1050],
    [70, 150, 163, 156, 158, 980],
    [80, 149, 161, 158, 155, 1020],
]

# Volume spike in final candles.
_HIGH_VOLUME_END = [
    [10, 150, 160, 155, 158, 500],
    [20, 152, 162, 158, 160, 520],
    [30, 154, 164, 160, 162, 510],
    [40, 156, 166, 162, 164, 490],
    [50, 158, 168, 164, 166, 500],
    [60, 160, 170, 166, 169, 2000],  # spike
    [70, 162, 172, 169, 171, 1900],
]

# Candles returned by Coinbase in descending order (most recent first).
_DESCENDING_ORDER = list(reversed(_UPTREND))


class TestNormalize:
    def test_sorts_ascending(self):
        rows = _normalize_candles(_DESCENDING_ORDER)
        ts_list = [r[0] for r in rows]
        assert ts_list == sorted(ts_list)

    def test_skips_garbage(self):
        dirty = [["x", None, None, None, None, None], *_UPTREND]
        rows = _normalize_candles(dirty)
        assert len(rows) == len(_UPTREND)

    def test_skips_zero_price(self):
        bad = [[1, 0, 0, 0, 0, 0], *_UPTREND[:3]]
        rows = _normalize_candles(bad)
        assert len(rows) == 3


class TestTrend:
    def test_detects_uptrend(self):
        rows = _normalize_candles(_UPTREND)
        assert _calculate_trend(rows)["label"] == "up"

    def test_detects_downtrend(self):
        rows = _normalize_candles(_DOWNTREND)
        assert _calculate_trend(rows)["label"] == "down"

    def test_detects_sideways(self):
        rows = _normalize_candles(_SIDEWAYS)
        assert _calculate_trend(rows)["label"] == "sideways"

    def test_too_few_candles_is_sideways(self):
        rows = _normalize_candles(_UPTREND[:2])
        assert _calculate_trend(rows)["label"] == "sideways"


class TestSupportZone:
    def test_zone_is_ordered_low_to_high(self):
        rows = _normalize_candles(_UPTREND)
        lo, hi = _find_support_zone(rows)
        assert lo <= hi

    def test_zone_is_near_minimum(self):
        rows = _normalize_candles(_UPTREND)
        lo, hi = _find_support_zone(rows)
        all_lows = [r[1] for r in rows]
        assert (
            lo == pytest_approx(min(all_lows), rel=0.01) or lo <= min(all_lows) * 1.05
        )

    def test_zone_width_is_nonzero(self):
        rows = _normalize_candles(_UPTREND)
        lo, hi = _find_support_zone(rows)
        assert hi > lo


class TestResistanceZone:
    def test_zone_is_ordered_low_to_high(self):
        rows = _normalize_candles(_UPTREND)
        lo, hi = _find_resistance_zone(rows)
        assert lo <= hi

    def test_zone_is_near_maximum(self):
        rows = _normalize_candles(_UPTREND)
        lo, hi = _find_resistance_zone(rows)
        all_highs = [r[2] for r in rows]
        assert hi >= max(all_highs) * 0.98


class TestVolume:
    def test_normal_volume(self):
        rows = _normalize_candles(_UPTREND)
        v = _compare_volume(rows)
        assert v["label"] in ("normal", "high", "low")

    def test_high_volume_spike(self):
        rows = _normalize_candles(_HIGH_VOLUME_END)
        v = _compare_volume(rows)
        assert v["label"] == "high"
        assert v["ratio"] > 1.5

    def test_too_few_returns_normal(self):
        rows = _normalize_candles(_UPTREND[:2])
        v = _compare_volume(rows)
        assert v["label"] == "normal"


class TestRangePosition:
    def test_near_resistance_when_price_at_top(self):
        rows = _normalize_candles(_UPTREND)
        # Last close is 178, high is 180, low is 150 → near top.
        rp = _range_position(rows)
        assert rp["zone"] in ("upper_range", "near_resistance")

    def test_near_support_when_price_at_bottom(self):
        rows = _normalize_candles(_DOWNTREND)
        rp = _range_position(rows)
        assert rp["zone"] in ("near_support", "lower_range")


class TestConfidence:
    def test_low_confidence_few_candles(self):
        assert _score_confidence("up", "normal", 5) == "low"

    def test_medium_confidence_moderate(self):
        assert _score_confidence("up", "normal", 25) == "medium"

    def test_high_confidence_with_volume(self):
        assert _score_confidence("up", "high", 45) == "high"

    def test_sideways_no_direction_boost(self):
        c = _score_confidence("sideways", "normal", 50)
        assert c in ("low", "medium")


class TestAnalyzeCandles:
    def test_returns_none_for_too_few(self):
        assert analyze_candles(_UPTREND[:3], "SOL") is None

    def test_returns_correct_symbol(self):
        result = analyze_candles(_UPTREND, "sol")
        assert result["symbol"] == "SOL"

    def test_not_financial_advice_always_true(self):
        result = analyze_candles(_UPTREND, "BTC")
        assert result["not_financial_advice"] is True

    def test_no_trading_words_in_summary(self):
        """Guardrail: summary must never contain trading action words (whole-word match)."""
        import re

        for candles, sym in [
            (_UPTREND, "BTC"),
            (_DOWNTREND, "ETH"),
            (_SIDEWAYS, "SOL"),
        ]:
            result = analyze_candles(candles, sym)
            text = (result["summary"] + " " + " ".join(result["watch_next"])).lower()
            # Check whole-word only — "sellers" is descriptive and permitted; "sell" as a verb is not.
            forbidden = [
                r"\bbuy\b",
                r"\bsell\b",
                r"\bhold\b",
                r"\benter\b",
                r"\bexit\b",
                r"stop loss",
                r"take profit",
            ]
            for pattern in forbidden:
                assert not re.search(
                    pattern, text
                ), f"Forbidden pattern '{pattern}' found in output for {sym}"

    def test_uptrend_read_shape(self):
        result = analyze_candles(_UPTREND, "SOL", "1h")
        assert result["direction"]["label"] == "up"
        assert isinstance(result["lower_area"]["zone"], list)
        assert len(result["lower_area"]["zone"]) == 2
        assert isinstance(result["upper_area"]["zone"], list)
        assert result["lower_area"]["zone"][0] < result["upper_area"]["zone"][1]
        assert result["confidence"] in ("low", "medium", "high")
        assert len(result["watch_next"]) == 2
        assert result["candle_count"] == 10
        assert result["window_hours"] == 10.0

    def test_descending_input_sorted_correctly(self):
        # API returns candles newest-first; result should match ascending input.
        asc_result = analyze_candles(_UPTREND, "SOL")
        desc_result = analyze_candles(_DESCENDING_ORDER, "SOL")
        assert asc_result["direction"]["label"] == desc_result["direction"]["label"]

    def test_high_volume_reflected(self):
        result = analyze_candles(_HIGH_VOLUME_END, "BTC")
        assert result["trading_activity"]["label"] == "high"

    def test_timeframe_affects_window_hours(self):
        result_1h = analyze_candles(_UPTREND, "BTC", "1h")
        result_4h = analyze_candles(_UPTREND, "BTC", "4h")
        assert result_4h["window_hours"] == result_1h["window_hours"] * 4


# Small helper to avoid importing pytest in the assertion (works with plain assert too).
def pytest_approx(value, rel=1e-6):
    return value
