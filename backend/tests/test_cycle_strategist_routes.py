import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app
import paper_execution_store
import watchlist
from agents.contracts import AgentObservation
from agents.cycle_context import build_cycle_context, evaluate_smart_alerts
from agents.cycle_strategist import CycleStrategistAgent
from agents.runner import run_once
from agents.store import AgentStore
from smart_alerts import DEFAULT_RULES, SmartAlertEngine

NOW = 1_800_000_000.0
OWNER = {"id": 1, "email": "owner@example.test"}


def _row(symbol, price, **extra):
    return {"symbol": symbol, "product_id": f"{symbol}-USD", "available": True, "price": price, **extra}


def _scan(*rows, stage="stage_1_macro_compression"):
    return {"industry": {"available": True, "liquidity_rotation_stage": stage}, "coins": list(rows)}


SCAN = _scan(
    _row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0}),
    _row(
        "AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=65.0,
        accumulation_invalidation_stop={"stop_price": 28.0},
        rollover_target_box={"low": 40.0, "high": 50.0},
    ),
)


@pytest.fixture
def client(monkeypatch, tmp_path, macro_scan_state):
    monkeypatch.setenv("MW_AGENT_OBSERVATIONS_DB", str(tmp_path / "agents.sqlite"))
    monkeypatch.setenv("MW_SMART_ALERTS_DB", str(tmp_path / "smart.sqlite"))
    monkeypatch.setenv("MW_PAPER_EXECUTION_DB", str(tmp_path / "paper.sqlite"))
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", OWNER["email"])
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "watchlist.sqlite")
    monkeypatch.delenv("MW_NTFY_URL", raising=False)
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: OWNER)
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    monkeypatch.setitem(backend_app.app.config, "TESTING", True)
    return backend_app.app.test_client()


def _seed_proposals():
    agent = CycleStrategistAgent(AgentStore())
    agent.run({
        "now_ts": NOW,
        "cycle_scan": SCAN,
        "positions": [{"symbol": "SOL", "quantity": 10}],
        "watchlist": ["AVAX"],
    })
    return {p["action"]: p for p in agent.last_proposals}


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/agents/proposals"),
        ("post", "/api/agents/proposals/0123456789abcdef/approve"),
        ("get", "/api/agents/autonomy"),
        ("post", "/api/agents/autonomy"),
        ("get", "/api/agents/settings"),
        ("post", "/api/agents/settings"),
        ("get", "/api/smart-alerts/rules"),
        ("post", "/api/smart-alerts/rules"),
        ("patch", "/api/smart-alerts/rules/1"),
        ("delete", "/api/smart-alerts/rules/1"),
        ("get", "/api/smart-alerts/history"),
        ("post", "/api/smart-alerts/test"),
    ],
)
def test_routes_are_owner_only(client, monkeypatch, method, path):
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    anonymous = getattr(client, method)(path, json={})
    assert anonymous.status_code == 401
    assert "no-store" in anonymous.headers["Cache-Control"]
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 2, "email": "x@example.test"})
    forbidden = getattr(client, method)(path, json={})
    assert forbidden.status_code == 403
    assert "no-store" in forbidden.headers["Cache-Control"]


def test_list_approve_and_reject_proposals(client):
    seeded = _seed_proposals()
    body = client.get("/api/agents/proposals").json
    assert body["dry_run_only"] is True
    assert body["autonomy"]["autonomy_mode"] == "approval_queue"
    assert {p["action"] for p in body["proposals"]} == {"TRIM_TO_USDC", "BREAKOUT_ENTRY"}
    assert client.get("/api/agents/proposals?symbol=SOL").json["proposals"][0]["symbol"] == "SOL"

    entry_id = seeded["BREAKOUT_ENTRY"]["proposal_id"]
    trim_id = seeded["TRIM_TO_USDC"]["proposal_id"]
    for proposal_id in (trim_id, entry_id):
        url = f"/api/agents/proposals/{proposal_id}/approve"
        cross_origin = client.post(url, headers={"Origin": "https://other.example.test"})
        assert cross_origin.status_code == 415
        assert "Access-Control-Allow-Origin" not in cross_origin.headers
        assert AgentStore().get_proposal(proposal_id)["status"] == "pending_approval"
        first = client.post(url, json={})
        assert first.status_code == 200
        approved = first.json["proposal"]
        assert approved["status"] == "approved"
        assert approved["execution"] is None
        assert client.post(url, json={}).json["proposal"] == approved
        assert client.post(f"/api/agents/proposals/{proposal_id}/reject", json={}).status_code == 409

    assert client.post("/api/agents/proposals/ffffffffffffffff/approve", json={}).status_code == 404
    assert client.post("/api/agents/proposals/not-an-id/approve", json={}).status_code == 400
    assert client.post(f"/api/agents/proposals/{entry_id}/execute", json={}).status_code == 404
    assert client.get("/api/agents/proposals?status=unknown").status_code == 400


def test_autonomy_settings_round_trip_and_validation(client):
    assert client.get("/api/agents/autonomy").json["autonomy"]["execution_mode"] == "dry_run"
    updated = client.post(
        "/api/agents/autonomy",
        json={"autonomy_mode": "auto_protect_exits", "emergency_pause": True, "daily_order_cap": 5},
    ).json["autonomy"]
    assert updated["autonomy_mode"] == "auto_protect_exits"
    assert updated["emergency_pause"] is True and updated["daily_order_cap"] == 5
    assert client.post("/api/agents/autonomy", json={"execution_mode": "live_guarded"}).json["autonomy"]["execution_mode"] == "live_guarded"
    for bad in (
        {"autonomy_mode": "yolo"},
        {"execution_mode": "live"},
        {"emergency_pause": "yes"},
        {"daily_order_cap": 21},
        {"daily_order_cap": True},
        {"surprise": 1},
    ):
        assert client.post("/api/agents/autonomy", json=bad).status_code == 400, bad
    assert client.post("/api/agents/autonomy", data="x", content_type="text/plain").status_code == 415
    assert client.get("/api/agents/autonomy").json["autonomy"]["daily_order_cap"] == 5


