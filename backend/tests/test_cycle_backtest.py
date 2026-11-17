"""Tests for cycle_backtest: synthetic candles only, no network."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cycle_backtest as cb

DAY = 86400


def series(start, legs, t0=0):
    """Daily bars along geometric legs: ``[(bars, target_close), ...]``."""
    closes, price = [float(start)], float(start)
    for count, target in legs:
        step = (target / price) ** (1 / count)
        for _ in range(count):
            price *= step
            closes.append(price)
    out, prior = [], closes[0]
    for i, close in enumerate(closes):
        out.append([t0 + i * DAY, min(prior, close) * 0.995, max(prior, close) * 1.005, prior, close, 10.0])
        prior = close
    return out


def extend(candles, legs):
    """The same bars followed by more legs from the last close."""
    more = series(candles[-1][4], legs, t0=candles[-1][0])
    return candles + more[1:]


BOOM_BUST_RECOVERY = series(10, [(200, 100), (150, 20), (200, 80)])
STOP_AND_RETURN = series(50, [(100, 50), (20, 25), (40, 25), (60, 60)])
MOON = series(10, [(200, 100), (10, 90), (150, 300)])


def kinds(result):
    return [event["type"] for event in result["events"]]


def test_boom_bust_recovery_compounds_more_coins_than_holding():
    result = cb.simulate_cycle_compounding(BOOM_BUST_RECOVERY)
    assert kinds(result) == ["TRIM_TO_USDC", "RELOAD_ACCUMULATE", "RELOAD_ACCUMULATE", "RELOAD_ACCUMULATE"]
    trim, *fills = result["events"]
    # The trim is the first down day after the peak: 35% of 100 coins.
    assert trim["index"] == 201 and trim["coins_delta"] == pytest.approx(-35.0)
    assert trim["ts"] == 201 * DAY and 95 < trim["price"] < 100
    assert [fill["rung"] for fill in fills] == [1, 2, 3]
    assert [fill["retracement"] for fill in fills] == [0.382, 0.5, 0.618]
    assert trim["rung_prices"] == [fill["price"] for fill in fills]
    assert all(fill["price"] < trim["price"] for fill in fills)
    assert fills[0]["price"] > fills[1]["price"] > fills[2]["price"]
    # The freed USDC is split 40 / 35 / 25 and fully redeployed.
    freed = trim["usdc_delta"]
    assert [-fill["usdc_delta"] / freed for fill in fills] == pytest.approx([0.40, 0.35, 0.25], abs=1e-6)
    assert result["freed_usdc_remaining"] == 0 and result["open_ladder"] is None

    assert result["hodl_final_coins"] == result["initial_coins"] == 100.0
    assert result["compounded_final_coins"] > result["hodl_final_coins"]
    assert result["extra_coins_gained"] == pytest.approx(result["compounded_final_coins"] - 100.0)
    assert result["extra_coins_pct"] == pytest.approx(result["extra_coins_gained"], abs=1e-3)
    assert result["extra_coins_pct"] > 50
    assert result["strategy_final_value_usd"] > result["hodl_final_value_usd"]
    assert result["hodl_final_value_usd"] == pytest.approx(100 * 80, rel=1e-6)
    assert result["completed_trim_reload_cycles"] == 1
    assert result["max_drawdown_hodl_pct"] == pytest.approx(80.0, abs=0.5)
    assert result["max_drawdown_strategy_pct"] < result["max_drawdown_hodl_pct"]
    assert result["drawdown_reduction_pct"] == pytest.approx(
        result["max_drawdown_hodl_pct"] - result["max_drawdown_strategy_pct"], abs=1e-3
    )
    assert result["fresh_cash_added_usd"] == 0.0 and result["outcome_validated"] is False


def test_no_fresh_cash_every_event_trades_coins_against_usdc_at_its_price():
    for candles in (BOOM_BUST_RECOVERY, STOP_AND_RETURN, MOON):
        result = cb.simulate_cycle_compounding(candles)
        coins, usdc = result["initial_coins"], 0.0
        for event in result["events"]:
            assert event["usdc_delta"] == pytest.approx(-event["coins_delta"] * event["price"], rel=1e-6)
            coins += event["coins_delta"]
            usdc += event["usdc_delta"]
            assert coins >= -1e-9 and usdc >= -1e-6
            assert event["coins_after"] == pytest.approx(coins) and event["usdc_after"] == pytest.approx(usdc, abs=1e-4)
        assert result["compounded_final_coins"] == pytest.approx(coins)
        assert result["strategy_final_value_usd"] == pytest.approx(coins * candles[-1][4] + usdc, abs=0.02)


def test_flat_market_does_nothing():
    result = cb.simulate_cycle_compounding(series(50, [(300, 50)]))
    assert result["events"] == [] and result["completed_trim_reload_cycles"] == 0
    assert result["compounded_final_coins"] == 100.0 and result["extra_coins_gained"] == 0
    assert result["strategy_final_value_usd"] == result["hodl_final_value_usd"]
    assert result["max_drawdown_hodl_pct"] == result["max_drawdown_strategy_pct"] == 0
    assert result["drawdown_reduction_pct"] == 0


def test_chop_never_adds_cash_and_reloads_only_below_the_trim_price():
    legs = [(15, 60), (15, 50)] * 12
    result = cb.simulate_cycle_compounding(series(50, legs))
    trims = {e["index"]: e for e in result["events"] if e["type"] == "TRIM_TO_USDC"}
    for event in result["events"]:
        if event["type"] == "RELOAD_ACCUMULATE" and event["reason"] == "fib_reload_rung":
            assert event["price"] <= trims[event["trim_index"]]["price"]
    # With no stop, a rung fill can only add coins, so the stack never shrinks
    # below what was held after the trims still waiting on their ladder.
    if "PROTECTIVE_STOP" not in kinds(result) and result["open_ladder"] is None:
        assert result["compounded_final_coins"] >= 100.0
    assert result["strategy_final_value_usd"] > 0


def test_trim_cooldown_and_open_ladder_block_a_second_trim_of_the_same_rally():
    result = cb.simulate_cycle_compounding(MOON)
    # The price never comes back to a rung, so the one trim stays the only event.
    assert kinds(result) == ["TRIM_TO_USDC"]
    assert result["compounded_final_coins"] == pytest.approx(65.0)
    assert result["completed_trim_reload_cycles"] == 0
    assert [rung["index"] for rung in result["open_ladder"]["unfilled_rungs"]] == [1, 2, 3]
    assert result["freed_usdc_remaining"] > 0
    # Honest result: trimming before a moon leaves the strategy behind holding.
    assert result["strategy_final_value_usd"] < result["hodl_final_value_usd"]
    assert result["strategy_final_coin_equivalent"] < 100.0


def test_structural_break_stops_out_and_reaccumulates_on_the_breakout():
    result = cb.simulate_cycle_compounding(STOP_AND_RETURN)
    assert kinds(result) == ["PROTECTIVE_STOP", "RELOAD_ACCUMULATE"]
    stop, back = result["events"]
    assert stop["index"] == 101 and stop["reason"] == "structural_support_break"
    assert stop["price"] < stop["support"] * 0.98 and stop["coins_after"] == 0
    assert stop["usdc_after"] == pytest.approx(100 * stop["price"], rel=1e-6)
    assert back["reason"] == "low_confirmation_breakout" and back["price"] > back["breakout_above"]
    assert back["price"] < stop["price"] and back["usdc_after"] == 0
    assert result["compounded_final_coins"] > 150 and result["ended_stopped_out"] is False
    assert result["max_drawdown_strategy_pct"] < result["max_drawdown_hodl_pct"]
    assert result["completed_trim_reload_cycles"] == 0


def test_a_run_that_ends_stopped_out_reports_zero_coins_but_keeps_the_usdc():
    result = cb.simulate_cycle_compounding(series(50, [(100, 50), (20, 25), (30, 25)]))
    assert kinds(result) == ["PROTECTIVE_STOP"] and result["ended_stopped_out"] is True
    assert result["compounded_final_coins"] == 0 and result["freed_usdc_remaining"] > 0
    assert result["strategy_final_value_usd"] == pytest.approx(result["freed_usdc_remaining"], abs=0.01)
    assert result["strategy_final_value_usd"] > result["hodl_final_value_usd"]


def test_a_steady_decline_sets_fresh_lows_and_is_not_a_structural_break():
    result = cb.simulate_cycle_compounding(series(100, [(250, 20)]))
    assert "PROTECTIVE_STOP" not in kinds(result)


@pytest.mark.parametrize("candles", [BOOM_BUST_RECOVERY, STOP_AND_RETURN, MOON])
def test_zero_lookahead_a_prefix_replays_the_same_events(candles):
    full = cb.simulate_cycle_compounding(candles)["events"]
    assert full
    for cut in (61, 102, 150, 202, 230, 300, 352, len(candles) - 1):
        if cut >= len(candles):
            continue
        prefix = cb.simulate_cycle_compounding(candles[:cut])["events"]
        assert prefix == [event for event in full if event["index"] < cut]


@pytest.mark.parametrize("future", [[(60, 0.5)], [(60, 5000)], [(5, 1), (5, 900), (40, 3)]])
def test_zero_lookahead_future_crash_or_moon_bars_never_change_earlier_events(future):
    for candles in (BOOM_BUST_RECOVERY, STOP_AND_RETURN, MOON):
        base = cb.simulate_cycle_compounding(candles)
        scale = candles[-1][4]
        longer = extend(candles, [(bars, scale * mult if mult < 100 else mult) for bars, mult in future])
        later = cb.simulate_cycle_compounding(longer)["events"]
        assert [event for event in later if event["index"] < len(candles)] == base["events"]


def test_input_order_duplicates_and_bad_rows_do_not_matter():
    base = cb.simulate_cycle_compounding(BOOM_BUST_RECOVERY)
    noisy = list(reversed(BOOM_BUST_RECOVERY)) + [BOOM_BUST_RECOVERY[5], None, [1, 2], ["x"] * 6, [7 * DAY, -1, 1, 1, 1, 1]]
    assert cb.simulate_cycle_compounding(noisy) == base
    assert cb.simulate_cycle_compounding(tuple(BOOM_BUST_RECOVERY)) == base


def test_parameters_change_size_and_ladder_split():
    result = cb.simulate_cycle_compounding(
        BOOM_BUST_RECOVERY, initial_coins=10, trim_fraction=0.5, ladder_weights=(2, 1, 1)
    )
    trim, *fills = result["events"]
    assert trim["coins_delta"] == pytest.approx(-5.0)
    assert [-fill["usdc_delta"] / trim["usdc_delta"] for fill in fills] == pytest.approx([0.5, 0.25, 0.25], abs=1e-6)
    assert result["compounded_final_coins"] > 10
    # A long cooldown cannot stop the first trim, and a long warm-up delays everything.
    assert cb.simulate_cycle_compounding(BOOM_BUST_RECOVERY, warmup_bars=540)["events"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial_coins": 0}, {"initial_coins": float("nan")}, {"trim_fraction": 0}, {"trim_fraction": 1},
        {"ladder_weights": (0.5, 0.5)}, {"ladder_weights": (0.5, 0.5, 0)}, {"ladder_weights": (1, "x", 1)},
        {"lookback_bars": 0}, {"warmup_bars": True}, {"cooldown_bars": 1.5}, {"stop_buffer_pct": 100},
    ],
)
def test_invalid_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        cb.simulate_cycle_compounding(BOOM_BUST_RECOVERY, **kwargs)


@pytest.mark.parametrize("candles", [None, [], [[0, 1, 1, 1, 1, 1]], "nope"])
def test_too_few_candles_are_rejected(candles):
    with pytest.raises(ValueError):
        cb.simulate_cycle_compounding(candles)
