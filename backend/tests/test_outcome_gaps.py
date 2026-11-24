"""Outcome tracking across collection gaps (backend stopped, PC asleep).

Before this, the first observe() after a gap recorded the post-gap price as
each missed checkpoint's return and finished the row, so a "15-minute
return" could be measured days later. See backend/outcome_gaps.py.
"""

import pytest

try:
    from board_outcomes import BoardOutcomeStore
    from signal_outcomes import SignalOutcomeStore
except Exception:  # pragma: no cover
    from backend.board_outcomes import BoardOutcomeStore
    from backend.signal_outcomes import SignalOutcomeStore

DAY = 86400


@pytest.fixture(autouse=True)
def real_threshold(monkeypatch):
    monkeypatch.setenv("MW_OUTCOME_GAP_SECONDS", "300")


def event(signal_id="sig-1"):
    return {
        "id": signal_id,
        "event_id": "event-1",
        "product_id": "KITE-USD",
        "primary_state": "Breakout",
        "direction": "up",
        "confidence": 80,
        "the_read": {"label": "CONTINUATION FAVORED"},
        "evidence": {"price": 100},
    }


def signal_row(store, signal_id="sig-1"):
    conn = store._connect()
    try:
        return conn.execute(
            "SELECT * FROM signal_outcomes WHERE signal_id = ?", (signal_id,)
        ).fetchone()
    finally:
        conn.close()


def tick(store, start, end, price, step=15, events=()):
    """Observe on the live cadence from start to end inclusive."""
    for t in range(start, end + 1, step):
        store.observe(list(events) if t == start else [], price if isinstance(price, dict) else {"KITE": price}, now_ts=t)


# --- signals ---------------------------------------------------------------


def test_signal_on_normal_cadence_grades_every_checkpoint(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    tick(store, 1000, 1000 + 3600 + 15, 101, events=[event()])
    row = signal_row(store)
    assert row["complete"] == 1
    assert row["outcome"] != "interrupted"
    assert all(row[c] is not None for c in ("return_5m", "return_15m", "return_30m", "return_60m"))


def test_signal_open_when_tracking_stopped_is_interrupted_not_graded_late(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    tick(store, 1000, 1400, 100, events=[event()])  # 5m checkpoint on time
    store.observe([], {"KITE": 150}, now_ts=1000 + 3 * DAY)  # wake up days later

    row = signal_row(store)
    assert row["complete"] == 1
    assert row["outcome"] == "interrupted"
    assert row["return_5m"] == pytest.approx(0.0)
    assert row["return_15m"] is None and row["return_60m"] is None
    assert row["last_price"] == 100  # the post-gap price is never attributed to it
    assert store.status()["interrupted"] == 1


def test_signal_gap_is_detected_across_a_restart(tmp_path):
    db = tmp_path / "s.sqlite"
    tick(SignalOutcomeStore(db), 1000, 1400, 100, events=[event()])
    restarted = SignalOutcomeStore(db)
    restarted.observe([], {"KITE": 150}, now_ts=1000 + DAY)
    assert signal_row(restarted)["outcome"] == "interrupted"


def test_signal_gap_detected_in_a_store_written_before_the_heartbeat(tmp_path):
    db = tmp_path / "s.sqlite"
    store = SignalOutcomeStore(db)
    tick(store, 1000, 1400, 100, events=[event()])
    conn = store._connect()
    conn.execute("DELETE FROM tracker_heartbeat")
    conn.commit()
    conn.close()
    SignalOutcomeStore(db).observe([], {"KITE": 150}, now_ts=1000 + DAY)
    assert signal_row(store)["outcome"] == "interrupted"


def test_signal_checkpoint_missed_while_price_was_absent_stays_empty(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    tick(store, 1000, 1240, 100, events=[event()])
    tick(store, 1255, 1700, {})  # tracker running, no KITE price past the 5m mark
    tick(store, 1715, 2000, 103)
    row = signal_row(store)
    assert row["return_5m"] is None  # would have been read 400s+ late
    assert row["return_15m"] == pytest.approx(3.0)  # back on time for 15m


def test_interrupted_signals_are_left_out_of_the_scorecard(tmp_path):
    store = SignalOutcomeStore(tmp_path / "s.sqlite")
    tick(store, 1000, 1400, 100, events=[event("lost")])
    store.observe([], {"KITE": 150}, now_ts=1000 + DAY)
    later = 1000 + DAY
    tick(store, later + 15, later + 15 + 3615, 101, events=[event("graded")])
    assert signal_row(store, "graded")["outcome"] != "interrupted"
    # Only the graded row reaches the scorecard's research rows.
    assert store.scorecard()["research_only_rows_excluded"] == 1


# --- boards ----------------------------------------------------------------


def board_item(price=100.0, change=1.2):
    return {"symbol": "SOL", "product_id": "SOL-USD", "current_price": price,
            "change_1m": change, "change_3m": change}


def board_tick(store, start, end, price, step=15):
    boards = {"ignition_1m": [board_item(price)], "confirmation_3m_up": [], "confirmation_3m_down": []}
    for t in range(start, end + 1, step):
        store.observe(boards, {"SOL-USD": price}, now_ts=t)


def board_row(store):
    conn = store._connect()
    try:
        return conn.execute("SELECT * FROM board_outcomes_v2 WHERE board = 'ignition_1m'").fetchone()
    finally:
        conn.close()


def test_board_row_open_when_tracking_stopped_gets_no_grade(tmp_path):
    store = BoardOutcomeStore(tmp_path / "b.sqlite")
    board_tick(store, 10_000, 10_400, 100.0)  # 5m on time, gap before 15m
    board_tick(store, 10_000 + 2 * DAY, 10_000 + 2 * DAY, 130.0)

    row = board_row(store)
    assert row["complete"] == 1
    assert row["outcome_15m"] == "interrupted"
    assert row["return_5m"] is not None
    assert row["return_15m"] is None and row["return_60m"] is None
    status = store.status()
    assert status["interrupted"] == 1
    assert status["boards"]["ignition_1m"]["sample_size"] == 0  # not counted as noise


def test_board_grade_earned_before_the_gap_stands(tmp_path):
    store = BoardOutcomeStore(tmp_path / "b.sqlite")
    board_tick(store, 10_000, 11_000, 103.0)  # 15m measured and graded on time
    graded = board_row(store)["outcome_15m"]
    assert graded not in (None, "interrupted")
    board_tick(store, 10_000 + DAY, 10_000 + DAY, 50.0)

    row = board_row(store)
    assert row["complete"] == 1
    assert row["outcome_15m"] == graded
    assert row["return_60m"] is None  # not the price a day later
