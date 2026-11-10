from copy import deepcopy
from decimal import Decimal

import pytest

from scripts.coinbase_paper_exit import simulate_exit


def scenario():
    return {
        "product_id": "BTC-USD",
        "quantity": "0.01",
        "entry_cost_usd": "500",
        "exit_fee_bps": "100",
        "slippage_bps": "0",
        "thresholds": {"rebound_usd": 50, "rebound_pct": 8, "net_profit_pct": 8},
        "quotes": [
            {"observed_at_ms": i * 1000, "bid_usd": bid}
            for i, bid in enumerate(["40000", "43200", "45000", "54000", "55000"])
        ],
    }


def test_distinguishes_rebound_from_profit_after_costs():
    exits = simulate_exit(scenario())["first_hypothetical_exits"]

    assert exits["rebound_pct"]["observed_at_ms"] == 1000
    assert exits["rebound_usd"]["observed_at_ms"] == 2000
    assert exits["rebound_usd"]["estimated_pnl_usd"] == Decimal("-54.50")
    assert exits["net_profit_pct"]["observed_at_ms"] == 4000
    assert exits["net_profit_pct"]["estimated_net_proceeds_usd"] == Decimal("544.50")


def test_future_low_cannot_move_earlier_exit():
    spec = scenario()
    original = simulate_exit(spec)
    spec["quotes"].append({"observed_at_ms": 5000, "bid_usd": "35000"})
    result = simulate_exit(spec)

    assert result["first_hypothetical_exits"] == original["first_hypothetical_exits"]
    assert result["hold_last_quote"]["observed_low_bid_usd"] == Decimal("35000")


def test_slippage_can_prevent_net_profit_trigger():
    spec = scenario()
    spec["slippage_bps"] = "100"
    exits = simulate_exit(spec)["first_hypothetical_exits"]

    assert exits["net_profit_pct"] is None
    assert exits["rebound_usd"]["observed_at_ms"] == 2000


@pytest.mark.parametrize(
    ("quote_change", "error"),
    [
        ({"observed_at_ms": 0}, "strictly increasing"),
        ({"observed_at_ms": True}, "strictly increasing"),
        ({"bid_usd": "NaN"}, "finite and positive"),
        ({"bid_usd": False}, "decimal number"),
        ({"bid_usd": 0}, "finite and positive"),
    ],
)
def test_rejects_unusable_quote_observations(quote_change, error):
    spec = deepcopy(scenario())
    spec["quotes"][1].update(quote_change)
    with pytest.raises(ValueError, match=error):
        simulate_exit(spec)
