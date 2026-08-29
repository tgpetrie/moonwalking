import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sell_side_intelligence import build_sell_plan


LEVELS = {
    "support": 95,
    "resistance": 112,
    "atr": 2,
    "band_low": 98,
    "band_high": 102,
    "range_position_pct": 60,
    "range_zone": "mid_range",
    "volatility_pct": 2,
    "momentum_1h_pct": 1.2,
    "volume_ratio": 1.1,
    "window_hours": 50,
    "candle_count": 50,
    "source": "coinbase_candles",
}


def test_builds_stop_trigger_below_support_and_limit_below_trigger():
    plan = build_sell_plan(product_id="BTC-USD", current_price=100, levels=LEVELS)

    assert plan["available"] is True
    assert plan["stop"]["trigger_price"] < LEVELS["support"]
    assert plan["stop"]["limit_price"] < plan["stop"]["trigger_price"]
    assert plan["stop"]["invalidation_price"] == LEVELS["support"]
    assert plan["methodology"]["order_placement"] is False


def test_uses_resistance_as_first_trim_and_reports_reward_risk():
    plan = build_sell_plan(product_id="BTC-USD", current_price=100, levels=LEVELS)

    assert plan["profit"]["first_trim_price"] == 112
    assert plan["profit"]["reward_pct"] == 12
    assert plan["profit"]["reward_risk_ratio"] > 1


def test_top_watch_combines_resistance_momentum_and_live_warning():
    levels = {
        **LEVELS,
        "range_position_pct": 92,
        "range_zone": "near_resistance",
        "momentum_1h_pct": -1.4,
        "volume_ratio": 1.8,
        "resistance": 101,
    }
    plan = build_sell_plan(
        product_id="BTC-USD",
        current_price=100,
        levels=levels,
        signal_context={"primary_state": "Reversal Risk", "direction": "down"},
    )

    assert plan["top_signal"]["status"] == "high"
    assert plan["top_signal"]["label"] == "Protect now"
    assert any("reversal" in reason.lower() for reason in plan["top_signal"]["reasons"])


def test_support_zone_is_not_presented_as_automatic_buy():
    plan = build_sell_plan(product_id="BTC-USD", current_price=100, levels=LEVELS)

    assert "require a hold or reclaim" in plan["support_zone"]["why"]


def test_requires_price_and_candle_structure():
    missing_price = build_sell_plan(
        product_id="BTC-USD", current_price=None, levels=LEVELS
    )
    missing_levels = build_sell_plan(product_id="BTC-USD", current_price=100, levels={})

    assert missing_price["available"] is False
    assert missing_levels["available"] is False
