import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from entry_signal_intelligence import build_entry_read
from portfolio_risk import build_risk_board, normalize_holdings
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


def read(levels=None, price=100, **kwargs):
    return build_entry_read(
        product_id="BTC-USD",
        current_price=price,
        levels={**LEVELS, **(levels or {})},
        **kwargs,
    )


def test_requires_price_and_candle_structure():
    missing_price = build_entry_read(
        product_id="BTC-USD", current_price=None, levels=LEVELS
    )
    missing_levels = build_entry_read(
        product_id="BTC-USD", current_price=100, levels={}
    )

    assert missing_price["available"] is False
    assert missing_levels["available"] is False
    assert missing_levels["entry_signal"]["status"] == "unavailable"
    assert "candles" in missing_levels["reason"]


def test_never_places_an_order_or_claims_a_validated_outcome():
    plan = read()

    assert plan["methodology"]["order_placement"] is False
    assert plan["methodology"]["outcome_validated"] is False
    assert plan["methodology"]["history_available"] is False
    assert "not a buy instruction" in plan["methodology"]["disclosure"]


def test_range_bands_are_declared_recent_location_not_empirical_tails():
    methodology = read()["methodology"]
    bands = methodology["range_bands"]
    disclosure = methodology["disclosure"].lower()

    assert bands == {
        "range_band_status": "declared_convention",
        "range_band_meaning": "recent_range_location",
        "range_band_lower_pct": 15.0,
        "range_band_upper_pct": 85.0,
        "empirical_tail_quantiles": "unavailable",
    }
    assert "location bands for the recent measured range" in disclosure
    for word in ("unusual", "rare", "selective", "calibrated", "empirical tail"):
        assert word not in disclosure


def test_breakout_watch_requires_volume_and_momentum_together():
    breaking = read(
        {
            "range_position_pct": 96,
            "range_zone": "near_resistance",
            "resistance": 101,
            "volume_ratio": 1.8,
            "momentum_1h_pct": 1.5,
        }
    )

    assert breaking["entry_signal"]["status"] == "breakout"
    assert breaking["entry_signal"]["label"] == "Breakout watch"
    assert breaking["entry_zone"]["label"] == "Breakout retest band"
    assert any("1.8x" in reason for reason in breaking["entry_signal"]["reasons"])


def test_same_push_without_volume_is_too_extended_not_a_breakout():
    unconfirmed = read(
        {
            "range_position_pct": 96,
            "range_zone": "near_resistance",
            "resistance": 101,
            "volume_ratio": 1.0,
            "momentum_1h_pct": 1.5,
        }
    )

    assert unconfirmed["entry_signal"]["status"] == "extended"
    assert unconfirmed["entry_zone"]["low"] is None
    assert any(
        "above-baseline volume" in reason
        for reason in unconfirmed["entry_signal"]["reasons"]
    )


def test_volume_wording_matches_the_measured_bucket_without_changing_the_gate():
    # The newest hourly bucket can still be in progress, so no reason may claim it closed.
    at_gate = read(
        {
            "range_position_pct": 96,
            "range_zone": "near_resistance",
            "resistance": 101,
            "volume_ratio": 1.5,
            "momentum_1h_pct": 1.5,
        }
    )
    below_gate = read(
        {
            "range_position_pct": 96,
            "range_zone": "near_resistance",
            "resistance": 101,
            "volume_ratio": 1.49,
            "momentum_1h_pct": 1.5,
        }
    )

    assert at_gate["entry_signal"]["status"] == "breakout"
    assert below_gate["entry_signal"]["status"] == "extended"

    volume_reasons = [
        reason
        for plan in (at_gate, below_gate)
        for reason in plan["entry_signal"]["reasons"]
        if "volume" in reason
    ]
    assert volume_reasons
    assert all("completed candle" not in reason for reason in volume_reasons)
    assert any("latest measured candle" in reason for reason in volume_reasons)
    assert any("1.5x the median volume" in reason for reason in volume_reasons)


