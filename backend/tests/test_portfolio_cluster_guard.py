"""Tests for portfolio_cluster_guard: synthetic numbers only, no network."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import portfolio_cluster_guard as pcg

BTC_RETURNS = [0.02, -0.01, 0.03, -0.03, 0.01, -0.02] * 6


def closes(returns, start=100.0):
    out = [start]
    for value in returns:
        out.append(out[-1] * (1 + value))
    return out


BTC = closes(BTC_RETURNS, 50_000.0)
# Falls twice as hard as BTC on down days and rises half as much on up days.
FRAGILE = closes([r * 2 if r < 0 else r * 0.5 for r in BTC_RETURNS])


# ─── downside beta ────────────────────────────────────────────────────────────


def test_downside_beta_is_measured_on_btc_down_days_only():
    read = pcg.compute_downside_btc_beta(FRAGILE, BTC)
    assert read["available"] is True and read["observations"] == 36 and read["down_days"] == 18
    assert read["downside_available"] is True
    assert read["downside_beta"] == pytest.approx(2.0, abs=1e-4)
    assert read["downside_correlation"] == pytest.approx(1.0, abs=1e-4)
    # The full-sample beta blends the 2.0 down days with the 0.5 up days.
    assert 0.5 < read["beta"] < 2.0
    assert read["effective_downside_beta"] == read["downside_beta"]
    assert read["relative_drawdown_multiplier"] > 1.5


def test_an_asset_that_is_btc_has_beta_one_everywhere():
    read = pcg.compute_downside_btc_beta([c / 500 for c in BTC], BTC)
    assert read["beta"] == read["downside_beta"] == 1.0
    assert read["correlation"] == read["downside_correlation"] == 1.0
    assert read["relative_drawdown_multiplier"] == 1.0


def test_too_few_down_days_falls_back_to_the_full_sample_beta():
    read = pcg.compute_downside_btc_beta(FRAGILE, BTC, min_down_days=19)
    assert read["available"] is True and read["down_days"] == 18
    assert read["downside_beta"] is None and read["downside_available"] is False
    assert read["downside_correlation"] is None
    assert read["effective_downside_beta"] == read["beta"]


def test_betas_and_the_drawdown_multiplier_are_clamped():
    calm_btc = closes([r * 0.05 for r in BTC_RETURNS], 50_000.0)
    wild = closes([r * 0.05 * 40 for r in BTC_RETURNS])
    read = pcg.compute_downside_btc_beta(wild, calm_btc)
    assert read["beta"] == read["downside_beta"] == pcg.BETA_MAX == 5.0
    assert read["relative_drawdown_multiplier"] == pcg.DRAWDOWN_MULTIPLIER_MAX == 10.0
    inverse = closes([-r * 0.05 * 40 for r in BTC_RETURNS])
    assert pcg.compute_downside_btc_beta(inverse, calm_btc)["beta"] == pcg.BETA_MIN == -2.0


def test_unreadable_series_report_why_and_default_to_beta_one():
    flat = pcg.compute_downside_btc_beta(FRAGILE, [50_000.0] * len(FRAGILE))
    assert flat["available"] is False and flat["reason"] == "btc_did_not_move"
    assert flat["effective_downside_beta"] == 1.0 and flat["relative_drawdown_multiplier"] is None
    for asset, btc in (([], []), ([1.0], [1.0]), (None, BTC), ([1.0, 2.0], [None, "x"])):
        short = pcg.compute_downside_btc_beta(asset, btc)
        assert short["available"] is False and short["reason"] == "not_enough_history"
        assert short["beta"] is None and short["effective_downside_beta"] == 1.0


def test_series_are_aligned_at_their_ends_and_bad_closes_break_the_chain():
    base = pcg.compute_downside_btc_beta(FRAGILE, BTC)
    assert pcg.compute_downside_btc_beta([1.0, 9.0, 3.0] + FRAGILE, BTC) == base
    assert pcg.compute_downside_btc_beta(FRAGILE, [7.0] * 5 + BTC) == base
    holed = list(FRAGILE)
    holed[10] = None
    read = pcg.compute_downside_btc_beta(holed, BTC)
    # The bad day removes the return into it and the return out of it.
    assert read["observations"] == 34 and read["available"] is True
    for bad in (0, -5.0, float("nan"), "x", True):
        holed[10] = bad
        assert pcg.compute_downside_btc_beta(holed, BTC)["observations"] == 34


@pytest.mark.parametrize("value", [1, 0, True, 2.5, None])
def test_min_down_days_must_be_an_integer_of_two_or_more(value):
    with pytest.raises(ValueError):
        pcg.compute_downside_btc_beta(FRAGILE, BTC, min_down_days=value)


def test_beta_heat_multiplier_only_penalizes_betas_above_the_neutral_level():
    assert pcg.beta_heat_multiplier(0.4) == 1.0
    assert pcg.beta_heat_multiplier(1.25) == 1.0
    assert pcg.beta_heat_multiplier(2.5) == 2.0
    assert pcg.beta_heat_multiplier(100) == 4.0  # clamped to a beta of 5
    for unreadable in (None, "x", float("nan"), float("inf"), True):
        assert pcg.beta_heat_multiplier(unreadable) == 1.0


# ─── cluster and beta heat ────────────────────────────────────────────────────

EQUITY = 10_000.0


def held(symbol, cluster, risk_usd, **extra):
    return {"symbol": symbol, "category_id": cluster, "risk_usd": risk_usd, **extra}


def guard(existing, candidates, **limits):
    return pcg.evaluate_cluster_and_beta_heat(existing, candidates, equity_usd=EQUITY, **limits)


def reasons(result):
    return [(p["symbol"], p["suppression_reason"]) for p in result["suppressed_proposals"]]


def test_candidates_are_accepted_until_the_cluster_holds_two_coins():
    result = guard(
        [held("SOL", "layer-1", 100)],
        [held("AVAX", "layer-1", 50), held("NEAR", "layer-1", 10), held("LINK", "oracle", 80)],
    )
    assert [p["symbol"] for p in result["accepted_proposals"]] == ["AVAX", "LINK"]
    assert reasons(result) == [("NEAR", "cluster_count_cap_exceeded")]
    assert result["clusters"]["layer-1"] == {
        "symbols": ["SOL", "AVAX"], "position_count": 2,
        "risk_usd": 150.0, "risk_pct": 1.5, "beta_adjusted_risk_pct": 1.5,
    }
    assert result["existing_risk_pct"] == 1.0 and result["total_risk_pct"] == 2.3
    assert result["total_beta_adjusted_risk_pct"] == 2.3
    block = result["accepted_proposals"][0]["cluster_guard"]
    assert block == {
        "symbol": "AVAX", "cluster": "layer-1", "risk_usd": 50.0, "risk_pct": 0.5,
        "beta_multiplier": 1.0, "beta_adjusted_risk_pct": 0.5,
    }
    assert result["suppressed_proposals"][0]["cluster_guard"]["suppression_reason"] == "cluster_count_cap_exceeded"
    assert result["outcome_validated"] is False


def test_cluster_raw_heat_cap_is_inclusive_at_the_limit():
    over = guard([held("SOL", "layer-1", 150)], [held("AVAX", "layer-1", 60)])
    assert reasons(over) == [("AVAX", "cluster_heat_cap_exceeded")] and over["accepted_proposals"] == []
    assert over["clusters"]["layer-1"]["risk_pct"] == 1.5  # a suppressed candidate adds nothing
    exact = guard([held("SOL", "layer-1", 150)], [held("AVAX", "layer-1", 50)])
    assert reasons(exact) == [] and exact["clusters"]["layer-1"]["risk_pct"] == 2.0


def test_total_heat_is_beta_adjusted():
    existing = [held("WIF", "meme", 150, downside_beta=2.5)]  # 1.5% raw, 3.0% adjusted
    hot = guard(existing, [held("TAO", "ai", 150, downside_beta=2.5)])
    assert reasons(hot) == [("TAO", "beta_adjusted_heat_cap_exceeded")]
    assert hot["existing_risk_pct"] == 1.5 and hot["existing_beta_adjusted_risk_pct"] == 3.0
    guard_block = hot["suppressed_proposals"][0]["cluster_guard"]
    assert guard_block["beta_multiplier"] == 2.0 and guard_block["beta_adjusted_risk_pct"] == 3.0
    # The same raw risk with an ordinary beta fits: 3.0 + 1.5 <= 5.0.
    calm = guard(existing, [held("TAO", "ai", 150, downside_beta=1.0)])
    assert reasons(calm) == [] and calm["total_beta_adjusted_risk_pct"] == 4.5
    assert calm["total_risk_pct"] == 3.0
    # A missing or unreadable beta counts as 1.
    assert reasons(guard(existing, [held("TAO", "ai", 150, downside_beta="n/a")])) == []


def test_checks_run_in_order_count_then_cluster_heat_then_total_heat():
    existing = [held("SOL", "layer-1", 100, downside_beta=5.0), held("AVAX", "layer-1", 90, downside_beta=5.0)]
    # NEAR breaks all three limits; the count cap is the one reported.
    assert reasons(guard(existing, [held("NEAR", "layer-1", 500)])) == [("NEAR", "cluster_count_cap_exceeded")]
    # Adding to a coin already held skips the count cap, so cluster heat is reported.
    assert reasons(guard(existing, [held("SOL", "layer-1", 500)])) == [("SOL", "cluster_heat_cap_exceeded")]
    # Another cluster passes the first two and fails on total beta-adjusted heat (7.6% held).
    assert reasons(guard(existing, [held("LINK", "oracle", 10)])) == [("LINK", "beta_adjusted_heat_cap_exceeded")]


def test_adding_to_a_held_coin_does_not_count_as_a_new_position():
    existing = [held("SOL", "layer-1", 50), held("AVAX", "layer-1", 50)]
    result = guard(existing, [{"product_id": "sol-usd", "category_id": "Layer-1", "risk_usd": 50}])
    assert reasons(result) == []
    assert result["clusters"]["layer-1"]["symbols"] == ["SOL", "AVAX"]
    assert result["clusters"]["layer-1"]["risk_pct"] == 1.5


def test_earlier_candidates_count_against_later_ones():
    first, second = held("AVAX", "layer-1", 120), held("NEAR", "layer-1", 120)
    result = guard([], [first, second])
    assert [p["symbol"] for p in result["accepted_proposals"]] == ["AVAX"]
    assert reasons(result) == [("NEAR", "cluster_heat_cap_exceeded")]
    flipped = guard([], [second, first])
    assert [p["symbol"] for p in flipped["accepted_proposals"]] == ["NEAR"]
    # The inputs are not modified.
    assert "cluster_guard" not in first and "suppression_reason" not in second


def test_limits_can_be_changed():
    existing = [held("SOL", "layer-1", 100)]
    candidates = [held("AVAX", "layer-1", 50), held("NEAR", "layer-1", 40)]
    assert reasons(guard(existing, candidates, max_positions_per_cluster=3)) == []
    assert reasons(guard(existing, candidates, max_positions_per_cluster=1)) == [
        ("AVAX", "cluster_count_cap_exceeded"), ("NEAR", "cluster_count_cap_exceeded"),
    ]
    assert reasons(guard(existing, candidates, max_cluster_heat_pct=1.2)) == [
        ("AVAX", "cluster_heat_cap_exceeded"), ("NEAR", "cluster_heat_cap_exceeded"),
    ]
    assert reasons(guard(existing, candidates[:1], max_total_heat_pct=1.2)) == [
        ("AVAX", "beta_adjusted_heat_cap_exceeded"),
    ]


def test_risk_is_read_from_usd_percent_or_a_size_and_stop():
    candidates = [
        {"symbol": "A", "category_id": "a", "risk_usd": 100},
        {"symbol": "B", "category_id": "b", "risk_pct": 0.5},
        {"symbol": "C", "category_id": "c", "quantity": 10, "entry_price": 100, "stop_price": 90},
        {"symbol": "D", "category_id": "d", "notional_usd": 1000, "reference_price": 50, "stop_price": 45},
        {"symbol": "E", "category_id": "e", "sizing": {"risk_usd": 25}},
        {"symbol": "F", "category_id": "f", "sizing": {"suggested_notional_usd": 500}, "reference_price": 10, "stop_price": 9},
    ]
    result = guard([], candidates)
    assert reasons(result) == []
    assert [p["cluster_guard"]["risk_usd"] for p in result["accepted_proposals"]] == [100.0, 50.0, 100.0, 100.0, 25.0, 50.0]
    assert result["total_risk_pct"] == 4.25

    unreadable = [
        {"symbol": "G", "category_id": "g"},
        {"symbol": "H", "category_id": "h", "quantity": 10, "entry_price": 100, "stop_price": 100},
        {"symbol": "I", "category_id": "i", "risk_usd": -5, "reference_price": 10, "stop_price": 9},
        "junk",
    ]
    blocked = guard([], unreadable)
    assert reasons(blocked) == [("G", "risk_unavailable"), ("H", "risk_unavailable"), ("I", "risk_unavailable")]
    assert blocked["total_risk_pct"] == 0 and blocked["accepted_proposals"] == []
    assert set(pcg.SUPPRESSION_REASONS) >= {reason for _symbol, reason in reasons(blocked)}


def test_coins_without_a_cluster_stand_alone_and_positions_without_risk_still_count():
    loose = [{"symbol": "AAA", "risk_usd": 50}, {"symbol": "BBB", "risk_usd": 50}]
    result = guard([], loose, max_positions_per_cluster=1)
    assert reasons(result) == []
    assert set(result["clusters"]) == {"uncategorized:AAA", "uncategorized:BBB"}

    existing = [{"symbol": "SOL", "category_id": "layer-1"}, {"symbol": "AVAX", "cluster": "layer-1"}, None]
    crowded = guard(existing, [held("NEAR", "layer-1", 10)])
    assert reasons(crowded) == [("NEAR", "cluster_count_cap_exceeded")]
    assert crowded["positions_without_risk"] == ["SOL", "AVAX"] and crowded["existing_risk_pct"] == 0
    assert guard(None, None)["accepted_proposals"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"equity_usd": 0}, {"equity_usd": float("nan")}, {"equity_usd": "x"},
        {"equity_usd": 1000, "max_total_heat_pct": 0}, {"equity_usd": 1000, "max_cluster_heat_pct": -1},
        {"equity_usd": 1000, "max_positions_per_cluster": 0}, {"equity_usd": 1000, "max_positions_per_cluster": 1.5},
    ],
)
def test_invalid_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        pcg.evaluate_cluster_and_beta_heat([], [], **kwargs)
