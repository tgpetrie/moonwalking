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
    monkeypatch.setattr(backend_app, "_trusted_execution_sentiment", lambda symbol: None)
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
    assert "open_positions_unavailable" not in blocked["block_reasons"]
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
    import chart_reader
    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", lambda product: [])
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


def test_autonomous_risk_ledger_fill_close_and_daily_loss(client, monkeypatch):
    import paper_execution_store

    monkeypatch.setattr(backend_app, "_trusted_execution_sentiment", lambda symbol: "quiet")
    client.post("/api/execution-agent/mode", json={"mode": "autonomous"})
    ticket = client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]
    assert ticket["status"] == "auto_approved_autonomous"
    assert paper_execution_store.risk_metrics(1)["open_positions"] == 1
    assert client.post("/api/execution-agent/tickets", json={"action": "fill", "ticket_id": ticket["id"], "fill_price": 101}).status_code == 400
    assert client.post("/api/execution-agent/tickets", json={"action": "fill", "ticket_id": ticket["id"], "fill_price": 100}).json["ticket"]["status"] == "filled_paper"
    assert client.post("/api/execution-agent/tickets", json={"action": "fill", "ticket_id": ticket["id"], "fill_price": 100}).status_code == 400
    closed = client.post("/api/execution-agent/tickets", json={"action": "close", "ticket_id": ticket["id"], "exit_price": 88}).json["ticket"]
    assert closed["realized_r"] == -2
    assert paper_execution_store.risk_metrics(1) == {"open_positions": 0, "daily_realized_r": -2}
    blocked = client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]
    assert "max_daily_loss_reached" in blocked["block_reasons"]
    assert client.post("/api/execution-agent/tickets", json={"action": "close", "ticket_id": ticket["id"], "exit_price": 100}).status_code == 400
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 3, "email": "owner@example.test"})
    assert paper_execution_store.risk_metrics(3) == {"open_positions": 0, "daily_realized_r": 0}
    assert client.post("/api/execution-agent/tickets", json={"action": "close", "ticket_id": ticket["id"], "exit_price": 100}).status_code == 404


def test_autonomous_reserves_approved_orders_and_blocks_fourth_successor(client, monkeypatch):
    monkeypatch.setattr(backend_app, "_trusted_execution_sentiment", lambda symbol: "quiet")
    client.post("/api/execution-agent/mode", json={"mode": "autonomous"})
    statuses = [client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]["status"] for _ in range(5)]
    assert statuses == ["auto_approved_autonomous"] * 4 + ["blocked_by_circuit_breaker"]
    approved = client.get("/api/execution-agent/tickets").json["tickets"][1]
    assert client.post("/api/execution-agent/tickets", json={"action": "cancel", "ticket_id": approved["id"]}).json["ticket"]["status"] == "cancelled_paper"
    assert client.post("/api/execution-agent/tickets", json={"action": "stage", "ticket": TICKET}).json["ticket"]["status"] == "auto_approved_autonomous"


def test_autonomous_sell_uses_calculated_rr(client, monkeypatch):
    monkeypatch.setattr(backend_app, "_trusted_execution_sentiment", lambda symbol: "quiet")
    client.post("/api/execution-agent/mode", json={"mode": "autonomous"})
    ticket = dict(TICKET, side="sell", intent_type="protective_stop_limit", current_price=100, rr_planned=99)
    result = client.post("/api/execution-agent/tickets", json={"action": "preview", "ticket": ticket}).json["ticket"]
    assert result["rr_planned"] == 2.5
    assert result["status"] == "auto_approved_autonomous"


def test_trusted_sentiment_requires_fresh_feeds_and_all_chart_degrees(monkeypatch):
    import catalyst_sentiment
    reads = {tf: {"active_pattern": "none", "status": "none", "bias": "neutral"} for tf in ("15m", "1h", "4h")}

    class Service:
        def symbol(self, symbol):
            return {"hype": "quiet"}

        def source_health(self):
            return {"trending": {"status": "ok"}, "optional_news:blog": {"status": "unavailable"}}

    monkeypatch.setattr(catalyst_sentiment, "get_service", lambda: Service())
    monkeypatch.setattr(backend_app, "_structure_posture_for", lambda symbol: {"reads": reads})
    assert backend_app._trusted_execution_sentiment("BTC") == "quiet"
    reads.pop("15m")
    assert backend_app._trusted_execution_sentiment("BTC") is None
    monkeypatch.setattr(Service, "symbol", lambda self, symbol: {"negative_catalyst_risk": True})
    assert backend_app._trusted_execution_sentiment("BTC") == "negative_catalyst_risk"


def test_autonomous_reservations_are_atomic_under_concurrency(client):
    from concurrent.futures import ThreadPoolExecutor
    import paper_execution_store as store

    def stage():
        return store.stage_evaluated_ticket(1, lambda risk: {
            "product_id": "BTC-USD",
            "side": "buy",
            "status": "auto_approved_autonomous" if risk["open_positions"] < 4 else "blocked_by_circuit_breaker",
        })

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: stage(), range(8)))
    assert sum(ticket["status"] == "auto_approved_autonomous" for ticket in results) == 4
    assert store.risk_metrics(1)["open_positions"] == 4
