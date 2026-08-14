from __future__ import annotations

import pytest

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


def _row(store, signal_id):
    conn = store._connect()
    try:
        return conn.execute(
            "SELECT * FROM signal_outcomes WHERE signal_id = ?", (signal_id,)
        ).fetchone()
    finally:
        conn.close()


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


def test_sample_after_horizon_cannot_create_target_or_favorable_extreme(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-late-target")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 105}, now_ts=4601)

    row = _row(store, "signal-late-target")

    assert row["target_hit_ts"] is None
    assert row["max_favorable_pct"] == 0.0
    assert row["complete"] == 1
    assert row["outcome"] == "did_not_follow_through"


def test_sample_after_horizon_cannot_create_adverse_hit_or_extreme(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-late-adverse")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 90}, now_ts=4601)

    row = _row(store, "signal-late-adverse")

    assert row["adverse_hit_ts"] is None
    assert row["max_adverse_pct"] == 0.0
    assert row["complete"] == 1


def test_sample_at_horizon_boundary_still_counts(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-boundary")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 102.5}, now_ts=4600)

    row = _row(store, "signal-boundary")

    assert row["target_hit_ts"] == 4600
    assert row["max_favorable_pct"] == pytest.approx(2.5)
    assert row["complete"] == 1
    assert row["outcome"] == "followed_through"


def test_on_time_samples_record_each_checkpoint(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-checkpoints")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 101}, now_ts=1300)
    store.observe([], {"KITE": 102}, now_ts=1900)
    store.observe([], {"KITE": 103}, now_ts=2800)
    store.observe([], {"KITE": 104}, now_ts=4600)

    row = _row(store, "signal-checkpoints")

    assert row["return_5m"] == pytest.approx(1.0)
    assert row["return_15m"] == pytest.approx(2.0)
    assert row["return_30m"] == pytest.approx(3.0)
    assert row["return_60m"] == pytest.approx(4.0)


def test_gap_records_only_latest_reached_checkpoint(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-checkpoint-gap")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 107}, now_ts=4700)

    row = _row(store, "signal-checkpoint-gap")

    assert row["return_5m"] is None
    assert row["return_15m"] is None
    assert row["return_30m"] is None
    assert row["return_60m"] == pytest.approx(7.0)


def test_grading_window_starts_when_baseline_price_is_observed(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    observed_ts = 100_000
    event = _event("signal-delayed-observation")
    event["latest_transition_ts_ms"] = (observed_ts - 1200) * 1000

    store.observe([event], {"KITE": 100}, now_ts=observed_ts)
    row = _row(store, "signal-delayed-observation")

    assert row["started_ts"] == observed_ts
    assert row["start_price"] == 100
    assert row["return_5m"] is None
    assert row["return_15m"] is None
    assert row["complete"] == 0

    store.observe([], {"KITE": 101}, now_ts=observed_ts + 2500)
    assert _row(store, "signal-delayed-observation")["complete"] == 0

    store.observe([], {"KITE": 102.5}, now_ts=observed_ts + 3600)
    row = _row(store, "signal-delayed-observation")

    assert row["complete"] == 1
    assert row["outcome"] == "followed_through"


def test_missing_price_before_horizon_leaves_outcome_open(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-missing-early")], {"KITE": 100}, now_ts=1000)
    store.observe([], {}, now_ts=4500)

    row = _row(store, "signal-missing-early")

    assert row["complete"] == 0
    assert row["outcome"] is None
    assert row["last_ts"] == 1000
    assert row["last_price"] == 100


def test_missing_price_at_horizon_closes_without_inventing_evidence(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-missing-horizon")], {"KITE": 100}, now_ts=1000)
    store.observe([], {}, now_ts=4600)

    row = _row(store, "signal-missing-horizon")

    assert row["complete"] == 1
    assert row["outcome"] == "did_not_follow_through"
    assert row["target_hit_ts"] is None
    assert row["adverse_hit_ts"] is None
    assert store.status()["collecting"] == 0


def test_missing_final_price_preserves_observed_target(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    store.observe([_event("signal-missing-after-target")], {"KITE": 100}, now_ts=1000)
    store.observe([], {"KITE": 102.5}, now_ts=1300)
    store.observe([], {}, now_ts=4600)

    row = _row(store, "signal-missing-after-target")

    assert row["complete"] == 1
    assert row["outcome"] == "followed_through"
    assert row["target_hit_ts"] == 1300
    assert row["last_ts"] == 1300
    assert row["last_price"] == pytest.approx(102.5)


def test_baseline_uses_canonical_snapshot_instead_of_event_evidence(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    event = _event("signal-source-disagreement")
    event["evidence"]["price"] = 100

    store.observe([event], {"KITE": 103}, now_ts=1000)
    row = _row(store, "signal-source-disagreement")

    assert row["start_price"] == 103
    assert row["last_price"] == 103
    assert row["target_hit_ts"] is None
    assert row["max_favorable_pct"] == 0.0


def test_event_evidence_without_canonical_quote_creates_no_outcome(tmp_path):
    store = SignalOutcomeStore(tmp_path / "outcomes.sqlite")
    event = _event("signal-evidence-only")
    event["evidence"]["price"] = 100

    store.observe([event], {}, now_ts=1000)

    assert _row(store, "signal-evidence-only") is None
    assert store.status()["total"] == 0
