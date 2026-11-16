from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from agents.catalog import AGENT_CATALOG
from agents.cycle_context import build_cycle_context, fetch_live_quotes, fetch_top_of_book
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
        rollover_target_box={"low": 1.4, "high": 1.8},
    )
    return _row("LINK", 1.0, **{**base, **overrides})


# A stop and a target far enough away for the reward-to-risk gate (15 / 2 = 7.5).
BREAKOUT_LEVELS = dict(
    accumulation_invalidation_stop={"stop_price": 28.0},
    rollover_target_box={"low": 40.0, "high": 50.0},
)


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
    row = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=63.0, **BREAKOUT_LEVELS)
    agent, _ = _run(store, {"cycle_scan": _scan(row), "watchlist": ["AVAX"]})
    assert agent.last_proposals[0]["action"] == BREAKOUT_ENTRY
    weak = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=60.0, **BREAKOUT_LEVELS)
    assert CycleStrategistAgent(store).evaluate({"cycle_scan": _scan(weak), "watchlist": ["AVAX"]}) == []


def _mixed_context():
    trim = _row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0})
    breakout = _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=65.0, **BREAKOUT_LEVELS)
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
        (_quote(174.8, exchange_time_ms=NOW_MS + 1_001), "exchange_book_stale"),
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


def test_exchange_time_may_lead_the_local_clock_only_within_the_skew_allowance():
    # _quote() is received at NOW - 1s. Coinbase stamps live books a few hundred
    # milliseconds after local receipt when the PC clock runs slightly behind.
    ahead = lambda ms: _quote(174.8, exchange_time_ms=NOW_MS - 1_000 + ms)
    default = GuardedDryRunExitExecutor()
    assert default.max_clock_skew_ms == 2_000
    assert default.quote_guard(ahead(539), 174.8, 1.0, NOW_MS) == []
    assert default.quote_guard(ahead(2_000), 174.8, 1.0, NOW_MS) == []
    assert default.quote_guard(ahead(2_001), 174.8, 1.0, NOW_MS) == ["exchange_book_stale"]
    # The book may also be stamped after the decision time, inside the same allowance.
    assert default.quote_guard(ahead(1_500), 174.8, 1.0, NOW_MS - 900) == []
    strict = GuardedDryRunExitExecutor(max_clock_skew_ms=0)
    assert strict.quote_guard(ahead(1), 174.8, 1.0, NOW_MS) == ["exchange_book_stale"]
    assert strict.quote_guard(ahead(0), 174.8, 1.0, NOW_MS) == []
    for bad in (-1, 15_001, float("nan"), None):
        with pytest.raises(ValueError):
            GuardedDryRunExitExecutor(max_clock_skew_ms=bad)


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
    row = _row(
        "AVAX", 30, weekly_rsi=60.0, weekly_rsi_regime="growth_expansion",
        breaking_confirmation_pivot=True, **BREAKOUT_LEVELS,
    )
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


# ─── Phase 2: reload ladder ──────────────────────────────────────────────────

DAY = 86_400
SUPPORT = {"0.618": 120.0, "0.702": 105.0, "0.786": 90.0}


def _sol_trim_row(price=175.0, **extra):
    base = dict(rollover_target_box={"low": 150.0, "high": 200.0}, support_levels=SUPPORT, cycle_low=60.0)
    return _row("SOL", price, **{**base, **extra})


def _approved_trim(store, quantity=10):
    agent, _ = _run(store, {"cycle_scan": _scan(_sol_trim_row()), "positions": [{"symbol": "SOL", "quantity": quantity}]})
    (trim,) = agent.last_proposals
    assert store.active_reload_plans() == []  # a pending trim has freed nothing
    return store.decide_proposal(trim["proposal_id"], "approve")


def _reload_row(price, **extra):
    """SOL back at support: a tight scanner stop and a weekly StochRSI turn."""
    base = dict(
        accumulation_invalidation_stop={"stop_price": price - 8.0},
        weekly_stoch_direction="oversold_turn_up",
    )
    return _sol_trim_row(price, **{**base, **extra})


