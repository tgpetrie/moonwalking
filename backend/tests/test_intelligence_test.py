"""Tests for the developer portfolio intelligence test layer."""

from __future__ import annotations

import json

from flask import Flask

from backend import intelligence_test
from backend.intelligence_memory import IntelligenceMemoryStore
from backend.portfolio_change_intelligence import capture_portfolio_snapshot


def _snapshot(*, sol_value: float, btc_value: float = 100.0, cash: float = 10.0):
    total = sol_value + btc_value + cash
    return {
        "status": "live",
        "updated_at": "2026-07-26T00:00:00Z",
        "summary": {"total_value_usd": total},
        "holdings": [
            {
                "symbol": "SOL",
                "market_value_usd": sol_value,
                "allocation_pct": round(sol_value / total * 100, 4),
                "is_cash": False,
            },
            {
                "symbol": "BTC",
                "market_value_usd": btc_value,
                "allocation_pct": round(btc_value / total * 100, 4),
                "is_cash": False,
            },
            {
                "symbol": "USD",
                "market_value_usd": cash,
                "allocation_pct": round(cash / total * 100, 4),
                "is_cash": True,
            },
        ],
    }


class FakeService:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


def _app():
    app = Flask(__name__)
    app.register_blueprint(intelligence_test.intelligence_test_bp)
    app.config["TESTING"] = True
    return app


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    return IntelligenceMemoryStore()


def test_dry_run_does_not_persist_snapshot_or_event(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    capture_portfolio_snapshot(42, snapshot=_snapshot(sol_value=100.0), store=store)

    result = intelligence_test.run_portfolio_intelligence_test(
        42,
        hours=4,
        dry_run=True,
        store=store,
        current_snapshot=_snapshot(sol_value=140.0),
    )

    assert result["dry_run"] is True
    assert result["window_hours"] == 4
    assert result["triggered"] is True
    assert result["events_created"] == []
    assert result["evidence_packet_ids"] == []
    assert result["proposed_event"]["persisted"] is False
    assert result["portfolio_change"]["portfolio_change_pct"] is not None
    assert len(store.recent_portfolio_snapshots(42, limit=50)) == 1
    assert store.list_intelligence_events(user_id=42) == []


def test_route_returns_live_summary(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    capture_portfolio_snapshot(42, snapshot=_snapshot(sol_value=100.0), store=store)

    monkeypatch.setattr(
        intelligence_test,
        "_resolve_user_service",
        lambda user_id: (
            FakeService(_snapshot(sol_value=140.0)),
            {"status": "connected", "detail": None, "credential_status": "connected"},
        ),
    )
    monkeypatch.setattr(
        intelligence_test,
        "get_authenticated_user",
        lambda: {"id": 42},
    )

    app = _app()
    client = app.test_client()
    response = client.post(
        "/api/intelligence/test-run",
        data=json.dumps({"user_id": 42, "hours": 4, "dry_run": False}),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["window_hours"] == 4
    assert payload["triggered"] is True
    assert payload["portfolio_change"]["value_change_usd"] == 40.0
    assert payload["top_positive_contributors"][0]["asset"] == "SOL"
    assert len(payload["events_created"]) == 1
    assert len(payload["evidence_packet_ids"]) == 1
    assert len(store.recent_portfolio_snapshots(42, limit=50)) == 2
    assert len(store.list_intelligence_events(user_id=42)) == 1


def test_cli_dry_run_prints_json(tmp_path, monkeypatch, capsys):
    _store(tmp_path, monkeypatch)

    monkeypatch.setattr(
        intelligence_test,
        "_resolve_user_service",
        lambda user_id: (
            FakeService(_snapshot(sol_value=140.0)),
            {"status": "connected", "detail": None, "credential_status": "connected"},
        ),
    )

    exit_code = intelligence_test.main(["--user", "42", "--hours", "4", "--dry-run"])
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["window_hours"] == 4
    assert payload["events_created"] == []
    assert payload["evidence_packet_ids"] == []
