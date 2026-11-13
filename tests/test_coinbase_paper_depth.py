from decimal import Decimal
import inspect
import urllib.error

import pytest

from scripts import coinbase_paper_depth_collect as collector
from scripts.coinbase_paper_depth import (
    DEPTH_SCHEMA,
    NOT_OFFICIAL,
    estimate_sell_proceeds,
    simulate_depth_exit,
)
from scripts.coinbase_paper_exit import (
    BPS,
    PILOT_SETTINGS,
    PILOT_WINDOW_MS,
    _mark,
)

DEEP = [(40000, "1")]
LADDER = [(45000, "0.01"), (44900, "0.01"), (44800, "0.05")]


def depth_window(rows, *, latency=500, quantity="0.03", cost="1500", fee="100",
                 slip="0"):
    """rows: (observed_ms, ladder) or (observed_ms, "UNAVAILABLE")."""
    quotes = []
    for observed, ladder in rows:
        if ladder == "UNAVAILABLE":
            quotes.append({"observed_at_ms": observed, "quote_status": "UNAVAILABLE"})
            continue
        quotes.append(
            {
                "observed_at_ms": observed,
                "exchange_time_ms": observed,
                "bids": [{"price": str(p), "size": s} for p, s in ladder],
            }
        )
    return {
        "schema_version": DEPTH_SCHEMA,
        "window_start_ms": 0,
        "window_end_ms": rows[-1][0],
        **PILOT_SETTINGS,
        "decision_latency_ms": latency,
        "product_id": "BTC-USD",
        "quantity": quantity,
        "entry_cost_usd": cost,
        "exit_fee_bps": fee,
        "slippage_bps": slip,
        "thresholds": {"rebound_usd": 50, "rebound_pct": 8, "net_profit_pct": 8},
        "synthetic_position": True,
        "quotes": quotes,
    }


def levels(ladder):
    return [(Decimal(str(p)), Decimal(s)) for p, s in ladder]


def test_exit_spans_multiple_bid_levels_with_fees():
    result = simulate_depth_exit(
        depth_window(
            [
                (0, DEEP),
                (1000, LADDER),
                (1500, LADDER),
                (2000, [(41000, "1")]),
                (3000, [(41000, "1")]),
            ]
        )
    )
    assert result["data_quality"]["window_valid"]
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["trigger_quote"]["observed_at_ms"] == 1000
    assert exit_row["observed_at_ms"] == 1500
    depth = exit_row["depth"]
    assert depth["status"] == "FILLED"
    assert depth["levels_consumed"] == 3
    # 0.01 @ 45000 + 0.01 @ 44900 + 0.01 @ 44800
    assert depth["gross_proceeds_usd"] == Decimal("1347.00")
    assert depth["estimated_vwap_usd"] == Decimal("44900")
    assert depth["fee_usd"] == Decimal("13.4700")
    assert depth["estimated_net_proceeds_usd"] == Decimal("1333.5300")
    # The pilot's top-bid estimate would have claimed three dollars more.
    assert depth["top_bid_only_gross_usd"] == Decimal("1350.00")
    assert depth["depth_cost_vs_top_bid_usd"] == Decimal("3.00")
    comparison = result["hold_comparison"]["rebound_usd"]
    # Hold: 0.03 @ 41000 less 1% fee = 1217.70
    assert comparison["delta_vs_hold_usd"] == Decimal("115.83")
    assert result["hold_comparison_status"]["net_profit_pct"] == "AVAILABLE"
    assert result["hold_comparison"]["net_profit_pct"]["delta_vs_hold_usd"] == 0


def test_top_level_fill_matches_the_pilot_mark():
    fill = estimate_sell_proceeds(
        levels([(45000, "1")]), Decimal("0.03"), Decimal(60) / BPS, Decimal(25) / BPS
    )
    pilot = _mark(
        0, Decimal(45000), Decimal(45000), 0,
        Decimal("0.03"), Decimal(1), Decimal(60) / BPS, Decimal(25) / BPS,
    )
    assert fill["levels_consumed"] == 1
    assert fill["estimated_net_proceeds_usd"] == pilot["estimated_net_proceeds_usd"]
    assert fill["depth_cost_vs_top_bid_usd"] == 0


def test_insufficient_depth_is_explicit_and_withholds_proceeds():
    fill = estimate_sell_proceeds(
        levels([(45000, "0.01"), (44900, "0.005")]), Decimal("0.03"),
        Decimal("0.01"), Decimal(0),
    )
    assert fill["status"] == "INSUFFICIENT_DEPTH"
    assert fill["levels_consumed"] == 2
    assert fill["fillable_quantity"] == Decimal("0.015")
    assert fill["depth_shortfall_quantity"] == Decimal("0.015")
    assert fill["fillable_gross_proceeds_usd"] == Decimal("674.500")
    assert fill["estimated_net_proceeds_usd"] is None


def test_execution_quote_with_insufficient_depth_leaves_outcome_unknown():
    result = simulate_depth_exit(
        depth_window(
            [
                (0, DEEP),
                (1000, LADDER),
                (1500, [(45000, "0.01")]),
                (2000, [(41000, "1")]),
                (3000, [(41000, "1")]),
            ]
        )
    )
    assert result["data_quality"]["window_valid"]
    assert result["data_quality"]["insufficient_depth_quotes_count"] == 1
    diagnostics = result["rule_diagnostics"]["rebound_usd"]
    first = diagnostics["first_execution"]
    assert (first["status"], first["reason"]) == (
        "missed",
        "EXECUTION_INSUFFICIENT_DEPTH",
    )
    assert diagnostics["execution_insufficient_depth"] == 1
    assert result["first_hypothetical_exits"]["rebound_usd"] is None
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"


