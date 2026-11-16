import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app
import watchlist


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MW_PAPER_EXECUTION_DB", str(tmp_path / "paper.sqlite"))
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "owner@example.test")
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 1, "email": "owner@example.test"})
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    monkeypatch.setitem(backend_app.app.config, "TESTING", True)
    return backend_app.app.test_client()


TICKET = {
    "product_id": "BTC-USD",
    "side": "buy",
    "intent_type": "entry",
    "entry_price": 100,
    "stop_trigger_price": 95,
    "stop_limit_price": 94,
    "target_price": 115,
    "base_size": 1,
    "rr_planned": 99,
}


def test_owner_only_mode_and_persisted_paper_approval(client, monkeypatch):
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    assert client.get("/api/execution-agent/mode").status_code == 401
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 2, "email": "other@example.test"})
    assert client.post("/api/execution-agent/mode", json={"mode": "guardian"}).status_code == 403
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 1, "email": "owner@example.test"})
    assert client.post("/api/execution-agent/mode", json={"mode": "invalid"}).status_code == 400
    assert client.get("/api/execution-agent/mode").json["mode"] == "advisory"
    staged = client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]
    assert staged["rr_planned"] == 2.5
    assert staged["status"] == "staged_for_approval"
    approved = client.post("/api/execution-agent/tickets", json={"action": "approve", "ticket_id": staged["id"]}).json
    assert approved["paper"] and approved["ticket"]["status"] == "approved_paper"
    assert client.get("/api/execution-agent/tickets").json["tickets"][0]["status"] == "approved_paper"
    assert client.post("/api/execution-agent/tickets", json={"action": "approve", "ticket_id": staged["id"]}).status_code == 400
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 3, "email": "owner@example.test"})
    assert client.get("/api/execution-agent/tickets").json["tickets"] == []
    assert client.post("/api/execution-agent/tickets", json={"action": "approve", "ticket_id": staged["id"]}).status_code == 404


def test_autonomous_block_cannot_be_approved_and_guardian_cannot_trust_client_held_flag(client, monkeypatch):
    client.post("/api/execution-agent/mode", json={"mode": "autonomous"})
    blocked = client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]
    assert blocked["status"] == "blocked_by_circuit_breaker"
    assert "open_positions_unavailable" in blocked["block_reasons"]
    assert "sentiment_posture_unavailable" in blocked["block_reasons"]
    assert client.post("/api/execution-agent/tickets", json={"action": "approve", "ticket_id": blocked["id"]}).status_code == 400
    client.post("/api/execution-agent/mode", json={"mode": "guardian"})
    import portfolio_mode

    class Portfolio:
        def snapshot(self):
            return {"status": "stale", "holdings": [{"product_id": "BTC-USD", "available_quantity": 1}]}

    monkeypatch.setattr(portfolio_mode, "get_portfolio_service", lambda: Portfolio())
    sell = dict(TICKET, side="sell", intent_type="protective_stop_limit", position_held=True)
    preview = client.post("/api/execution-agent/tickets", json={"action": "preview", "ticket": sell}).json["ticket"]
    assert preview["status"] == "staged_for_approval"
    monkeypatch.setattr(Portfolio, "snapshot", lambda self: {"status": "live", "holdings": [{"product_id": "BTC-USD", "available_quantity": 1}]})
    preview = client.post("/api/execution-agent/tickets", json={"action": "preview", "ticket": sell}).json["ticket"]
    assert preview["status"] == "auto_approved_guardian"
    sell["base_size"] = 2
    preview = client.post("/api/execution-agent/tickets", json={"action": "preview", "ticket": sell}).json["ticket"]
    assert preview["status"] == "staged_for_approval"


def test_chart_includes_paper_ticket_only_for_owner(client, monkeypatch):
    ticket = client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]
    candles = [[1_700_000_000 + i * 3600, 90, 110, 100, 105, 10] for i in range(60)]
    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", lambda *args, **kwargs: candles[::-1])
    import catalyst_sentiment

    class Unavailable:
        def symbol(self, symbol):
            return {}

        def source_health(self):
            return {}

    monkeypatch.setattr(catalyst_sentiment, "get_service", lambda: Unavailable())
    assert client.get("/api/chart-read/BTC").json["paper_order_ticket"]["id"] == ticket["id"]
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    assert "paper_order_ticket" not in client.get("/api/chart-read/BTC").json
