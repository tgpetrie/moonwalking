"""HTTP-level tests: auth gating, user scoping, consent, and validation."""

import os
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import watchlist
import alert_rules
import alert_rules_api
from alert_evaluator import evaluate_rule


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "wl.sqlite")
    monkeypatch.setattr(alert_rules, "_schema_ready", False)
    watchlist._ensure_watchlist_schema()
    alert_rules.ensure_alert_schema()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(alert_rules_api.alert_rules_bp)
    return app.test_client()


def _mk_user(email="a@example.com", username="alice"):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        cur = conn.execute(
            """INSERT INTO users (email, password_hash, display_name, username,
               plan, created_at, updated_at) VALUES (?,?,?,?,?,?,?)""",
            (email, "x", "A", username, "Free Account", now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _login(monkeypatch, user_id):
    monkeypatch.setattr(
        alert_rules_api, "get_authenticated_user", lambda: {"id": user_id}
    )


def _logout(monkeypatch):
    monkeypatch.setattr(alert_rules_api, "get_authenticated_user", lambda: None)


# ── auth gating ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/alert-rules"),
        ("post", "/api/alert-rules"),
        ("get", "/api/alert-rules/rule_x"),
        ("patch", "/api/alert-rules/rule_x"),
        ("delete", "/api/alert-rules/rule_x"),
        ("get", "/api/alert-recommendations"),
        ("post", "/api/alert-recommendations/refresh"),
        ("post", "/api/alert-recommendations/rec_x/accept"),
        ("post", "/api/alert-recommendations/rec_x/dismiss"),
        ("get", "/api/alert-history"),
    ],
)
def test_all_routes_require_auth(client, monkeypatch, method, path):
    _logout(monkeypatch)
    resp = getattr(client, method)(path, json={})
    assert resp.status_code == 401


# ── create / read ────────────────────────────────────────────────────────────


def test_create_rule_returns_201(client, monkeypatch):
    uid = _mk_user()
    _login(monkeypatch, uid)
    resp = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["rule"]["symbol"] == "BTC"
    assert body["not_financial_advice"] is True
    assert "not financial advice" in body["disclaimer"].lower()


def test_create_rejects_already_satisfied_target(client, monkeypatch):
    _login(monkeypatch, _mk_user())
    resp = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 90.0,
            "current_price": 100.0,
        },
    )
    assert resp.status_code == 400
    assert "already at or below" in resp.get_json()["error"]


def test_create_rejects_unsupported_window(client, monkeypatch):
    _login(monkeypatch, _mk_user())
    resp = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "percent_move",
            "direction": "up",
            "threshold": 5,
            "window": "7d",
        },
    )
    assert resp.status_code == 400
    assert "Time window" in resp.get_json()["error"]


def test_list_rules(client, monkeypatch):
    uid = _mk_user()
    _login(monkeypatch, uid)
    client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    )
    body = client.get("/api/alert-rules").get_json()
    assert body["count"] == 1


# ── pause / resume / delete ──────────────────────────────────────────────────


def test_pause_resume_delete(client, monkeypatch):
    uid = _mk_user()
    _login(monkeypatch, uid)
    rid = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    ).get_json()["rule"]["id"]

    assert (
        client.post(f"/api/alert-rules/{rid}/pause").get_json()["rule"]["status"]
        == "paused"
    )
    assert (
        client.post(f"/api/alert-rules/{rid}/resume").get_json()["rule"]["status"]
        == "active"
    )
    assert client.delete(f"/api/alert-rules/{rid}").status_code == 200
    assert client.get(f"/api/alert-rules/{rid}").status_code == 404


def test_update_requires_a_field(client, monkeypatch):
    uid = _mk_user()
    _login(monkeypatch, uid)
    rid = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    ).get_json()["rule"]["id"]
    assert client.patch(f"/api/alert-rules/{rid}", json={}).status_code == 400


# ── cross-user access ────────────────────────────────────────────────────────


def test_other_user_cannot_read_update_or_delete(client, monkeypatch):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _login(monkeypatch, a)
    rid = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    ).get_json()["rule"]["id"]

    _login(monkeypatch, b)
    assert client.get(f"/api/alert-rules/{rid}").status_code == 404
    assert (
        client.patch(f"/api/alert-rules/{rid}", json={"status": "paused"}).status_code
        == 404
    )
    assert client.delete(f"/api/alert-rules/{rid}").status_code == 404
    assert client.get("/api/alert-rules").get_json()["count"] == 0

    _login(monkeypatch, a)  # still intact for the owner
    assert client.get(f"/api/alert-rules/{rid}").status_code == 200


# ── recommendations require consent ──────────────────────────────────────────


def _add_holding(uid, symbol):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        conn.execute(
            """INSERT INTO manual_cost_basis (user_id, symbol, average_price, note,
               created_at, updated_at) VALUES (?,?,?,?,?,?)""",
            (uid, symbol, 100.0, "", now, now),
        )
        conn.commit()
    finally:
        conn.close()