def test_smart_alert_rule_crud(client):
    listed = client.get("/api/smart-alerts/rules").json
    assert [r["name"] for r in listed["rules"]] == [r["name"] for r in DEFAULT_RULES]
    assert "fib_zone_hit" in listed["predicates"] and listed["urgencies"] == ["wake_up", "action_queue", "watch"]

    rule = {
        "name": "RENDER reclaim",
        "urgency": "action_queue",
        "scope": "symbols",
        "symbols": ["render-usd"],
        "conditions": [{"predicate": "price_above", "value": 9.5}],
    }
    created = client.post("/api/smart-alerts/rules", json=rule)
    assert created.status_code == 201
    rule_id = created.json["rule"]["id"]
    assert created.json["rule"]["symbols"] == ["RENDER"]
    assert client.post("/api/smart-alerts/rules", json=rule).status_code == 409
    assert client.post("/api/smart-alerts/rules", json={**rule, "name": "x", "conditions": [{"predicate": "nope"}]}).status_code == 400

    toggled = client.patch(f"/api/smart-alerts/rules/{rule_id}", json={"enabled": False}).json["rule"]
    assert toggled["enabled"] is False
    edited = client.patch(f"/api/smart-alerts/rules/{rule_id}", json={"urgency": "wake_up", "name": "RENDER wake"}).json["rule"]
    assert edited["urgency"] == "wake_up" and edited["name"] == "RENDER wake" and edited["enabled"] is False
    assert client.patch(f"/api/smart-alerts/rules/{rule_id}", json={"urgency": "loud"}).status_code == 400
    assert client.patch(f"/api/smart-alerts/rules/{rule_id}", json={"name": DEFAULT_RULES[0]["name"]}).status_code == 409
    assert client.patch("/api/smart-alerts/rules/9999", json={"enabled": True}).status_code == 404

    assert client.delete(f"/api/smart-alerts/rules/{rule_id}").json["deleted"] == rule_id
    assert client.delete(f"/api/smart-alerts/rules/{rule_id}").status_code == 404


def test_smart_alert_test_fire_is_recorded_and_delivered(client, monkeypatch):
    sent = []
    monkeypatch.setenv("MW_NTFY_URL", "https://ntfy.example.test/topic")
    monkeypatch.setattr("smart_alerts._post_ntfy", lambda url, body, headers: sent.append(headers))
    # The engine binds http_post at construction from the module default.
    monkeypatch.setattr(
        backend_app,
        "_smart_alert_engine",
        lambda: SmartAlertEngine(http_post=lambda url, body, headers: sent.append(headers)),
    )
    fired = client.post("/api/smart-alerts/test", json={"urgency": "wake_up"}).json["alert"]
    assert fired["symbol"] == "TEST" and fired["delivered"]["ntfy"] == "sent"
    assert sent[-1]["Priority"] == "urgent"
    assert client.post("/api/smart-alerts/test", json={"urgency": "loud"}).status_code == 400
    assert client.post("/api/smart-alerts/test", json={"rule_id": 9999}).status_code == 404
    assert client.post("/api/smart-alerts/test", json={"rule_id": "1"}).status_code == 400
    history = client.get("/api/smart-alerts/history").json["history"]
    assert history[0]["symbol"] == "TEST" and history[0]["evidence"] == {"test": True}


@pytest.mark.parametrize(
    "method,path,payload,expected",
    [
        ("get", "/api/agents/proposals?limit=251", None, 400),
        ("get", "/api/smart-alerts/history?limit=0", None, 400),
        ("get", "/api/smart-alerts/history?limit=501", None, 400),
        ("post", "/api/agents/autonomy", [], 400),
        ("post", "/api/smart-alerts/rules", ["bad"], 400),
        ("post", "/api/smart-alerts/test", {"urgency": []}, 400),
        ("post", "/api/smart-alerts/test", {"rule_id": 2**63}, 400),
        ("post", "/api/smart-alerts/test", {"urgency": "watch", "rule_id": 1}, 400),
        ("patch", f"/api/smart-alerts/rules/{2**63}", {"enabled": True}, 404),
        ("delete", f"/api/smart-alerts/rules/{2**63}", None, 404),
        ("head", "/api/smart-alerts/rules", None, 200),
    ],
)
def test_owner_route_validation_and_caching(client, method, path, payload, expected):
    result = getattr(client, method)(path, json=payload)
    assert result.status_code == expected
    assert "no-store" in result.headers["Cache-Control"]


def test_invalid_json_has_no_store_and_leaves_settings_unchanged(client):
    result = client.post(
        "/api/agents/autonomy", data='{"emergency_pause":', content_type="application/json"
    )
    assert result.status_code == 400
    assert "no-store" in result.headers["Cache-Control"]
    assert client.get("/api/agents/autonomy").json["autonomy"]["emergency_pause"] is False


def test_public_observations_and_status_exclude_strategist(client, monkeypatch):
    store = AgentStore()
    for agent in ("tape_scout", "cycle_strategist"):
        run_id = store.begin_run(agent, model_version="test")
        store.record_observations(
            run_id, [AgentObservation(agent=agent, kind="test", summary="test", symbol="SOL")]
        )
        store.finish_run(run_id, status="ok", observation_count=1)

    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    recent = client.get("/api/agents/observations?limit=1").json["observations"]
    assert [row["agent"] for row in recent] == ["tape_scout"]
    assert client.get("/api/agents/observations?agent=cycle_strategist").json["observations"] == []
    status = client.get("/api/agents/status").json
    assert status["total_observations"] == 1
    assert status["last_run"]["agent"] == "tape_scout"
    assert "cycle_strategist" not in {row["agent"] for row in status["agents"]}
    catalog = next(row for row in status["agent_summaries"] if row["agent"] == "cycle_strategist")
    assert catalog["latest_run"] is None and catalog["latest_findings_by_severity"] == {}


def test_public_signup_cannot_claim_configured_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "  Owner@Example.Test ")
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "watchlists.sqlite")
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    monkeypatch.setitem(backend_app.app.config, "TESTING", True)
    client = backend_app.app.test_client()
    result = client.post("/api/auth/signup", json={
        "name": "Someone",
        "email": "OWNER@example.test",
        "password": "a password long enough",
    })
    assert result.status_code == 409
    assert client.get("/api/auth/session").json["authenticated"] is False
    assert client.get("/api/agents/proposals").status_code == 401


