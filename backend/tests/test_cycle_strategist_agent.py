import pytest

from agents.catalog import AGENT_CATALOG
from agents.cycle_strategist import (
    ACCUMULATE_SUPPORT,
    BREAKOUT_ENTRY,
    PROTECTIVE_STOP,
    TRIM_TO_USDC,
    CycleStrategistAgent,
    GuardedDryRunExitExecutor,
)
from agents.runner import DEFAULT_AGENT_FACTORIES, run_once
from agents.store import AgentStore

NOW = 1_800_000_000.0
NOW_MS = int(NOW * 1000)


def _row(symbol, price, **extra):
    return {"symbol": symbol, "product_id": f"{symbol}-USD", "available": True, "price": price, **extra}


def _scan(*rows, stage="stage_1_macro_compression"):
    return {"industry": {"available": True, "liquidity_rotation_stage": stage}, "coins": list(rows)}


def _quote(bid, size=1_000.0, age_ms=1_000):
    return {"observed_at_ms": NOW_MS - age_ms, "bid_usd": bid, "bid_size": size}


@pytest.fixture
def store(tmp_path):
    return AgentStore(tmp_path / "agents.sqlite")


def _run(store, context):
    agent = CycleStrategistAgent(store)
    observations = agent.run({"now_ts": NOW, **context})
    return agent, observations


def test_registered_in_runner_and_catalog():
    assert CycleStrategistAgent in DEFAULT_AGENT_FACTORIES
    assert "cycle_strategist" in AGENT_CATALOG


def test_trim_inside_rollover_box_scales_with_depth(store):
    scan = _scan(_row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0}))
    agent, obs = _run(store, {"cycle_scan": scan, "positions": [{"symbol": "SOL", "quantity": 10}]})
    (proposal,) = agent.last_proposals
    assert proposal["action"] == TRIM_TO_USDC
    assert proposal["trim_pct"] == 37.5
    assert proposal["status"] == "pending_approval"
    assert obs[0].severity == "warning"


def test_trim_at_overhead_weekly_sma_and_only_in_stage_1_or_2(store):
    row = _row("ETH", 3_000.0)
    contexts = {"ETH": {"weekly_sma_ladder": {"sma_50w": 3_040.0}}}
    positions = [{"symbol": "ETH", "quantity": 2}]
    agent, _ = _run(store, {"cycle_scan": _scan(row), "multi_year_contexts": contexts, "positions": positions})
    assert agent.last_proposals[0]["trim_pct"] == 25.0
    agent, _ = _run(
        store,
        {
            "cycle_scan": _scan(row, stage="stage_3_alt_index_breakout"),
            "multi_year_contexts": contexts,
            "positions": positions,
        },
    )
    assert agent.last_proposals == []


def test_protective_stop_on_floor_breach_preempts_trim(store):
    row = _row("SOL", 140.0, rollover_target_box={"low": 130.0, "high": 160.0})
    positions = [{"symbol": "SOL", "quantity": 10, "higher_low_floor": 145.0}]
    agent, obs = _run(store, {"cycle_scan": _scan(row), "positions": positions})
    (proposal,) = agent.last_proposals
    assert proposal["action"] == PROTECTIVE_STOP
    assert proposal["evidence"]["trigger"] == "higher_low_floor_breached"
    assert obs[0].severity == "critical"


def test_protective_stop_when_invalidation_stop_is_near(store):
    row = _row("ADA", 1.0, accumulation_invalidation_stop={"stop_price": 0.975, "stop_distance_pct": 2.5})
    agent, _ = _run(store, {"cycle_scan": _scan(row), "positions": [{"symbol": "ADA", "quantity": 100}]})
    assert agent.last_proposals[0]["evidence"]["trigger"] == "invalidation_stop_near"


def _accumulation_row(**overrides):
    base = dict(
        bucket="deep_accumulation_exhaustion",
        monthly_bearish_streak=19,
        weekly_stoch_direction="oversold_turn_up",
        daily_macd_kiss=True,
        accumulation_invalidation_stop={"stop_price": 0.92, "stop_distance_pct": 8.0},
    )
    return _row("LINK", 1.0, **{**base, **overrides})


def test_accumulate_support_requires_every_condition(store):
    agent, _ = _run(store, {"cycle_scan": _scan(_accumulation_row()), "watchlist": ["LINK"]})
    assert agent.last_proposals[0]["action"] == ACCUMULATE_SUPPORT
    assert agent.last_proposals[0]["side"] == "buy"
    for override in (
        {"monthly_bearish_streak": 17},
        {"weekly_stoch_direction": "bullish_expansion"},
        {"daily_macd_kiss": False},
        {"accumulation_invalidation_stop": {"stop_price": 0.85, "stop_distance_pct": 12.0}},
    ):
        assert CycleStrategistAgent(store).evaluate(
            {"cycle_scan": _scan(_accumulation_row(**override)), "watchlist": ["LINK"]}
        ) == [], override
    divergence = _accumulation_row(daily_macd_kiss=False, macro_bullish_divergence=True)
    assert CycleStrategistAgent(store).evaluate({"cycle_scan": _scan(divergence), "watchlist": ["LINK"]})


def test_breakout_entry_needs_weekly_rsi_above_60(store):
    row = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=63.0)
    agent, _ = _run(store, {"cycle_scan": _scan(row), "watchlist": ["AVAX"]})
    assert agent.last_proposals[0]["action"] == BREAKOUT_ENTRY
    weak = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=60.0)
    assert CycleStrategistAgent(store).evaluate({"cycle_scan": _scan(weak), "watchlist": ["AVAX"]}) == []