def test_trim_carries_a_three_rung_reload_plan_with_the_coin_gain(store):
    agent, obs = _run(store, {"cycle_scan": _scan(_sol_trim_row()), "positions": [{"symbol": "SOL", "quantity": 10}]})
    plan = agent.last_proposals[0]["reload_plan"]
    assert plan["available"] is True and plan["fresh_cash_usd"] == 0.0
    assert plan["trim_quantity"] == 3.75 and plan["freed_usdc"] == 656.25
    assert plan["invalidation_basis"] == "cycle_low" and plan["invalidation_stop"] == pytest.approx(58.8)
    assert [(t["level"], t["weight_pct"], t["usdc"], t["basis"]) for t in plan["tranches"]] == [
        (120.0, 25.0, 164.06, "log_fib_0.618"),
        (105.0, 35.0, 229.69, "log_fib_0.702"),
        (90.0, 40.0, 262.5, "log_fib_0.786"),
    ]
    coins = 164.0625 / 120 + 229.6875 / 105 + 262.5 / 90
    assert plan["projected_reloaded_coins"] == pytest.approx(coins)
    assert plan["net_coin_gain_qty"] == pytest.approx(coins - 3.75)
    assert plan["net_coin_gain_pct"] == round((coins - 3.75) / 10 * 100, 2) == 27.21
    assert plan["reloaded_vs_trimmed_pct"] == 72.57
    assert plan["average_reload_price"] == pytest.approx(656.25 / coins)
    assert obs[0].evidence["reload_plan"]["net_coin_gain_pct"] == 27.21


def test_reload_ladder_stays_above_the_stop_and_fills_from_floor_and_clusters(store):
    # The scanner stop at 100 removes the 0.786 rung; the daily floor replaces it.
    row = _sol_trim_row(
        accumulation_invalidation_stop={"stop_price": 100.0},
        fib_cluster_mids=[119.5, 140.0, 95.0],
    )
    positions = [{"symbol": "SOL", "quantity": 10, "higher_low_floor": 160.0}]
    agent, _ = _run(store, {"cycle_scan": _scan(row), "positions": positions})
    plan = agent.last_proposals[0]["reload_plan"]
    assert plan["invalidation_basis"] == "accumulation_invalidation_stop"
    assert [(t["level"], t["basis"]) for t in plan["tranches"]] == [
        (160.0, "daily_higher_low_floor"), (120.0, "log_fib_0.618"), (105.0, "log_fib_0.702"),
    ]
    assert all(t["level"] > plan["invalidation_stop"] for t in plan["tranches"])

    # Clusters alone: 174.9 is not a real discount and 30 is under the cycle low.
    clusters = _sol_trim_row(support_levels=None, fib_cluster_mids=[174.9, 140.0, 119.5, 30.0])
    agent, _ = _run(store, {"cycle_scan": _scan(clusters), "positions": [{"symbol": "SOL", "quantity": 10}]})
    plan = agent.last_proposals[0]["reload_plan"]
    assert [t["level"] for t in plan["tranches"]] == [140.0, 119.5]
    assert [t["weight_pct"] for t in plan["tranches"]] == [41.67, 58.33]
    assert sum(t["usdc"] for t in plan["tranches"]) == pytest.approx(656.25, abs=0.02)

    bare = _row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0})
    agent, _ = _run(store, {"cycle_scan": _scan(bare), "positions": [{"symbol": "SOL", "quantity": 10}]})
    plan = agent.last_proposals[0]["reload_plan"]
    assert plan == {
        "available": False, "reason": "no_support_level_between_stop_and_price",
        "reference_price": 175.0, "trim_quantity": 3.75, "freed_usdc": 656.25,
        "invalidation_stop": None, "invalidation_basis": None, "fresh_cash_usd": 0.0,
        "assumptions": plan["assumptions"],
    }


def test_only_an_approved_or_executed_trim_opens_a_reload_plan(store):
    agent, _ = _run(store, {"cycle_scan": _scan(_sol_trim_row()), "positions": [{"symbol": "SOL", "quantity": 10}]})
    trim_id = agent.last_proposals[0]["proposal_id"]
    store.decide_proposal(trim_id, "reject")
    assert store.active_reload_plans() == []

    other = AgentStore(store.db_path.with_name("executed.sqlite"))
    other.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    agent, _ = _run(other, {
        "cycle_scan": _scan(_sol_trim_row()),
        "positions": [{"symbol": "SOL", "quantity": 10}],
        "quotes": {"SOL-USD": _quote(174.8)},
    })
    assert agent.last_proposals[0]["status"] == "auto_executed_dry_run"
    (plan,) = other.active_reload_plans("sol-usd")
    assert plan["trim_status"] == "auto_executed_dry_run" and plan["remaining_usdc"] == 656.25
    assert other.active_reload_plans("AVAX") == []