def test_test_alert_does_not_reset_a_real_cooldown(tmp_path):
    engine = SmartAlertEngine(tmp_path / "s.sqlite", ntfy_url="", seed_defaults=False)
    rule = engine.upsert_rule({
        "name": "SOL above",
        "urgency": "wake_up",
        "scope": "symbols",
        "symbols": ["SOL"],
        "conditions": [{"predicate": "price_above", "value": 100}],
    })
    engine.send_test(rule_id=rule["id"], now=NOW)
    assert len(engine.evaluate(SCAN, now=NOW + 1)) == 1


def test_runner_feeds_cycle_context_to_strategist_and_smart_alerts(tmp_path):
    store = AgentStore(tmp_path / "agents.sqlite")
    engine = SmartAlertEngine(tmp_path / "smart.sqlite", ntfy_url="", default_quiet_hours=None)
    context = {
        "now_ts": NOW,
        **build_cycle_context(
            SCAN,
            positions=[{"product_id": "SOL-USD", "quantity": "4"}, {"symbol": "SOL", "quantity": 6}, {"symbol": "DOGE", "quantity": 0}],
            watchlist=["avax-usd", {"symbol": "AVAX"}],
        ),
    }
    assert context["positions"] == [{"symbol": "SOL", "product_id": "SOL-USD", "quantity": 10.0}]
    assert context["watchlist"] == ["AVAX"]
    result = run_once(context, store=store, agents=[CycleStrategistAgent()], smart_alert_engine=engine)
    assert result["runs"][0]["observations"] == 2
    assert result["smart_alerts"]["status"] == "ok"
    # The seeded held-position rollover rule fires for SOL.
    assert any(row["symbol"] == "SOL" for row in engine.history())
    assert result["smart_alerts"]["fired"] == len(engine.history())


def test_warming_scan_skips_cycle_agents_and_alerts(tmp_path):
    context = build_cycle_context({"status": "warming", "coins": []}, positions=[{"symbol": "SOL", "quantity": 1}])
    assert context["cycle_scan"] is None
    engine = SmartAlertEngine(tmp_path / "smart.sqlite", ntfy_url="")
    assert evaluate_smart_alerts(context, engine) == {"status": "skipped", "reason": "no_cycle_scan", "fired": []}


def test_open_paper_positions_feed_held_positions(client):
    with paper_execution_store._connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
            ("t1", 1, "SOL-USD", 2.5, 150.0, 10.0, int(NOW)),
        )
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("t2", 1, "ETH-USD", 1.0, 3000.0, 10.0, int(NOW), int(NOW) + 5, 3100.0, 1.0),
        )
    rows = paper_execution_store.list_open_positions(1)
    assert [(r["symbol"], r["quantity"], r["source"]) for r in rows] == [("SOL", 2.5, "paper")]
    assert paper_execution_store.list_open_positions(2) == []


# ─── Phase 2: reload plans, sizing and the new actions over HTTP ─────────────

DAY = 86_400
PHASE2_SOL = dict(
    rollover_target_box={"low": 150.0, "high": 200.0},
    support_levels={"0.618": 120.0, "0.702": 105.0, "0.786": 90.0},
    cycle_low=60.0,
)


def _phase2_run(now, *rows, positions=(), watchlist=(), **context):
    agent = CycleStrategistAgent(AgentStore())
    agent.run({
        "now_ts": now, "cycle_scan": _scan(*rows), "positions": list(positions),
        "watchlist": list(watchlist), "portfolio_equity_usd": 10_000, **context,
    })
    return {p["action"]: p for p in agent.last_proposals}


def test_proposals_expose_reload_plan_sizing_and_reward_to_risk(client):
    seeded = _phase2_run(
        NOW, _row("SOL", 175.0, **PHASE2_SOL), SCAN["coins"][1],
        positions=[{"symbol": "SOL", "quantity": 10, "stop_price": 165.0}], watchlist=["AVAX"],
    )
    body = client.get("/api/agents/proposals").json
    by_action = {p["action"]: p for p in body["proposals"]}
    plan = by_action["TRIM_TO_USDC"]["reload_plan"]
    assert plan["freed_usdc"] == 656.25 and plan["net_coin_gain_pct"] == 27.21
    assert [t["level"] for t in plan["tranches"]] == [120.0, 105.0, 90.0]
    entry = by_action["BREAKOUT_ENTRY"]
    assert entry["reward_to_risk_ratio"] == 7.5 and entry["target_price"] == 45.0
    assert entry["sizing"]["suggested_notional_usd"] == 750.0
    assert entry["sizing"]["risk_budget_pct"] == 0.5
    # A pending trim has freed nothing, so no ladder is open yet.
    assert body["reload_plans"] == []

    trim_id = seeded["TRIM_TO_USDC"]["proposal_id"]
    assert client.post(f"/api/agents/proposals/{trim_id}/approve", json={}).status_code == 200
    (open_plan,) = client.get("/api/agents/proposals").json["reload_plans"]
    assert open_plan["plan_id"] == trim_id and open_plan["symbol"] == "SOL"
    assert open_plan["trim_status"] == "approved" and open_plan["remaining_usdc"] == 656.25
    assert [t["filled"] for t in open_plan["tranches"]] == [False, False, False]
    assert client.get("/api/agents/proposals?symbol=AVAX").json["reload_plans"] == []
    assert len(client.get("/api/agents/proposals?symbol=sol-usd").json["reload_plans"]) == 1


def test_reload_accumulate_round_trip_through_the_routes(client):
    trim = _phase2_run(
        NOW, _row("SOL", 175.0, **PHASE2_SOL), positions=[{"symbol": "SOL", "quantity": 10}]
    )["TRIM_TO_USDC"]
    client.post(f"/api/agents/proposals/{trim['proposal_id']}/approve", json={})

    at_support = _row(
        "SOL", 118.0, **PHASE2_SOL,
        accumulation_invalidation_stop={"stop_price": 110.0},
        weekly_stoch_direction="oversold_turn_up",
    )
    _phase2_run(NOW + DAY, at_support, positions=[{"symbol": "SOL", "quantity": 6.25}])
    listed = client.get("/api/agents/proposals?status=pending_approval").json["proposals"]
    (reload_,) = [p for p in listed if p["action"] == "RELOAD_ACCUMULATE"]
    assert reload_["side"] == "buy" and reload_["product_id"] == "SOL-USD"
    assert reload_["evidence"]["reload_fills"][0]["plan_id"] == trim["proposal_id"]
    assert reload_["sizing"]["funded_usd"] == 164.06

    path = f"/api/agents/proposals/{reload_['proposal_id']}"
    rejected_first = client.post(f"{path}/reject", json={"note": "x"})
    assert rejected_first.status_code == 400  # the body must be an empty object
    approved = client.post(f"{path}/approve", json={}).json["proposal"]
    assert approved["status"] == "approved" and approved["execution"] is None
    (open_plan,) = client.get("/api/agents/proposals").json["reload_plans"]
    assert [t["filled"] for t in open_plan["tranches"]] == [True, False, False]
    assert open_plan["remaining_usdc"] == 492.19
    assert AgentStore().count_auto_orders_since(0) == 0


