"""Delayed readiness is scoped, keeps missing rows, and does not imply delivery."""

from dataclasses import replace

import pytest

from test_instant_timed_features import BTC, COIN, CUTOFF, feature_tape
from instant_delayed_decision import prepare_decision
from instant_delayed_eligibility import LocalDelivery, assess_cohort


def test_proof_arrival_changes_a_new_view_without_rewriting_an_earlier_decision():
    tape = feature_tape()
    early = CUTOFF + 1
    late = CUTOFF + 180
    before = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=early)
    ready = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=late)
    control = prepare_decision(tape.rec, BTC, CUTOFF, "up", asof=late)

    def assess(asof, decisions, **kwargs):
        cohort = assess_cohort(
            tape.rec, CUTOFF, asof=asof, decisions=decisions, **kwargs
        )
        assert cohort["planned_rows"] == 4
        assert not cohort["study_eligible"]
        return {(r["product_id"], r["direction"]): r for r in cohort["rows"]}

    old = assess(early, [before])
    assert (
        old[(COIN, "up")]["feature_reasons"]["F2"] == "trade_row_processing_incomplete"
    )
    assert not old[(COIN, "up")]["complete_vector_candidate"]
    observation = LocalDelivery(ready.sha256, CUTOFF + 240, CUTOFF + 260)
    new = assess(
        late,
        [ready, control],
        local_deliveries={(COIN, "up"): observation},
        deadline_age_ms=250,
    )
    coin = new[(COIN, "up")]
    assert coin["complete_vector_candidate"]
    assert coin["delivery"] == dict(
        status="after_bound", commit_age_ms=240, consumer_age_ms=260
    )
    assert not new[(BTC, "up")]["complete_vector_candidate"]
    assert new[(BTC, "up")]["role"] == "benchmark"
    assert new[(COIN, "down")]["input_status"] == "decision_missing"
    assert new[(BTC, "down")]["delivery"]["status"] == "not_measured"
    tape.now += 5000
    tape.hb(tape.now, 10, BTC)
    assert assess(early, [before]) == old


def test_rejects_duplicate_decisions_and_unbound_delivery():
    tape = feature_tape()
    asof = CUTOFF + 180
    decision = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=asof)
    with pytest.raises(ValueError, match="duplicated"):
        assess_cohort(tape.rec, CUTOFF, asof=asof, decisions=[decision, decision])
    wrong = LocalDelivery("wrong-digest", CUTOFF + 200, CUTOFF + 210)
    with pytest.raises(ValueError, match="does not match decision digest"):
        assess_cohort(
            tape.rec,
            CUTOFF,
            asof=asof,
            decisions=[decision],
            local_deliveries={(COIN, "up"): wrong},
        )
    with pytest.raises(ValueError, match="precedes"):
        assess_cohort(
            tape.rec,
            CUTOFF,
            asof=asof,
            decisions=[decision],
            local_deliveries={
                (COIN, "up"): replace(
                    wrong,
                    decision_sha256=decision.sha256,
                    consumer_seen_ts_ms=CUTOFF + 199,
                )
            },
        )
