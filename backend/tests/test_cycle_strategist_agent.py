from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from agents.catalog import AGENT_CATALOG
from agents.cycle_context import build_cycle_context
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


def _quote(bid, size=1_000.0, age_ms=1_000, **changes):
    return {
        "observed_at_ms": NOW_MS - age_ms,
        "exchange_time_ms": NOW_MS - age_ms - 100,
        "bid_usd": bid,
        "ask_usd": bid * 1.001,
        "bid_size": size,
        **changes,
    }


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
    row = _row(
        "SOL", 140.0, rollover_target_box={"low": 130.0, "high": 160.0},
        breaking_confirmation_pivot=True, weekly_rsi=65.0,
    )
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
        multi_year_oversold_exhaustion=True,
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
        {"multi_year_oversold_exhaustion": False},
        {"monthly_bearish_streak": "bad"},
        {"accumulation_invalidation_stop": {"stop_price": 0.89999, "stop_distance_pct": 10.0}},
        {"weekly_stoch_direction": "bullish_expansion"},
        {"daily_macd_kiss": False},
        {"accumulation_invalidation_stop": {"stop_price": 0.85, "stop_distance_pct": 12.0}},
    ):
        assert CycleStrategistAgent(store).evaluate(
            {"cycle_scan": _scan(_accumulation_row(**override)), "watchlist": ["LINK"]}
        ) == [], override
    divergence = _accumulation_row(daily_macd_kiss=False, daily_bullish_divergence=True)
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
        (_quote(174.8, age_ms=-1_000), "quote_stale"),
        (_quote(174.8, exchange_time_ms=None), "quote_missing_exchange_timestamp"),
        (_quote(174.8, exchange_time_ms=NOW_MS - 30_000), "exchange_book_stale"),
        (_quote(174.8, exchange_time_ms=NOW_MS), "exchange_book_stale"),
        (_quote(174.8, ask_usd=None), "quote_missing_ask"),
        (_quote(174.8, ask_usd=174), "quote_crossed_book"),
        (_quote(174.8, ask_usd=180), "quote_spread_too_wide"),
        (_quote(174.8, size=None), "quote_missing_bid_size"),
        (_quote(174.8, size=float("nan")), "quote_missing_bid_size"),
        (_quote(174.8, product_id="AVAX-USD"), "quote_product_mismatch"),
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
    assert executor.execute(proposal, {"quantity": 100.0}, None, NOW_MS)["status"] == "blocked_by_guard"
    result = executor.execute(proposal, {"quantity": 100.0}, _quote(1.0), NOW_MS)
    assert result["status"] == "auto_armed_dry_run"
    bad_bid = executor.execute(proposal, {"quantity": 100.0}, _quote(0.97), NOW_MS)
    assert bad_bid["status"] == "blocked_by_guard"
    assert result["stop_price"] == 0.975


def test_operator_decisions_stick_across_runs(store):
    agent, _ = _run(store, _mixed_context())
    trim = _by_action(agent)[TRIM_TO_USDC]
    rejected = store.decide_proposal(trim["proposal_id"], "reject")
    assert rejected["status"] == "rejected"
    assert rejected == store.decide_proposal(trim["proposal_id"], "reject")
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



def test_real_scan_shape_uses_nested_ladder_and_floor_and_position_stop(store):
    scan = _scan(
        _row("ETH", 3000, multi_year_context={"weekly_sma_ladder": {"sma_50w": 3040}}),
        _row("ADA", 1.0, multi_year_context={"daily_structure": {"higher_low_floor": 1.05}}),
        _row("SOL", 170, rollover_target_box={"low": 150, "high": 200}),
    )
    context = build_cycle_context(scan, positions=[
        {"product_id": "ETH-USD", "quantity": "1"},
        {"symbol": "ADA", "quantity": 100},
        {"symbol": "SOL", "quantity": 4, "stop_price": 173},
    ])
    agent, _ = _run(store, context)
    by_symbol = {p["symbol"]: p for p in agent.last_proposals}
    assert by_symbol["ETH"]["action"] == TRIM_TO_USDC
    assert by_symbol["ADA"]["evidence"]["trigger"] == "higher_low_floor_breached"
    assert by_symbol["SOL"]["evidence"]["trigger"] == "invalidation_stop_breached"


def test_below_price_average_is_not_overhead_resistance(store):
    row = _row("ETH", 3000, multi_year_context={"weekly_sma_ladder": {"sma_50w": 2990}})
    context = build_cycle_context(_scan(row), positions=[{"symbol": "ETH", "quantity": 1}])
    assert _run(store, context)[1] == []


def test_breakout_uses_unrounded_rsi_regime(store):
    row = _row("AVAX", 30, weekly_rsi=60.0, weekly_rsi_regime="growth_expansion", breaking_confirmation_pivot=True)
    context = build_cycle_context(_scan(row), watchlist=["AVAX"])
    assert _run(store, context)[0].last_proposals[0]["action"] == BREAKOUT_ENTRY


