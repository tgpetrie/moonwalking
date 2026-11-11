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


def pilot_window(rows, *, latency=0, fee="100", slip="0"):
    spec = scenario()
    spec.update(
        schema_version="2.0",
        window_start_ms=0,
        window_end_ms=rows[-1][0],
        poll_interval_ms=1000,
        decision_latency_ms=latency,
        max_stale_ms=2000,
        max_gap_ms=5000,
        cost_basis_verified=True,
        cost_basis_coverage_pct="100",
        exit_fee_bps=fee,
        slippage_bps=slip,
        quotes=[
            {
                "observed_at_ms": observed,
                "exchange_time_ms": observed,
                "bid_usd": price,
                "bid_size": size,
            }
            for observed, price, size in rows
        ],
    )
    return spec


def test_tc01_hold_comparison_deltas():
    spec = pilot_window(
        [
            (i * 1000, price, "1")
            for i, price in enumerate([40000, 43200, 45000, 54000, 55000])
        ]
    )
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["hold_last_quote"]["estimated_net_proceeds_usd"] == Decimal("544.50")
    assert {
        rule: row["delta_vs_hold_usd"]
        for rule, row in result["hold_comparison"].items()
    } == {
        "rebound_pct": Decimal("-116.82"),
        "rebound_usd": Decimal("-99.00"),
        "net_profit_pct": Decimal("0"),
    }


def test_tc02_compounded_slippage_and_fee_boundary():
    spec = pilot_window(
        [
            (i * 1000, price, "1")
            for i, price in enumerate([40000, 45000, 55000, 55096, 55107])
        ],
        slip="100",
    )
    exit_row = simulate_exit(spec)["first_hypothetical_exits"]["net_profit_pct"]
    assert exit_row["trigger_quote"]["observed_at_ms"] == 4000
    assert exit_row["estimated_net_proceeds_usd"] == Decimal("540.103707")


def test_tc03_thin_bid_and_latency_gate():
    result = simulate_exit(
        pilot_window(
            [
                (0, 40000, "0.5"),
                (1000, 45000, "0.002"),
                (1600, 44000, "0.5"),
                (2000, 45200, "0.5"),
                (2200, 44000, "0.5"),
                (2600, 45100, "0.5"),
            ],
            latency=500,
        )
    )
    assert result["data_quality"]["window_valid"]
    for rule, triggered, executed, net in (
        ("rebound_pct", 1600, 2200, "435.60"),
        ("rebound_usd", 2000, 2600, "446.49"),
    ):
        exit_row = result["first_hypothetical_exits"][rule]
        assert exit_row["trigger_quote"]["observed_at_ms"] == triggered
        assert exit_row["execution_quote"]["observed_at_ms"] == executed
        assert exit_row["estimated_net_proceeds_usd"] == Decimal(net)
        assert exit_row["threshold_held_at_exec"]
        assert result["rule_diagnostics"][rule]["thin_trigger"] == 1


def test_tc04_zero_trigger_window_accounting():
    result = simulate_exit(
        pilot_window(
            [
                (0, 50000, "1"),
                (1000, 49000, "1"),
                (2000, 48000, "1"),
                (3000, 47000, "1"),
            ]
        )
    )
    assert result["data_quality"]["window_valid"]
    assert all(mark is None for mark in result["first_hypothetical_exits"].values())
    assert all(
        row["delta_vs_hold_usd"] == 0
        and row["estimated_net_proceeds_usd"] == Decimal("465.30")
        for row in result["hold_comparison"].values()
    )


def test_tc05_data_quality_rejections():
    spec = pilot_window(
        [
            (0, 50000, "1"),
            (3000, 40000, "1"),
            (45000, 50000, "1"),
        ]
    )
    spec["cost_basis_coverage_pct"] = "85"
    with pytest.raises(ValueError, match="SKIPPED_UNVERIFIED_COST_BASIS"):
        simulate_exit(spec)

    spec["cost_basis_coverage_pct"] = "100"
    spec["quotes"][1]["exchange_time_ms"] = 0
    result = simulate_exit(spec)
    assert result["data_quality"]["stale_quotes_count"] == 1
    assert result["data_quality"]["rejection_reason"] == "MAX_SINGLE_GAP_EXCEEDED"
    assert result["hold_last_quote"]["observed_low_bid_usd"] == 50000
    assert all(mark is None for mark in result["first_hypothetical_exits"].values())
    assert all(row is None for row in result["hold_comparison"].values())


def test_first_post_latency_quote_can_miss_or_lose_the_threshold():
    spec = pilot_window(
        [
            (0, 40000, "1"),
            (1000, 45000, "1"),
            (1500, 43000, "1"),
            (2000, 41500, "1"),
            (3000, 41000, "1"),
        ],
        latency=500,
    )
    result = simulate_exit(spec)
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["execution_quote"]["observed_at_ms"] == 1500
    assert not exit_row["threshold_held_at_exec"]
    assert exit_row["estimated_net_proceeds_usd"] == Decimal("425.70")

    spec["quotes"][2]["bid_size"] = "0.001"
    result = simulate_exit(spec)
    assert result["first_hypothetical_exits"]["rebound_usd"] is None
    assert result["rule_diagnostics"]["rebound_usd"]["execution_unavailable"] == 1


def test_hold_endpoint_uses_observed_and_exchange_age_at_window_end():
    spec = pilot_window([(0, 40000, "1"), (1000, 41000, "1"), (2900, 42000, "1")])
    spec["window_end_ms"] = 3000
    spec["quotes"][2]["exchange_time_ms"] = 950
    result = simulate_exit(spec)
    assert result["data_quality"]["rejection_reason"] == "ENDPOINT_UNAVAILABLE"
    assert result["hold_last_quote"] is None
