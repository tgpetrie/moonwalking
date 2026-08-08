"""Phase 1 alert-rule engine tests: rules, lifecycle, noise control, scoping."""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import watchlist
import alert_rules
from alert_evaluator import (
    Decision,
    evaluate_rule,
    validate_rule_params,
    MAX_PRICE_AGE_SECONDS,
)


# Captured once at import. Assertions are all relative to this, but it must
# track the real clock: DB-created rules carry a real 90-day expiry, and a
# hardcoded future timestamp would make every one of them look expired.
NOW = time.time()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated SQLite file with the real users/watchlists/alert schema."""
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "wl.sqlite")
    monkeypatch.setattr(watchlist, "_schema_ready", False, raising=False)
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


def _rule(**over):
    """Evaluator-shaped rule dict (no DB needed)."""
    base = {
        "id": "rule_test",
        "user_id": 1,
        "symbol": "BTC",
        "trigger_type": "price_cross",
        "params": {"direction": "above", "threshold": 100.0},
        "repeat_mode": "once",
        "status": "active",
        "armed": True,
        "arm_cycle": 0,
        "cooldown_seconds": 0,
        "reset_pct": 1.0,
        "percent_rearm_ratio": 0.75,
        "last_triggered_ts": None,
        "expires_ts": None,
        "source": "manual",
    }
    base.update(over)
    return base


# ── 1-3. price crossing ──────────────────────────────────────────────────────


def test_upward_price_crossing_fires():
    d = evaluate_rule(_rule(), {"price": 101.0}, now_ts=NOW)
    assert d.should_fire is True
    assert d.event_type == "price_cross"
    assert d.observed_value == 101.0
    assert d.boundary_value == 100.0


def test_downward_price_crossing_fires():
    r = _rule(params={"direction": "below", "threshold": 100.0})
    d = evaluate_rule(r, {"price": 99.0}, now_ts=NOW)
    assert d.should_fire is True


def test_no_trigger_before_crossing():
    d = evaluate_rule(_rule(), {"price": 99.5}, now_ts=NOW)
    assert d.should_fire is False
    assert d.suppression_reason == "condition_not_met"


def test_exact_boundary_does_not_fire():
    # Strictly above, not at — avoids flapping right on the line.
    assert evaluate_rule(_rule(), {"price": 100.0}, now_ts=NOW).should_fire is False


# ── 4. already-satisfied rules rejected at creation ──────────────────────────


def test_above_target_below_current_price_is_rejected():
    ok, err, _ = validate_rule_params(
        "price_cross", {"direction": "above", "threshold": 90.0}, current_price=100.0
    )
    assert ok is False
    assert "already at or below" in err


def test_below_target_above_current_price_is_rejected():
    ok, err, _ = validate_rule_params(
        "price_cross", {"direction": "below", "threshold": 110.0}, current_price=100.0
    )
    assert ok is False
    assert "already at or above" in err


def test_valid_targets_accepted():
    ok, _, p = validate_rule_params(
        "price_cross", {"direction": "above", "threshold": 110.0}, current_price=100.0
    )
    assert ok is True and p["threshold"] == 110.0


@pytest.mark.parametrize("bad", [0, -5, None, "abc", float("nan")])
def test_nonpositive_thresholds_rejected(bad):
    ok, _, _ = validate_rule_params(
        "price_cross", {"direction": "above", "threshold": bad}
    )
    assert ok is False


def test_unsupported_window_rejected():
    ok, err, _ = validate_rule_params(
        "percent_move", {"direction": "up", "threshold": 5, "window": "7d"}
    )
    assert ok is False and "Time window" in err


# ── 5-7. rolling percentage moves ────────────────────────────────────────────


def _pct_rule(**over):
    base = dict(
        trigger_type="percent_move",
        params={"direction": "up", "threshold": 5.0, "window": "1h"},
    )
    base.update(over)
    return _rule(**base)


def test_rolling_1h_percent_move_fires():
    d = evaluate_rule(_pct_rule(), {"price": 106.0, "past_price": 100.0}, now_ts=NOW)
    assert d.should_fire is True
    assert d.comparison_value == 100.0
    assert d.window_label == "1h"


def test_rolling_24h_percent_move_fires():
    r = _pct_rule(params={"direction": "up", "threshold": 5.0, "window": "24h"})
    d = evaluate_rule(r, {"price": 110.0, "past_price": 100.0}, now_ts=NOW)
    assert d.should_fire is True and d.window_label == "24h"


def test_percent_move_below_threshold_does_not_fire():
    d = evaluate_rule(_pct_rule(), {"price": 104.0, "past_price": 100.0}, now_ts=NOW)
    assert d.should_fire is False


def test_direction_up_ignores_downward_move():
    d = evaluate_rule(_pct_rule(), {"price": 90.0, "past_price": 100.0}, now_ts=NOW)
    assert d.should_fire is False


def test_direction_down_fires_on_drop_only():
    r = _pct_rule(params={"direction": "down", "threshold": 5.0, "window": "1h"})
    assert evaluate_rule(
        r, {"price": 94.0, "past_price": 100.0}, now_ts=NOW
    ).should_fire
    assert not evaluate_rule(
        r, {"price": 106.0, "past_price": 100.0}, now_ts=NOW
    ).should_fire


def test_direction_either_fires_both_ways():
    r = _pct_rule(params={"direction": "either", "threshold": 5.0, "window": "1h"})
    assert evaluate_rule(
        r, {"price": 106.0, "past_price": 100.0}, now_ts=NOW
    ).should_fire
    assert evaluate_rule(
        r, {"price": 94.0, "past_price": 100.0}, now_ts=NOW
    ).should_fire


# ── 10. cooldown ─────────────────────────────────────────────────────────────


def test_cooldown_blocks_refire():
    r = _rule(
        repeat_mode="recurring",
        cooldown_seconds=3600,
        last_triggered_ts=NOW - 60,
        armed=True,
    )
    d = evaluate_rule(r, {"price": 101.0}, now_ts=NOW)
    assert d.should_fire is False and d.suppression_reason == "cooldown"


def test_fires_after_cooldown_elapses():
    r = _rule(
        repeat_mode="recurring",
        cooldown_seconds=3600,
        last_triggered_ts=NOW - 7200,
        armed=True,
    )
    assert evaluate_rule(r, {"price": 101.0}, now_ts=NOW).should_fire is True


def test_per_type_minimum_cooldown_is_enforced():
    # A 1-second cooldown is floored to the price_cross minimum (900s).
    r = _rule(
        repeat_mode="recurring",
        cooldown_seconds=1,
        last_triggered_ts=NOW - 60,
        armed=True,
    )
    assert (
        evaluate_rule(r, {"price": 101.0}, now_ts=NOW).suppression_reason == "cooldown"
    )


# ── 11-12. hysteresis and re-arming ──────────────────────────────────────────


def test_disarmed_rule_does_not_refire_while_condition_holds():
    r = _rule(repeat_mode="recurring", armed=False)
    d = evaluate_rule(r, {"price": 150.0}, now_ts=NOW)
    assert d.should_fire is False and d.suppression_reason == "awaiting_reset"


def test_price_must_retreat_past_reset_boundary_to_rearm():
    r = _rule(repeat_mode="recurring", armed=False, reset_pct=1.0)
    # 99.5 is above the 99.0 reset boundary — still not re-armed.
    assert (
        evaluate_rule(r, {"price": 99.5}, now_ts=NOW).suppression_reason
        == "awaiting_reset"
    )
    # 98.9 clears it.
    d = evaluate_rule(r, {"price": 98.9}, now_ts=NOW)
    assert d.suppression_reason == "rearmed"
    assert d.next_armed is True and d.armed_changed is True


def test_below_rule_rearms_upward():
    r = _rule(
        params={"direction": "below", "threshold": 100.0},
        repeat_mode="recurring",
        armed=False,
        reset_pct=1.0,
    )
    assert (
        evaluate_rule(r, {"price": 100.5}, now_ts=NOW).suppression_reason
        == "awaiting_reset"
    )
    assert (
        evaluate_rule(r, {"price": 101.5}, now_ts=NOW).suppression_reason == "rearmed"
    )


def test_percent_move_rearms_only_after_magnitude_decays():
    """Cooldown alone is insufficient: the rolling window stays true for hours."""
    r = _pct_rule(repeat_mode="recurring", armed=False, percent_rearm_ratio=0.75)
    # Move still 6% (>= 5 * 0.75 = 3.75) — not re-armed.
    assert (
        evaluate_rule(
            r, {"price": 106.0, "past_price": 100.0}, now_ts=NOW
        ).suppression_reason
        == "awaiting_reset"
    )
    # Decayed to 3% — re-arms.
    assert (
        evaluate_rule(
            r, {"price": 103.0, "past_price": 100.0}, now_ts=NOW
        ).suppression_reason
        == "rearmed"
    )


# ── 19-20. bad market data ───────────────────────────────────────────────────


def test_stale_price_never_fires():
    obs = {"price": 101.0, "price_ts": NOW - (MAX_PRICE_AGE_SECONDS + 60)}
    assert evaluate_rule(_rule(), obs, now_ts=NOW).suppression_reason == "stale_price"


def test_fresh_price_still_fires():
    obs = {"price": 101.0, "price_ts": NOW - 10}
    assert evaluate_rule(_rule(), obs, now_ts=NOW).should_fire is True


@pytest.mark.parametrize("bad", [None, 0, -1, "abc", float("nan"), float("inf"), True])
def test_malformed_price_never_fires(bad):
    d = evaluate_rule(_rule(), {"price": bad}, now_ts=NOW)
    assert d.should_fire is False and d.suppression_reason == "no_price"


def test_missing_comparison_price_is_recorded_not_fabricated():
    d = evaluate_rule(_pct_rule(), {"price": 106.0, "past_price": None}, now_ts=NOW)
    assert d.should_fire is False
    assert d.suppression_reason == "no_comparison_price"


def test_paused_and_expired_rules_never_fire():
    assert (
        evaluate_rule(
            _rule(status="paused"), {"price": 999.0}, now_ts=NOW
        ).suppression_reason
        == "rule_paused"
    )
    assert (
        evaluate_rule(
            _rule(expires_ts=NOW - 1), {"price": 999.0}, now_ts=NOW
        ).suppression_reason
        == "rule_expired"
    )


# ── 23. deterministic explanations ───────────────────────────────────────────


def test_explanation_states_what_and_why():
    d = evaluate_rule(_rule(), {"price": 101.0}, now_ts=NOW)
    assert "BTC rose above $100.00" in d.explanation
    assert "You created this alert" in d.explanation


def test_explanation_is_deterministic():
    a = evaluate_rule(_rule(), {"price": 101.0}, now_ts=NOW).explanation
    b = evaluate_rule(_rule(), {"price": 101.0}, now_ts=NOW + 5000).explanation
    assert a == b


def test_recommended_rule_explains_its_origin():
    r = _rule(source="recommended", recommendation_basis="portfolio")
    d = evaluate_rule(r, {"price": 101.0}, now_ts=NOW)
    assert "portfolio holding" in d.explanation


def test_recurring_explains_cooldown_not_advice():
    r = _rule(repeat_mode="recurring")
    d = evaluate_rule(r, {"price": 101.0}, now_ts=NOW)
    assert "cooling down" in d.explanation


def test_explanations_contain_no_trading_advice():
    import re

    forbidden = [
        r"\bbuy\b",
        r"\bsell\b",
        r"\bhold\b",
        r"\benter\b",
        r"\bexit\b",
        r"stop loss",
        r"take profit",
        r"will go",
        r"should you",
    ]
    cases = [
        evaluate_rule(_rule(), {"price": 101.0}, now_ts=NOW),
        evaluate_rule(
            _rule(params={"direction": "below", "threshold": 100.0}),
            {"price": 99.0},
            now_ts=NOW,
        ),
        evaluate_rule(_pct_rule(), {"price": 106.0, "past_price": 100.0}, now_ts=NOW),
        evaluate_rule(
            _pct_rule(repeat_mode="recurring"),
            {"price": 106.0, "past_price": 100.0},
            now_ts=NOW,
        ),
    ]
    for d in cases:
        for pat in forbidden:
            assert not re.search(pat, d.explanation.lower()), (pat, d.explanation)


# ── 8-9, 13-14, 22. persistence and lifecycle ────────────────────────────────


def test_rule_created_and_listed(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="btc",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    assert rule["symbol"] == "BTC" and rule["status"] == "active" and rule["armed"]
    assert len(alert_rules.list_rules(uid)) == 1


def test_create_rejects_already_satisfied_rule(db):
    uid = _mk_user()
    with pytest.raises(alert_rules.RuleError, match="already at or below"):
        alert_rules.create_rule(
            uid,
            symbol="BTC",
            trigger_type="price_cross",
            params={"direction": "above", "threshold": 90.0},
            current_price=100.0,
        )


def test_duplicate_rule_detected(db):
    uid = _mk_user()
    kw = dict(
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.create_rule(uid, **kw)
    with pytest.raises(alert_rules.RuleError, match="already have a similar alert"):
        alert_rules.create_rule(uid, **kw)


def test_once_rule_transitions_to_triggered(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="once",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    d = evaluate_rule(rule, {"price": 115.0}, now_ts=NOW)
    event = alert_rules.apply_decision(rule, d)
    assert event is not None
    after = alert_rules.get_rule(uid, rule["id"])
    assert after["status"] == "triggered" and after["armed"] is False


def test_recurring_rule_transitions_to_cooling_down(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="recurring",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.apply_decision(rule, evaluate_rule(rule, {"price": 115.0}, now_ts=NOW))
    after = alert_rules.get_rule(uid, rule["id"])
    assert after["status"] == "cooling_down" and after["armed"] is False


def test_rearm_returns_recurring_rule_to_active_and_bumps_cycle(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="recurring",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.apply_decision(rule, evaluate_rule(rule, {"price": 115.0}, now_ts=NOW))
    fired = alert_rules.get_rule(uid, rule["id"])
    assert fired["arm_cycle"] == 0

    rearm = evaluate_rule(fired, {"price": 100.0}, now_ts=NOW + 10_000)
    alert_rules.apply_decision(fired, rearm)
    back = alert_rules.get_rule(uid, rule["id"])
    assert back["status"] == "active" and back["armed"] is True
    assert back["arm_cycle"] == 1


def test_duplicate_event_suppressed_within_arm_cycle(db):
    """The same firing cannot be recorded twice — enforced by the database."""
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="recurring",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    d = evaluate_rule(rule, {"price": 115.0}, now_ts=NOW)
    assert alert_rules.record_event(rule, d) is not None
    assert alert_rules.record_event(rule, d) is None  # same arm cycle
    assert len(alert_rules.list_events(uid)) == 1


def test_new_arm_cycle_allows_a_genuinely_new_event(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="recurring",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.apply_decision(rule, evaluate_rule(rule, {"price": 115.0}, now_ts=NOW))
    fired = alert_rules.get_rule(uid, rule["id"])
    alert_rules.apply_decision(
        fired, evaluate_rule(fired, {"price": 100.0}, now_ts=NOW + 10_000)
    )
    rearmed = alert_rules.get_rule(uid, rule["id"])
    rearmed["last_triggered_ts"] = None  # cooldown already covered elsewhere
    alert_rules.apply_decision(
        rearmed, evaluate_rule(rearmed, {"price": 120.0}, now_ts=NOW + 20_000)
    )
    assert len(alert_rules.list_events(uid)) == 2


def test_dedupe_and_state_survive_restart(db, monkeypatch):
    """Simulate a process restart: reset module state, reopen the same file."""
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        repeat_mode="recurring",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    d = evaluate_rule(rule, {"price": 115.0}, now_ts=NOW)
    alert_rules.apply_decision(rule, d)

    monkeypatch.setattr(alert_rules, "_schema_ready", False)  # cold start
    alert_rules.ensure_alert_schema()

    reloaded = alert_rules.get_rule(uid, rule["id"])
    assert reloaded["armed"] is False  # cooldown/arm state persisted
    assert reloaded["status"] == "cooling_down"
    assert alert_rules.record_event(reloaded, d) is None  # dedupe survived
    assert len(alert_rules.list_events(uid)) == 1


def test_history_records_explanation_and_values(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.apply_decision(rule, evaluate_rule(rule, {"price": 115.0}, now_ts=NOW))
    ev = alert_rules.list_events(uid)[0]
    assert ev["observed_value"] == 115.0 and ev["boundary_value"] == 110.0
    assert "BTC rose above" in ev["explanation"]
    assert ev["delivery_status"] == "pending"
    assert ev["not_financial_advice"] is True


def test_pause_and_delete(db):
    uid = _mk_user()
    rule = alert_rules.create_rule(
        uid,
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    assert alert_rules.set_rule_status(uid, rule["id"], "paused")["status"] == "paused"
    assert alert_rules.delete_rule(uid, rule["id"]) is True
    assert alert_rules.get_rule(uid, rule["id"]) is None


# ── 21. per-user isolation ───────────────────────────────────────────────────


def test_rules_are_isolated_between_users(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    rule = alert_rules.create_rule(
        a,
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    assert alert_rules.list_rules(b) == []
    assert alert_rules.get_rule(b, rule["id"]) is None
    assert alert_rules.delete_rule(b, rule["id"]) is False
    assert alert_rules.get_rule(a, rule["id"]) is not None  # untouched


def test_events_are_isolated_between_users(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    rule = alert_rules.create_rule(
        a,
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    alert_rules.apply_decision(rule, evaluate_rule(rule, {"price": 115.0}, now_ts=NOW))
    assert len(alert_rules.list_events(a)) == 1
    assert alert_rules.list_events(b) == []


def test_two_users_may_hold_identical_rules(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    kw = dict(
        symbol="BTC",
        trigger_type="price_cross",
        params={"direction": "above", "threshold": 110.0},
        current_price=100.0,
    )
    ra = alert_rules.create_rule(a, **kw)
    rb = alert_rules.create_rule(b, **kw)  # not a duplicate: different owner
    assert ra["id"] != rb["id"]


# ── 15-18. recommendations ───────────────────────────────────────────────────


def _add_watchlist_item(uid, symbol):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        wl = conn.execute(
            "SELECT id FROM watchlists WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone()
        if not wl:
            conn.execute(
                """INSERT INTO watchlists (id, user_id, name, description, notes,
                   position, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
                (f"wl_{uid}", uid, "Main", "", "", 1, now, now),
            )
            wl_id = f"wl_{uid}"
        else:
            wl_id = wl["id"]
        conn.execute(
            """INSERT INTO watchlist_items (id, watchlist_id, item_key, item_type,
               title, notes, position, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (f"it_{uid}_{symbol}", wl_id, symbol, "Asset", symbol, "", 1, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def _add_holding(uid, symbol, price=100.0):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        conn.execute(
            """INSERT INTO manual_cost_basis (user_id, symbol, average_price, note,
               created_at, updated_at) VALUES (?,?,?,?,?,?)""",
            (uid, symbol, price, "", now, now),
        )
        conn.commit()
    finally:
        conn.close()


def test_recommendations_built_from_portfolio_and_watchlist(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    _add_watchlist_item(uid, "SOL")
    recs = alert_rules.build_recommendations(uid)
    by_symbol = {r["symbol"]: r for r in recs}
    assert by_symbol["ETH"]["basis"] == "portfolio"
    assert by_symbol["SOL"]["basis"] == "watchlist"
    assert "in your portfolio" in by_symbol["ETH"]["reason"]


def test_recommendation_is_never_active_without_consent(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    recs = alert_rules.build_recommendations(uid)
    assert recs and all(r["status"] == "pending" for r in recs)
    assert alert_rules.list_rules(uid) == []  # nothing activated


def test_accepting_a_recommendation_creates_an_active_rule(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    rec = alert_rules.build_recommendations(uid)[0]
    rule = alert_rules.accept_recommendation(uid, rec["id"])
    assert rule["status"] == "active"
    assert rule["source"] == "recommended"
    assert rule["recommendation_basis"] == "portfolio"
    assert alert_rules.list_recommendations(uid) == []  # no longer pending


def test_dismissed_recommendation_does_not_return(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    rec = alert_rules.build_recommendations(uid)[0]
    assert alert_rules.dismiss_recommendation(uid, rec["id"]) is True
    assert alert_rules.list_recommendations(uid) == []
    alert_rules.build_recommendations(uid)  # rebuild must not resurrect it
    assert alert_rules.list_recommendations(uid) == []


def test_expired_recommendations_are_not_listed(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    rec = alert_rules.build_recommendations(uid)[0]
    conn = watchlist._db_connect()
    try:
        conn.execute(
            "UPDATE alert_recommendations SET expires_ts = ? WHERE id = ?",
            (int(time.time()) - 10, rec["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    assert alert_rules.list_recommendations(uid) == []


def test_manual_rule_takes_precedence_over_recommendation(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    alert_rules.create_rule(
        uid,
        symbol="ETH",
        trigger_type="percent_move",
        params={"direction": "either", "threshold": 6.0, "window": "24h"},
    )
    recs = alert_rules.build_recommendations(uid)
    assert all(r["symbol"] != "ETH" for r in recs)


def test_accepted_recommendation_cannot_be_accepted_twice(db):
    uid = _mk_user()
    _add_holding(uid, "ETH")
    rec = alert_rules.build_recommendations(uid)[0]
    alert_rules.accept_recommendation(uid, rec["id"])
    with pytest.raises(alert_rules.RuleError, match="already"):
        alert_rules.accept_recommendation(uid, rec["id"])


def test_recommendations_are_user_scoped(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _add_holding(a, "ETH")
    alert_rules.build_recommendations(a)
    assert alert_rules.list_recommendations(b) == []
    assert alert_rules.build_recommendations(b) == []


def test_other_user_cannot_accept_or_dismiss(db):
    a = _mk_user("a@x.com", "alice")
    b = _mk_user("b@x.com", "bob")
    _add_holding(a, "ETH")
    rec = alert_rules.build_recommendations(a)[0]
    with pytest.raises(alert_rules.RuleError):
        alert_rules.accept_recommendation(b, rec["id"])
    assert alert_rules.dismiss_recommendation(b, rec["id"]) is False


# ── suggested thresholds scale with the asset ────────────────────────────────


def test_suggested_thresholds_are_not_universal():
    btc = alert_rules.suggest_threshold("BTC")
    mid = alert_rules.suggest_threshold("SOL")
    micro = alert_rules.suggest_threshold("SOMEMICROCAP")
    assert btc < mid < micro


def test_volatility_data_overrides_tier_default():
    quiet = alert_rules.suggest_threshold("SOMEMICROCAP", daily_volatility_pct=2.0)
    jumpy = alert_rules.suggest_threshold("SOMEMICROCAP", daily_volatility_pct=14.0)
    assert quiet < jumpy
    assert 3.0 <= quiet <= 25.0 and 3.0 <= jumpy <= 25.0


def test_suggested_threshold_is_deterministic():
    assert alert_rules.suggest_threshold("BTC") == alert_rules.suggest_threshold("BTC")


# ── user interest sources never touch the global watchlist set ───────────────


def test_interest_sources_ignore_global_watchlist_db(db):
    uid = _mk_user()
    watchlist.watchlist_db.add("GLOBALLEAK")
    try:
        assert "GLOBALLEAK" not in alert_rules.user_watchlist_symbols(uid)
        assert "GLOBALLEAK" not in alert_rules.user_portfolio_symbols(uid)
    finally:
        watchlist.watchlist_db.discard("GLOBALLEAK")