def test_reload_accumulate_fires_at_a_reached_rung_and_spends_it_once(store):
    trim = _approved_trim(store)
    held = [{"symbol": "SOL", "quantity": 6.25}]
    risk = {"portfolio_equity_usd": 10_000}

    def later(days, row, **context):
        agent = CycleStrategistAgent(store)
        agent.run({"now_ts": NOW + days * DAY, "cycle_scan": _scan(row), "positions": held, **risk, **context})
        return agent

    # Above every rung, or at a rung without a momentum turn: nothing.
    assert later(1, _reload_row(130.0)).last_proposals == []
    assert later(1, _reload_row(118.0, weekly_stoch_direction="oversold_falling")).last_proposals == []

    agent = later(1, _reload_row(118.0))
    (reload_,) = agent.last_proposals
    assert reload_["action"] == "RELOAD_ACCUMULATE" and reload_["side"] == "buy"
    assert reload_["status"] == "pending_approval"
    assert reload_["evidence"]["reload_fills"] == [
        {"plan_id": trim["proposal_id"], "tranche": 1, "level": 120.0, "usdc": 164.06}
    ]
    assert reload_["evidence"]["reload_pool_remaining_usdc"] == 656.25
    assert reload_["stop_price"] == 110.0 and reload_["target_price"] == 175.0
    assert reload_["reward_to_risk_ratio"] == round(57 / 8, 2)
    sizing = reload_["sizing"]
    assert sizing["funded_usd"] == sizing["suggested_notional_usd"] == 164.06
    assert sizing["suggested_quantity"] == pytest.approx(164.06 / 118)

    # Until it is approved the rung stays open; afterwards it is spent.
    assert store.active_reload_plans()[0]["remaining_usdc"] == 656.25
    store.decide_proposal(reload_["proposal_id"], "approve")
    (plan,) = store.active_reload_plans()
    assert [t["filled"] for t in plan["tranches"]] == [True, False, False]
    assert plan["remaining_usdc"] == 492.19

    # A daily MACD kiss also qualifies, and a deeper fall takes both open rungs.
    kiss = _reload_row(88.0, weekly_stoch_direction=None, daily_macd_kiss=True)
    agent = later(2, kiss)
    (deeper,) = agent.last_proposals
    assert [fill["tranche"] for fill in deeper["evidence"]["reload_fills"]] == [2, 3]
    assert deeper["sizing"]["funded_usd"] == 492.19
    store.decide_proposal(deeper["proposal_id"], "approve")
    assert store.active_reload_plans() == []
    assert later(3, _reload_row(88.0)).last_proposals == []


def test_reload_is_found_without_a_position_and_never_auto_executes(store):
    _approved_trim(store)
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=20)
    agent = CycleStrategistAgent(store)
    agent.run({
        "now_ts": NOW + DAY,
        "cycle_scan": _scan(_reload_row(118.0)),
        "quotes": {"SOL-USD": _quote(118.0)},
    })
    (reload_,) = agent.last_proposals
    assert reload_["action"] == "RELOAD_ACCUMULATE" and reload_["status"] == "pending_approval"
    assert reload_["sizing"]["note"] == "equity_unknown"
    assert reload_["sizing"]["suggested_notional_usd"] == 164.06
    assert store.count_auto_orders_since(0) == 0


def test_reload_plan_stops_triggering_below_its_invalidation(store):
    _approved_trim(store)
    broken = _reload_row(58.0, accumulation_invalidation_stop={"stop_price": 55.0})
    agent = CycleStrategistAgent(store)
    assert agent.evaluate({"cycle_scan": _scan(broken), "now_ts": NOW + DAY}) == []


# ─── Phase 2: reward to risk, sizing and heat ────────────────────────────────


def _breakout(symbol="AVAX", price=30.0, **extra):
    return _row(symbol, price, breaking_confirmation_pivot=True, weekly_rsi=65.0, **{**BREAKOUT_LEVELS, **extra})


