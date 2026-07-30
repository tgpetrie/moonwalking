import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from position_levels import compute_levels

# [time, low, high, open, close, volume]
_CANDLES = [
    [1, 8, 12, 10, 11, 100],
    [2, 9, 13, 11, 12, 100],
    [3, 7, 14, 12, 10, 100],
    [4, 9, 15, 10, 13, 100],
    [5, 11, 16, 13, 14, 300],
]


def test_computes_swing_range_and_position():
    levels = compute_levels(_CANDLES, current_price=14.0)
    assert levels["support"] == 7  # lowest low
    assert levels["resistance"] == 16  # highest high
    # (14 - 7) / (16 - 7) = 77.8% of range.
    assert levels["range_position_pct"] == 77.8
    assert levels["range_zone"] == "upper_range"


def test_computes_atr_band_and_volatility():
    levels = compute_levels(_CANDLES, current_price=14.0)
    # ATR over the 4 available true ranges: (4 + 7 + 6 + 5) / 4 = 5.5.
    assert levels["atr"] == 5.5
    assert levels["band_low"] == 8.5
    assert levels["band_high"] == 19.5
    assert levels["volatility_pct"] == 39.29


def test_computes_momentum_and_volume_trend():
    levels = compute_levels(_CANDLES, current_price=14.0)
    # Last close 14 vs prior close 13.
    assert levels["momentum_1h_pct"] == 7.69
    # Last volume 300 vs median of prior [100,100,100,100] = 100.
    assert levels["volume_ratio"] == 3.0


def test_is_always_marked_not_outcome_validated():
    levels = compute_levels(_CANDLES, current_price=14.0)
    assert levels["outcome_validated"] is False
    assert levels["source"] == "coinbase_candles"


def test_falls_back_to_last_close_when_no_price():
    levels = compute_levels(_CANDLES, current_price=None)
    # Last close is 14 -> same range position as passing 14 explicitly.
    assert levels["range_position_pct"] == 77.8


def test_unsorted_candles_are_handled():
    shuffled = [_CANDLES[3], _CANDLES[0], _CANDLES[4], _CANDLES[1], _CANDLES[2]]
    levels = compute_levels(shuffled, current_price=14.0)
    assert levels["support"] == 7
    assert levels["resistance"] == 16
    assert levels["momentum_1h_pct"] == 7.69  # sequencing preserved


def test_range_zone_near_support():
    # (8 - 7) / 9 = 11% of range -> near_support (<=15%).
    levels = compute_levels(_CANDLES, current_price=8.0)
    assert levels["range_zone"] == "near_support"


def test_insufficient_candles_returns_none():
    assert compute_levels([], current_price=10.0) is None
    assert compute_levels([[1, 8, 12, 10, 11, 100]], current_price=10.0) is None


def test_garbage_rows_are_skipped():
    dirty = [["x", None, None, None, None, None], *_CANDLES]
    levels = compute_levels(dirty, current_price=14.0)
    assert levels["candle_count"] == 5
