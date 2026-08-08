"""Phase 2 scan-loop tests: evaluation, isolation, bad data, spike guard."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import watchlist
import alert_rules
import alert_runner
from alert_runner import run_evaluation_cycle, history_drift_tolerance

HOUR = 3600


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "wl.sqlite")
    monkeypatch.setattr(alert_rules, "_schema_ready", False)
    watchlist._ensure_watchlist_schema()
    alert_rules.ensure_alert_schema()
    yield tmp_path


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


def _prices(mapping, ts=None):
    """price_source returning a fixed snapshot."""
    snap_ts = int(time.time()) if ts is None else int(ts)
    return lambda: (mapping, snap_ts)


def _no_history(_pid, _ts):
    return None


def _history(price, at_ts):
    return lambda _pid, _target: (int(at_ts), price)


def _cross_rule(uid, symbol="BTC", threshold=110.0, repeat="once"):
    return alert_rules.create_rule(
        uid,
        symbol=symbol,
        trigger_type="price_cross",
        repeat_mode=repeat,
        params={"direction": "above", "threshold": threshold},
        current_price=100.0,
    )


def _pct_rule(uid, symbol="BTC", threshold=5.0, window="24h", repeat="once"):
    return alert_rules.create_rule(
        uid,
        symbol=symbol,
        trigger_type="percent_move",
        repeat_mode=repeat,
        params={"direction": "up", "threshold": threshold, "window": window},
    )


def _run(prices_map, history=_no_history, *, now=None, ts=None, sustain=1.0):
    return run_evaluation_cycle(
        price_source=_prices(prices_map, ts=ts if ts is not None else now),
        history_lookup=history,
        now_ts=now,
        sustain_seconds=sustain,
    )


def _confirm(prices_map, history=_no_history, *, now=None, sustain=1.0):
    """Two cycles: arm the pending state, then confirm it."""
    _run(prices_map, history, now=now, sustain=sustain)
    return _run(prices_map, history, now=(now or time.time()) + 30, sustain=sustain)


# ── 1. only the right rules are evaluated ────────────────────────────────────


def test_only_active_and_cooling_down_rules_are_loaded(db):
    uid = _mk_user()
    active = _cross_rule(uid, "BTC")
    paused = _cross_rule(uid, "ETH")
    alert_rules.set_rule_status(uid, paused["id"], "paused")

    loaded = {r["id"] for r in alert_rules.list_evaluable_rules()}
    assert active["id"] in loaded
    assert paused["id"] not in loaded


def test_triggered_once_rule_is_not_reloaded(db):
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC", repeat="once")
    now = time.time()
    _confirm({"BTC-USD": 150.0}, now=now)
    assert alert_rules.get_rule(uid, rule["id"])["status"] == "triggered"
    assert rule["id"] not in {r["id"] for r in alert_rules.list_evaluable_rules()}


def test_expired_rule_is_not_loaded(db):
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC")
    conn = watchlist._db_connect()
    try:
        conn.execute(
            "UPDATE alert_rules SET expires_ts = ? WHERE id = ?",
            (int(time.time()) - 10, rule["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    assert alert_rules.list_evaluable_rules() == []


def test_paused_rule_never_fires_through_runner(db):
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC")
    alert_rules.set_rule_status(uid, rule["id"], "paused")
    _confirm({"BTC-USD": 500.0})
    assert alert_rules.list_events(uid) == []


# ── 2. exactly one event per arm cycle ───────────────────────────────────────


def test_fires_once_and_only_once_per_arm_cycle(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC", repeat="recurring")
    now = time.time()

    stats = _confirm({"BTC-USD": 150.0}, now=now)
    assert stats.fired == 1
    assert len(alert_rules.list_events(uid)) == 1

    # Condition still true across many further cycles — no new events.
    for i in range(5):
        _run({"BTC-USD": 150.0}, now=now + 100 + i * 30)
    assert len(alert_rules.list_events(uid)) == 1


def test_rearm_then_fire_creates_a_second_event(db):
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC", repeat="recurring")
    now = time.time()
    _confirm({"BTC-USD": 150.0}, now=now)

    # Retreat past the reset boundary → re-arms.
    stats = _run({"BTC-USD": 100.0}, now=now + 200)
    assert stats.rearmed == 1
    assert alert_rules.get_rule(uid, rule["id"])["arm_cycle"] == 1

    # Clear cooldown so only arm-cycle semantics are under test.
    conn = watchlist._db_connect()
    try:
        conn.execute(
            "UPDATE alert_rules SET last_triggered_ts = NULL WHERE id = ?",
            (rule["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    _confirm({"BTC-USD": 160.0}, now=now + 5000)
    assert len(alert_rules.list_events(uid)) == 2


# ── 3. restart safety ────────────────────────────────────────────────────────


def test_cooldown_and_hysteresis_survive_restart(db, monkeypatch):
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC", repeat="recurring")
    now = time.time()
    _confirm({"BTC-USD": 150.0}, now=now)
    assert len(alert_rules.list_events(uid)) == 1

    monkeypatch.setattr(alert_rules, "_schema_ready", False)  # cold start
    alert_rules.ensure_alert_schema()

    reloaded = alert_rules.get_rule(uid, rule["id"])
    assert reloaded["armed"] is False and reloaded["status"] == "cooling_down"

    # Post-restart cycles with the condition still true add nothing.
    for i in range(3):
        _run({"BTC-USD": 150.0}, now=now + 200 + i * 30)
    assert len(alert_rules.list_events(uid)) == 1


def test_pending_state_survives_restart(db, monkeypatch):
    """A half-confirmed trigger is not lost, and not double-counted, on restart."""
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC")
    now = time.time()
    _run({"BTC-USD": 150.0}, now=now)  # pending only
    assert alert_rules.get_rule(uid, rule["id"])["pending_since_ts"] is not None

    monkeypatch.setattr(alert_rules, "_schema_ready", False)
    alert_rules.ensure_alert_schema()

    _run({"BTC-USD": 150.0}, now=now + 30)  # confirms after restart
    assert len(alert_rules.list_events(uid)) == 1


# ── 4-5. bad price data ──────────────────────────────────────────────────────


def test_stale_snapshot_skips_entire_cycle(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    now = time.time()
    stats = _run({"BTC-USD": 150.0}, now=now, ts=now - 3600)
    assert stats.skipped.get("stale_snapshot") == 1
    assert stats.rules_loaded == 0 and stats.fired == 0
    assert alert_rules.list_events(uid) == []


def test_missing_symbol_price_skips_rule(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    stats = _confirm({"ETH-USD": 150.0})
    assert stats.skipped.get("no_price") == 1
    assert alert_rules.list_events(uid) == []


@pytest.mark.parametrize("bad", [None, 0, -5, float("nan"), float("inf")])
def test_malformed_price_never_fires(db, bad):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    _confirm({"BTC-USD": bad})
    assert alert_rules.list_events(uid) == []


def test_empty_snapshot_skips_cycle(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    stats = _run({})
    assert stats.skipped.get("no_price_snapshot") == 1
    assert alert_rules.list_events(uid) == []


def test_missing_history_skips_percent_rule(db):
    uid = _mk_user()
    _pct_rule(uid, "BTC")
    stats = _confirm({"BTC-USD": 150.0}, _no_history)
    assert stats.skipped.get("no_comparison_price") == 1
    assert alert_rules.list_events(uid) == []


def test_price_source_exception_is_contained(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")

    def boom():
        raise RuntimeError("provider down")

    stats = run_evaluation_cycle(price_source=boom, history_lookup=_no_history)
    assert stats.errors == 1 and stats.fired == 0
    assert alert_rules.list_events(uid) == []


# ── 7. history drift guard ───────────────────────────────────────────────────


def test_drift_tolerance_scales_with_window():
    assert history_drift_tolerance(HOUR) == pytest.approx(720.0)  # 20%
    assert history_drift_tolerance(24 * HOUR) == pytest.approx(17280.0)  # 20%
    assert history_drift_tolerance(60) == 300.0  # floor


def test_24h_rule_does_not_fire_on_3h_of_history(db):
    """After a restart price_db may hold only a few hours. A '24h move'
    computed from 3h of data understates the real move, so it must not fire."""
    uid = _mk_user()
    _pct_rule(uid, "BTC", threshold=5.0, window="24h")
    now = time.time()
    shallow = _history(100.0, at_ts=now - 3 * HOUR)  # asked for 24h ago
    stats = _confirm({"BTC-USD": 150.0}, shallow, now=now)
    assert stats.skipped.get("no_comparison_price") == 1
    assert alert_rules.list_events(uid) == []


def test_1h_rule_does_not_fire_on_a_20h_stale_row(db):
    """A data gap: nearest row is far older than the target, which would
    overstate a '1h move'."""
    uid = _mk_user()
    _pct_rule(uid, "BTC", threshold=5.0, window="1h")
    now = time.time()
    gappy = _history(100.0, at_ts=now - 20 * HOUR)
    stats = _confirm({"BTC-USD": 150.0}, gappy, now=now)
    assert stats.skipped.get("no_comparison_price") == 1
    assert alert_rules.list_events(uid) == []


def test_history_within_tolerance_is_accepted(db):
    uid = _mk_user()
    _pct_rule(uid, "BTC", threshold=5.0, window="24h")
    now = time.time()
    good = _history(100.0, at_ts=now - 23 * HOUR)  # within 20% of target
    _confirm({"BTC-USD": 150.0}, good, now=now)
    assert len(alert_rules.list_events(uid)) == 1


# ── spike guard (sustained crossing) ─────────────────────────────────────────


def test_single_bad_tick_does_not_create_an_event(db):
    """A one-cycle provider spike must never produce an event."""
    uid = _mk_user()
    rule = _cross_rule(uid, "BTC")
    now = time.time()

    spike = _run({"BTC-USD": 99_999.0}, now=now)
    assert spike.fired == 0 and spike.pending == 1
    assert alert_rules.list_events(uid) == []
    assert alert_rules.get_rule(uid, rule["id"])["pending_since_ts"] is not None

    recovered = _run({"BTC-USD": 100.0}, now=now + 30)
    assert recovered.fired == 0 and recovered.unconfirmed == 1
    assert alert_rules.list_events(uid) == []
    assert alert_rules.get_rule(uid, rule["id"])["pending_since_ts"] is None


def test_sustained_crossing_fires_on_second_cycle(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    now = time.time()

    first = _run({"BTC-USD": 150.0}, now=now)
    assert first.fired == 0 and first.pending == 1
    assert alert_rules.list_events(uid) == []

    second = _run({"BTC-USD": 150.0}, now=now + 30)
    assert second.fired == 1
    assert len(alert_rules.list_events(uid)) == 1


def test_percent_move_spike_does_not_fire(db):
    uid = _mk_user()
    _pct_rule(uid, "BTC", threshold=5.0, window="1h")
    now = time.time()
    hist = _history(100.0, at_ts=now - HOUR)

    assert _run({"BTC-USD": 200.0}, hist, now=now).fired == 0  # spike
    assert _run({"BTC-USD": 101.0}, hist, now=now + 30).fired == 0  # gone
    assert alert_rules.list_events(uid) == []


def test_confirmation_resets_after_a_spike(db):
    """A cleared spike must not shorten the next confirmation."""
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    now = time.time()
    _run({"BTC-USD": 150.0}, now=now)  # pending
    _run({"BTC-USD": 100.0}, now=now + 30)  # cleared
    assert _run({"BTC-USD": 150.0}, now=now + 60).fired == 0  # must re-confirm
    assert _run({"BTC-USD": 150.0}, now=now + 90).fired == 1


# ── 8. per-rule failure isolation ────────────────────────────────────────────


def test_one_failing_rule_does_not_stop_the_batch(db, monkeypatch):
    uid = _mk_user()
    bad = _cross_rule(uid, "AAA")
    good = _cross_rule(uid, "BBB")

    real = alert_runner.evaluate_rule

    def flaky(rule, obs, **kw):
        if rule["symbol"] == "AAA":
            raise RuntimeError("boom")
        return real(rule, obs, **kw)

    monkeypatch.setattr(alert_runner, "evaluate_rule", flaky)

    now = time.time()
    prices = {"AAA-USD": 150.0, "BBB-USD": 150.0}
    _run(prices, now=now)
    stats = _run(prices, now=now + 30)

    assert stats.errors == 1  # one bad rule raised in this cycle
    assert stats.fired == 1  # the good rule still fired
    events = alert_rules.list_events(uid)
    assert len(events) == 1 and events[0]["symbol"] == "BBB"


def test_failure_in_one_users_rule_does_not_affect_another(db, monkeypatch):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _cross_rule(a, "AAA")
    _cross_rule(b, "BBB")

    real = alert_runner.evaluate_rule

    def flaky(rule, obs, **kw):
        if rule["symbol"] == "AAA":
            raise RuntimeError("boom")
        return real(rule, obs, **kw)

    monkeypatch.setattr(alert_runner, "evaluate_rule", flaky)

    now = time.time()
    prices = {"AAA-USD": 150.0, "BBB-USD": 150.0}
    _run(prices, now=now)
    _run(prices, now=now + 30)

    assert alert_rules.list_events(a) == []
    assert len(alert_rules.list_events(b)) == 1


def test_cycle_never_raises_even_if_store_fails(db, monkeypatch):
    def boom(**_kw):
        raise RuntimeError("db gone")

    monkeypatch.setattr(alert_rules, "list_evaluable_rules", boom)
    stats = _run({"BTC-USD": 150.0})
    assert stats.errors == 1


# ── 9. user-scoped events ────────────────────────────────────────────────────


def test_events_are_written_to_the_owning_user(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _cross_rule(a, "BTC")
    now = time.time()
    _confirm({"BTC-USD": 150.0}, now=now)

    assert len(alert_rules.list_events(a)) == 1
    assert alert_rules.list_events(b) == []


def test_two_users_same_symbol_each_get_their_own_event(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _cross_rule(a, "BTC")
    _cross_rule(b, "BTC")
    now = time.time()
    stats = _confirm({"BTC-USD": 150.0}, now=now)

    assert stats.fired == 2
    assert len(alert_rules.list_events(a)) == 1
    assert len(alert_rules.list_events(b)) == 1
    assert alert_rules.list_events(a)[0]["id"] != alert_rules.list_events(b)[0]["id"]


# ── 12. shared market work is memoized ───────────────────────────────────────


def test_history_lookup_is_shared_across_users(db):
    calls = []

    def counting(pid, target):
        calls.append((pid, target))
        return (int(time.time()) - HOUR, 100.0)

    for i in range(4):
        uid = _mk_user(f"u{i}@x.com", f"user{i}")
        _pct_rule(uid, "BTC", threshold=5.0, window="1h")

    _run({"BTC-USD": 150.0}, counting, now=time.time())
    assert len(calls) == 1  # four users, one lookup


def test_history_lookup_not_called_for_price_cross(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")

    def unexpected(_pid, _t):
        raise AssertionError("price_cross must not need history")

    _run({"BTC-USD": 150.0}, unexpected)


# ── 10-11. legacy feed and global watchlist untouched ────────────────────────


def test_runner_writes_only_to_alert_events_user(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    now = time.time()
    _confirm({"BTC-USD": 150.0}, now=now)

    conn = watchlist._db_connect()
    try:
        tables = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()

    # The legacy market-wide feed lives elsewhere entirely.
    assert "alert_events_user" in tables
    assert "alerts_log_main" not in tables
    assert "alerts" not in tables


def test_runner_does_not_touch_global_watchlist_db(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    watchlist.watchlist_db.add("GLOBALLEAK")
    try:
        before = set(watchlist.watchlist_db)
        _confirm({"BTC-USD": 150.0, "GLOBALLEAK-USD": 1.0})
        assert set(watchlist.watchlist_db) == before
        assert all(e["symbol"] != "GLOBALLEAK" for e in alert_rules.list_events(uid))
    finally:
        watchlist.watchlist_db.discard("GLOBALLEAK")


def test_runner_source_imports_no_legacy_alert_modules():
    """Static guarantee that the scanner cannot reach the legacy feed."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "alert_runner.py")).read()
    for forbidden in (
        "alerts_engine",
        "alerts_log_main",
        "alerts.db",
        "alert_events_main",
    ):
        assert forbidden not in src


# ── stats shape ──────────────────────────────────────────────────────────────


def test_cycle_stats_serialize(db):
    uid = _mk_user()
    _cross_rule(uid, "BTC")
    stats = _run({"BTC-USD": 150.0})
    d = stats.as_dict()
    assert d["rules_loaded"] == 1 and d["pending"] == 1
    assert "duration_ms" in d and isinstance(d["skipped"], dict)
