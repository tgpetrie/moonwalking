from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from email.header import decode_header, make_header
import json
from threading import Event

import pytest

from alert_delivery import AlertDeliveryDispatcher
from macro_industry_scanner import scan_universe_cycles
from smart_alerts import (
    DEFAULT_RULES,
    PREDICATES,
    DuplicateRuleName,
    SmartAlertEngine,
    in_quiet_hours,
)

NOW = 1_800_000_000.0


def _row(symbol, price, **extra):
    return {"symbol": symbol, "available": True, "price": price, **extra}


def _scan(*rows, stage="stage_1_macro_compression"):
    return {"industry": {"available": True, "liquidity_rotation_stage": stage}, "coins": list(rows)}


class FakeDispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, events, *, now=None):
        self.events.extend(events)
        return len(events)


@pytest.fixture
def pushes():
    return []


@pytest.fixture
def engine(tmp_path, pushes):
    return SmartAlertEngine(
        tmp_path / "alerts.sqlite",
        ntfy_url="https://ntfy.example/topic",
        dispatcher=FakeDispatcher(),
        http_post=lambda url, body, headers: pushes.append((url, body, headers)),
        local_hour=lambda ts: 12,
    )


def _only(engine, *names):
    for rule in engine.list_rules():
        engine.set_enabled(rule["id"], rule["name"] in names)


def test_default_rules_seed_once_and_deleted_rules_stay_deleted(tmp_path):
    engine = SmartAlertEngine(tmp_path / "a.sqlite", ntfy_url="")
    names = [rule["name"] for rule in engine.list_rules()]
    assert names == [rule["name"] for rule in DEFAULT_RULES]
    engine.delete_rule(engine.list_rules()[0]["id"])
    assert len(SmartAlertEngine(tmp_path / "a.sqlite", ntfy_url="").list_rules()) == 3


def test_stage_3_wake_up_pushes_urgent_ntfy_and_dispatches(engine, pushes):
    _only(engine, "Stage 3 Industry Breakout Wake-Up")
    assert engine.evaluate(_scan(), now=NOW) == []
    (alert,) = engine.evaluate(_scan(stage="stage_3_alt_index_breakout"), now=NOW)
    assert alert["symbol"] == "MARKET" and alert["urgency"] == "wake_up"
    (_url, _body, headers), = pushes
    assert headers["Priority"] == "urgent"
    assert alert["delivered"] == {"ntfy": "sent", "dispatcher": 1}
    assert engine.dispatcher.events[0]["primary_state"] == "Stage 3 Industry Breakout Wake-Up"


def test_held_rules_only_read_held_coins(engine, pushes):
    _only(engine, "Held Position Rollover Trim Alert", "Held Position Stop-Proximity Alert")
    scan = _scan(
        _row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0}),
        _row("ETH", 3000.0, rollover_target_box={"low": 2900.0, "high": 3100.0}),
        _row("ADA", 1.0, accumulation_invalidation_stop={"stop_price": 0.98, "stop_distance_pct": 2.0}),
    )
    fired = engine.evaluate(scan, positions=[{"symbol": "SOL"}, {"product_id": "ADA-USD"}], now=NOW)
    assert {(a["symbol"], a["rule_name"]) for a in fired} == {
        ("SOL", "Held Position Rollover Trim Alert"),
        ("ADA", "Held Position Stop-Proximity Alert"),
    }
    assert {h["Priority"] for _u, _b, h in pushes} == {"high", "urgent"}


def test_position_stop_overrides_cycle_stop_for_proximity(engine):
    _only(engine, "Held Position Stop-Proximity Alert")
    scan = _scan(_row("ADA", 1.0, accumulation_invalidation_stop={"stop_price": 0.8, "stop_distance_pct": 20.0}))
    assert engine.evaluate(scan, positions=[{"symbol": "ADA"}], now=NOW) == []
    assert engine.evaluate(scan, positions=[{"symbol": "ADA", "stop_price": 0.99}], now=NOW)


