import pytest

from agents.catalog import AGENT_CATALOG
from agents.runner import DEFAULT_AGENT_FACTORIES
from coinbase_execution_agent import (
    VALID_MODES,
    CoinbaseExecutionAgent,
    build_coinbase_v3_order_preview,
    compute_position_size,
    evaluate_1h_reclaim_ticket,
    evaluate_a1_momentum_ticket,
    evaluate_position_defense_ticket,
)


def _reclaim_context():
    return {
        "symbol": "BTC",
        "wave_analysis": {
            "available": True,
            "bias": "bullish",
            "active_pattern": "abc_in_progress",
            "status": "in_c_zone",
            "higher_tf_trend": "up",
            "wave_points": [
                {"label": "B", "price": 110},
                {"label": "C", "price": 99},
            ],
            "confluence_factors": [{"name": "ema_reclaim", "state": "present"}],
            "chart": {
                "candles": [
                    [1, 98, 102, 99, 100, 1],
                    [2, 99, 103, 101, 102, 1],
                ]
            },
        },
    }


def test_1h_reclaim_builds_stop_limit_ticket_from_validated_wave_and_turn_bar():
    ticket = evaluate_1h_reclaim_ticket(_reclaim_context())

    assert ticket["intent_type"] == "entry"
    assert ticket["side"] == "buy"
    assert ticket["entry_price"] == 102
    assert ticket["stop_trigger_price"] == 98.8515
    assert ticket["stop_limit_price"] == 98.6535
    assert ticket["target_price"] == 110
    assert ticket["rr_planned"] == round((110 - 102) / (102 - 98.6535), 2)


@pytest.mark.parametrize(
    "update",
    [
        {"higher_tf_trend": "opposed"},
        {"active_pattern": "abc_complete"},
        {"status": "awaiting_c_zone"},
        {"bias": "bearish"},
    ],
)
def test_1h_reclaim_rejects_wave_reads_that_miss_required_structure(update):
    context = _reclaim_context()
    context["wave_analysis"].update(update)

    assert evaluate_1h_reclaim_ticket(context) is None


def test_1h_reclaim_requires_bullish_confirmation_and_a_reclaim_cue():
    context = _reclaim_context()
    context["wave_analysis"]["confluence_factors"] = []

    assert evaluate_1h_reclaim_ticket(context) is None

    context = _reclaim_context()
    context["wave_analysis"]["chart"]["candles"][-1][4] = 100
    assert evaluate_1h_reclaim_ticket(context) is None


def test_1h_reclaim_accepts_only_a_prior_bar_at_the_c_low():
    context = _reclaim_context()
    context["wave_analysis"]["confluence_factors"] = []
    context["wave_analysis"]["chart"]["candles"][0][1] = 99
    assert evaluate_1h_reclaim_ticket(context) is not None
    context["wave_analysis"]["chart"]["candles"][0][1] = 99.1
    assert evaluate_1h_reclaim_ticket(context) is None


def test_1h_reclaim_rejects_opposed_higher_timeframe_factor():
    context = _reclaim_context()
    context["wave_analysis"]["confluence_factors"].append(
        {"name": "higher_tf_trend", "state": "opposed"}
    )

    assert evaluate_1h_reclaim_ticket(context) is None


def test_a1_momentum_requires_gate_clean_structure_and_no_finished_impulse():
    context = {
        "symbol": "ETH",
        "a1_gate_pass": True,
        "structure_posture": "1h_abc_clean",
        "current_price": 100,
        "support": 95,
        "ignition_base": 96,
        "resistance": 110,
        "wave_analysis": {
            "1h": {"active_pattern": "abc_in_progress", "bias": "bullish"},
            "15m": {"active_pattern": "abc_in_progress", "bias": "bullish"},
            "4h": {"active_pattern": "none", "bias": "bullish"},
        },
    }

    ticket = evaluate_a1_momentum_ticket(context)

    assert ticket["side"] == "buy"
    assert ticket["stop_trigger_price"] < 95
    assert ticket["stop_limit_price"] < ticket["stop_trigger_price"]
    assert ticket["target_price"] == 110

    for timeframe in ("15m", "1h", "4h"):
        context["wave_analysis"][timeframe] = {
            "active_pattern": "impulse_complete",
            "status": "complete",
            "bias": "bullish",
        }
        assert evaluate_a1_momentum_ticket(context) is None
        context["wave_analysis"][timeframe] = {"active_pattern": "none"}


def test_position_defense_trails_stop_and_carries_scale_out_reference():
    ticket = evaluate_position_defense_ticket(
        {
            "position": {
                "symbol": "BTC",
                "quantity": 0.5,
                "current_price": 105,
                "held": True,
            },
            "sell_plan": {
                "stop": {"trigger_price": 90, "limit_price": 89},
                "support_fails": 95,
                "profit": {"first_trim_price": 115},
            },
            "wave_analysis": {"higher_low": 100},
            "sentiment_posture": {"key": "crowded_euphoria_top"},
        }
    )

    assert ticket["intent_type"] == "protective_stop_limit"
    assert ticket["side"] == "sell"
    assert ticket["position_held"] is True
    assert ticket["stop_trigger_price"] == 100
    assert ticket["stop_limit_price"] < 100
    assert ticket["target_price"] == 115


def test_position_sizing_caps_notional_and_recomputes_actual_risk():
    sizing = compute_position_size(
        entry_price=100,
        stop_limit_price=90,
        account_equity_usd=1000,
        risk_per_trade_pct=1,
        max_order_usd=50,
    )

    assert sizing["risk_budget_usd"] == 10
    assert sizing["risk_based_size"] == 1
    assert sizing["base_size"] == 0.5
    assert sizing["size"] == 0.5
    assert sizing["notional_usd"] == 50
    assert sizing["actual_risk_usd"] == 5


