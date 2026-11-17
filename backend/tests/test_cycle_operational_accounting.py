"""Independent fee, inventory and snapshot checks for the paper cycle ledger."""

import pytest

from agents.store import AgentStore
from agents.trading_costs import cost_model, paper_sale


def save(ledger, record, timestamp, execution=None):
    ledger.route_proposal(
        {"agent": "cycle_strategist", "product_id": "SOL-USD", "symbol": "SOL", **record},
        lambda *args: ("auto_executed_dry_run" if execution else "approved", execution),
        clock=lambda: timestamp,
    )


def test_fee_inclusive_reload_and_remaining_inventory_match_cash_conservation(tmp_path):
    ledger = AgentStore(tmp_path / "ledger.sqlite")
    model = cost_model(60, 10)
    # Sell 4 of 10 SOL at a 100 reference. Pay 0.1% slippage and 0.6% fees.
    proceeds = 397.20
    save(ledger, {
        "proposal_id": "trim", "action": "TRIM_TO_USDC", "side": "sell",
        "reference_price": 100, "cost_model": model, "trim_pct": 40,
        "evidence": {"held_quantity": 10},
        "reload_plan": {
            "available": True, "trim_quantity": 4, "freed_usdc": proceeds,
            "tranches": [{"index": 1, "level": 80, "usdc": proceeds}],
        },
    }, 100)
    save(ledger, {
        "proposal_id": "reload", "action": "RELOAD_ACCUMULATE", "side": "buy",
        "reference_price": 80, "cost_model": model,
        "evidence": {
            "reload_allocation_version": 1,
            "reload_fills": [{"plan_id": "trim", "tranche": 1, "usdc": 100}],
        },
    }, 200)
    snapshot = {"snapshot_id": "daily", "as_of_ts": 86400, "timeframe": "1d"}
    summary = ledger.get_compounding_summary({"SOL": 70}, market_snapshot=snapshot)
    bought = (100 / 1.006) / 80.08
    assert summary["remaining_inventory_by_symbol"] == {"SOL": pytest.approx(6 + bought)}
    assert summary["remaining_cash_usd"] == summary["freed_usdc_available"] == 297.20
    assert summary["remaining_inventory_value_usd"] == round((6 + bought) * 70, 2)
    assert summary["strategy_value_usd"] == round((6 + bought) * 70 + 297.20, 2)
    assert summary["hold_value_usd"] == 700
    assert summary["net_value_vs_hold_usd"] == round((6 + bought) * 70 + 297.20 - 700, 2)
    assert summary["realized_extra_coins_by_symbol"]["SOL"] == pytest.approx(bought - 4 * 100 / proceeds)
    assert summary["fees_deducted_usd"] == round(399.6 * .006 + 100 - 100 / 1.006, 2)
    assert summary["slippage_deducted_usd"] == round(.4 + bought * .08, 2)
    assert summary["legacy_costs_unrecorded"] == []
    assert summary["mark_snapshot"] == snapshot

    # A rally can underperform holding. Its signed value remains visible.
    rally = ledger.get_compounding_summary({"SOL": 200})
    assert rally["net_value_vs_hold_usd"] < 0
    assert rally["drawdown_avoided_usd"] == 0
    missing = ledger.get_compounding_summary()
    assert missing["valuation_complete"] is False and missing["unpriced_symbols"] == ["SOL"]
    assert missing["strategy_value_usd"] is None and missing["net_value_vs_hold_usd"] is None
    assert ledger.get_compounding_summary({"SOL": 70})["remaining_cash_usd"] == 297.20


def test_recorded_execution_costs_are_deducted_once_and_stop_retires_remaining_inventory(tmp_path):
    ledger = AgentStore(tmp_path / "ledger.sqlite")
    model = cost_model(60, 10)
    sale = paper_sale(100, 4, model)
    save(ledger, {
        "proposal_id": "trim", "action": "TRIM_TO_USDC", "side": "sell",
        "reference_price": 110, "cost_model": model,
        "evidence": {"held_quantity": 10},
        "reload_plan": {
            "available": True, "trim_quantity": 4, "freed_usdc": 440,
            "tranches": [{"index": 1, "level": 80, "usdc": 440}],
        },
    }, 100, {"base_size": 4, **sale, "cost_model": model})
    opened = ledger.get_compounding_summary({"SOL": 70})
    assert opened["freed_usdc_available"] == 397.20
    assert opened["remaining_cash_usd"] == 397.20
    assert opened["fees_deducted_usd"] == round(sale["fee_usd"], 2)
    save(ledger, {
        "proposal_id": "stop", "action": "PROTECTIVE_STOP", "side": "sell",
        "reference_price": 90, "cost_model": model, "evidence": {"quantity": 10, "held_quantity": 10},
    }, 300)
    # Overlapping exits retire only the remaining six coins.
    summary = ledger.get_compounding_summary({"SOL": 70})
    assert summary["remaining_inventory_by_symbol"] == {"SOL": 0}
    assert summary["remaining_inventory_value_usd"] == 0
    assert summary["remaining_cash_usd"] == pytest.approx(397.20 + paper_sale(90, 6, model)["proceeds_usd"])


@pytest.mark.parametrize("bad", [True, -1, float("nan"), float("inf"), 10000])
def test_invalid_costs_are_rejected(bad):
    with pytest.raises(ValueError):
        cost_model(bad, 0)


def test_overlapping_historical_ladders_report_the_cash_shortfall(tmp_path):
    ledger = AgentStore(tmp_path / "ledger.sqlite")
    for i in range(2):
        save(ledger, {
            "proposal_id": f"trim-{i}", "action": "TRIM_TO_USDC", "side": "sell",
            "reference_price": 100, "cost_model": cost_model(),
            "evidence": {"held_quantity": 10},
            "reload_plan": {
                "available": True, "trim_quantity": 10, "freed_usdc": 1000,
                "tranches": [{"index": 1, "level": 80, "usdc": 1000}],
            },
        }, i + 100)
    summary = ledger.get_compounding_summary({"SOL": 80})
    assert summary["remaining_cash_usd"] == summary["freed_usdc_available"] == 1000
    assert summary["reload_funding_shortfall_by_symbol"] == {"SOL": 1000}
    assert "SOL" not in summary["projected_extra_coins_by_symbol"]