def test_support_reclaim_names_the_close_invalidation():
    reclaim = read(
        {
            "range_position_pct": 8,
            "range_zone": "near_support",
            "support": 98,
            "momentum_1h_pct": 0.9,
        }
    )

    assert reclaim["entry_signal"]["status"] == "entry_watch"
    assert reclaim["entry_signal"]["label"] == "Support reclaim"
    assert reclaim["invalidation"]["price"] == 98
    assert reclaim["invalidation"]["distance_pct"] < 0


def test_pullback_watch_requires_a_live_constructive_signal():
    pulling_back = {
        "range_position_pct": 35,
        "range_zone": "lower_range",
        "momentum_1h_pct": -0.8,
    }
    with_signal = read(
        pulling_back, signal_context={"primary_state": "Building", "direction": "up"}
    )
    without_signal = read(pulling_back)

    assert with_signal["entry_signal"]["status"] == "pullback"
    assert without_signal["entry_signal"]["status"] == "clear"
    assert without_signal["entry_signal"]["label"] == "No entry signal"


def test_reversal_warning_and_broken_structure_both_invalidate():
    warned = read(
        {"range_position_pct": 8, "range_zone": "near_support", "momentum_1h_pct": 0.9},
        signal_context={"primary_state": "Reversal Risk", "direction": "neutral"},
    )
    broken = read({"support": 100, "range_position_pct": 0}, price=99)

    assert warned["entry_signal"]["status"] == "invalidated"
    assert warned["entry_signal"]["score"] == 0
    assert broken["entry_signal"]["status"] == "invalidated"
    assert any(
        "measured support" in reason for reason in broken["entry_signal"]["reasons"]
    )


def test_broken_structure_uses_measured_support_not_derived_plan_reference():
    levels = {"support": 100, "band_low": 98, "range_position_pct": 0}
    sell_plan = build_sell_plan(
        product_id="BTC-USD", current_price=99, levels={**LEVELS, **levels}
    )

    assert sell_plan["stop"]["invalidation_price"] == 98
    assert 99 > sell_plan["stop"]["invalidation_price"]

    broken = read(
        levels,
        price=99,
        sell_plan=sell_plan,
    )

    assert broken["entry_signal"]["status"] == "invalidated"
    assert broken["invalidation"]["price"] == 100
    assert "measured support" in broken["invalidation"]["why"]
    assert "measured support" in broken["entry_signal"]["reasons"][0]
    assert broken["target_reference"]["reward_risk_ratio"] is None
    assert "withheld" in broken["target_reference"]["why"]


def test_thin_reward_against_structural_risk_reads_as_no_chase():
    thin = read({"resistance": 101, "support": 90, "range_position_pct": 70})

    assert thin["entry_signal"]["status"] == "extended"
    assert thin["target_reference"]["reward_risk_ratio"] < 1


def test_the_no_chase_label_matches_the_reason_it_gives():
    """A mid-range coin is not "extended"; only its reward-to-risk is poor."""
    mid_range = read({"resistance": 101, "support": 90, "range_position_pct": 52})
    at_the_top = read(
        {
            "resistance": 101,
            "range_position_pct": 92,
            "range_zone": "near_resistance",
            "volume_ratio": 1.0,
        }
    )

    assert mid_range["entry_signal"]["label"] == "Poor reward from here"
    assert mid_range["entry_signal"]["status"] == "extended"
    assert "reward" in mid_range["entry_signal"]["action"]
    # The first reason is the one the label was decided on.
    assert "Reward to the measured resistance" in mid_range["entry_signal"]["reasons"][0]
    assert "top 15%" in at_the_top["entry_signal"]["reasons"][0]
    assert at_the_top["entry_signal"]["label"] == "Too extended"
    assert "top of the measured range" in at_the_top["entry_signal"]["action"]


