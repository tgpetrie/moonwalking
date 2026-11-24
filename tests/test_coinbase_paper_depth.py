from datetime import datetime, timezone
from decimal import Decimal
import inspect
import json
import urllib.error

import pytest

from scripts import coinbase_paper_depth_collect as collector
from backend.paper_fills import FILLED
from scripts.coinbase_paper_depth import (
    DEPTH_SCHEMA,
    NOT_OFFICIAL,
    simulate_depth_exit,
)
from scripts.coinbase_paper_exit import (
    PILOT_SETTINGS,
    PILOT_WINDOW_MS,
)

DEEP = [(40000, "1")]
LADDER = [(45000, "0.01"), (44900, "0.01"), (44800, "0.05")]


def depth_window(
    rows, *, latency=500, quantity="0.03", cost="1500", fee="100", slip="0"
):
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
    assert depth["status"] == FILLED
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
    # A top bid with too little size behind it has no executable price, so
    # it neither triggers a rebound nor counts as a missed one.
    diagnostics = result["rule_diagnostics"]["rebound_usd"]
    assert "insufficient_depth_trigger" not in diagnostics
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


def test_threshold_at_execution_uses_the_low_seen_at_trigger():
    # Low $40,000; trigger at $45,000 (12.5%, $100); the book then dips to
    # $35,000 before execution at $42,000. Against the trigger's low that is
    # 5% and $40, below both rebound thresholds. Against the later low it
    # would read 20% and $140.
    result = simulate_depth_exit(
        depth_window(
            [
                (0, [(40000, "1")]),
                (1000, [(45000, "1")]),
                (1200, [(35000, "1")]),
                (1500, [(42000, "1")]),
                (2000, [(42000, "1")]),
                (3000, [(42000, "1")]),
            ],
            quantity="0.02",
        )
    )
    for rule in ("rebound_pct", "rebound_usd"):
        exit_row = result["first_hypothetical_exits"][rule]
        assert exit_row["trigger_quote"]["observed_at_ms"] == 1000
        assert exit_row["trigger_quote"]["observed_low_bid_usd"] == 40000
        assert exit_row["observed_at_ms"] == 1500
        assert exit_row["top_bid_usd"] == 42000
        assert exit_row["observed_low_bid_usd"] == 40000
        assert exit_row["rebound_pct"] == Decimal("5")
        assert exit_row["rebound_usd"] == Decimal("40")
        # The running low did fall; it just isn't the reference.
        assert exit_row["execution_quote"]["observed_low_bid_usd"] == 35000
        assert exit_row["execution_quote"]["rebound_pct"] == Decimal("20")
        assert exit_row["threshold_held_at_exec"] is False


def test_four_hour_synthetic_depth_run_is_never_official():
    spec = depth_window([(time, DEEP) for time in range(0, PILOT_WINDOW_MS + 1, 1000)])
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


# ─── Stage 2: rebounds measured on the executable price ─────────────────────


def test_a_dust_top_bid_jump_is_not_an_executable_rebound():
    # 0.0001 BTC bid at $45,000 above a flat book near $40,100. Against the
    # $40,000 low the top bid alone reads 12.5% and $150 for 0.03 BTC; what a
    # 0.03 BTC sale would actually get is about $40,116.
    spike = [(45000, "0.0001"), (40100, "1")]
    result = simulate_depth_exit(
        depth_window(
            [(0, DEEP), (1000, DEEP), (2000, spike), (2500, spike), (3000, spike)]
        )
    )
    assert result["data_quality"]["window_valid"]
    exits = result["first_hypothetical_exits"]
    assert exits["rebound_usd"] is None and exits["rebound_pct"] is None
    hold = result["hold_last_quote"]
    executable = (
        Decimal(45000) * Decimal("0.0001") + Decimal(40100) * Decimal("0.0299")
    ) / Decimal("0.03")
    assert hold["top_bid_usd"] == 45000
    assert hold["executable_price_usd"] == executable
    assert hold["observed_low_bid_usd"] == 40000
    assert hold["rebound_pct"] == 100 * (executable - 40000) / 40000
    assert hold["rebound_usd"] == (executable - 40000) * Decimal("0.03")
    assert hold["rebound_pct"] < 1