def test_rejected_reload_leaves_the_rung_open(client):
    trim = _phase2_run(
        NOW, _row("SOL", 175.0, **PHASE2_SOL), positions=[{"symbol": "SOL", "quantity": 10}]
    )["TRIM_TO_USDC"]
    client.post(f"/api/agents/proposals/{trim['proposal_id']}/approve", json={})
    at_support = _row(
        "SOL", 118.0, **PHASE2_SOL,
        accumulation_invalidation_stop={"stop_price": 110.0}, daily_macd_kiss=True,
    )
    reload_ = _phase2_run(NOW + DAY, at_support)["RELOAD_ACCUMULATE"]
    client.post(f"/api/agents/proposals/{reload_['proposal_id']}/reject", json={})
    (open_plan,) = client.get("/api/agents/proposals").json["reload_plans"]
    assert open_plan["remaining_usdc"] == 656.25
    # The next day the same rung is proposed again under a new ID.
    again = _phase2_run(NOW + 2 * DAY, at_support)["RELOAD_ACCUMULATE"]
    assert again["proposal_id"] != reload_["proposal_id"] and again["status"] == "pending_approval"


def test_rotate_to_leader_is_listed_and_decided_like_any_proposal(client):
    AgentStore().set_autonomy_settings(autonomy_mode="auto_protect_exits")
    laggard = _row("DOT", 5.0, above_50w_sma=False, weekly_rsi=40.0, at_multi_year_support=False)
    leader = _row(
        "LINK", 1.0, bucket="deep_accumulation_exhaustion", score=30.0,
        accumulation_invalidation_stop={"stop_price": 0.92},
        rollover_target_box={"low": 1.4, "high": 1.8},
    )
    seeded = _phase2_run(NOW, laggard, leader, positions=[{"symbol": "DOT", "quantity": 100}])
    assert set(seeded) == {"ROTATE_TO_LEADER"}
    (rotation,) = client.get("/api/agents/proposals?symbol=DOT").json["proposals"]
    assert rotation["status"] == "pending_approval"  # never auto-executed, even in Mode B
    assert rotation["pair"]["buy_product_id"] == "LINK-USD"
    assert rotation["pair"]["leader"]["reward_to_risk_ratio"] == 7.5
    assert rotation["sizing"]["suggested_notional_usd"] == 125.0
    approved = client.post(f"/api/agents/proposals/{rotation['proposal_id']}/approve", json={})
    assert approved.json["proposal"]["status"] == "approved"
    assert approved.json["proposal"]["execution"] is None
    assert AgentStore().count_auto_orders_since(0) == 0


def test_phase_two_evidence_stays_off_public_surfaces(client, monkeypatch):
    store = AgentStore()
    result = run_once(
        {
            "now_ts": NOW, "cycle_scan": _scan(_row("SOL", 175.0, **PHASE2_SOL)),
            "positions": [{"symbol": "SOL", "quantity": 10}],
        },
        store=store, agents=[CycleStrategistAgent()],
    )
    assert result["runs"][0]["observations"] == 1
    owner_view = store.latest(agent="cycle_strategist")[0]["evidence"]
    assert owner_view["reload_plan"]["freed_usdc"] == 656.25
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    assert client.get("/api/agents/observations").json["observations"] == []
    assert client.get("/api/agents/proposals").status_code == 401


# ─── POST /api/agents/run-cycle-pass ─────────────────────────────────────────

PASS_URL = "/api/agents/run-cycle-pass"


@pytest.fixture
def cycle_pass(client, monkeypatch):
    """The route with a cached scan, a watchlist, no live portfolio and a counted quote fetcher."""
    state = {"scan": SCAN, "wanted": [], "quotes": [], "holdings": None}

    def scan(wanted):
        state["wanted"].append(list(wanted))
        return state["scan"]

    def quotes(products):
        state["quotes"].append(list(products))
        return {}

    monkeypatch.setattr(backend_app, "_cycle_pass_scan", scan)
    monkeypatch.setattr(backend_app, "_cycle_pass_quote_fetcher", quotes)
    monkeypatch.setattr(backend_app, "_cycle_pass_watchlist", lambda user: ["avax-usd", "AVAX"])
    monkeypatch.setattr(backend_app, "_cycle_pass_portfolio_holdings", lambda: state["holdings"])
    with paper_execution_store._connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
            ("t1", 1, "SOL-USD", 10.0, 150.0, 10.0, int(NOW)),
        )
    return state


def test_cycle_pass_is_owner_only_and_needs_a_json_body(client, cycle_pass, monkeypatch):
    for body in ({"data": "{}"}, {"headers": {"Origin": "https://other.example.test"}}):
        refused = client.post(PASS_URL, **body)
        assert refused.status_code == 415 and "no-store" in refused.headers["Cache-Control"]
    assert client.post(PASS_URL, json=[]).status_code == 400
    assert client.post(PASS_URL, json={"symbols": ["SOL"]}).status_code == 400
    assert client.get(PASS_URL).status_code == 405
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    anonymous = client.post(PASS_URL, json={})
    assert anonymous.status_code == 401 and "no-store" in anonymous.headers["Cache-Control"]
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 2, "email": "x@example.test"})
    forbidden = client.post(PASS_URL, json={})
    assert forbidden.status_code == 403 and "no-store" in forbidden.headers["Cache-Control"]
    # Nothing ran for any refused request.
    assert cycle_pass["wanted"] == [] and AgentStore().list_proposals(limit=10) == []


