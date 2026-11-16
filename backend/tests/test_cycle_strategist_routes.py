import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app
import paper_execution_store
import watchlist
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
    _row("AVAX", 30.0, breaking_confirmation_pivot=True, weekly_rsi=65.0),
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
    assert getattr(client, method)(path, json={}).status_code == 401
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 2, "email": "x@example.test"})
    assert getattr(client, method)(path, json={}).status_code == 403


def test_list_approve_and_reject_proposals(client):
    seeded = _seed_proposals()
    body = client.get("/api/agents/proposals").json
    assert body["dry_run_only"] is True
    assert body["autonomy"]["autonomy_mode"] == "approval_queue"
    assert {p["action"] for p in body["proposals"]} == {"TRIM_TO_USDC", "BREAKOUT_ENTRY"}
    assert client.get("/api/agents/proposals?symbol=SOL").json["proposals"][0]["symbol"] == "SOL"

    trim_id = seeded["TRIM_TO_USDC"]["proposal_id"]
    approved = client.post(f"/api/agents/proposals/{trim_id}/approve").json
    assert approved["proposal"]["status"] == "approved"
    assert approved["proposal"]["execution"] is None  # approval never executes
    assert client.post(f"/api/agents/proposals/{trim_id}/reject").status_code == 409

    entry_id = seeded["BREAKOUT_ENTRY"]["proposal_id"]
    assert client.post(f"/api/agents/proposals/{entry_id}/reject").json["proposal"]["status"] == "rejected"
    assert client.post("/api/agents/proposals/ffffffffffffffff/approve").status_code == 404
    assert client.post("/api/agents/proposals/not-an-id/approve").status_code == 400
    assert client.post(f"/api/agents/proposals/{entry_id}/execute").status_code == 404
    assert client.get("/api/agents/proposals?status=Bad!").status_code == 400


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
    assert client.patch(f"/api/smart-alerts/rules/{rule_id}", json={"name": DEFAULT_RULES[0]["name"]}).status_code == 400
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