def test_position_sizing_rejects_invalid_stop_prices():
    with pytest.raises(ValueError, match="below entry"):
        compute_position_size(entry_price=100, stop_limit_price=100)


def test_coinbase_v3_previews_use_expected_order_configurations():
    entry = build_coinbase_v3_order_preview(
        {
            "product_id": "BTC-USD",
            "side": "buy",
            "intent_type": "entry",
            "base_size": 0.1,
            "entry_price": 100,
        }
    )
    protective = build_coinbase_v3_order_preview(
        {
            "product_id": "BTC-USD",
            "side": "sell",
            "intent_type": "protective_stop_limit",
            "base_size": 0.1,
            "stop_trigger_price": 90,
            "stop_limit_price": 89,
        }
    )

    assert entry["dry_run"] is True
    assert entry["payload"]["order_configuration"]["limit_limit_gtc"] == {
        "base_size": "0.1",
        "limit_price": "100",
        "post_only": False,
    }
    assert protective["payload"]["order_configuration"][
        "stop_limit_stop_limit_gtc"
    ] == {
        "base_size": "0.1",
        "limit_price": "89",
        "stop_price": "90",
        "stop_direction": "STOP_DIRECTION_STOP_DOWN",
    }


def test_modes_apply_guardian_and_autonomous_circuit_breakers():
    assert VALID_MODES == ("advisory", "guardian", "autonomous")
    guardian = CoinbaseExecutionAgent(mode="guardian")
    sells = guardian.run(
        {
            "trade_intents": [
                {
                    "symbol": "BTC",
                    "product_id": "BTC-USD",
                    "side": "sell",
                    "intent_type": "protective_stop_limit",
                    "position_held": True,
                    "base_size": 0.1,
                    "current_price": 100,
                    "stop_trigger_price": 90,
                    "stop_limit_price": 89,
                    "target_price": 120,
                    "rr_planned": 2,
                },
                {
                    "symbol": "ETH",
                    "product_id": "ETH-USD",
                    "side": "buy",
                    "intent_type": "entry",
                    "base_size": 0.1,
                    "entry_price": 100,
                    "stop_limit_price": 90,
                    "target_price": 120,
                    "rr_planned": 2,
                },
                {
                    "symbol": "SOL",
                    "product_id": "SOL-USD",
                    "side": "sell",
                    "intent_type": "protective_stop_limit",
                    "position_held": False,
                    "base_size": 0.1,
                    "current_price": 100,
                    "stop_trigger_price": 90,
                    "stop_limit_price": 89,
                    "target_price": 120,
                    "rr_planned": 2,
                },
            ]
        }
    )

    assert [item.evidence["ticket"]["status"] for item in sells] == [
        "auto_approved_guardian",
        "staged_for_approval",
        "staged_for_approval",
    ]

    autonomous = CoinbaseExecutionAgent(mode="autonomous")
    approved = autonomous.run(
        {
            "open_positions": 3,
            "daily_realized_r": -1.9,
            "sentiment_posture": "neutral",
            "trade_intents": [
                {
                    "symbol": "BTC",
                    "product_id": "BTC-USD",
                    "side": "buy",
                    "intent_type": "entry",
                    "base_size": 2.5,
                    "entry_price": 100,
                    "stop_limit_price": 90,
                    "notional_usd": 250,
                    "rr_planned": 1.5,
                }
            ],
        }
    )
    assert approved[0].evidence["ticket"]["status"] == "auto_approved_autonomous"

    blocked = autonomous.run(
        {
            "open_positions": 4,
            "daily_realized_r": -2,
            "sentiment_posture": "crowded_euphoria_top",
            "trade_intents": [
                {
                    "symbol": "BTC",
                    "product_id": "BTC-USD",
                    "side": "buy",
                    "intent_type": "entry",
                    "base_size": 3,
                    "entry_price": 100,
                    "stop_limit_price": 90,
                    "notional_usd": 300,
                    "rr_planned": 1,
                }
            ],
        }
    )
    ticket = blocked[0].evidence["ticket"]
    assert ticket["status"] == "blocked_by_circuit_breaker"
    assert len(ticket["block_reasons"]) == 5


def test_agent_returns_observations_and_is_discoverable_by_runner():
    agent = CoinbaseExecutionAgent()
    observations = agent.run(
        {
            "trade_intents": [
                {
                    "symbol": "BTC",
                    "side": "buy",
                    "intent_type": "entry",
                    "base_size": 0.1,
                    "entry_price": 100,
                    "stop_limit_price": 90,
                    "target_price": 120,
                    "rr_planned": 2,
                }
            ]
        }
    )

    assert len(observations) == 1
    assert observations[0].agent == agent.name
    assert observations[0].evidence["ticket"]["status"] == "staged_for_approval"
    assert agent.__class__ in DEFAULT_AGENT_FACTORIES
    assert agent.name in AGENT_CATALOG


def test_agent_carries_cycle_context_on_paper_tickets():
    cycle = {"available": True, "is_multi_year": True, "cycle_range_position_pct": 28}
    observation = CoinbaseExecutionAgent().run({
        "multi_year_context": cycle,
        "trade_intents": [{
            "product_id": "BTC-USD", "side": "buy", "intent_type": "entry",
            "base_size": 0.1, "entry_price": 100, "stop_limit_price": 90,
        }],
    })[0]
    assert observation.evidence["ticket"]["multi_year_context"] == cycle