def test_cycle_pass_runs_strategist_and_alerts_from_paper_positions(client, cycle_pass):
    response = client.post(PASS_URL, json={})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    body = response.json
    assert body["status"] == "ok" and body["dry_run_only"] is True
    assert body["positions_source"] == "paper" and body["positions"] == 1 and body["watchlist"] == 1
    assert body["cycle_scan"]["usable"] is True
    assert body["runs"] == [{"agent": "cycle_strategist", "status": "ok", "observations": 2}]
    assert {p["action"] for p in body["proposals"]} == {"TRIM_TO_USDC", "BREAKOUT_ENTRY"}
    assert body["smart_alerts"]["status"] == "ok"
    assert body["autonomy"]["autonomy_mode"] == "approval_queue"
    # Held and watchlist symbols are asked of the cached scan, held first.
    assert cycle_pass["wanted"] == [["SOL-USD", "AVAX-USD"]]
    # Approval-queue mode never fetches a live quote.
    assert cycle_pass["quotes"] == []
    listed = client.get("/api/agents/proposals").json["proposals"]
    assert {p["action"] for p in listed} == {"TRIM_TO_USDC", "BREAKOUT_ENTRY"}
    assert all(p["status"] == "pending_approval" for p in listed)
    # The owner's symbols move to the front of the next atlas universe.
    assert backend_app._MACRO_ATLAS_PRIORITY["held"] == ("SOL",)
    assert backend_app._MACRO_ATLAS_PRIORITY["watchlist"] == ("AVAX",)


def test_cycle_pass_hands_held_coins_cached_history_to_the_reload_ladder(client, cycle_pass, monkeypatch):
    import macro_industry_scanner as mis

    # Without an atlas the pass still runs and the ladder keeps 25/35/40.
    monkeypatch.setattr(backend_app.time, "time", lambda: NOW)
    monkeypatch.setattr(backend_app, "_MACRO_ATLAS", None)
    cycle_pass["scan"] = _scan(_row("SOL", 175.0, **PHASE2_SOL))
    trim = client.post(PASS_URL, json={}).json["proposals"][0]
    assert trim["reload_plan"]["weight_source"] == "default"

    # With deep-wick history in the atlas cache, the ladder tilts deep.
    wicky = [
        [NOW - (100 - i) * DAY, 92.0 if i % 7 == 0 else 100.0, 110.0, 100.0, 105.0, 10.0]
        for i in range(100)
    ]
    atlas = mis.CycleAtlas()
    atlas.entries["SOL-USD"] = {"candles": wicky, "fetched_at": NOW, "checked_at": NOW}
    monkeypatch.setattr(backend_app, "_MACRO_ATLAS", atlas)
    assert backend_app._cycle_pass_histories(["SOL", "NOPE"], now=NOW) == {"SOL-USD": wicky}
    deep = client.post(PASS_URL, json={}).json["proposals"][0]["reload_plan"]
    assert deep["weight_source"] == "ladder_optimizer"
    assert deep["ladder_optimizer"]["regime"] == "deep_wick"
    atlas.entries["SOL-USD"]["fetched_at"] -= DAY
    stale = client.post(PASS_URL, json={}).json["proposals"][0]["reload_plan"]
    assert stale["weight_source"] == "default"


def test_cycle_pass_prefers_the_live_portfolio_and_fetches_quotes_only_in_mode_b(client, cycle_pass):
    cycle_pass["holdings"] = [
        {"symbol": "SOL", "quantity": 4.0, "market_value_usd": 700.0},
        {"symbol": "USDC", "quantity": 2_000.0, "market_value_usd": 2_000.0, "is_cash": True},
        "junk",
    ]
    first = client.post(PASS_URL, json={}).json
    assert first["positions_source"] == "portfolio" and first["positions"] == 1
    assert first["cluster_guard"]["limits"]["equity_usd"] == 2700.0
    (blocked,) = first["cluster_guard"]["suppressed_proposals"]
    assert blocked["symbol"] == "AVAX" and blocked["suggested_notional_usd"] > 0
    assert blocked["suppression_reason"] == "cluster_heat_cap_exceeded"
    assert cycle_pass["quotes"] == []

    AgentStore().set_autonomy_settings(autonomy_mode="auto_protect_exits")
    cycle_pass["scan"] = _scan(_row("SOL", 176.0, rollover_target_box={"low": 150.0, "high": 200.0}))
    second = client.post(PASS_URL, json={}).json
    assert second["status"] == "ok" and second["autonomy"]["autonomy_mode"] == "auto_protect_exits"
    # Mode B asks for a quote only for the exit it is about to simulate.
    assert cycle_pass["quotes"] == [["SOL-USD"]]
    assert AgentStore().count_auto_orders_since(0) == 0  # no quote came back, so nothing executed


def test_desk_pass_persists_configured_paper_costs(client, cycle_pass, monkeypatch):
    monkeypatch.setenv("MW_CYCLE_FEE_BPS", "60")
    monkeypatch.setenv("MW_CYCLE_SLIPPAGE_BPS", "10")
    cycle_pass["scan"] = _scan(_row("SOL", 175, **PHASE2_SOL))
    trim = client.post(PASS_URL, json={}).json["proposals"][0]
    assert trim["cost_model"]["fee_bps"] == 60 and trim["cost_model"]["slippage_bps"] == 10
    plan = trim["reload_plan"]
    expected = int(3.75 * 175 * .999 * .994 * 100) / 100
    assert plan["freed_usdc"] == expected
    assert sum(rung["usdc"] for rung in plan["tranches"]) == pytest.approx(expected)
    AgentStore().decide_proposal(trim["proposal_id"], "approve")
    summary = AgentStore().get_compounding_summary({"SOL": 118})
    assert summary["freed_usdc_available"] == summary["remaining_cash_usd"] == expected
    assert summary["fees_deducted_usd"] > 0 and summary["slippage_deducted_usd"] > 0


