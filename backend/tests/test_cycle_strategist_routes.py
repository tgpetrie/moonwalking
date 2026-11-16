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
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MW_AGENT_OBSERVATIONS_DB", str(tmp_path / "agents.sqlite"))
    monkeypatch.setenv("MW_SMART_ALERTS_DB", str(tmp_path / "smart.sqlite"))
    monkeypatch.setenv("MW_PAPER_EXECUTION_DB", str(tmp_path / "paper.sqlite"))
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", OWNER["email"])
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
        positions=[{"symbol": "SOL", "quantity": 10}], watchlist=["AVAX"],
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