@pytest.mark.parametrize(
    "status,computed_at,ready",
    [("warming", NOW - 1, False), ("refreshing", NOW - 1, False),
     ("ready", NOW + 1, False), ("ready", NOW - 1801, False),
     ("ready", NOW - 1, True)],
)
def test_context_requires_ready_and_fresh_http_scan(status, computed_at, ready):
    http_scan = {**_scan(_row("ETH", 3000)), "status": status, "computed_at": computed_at, "ttl_seconds": 1800}
    assert (build_cycle_context(http_scan, now=NOW)["cycle_scan"] is not None) is ready


def test_mode_b_never_simulates_accumulation_even_with_a_quote(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=20)
    agent, _ = _run(store, {
        "cycle_scan": _scan(_accumulation_row()),
        "watchlist": ["LINK"],
        "quotes": {"LINK-USD": _quote(1)},
    })
    assert _by_action(agent)[ACCUMULATE_SUPPORT]["status"] == "pending_approval"
    assert store.count_auto_orders_since(0) == 0


def test_approval_is_idempotent_and_preserves_the_reviewed_evidence(store):
    agent, _ = _run(store, _mixed_context())
    before = _by_action(agent)[TRIM_TO_USDC]
    proposal_id = before["proposal_id"]
    approved = store.decide_proposal(proposal_id, "approve")
    assert approved["status"] == "approved"
    assert approved["execution"] is None and approved["executed_ts"] is None
    assert store.decide_proposal(proposal_id, "approve") == approved
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    revised = _mixed_context()
    revised["cycle_scan"]["coins"][0]["price"] += 2
    agent, _ = _run(store, revised)
    assert _by_action(agent)[TRIM_TO_USDC] == approved
    assert store.count_auto_orders_since(0) == 0


def test_simultaneous_proposal_decisions_cannot_overwrite_each_other(store):
    seed, _ = _run(store, _mixed_context())
    id_ = _by_action(seed)[TRIM_TO_USDC]["proposal_id"]
    start = Barrier(2)
    other_store = AgentStore(store.db_path)

    def decide(ledger, decision):
        start.wait(timeout=5)
        try:
            return ledger.decide_proposal(id_, decision)["status"]
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        approve = pool.submit(decide, store, "approve")
        reject = pool.submit(decide, other_store, "reject")
        results = (approve.result(timeout=5), reject.result(timeout=5))
    assert results.count("conflict") == 1
    assert store.get_proposal(id_)["status"] in results
    assert store.count_auto_orders_since(0) == 0


def test_parallel_inflight_exits_share_daily_cap(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=1)
    other_store = AgentStore(store.db_path)
    first_started, second_started, finish_first = Event(), Event(), Event()

    class SlowDryRun(GuardedDryRunExitExecutor):
        def execute(self, *args):
            first_started.set()
            assert finish_first.wait(timeout=5)
            return super().execute(*args)

    def run_symbol(symbol, agent, started=None):
        if started:
            started.set()
        agent.run({
            "now_ts": NOW,
            "cycle_scan": _scan(_row(symbol, 175, rollover_target_box={"low": 150, "high": 200})),
            "positions": [{"symbol": symbol, "quantity": 10}],
            "quotes": {f"{symbol}-USD": _quote(175)},
        })
        return agent.last_proposals[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run_symbol, "SOL", CycleStrategistAgent(store, executor=SlowDryRun()))
        try:
            assert first_started.wait(timeout=5)
            second = pool.submit(run_symbol, "AVAX", CycleStrategistAgent(other_store), second_started)
            assert second_started.wait(timeout=5)
        finally:
            finish_first.set()
        assert first.result(timeout=5)["status"] == "auto_executed_dry_run"
        assert second.result(timeout=5)["execution"]["block_reasons"] == ["daily_order_cap_reached"]
    assert store.count_auto_orders_since(0) == 1



def test_runner_observes_pause_committed_between_proposals(store, monkeypatch):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    other_store = AgentStore(store.db_path)
    route = store.route_proposal

    def pause_after_first(*args, **kwargs):
        result = route(*args, **kwargs)
        if result[0]["status"] == "auto_executed_dry_run":
            other_store.set_autonomy_settings(emergency_pause=True)
        return result

    monkeypatch.setattr(store, "route_proposal", pause_after_first)
    symbols = ("SOL", "AVAX")
    agent, _ = _run(store, {
        "cycle_scan": _scan(*(
            _row(symbol, 175, rollover_target_box={"low": 150, "high": 200})
            for symbol in symbols
        )),
        "positions": [{"symbol": symbol, "quantity": 10} for symbol in symbols],
        "quotes": {f"{symbol}-USD": _quote(175) for symbol in symbols},
    })
    by_symbol = {p["symbol"]: p for p in agent.last_proposals}
    assert by_symbol["AVAX"]["status"] == "auto_executed_dry_run"
    assert by_symbol["SOL"]["execution"] == {"held_reason": "emergency_pause"}
    assert store.count_auto_orders_since(0) == 1