def test_trigger_without_depth_does_not_execute():
    result = simulate_depth_exit(
        depth_window(
            [
                (0, DEEP),
                (1000, [(45000, "0.01")]),
                (2000, [(41000, "1")]),
                (3000, [(41000, "1")]),
            ]
        )
    )
    diagnostics = result["rule_diagnostics"]["rebound_usd"]
    assert diagnostics["insufficient_depth_trigger"] == 1
    assert diagnostics["first_execution"] == {"status": "none"}
    assert result["first_hypothetical_exits"]["rebound_usd"] is None


def test_trigger_followed_by_unavailable_execution_quote():
    result = simulate_depth_exit(
        depth_window(
            [
                (0, DEEP),
                (1000, LADDER),
                (1500, "UNAVAILABLE"),
                (2000, [(41000, "1")]),
                (3000, LADDER),
                (3500, LADDER),
                (4000, [(41000, "1")]),
            ]
        )
    )
    assert result["data_quality"]["window_valid"]
    assert result["data_quality"]["unavailable_quotes_count"] == 1
    diagnostics = result["rule_diagnostics"]["rebound_usd"]
    first = diagnostics["first_execution"]
    assert (first["status"], first["reason"]) == ("missed", "QUOTE_UNAVAILABLE")
    assert first["trigger_quote"]["observed_at_ms"] == 1000
    assert first["execution_observed_at_ms"] == 1500
    assert diagnostics["execution_unavailable"] == 1
    # A later trigger executes, but cannot erase the unknown first order.
    exit_row = result["first_hypothetical_exits"]["rebound_usd"]
    assert exit_row["trigger_quote"]["observed_at_ms"] == 3000
    assert exit_row["prior_missed_executions"] == 1
    assert result["hold_comparison"]["rebound_usd"] is None
    assert result["hold_comparison_status"]["rebound_usd"] == "FIRST_EXECUTION_UNKNOWN"


def test_execution_book_must_be_newer_than_trigger_book():
    spec = depth_window(
        [(0, DEEP), (1000, LADDER), (1500, LADDER), (2000, DEEP), (3000, DEEP)]
    )
    spec["quotes"][2]["exchange_time_ms"] = 1000
    first = simulate_depth_exit(spec)["rule_diagnostics"]["rebound_usd"][
        "first_execution"
    ]
    assert first["reason"] == "BOOK_NOT_AFTER_TRIGGER"


def test_four_hour_synthetic_depth_run_is_never_official():
    spec = depth_window(
        [(time, DEEP) for time in range(0, PILOT_WINDOW_MS + 1, 1000)]
    )
    result = simulate_depth_exit(spec)
    assert result["data_quality"]["window_valid"]
    assert result["declared_settings"] == PILOT_SETTINGS
    assert result["official_pilot_result"] is False
    assert result["official_pilot_result_blocked_reason"] == NOT_OFFICIAL


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"synthetic_position": False}, "synthetic positions only"),
        ({"schema_version": "2.0"}, "depth-prototype-1"),
    ],
)
def test_refuses_account_backed_or_pilot_tapes(change, error):
    spec = depth_window([(0, DEEP), (1000, DEEP)])
    spec.update(change)
    with pytest.raises(ValueError, match=error):
        simulate_depth_exit(spec)


def test_rejects_a_bid_ladder_that_does_not_descend():
    spec = depth_window([(0, [(40000, "1"), (40000, "1")]), (1000, DEEP)])
    with pytest.raises(ValueError, match="descend"):
        simulate_depth_exit(spec)


def test_collector_records_the_public_ladder():
    def fetch(product_id, depth):
        assert (product_id, depth) == ("BTC-USD", 3)
        return {
            "pricebook": {
                "product_id": "BTC-USD",
                "time": "2026-11-12T00:00:01.250000+00:00",
                "bids": [
                    {"price": "45000", "size": "0.01"},
                    {"price": "44900", "size": "0.02"},
                ],
            }
        }

    quote = collector.poll_depth("BTC-USD", 3, now_ms=lambda: 7, fetch=fetch)
    assert quote["observed_at_ms"] == 7
    assert quote["exchange_time_ms"] == 1_794_441_601_250
    assert [level["price"] for level in quote["bids"]] == ["45000", "44900"]


def test_collector_marks_a_failed_request_unavailable():
    def fetch(product_id, depth):
        raise urllib.error.URLError("offline")

    quote = collector.poll_depth("BTC-USD", 3, now_ms=lambda: 9, fetch=fetch)
    assert quote == {"observed_at_ms": 9, "quote_status": "UNAVAILABLE"}


def test_collector_is_credential_free():
    source = inspect.getsource(collector)
    for marker in (
        "COINBASE_API_KEY",
        "os.environ",
        "getenv",
        "CoinbaseAdvancedTradeClient",
        "portfolio_mode",
        "Authorization",
    ):
        assert marker not in source
    assert collector.PUBLIC_BOOK.endswith("/brokerage/market/product_book")