def _mixed_context():
    trim = _row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0})
    breakout = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=65.0)
    return {
        "cycle_scan": _scan(trim, breakout),
        "positions": [{"symbol": "SOL", "quantity": 10}],
        "watchlist": ["AVAX"],
        "quotes": {"SOL-USD": _quote(174.8)},
    }


def _by_action(agent):
    return {p["action"]: p for p in agent.last_proposals}


def test_approval_queue_keeps_everything_pending(store):
    agent, _ = _run(store, _mixed_context())
    assert {p["status"] for p in agent.last_proposals} == {"pending_approval"}


def test_auto_protect_exits_dry_runs_exits_but_not_entries(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    agent, _ = _run(store, _mixed_context())
    proposals = _by_action(agent)
    trim = proposals[TRIM_TO_USDC]
    assert trim["status"] == "auto_executed_dry_run"
    assert trim["execution"]["order_submitted"] is False
    assert trim["execution"]["base_size"] == 3.75
    assert proposals[BREAKOUT_ENTRY]["status"] == "pending_approval"
    # A repeat run the same day neither re-executes nor counts another order.
    agent, _ = _run(store, _mixed_context())
    assert _by_action(agent)[TRIM_TO_USDC]["executed_ts"] == trim["executed_ts"]
    assert store.count_auto_orders_since(0) == 1


def test_emergency_pause_and_live_guarded_block_auto_exits(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", emergency_pause=True)
    agent, _ = _run(store, _mixed_context())
    trim = _by_action(agent)[TRIM_TO_USDC]
    assert trim["status"] == "pending_approval"
    assert trim["execution"] == {"held_reason": "emergency_pause"}

    store.set_autonomy_settings(emergency_pause=False, execution_mode="live_guarded")
    agent, _ = _run(store, _mixed_context())
    trim = _by_action(agent)[TRIM_TO_USDC]
    assert trim["status"] == "blocked_by_guard"
    assert trim["execution"]["block_reasons"] == ["live_order_route_unavailable"]


def test_daily_order_cap_blocks_auto_exits(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=0)
    agent, _ = _run(store, _mixed_context())
    assert _by_action(agent)[TRIM_TO_USDC]["execution"]["block_reasons"] == ["daily_order_cap_reached"]


@pytest.mark.parametrize(
    "quote, reason",
    [
        (None, "quote_unavailable"),
        ({"observed_at_ms": NOW_MS, "quote_status": "UNAVAILABLE"}, "quote_unavailable"),
        (_quote(174.8, age_ms=60_000), "quote_stale"),
        (_quote(160.0), "quote_deviates_from_reference"),
        (_quote(174.8, size=1.0), "insufficient_top_of_book_size"),
    ],
)
def test_quote_fill_guards_block_bad_quotes(store, quote, reason):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    context = _mixed_context()
    context["quotes"] = {"SOL-USD": quote} if quote else {}
    agent, _ = _run(store, context)
    trim = _by_action(agent)[TRIM_TO_USDC]
    assert trim["status"] == "blocked_by_guard"
    assert reason in trim["execution"]["block_reasons"]


def test_protective_stop_near_invalidation_is_armed_not_sold():
    executor = GuardedDryRunExitExecutor()
    store_agent = CycleStrategistAgent()
    row = _row("ADA", 1.0, accumulation_invalidation_stop={"stop_price": 0.975, "stop_distance_pct": 2.5})
    (proposal,) = store_agent.evaluate({"cycle_scan": _scan(row), "positions": [{"symbol": "ADA", "quantity": 100}]})
    result = executor.execute(proposal, {"quantity": 100.0}, None, NOW_MS)
    assert result["status"] == "auto_armed_dry_run"
    assert result["stop_price"] == 0.975


def test_operator_decisions_stick_across_runs(store):
    agent, _ = _run(store, _mixed_context())
    trim = _by_action(agent)[TRIM_TO_USDC]
    assert store.decide_proposal(trim["proposal_id"], "reject")["status"] == "rejected"
    agent, _ = _run(store, _mixed_context())
    assert _by_action(agent)[TRIM_TO_USDC]["status"] == "rejected"
    with pytest.raises(ValueError):
        store.decide_proposal(trim["proposal_id"], "approve")


def test_autonomy_settings_validate_and_persist(store, tmp_path):
    assert store.get_autonomy_settings()["autonomy_mode"] == "approval_queue"
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=5)
    reopened = AgentStore(tmp_path / "agents.sqlite").get_autonomy_settings()
    assert reopened["autonomy_mode"] == "auto_protect_exits"
    assert reopened["daily_order_cap"] == 5
    for bad in ({"autonomy_mode": "yolo"}, {"execution_mode": "live"}, {"emergency_pause": "no"}, {"daily_order_cap": 99}):
        with pytest.raises(ValueError):
            store.set_autonomy_settings(**bad)


def test_runner_binds_store_and_records_observations(store):
    result = run_once({"now_ts": NOW, **_mixed_context()}, store=store, agents=[CycleStrategistAgent()])
    assert result["runs"] == [{"agent": "cycle_strategist", "status": "ok", "observations": 2}]
    assert len(store.list_proposals()) == 2


def test_no_scan_means_no_proposals(store):
    agent, obs = _run(store, {"positions": [{"symbol": "SOL", "quantity": 1}]})
    assert obs == [] and agent.last_proposals == []