def test_entries_need_reward_to_risk_of_two(store):
    agent = CycleStrategistAgent(store)
    (entry,) = agent.evaluate({"cycle_scan": _scan(_breakout()), "watchlist": ["AVAX"]})
    assert entry.reward_to_risk_ratio == 7.5 and entry.target_price == 45.0
    assert entry.evidence["target"]["tier"] == "rollover_target_box"

    cases = {
        "reward_to_risk_below_minimum": _breakout(rollover_target_box={"low": 31.0, "high": 35.0}),
        "no_target_above_price": _breakout(rollover_target_box={"low": 20.0, "high": 28.0}),
        "no_stop_below_price": _breakout(accumulation_invalidation_stop=None),
    }
    for reason, row in cases.items():
        assert agent.evaluate({"cycle_scan": _scan(row), "watchlist": ["AVAX"]}) == [], reason
        assert agent.last_skipped[0]["reason"] == reason
        assert agent.last_skipped[0]["action"] == BREAKOUT_ENTRY

    exactly_two = _breakout(rollover_target_box={"low": 33.0, "high": 35.0})
    (entry,) = agent.evaluate({"cycle_scan": _scan(exactly_two), "watchlist": ["AVAX"]})
    assert entry.reward_to_risk_ratio == 2.0 and agent.last_skipped == []


def test_breakout_falls_back_to_the_daily_floor_and_stage_selects_the_target(store):
    row = _breakout(
        accumulation_invalidation_stop=None,
        multi_year_context={"daily_structure": {"higher_low_floor": 27.0}},
        full_extension_targets={"low": 60.0, "high": 120.0},
        active_target_tier="full_extension_targets",
    )
    (entry,) = CycleStrategistAgent(store).evaluate(
        {"cycle_scan": _scan(row, stage="stage_3_alt_index_breakout"), "watchlist": ["AVAX"]}
    )
    assert entry.stop_price == 27.0 and entry.target_price == 90.0
    assert entry.reward_to_risk_ratio == 20.0
    assert entry.evidence["target"]["tier"] == "full_extension_targets"


@pytest.mark.parametrize(
    "stage,multiplier,notional",
    [
        ("stage_1_macro_compression", 0.5, 750.0),
        ("stage_2_btc_majors_lead", 0.75, 1125.0),
        ("stage_3_alt_index_breakout", 1.0, 1500.0),
        ("stage_4_alt_season_expansion", 1.0, 1500.0),
        (None, 0.5, 750.0),
    ],
)
def test_suggested_size_scales_with_the_rotation_stage(store, stage, multiplier, notional):
    context = {"cycle_scan": _scan(_breakout(), stage=stage), "watchlist": ["AVAX"], "portfolio_equity_usd": 10_000}
    (entry,) = CycleStrategistAgent(store).evaluate(context)
    sizing = entry.sizing
    assert sizing["stage_multiplier"] == multiplier and sizing["risk_budget_pct"] == multiplier
    assert sizing["suggested_notional_usd"] == notional
    assert sizing["risk_at_stop_usd"] == pytest.approx(10_000 * multiplier / 100)
    assert sizing["suggested_quantity"] == pytest.approx(notional / 30)
    assert sizing["heat_capped"] is False and sizing["open_risk_pct"] == 0.0


def test_position_cap_and_custom_risk_settings(store):
    tight = _breakout(accumulation_invalidation_stop={"stop_price": 29.7})  # 1% stop
    context = {
        "cycle_scan": _scan(tight, stage="stage_3_alt_index_breakout"),
        "watchlist": ["AVAX"], "portfolio_equity_usd": 10_000,
    }
    (entry,) = CycleStrategistAgent(store).evaluate(context)
    assert entry.sizing["position_capped"] is True
    assert entry.sizing["suggested_notional_usd"] == 2_500.0  # 25% of equity
    assert entry.sizing["risk_budget_pct"] == 0.25

    (entry,) = CycleStrategistAgent(store).evaluate({**context, "base_risk_pct": 0.2, "max_open_risk_pct": 3})
    assert entry.sizing["base_risk_pct"] == 0.2 and entry.sizing["max_open_risk_pct"] == 3
    assert entry.sizing["suggested_notional_usd"] == 2_000.0
    # Out-of-range settings fall back to the defaults.
    (entry,) = CycleStrategistAgent(store).evaluate({**context, "base_risk_pct": -1, "max_open_risk_pct": 500})
    assert entry.sizing["base_risk_pct"] == 1.0 and entry.sizing["max_open_risk_pct"] == 5.0


