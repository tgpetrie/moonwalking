from __future__ import annotations

try:
    from signal_outcomes import SignalOutcomeStore
except Exception:  # pragma: no cover
    from backend.signal_outcomes import SignalOutcomeStore


def _event(signal_id="signal-1", direction="up"):
    return {
        "id": signal_id,
        "event_id": "event-1",
        "product_id": "KITE-USD",
        "primary_state": "Breakout",
        "direction": direction,
        "confidence": 84,
        "latest_transition_ts_ms": 1_000_000,
        "the_read": {"label": "CONTINUATION FAVORED"},
        "evidence": {"price": 100},
    }


def test_outcome_store_records_target_before_adverse(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event()], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 102.5}, now_ts=1300)
    store.observe([], {"KITE": 102.2}, now_ts=4600)

    history = store.history_for(_event())
    status = store.status()

    assert status == {
        "total": 1,
        "complete": 1,
        "collecting": 0,
        "target_pct": 2.0,
        "adverse_pct": 1.0,
        "horizon_minutes": 60,
    }
    assert history["sample_size"] == 1
    assert history["follow_through_rate"] == 1.0
    assert history["median_favorable_pct"] == 2.5


def test_outcome_store_marks_stop_first_as_no_follow_through(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-2")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 98.5}, now_ts=1100)
    store.observe([], {"KITE": 103}, now_ts=1200)
    store.observe([], {"KITE": 102}, now_ts=4600)

    history = store.history_for(_event("signal-2"))

    assert history["sample_size"] == 1
    assert history["follow_through_rate"] == 0.0


def test_down_direction_scores_falling_price_as_favorable(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    event = _event("signal-down", direction="down")
    store.observe([event], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 97.5}, now_ts=1300)
    store.observe([], {"KITE": 98}, now_ts=4600)

    history = store.history_for(event)

    assert history["follow_through_rate"] == 1.0
