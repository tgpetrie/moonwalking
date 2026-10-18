"""Weak reads are demoted, and 4h/12h/24h outcomes are collected without
disturbing the existing 1-hour grading.

Why: over 369,611 production signals followed for ~24h, "QUIET FLOW BUILDING"
and "MIXED - NO CLEAR EDGE" did measurably worse than a random entry, and the
stored outcomes stopped at one hour so none of that could be checked live.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# The stores import their siblings by flat name, so make this file runnable
# on its own instead of depending on another test having set the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from alert_events import (
        build_event_evolution,
        demoted_last,
        derive_event_read,
        enrich_event,
        notification_candidates,
    )
    from signal_outcomes import (
        EXTENDED_COLUMNS,
        EXTENDED_HORIZON_SECONDS,
        SignalOutcomeStore,
    )
except Exception:  # pragma: no cover
    from backend.alert_events import (  # type: ignore
        build_event_evolution,
        demoted_last,
        derive_event_read,
        enrich_event,
        notification_candidates,
    )
    from backend.signal_outcomes import (  # type: ignore
        EXTENDED_COLUMNS,
        EXTENDED_HORIZON_SECONDS,
        SignalOutcomeStore,
    )

H = 3600
NOW_MS = 1_800_000_000_000
NOW = 1_800_000_000


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "MW_DEMOTE_WEAK_READS",
        "MW_EXTENDED_OUTCOMES",
        "MW_EXTENDED_CHECKPOINT_TOLERANCE_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


# -- demotion ---------------------------------------------------------------


def _alert(offset_s, typ, severity="medium", direction="up", sym="SOL-USD"):
    ts_ms = NOW_MS + offset_s * 1000
    return {
        "id": f"{typ}-{offset_s}-{sym}",
        "symbol": sym,
        "type": typ,
        "type_key": typ,
        "severity": severity,
        "direction": direction,
        "event_ts_ms": ts_ms,
        "expires_at": datetime.fromtimestamp(
            (ts_ms + 900_000) / 1000, tz=timezone.utc
        ).isoformat(),
        "evidence": {},
    }


def test_quiet_flow_and_mixed_reads_are_flagged_as_demoted():
    quiet = derive_event_read(
        state="Building", confidence=62, direction="up",
        families=["flow"], modifiers=["Flow"], evidence={"pct_3m": 0.0},
    )
    mixed = derive_event_read(
        state="Breakout", confidence=90, direction="up",
        families=["price", "flow"], modifiers=["Flow"], conflicting_directions=True,
    )
    assert quiet["label"] == "QUIET FLOW BUILDING" and quiet["demoted"] is True
    assert mixed["label"] == "MIXED — NO CLEAR EDGE" and mixed["demoted"] is True
    assert "no" in quiet["demotion_reason"].lower() and "edge" in quiet["demotion_reason"]
    assert "worse than" not in quiet["demotion_reason"]  # not a claim we can support


@pytest.mark.parametrize("state,conf,fams,mods,evidence", [
    ("Breakout", 84, ["price", "flow"], ["Flow"], {"pct_1m": 0.9}),         # continuation
    ("Reversal Risk", 96, ["price", "flow", "structure"], ["Flow"], {"pct_3m": -2.0}),
    ("Building", 55, ["flow"], ["Flow"], {"pct_3m": 0.6}),                  # quiet strength
])
def test_other_reads_are_not_demoted(state, conf, fams, mods, evidence):
    read = derive_event_read(
        state=state, confidence=conf, direction="up", families=fams,
        modifiers=mods, evidence=evidence,
    )
    assert read["demoted"] is False
    assert "demotion_reason" not in read


def test_demotion_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("MW_DEMOTE_WEAK_READS", "0")
    read = derive_event_read(
        state="Building", confidence=62, direction="up",
        families=["flow"], modifiers=["Flow"], evidence={"pct_3m": 0.0},
    )
    assert read["label"] == "QUIET FLOW BUILDING" and read["demoted"] is False


def test_built_events_from_real_alerts_carry_the_flag():
    event = build_event_evolution([_alert(0, "whale_move", "high")], now_ms=NOW_MS + 60_000)[0]
    assert event["the_read"]["label"] == "QUIET FLOW BUILDING"
    assert event["read_demoted"] is True
    assert event["notify_eligible"] is False


def _event(symbol, confidence, **extra):
    row = {
        "symbol": symbol, "confidence": confidence,
        "notify_eligible": True, "delivery_tier": "notify",
    }
    row.update(extra)
    return row


def test_a_demoted_read_never_notifies_even_at_high_confidence_or_for_holdings():
    events = [
        _event("AAA-USD", 95, read_demoted=True),
        _event("BBB-USD", 95, the_read={"demoted": True}),
        _event("SOL-USD", 70, notify_eligible=False, read_demoted=True),  # held, elevated bar
        _event("CCC-USD", 95),
    ]
    out = notification_candidates(events, priority_symbols={"SOL"})
    assert [e["symbol"] for e in out] == ["CCC-USD"]


def test_context_that_turns_a_read_into_mixed_removes_the_notification():
    event = {
        "id": "x:1", "symbol": "SOL-USD", "primary_state": "Moonwalking",
        "confidence": 95, "direction": "up", "families": ["price", "flow"],
        "modifiers": ["Flow"], "evidence": {"pct_1m": 1.5},
        "notify_eligible": True, "delivery_tier": "notify",
    }
    plain = enrich_event(event, context={})
    assert plain["the_read"]["label"] == "CONTINUATION FAVORED"
    assert plain["read_demoted"] is False and plain["notify_eligible"] is True

    opposed = enrich_event(event, context={"spot_pressure": "selling"})
    assert opposed["the_read"]["label"] == "MIXED — NO CLEAR EDGE"
    assert opposed["read_demoted"] is True
    assert opposed["notify_eligible"] is False
    assert opposed["delivery_tier"] == "signal"


def test_demoted_events_sort_after_all_others_but_keep_their_relative_order():
    events = [
        {"id": 1, "read_demoted": True},
        {"id": 2},
        {"id": 3, "read_demoted": True},
        {"id": 4, "read_demoted": False},
    ]
    assert [e["id"] for e in demoted_last(events)] == [2, 4, 1, 3]


def test_evolution_feed_puts_demoted_reads_last_even_with_higher_confidence():
    quiet = build_event_evolution(
        [_alert(0, "whale_move", "critical", sym="QUIET-USD")], now_ms=NOW_MS + 60_000
    )
    solid = build_event_evolution(
        [_alert(0, "breakout", "high", sym="SOLID-USD"),
         _alert(30, "whale_move", "high", sym="SOLID-USD")],
        now_ms=NOW_MS + 60_000,
    )
    # Force the demoted one to outrank on raw confidence.
    quiet[0]["confidence"] = 99
    merged = build_event_evolution(
        [_alert(0, "whale_move", "critical", sym="QUIET-USD"),
         _alert(0, "breakout", "high", sym="SOLID-USD"),
         _alert(30, "whale_move", "high", sym="SOLID-USD")],
        now_ms=NOW_MS + 60_000,
    )
    assert [e["symbol"] for e in merged] == ["SOLID-USD", "QUIET-USD"]
    assert quiet[0]["read_demoted"] and not solid[0]["read_demoted"]


# -- extended outcomes ------------------------------------------------------


def _row(store, sid, age, *, direction="up", price=100.0, complete=1,
         mfe=0.0, mae=0.0, **extra):
    started = NOW - age
    conn = sqlite3.connect(store.db_path)
    cols = {
        "signal_id": sid, "event_id": sid, "product_id": "BTC-USD",
        "primary_state": "Building", "read_label": "X", "direction": direction,
        "confidence": 50, "started_ts": started, "start_price": price,
        "last_ts": started + H, "last_price": price, "return_15m": 0.5,
        "max_favorable_pct": mfe, "max_adverse_pct": mae, "complete": complete,
    }
    cols.update(extra)
    conn.execute(
        f"INSERT INTO signal_outcomes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(cols.values()),
    )
    conn.commit()
    conn.close()


def _get(store, sid):
    conn = sqlite3.connect(store.db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM signal_outcomes WHERE signal_id=?", (sid,)).fetchone())
    conn.close()
    return row


def test_checkpoints_are_recorded_on_time_in_the_trade_direction(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "long", 4 * H + 60)
    _row(store, "short", 4 * H + 60, direction="down")
    store.advance_extended({"BTC-USD": 102.0}, NOW)
    long_, short = _get(store, "long"), _get(store, "short")
    assert long_["return_4h"] == pytest.approx(2.0)
    assert short["return_4h"] == pytest.approx(-2.0)  # price rose against a short
    assert long_["return_12h"] is None and long_["return_24h"] is None
    assert long_["extended_complete"] == 0


def test_a_missed_checkpoint_is_left_empty_never_filled_late(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "gap", 4 * H + 3000)  # read 50 minutes after the 4h mark
    store.advance_extended({"BTC-USD": 150.0}, NOW)
    assert _get(store, "gap")["return_4h"] is None


def test_each_checkpoint_is_recorded_once(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "a", 4 * H + 60)
    store.advance_extended({"BTC-USD": 102.0}, NOW)
    store.advance_extended({"BTC-USD": 110.0}, NOW + 30)
    assert _get(store, "a")["return_4h"] == pytest.approx(2.0)


def test_excursions_start_from_the_first_hour_and_track_the_24h_extremes(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "a", 2 * H, mfe=1.5, mae=-0.8)
    store.advance_extended({"BTC-USD": 103.0}, NOW)          # +3%: new high
    store.advance_extended({"BTC-USD": 98.0}, NOW + 60)      # -2%: new low
    store.advance_extended({"BTC-USD": 100.0}, NOW + 120)
    row = _get(store, "a")
    assert row["max_favorable_24h"] == pytest.approx(3.0)
    assert row["max_adverse_24h"] == pytest.approx(-2.0)


def test_rows_finish_at_24h_and_stale_rows_are_left_alone(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "done", EXTENDED_HORIZON_SECONDS + 5)
    _row(store, "stale", EXTENDED_HORIZON_SECONDS + 5000)  # beyond tolerance
    store.advance_extended({"BTC-USD": 101.0}, NOW)
    assert _get(store, "done")["extended_complete"] == 1
    assert _get(store, "done")["return_24h"] == pytest.approx(1.0)
    assert _get(store, "stale")["extended_complete"] == 0
    assert _get(store, "stale")["return_24h"] is None


def test_unfinished_hour_rows_are_not_touched(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "open", 5 * H, complete=0)
    store.advance_extended({"BTC-USD": 120.0}, NOW)
    assert _get(store, "open")["return_4h"] is None


def test_missing_price_finishes_a_row_without_inventing_a_return(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "a", EXTENDED_HORIZON_SECONDS + 5)
    store.advance_extended({}, NOW)
    row = _get(store, "a")
    assert row["extended_complete"] == 1 and row["return_24h"] is None


def test_existing_one_hour_grading_is_unchanged(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "a", 4 * H + 60, outcome="followed_through")
    before = _get(store, "a")
    store.advance_extended({"BTC-USD": 102.0}, NOW)
    after = _get(store, "a")
    for col in ("return_15m", "outcome", "complete", "max_favorable_pct",
                "max_adverse_pct", "start_price", "last_ts"):
        assert after[col] == before[col]


def test_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_EXTENDED_OUTCOMES", "0")
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "a", 4 * H + 60)
    store.advance_extended({"BTC-USD": 102.0}, NOW)
    assert _get(store, "a")["return_4h"] is None


def test_existing_database_is_migrated_without_losing_rows(tmp_path):
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE signal_outcomes (signal_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,"
        " product_id TEXT NOT NULL, primary_state TEXT NOT NULL, read_label TEXT NOT NULL,"
        " direction TEXT NOT NULL, confidence INTEGER NOT NULL, started_ts INTEGER NOT NULL,"
        " start_price REAL NOT NULL, last_ts INTEGER NOT NULL, last_price REAL NOT NULL,"
        " return_5m REAL, return_15m REAL, return_30m REAL, return_60m REAL,"
        " max_favorable_pct REAL NOT NULL DEFAULT 0, max_adverse_pct REAL NOT NULL DEFAULT 0,"
        " target_hit_ts INTEGER, adverse_hit_ts INTEGER, outcome TEXT,"
        " complete INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO signal_outcomes (signal_id,event_id,product_id,primary_state,read_label,"
        "direction,confidence,started_ts,start_price,last_ts,last_price,return_15m,complete)"
        " VALUES ('legacy','legacy','BTC-USD','Building','X','up',50,1,100,2,100,0.4,1)"
    )
    conn.commit()
    conn.close()
    store = SignalOutcomeStore(path)
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(signal_outcomes)")}
    assert {c.split()[0] for c in EXTENDED_COLUMNS} <= cols
    legacy = _get(store, "legacy")
    assert legacy["return_15m"] == 0.4 and legacy["extended_complete"] == 0


def test_extended_status_counts_collected_evidence(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    _row(store, "full", EXTENDED_HORIZON_SECONDS + 5, return_4h=1.0, return_12h=2.0, extended_complete=1,
         return_24h=3.0)
    _row(store, "partial", EXTENDED_HORIZON_SECONDS + 5, return_4h=1.0, extended_complete=1)
    status = store.extended_status()
    assert status["rows_finished"] == 2
    assert (status["with_4h"], status["with_12h"], status["with_24h"]) == (2, 1, 1)
