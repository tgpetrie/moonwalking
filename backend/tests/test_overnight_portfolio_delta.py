"""Tests for the portfolio change intelligence engine and compatibility shim."""

from __future__ import annotations

import pytest

from backend.intelligence_memory import IntelligenceMemoryStore
from backend.overnight_portfolio_delta import (
    EVENT_TYPE,
    DeltaThresholds,
    build_overnight_delta_packet,
    capture_portfolio_snapshot,
    compute_portfolio_delta,
    detect_overnight_delta,
    run_overnight_portfolio_delta,
)


def _snapshot(*, sol_value: float, btc_value: float, cash: float = 10.0):
    total = sol_value + btc_value + cash
    holdings = [
        {
            "symbol": "SOL",
            "market_value_usd": sol_value,
            "allocation_pct": round(sol_value / total * 100, 4),
            "is_cash": False,
            "cost_basis": {"status": "complete", "known_cost_usd": sol_value},
        },
        {
            "symbol": "BTC",
            "market_value_usd": btc_value,
            "allocation_pct": round(btc_value / total * 100, 4),
            "is_cash": False,
            "cost_basis": {"status": "complete", "known_cost_usd": btc_value},
        },
        {
            "symbol": "USD",
            "market_value_usd": cash,
            "allocation_pct": round(cash / total * 100, 4),
            "is_cash": True,
            "cost_basis": {"status": "not_applicable", "known_cost_usd": cash},
        },
    ]
    return {
        "status": "live",
        "mode": "view_only",
        "updated_at": "2026-07-26T00:00:00Z",
        "summary": {"total_value_usd": total},
        "holdings": holdings,
    }


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    return IntelligenceMemoryStore()


# --- 1. Snapshot creation ----------------------------------------------------


def test_capture_snapshot_persists_and_fails_gracefully(store):
    recorded = capture_portfolio_snapshot(
        1, snapshot=_snapshot(sol_value=100.0, btc_value=100.0), store=store
    )
    assert recorded is not None
    assert recorded["holdings_count"] == 3

    # Missing/invalid portfolio data must not raise — returns None.
    assert capture_portfolio_snapshot(1, snapshot={"holdings": []}, store=store) is None
    assert (
        capture_portfolio_snapshot(1, snapshot=None, service=None, store=store) is None
    )


# --- 2. Snapshot comparison (deterministic delta engine) ---------------------


def test_compute_delta_math():
    previous = _snapshot(sol_value=100.0, btc_value=100.0, cash=10.0)  # total 210
    current = _snapshot(sol_value=130.0, btc_value=100.0, cash=10.0)  # total 240
    delta = compute_portfolio_delta(previous, current)

    assert delta["status"] == "compared"
    assert delta["total_change_usd"] == 30.0
    assert delta["total_change_pct"] == pytest.approx(30 / 210 * 100, rel=1e-6)

    sol = next(c for c in delta["asset_contributions"] if c["asset_symbol"] == "SOL")
    assert sol["value_delta_usd"] == 30.0
    assert sol["contribution_pct"] == pytest.approx(30 / 210 * 100, rel=1e-6)
    assert delta["biggest_movers"][0]["asset_symbol"] == "SOL"


def test_compute_delta_no_previous():
    delta = compute_portfolio_delta(None, _snapshot(sol_value=100.0, btc_value=100.0))
    assert delta["status"] == "no_previous_snapshot"
    assert delta["total_change_pct"] is None


# --- 3. Threshold detection --------------------------------------------------


def test_portfolio_move_triggers():
    previous = _snapshot(sol_value=100.0, btc_value=100.0, cash=10.0)
    current = _snapshot(sol_value=130.0, btc_value=100.0, cash=10.0)  # +14.3%
    detection = detect_overnight_delta(compute_portfolio_delta(previous, current))
    assert detection["triggered"] is True
    assert any(r["type"] == "portfolio_move" for r in detection["reasons"])


def test_single_asset_contribution_triggers_when_portfolio_flat():
    # Portfolio nearly flat overall, but SOL swings hard against BTC.
    previous = _snapshot(sol_value=100.0, btc_value=100.0, cash=10.0)  # 210
    current = _snapshot(sol_value=108.0, btc_value=92.0, cash=10.0)  # 210 total
    delta = compute_portfolio_delta(previous, current)
    assert delta["total_change_pct"] == pytest.approx(0.0, abs=1e-6)

    detection = detect_overnight_delta(delta)  # SOL +8/210 = 3.8% >= 3%
    assert detection["triggered"] is True
    reasons = {r["type"] for r in detection["reasons"]}
    assert "asset_contribution" in reasons
    assert "portfolio_move" not in reasons


def test_thresholds_are_configurable_via_env(monkeypatch):
    monkeypatch.setenv("MW_OVERNIGHT_DELTA_PORTFOLIO_PCT", "20")
    monkeypatch.setenv("MW_OVERNIGHT_DELTA_ASSET_PCT", "15")
    t = DeltaThresholds.from_env()
    assert t.portfolio_pct == 20.0 and t.asset_contribution_pct == 15.0

    previous = _snapshot(sol_value=100.0, btc_value=100.0, cash=10.0)
    current = _snapshot(sol_value=130.0, btc_value=100.0, cash=10.0)  # +14.3%, <20%
    detection = detect_overnight_delta(compute_portfolio_delta(previous, current), t)
    assert detection["triggered"] is False


# --- 4. Ignored insignificant changes ----------------------------------------


def test_insignificant_change_is_ignored(store):
    capture_portfolio_snapshot(
        5, snapshot=_snapshot(sol_value=100.0, btc_value=100.0, cash=10.0), store=store
    )
    # +1% portfolio, sub-threshold per-asset — nothing should fire.
    result = run_overnight_portfolio_delta(
        5,
        store=store,
        current_snapshot=_snapshot(sol_value=101.0, btc_value=100.0, cash=10.0),
    )
    assert result["status"] == "evaluated"
    assert result["triggered"] is False
    assert "event_id" not in result


# --- 5. Event creation (full proactive run) ----------------------------------


def test_run_creates_event_and_packet(store):
    capture_portfolio_snapshot(
        9, snapshot=_snapshot(sol_value=100.0, btc_value=100.0, cash=10.0), store=store
    )
    result = run_overnight_portfolio_delta(
        9,
        store=store,
        current_snapshot=_snapshot(sol_value=140.0, btc_value=100.0, cash=10.0),
    )
    assert result["triggered"] is True
    assert result["event_id"]
    assert result["evidence_packet_id"]

    packet = store.latest_evidence_packet(
        scope="portfolio_change_intelligence",
        user_id=9,
        series_key="portfolio_change_intelligence:9",
    )
    assert packet is not None
    assert packet["packet"]["event_type"] == EVENT_TYPE
    assert "SOL" in packet["packet"]["affected_assets"]
    # Facts only — no prediction/advice fields.
    assert packet["packet"]["confidence"]["level"] == "deterministic"


def test_run_without_previous_snapshot_does_not_trigger(store):
    result = run_overnight_portfolio_delta(
        11, store=store, current_snapshot=_snapshot(sol_value=100.0, btc_value=100.0)
    )
    assert result["triggered"] is False
    assert result["change"]["status"] == "no_previous_snapshot"
