import pytest

from smart_alerts import DEFAULT_RULES, PREDICATES, SmartAlertEngine, in_quiet_hours

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
