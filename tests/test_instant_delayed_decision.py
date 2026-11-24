"""Synthetic late-decision and independent grading-clock tests."""

from dataclasses import FrozenInstanceError
import json
import math

import pytest

from test_instant_timed_features import CUTOFF, COIN, BTC, feature_tape
from instant_delayed_decision import (
    grade_publication,
    observe_publication,
    prepare_decision,
)


def start(tape, *, asof=CUTOFF + 180, direction="up"):
    decision = prepare_decision(tape.rec, COIN, CUTOFF, direction, asof=asof)
    tape.now = CUTOFF + 260
    publication = observe_publication(
        tape.rec, decision, publication_id="synthetic-1", published=CUTOFF + 230
    )
    return decision, publication


def outcome(tape, horizon=300, *, blank_btc_close=False):
    end = CUTOFF + horizon * 1000
    watermark = tape.rec.trades[-1].trade_id
    ids = []
    for ts in range(CUTOFF, end, 5000):
        if len(ids) < 3:
            watermark += 1
            ids.append(watermark)
            tape.trade(ts + 1000, watermark)
        mid = 110 + 40 * (ts + 5000 - CUTOFF) / (end - CUTOFF)
        tape.send(
            ts + 2000,
            "snapshot",
            COIN,
            bids=[[str(mid - 1), "3"]],
            asks=[[str(mid + 1), "1"]],
        )
        if not blank_btc_close or ts not in (end - 5000, end - 10000):
            tape.send(
                ts + 2000, "snapshot", BTC, bids=[["50999", "3"]], asks=[["51001", "1"]]
            )
        tape.hb(ts + 5000, watermark)
        tape.hb(ts + 5000, 10, BTC)
    # Exact right boundary also contributes no forward match.
    tape.trade(end, watermark + 1)
    tape.now = end + 1
    return end, ids


def test_freezes_actual_feature_timing_and_binds_observed_publication():
    tape = feature_tape()
    decision, publication = start(tape)
    row = json.loads(decision.feature_json)
    assert row["features"]["F2"]["evidence_available_ts_ms"] == CUTOFF + 180
    assert decision.knowledge_asof_ts_ms == CUTOFF + 180
    assert decision.feature_computation_completed_ts_ms == CUTOFF + 180
    assert decision.decision_completed_ts_ms == CUTOFF + 180
    assert publication.timing.published_ts_ms == CUTOFF + 230
    assert publication.timing.feature_age_at_publication_ms == 230
    assert publication.timing.legacy_cutoff_inputs_compatible is False
    assert publication.observation_recorded_ts_ms == CUTOFF + 260
    assert publication.durable_publication_verified is False
    with pytest.raises(FrozenInstanceError):
        decision.feature_json = "{}"
    row["features"].clear()
    assert json.loads(decision.feature_json)["features"]["F2"]["status"] == "ready"


@pytest.mark.parametrize(
    ("published", "error"),
    [(CUTOFF + 179, "causal"), (CUTOFF + 181, "has not been reached")],
)
def test_rejects_impossible_publication_clock(published, error):
    tape = feature_tape()
    decision = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=CUTOFF + 180)
    with pytest.raises(ValueError, match=error):
        observe_publication(tape.rec, decision, publication_id="x", published=published)


def test_rejects_a_different_tape_with_the_same_plan():
    decision, publication = start(feature_tape())
    other = feature_tape(unknown_side=True)
    with pytest.raises(ValueError, match="evidence prefix differ"):
        observe_publication(
            other.rec, decision, publication_id="x", published=CUTOFF + 180
        )
    other.now = CUTOFF + 1000
    with pytest.raises(ValueError, match="evidence prefix differ"):
        grade_publication(other.rec, publication, 300, asof=other.now)


@pytest.mark.parametrize(
    ("horizon", "direction", "success"), [(300, "up", True), (900, "down", False)]
)
def test_maturity_horizon_direction_and_open_forward_trade_bounds(
    horizon, direction, success
):
    tape = feature_tape()
    decision, publication = start(tape, direction=direction)
    end, _ = outcome(tape, horizon)
    pending = grade_publication(tape.rec, publication, horizon, asof=end - 1)
    assert pending["status"] == "pending"
    assert pending["cutoff_verified_forward"] is None
    closed = grade_publication(tape.rec, publication, horizon, asof=end)
    assert closed["status"] == "unavailable"
    assert closed["cutoff_verified_forward"] is None
    grade = grade_publication(tape.rec, publication, horizon, asof=end + 1)
    assert grade["status"] == "ready"
    assert grade["cutoff_verified_forward"] is success
    assert grade["forward_match_count"] == 3
    assert grade["terminal_residual_log"] == pytest.approx(
        math.log(150 / 110) * (1 if direction == "up" else -1)
    )
    assert grade["horizon_end_ts_ms"] == CUTOFF + horizon * 1000
    assert grade["decision_sha256"] == decision.sha256


@pytest.mark.parametrize("decision_conflict", [False, True])
def test_late_conflict_vetoes_grading_without_rewriting_the_decision(decision_conflict):
    tape = feature_tape()
    decision, publication = start(tape)
    frozen = decision.sha256
    end, ids = outcome(tape)
    trade_id = (
        next(t.trade_id for t in tape.rec.trades if t.receipt_ts_ms == CUTOFF - 30000)
        if decision_conflict
        else ids[0]
    )
    assert grade_publication(tape.rec, publication, 300, asof=end + 1)[
        "cutoff_verified_forward"
    ]
    ts = end + 2000
    tape.trade(ts, trade_id, size="250", steps=[ts, ts, ts, ts, ts + 90])
    partial = grade_publication(tape.rec, publication, 300, asof=ts + 1)
    assert partial["reason"] == "grading_payload_processing_incomplete"
    later = grade_publication(tape.rec, publication, 300, asof=ts + 90)
    assert later["status"] == "unavailable"
    assert later["reason"] == "conflicting_trade_id"
    assert later["evidence_scope"] == (
        "decision_trade_window" if decision_conflict else "outcome_trade_window"
    )
    assert later["cutoff_verified_forward"] is None
    prior = grade_publication(tape.rec, publication, 300, asof=end + 1)
    assert prior["cutoff_verified_forward"] is True
    assert decision.sha256 == frozen
    assert (
        later["grading_packet_prefix_sha256"] != prior["grading_packet_prefix_sha256"]
    )


def test_later_evidence_cannot_fill_a_feature_missing_from_the_decision():
    tape = feature_tape()
    decision, publication = start(tape, asof=CUTOFF + 1)
    end, _ = outcome(tape)
    grade = grade_publication(tape.rec, publication, 300, asof=end + 1)
    assert grade["reason"] == "decision_features_unavailable"
    assert grade["missing_features"] == ["F2"]
    assert (
        json.loads(decision.feature_json)["features"]["F2"]["status"] == "unavailable"
    )
    assert grade["cutoff_verified_forward"] is None


def test_missing_benchmark_close_is_ungradable():
    tape = feature_tape()
    _, publication = start(tape)
    end, _ = outcome(tape, blank_btc_close=True)
    grade = grade_publication(tape.rec, publication, 300, asof=end + 1)
    assert grade["reason"] == "stale_book_observation"
    assert grade["missing_quote_ts_ms"] == end
    assert grade["product_with_missing_evidence"] == BTC
    assert grade["cutoff_verified_forward"] is None
