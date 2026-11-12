from copy import deepcopy
from decimal import Decimal

import pytest

from scripts.coinbase_paper_exit import PILOT_SETTINGS, PILOT_WINDOW_MS, simulate_exit


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
    assert set(result["hold_comparison_status"].values()) == {"AVAILABLE"}
    assert all(
        row == {"first_execution": {"status": "none"}}
        for row in result["rule_diagnostics"].values()
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
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"


def test_hold_endpoint_uses_observed_and_exchange_age_at_window_end():
    spec = pilot_window([(0, 40000, "1"), (1000, 41000, "1"), (2900, 42000, "1")])
    spec["window_end_ms"] = 3000
    spec["quotes"][2]["exchange_time_ms"] = 950
    result = simulate_exit(spec)
    assert result["data_quality"]["rejection_reason"] == "ENDPOINT_UNAVAILABLE"
    assert result["hold_last_quote"] is None


@pytest.mark.parametrize("lagged_exchange_ms", [900, 1000])
def test_execution_book_must_be_newer_than_the_trigger_book(lagged_exchange_ms):
    spec = pilot_window(
        [
            (0, 40000, "1"),
            (1000, 45000, "1"),
            (1500, 45000, "1"),
            (2500, 41000, "1"),
            (3000, 41000, "1"),
        ],
        latency=500,
    )
    spec["quotes"][2]["exchange_time_ms"] = lagged_exchange_ms
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    diagnostics = result["rule_diagnostics"]["rebound_usd"]
    assert diagnostics["execution_book_not_after_trigger"] == 1
    assert diagnostics["first_execution"]["status"] == "missed"
    assert diagnostics["first_execution"]["reason"] == "BOOK_NOT_AFTER_TRIGGER"
    assert diagnostics["first_execution"]["trigger_quote"]["observed_at_ms"] == 1000
    assert diagnostics["first_execution"]["execution_observed_at_ms"] == 1500
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["execution_quote"]["observed_at_ms"] == 2500
    assert exit_row["estimated_net_proceeds_usd"] == Decimal("405.90")
    assert exit_row["prior_missed_executions"] == 1
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"

    spec["quotes"][2]["exchange_time_ms"] = 1001
    result = simulate_exit(spec)
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["execution_quote"]["observed_at_ms"] == 1500
    assert exit_row["prior_missed_executions"] == 0
    comparison = result["hold_comparison"]["rebound_usd"]
    assert comparison["delta_vs_hold_usd"] == Decimal("39.60")


def test_zero_delay_may_execute_on_the_trigger_book():
    spec = pilot_window([(0, 40000, "1"), (1000, 45000, "1"), (2000, 41000, "1")])
    result = simulate_exit(spec)
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["execution_quote"]["observed_at_ms"] == 1000
    assert result["hold_comparison_status"]["rebound_usd"] == "AVAILABLE"


def test_missed_first_execution_is_not_credited_with_hold_proceeds():
    result = simulate_exit(
        pilot_window(
            [
                (0, 40000, "1"),
                (1000, 40000, "1"),
                (2000, 40000, "1"),
                (3000, 45000, "1"),
                (3600, 30000, "0.004"),
                (4000, 44900, "1"),
                (5000, 44900, "1"),
            ],
            latency=500,
        )
    )
    assert result["data_quality"]["window_valid"]
    assert result["hold_last_quote"]["estimated_net_proceeds_usd"] == Decimal("444.51")
    assert result["first_hypothetical_exits"]["rebound_usd"] is None
    first = result["rule_diagnostics"]["rebound_usd"]["first_execution"]
    assert (first["status"], first["reason"]) == ("missed", "QUOTE_THIN")
    assert first["trigger_quote"]["observed_at_ms"] == 3000
    assert first["execution_observed_at_ms"] == 3600
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"
    # net_profit_pct never triggers in this window: a genuine zero difference.
    assert result["hold_comparison"]["net_profit_pct"]["delta_vs_hold_usd"] == 0
    assert result["hold_comparison_status"]["net_profit_pct"] == "AVAILABLE"


def test_later_exit_does_not_erase_a_missed_first_execution():
    result = simulate_exit(
        pilot_window(
            [
                (0, 40000, "1"),
                (1000, 45000, "1"),
                (1500, 30000, "0.004"),
                (2000, 30500, "1"),
                (3000, 50000, "1"),
                (4000, 50000, "1"),
                (5000, 50000, "1"),
            ],
            latency=500,
        )
    )
    assert result["data_quality"]["window_valid"]
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["trigger_quote"]["observed_at_ms"] == 3000
    assert exit_row["estimated_net_proceeds_usd"] == Decimal("495.00")
    assert exit_row["prior_missed_executions"] == 1
    first = result["rule_diagnostics"]["rebound_usd"]["first_execution"]
    assert (first["status"], first["reason"]) == ("missed", "QUOTE_THIN")
    assert first["trigger_quote"]["observed_at_ms"] == 1000
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"


def test_trigger_with_no_quote_after_the_delay_is_unknown():
    result = simulate_exit(
        pilot_window(
            [(0, 40000, "1"), (1000, 40000, "1"), (2000, 45000, "1")], latency=500
        )
    )
    assert result["data_quality"]["window_valid"]
    first = result["rule_diagnostics"]["rebound_usd"]["first_execution"]
    assert (first["status"], first["reason"]) == ("missed", "NO_QUOTE_AFTER_DELAY")
    assert result["hold_comparison"]["rebound_usd"] is None


def official_window():
    return pilot_window([(i * 1000, 40000, "1") for i in range(6)], latency=500)


def test_official_pilot_settings_are_declared_and_reported():
    assert PILOT_SETTINGS == {
        "poll_interval_ms": 1000,
        "decision_latency_ms": 500,
        "max_stale_ms": 2000,
        "max_gap_ms": 5000,
    }
    spec = pilot_window(
        [(time, 40000, "1") for time in range(0, PILOT_WINDOW_MS + 1, 1000)],
        latency=500,
    )
    result = simulate_exit(spec)
    assert result["pilot_settings"] == {
        "declared": PILOT_SETTINGS,
        "official": PILOT_SETTINGS,
        "matches_official": True,
        "window_matches_official": True,
    }
    assert result["official_pilot_result"] is True

    spec["max_stale_ms"] = 29_000
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["pilot_settings"]["window_matches_official"] is True
    assert result["official_pilot_result"] is False
    spec["max_stale_ms"] = PILOT_SETTINGS["max_stale_ms"]

    spec["window_start_ms"] += 1000
    spec["window_end_ms"] += 1000
    for quote in spec["quotes"]:
        quote["observed_at_ms"] += 1000
        quote["exchange_time_ms"] += 1000
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["pilot_settings"]["matches_official"] is True
    assert result["pilot_settings"]["window_matches_official"] is False
    assert result["official_pilot_result"] is False

    spec["quotes"] = spec["quotes"][:2]
    spec["window_start_ms"] = 0
    spec["window_end_ms"] = PILOT_WINDOW_MS
    result = simulate_exit(spec)
    assert not result["data_quality"]["window_valid"]
    assert result["pilot_settings"]["window_matches_official"] is True
    assert result["official_pilot_result"] is False


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("poll_interval_ms", 5000),
        ("decision_latency_ms", 0),
        ("max_stale_ms", 29000),
        ("max_gap_ms", 30000),
    ],
)
def test_looser_declared_settings_cannot_be_an_official_pilot_result(setting, value):
    spec = official_window()
    spec[setting] = value
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["pilot_settings"]["declared"][setting] == value
    assert result["pilot_settings"]["matches_official"] is False
    assert result["official_pilot_result"] is False


def test_sparse_stale_custom_tape_replays_but_is_not_official():
    spec = pilot_window(
        [(t, 45000 if t >= 60_000 else 40000, "1") for t in range(0, 120_001, 30_000)]
    )
    spec.update(poll_interval_ms=30_000, max_stale_ms=29_000, max_gap_ms=30_000)
    for quote in spec["quotes"]:
        quote["exchange_time_ms"] = max(0, quote["observed_at_ms"] - 29_000)
    result = simulate_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["data_quality"]["valid_poll_slots"] == 4
    assert result["official_pilot_result"] is False