def test_price_above_the_measured_range_reports_no_overhead_reference():
    above = read({"resistance": 99, "range_position_pct": 100}, price=100)

    assert above["target_reference"]["first_resistance"] is None
    assert above["target_reference"]["reward_pct"] is None
    assert "no overhead reference" in above["target_reference"]["why"]


def test_entry_read_reuses_the_protection_plan_levels():
    plan = build_sell_plan(product_id="BTC-USD", current_price=100, levels=LEVELS)
    entry = read(
        {"range_position_pct": 8, "range_zone": "near_support", "momentum_1h_pct": 0.9},
        sell_plan=plan,
    )

    assert entry["invalidation"]["price"] == plan["stop"]["invalidation_price"]
    assert entry["entry_zone"]["low"] == plan["support_zone"]["low"]
    assert entry["entry_zone"]["high"] == plan["support_zone"]["high"]


def test_missing_momentum_and_volume_are_named_not_assumed():
    quiet = read({"momentum_1h_pct": None, "volume_ratio": None})

    assert quiet["entry_signal"]["status"] == "clear"
    assert any(
        "Short-term momentum is unavailable" in reason
        for reason in quiet["entry_signal"]["reasons"]
    )
    assert any(
        "volume baseline is unavailable" in reason
        for reason in quiet["entry_signal"]["reasons"]
    )
    # The only evidence point left is the measured reward-to-risk ratio; a
    # missing field never scores.
    assert quiet["entry_signal"]["score"] == 1


def board(levels_by_symbol, contexts=None, *, quote_as_of=1000, now=1001):
    holdings = normalize_holdings(
        [{"symbol": "AAA", "price_usd": 100, "quantity": 2}], positions=True
    )
    return build_risk_board(
        holdings,
        levels_by_symbol,
        contexts or {},
        source="portfolio",
        quote_as_of=quote_as_of,
        now=now,
    )


def test_board_row_carries_both_reads_off_one_quote():
    result = board({"AAA": LEVELS})
    row = result["rows"][0]

    assert row["plan"]["available"] is True
    assert row["entry"]["available"] is True
    assert row["entry"]["current_price"] == row["plan"]["current_price"]
    assert row["entry"]["invalidation"]["price"] == row["plan"]["stop"][
        "invalidation_price"
    ]
    assert row["entry_status"] == row["entry"]["entry_signal"]["status"]
    assert result["summary"]["entry_counts"][row["entry_status"]] == 1


def test_board_entry_read_is_unavailable_without_candle_history():
    result = board({})
    row = result["rows"][0]

    assert row["entry"]["available"] is False
    assert row["entry_status"] == "unavailable"
    assert result["summary"]["entry_counts"]["unavailable"] == 1


def test_board_entry_read_reports_the_stale_quote_reason():
    result = board({"AAA": LEVELS}, quote_as_of=1, now=100000)
    row = result["rows"][0]

    assert row["entry"]["available"] is False
    assert "fresh quote" in row["entry"]["reason"]
    assert row["entry"]["entry_signal"]["reasons"] == [row["plan"]["reason"]]


def test_board_protection_ordering_is_unchanged_by_the_entry_read():
    holdings = normalize_holdings(
        [
            {"symbol": "AAA", "price_usd": 100, "quantity": 1},
            {"symbol": "BBB", "price_usd": 100, "quantity": 1},
        ],
        positions=True,
    )
    result = build_risk_board(
        holdings,
        {
            "AAA": LEVELS,
            "BBB": {**LEVELS, "momentum_1h_pct": -1, "range_position_pct": 90},
        },
        {"BBB": {"primary_state": "Reversal Risk"}},
        source="portfolio",
        quote_as_of=1000,
        now=1001,
    )

    assert [row["symbol"] for row in result["rows"]] == ["BBB", "AAA"]
    assert result["rows"][0]["entry"]["entry_signal"]["status"] == "invalidated"
