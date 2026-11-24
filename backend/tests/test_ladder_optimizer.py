"""Tests for ladder_optimizer: synthetic candles only, no network."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import ladder_optimizer as lo

DAY = 86400


def wicky(wick_low, bars=100, every=7):
    """Bodies 100-105 under a 110 high; every seventh bar wicks down to ``wick_low``."""
    return [
        [i * DAY, wick_low if i % every == 0 else 100.0, 110.0, 100.0, 105.0, 10.0]
        for i in range(bars)
    ]


SHALLOW = wicky(99.0)   # 10% of the box under body support
MID = wicky(95.0)       # 50%
DEEP = wicky(92.0)      # 80%


def ladder(**kwargs):
    return lo.optimize_reload_ladder(80.0, 100.0, 120.0, 1000.0, **kwargs)


def test_default_weights_prices_and_spread_without_history():
    result = ladder()
    assert result["weights"] == [0.40, 0.35, 0.25] and result["regime"] == "default"
    assert result["expected_fill_probability_by_rung"] == [0.70, 0.50, 0.30]
    assert [r["price"] for r in result["rungs"]] == pytest.approx([92.36, 90.0, 87.64])
    assert [r["usdc_allocation"] for r in result["rungs"]] == [400.0, 350.0, 250.0]
    # A buy pays half of the 15 bps spread over the rung price.
    for rung in result["rungs"]:
        assert rung["net_fill_price"] == pytest.approx(rung["price"] * 1.00075)
        assert rung["projected_coins"] == pytest.approx(rung["usdc_allocation"] / rung["net_fill_price"], rel=1e-6)
    assert result["projected_coins_if_all_fill"] == pytest.approx(sum(r["projected_coins"] for r in result["rungs"]))
    # The default split leans shallow, so it buys slightly fewer coins than equal thirds.
    assert result["net_extra_coins_vs_flat_weights"] < 0
    assert result["history"]["events"] == 0 and result["outcome_validated"] is False


def test_wick_penetration_is_measured_against_body_support():
    assert lo.measure_wick_penetration(SHALLOW)["touch_share_by_rung"] == [0.0, 0.0, 0.0]
    mid = lo.measure_wick_penetration(MID)
    assert mid["events"] == 11 and mid["enough_history"] is True
    assert mid["touch_share_by_rung"] == [1.0, 1.0, 0.0] and mid["median_depth"] == 0.5
    assert lo.measure_wick_penetration(DEEP)["touch_share_by_rung"] == [1.0, 1.0, 1.0]
    short = lo.measure_wick_penetration(DEEP[:40])
    assert short["events"] < lo.MIN_EVENTS and short["enough_history"] is False
    assert lo.measure_wick_penetration(None)["events"] == 0


def test_deep_wick_history_shifts_weight_to_the_deep_rung():
    result = ladder(daily_candles=DEEP)
    w1, w2, w3 = result["weights"]
    assert result["regime"] == "deep_wick" and w3 > 0.25 and w3 > w2 > w1
    assert w1 == pytest.approx(lo.MIN_WEIGHT) and sum(result["weights"]) == pytest.approx(1.0, abs=1e-5)
    assert result["expected_fill_probability_by_rung"] == [0.95, 0.95, 0.95]
    # More USDC at lower prices buys more coins than equal thirds.
    assert result["net_extra_coins_vs_flat_weights"] > 0
    assert result["expected_extra_coins_vs_flat_weights"] > 0
    assert result["projected_coins_if_all_fill"] > ladder()["projected_coins_if_all_fill"]


def test_fast_rebound_history_shifts_weight_to_the_shallow_rung():
    result = ladder(daily_candles=SHALLOW)
    w1, w2, w3 = result["weights"]
    assert result["regime"] == "fast_rebound" and w1 > 0.40 and w1 > w2 > w3
    assert w3 == pytest.approx(lo.MIN_WEIGHT) and sum(result["weights"]) == pytest.approx(1.0, abs=1e-5)
    assert result["expected_fill_probability_by_rung"] == [0.05, 0.05, 0.05]
    assert result["net_extra_coins_vs_flat_weights"] < ladder()["net_extra_coins_vs_flat_weights"] < 0


@pytest.mark.parametrize("candles", [SHALLOW, MID, DEEP, wicky(60.0), wicky(99.9), DEEP[:40], None])
def test_weights_always_sum_to_one_with_every_rung_at_least_fifteen_percent(candles):
    result = ladder(daily_candles=candles)
    assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-5)
    assert min(result["weights"]) >= lo.MIN_WEIGHT - 1e-6
    assert sum(r["usdc_allocation"] for r in result["rungs"]) == pytest.approx(1000.0, abs=0.02)
    assert all(0.05 <= p <= 0.95 for p in result["expected_fill_probability_by_rung"])


def test_base_weights_set_the_fallback_and_the_point_the_tilt_moves_from():
    deep_heavy = (25, 35, 40)
    assert ladder(base_weights=deep_heavy)["weights"] == [0.25, 0.35, 0.4]
    assert ladder(base_weights=deep_heavy)["net_extra_coins_vs_flat_weights"] > 0
    tilted = ladder(daily_candles=DEEP, base_weights=deep_heavy)["weights"]
    assert tilted[2] > 0.4 and tilted[0] == pytest.approx(lo.MIN_WEIGHT)
    rebound = ladder(daily_candles=SHALLOW, base_weights=deep_heavy)["weights"]
    assert rebound[0] > 0.25 and rebound[2] < 0.4
    for bad in ((1, 1), (1, 0, 1), (1, "x", 1), (1, float("nan"), 1), None):
        with pytest.raises(ValueError):
            ladder(base_weights=bad)


def test_short_history_keeps_the_default_split():
    result = ladder(daily_candles=DEEP[:40])
    assert result["weights"] == [0.40, 0.35, 0.25] and result["regime"] == "default"


def test_a_wider_spread_buys_fewer_coins_and_zero_spread_fills_at_the_rung():
    free, normal, wide = ladder(spread_bps=0), ladder(), ladder(spread_bps=100)
    assert free["projected_coins_if_all_fill"] > normal["projected_coins_if_all_fill"] > wide["projected_coins_if_all_fill"]
    assert all(r["net_fill_price"] == r["price"] for r in free["rungs"])
    assert wide["rungs"][0]["net_fill_price"] == pytest.approx(92.36 * 1.005)


def test_rungs_never_sit_above_the_current_price():
    result = lo.optimize_reload_ladder(80.0, 100.0, 89.0, 1000.0)
    assert [r["price"] for r in result["rungs"]] == pytest.approx([89.0, 89.0, 87.64])


def test_result_is_deterministic_and_ignores_candle_order_and_bad_rows():
    noisy = list(reversed(DEEP)) + [None, [1, 2], ["x"] * 6, [5 * DAY, -1, 1, 1, 1, 1]]
    assert ladder(daily_candles=noisy) == ladder(daily_candles=DEEP) == ladder(daily_candles=tuple(DEEP))


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((100.0, 80.0, 120.0, 1000.0), {}), ((80.0, 80.0, 120.0, 1000.0), {}),
        ((0, 100.0, 120.0, 1000.0), {}), ((80.0, 100.0, -1, 1000.0), {}),
        ((80.0, 100.0, 120.0, 0), {}), ((80.0, 100.0, 120.0, float("nan")), {}),
        ((80.0, "x", 120.0, 1000.0), {}), ((80.0, 100.0, 120.0, 1000.0), {"spread_bps": -1}),
        ((80.0, 100.0, 120.0, 1000.0), {"spread_bps": "x"}), ((80.0, 100.0, 120.0, 1000.0), {"spread_bps": 10_000}),
    ],
)
def test_invalid_inputs_are_rejected(args, kwargs):
    with pytest.raises(ValueError):
        lo.optimize_reload_ladder(*args, **kwargs)
