"""Tests for the scheduled intelligence runner and its execution guardrails."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.intelligence_memory import IntelligenceMemoryStore
from backend.intelligence_runner import (
    RunnerConfig,
    resolve_intelligence_user_ids,
    run_intelligence_cycle,
    run_portfolio_intelligence_for_user,
)
from backend.portfolio_change_intelligence import EVENT_TYPE, capture_portfolio_snapshot


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


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    return IntelligenceMemoryStore()


# No snapshot/event windows, so tests exercise detection rather than throttling.
OPEN_CONFIG = RunnerConfig(
    interval_seconds=60, delta_window_seconds=0, snapshot_min_gap_seconds=0
)


# --- 1. The runner invokes detection -----------------------------------------


def test_runner_invokes_detection_and_creates_event(store):
    capture_portfolio_snapshot(1, snapshot=_snapshot(sol_value=100.0), store=store)

    result = run_portfolio_intelligence_for_user(
        1,
        store=store,
        config=OPEN_CONFIG,
        current_snapshot=_snapshot(sol_value=140.0),
    )

    assert result["triggered"] is True
    assert result["event_id"]
    events = store.list_intelligence_events(user_id=1, event_type=EVENT_TYPE)
    assert len(events) == 1


def test_cycle_reports_summary(store):
    capture_portfolio_snapshot(1, snapshot=_snapshot(sol_value=100.0), store=store)
    summary = run_intelligence_cycle(
        user_ids=[1],
        store=store,
        config=OPEN_CONFIG,
        current_snapshot=_snapshot(sol_value=140.0),
    )
    assert summary["users_checked"] == 1
    assert summary["events_created"] == 1
    assert summary["results"][0]["user_id"] == 1


# --- 2. Duplicate execution does not duplicate events ------------------------


def test_snapshot_window_prevents_duplicate_snapshots(store):
    capture_portfolio_snapshot(2, snapshot=_snapshot(sol_value=100.0), store=store)
    config = RunnerConfig(
        interval_seconds=60, delta_window_seconds=0, snapshot_min_gap_seconds=3600
    )

    before = len(store.recent_portfolio_snapshots(2, limit=50))
    result = run_portfolio_intelligence_for_user(
        2, store=store, config=config, current_snapshot=_snapshot(sol_value=140.0)
    )

    assert result["status"] == "skipped_snapshot_window"
    assert result["triggered"] is False
    # No new snapshot row was written.
    assert len(store.recent_portfolio_snapshots(2, limit=50)) == before


def test_delta_window_suppresses_second_event(store):
    capture_portfolio_snapshot(3, snapshot=_snapshot(sol_value=100.0), store=store)
    first = run_portfolio_intelligence_for_user(
        3, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=140.0)
    )
    assert first["triggered"] is True

    # A second big move inside the delta window must not emit again.
    windowed = RunnerConfig(
        interval_seconds=60, delta_window_seconds=21600, snapshot_min_gap_seconds=0
    )
    second = run_portfolio_intelligence_for_user(
        3, store=store, config=windowed, current_snapshot=_snapshot(sol_value=200.0)
    )

    assert second["triggered"] is False
    assert second["status"] == "suppressed"
    assert second["suppressed_reason"] == "duplicate_condition"
    assert len(store.list_intelligence_events(user_id=3, event_type=EVENT_TYPE)) == 1


def test_unchanged_condition_does_not_re_emit_after_window_expires(store):
    capture_portfolio_snapshot(4, snapshot=_snapshot(sol_value=100.0), store=store)
    first = run_portfolio_intelligence_for_user(
        4, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=140.0)
    )
    assert first["triggered"] is True

    # Reproduce the exact same previous->current transition, which yields an
    # identical fingerprint. Even with every time window wide open, the same
    # condition must not re-fire.
    capture_portfolio_snapshot(4, snapshot=_snapshot(sol_value=100.0), store=store)
    repeat = run_portfolio_intelligence_for_user(
        4, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=140.0)
    )

    assert repeat["triggered"] is False
    assert repeat["suppressed_reason"] == "duplicate_condition"
    assert len(store.list_intelligence_events(user_id=4, event_type=EVENT_TYPE)) == 1


def test_expired_window_allows_a_genuinely_new_condition(store):
    capture_portfolio_snapshot(5, snapshot=_snapshot(sol_value=100.0), store=store)
    run_portfolio_intelligence_for_user(
        5, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=140.0)
    )

    # A different magnitude is a different condition -> allowed to emit.
    second = run_portfolio_intelligence_for_user(
        5, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=260.0)
    )
    assert second["triggered"] is True
    assert len(store.list_intelligence_events(user_id=5, event_type=EVENT_TYPE)) == 2


def test_delta_window_respects_elapsed_time(store):
    capture_portfolio_snapshot(6, snapshot=_snapshot(sol_value=100.0), store=store)
    run_portfolio_intelligence_for_user(
        6, store=store, config=OPEN_CONFIG, current_snapshot=_snapshot(sol_value=140.0)
    )

    windowed = RunnerConfig(
        interval_seconds=60, delta_window_seconds=3600, snapshot_min_gap_seconds=0
    )
    # Pretend we are well past the window; a new condition may then emit.
    later = datetime.now(timezone.utc) + timedelta(hours=5)
    result = run_portfolio_intelligence_for_user(
        6,
        store=store,
        config=windowed,
        now=later,
        current_snapshot=_snapshot(sol_value=260.0),
    )
    assert result["triggered"] is True


# --- 3. Failed portfolio fetch fails gracefully ------------------------------


def test_failed_portfolio_fetch_is_graceful(store):
    class BrokenService:
        def snapshot(self):
            raise RuntimeError("coinbase down")

    result = run_portfolio_intelligence_for_user(
        7, store=store, config=OPEN_CONFIG, service=BrokenService()
    )
    assert result["status"] == "portfolio_unavailable"
    assert result["triggered"] is False


def test_cycle_isolates_a_failing_user(store):
    capture_portfolio_snapshot(8, snapshot=_snapshot(sol_value=100.0), store=store)

    class BrokenStore:
        def __getattr__(self, name):
            raise RuntimeError("memory offline")

    summary = run_intelligence_cycle(
        user_ids=[8],
        store=BrokenStore(),
        config=OPEN_CONFIG,
    )
    # The cycle completes and reports, rather than raising.
    assert summary["users_checked"] == 1
    assert summary["events_created"] == 0


def test_empty_user_list_is_a_no_op(store):
    summary = run_intelligence_cycle(user_ids=[], store=store, config=OPEN_CONFIG)
    assert summary["users_checked"] == 0
    assert summary["events_created"] == 0
    assert summary["auth_failures"] == 0
    assert summary["results"] == []


# --- 4. Multiple users are isolated ------------------------------------------


def test_users_are_isolated(store):
    capture_portfolio_snapshot(100, snapshot=_snapshot(sol_value=100.0), store=store)
    capture_portfolio_snapshot(200, snapshot=_snapshot(sol_value=100.0), store=store)

    summary = run_intelligence_cycle(
        user_ids=[100, 200],
        store=store,
        config=OPEN_CONFIG,
        current_snapshot=_snapshot(sol_value=140.0),
    )
    assert summary["users_checked"] == 2
    assert summary["events_created"] == 2

    # Each user's event references only their own snapshots.
    for user_id in (100, 200):
        events = store.list_intelligence_events(user_id=user_id, event_type=EVENT_TYPE)
        assert len(events) == 1
        assert events[0]["user_id"] == user_id


def test_one_users_window_does_not_throttle_another(store):
    capture_portfolio_snapshot(300, snapshot=_snapshot(sol_value=100.0), store=store)
    run_portfolio_intelligence_for_user(
        300,
        store=store,
        config=OPEN_CONFIG,
        current_snapshot=_snapshot(sol_value=140.0),
    )

    # User 400 has never fired; user 300's active window must not block them.
    capture_portfolio_snapshot(400, snapshot=_snapshot(sol_value=100.0), store=store)
    windowed = RunnerConfig(
        interval_seconds=60, delta_window_seconds=21600, snapshot_min_gap_seconds=0
    )
    result = run_portfolio_intelligence_for_user(
        400, store=store, config=windowed, current_snapshot=_snapshot(sol_value=140.0)
    )
    assert result["triggered"] is True


# --- Configuration -----------------------------------------------------------


def test_config_reads_environment(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_RUN_INTERVAL", "120")
    monkeypatch.setenv("PORTFOLIO_CHANGE_INTELLIGENCE_EVENT_WINDOW", "600")
    monkeypatch.setenv("INTELLIGENCE_SNAPSHOT_MIN_GAP", "300")
    monkeypatch.setenv("PORTFOLIO_CHANGE_INTELLIGENCE_WINDOW_HOURS", "24")
    config = RunnerConfig.from_env()
    assert config.interval_seconds == 120
    assert config.delta_window_seconds == 600
    assert config.snapshot_min_gap_seconds == 300
    assert config.comparison_window_hours == 24.0


def test_config_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_RUN_INTERVAL", "not-a-number")
    assert RunnerConfig.from_env().interval_seconds == RunnerConfig().interval_seconds


def test_comparison_window_uses_requested_hours(store):
    capture_portfolio_snapshot(9, snapshot=_snapshot(sol_value=100.0), store=store)
    capture_portfolio_snapshot(9, snapshot=_snapshot(sol_value=120.0), store=store)

    result = run_portfolio_intelligence_for_user(
        9,
        store=store,
        config=RunnerConfig(
            interval_seconds=60,
            delta_window_seconds=0,
            snapshot_min_gap_seconds=0,
            comparison_window_hours=1,
        ),
        current_snapshot=_snapshot(sol_value=140.0),
    )

    assert result["triggered"] is True
    assert result["comparison_window_hours"] == 1
    assert result["comparison_window_label"] == "1 hour"


def test_explicit_user_ids_from_env(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_RUN_USER_IDS", "3, 9 ,bad,12")
    assert resolve_intelligence_user_ids() == [3, 9, 12]


# --- Live credential path ----------------------------------------------------


class _FakeService:
    """Stands in for PortfolioService."""

    def __init__(self, snapshot=None, error=None):
        self._snapshot = snapshot
        self._error = error
        self.calls = 0

    def snapshot(self, **_kwargs):
        self.calls += 1
        if self._error:
            raise self._error
        return self._snapshot


class _Resolved:
    def __init__(self, status, detail=None):
        self.status = status
        self.detail = detail


def _patch_credentials(monkeypatch, *, resolver=None, eligible=None):
    """Swap the runner's credential-service seam for a stub."""
    import backend.intelligence_runner as runner

    class _Stub:
        resolve_portfolio_service = staticmethod(
            resolver or (lambda uid: (None, _Resolved("not_connected")))
        )
        list_snapshot_eligible_users = staticmethod(eligible or (lambda: ([], [])))

    monkeypatch.setattr(runner, "_credentials_module", lambda: _Stub)