def test_portfolio_heat_caps_and_is_shared_between_entries(store):
    # ETH: 2 coins with a stop 240 under price -> $480 of open risk = 4.8% of $10k.
    held = _row("ETH", 3000.0)
    context = {
        "cycle_scan": _scan(held, _breakout("AVAX"), _breakout("NEAR"), stage="stage_3_alt_index_breakout"),
        "positions": [{"symbol": "ETH", "quantity": 2, "stop_price": 2760.0}],
        "watchlist": ["AVAX", "NEAR"],
        "portfolio_equity_usd": 10_000,
    }
    agent = CycleStrategistAgent(store)
    avax, near = agent.evaluate(context)
    assert agent.last_heat["open_risk_pct"] == 4.8 and agent.last_heat["open_risk_usd"] == 480.0
    assert avax.sizing["heat_capped"] is True and avax.sizing["risk_budget_pct"] == pytest.approx(0.2)
    assert avax.sizing["suggested_notional_usd"] == pytest.approx(300.0)
    # AVAX took the last of the headroom, so NEAR is sized at zero.
    assert near.sizing["heat_capped"] is True and near.sizing["suggested_notional_usd"] == 0.0

    # Without a supplied equity figure the held coins are the equity, and a
    # coin with no stop is counted at the assumed 10%.
    del context["portfolio_equity_usd"]
    context["positions"] = [{"symbol": "ETH", "quantity": 2}]
    avax, _ = agent.evaluate(context)
    assert agent.last_heat == {
        "equity_usd": 6000.0, "equity_basis": "held_positions_mark",
        "open_risk_usd": 600.0, "open_risk_pct": 10.0, "max_open_risk_pct": 5.0,
        "assumed_stop_symbols": ["ETH"], "unpriced_symbols": [],
    }
    assert avax.sizing["suggested_notional_usd"] == 0.0 and avax.sizing["heat_capped"] is True


def test_sizing_without_equity_gives_no_notional(store):
    (entry,) = CycleStrategistAgent(store).evaluate({"cycle_scan": _scan(_breakout()), "watchlist": ["AVAX"]})
    assert entry.sizing["note"] == "equity_unknown"
    assert entry.sizing["suggested_notional_usd"] is None and entry.sizing["risk_budget_pct"] == 0.5


# ─── Phase 2: pair rotation ──────────────────────────────────────────────────


def _laggard(**overrides):
    base = dict(above_50w_sma=False, weekly_rsi=40.0, bucket=None, at_multi_year_support=False)
    return _row("DOT", 5.0, **{**base, **overrides})


def _leader(symbol="LINK", score=30.0, **overrides):
    base = dict(
        bucket="deep_accumulation_exhaustion", score=score,
        accumulation_invalidation_stop={"stop_price": 0.92},
        rollover_target_box={"low": 1.4, "high": 1.8},
    )
    return _row(symbol, 1.0, **{**base, **overrides})


def _rotation_context(*rows, **extra):
    return {"cycle_scan": _scan(*rows), "positions": [{"symbol": "DOT", "quantity": 100}], **extra}


