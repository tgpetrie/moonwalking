"""The one Decimal sell estimate shared by the pilot replay and the executor."""

from decimal import ROUND_DOWN, Decimal

import pytest

from backend.paper_fills import (
    FILLED,
    INSUFFICIENT_BOOK_DEPTH,
    book_levels,
    estimate_sell_proceeds,
    rate_from_bps,
    sell_at_price,
)
from agents.trading_costs import cost_model, paper_sale
from scripts.coinbase_paper_exit import _mark

D = Decimal
LADDER = [("45000", "0.01"), ("44900", "0.01"), ("44800", "0.05")]


def test_single_level_matches_the_pilot_mark_and_the_strategist_sale():
    fee, slip = rate_from_bps(60), rate_from_bps(25)
    fill = estimate_sell_proceeds(
        book_levels([("45000", "1")]), D("0.03"), fee_rate=fee, slippage_rate=slip
    )
    pilot = _mark(0, D(45000), D(45000), 0, D("0.03"), D(1), fee, slip)
    assert fill["status"] == FILLED
    assert fill["levels_consumed"] == 1
    assert fill["estimated_sell_price_usd"] == pilot["estimated_sell_price_usd"]
    assert fill["estimated_net_proceeds_usd"] == pilot["estimated_net_proceeds_usd"]
    assert fill["depth_cost_vs_top_bid_usd"] == 0
    # The strategist's float sale rounds the same net down to whole cents.
    sale = paper_sale(45000, 0.03, cost_model(60, 25))
    cents = fill["estimated_net_proceeds_usd"].quantize(D("0.01"), rounding=ROUND_DOWN)
    assert sale["proceeds_usd"] == float(cents)
    assert sale["fill_price"] == float(fill["estimated_sell_price_usd"])
    assert sale["fee_usd"] == pytest.approx(float(fill["fee_usd"]))


def test_sell_at_price_is_a_single_covering_level():
    fill = sell_at_price(D("43200"), D("0.01"), fee_rate=D("0.01"), slippage_rate=D(0))
    assert fill["estimated_net_proceeds_usd"] == D("427.68")


def test_a_sale_across_three_bid_levels():
    fill = estimate_sell_proceeds(
        book_levels(LADDER), D("0.03"), fee_rate=rate_from_bps(100), slippage_rate=D(0)
    )
    assert fill["status"] == FILLED
    assert fill["levels_consumed"] == 3
    assert fill["gross_proceeds_usd"] == D("1347.00")
    assert fill["estimated_vwap_usd"] == D("44900")
    assert fill["fee_usd"] == D("13.4700")
    assert fill["estimated_net_proceeds_usd"] == D("1333.5300")
    assert fill["top_bid_only_gross_usd"] == D("1350.00")
    assert fill["depth_cost_vs_top_bid_usd"] == D("3.00")


def test_slippage_applies_on_top_of_the_walk_then_the_fee():
    fill = estimate_sell_proceeds(
        book_levels(LADDER),
        D("0.03"),
        fee_rate=rate_from_bps(60),
        slippage_rate=rate_from_bps(10),
    )
    sell = D("44900") * (1 - D("0.001"))
    assert fill["estimated_sell_price_usd"] == sell
    assert fill["slippage_cost_usd"] == D("1347.00") * D("0.001")
    assert fill["estimated_net_proceeds_usd"] == sell * D("0.03") * (1 - D("0.006"))


def test_too_little_depth_is_explicit_and_withholds_proceeds():
    fill = estimate_sell_proceeds(
        book_levels([("45000", "0.01"), ("44900", "0.005")]),
        D("0.03"),
        fee_rate=D("0.01"),
        slippage_rate=D(0),
    )
    assert fill["status"] == INSUFFICIENT_BOOK_DEPTH == "insufficient_book_depth"
    assert fill["levels_consumed"] == 2
    assert fill["fillable_quantity"] == D("0.015")
    assert fill["depth_shortfall_quantity"] == D("0.015")
    assert fill["fillable_gross_proceeds_usd"] == D("674.500")
    assert fill["estimated_net_proceeds_usd"] is None
    assert fill["estimated_vwap_usd"] is None
    assert "gross_proceeds_usd" not in fill


def test_book_levels_accept_coinbase_dicts_and_exchange_lists():
    from_dicts = book_levels(
        [{"price": "45000", "size": "0.5"}, {"price": "44999.5", "size": "1"}]
    )
    from_lists = book_levels([["45000", "0.5", 3], ["44999.5", "1", 1]])
    assert from_dicts == from_lists == [(D("45000"), D("0.5")), (D("44999.5"), D("1"))]
    # Floats from JSON keep their printed value rather than binary noise.
    assert book_levels([[174.8, 0.1]]) == [(D("174.8"), D("0.1"))]


@pytest.mark.parametrize(
    ("bids", "best_ask", "message"),
    [
        ([], None, "at least one bid"),
        (None, None, "at least one bid"),
        ([("45000", "1"), ("45000", "1")], None, "descend"),
        ([("44000", "1"), ("45000", "1")], None, "descend"),
        ([("45000", "0")], None, "size must be positive"),
        ([("45000", "-1")], None, "size must be positive"),
        ([("0", "1")], None, "price must be positive"),
        ([("NaN", "1")], None, "price must be positive"),
        ([("45000", "Infinity")], None, "size must be positive"),
        ([("abc", "1")], None, "price must be positive"),
        ([True, "1"], None, "level"),
        ([("45000",)], None, "level"),
        ([("45000", "1")], "45000", "crossed"),
        ([("45000", "1")], "44999", "crossed"),
    ],
)
def test_bad_books_are_rejected(bids, best_ask, message):
    with pytest.raises(ValueError, match=message):
        book_levels(bids, best_ask=best_ask)


def test_an_uncrossed_ask_is_accepted():
    assert book_levels([("45000", "1")], best_ask="45000.01") == [(D("45000"), D("1"))]


@pytest.mark.parametrize("quantity", [D(0), D(-1), D("NaN")])
def test_quantity_must_be_positive(quantity):
    with pytest.raises(ValueError, match="quantity"):
        estimate_sell_proceeds(
            book_levels([("1", "1")]), quantity, fee_rate=D(0), slippage_rate=D(0)
        )


def test_rates_come_from_basis_points():
    assert rate_from_bps("60") == D("0.006")
    assert rate_from_bps(10.0) == D("0.001")
    assert rate_from_bps(D("0")) == 0
    for bad in (-1, 10000, "NaN", True, None, "abc"):
        with pytest.raises(ValueError, match="basis points"):
            rate_from_bps(bad)