def _patch_resolver(monkeypatch, mapping):
    """Patch credential resolution to a {user_id: (service, status)} map."""

    def fake_resolve(user_id):
        entry = mapping.get(user_id)
        if entry is None:
            return None, _Resolved("not_connected", "No Coinbase connection.")
        service, status = entry
        return service, _Resolved(status)

    _patch_credentials(monkeypatch, resolver=fake_resolve)


def test_runner_captures_via_resolved_credentials(store, monkeypatch):
    capture_portfolio_snapshot(500, snapshot=_snapshot(sol_value=100.0), store=store)
    service = _FakeService(snapshot=_snapshot(sol_value=140.0))
    _patch_resolver(monkeypatch, {500: (service, "refreshed")})

    result = run_portfolio_intelligence_for_user(500, store=store, config=OPEN_CONFIG)

    assert service.calls == 1
    assert result["triggered"] is True
    assert result["credential_status"] == "refreshed"


def test_auth_failure_is_explicit_not_portfolio_unavailable(store, monkeypatch):
    _patch_resolver(monkeypatch, {})  # user 501 unresolvable

    result = run_portfolio_intelligence_for_user(501, store=store, config=OPEN_CONFIG)

    assert result["status"] == "auth_unavailable"
    assert result["credential_status"] == "not_connected"
    assert result["triggered"] is False
    # Must NOT be conflated with a Coinbase outage.
    assert result["status"] != "portfolio_unavailable"