def test_rotate_to_leader_pairs_a_weak_held_coin_with_the_top_candidate(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits", daily_order_cap=20)
    context = _rotation_context(
        _laggard(), _leader(), _leader("ATOM", score=40.0),
        _leader("BRK", score=99.0, bucket="low_confirmation_breakout", rollover_target_box={"low": 1.1, "high": 1.3}),
        quotes={"DOT-USD": _quote(5.0)}, portfolio_equity_usd=10_000,
    )
    agent, obs = _run(store, context)
    (rotation,) = agent.last_proposals
    assert rotation["action"] == "ROTATE_TO_LEADER" and rotation["symbol"] == "DOT"
    assert rotation["side"] == "sell" and rotation["trim_pct"] == 25.0
    # It has a buy leg, so Mode B leaves it for approval even with a good quote.
    assert rotation["status"] == "pending_approval" and store.count_auto_orders_since(0) == 0
    pair = rotation["pair"]
    assert (pair["sell_product_id"], pair["buy_product_id"]) == ("DOT-USD", "ATOM-USD")
    assert pair["freed_usd"] == 125.0
    # ATOM outranks LINK on score; BRK's reward to risk is 2.5, under the 3.0 bar.
    assert pair["leader"]["bucket_rank"] == 1 and pair["leader"]["reward_to_risk_ratio"] == 7.5
    assert rotation["reward_to_risk_ratio"] == 7.5 and rotation["target_price"] == pytest.approx(1.6)
    assert rotation["sizing"]["funded_usd"] == rotation["sizing"]["suggested_notional_usd"] == 125.0
    assert obs[0].kind == "trade_proposal_rotate_to_leader" and obs[0].severity == "watch"
    assert obs[0].evidence["pair"]["buy_symbol"] == "ATOM"


@pytest.mark.parametrize(
    "laggard",
    [
        {"weekly_rsi": 45.0},
        {"above_50w_sma": True},
        {"above_50w_sma": None},
        {"daily_bullish_divergence": {"kind": "regular"}},
        {"macro_bullish_divergence": True},
        {"at_multi_year_support": True},
        {"bucket": "deep_accumulation_exhaustion"},
        {"weekly_rsi": None},
    ],
)
def test_rotation_needs_every_weakness_condition(store, laggard):
    agent = CycleStrategistAgent(store)
    assert agent.evaluate(_rotation_context(_laggard(**laggard), _leader())) == []


def test_rotation_needs_a_qualifying_leader(store):
    agent = CycleStrategistAgent(store)
    for leader in (
        _leader(rollover_target_box={"low": 1.1, "high": 1.3}),  # reward to risk 2.5
        _leader(accumulation_invalidation_stop=None),
        _leader(bucket="growth_expansion_ride"),
    ):
        assert agent.evaluate(_rotation_context(_laggard(), leader)) == []
    # A coin cannot rotate into itself.
    own = _laggard(bucket="low_confirmation_breakout", score=50.0, **{
        "accumulation_invalidation_stop": {"stop_price": 4.8}, "rollover_target_box": {"low": 8.0, "high": 9.0},
    })
    assert [p.action for p in agent.evaluate(_rotation_context(own))] == []
    # Only the top three of a bucket are candidates.
    crowd = [_leader(f"C{i}", score=90.0 - i, rollover_target_box={"low": 1.1, "high": 1.3}) for i in range(3)]
    assert agent.evaluate(_rotation_context(_laggard(), _leader(score=1.0), *crowd)) == []


def test_a_defended_coin_is_neither_rotated_nor_used_as_the_leader(store):
    agent = CycleStrategistAgent(store)
    context = _rotation_context(_laggard(), _leader())
    context["positions"] = [
        {"symbol": "DOT", "quantity": 100, "stop_price": 5.5},
        {"symbol": "LINK", "quantity": 50, "stop_price": 1.2},
    ]
    assert {p.action for p in agent.evaluate(context)} == {PROTECTIVE_STOP}


# ─── Phase 2: live top-of-book quote feed ────────────────────────────────────


class _Book:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def _book(bid="174.80", ask="174.90", size="12.5", **changes):
    return {
        "bids": [[bid, size, 3]], "asks": [[ask, "4", 1]], "sequence": 1,
        "auction_mode": False, "time": "2027-01-15T08:00:00.250Z", **changes,
    }


def test_fetch_top_of_book_reads_the_public_exchange_level_one_book():
    calls = []

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Book(_book())

    quote = fetch_top_of_book("SOL-USD", http_get=http_get, now_ms=lambda: NOW_MS)
    assert calls[0][0] == "https://api.exchange.coinbase.com/products/SOL-USD/book"
    assert calls[0][1]["params"] == {"level": 1} and calls[0][1]["timeout"] > 0
    assert quote == {
        "product_id": "SOL-USD", "quote_status": "AVAILABLE",
        "source": "coinbase_exchange_book_level_1",
        "observed_at_ms": NOW_MS, "exchange_time_ms": NOW_MS + 250,
        "bid_usd": 174.8, "bid_size": 12.5, "ask_usd": 174.9, "ask_size": 4.0,
    }

    quotes = fetch_live_quotes(["sol", "SOL-USD", "avax-usd", "bad symbol"], http_get=http_get, now_ms=lambda: NOW_MS)
    assert list(quotes) == ["SOL-USD", "AVAX-USD"]
    assert len(calls) == 3


@pytest.mark.parametrize(
    "response,reason",
    [
        (_Book(_book(), status=429), "request_failed:RuntimeError"),
        (_Book(ValueError("not json")), "request_failed:ValueError"),
        (_Book(["not", "a", "book"]), "malformed_book"),
        (_Book(_book(auction_mode=True)), "auction_mode"),
    ],
)
def test_fetch_top_of_book_reports_failures_as_unavailable(response, reason):
    quote = fetch_top_of_book("SOL-USD", http_get=lambda url, **kw: response)
    assert quote == {"product_id": "SOL-USD", "quote_status": "UNAVAILABLE", "reason": reason}


def test_fetch_top_of_book_handles_one_sided_books_bad_time_and_bad_products():
    def boom(url, **kwargs):
        raise OSError("network down")

    assert fetch_top_of_book("SOL-USD", http_get=boom)["reason"] == "request_failed:OSError"
    assert fetch_top_of_book("../accounts", http_get=boom)["reason"] == "invalid_product"
    assert fetch_top_of_book("SOL-EUR", http_get=boom)["reason"] == "invalid_product"
    one_sided = fetch_top_of_book("SOL-USD", http_get=lambda url, **kw: _Book(_book(asks=[])))
    assert one_sided["quote_status"] == "UNAVAILABLE" and one_sided["ask_usd"] is None
    untimed = fetch_top_of_book("SOL-USD", http_get=lambda url, **kw: _Book(_book(time="yesterday")))
    assert untimed["quote_status"] == "AVAILABLE" and untimed["exchange_time_ms"] is None
    # The executor refuses a book with no exchange timestamp.
    blocks = GuardedDryRunExitExecutor().quote_guard(untimed, 174.8, 1.0, untimed["observed_at_ms"])
    assert "quote_missing_exchange_timestamp" in blocks


def _live_fetcher(calls, **changes):
    def fetch(products):
        calls.append(list(products))
        return {product: {"product_id": product, **_quote(174.8, **changes)} for product in products}
    return fetch


def test_quote_fetcher_is_only_called_for_exits_mode_b_will_simulate(store):
    calls = []
    context = _mixed_context()
    del context["quotes"]
    context["quote_fetcher"] = _live_fetcher(calls)

    agent, _ = _run(store, context)  # Mode A
    assert calls == [] and _by_action(agent)[TRIM_TO_USDC]["status"] == "pending_approval"
    for paused_or_live in ({"emergency_pause": True}, {"emergency_pause": False, "execution_mode": "live_guarded"}):
        store.set_autonomy_settings(autonomy_mode="auto_protect_exits", **paused_or_live)
        _run(store, context)
    assert calls == []

    store.set_autonomy_settings(execution_mode="dry_run")
    agent, _ = _run(store, context)
    assert calls == [["SOL-USD"]]  # the held exit only, never the AVAX entry
    trim = _by_action(agent)[TRIM_TO_USDC]
    assert trim["status"] == "auto_executed_dry_run" and trim["execution"]["bid_usd"] == 174.8
    assert _by_action(agent)[BREAKOUT_ENTRY]["status"] == "pending_approval"


def test_quote_fetcher_failures_and_bad_books_keep_the_exit_blocked(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")

    def run_with(fetcher):
        context = _mixed_context()
        del context["quotes"]
        context["quote_fetcher"] = fetcher
        return _by_action(_run(store, context)[0])[TRIM_TO_USDC]

    def raises(products):
        raise OSError("network down")

    for fetcher, reason in (
        (raises, "quote_unavailable"),
        (lambda products: None, "quote_unavailable"),
        (lambda products: {"SOL-USD": {"product_id": "SOL-USD", "quote_status": "UNAVAILABLE"}}, "quote_unavailable"),
        (_live_fetcher([], ask_usd=180.0), "quote_spread_too_wide"),
        (_live_fetcher([], size=0.5), "insufficient_top_of_book_size"),
        (_live_fetcher([], age_ms=60_000), "quote_stale"),
    ):
        trim = run_with(fetcher)
        assert trim["status"] == "blocked_by_guard" and reason in trim["execution"]["block_reasons"]
    assert store.count_auto_orders_since(0) == 0
    # A blocked exit is rechecked on the next pass and can then fill.
    assert run_with(_live_fetcher([]))["status"] == "auto_executed_dry_run"


def test_supplied_quotes_are_not_refetched(store):
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    calls = []
    context = {**_mixed_context(), "quote_fetcher": _live_fetcher(calls)}
    agent, _ = _run(store, context)
    assert calls == [] and _by_action(agent)[TRIM_TO_USDC]["status"] == "auto_executed_dry_run"


def test_build_cycle_context_carries_the_fetcher_and_risk_settings():
    fetcher = _live_fetcher([])
    context = build_cycle_context(
        _scan(_row("ETH", 3000)), quote_fetcher=fetcher,
        risk={"portfolio_equity_usd": "25000", "base_risk_pct": 0.5, "max_open_risk_pct": None, "other": 1},
    )
    assert context["quote_fetcher"] is fetcher
    assert context["portfolio_equity_usd"] == 25_000.0 and context["base_risk_pct"] == 0.5
    assert "max_open_risk_pct" not in context and "other" not in context
    assert "quote_fetcher" not in build_cycle_context(_scan(_row("ETH", 3000)))


# ─── Phase 2: the scanner's own rows ─────────────────────────────────────────


def test_scanner_rows_feed_the_reload_ladder_and_reward_to_risk(store, daily_series, cycle_fixture):
    import macro_industry_scanner as mis

    down = daily_series(60, [(200, 80), (1261, 8)])
    histories = dict.fromkeys(("BTC-USD", "ETH-USD", "ADA-USD", "XRP-USD"), down)
    histories.update({
        # A recovery that has climbed back into its 0.618-0.786 rollover box.
        "ROLL-USD": daily_series(5, [(200, 40), (700, 6), (561, 16.5)]),
        "AVAX-USD": daily_series(30, [(120, 40), (1200, 4.2), (25, 5.0), (40, 3.5), (76, 5.4)]),
        "FET-USD": cycle_fixture("fet_channel_fixture"),
    })
    scan = mis.scan_universe_cycles(histories)
    rows = {row["symbol"]: row for row in scan["coins"]}
    roll = rows["ROLL"]
    assert roll["rollover_target_box"]["low"] <= roll["price"] <= roll["rollover_target_box"]["high"]
    assert set(roll["support_levels"]) == {"0.618", "0.702", "0.786"}
    assert roll["cycle_low"] < roll["support_levels"]["0.786"] < roll["support_levels"]["0.618"] < roll["price"]
    assert rows["FET"]["full_extension_targets"]["low"] < rows["FET"]["full_extension_targets"]["high"]
    assert isinstance(rows["FET"]["fib_cluster_mids"], list)

    agent, _ = _run(store, {
        "cycle_scan": scan,
        "positions": [{"symbol": "ROLL", "quantity": 40}],
        "watchlist": ["AVAX"],
        "portfolio_equity_usd": 10_000,
    })
    proposals = _by_action(agent)
    trim = proposals[TRIM_TO_USDC]
    plan = trim["reload_plan"]
    assert plan["available"] is True and plan["invalidation_basis"] == "cycle_low"
    assert [t["basis"] for t in plan["tranches"]] == ["log_fib_0.618", "log_fib_0.702", "log_fib_0.786"]
    assert all(plan["invalidation_stop"] < t["level"] < trim["reference_price"] for t in plan["tranches"])
    assert sum(t["usdc"] for t in plan["tranches"]) == pytest.approx(plan["freed_usdc"], abs=0.02)
    assert plan["projected_reloaded_coins"] > plan["trim_quantity"]
    assert plan["net_coin_gain_pct"] > 0

    entry = proposals[BREAKOUT_ENTRY]
    assert entry["reward_to_risk_ratio"] >= 2.0
    assert entry["stop_price"] < entry["reference_price"] < entry["target_price"]
    sizing = entry["sizing"]
    assert sizing["stage_multiplier"] == 0.5  # the fixture universe is in Stage 1
    assert sizing["risk_at_stop_usd"] == pytest.approx(50.0, abs=0.01)
    assert sizing["suggested_notional_usd"] == pytest.approx(
        50.0 / (1 - entry["stop_price"] / entry["reference_price"]), abs=0.01
    )
