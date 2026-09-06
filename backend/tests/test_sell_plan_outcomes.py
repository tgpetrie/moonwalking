import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sell_plan_outcomes import SellPlanOutcomeStore


def _plan():
    return {
        "available": True,
        "product_id": "BTC-USD",
        "current_price": 100,
        "stop": {"trigger_price": 95, "limit_price": 94.5},
        "profit": {"measurement_target_price": 110},
        "market_structure": {"support": 96, "resistance": 110},
        "methodology": {"version": "sell_levels_v1"},
    }


def test_reopening_same_hour_does_not_manufacture_more_evidence(tmp_path):
    store = SellPlanOutcomeStore(tmp_path / "plans.sqlite")
    first = store.record_plan(_plan(), now_ts=3_600)
    second = store.record_plan(_plan(), now_ts=3_900)

    assert first == second
    assert store.history("BTC")["total_plans"] == 1


def test_records_target_as_first_boundary(tmp_path):
    store = SellPlanOutcomeStore(tmp_path / "plans.sqlite")
    store.record_plan(_plan(), now_ts=3_600)
    store.observe({"BTC-USD": 111}, now_ts=3_700)

    history = store.history("BTC-USD")
    assert history["outcomes"] == {
        "target_first": 1,
        "stop_first": 0,
        "expired": 0,
    }
    assert history["history"][0]["outcome"] == "target_first"


def test_records_stop_as_first_boundary(tmp_path):
    store = SellPlanOutcomeStore(tmp_path / "plans.sqlite")
    store.record_plan(_plan(), now_ts=3_600)
    store.observe({"BTC": 94}, now_ts=3_700)

    history = store.history("BTC")
    assert history["outcomes"]["stop_first"] == 1
    assert history["history"][0]["max_adverse_pct"] == -6


def test_expires_without_inventing_a_boundary_hit(tmp_path):
    store = SellPlanOutcomeStore(tmp_path / "plans.sqlite")
    store.horizon_seconds = 3_600
    store.record_plan(_plan(), now_ts=3_600)
    store.observe({"BTC": 101}, now_ts=7_201)

    history = store.history("BTC")
    assert history["outcomes"]["expired"] == 1
    assert history["target_first_rate"] is None
    assert history["measurement_status"] == "collecting"