def test_portfolio_outage_is_distinct_from_auth_failure(store, monkeypatch):
    capture_portfolio_snapshot(502, snapshot=_snapshot(sol_value=100.0), store=store)
    broken = _FakeService(error=RuntimeError("coinbase 503"))
    _patch_resolver(monkeypatch, {502: (broken, "connected")})

    result = run_portfolio_intelligence_for_user(502, store=store, config=OPEN_CONFIG)
    assert result["status"] == "portfolio_unavailable"


def test_cycle_accounts_for_mixed_auth_states(store, monkeypatch):
    capture_portfolio_snapshot(600, snapshot=_snapshot(sol_value=100.0), store=store)
    capture_portfolio_snapshot(602, snapshot=_snapshot(sol_value=100.0), store=store)

    _patch_resolver(
        monkeypatch,
        {
            600: (_FakeService(snapshot=_snapshot(sol_value=140.0)), "connected"),
            602: (_FakeService(error=RuntimeError("coinbase down")), "refreshed"),
            # 601 absent -> auth failure
        },
    )

    summary = run_intelligence_cycle(
        user_ids=[600, 601, 602], store=store, config=OPEN_CONFIG
    )

    assert summary["users_checked"] == 3
    assert summary["events_created"] == 1
    assert summary["auth_failures"] == 1
    assert summary["portfolio_unavailable"] == 1
    assert summary["snapshots_created"] == 1
    assert "duration_seconds" in summary and "started_at" in summary


def test_cycle_continues_after_one_user_fails(store, monkeypatch):
    capture_portfolio_snapshot(700, snapshot=_snapshot(sol_value=100.0), store=store)
    capture_portfolio_snapshot(701, snapshot=_snapshot(sol_value=100.0), store=store)

    _patch_resolver(
        monkeypatch,
        {
            700: (_FakeService(error=RuntimeError("boom")), "connected"),
            701: (_FakeService(snapshot=_snapshot(sol_value=140.0)), "connected"),
        },
    )

    summary = run_intelligence_cycle(
        user_ids=[700, 701], store=store, config=OPEN_CONFIG
    )
    # The healthy user still produced an event despite the earlier failure.
    assert summary["events_created"] == 1
    assert len(store.list_intelligence_events(user_id=701, event_type=EVENT_TYPE)) == 1


def test_eligibility_delegates_to_credential_service(monkeypatch):
    monkeypatch.delenv("INTELLIGENCE_RUN_USER_IDS", raising=False)
    _patch_credentials(
        monkeypatch,
        eligible=lambda: (
            [{"user_id": 11, "auth": "oauth"}],
            [{"user_id": 12, "reason": "refresh_failed", "detail": "reconnect"}],
        ),
    )
    # Only eligible users are checked; ineligible ones are logged, not dropped.
    assert resolve_intelligence_user_ids() == [11]