def test_refresh_creates_pending_only(client, monkeypatch):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    _login(monkeypatch, uid)

    recs = client.post("/api/alert-recommendations/refresh").get_json()[
        "recommendations"
    ]
    assert recs and all(r["status"] == "pending" for r in recs)
    # Nothing was activated as a side effect.
    assert client.get("/api/alert-rules").get_json()["count"] == 0


def test_accept_activates_rule(client, monkeypatch):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    _login(monkeypatch, uid)
    rec = client.post("/api/alert-recommendations/refresh").get_json()[
        "recommendations"
    ][0]

    resp = client.post(f"/api/alert-recommendations/{rec['id']}/accept", json={})
    assert resp.status_code == 201
    rule = resp.get_json()["rule"]
    assert rule["status"] == "active" and rule["source"] == "recommended"
    assert client.get("/api/alert-recommendations").get_json()["count"] == 0


def test_dismiss_is_permanent(client, monkeypatch):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    _login(monkeypatch, uid)
    rec = client.post("/api/alert-recommendations/refresh").get_json()[
        "recommendations"
    ][0]

    assert (
        client.post(f"/api/alert-recommendations/{rec['id']}/dismiss").status_code
        == 200
    )
    client.post("/api/alert-recommendations/refresh")
    assert client.get("/api/alert-recommendations").get_json()["count"] == 0


def test_other_user_cannot_accept(client, monkeypatch):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _add_holding(a, "ETH")
    _login(monkeypatch, a)
    rec = client.post("/api/alert-recommendations/refresh").get_json()[
        "recommendations"
    ][0]

    _login(monkeypatch, b)
    assert (
        client.post(
            f"/api/alert-recommendations/{rec['id']}/accept", json={}
        ).status_code
        == 400
    )
    assert (
        client.post(f"/api/alert-recommendations/{rec['id']}/dismiss").status_code
        == 404
    )


# ── history ──────────────────────────────────────────────────────────────────


def test_history_lists_triggered_events(client, monkeypatch):
    import time

    uid = _mk_user()
    _login(monkeypatch, uid)
    rid = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    ).get_json()["rule"]["id"]

    rule = alert_rules.get_rule(uid, rid)
    alert_rules.apply_decision(
        rule, evaluate_rule(rule, {"price": 115.0}, now_ts=time.time())
    )

    body = client.get("/api/alert-history").get_json()
    assert body["count"] == 1
    assert "BTC rose above" in body["events"][0]["explanation"]


def test_history_is_user_scoped(client, monkeypatch):
    import time

    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _login(monkeypatch, a)
    rid = client.post(
        "/api/alert-rules",
        json={
            "symbol": "BTC",
            "trigger_type": "price_cross",
            "direction": "above",
            "threshold": 110.0,
            "current_price": 100.0,
        },
    ).get_json()["rule"]["id"]
    rule = alert_rules.get_rule(a, rid)
    alert_rules.apply_decision(
        rule, evaluate_rule(rule, {"price": 115.0}, now_ts=time.time())
    )

    _login(monkeypatch, b)
    assert client.get("/api/alert-history").get_json()["count"] == 0


# ── regression guard ─────────────────────────────────────────────────────────


def test_cooling_down_rule_is_still_evaluated():
    """Regression: a cooling-down rule must reach the re-arm branch.

    Short-circuiting on status != 'active' stranded every recurring rule
    permanently after its first fire.
    """
    import time

    now = time.time()
    rule = {
        "id": "r",
        "user_id": 1,
        "symbol": "BTC",
        "trigger_type": "price_cross",
        "params": {"direction": "above", "threshold": 100.0},
        "repeat_mode": "recurring",
        "status": "cooling_down",
        "armed": False,
        "arm_cycle": 0,
        "cooldown_seconds": 0,
        "reset_pct": 1.0,
        "last_triggered_ts": None,
        "expires_ts": None,
        "source": "manual",
    }
    d = evaluate_rule(rule, {"price": 98.0}, now_ts=now)
    assert d.suppression_reason == "rearmed"
    assert d.next_armed is True


def test_paused_rule_is_not_evaluated():
    import time

    rule = {
        "id": "r",
        "user_id": 1,
        "symbol": "BTC",
        "trigger_type": "price_cross",
        "params": {"direction": "above", "threshold": 100.0},
        "repeat_mode": "recurring",
        "status": "paused",
        "armed": False,
        "arm_cycle": 0,
        "cooldown_seconds": 0,
        "reset_pct": 1.0,
        "last_triggered_ts": None,
        "expires_ts": None,
        "source": "manual",
    }
    d = evaluate_rule(rule, {"price": 98.0}, now_ts=time.time())
    assert d.suppression_reason == "rule_paused"