def test_direct_smart_alert_evaluation_rejects_stale_or_mixed_snapshot(engine):
    _only(engine, "Held Position Rollover Trim Alert")
    cutoff = int(NOW // 86400) * 86400
    scan = {
        **_scan(_row("SOL", 175, rollover_target_box={"low": 150, "high": 200}, market_as_of_ts=cutoff)),
        "status": "ready", "computed_at": NOW, "ttl_seconds": 1800,
        "market_snapshot": {"snapshot_id": "shared", "as_of_ts": cutoff, "timeframe": "1d"},
    }
    assert engine.evaluate(scan, positions=[{"symbol": "SOL"}], now=NOW + 1800) == []
    scan["coins"][0]["market_as_of_ts"] -= 86400
    assert engine.evaluate(scan, positions=[{"symbol": "SOL"}], now=NOW) == []
    scan["coins"][0]["market_as_of_ts"] += 86400
    (alert,) = engine.evaluate(scan, positions=[{"symbol": "SOL"}], now=NOW)
    assert alert["evidence"]["market_snapshot"]["snapshot_id"] == "shared"


def test_watchlist_accumulation_rule_needs_both_conditions(engine):
    _only(engine, "Watchlist Deep Accumulation + StochRSI Turn Alert")
    good = _row("LINK", 10.0, bucket="deep_accumulation_exhaustion", weekly_stoch_direction="oversold_turn_up")
    half = _row("UNI", 5.0, bucket="deep_accumulation_exhaustion", weekly_stoch_direction="high_to_low_drift")
    fired = engine.evaluate(_scan(good, half), watchlist=["LINK", "UNI-USD"], now=NOW)
    assert [a["symbol"] for a in fired] == ["LINK"]


def test_cooldown_suppresses_repeat_until_it_expires(engine):
    _only(engine)
    engine.upsert_rule(
        {"name": "BTC over 100k", "urgency": "action_queue", "scope": "symbols", "symbols": ["BTC"],
         "conditions": [{"predicate": "price_above", "value": 100_000}], "cooldown_seconds": 3600}
    )
    scan = _scan(_row("BTC", 101_000.0))
    assert len(engine.evaluate(scan, now=NOW)) == 1
    assert engine.evaluate(scan, now=NOW + 1800) == []
    assert len(engine.evaluate(scan, now=NOW + 3601)) == 1


def test_quiet_hours_hold_back_action_queue_but_not_wake_up(tmp_path):
    pushes = []
    engine = SmartAlertEngine(
        tmp_path / "q.sqlite",
        ntfy_url="https://ntfy.example/topic",
        http_post=lambda url, body, headers: pushes.append(headers),
        local_hour=lambda ts: 2,
        default_quiet_hours={"start_hour": 23, "end_hour": 7},
    )
    _only(engine, "Stage 3 Industry Breakout Wake-Up", "Held Position Rollover Trim Alert")
    scan = _scan(_row("SOL", 175.0, rollover_target_box={"low": 150.0, "high": 200.0}),
                 stage="stage_3_alt_index_breakout")
    fired = {a["rule_name"]: a for a in engine.evaluate(scan, positions=[{"symbol": "SOL"}], now=NOW)}
    assert fired["Held Position Rollover Trim Alert"]["suppressed_reason"] == "quiet_hours"
    assert fired["Stage 3 Industry Breakout Wake-Up"]["suppressed_reason"] is None
    assert [h["Priority"] for h in pushes] == ["urgent"]
    # A quiet-hours suppression does not start the cooldown.
    assert len(engine.history()) == 2


def test_watch_urgency_records_without_pushing(engine, pushes):
    _only(engine)
    engine.upsert_rule({"name": "ETH weak", "urgency": "watch", "scope": "universe",
                        "conditions": [{"predicate": "price_below", "value": 2000}]})
    (alert,) = engine.evaluate(_scan(_row("ETH", 1900.0)), now=NOW)
    assert alert["delivered"] == {} and pushes == []
    assert engine.history(symbol="ETH")[0]["rule_name"] == "ETH weak"


def test_ntfy_failure_is_recorded_not_raised(tmp_path):
    def boom(*_args):
        raise OSError("down")

    engine = SmartAlertEngine(tmp_path / "f.sqlite", ntfy_url="https://x/t", http_post=boom,
                              local_hour=lambda ts: 12)
    _only(engine, "Stage 3 Industry Breakout Wake-Up")
    (alert,) = engine.evaluate(_scan(stage="stage_4_alt_season_expansion"), now=NOW)
    assert alert["delivered"]["ntfy"] == "failed:OSError"


@pytest.mark.parametrize(
    "predicate, value, snapshot, expected",
    [
        ("cycle_bucket", ["growth_expansion_ride", "rollover_profit_zone"], {"bucket": "rollover_profit_zone"}, True),
        ("liquidity_rotation_stage", "stage_2_btc_majors_lead", {"liquidity_rotation_stage": "stage_2_btc_majors_lead"}, True),
        ("liquidity_rotation_stage", {"max": 2}, {"liquidity_rotation_stage": "stage_3_alt_index_breakout"}, False),
        ("rsi_regime", {"timeframe": "1w", "regime": "growth_expansion"}, {"rsi_regimes": {"1w": "growth_expansion"}}, True),
        ("weekly_stoch_rsi_turn", None, {"weekly_stoch_direction": "oversold_turn_up"}, True),
        ("daily_macd_kiss", True, {"daily_macd_kiss": False}, False),
        ("weekly_macd_cross", True, {"weekly_macd_bullish_cross": True}, True),
        ("fib_zone_hit", {"low": 1, "high": 2}, {"price": 1.5}, True),
        ("fib_zone_hit", "at_multi_year_support", {"price": 1.5, "at_multi_year_support": True}, True),
        ("confirmation_pivot_break", True, {"breaking_confirmation_pivot": True}, True),
        ("stop_proximity_pct", {"max": 3}, {"stop_distance_pct": None}, False),
        ("price_above", 10, {"price": 10}, False),
        ("price_below", 10, {"price": 9.99}, True),
    ],
)
def test_predicates(predicate, value, snapshot, expected):
    assert PREDICATES[predicate](snapshot, value) is expected


def test_rule_validation_rejects_bad_rules(engine):
    for bad in (
        {"name": "", "conditions": [{"predicate": "price_above", "value": 1}]},
        {"name": "x", "urgency": "panic", "conditions": [{"predicate": "price_above", "value": 1}]},
        {"name": "x", "conditions": [{"predicate": "moon_phase"}]},
        {"name": "x", "scope": "symbols", "conditions": [{"predicate": "price_above", "value": 1}]},
        {"name": "x", "quiet_hours": {"start_hour": 25, "end_hour": 1},
         "conditions": [{"predicate": "price_above", "value": 1}]},
    ):
        with pytest.raises(ValueError):
            engine.upsert_rule(bad)


def test_in_quiet_hours_wraps_midnight():
    window = {"start_hour": 22, "end_hour": 6}
    assert in_quiet_hours(window, 23) and in_quiet_hours(window, 5)
    assert not in_quiet_hours(window, 6) and not in_quiet_hours(None, 3)


def test_all_predicates_evaluate_real_cycle_rows(engine, cycle_fixture):
    _only(engine)
    render = cycle_fixture("render_cycle_fixture")
    fet = cycle_fixture("fet_channel_fixture")
    theta = cycle_fixture("theta_wxy_confluence_fixture")
    scan = scan_universe_cycles({
        "BTC-USD": render,
        "ETH-USD": render,
        "SOL-USD": render,
        "LINK-USD": theta,
        "AAVE-USD": fet,
        "RENDER-USD": render,
        "FET-USD": fet,
        "THETA-USD": theta,
    })
    cases = [
        ("liquidity_rotation_stage", 1, "MARKET"),
        ("cycle_bucket", "deep_accumulation_exhaustion", "RENDER"),
        ("rsi_regime", {"timeframe": "1m", "regime": "oversold_compression"}, "RENDER"),
        ("rsi_regime", {"timeframe": "1d", "regime": "growth_expansion"}, "THETA"),
        ("weekly_stoch_rsi_turn", "oversold_turn_up", "FET"),
        ("daily_macd_kiss", True, "RENDER"),
        ("weekly_macd_cross", False, "RENDER"),
        ("fib_zone_hit", "at_multi_year_support", "THETA"),
        ("confirmation_pivot_break", False, "RENDER"),
        ("stop_proximity_pct", {"max": 1}, "RENDER"),
        ("price_above", 1.5, "RENDER"),
        ("price_below", 0.7, "FET"),
    ]
    expected = set()
    for predicate, value, symbol in cases:
        rule = engine.create_rule({
            "name": f"{predicate} {symbol}",
            "scope": "market" if symbol == "MARKET" else "symbols",
            "symbols": [] if symbol == "MARKET" else [symbol],
            "conditions": [{"predicate": predicate, "value": value}],
        })
        expected.add((rule["id"], symbol))
    fired = engine.evaluate(scan, positions=[{"symbol": "RENDER", "stop_price": 1.71}], now=NOW)
    assert {predicate for predicate, _value, _symbol in cases} == set(PREDICATES)
    assert {(alert["rule_id"], alert["symbol"]) for alert in fired} == expected
    assert len(engine.history()) == len(expected)


@pytest.mark.parametrize("predicate, value", [
    ("rsi_regime", {"timeframe": [], "regime": "growth_expansion"}),
    ("rsi_regime", {"timeframe": "4h", "regime": "growth_expansion"}),
    ("liquidity_rotation_stage", {"min": 5}),
    ("liquidity_rotation_stage", {"min": 3, "max": 2}),
    ("stop_proximity_pct", {"max": "invalid"}),
    ("stop_proximity_pct", {}),
    ("fib_zone_hit", {"low": 2, "high": 1}),
    ("price_above", float("inf")),
    ("price_below", True),
    ("weekly_macd_cross", "false"),
])
def test_rule_rejects_unusable_condition_values(engine, predicate, value):
    with pytest.raises(ValueError, match=f"invalid value for {predicate}"):
        engine.create_rule({"name": "invalid", "conditions": [{"predicate": predicate, "value": value}]})


def test_invalid_legacy_rule_does_not_block_valid_rules(engine):
    _only(engine)
    rule = engine.create_rule({
        "name": "legacy",
        "conditions": [{"predicate": "rsi_regime", "value": "growth_expansion"}],
    })
    payload = {key: value for key, value in rule.items() if key not in {"id", "seeded"}}
    payload["conditions"][0]["value"] = {"timeframe": [], "regime": "growth_expansion"}
    with closing(engine._connect()) as conn, conn:
        conn.execute(
            "UPDATE smart_alert_rules SET rule_json = ? WHERE id = ?",
            (json.dumps(payload), rule["id"]),
        )
    engine.create_rule({"name": "valid", "conditions": [{"predicate": "price_above", "value": 1}]})
    (fired,) = engine.evaluate(_scan(_row("SOL", 2)), now=NOW)
    assert fired["rule_name"] == "valid"
    assert engine.set_enabled(rule["id"], False)["enabled"] is False


@pytest.mark.parametrize("predicate, field", [
    ("daily_macd_kiss", "daily_macd_kiss"),
    ("weekly_macd_cross", "weekly_macd_bullish_cross"),
    ("confirmation_pivot_break", "breaking_confirmation_pivot"),
])
def test_negative_predicate_needs_observed_false(predicate, field):
    assert PREDICATES[predicate]({field: False}, False)
    assert not PREDICATES[predicate]({field: None}, False)
    assert not PREDICATES[predicate]({}, False)


def test_create_rule_conflict_preserves_existing_rule_and_delete_preserves_history(engine):
    _only(engine)
    payload = {"name": "one", "conditions": [{"predicate": "price_above", "value": 1}]}
    rule = engine.create_rule(payload)
    with pytest.raises(DuplicateRuleName):
        engine.create_rule({**payload, "enabled": False})
    assert engine.get_rule(rule["id"])["enabled"] is True
    engine.evaluate(_scan(_row("SOL", 2)), now=NOW)
    assert engine.delete_rule(rule["id"])
    assert engine.history(symbol="SOL")[0]["rule_name"] == "one"


def test_concurrent_runners_share_cooldown_before_network_io(tmp_path):
    started = Event()
    release = Event()
    pushes = []

    def post(_url, body, _headers):
        pushes.append(body)
        if len(pushes) == 1:
            started.set()
            assert release.wait(5)

    kwargs = {"ntfy_url": "https://ntfy.example/topic", "http_post": post, "seed_defaults": False}
    one = SmartAlertEngine(tmp_path / "shared.sqlite", **kwargs)
    two = SmartAlertEngine(tmp_path / "shared.sqlite", **kwargs)
    one.create_rule({
        "name": "wake",
        "urgency": "wake_up",
        "conditions": [{"predicate": "price_above", "value": 1}],
    })
    scan = _scan(_row("SOL", 2))
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(one.evaluate, scan, now=NOW)
        try:
            assert started.wait(5)
            assert two.evaluate(scan, now=NOW) == []
        finally:
            release.set()
        (alert,) = first.result()
    assert len(pushes) == 1
    assert one.history() == [alert]
    assert len(two.evaluate(_scan(_row("ETH", 3)), now=NOW)) == 1


def test_quiet_hour_action_cooldown_does_not_delay_later_delivery(tmp_path):
    pushes = []
    engine = SmartAlertEngine(
        tmp_path / "quiet.sqlite",
        seed_defaults=False,
        ntfy_url="https://ntfy.example/topic",
        http_post=lambda *args: pushes.append(args),
        local_hour=lambda ts: 2 if ts < NOW + 3 else 10,
        default_quiet_hours={"start_hour": 22, "end_hour": 6},
    )
    for urgency in ("action_queue", "watch"):
        engine.create_rule({
            "name": urgency,
            "urgency": urgency,
            "conditions": [{"predicate": "price_above", "value": 1}],
        })
    scan = _scan(_row("SOL", 2))
    quiet_rows = {row["urgency"]: row for row in engine.evaluate(scan, now=NOW)}
    assert quiet_rows["action_queue"]["suppressed_reason"] == "quiet_hours"
    assert quiet_rows["watch"]["suppressed_reason"] is None
    assert not pushes
    assert engine.evaluate(scan, now=NOW + 1) == []
    (after_quiet,) = engine.evaluate(scan, now=NOW + 3)
    assert after_quiet["delivered"] == {"ntfy": "sent"}
    assert len(pushes) == 1


def test_test_alert_never_resets_cooldown_for_even_a_real_test_symbol(engine, monkeypatch):
    monkeypatch.setenv("MW_ALERT_NOTIFY_ENABLED", "1")
    monkeypatch.setenv("MW_DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("MW_NOTIFY_MAX_PER_HOUR", "6")
    monkeypatch.setenv("MW_NOTIFY_SYMBOL_COOLDOWN_SECONDS", "900")
    dispatcher = AlertDeliveryDispatcher()
    sent = []
    monkeypatch.setattr(dispatcher, "_send_discord", lambda event: sent.append(event))
    engine.dispatcher = dispatcher
    _only(engine)
    rule = engine.create_rule({
        "name": "Test symbol is traded",
        "urgency": "wake_up",
        "conditions": [{"predicate": "price_above", "value": 1}],
    })
    test = engine.send_test(rule_id=rule["id"], now=NOW)
    scan = _scan(_row("TEST", 2))
    (real,) = engine.evaluate(scan, now=NOW + 1)
    assert test["evidence"] == {"test": True}
    assert real["evidence"]["price"] == 2
    assert test["delivered"]["dispatcher"] == real["delivered"]["dispatcher"] == 1
    assert [event["is_test"] for event in sent] == [True, False]
    assert engine.evaluate(scan, now=NOW + 2) == []


def test_unicode_ntfy_title_and_dispatcher_failure_keep_history(engine, pushes, monkeypatch):
    class UnavailableDispatcher:
        def dispatch(self, *_args, **_kwargs):
            raise OSError("unavailable channel")

    engine.dispatcher = UnavailableDispatcher()
    title = "Wake · 波"
    rule = engine.create_rule({
        "name": title,
        "urgency": "wake_up",
        "conditions": [{"predicate": "price_above", "value": 1}],
    })
    alert = engine.send_test(rule_id=rule["id"], now=NOW)
    encoded = pushes[-1][2]["Title"]
    assert encoded.isascii()
    assert str(make_header(decode_header(encoded))) == f"Moonwalking: {title}"
    assert alert["delivered"] == {"ntfy": "sent", "dispatcher": "failed:OSError"}

    def broken_ntfy(*_args):
        raise RuntimeError("unavailable topic")

    monkeypatch.setattr(engine, "http_post", broken_ntfy)
    (fired,) = engine.evaluate(_scan(_row("SOL", 2)), now=NOW + 1)
    assert fired["delivered"] == {"ntfy": "failed:RuntimeError", "dispatcher": "failed:OSError"}
    assert engine.history()[:2] == [fired, alert]