def test_ladder_history_must_match_the_scan_revision(client, monkeypatch):
    import macro_industry_scanner as scanner

    daily = [[int(NOW // DAY - i) * DAY, 90, 110, 100, 105, 1] for i in (2, 1)]
    atlas = scanner.CycleAtlas()
    atlas.entries["SOL-USD"] = {"candles": daily, "fetched_at": NOW, "checked_at": NOW}
    monkeypatch.setattr(backend_app, "_MACRO_ATLAS", atlas)
    scan = {
        "market_snapshot": {"snapshot_id": "first"},
        "coins": [{"product_id": "SOL-USD", "history_id": scanner.daily_history_id(daily)}],
    }
    assert backend_app._cycle_pass_histories(["SOL"], now=NOW, scan=scan) == {"SOL-USD": daily}
    atlas.entries["SOL-USD"]["candles"] = [daily[0], [*daily[1][:4], 106, 1]]
    assert backend_app._cycle_pass_histories(["SOL"], now=NOW, scan=scan) == {}


def test_cycle_pass_skips_when_the_cached_scan_is_not_usable(client, cycle_pass):
    for scan in (None, {"status": "refreshing", "computed_at": NOW, "ttl_seconds": 1800, "coins": [_row("SOL", 175.0)]}):
        cycle_pass["scan"] = scan
        body = client.post(PASS_URL, json={}).json
        assert body["status"] == "skipped" and body["reason"] == "no_cycle_scan"
        assert body["cycle_scan"]["usable"] is False and body["proposals"] == [] and body["runs"] == []
    assert client.get("/api/agents/proposals").json["proposals"] == []
    assert cycle_pass["quotes"] == []


def test_cycle_pass_scan_runs_while_outer_atlas_slices_fill(client, monkeypatch, macro_scan_state):
    from agents.cycle_context import core_and_priority_ready, usable_cycle_scan

    now = backend_app.time.time()
    filling = {
        "status": "ready", "computed_at": now, "ttl_seconds": 1800,
        "industry": {"available": True}, "coins": [_row("SOL", 175.0)],
        "unavailable": ["GONE-USD"], "ready_count": 22, "target_universe_size": 120,
        "atlas_refreshing": True, "requested": 120,
    }
    assert core_and_priority_ready(filling, ["SOL-USD", "GONE-USD"]) is True
    assert core_and_priority_ready(filling, ["SOL-USD", "AVAX-USD"]) is False
    assert core_and_priority_ready({**filling, "industry": {"available": False}}, []) is False
    assert core_and_priority_ready(None, []) is False

    monkeypatch.setattr(backend_app, "_macro_scan_snapshot", lambda wanted, allow_inline=True: filling)
    monkeypatch.setattr(backend_app, "_cycle_pass_positions", lambda user: ([{"symbol": "SOL", "quantity": 10}], "paper", None))
    monkeypatch.setattr(backend_app, "_cycle_pass_watchlist", lambda user: ["GONE"])
    macro_scan_state.update(
        payload=filling, computed_at=now, day=backend_app._macro_scan_day(now),
        products=("SOL-USD", "AVAX-USD", "GONE-USD"),
    )
    ready = backend_app._cycle_pass_scan(["SOL-USD", "GONE-USD"])
    assert ready["status"] == "ready" and ready["atlas_refreshing"] is True
    assert usable_cycle_scan(ready, now=now + 60) is True
    assert usable_cycle_scan(ready, now=now + 1801) is False
    body = client.post(PASS_URL, json={}).json
    assert body["status"] == "ok" and body["cycle_scan"]["atlas_refreshing"] is True
    # An owner symbol that has not been read yet keeps the pass waiting.
    assert backend_app._cycle_pass_scan(["SOL-USD", "AVAX-USD"])["status"] == "refreshing"
    assert backend_app._cycle_scan_prices(ready) == {"SOL": 175.0}
    # A prior UTC day's snapshot cannot be promoted, even when its age is small.
    macro_scan_state["day"] -= 1
    assert backend_app._cycle_pass_scan(["SOL-USD"])["status"] == "refreshing"


def test_atlas_priority_is_seeded_from_sqlite_requests_and_movers(client, monkeypatch, macro_scan_state):
    import macro_industry_scanner as mis

    watchlist._ensure_watchlist_schema()
    monkeypatch.delenv("COINBASE_PORTFOLIO_OWNER_EMAIL")
    other_client = backend_app.app.test_client()
    for signup_client, email in ((client, OWNER["email"]), (other_client, "other@example.test")):
        signup = signup_client.post(
            "/api/auth/signup", json={"name": email, "email": email, "password": "fixture-password"},
        )
        assert signup.status_code == 201
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", OWNER["email"])
    watchlist_id = client.get("/api/watchlists").json["watchlists"][0]["id"]
    assert client.post(f"/api/watchlists/{watchlist_id}/items", json={"symbol": "ARB"}).status_code in (200, 201)
    with paper_execution_store._connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
            ("t1", 1, "RENDER-USD", 2.0, 5.0, 10.0, int(NOW)),
        )
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("t2", 1, "ETH-USD", 1.0, 3000.0, 10.0, int(NOW), int(NOW) + 5, 3100.0, 1.0),
        )
        conn.execute(
            "INSERT INTO paper_execution_positions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
            ("t3", 2, "PRIVATE-USD", 1.0, 30.0, 10.0, int(NOW)),
        )
    trim = _phase2_run(
        NOW, _row("INJ", 175.0, **PHASE2_SOL), positions=[{"symbol": "INJ", "quantity": 10}]
    )["TRIM_TO_USDC"]
    client.post(f"/api/agents/proposals/{trim['proposal_id']}/approve", json={})

    monkeypatch.setattr(backend_app, "latest_quote_volume_by_product", lambda now: {"AAA-USD": {"quote_volume_usd": 5.0}})
    known = {"FET-USD", "USDC-USD", "WBTC-USD"}
    monkeypatch.setattr(backend_app, "_load_product_ids", lambda **kwargs: setattr(backend_app, "PRODUCT_IDS", known))
    monkeypatch.setitem(backend_app.cache, "data", {"gainers": [{"symbol": "PEPE"}]})
    reads = []
    monkeypatch.setattr(backend_app, "_macro_atlas_fetch", lambda product: reads.append(product) or [])
    core = [*mis.MAJORS, *mis.ALT_INDEX_MEMBERS]
    body = client.get("/api/macro-cycle-scan?symbols=FET,fet-USD,USDC,WBTC,NOPE,bad!sym").json
    assert body["status"] == "ready"
    expected = [*core, "RENDER-USD", "ARB-USD", "INJ-USD", "FET-USD", "PEPE-USD", "AAA-USD"]
    assert reads == expected == list(macro_scan_state["products"])
    assert backend_app._MACRO_ATLAS_PRIORITY["requested"] == ("FET-USD",)
    assert body["atlas_refreshing"] is False


def test_compounding_summary_tracks_ladders_extra_coins_and_drawdown(client, cycle_pass):
    empty = client.get("/api/agents/proposals").json["compounding_summary"]
    assert empty["freed_usdc_available"] == 0 and empty["active_ladders_count"] == 0
    assert empty["realized_extra_coins_by_symbol"] == {} and empty["drawdown_avoided_usd"] == 0

    trim = _phase2_run(
        NOW, _row("SOL", 175.0, **PHASE2_SOL), positions=[{"symbol": "SOL", "quantity": 10}]
    )["TRIM_TO_USDC"]
    client.post(f"/api/agents/proposals/{trim['proposal_id']}/approve", json={})
    opened = AgentStore().get_compounding_summary({"SOL": 118.0, "AVAX": 1.0})
    assert opened["freed_usdc_available"] == 656.25 and opened["active_ladders_count"] == 1
    assert opened["realized_extra_coins_by_symbol"] == {}
    # 3.75 SOL sold at 175 and now marked at 118.
    assert opened["drawdown_avoided_usd"] == 213.75 and opened["drawdown_priced_symbols"] == ["SOL"]
    assert AgentStore().get_compounding_summary({"SOL": 180.0})["drawdown_avoided_usd"] == 0
    rungs = trim["reload_plan"]["tranches"]
    ladder = sum(t["usdc"] / t["level"] - t["usdc"] / 175.0 for t in rungs)
    assert opened["projected_extra_coins_by_symbol"]["SOL"] == pytest.approx(ladder, abs=0.01)
    # The same 27.21% of the 10 held coins the plan itself projects.
    assert round(ladder / 10 * 100, 2) == trim["reload_plan"]["net_coin_gain_pct"]

    at_support = _row(
        "SOL", 118.0, **PHASE2_SOL,
        accumulation_invalidation_stop={"stop_price": 110.0},
        weekly_stoch_direction="oversold_turn_up",
    )
    reload_ = _phase2_run(NOW + DAY, at_support, positions=[{"symbol": "SOL", "quantity": 6.25}])["RELOAD_ACCUMULATE"]
    client.post(f"/api/agents/proposals/{reload_['proposal_id']}/approve", json={})
    filled = client.get("/api/agents/proposals").json["compounding_summary"]
    assert filled["freed_usdc_available"] == 492.19 and filled["active_ladders_count"] == 1
    extra = 164.06 / reload_["reference_price"] - 164.06 / 175.0
    assert filled["realized_extra_coins_by_symbol"] == {"SOL": pytest.approx(extra, abs=1e-6)}
    assert filled["projected_extra_coins_by_symbol"]["SOL"] > filled["realized_extra_coins_by_symbol"]["SOL"]
    assert filled["dry_run_only"] is True

    # The pass reports the same summary, priced from the scan it just used.
    cycle_pass["scan"] = _scan(_row("SOL", 118.0))
    after = client.post(PASS_URL, json={}).json["compounding_summary"]
    assert after["drawdown_avoided_usd"] == 213.75 and after["freed_usdc_available"] == 492.19
    cycle_pass["scan"] = None
    assert "compounding_summary" in client.post(PASS_URL, json={}).json


def test_protective_stop_records_quantity_and_counts_toward_drawdown_avoided(client):
    broken = _row("DOT", 9.0, accumulation_invalidation_stop={"stop_price": 10.0})
    stop = _phase2_run(NOW, broken, positions=[{"symbol": "DOT", "quantity": 40}])["PROTECTIVE_STOP"]
    assert stop["evidence"]["quantity"] == 40 and stop["evidence"]["notional_usd"] == 360.0
    # Pending stops are not counted; an approved one is.
    assert AgentStore().get_compounding_summary({"DOT": 6.0})["drawdown_avoided_usd"] == 0
    client.post(f"/api/agents/proposals/{stop['proposal_id']}/approve", json={})
    summary = AgentStore().get_compounding_summary({"DOT": 6.0})
    assert summary["drawdown_avoided_usd"] == 120.0  # 40 DOT, 9.00 -> 6.00
    assert summary["drawdown_priced_symbols"] == ["DOT"]


def test_compounding_uses_simulated_fill_and_does_not_count_overlapping_exits(client):
    store = AgentStore()
    start = backend_app.time.time() - 3 * DAY
    trim = _phase2_run(
        start, _row("SOL", 175.0, **PHASE2_SOL), positions=[{"symbol": "SOL", "quantity": 10}]
    )["TRIM_TO_USDC"]
    saved, _ = store.route_proposal(
        trim, lambda *args: ("auto_executed_dry_run", {"fill_price": 160, "base_size": 2.5, "proceeds_usd": 400}),
        clock=lambda: start,
    )
    assert saved["status"] == "auto_executed_dry_run"
    opened = store.get_compounding_summary({"SOL": 80})
    assert opened["freed_usdc_available"] == 400 and opened["active_ladders_count"] == 1
    assert opened["drawdown_avoided_usd"] == 200

    broken = _row("SOL", 90, accumulation_invalidation_stop={"stop_price": 100})
    for days in (1, 2):
        stop = _phase2_run(
            start + days * DAY, broken, positions=[{"symbol": "SOL", "quantity": 10}],
        )["PROTECTIVE_STOP"]
        store.decide_proposal(stop["proposal_id"], "approve")
    # The paper trim covered 2.5 SOL. The stops cover the remaining 7.5 only once.
    assert store.get_compounding_summary({"SOL": 80})["drawdown_avoided_usd"] == 275
    summary = store.get_compounding_summary({"SOL": float("nan")})
    assert summary["drawdown_avoided_usd"] == 0 and summary["drawdown_priced_symbols"] == []
    assert summary["freed_usdc_available"] == 400


def test_compounding_debits_legacy_reload_once_and_ignores_unfunded_fills(client):
    store = AgentStore()
    trim = _phase2_run(
        NOW, _row("SOL", 175.0, **PHASE2_SOL), positions=[{"symbol": "SOL", "quantity": 10}]
    )["TRIM_TO_USDC"]
    store.decide_proposal(trim["proposal_id"], "approve")
    rung = trim["reload_plan"]["tranches"][0]
    for i, symbol in enumerate(("AVAX", "SOL", "SOL")):
        # Historical approvals consumed whole rungs. Import stored records
        # through the ledger to exercise duplicates predating validation.
        store.route_proposal({
            "proposal_id": f"legacy-{i}", "agent": "cycle_strategist",
            "action": "RELOAD_ACCUMULATE", "side": "buy", "symbol": symbol, "product_id": f"{symbol}-USD",
            "reference_price": 118,
            "evidence": {"reload_fills": [{"plan_id": trim["proposal_id"], "tranche": rung["index"]}]},
        }, lambda *args: ("approved", None), clock=lambda: NOW + DAY)
    summary = store.get_compounding_summary()
    expected = rung["usdc"] / 118 - rung["usdc"] / 175
    assert summary["realized_extra_coins_by_symbol"] == {"SOL": pytest.approx(expected)}
    assert summary["freed_usdc_available"] == 492.19
    assert summary["projected_extra_coins_by_symbol"]["SOL"] > expected


def test_atlas_movers_read_only_the_in_memory_board_snapshot(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the scan worker must not fetch prices")

    monkeypatch.setattr(backend_app, "get_crypto_data", boom)
    monkeypatch.setitem(backend_app.cache, "data", None)
    assert backend_app._macro_atlas_movers() == []
    monkeypatch.setitem(backend_app.cache, "data", {"gainers": [{"symbol": "PEPE"}, "junk", {"symbol": "WIF"}]})
    assert backend_app._macro_atlas_movers() == ["PEPE", "WIF"]


def test_cycle_pass_refuses_to_overlap_another_pass(client, cycle_pass):
    assert backend_app._CYCLE_PASS_LOCK.acquire(blocking=False)
    try:
        busy = client.post(PASS_URL, json={})
        assert busy.status_code == 409 and "no-store" in busy.headers["Cache-Control"]
    finally:
        backend_app._CYCLE_PASS_LOCK.release()
    assert client.post(PASS_URL, json={}).status_code == 200


def test_cycle_pass_releases_lock_after_error(client, cycle_pass, monkeypatch):
    def fail(*args):
        raise RuntimeError("injected desk pass failure")

    with monkeypatch.context() as patch:
        patch.setattr(backend_app, "_cycle_pass_positions", fail)
        patch.setitem(backend_app.app.config, "PROPAGATE_EXCEPTIONS", False)
        response = client.post(PASS_URL, json={})
        assert response.status_code == 500
        assert response.headers["Cache-Control"] == "private, no-store"
    assert client.post(PASS_URL, json={}).status_code == 200


# ─── Phase 5: mission stances ────────────────────────────────────────────────

SETTINGS_URL = "/api/agents/settings"
STANCE_KEYS = {"configured_stance", "effective_stance", "effective_stance_reason", "stance_profiles"}


def test_settings_route_validates_and_round_trips_the_stance(client):
    first = client.get(SETTINGS_URL)
    assert first.status_code == 200 and first.headers["Cache-Control"] == "private, no-store"
    assert first.json["autonomy"]["stance"] == "orbit" and STANCE_KEYS <= set(first.json)
    assert set(first.json["stance_profiles"]) == {"autopilot", "bunker", "orbit", "gravity_assist", "full_burn"}

    saved = client.post(SETTINGS_URL, json={"stance": "gravity_assist"})
    assert saved.status_code == 200
    assert saved.json["autonomy"]["stance"] == "gravity_assist"
    assert saved.json["configured_stance"] == saved.json["effective_stance"] == "gravity_assist"
    assert saved.json["stance_profiles"]["gravity_assist"]["max_total_heat_pct"] == 7.5

    for bad in ("moon", "", None, 1, ["orbit"], "Full_Burn"):
        refused = client.post(SETTINGS_URL, json={"stance": bad})
        assert refused.status_code == 400, bad
        assert "stance" in refused.json["error"] and "no-store" in refused.headers["Cache-Control"]
    # The autonomy route is the same store.
    assert client.get("/api/agents/autonomy").json["autonomy"]["stance"] == "gravity_assist"
    both = client.post(SETTINGS_URL, json={"stance": "bunker", "emergency_pause": True}).json
    assert both["autonomy"]["stance"] == "bunker" and both["autonomy"]["emergency_pause"] is True


def test_proposals_list_exposes_the_configured_and_effective_stance(client):
    body = client.get("/api/agents/proposals").json
    assert body["configured_stance"] == body["effective_stance"] == "orbit"
    assert body["effective_stance_reason"] == "Manual stance: Low-Lunar Orbit."
    assert body["stance_profiles"]["bunker"]["base_ladder_weights"] == [0.15, 0.3, 0.55]

    AgentStore().set_autonomy_settings(stance="autopilot")
    body = client.get("/api/agents/proposals").json
    # Without a usable cycle scan Auto-Pilot holds the bunker.
    assert body["configured_stance"] == "autopilot" and body["effective_stance"] == "bunker"
    assert "unavailable" in body["effective_stance_reason"]


def test_cycle_pass_runs_the_autopilot_gear_and_reports_it(client, cycle_pass):
    AgentStore().set_autonomy_settings(stance="autopilot")
    risk_off = _scan(*SCAN["coins"])
    risk_off["industry"]["macro_regime_gate"] = "risk_off_headwind"
    cycle_pass["scan"] = risk_off
    body = client.post(PASS_URL, json={}).json
    assert body["status"] == "ok"
    assert body["configured_stance"] == "autopilot" and body["effective_stance"] == "bunker"
    assert "risk-off" in body["effective_stance_reason"] and STANCE_KEYS <= set(body)
    # Bunker trims harder and its entry gate holds back the plain AVAX breakout.
    (trim,) = body["proposals"]
    assert trim["action"] == "TRIM_TO_USDC" and trim["trim_pct"] == 53.6
    assert trim["evidence"]["configured_stance"] == "autopilot"
    assert trim["evidence"]["effective_stance"] == "bunker"

    cycle_pass["scan"] = None
    skipped = client.post(PASS_URL, json={}).json
    assert skipped["status"] == "skipped"
    assert skipped["configured_stance"] == "autopilot" and skipped["effective_stance"] == "bunker"
