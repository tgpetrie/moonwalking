"""Tests for the intelligence feed delivery path (events -> JSON)."""

from __future__ import annotations

import pytest

from backend.intelligence_feed import serialize_event
from backend.intelligence_memory import IntelligenceMemoryStore
from backend.portfolio_change_intelligence import (
    EVENT_TYPE,
    capture_portfolio_snapshot,
    run_portfolio_intelligence_check,
)


def _snapshot(*, sol_value: float, btc_value: float, cash: float = 10.0):
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


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    return IntelligenceMemoryStore()


@pytest.fixture
def triggered_store(store):
    capture_portfolio_snapshot(
        42, snapshot=_snapshot(sol_value=100.0, btc_value=100.0), store=store
    )
    run_portfolio_intelligence_check(
        42,
        hours=12,
        store=store,
        current_snapshot=_snapshot(sol_value=140.0, btc_value=100.0),
    )
    return store


def test_events_are_listed_with_joined_evidence_packet(triggered_store):
    events = triggered_store.list_intelligence_events(user_id=42)
    assert len(events) == 1

    event = events[0]
    assert event["event_type"] == EVENT_TYPE
    assert event["status"] == "detected"
    assert event["evidence_packet"] is not None
    assert event["evidence_packet"]["event_type"] == EVENT_TYPE
    assert event["evidence_comparison"]["status"] == "compared"


def test_events_are_scoped_per_user(triggered_store):
    assert triggered_store.list_intelligence_events(user_id=999) == []


def test_serialize_event_exposes_feed_contract(triggered_store):
    event = triggered_store.list_intelligence_events(user_id=42)[0]
    view = serialize_event(event)

    # what changed / affected asset / portfolio impact / timestamp / confidence
    assert "SOL" in view["affected_assets"]
    assert view["what_changed"]["total_change_pct"] > 0
    assert view["portfolio_impact"]["previous_total_usd"] == 210.0
    assert view["portfolio_impact"]["current_total_usd"] == 250.0
    assert view["observed_at"]
    assert view["confidence"]["level"] == "deterministic"
    assert view["evidence"]["available"] is True
    assert view["supporting_metrics"]["biggest_movers"][0]["asset_symbol"] == "SOL"
    assert (
        view["supporting_metrics"]["biggest_positive_contributors"][0]["asset_symbol"]
        == "SOL"
    )
    assert view["supporting_metrics"]["new_positions"] == []
    assert view["supporting_metrics"]["removed_positions"] == []

    # Headline is a factual restatement, and no LLM output is fabricated yet.
    assert "Portfolio up" in view["headline"]
    assert view["explanation"] is None


def test_status_transitions_and_active_filtering(triggered_store):
    event_id = triggered_store.list_intelligence_events(user_id=42)[0]["event_id"]

    assert triggered_store.update_intelligence_event_status(
        event_id, "seen", user_id=42
    )
    assert (
        len(
            triggered_store.list_intelligence_events(
                user_id=42, statuses=("detected", "seen")
            )
        )
        == 1
    )

    assert triggered_store.update_intelligence_event_status(
        event_id, "dismissed", user_id=42
    )
    assert (
        triggered_store.list_intelligence_events(
            user_id=42, statuses=("detected", "seen")
        )
        == []
    )
    # Still retrievable when dismissed events are explicitly included.
    assert len(triggered_store.list_intelligence_events(user_id=42)) == 1


def test_status_update_cannot_cross_users(triggered_store):
    event_id = triggered_store.list_intelligence_events(user_id=42)[0]["event_id"]
    assert (
        triggered_store.update_intelligence_event_status(
            event_id, "dismissed", user_id=7
        )
        is False
    )


def test_event_without_packet_still_renders():
    view = serialize_event(
        {
            "event_id": "event-1",
            "event_type": EVENT_TYPE,
            "status": "detected",
            "observed_at": "2026-07-26T00:00:00Z",
            "payload": {"total_change_pct": -6.5, "affected_assets": ["BTC"]},
            "evidence_packet": None,
        }
    )
    assert view["evidence"]["available"] is False
    assert "Portfolio down 6.50%" in view["headline"]
    assert view["confidence"]["level"] == "unknown"