def test_a_real_rebound_in_the_executable_price_still_triggers():
    deep_rally = [(43400, "0.02"), (43300, "1")]
    result = simulate_depth_exit(
        depth_window(
            [(0, DEEP), (1000, deep_rally), (1500, deep_rally), (2000, deep_rally)]
        )
    )
    exit_row = result["first_hypothetical_exits"]["rebound_pct"]
    # (0.02 @ 43400 + 0.01 @ 43300) / 0.03 = 43366.67, 8.4% over $40,000.
    executable = (
        Decimal(43400) * Decimal("0.02") + Decimal(43300) * Decimal("0.01")
    ) / Decimal("0.03")
    assert exit_row["trigger_quote"]["executable_price_usd"] == executable
    assert exit_row["rebound_pct"] == 100 * (executable - 40000) / 40000
    assert exit_row["threshold_held_at_exec"] is True


def test_a_thin_first_quote_does_not_set_the_running_low():
    # A thin $35,000 first quote would make $42,000 look like a 20% / $140
    # rebound on 0.02 BTC. Against the real $40,000 low it is 5% / $40.
    thin = [(35000, "0.001")]
    result = simulate_depth_exit(
        depth_window(
            [(0, thin), (1000, DEEP), (2000, [(42000, "1")]), (3000, [(42000, "1")])],
            quantity="0.02",
        )
    )
    assert result["first_hypothetical_exits"]["rebound_pct"] is None
    assert result["first_hypothetical_exits"]["rebound_usd"] is None
    hold = result["hold_last_quote"]
    assert hold["observed_low_bid_usd"] == 40000
    assert hold["low_observed_at_ms"] == 1000
    assert result["data_quality"]["insufficient_depth_quotes_count"] == 1


def test_a_window_that_opens_thin_has_no_low_until_a_fillable_quote():
    thin = [(35000, "0.001")]
    result = simulate_depth_exit(
        depth_window([(0, thin), (1000, thin), (2000, DEEP), (3000, DEEP)])
    )
    assert result["hold_last_quote"]["observed_low_bid_usd"] == 40000
    assert result["hold_last_quote"]["low_observed_at_ms"] == 2000
    assert all(
        exit_row is None for exit_row in result["first_hypothetical_exits"].values()
    )


# ─── collector: fee source and an end-to-end replay ─────────────────────────


def _spec(**changes):
    values = {
        "product_id": "BTC-USD",
        "quantity": "0.01",
        "entry_cost_usd": "700",
        "exit_fee_bps": None,
        "slippage_bps": "10",
        "duration_seconds": 5,
        "levels": 50,
        "start_ms": 1_794_441_600_000,
    }
    values.update(changes)
    return collector.build_spec(**values)


def test_the_collector_defaults_the_fee_to_the_configured_cost_model(monkeypatch):
    monkeypatch.delenv("MW_CYCLE_FEE_BPS", raising=False)
    spec = _spec()
    assert (spec["exit_fee_bps"], spec["fee_source"]) == ("60.0", "configured_default")
    monkeypatch.setenv("MW_CYCLE_FEE_BPS", "75")
    assert _spec()["exit_fee_bps"] == "75.0"
    declared = _spec(exit_fee_bps="40")
    assert (declared["exit_fee_bps"], declared["fee_source"]) == ("40", "declared")
    assert declared["synthetic_position"] is True
    assert declared["window_end_ms"] - declared["window_start_ms"] == 5_000


def test_a_public_depth_tape_replays_end_to_end_and_is_never_official():
    start = 1_794_441_600_000
    clock = {"now": start - 400}

    def now_ms():
        return clock["now"]

    def sleep(seconds):
        clock["now"] += round(seconds * 1000)

    def fetch(product_id, depth):
        clock["now"] += 120
        stamp = datetime.fromtimestamp((clock["now"] - 300) / 1000, timezone.utc)
        return {
            "pricebook": {
                "product_id": product_id,
                "time": stamp.isoformat(),
                "bids": [
                    {"price": "45000", "size": "0.004"},
                    {"price": "44990", "size": "0.004"},
                    {"price": "44980", "size": "0.5"},
                ],
            }
        }

    spec = _spec(exit_fee_bps="60", start_ms=start)
    spec["quotes"] = collector.collect(
        "BTC-USD",
        start,
        spec["window_end_ms"],
        50,
        now_ms=now_ms,
        sleep=sleep,
        fetch=fetch,
    )
    result = simulate_depth_exit(json.loads(json.dumps(spec)))
    assert result["data_quality"]["window_valid"]
    assert result["data_quality"]["valid_poll_slots"] == 5
    assert result["official_pilot_result"] is False
    assert result["official_pilot_result_blocked_reason"] == NOT_OFFICIAL
    depth = result["hold_last_quote"]["depth"]
    assert depth["status"] == FILLED and depth["levels_consumed"] == 3
    assert set(result["hold_comparison_status"].values()) == {"AVAILABLE"}
