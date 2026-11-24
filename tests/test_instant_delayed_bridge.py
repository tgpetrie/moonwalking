"""Synthetic probes for the delayed-decision bridge and the benchmark guard."""

import copy

import pytest

from test_instant_delayed_decision import outcome
from test_instant_timed_features import BTC, COIN, CUTOFF, feature_tape
import instant_association as assoc
import instant_directional_exposure as directional
from instant_delayed_bridge import (
    SELF_RESIDUAL,
    VERSION,
    delayed_eligibility_to_directional_slots,
    grades_to_association_labels,
    provenance,
    version,
)
from instant_delayed_decision import (
    grade_publication,
    observe_publication,
    prepare_decision,
)
from instant_delayed_eligibility import assess_cohort
from instant_targets import V2_CONTRACT_PATH, load_contract


ASOF = CUTOFF + 180
END = CUTOFF + 300_000
CONTRACT = load_contract(V2_CONTRACT_PATH)[1]
SLOTS = [(COIN, "up"), (COIN, "down"), (BTC, "up"), (BTC, "down")]


def graded_cohort():
    """One cutoff, both products and directions, published and graded at 300s."""
    tape = feature_tape()
    decisions = {
        slot: prepare_decision(tape.rec, slot[0], CUTOFF, slot[1], asof=ASOF)
        for slot in SLOTS
    }
    cohort = assess_cohort(
        tape.rec, CUTOFF, asof=ASOF, decisions=list(decisions.values())
    )
    tape.now = CUTOFF + 260
    publications = {
        slot: observe_publication(
            tape.rec,
            decision,
            publication_id=f"pub-{slot[0]}-{slot[1]}",
            published=CUTOFF + 230,
        )
        for slot, decision in decisions.items()
    }
    end, _ = outcome(tape, 300)
    assert end == END

    def grades(asof):
        return {
            slot: grade_publication(tape.rec, publication, 300, asof=asof)
            for slot, publication in publications.items()
        }

    return cohort, grades(END - 1), grades(END + 1)


@pytest.fixture(scope="module")
def graded():
    return graded_cohort()


def labels_by_slot(grades):
    rows = grades_to_association_labels(grades.values(), v2_contract_sha256=CONTRACT)
    return {(row["product_id"], row["direction"]): row for row in rows}


def alert(slot):
    return dict(
        publication_id=f"pub-{slot[0]}-{slot[1]}",
        product_id=slot[0],
        direction=slot[1],
        anchor_ts_ms=CUTOFF,
        inputs_available_ts_ms=ASOF,
        published_ts_ms=CUTOFF + 230,
    )


# ---------- benchmark guard in the grader ----------


def test_benchmark_grade_is_unavailable_and_never_a_failed_outcome(graded):
    _, pending, mature = graded
    for direction in ("up", "down"):
        early, late = pending[(BTC, direction)], mature[(BTC, direction)]
        assert (early["status"], early["reason"]) == ("pending", "horizon_not_mature")
        assert (late["status"], late["reason"]) == ("unavailable", SELF_RESIDUAL)
        assert late["cutoff_verified_forward"] is None
        assert "terminal_residual_log" not in late  # no zero residual is reported
    assert mature[(COIN, "up")]["cutoff_verified_forward"] is True
    assert mature[(COIN, "down")]["cutoff_verified_forward"] is False


def test_ready_grade_records_when_its_forward_peak_occurred(graded):
    _, _, mature = graded
    # The synthetic mid rises to the horizon end, so an up peak is the last
    # grid point and a down peak is the anchor itself.
    assert mature[(COIN, "up")]["peak_ts_ms"] == END
    assert mature[(COIN, "down")]["peak_ts_ms"] == CUTOFF


# ---------- grades to association labels ----------


def test_ready_grades_become_labels_the_association_report_accepts(graded):
    _, _, mature = graded
    labels = labels_by_slot(mature)
    up, down = labels[(COIN, "up")], labels[(COIN, "down")]
    for row in labels.values():
        assert all(key in row for key in assoc.LABEL_KEYS)
        assert row["contract_version"] == assoc.TARGET_VERSION
        assert row["contract_sha256"] == CONTRACT
        assert row["evaluator_sha256"] == provenance()["adapted_evaluator_sha256"]
        assert row["bridge_version"] == VERSION == version
        assert (row["anchor_ts_ms"], row["label_maturity_ts_ms"]) == (CUTOFF, END)
    assert (up["status"], up["verified_forward"]) == ("ready", True)
    assert up["peak_ts_ms"] == END
    assert (down["status"], down["verified_forward"]) == ("ready", False)
    assert up["decision_sha256"] == mature[(COIN, "up")]["decision_sha256"]
    assert up["publication_id"] == "pub-" + COIN + "-up"

    alerts = [alert(slot) for slot in SLOTS[:3]]
    report = assoc.association_report(list(labels.values()), alerts, asof_ts_ms=END + 1)
    table = report["horizons"]["300"]["primary_pointwise"]
    assert (table["success_count"], table["failure_count"]) == (1, 1)
    assert table["ungradable_reasons"] == {f"unavailable:{SELF_RESIDUAL}": 1}
    assert report["target_evaluator_sha256"] == up["evaluator_sha256"]
    window = report["horizons"]["300"]["forward_window_coverage"]
    assert window["window_count"] == 1 and window["covered_count"] == 1


def test_unadapted_grades_still_fail_the_association_report(graded):
    _, _, mature = graded
    with pytest.raises(ValueError, match="malformed label row"):
        assoc.association_report(list(mature.values()), [], asof_ts_ms=END + 1)


def test_pending_and_unavailable_grades_are_preserved_not_coerced(graded):
    _, pending, mature = graded
    for row in labels_by_slot(pending).values():
        assert (row["status"], row["verified_forward"]) == ("pending", None)
        assert row["reason"] == "horizon_not_mature" and "peak_ts_ms" not in row
    benchmark = labels_by_slot(mature)[(BTC, "up")]
    assert (benchmark["status"], benchmark["verified_forward"]) == ("unavailable", None)
    assert benchmark["reason"] == SELF_RESIDUAL

    stale = dict(mature[(COIN, "up")], status="unavailable", reason="stale_book")
    with pytest.raises(ValueError, match="incomplete grade cannot carry an outcome"):
        grades_to_association_labels([stale], v2_contract_sha256=CONTRACT)
    stale["cutoff_verified_forward"] = None
    (row,) = grades_to_association_labels([stale], v2_contract_sha256=CONTRACT)
    assert (row["status"], row["reason"]) == ("unavailable", "stale_book")
    assert row["verified_forward"] is None
    unknown = dict(mature[(COIN, "up")], cutoff_verified_forward=None)
    with pytest.raises(ValueError, match="never coerce"):
        grades_to_association_labels([unknown], v2_contract_sha256=CONTRACT)


def test_a_ready_benchmark_grade_from_an_older_grader_is_not_a_failure(graded):
    _, _, mature = graded
    old = dict(mature[(COIN, "down")], product_id=BTC)  # ready and False
    (row,) = grades_to_association_labels([old], v2_contract_sha256=CONTRACT)
    assert (row["status"], row["reason"]) == ("unavailable", SELF_RESIDUAL)
    assert row["verified_forward"] is None and "peak_ts_ms" not in row
    assert row["source_grade_status"] == "ready"


@pytest.mark.parametrize("peak", [None, CUTOFF - 5000, END + 5000, float(END)])
def test_a_ready_grade_without_a_valid_peak_time_is_unavailable(graded, peak):
    _, _, mature = graded
    grade = dict(mature[(COIN, "up")], peak_ts_ms=peak)
    if peak is None:
        del grade["peak_ts_ms"]
    (row,) = grades_to_association_labels([grade], v2_contract_sha256=CONTRACT)
    assert (row["status"], row["verified_forward"]) == ("unavailable", None)
    assert row["reason"] == "grade_forward_peak_time_missing"


def test_rejects_foreign_duplicate_and_malformed_grades(graded):
    _, _, mature = graded
    grade = mature[(COIN, "up")]

    def adapt(*rows, contract=CONTRACT):
        return grades_to_association_labels(rows, v2_contract_sha256=contract)

    with pytest.raises(ValueError, match="declared v2 contract"):
        adapt(grade, contract="another-contract")
    with pytest.raises(ValueError, match="duplicate delayed grade identity"):
        adapt(grade, dict(grade))
    with pytest.raises(ValueError, match="malformed delayed grade row"):
        adapt({k: v for k, v in grade.items() if k != "decision_sha256"})
    with pytest.raises(ValueError, match="unsupported grade version or scope"):
        adapt(dict(grade, version="instant-later-cutoff-grade-v0"))
    with pytest.raises(ValueError, match="5s grid"):
        adapt(dict(grade, feature_cutoff_ts_ms=CUTOFF + 1))
    with pytest.raises(ValueError, match="cutoff plus horizon"):
        adapt(dict(grade, horizon_end_ts_ms=END + 5000))
    with pytest.raises(ValueError, match="unknown grade status"):
        adapt(dict(grade, status="graded"))


def test_adapted_labels_cannot_be_mixed_with_native_labels(graded):
    _, _, mature = graded
    adapted = labels_by_slot(mature)[(COIN, "up")]
    native = dict(
        adapted,
        anchor_ts_ms=CUTOFF + 5000,
        label_maturity_ts_ms=END + 5000,
        peak_ts_ms=END,
        evaluator_sha256="native-v2-evaluator",
    )
    with pytest.raises(ValueError, match="cannot mix"):
        assoc.association_report([adapted, native], [], asof_ts_ms=END + 5001)


# ---------- delayed eligibility to directional slots ----------


def slots_by_key(cohort, wait):
    slots = delayed_eligibility_to_directional_slots([cohort], allowed_wait_ms=wait)
    return slots, {(row["product_id"], row["direction"]): row for row in slots}


def test_delayed_cohort_becomes_paired_slots_the_exposure_report_accepts(graded):
    cohort, _, mature = graded
    slots, by_key = slots_by_key(cohort, 180)
    assert len(slots) == 4
    for row in slots:
        assert row["ts_ms"] == row["available_ts_ms"] == CUTOFF  # raw cutoff kept
        assert (row["known_at_ts_ms"], row["allowed_wait_ms"]) == (ASOF, 180)
        assert row["known_within_allowed_wait"] is True
    for direction in ("up", "down"):
        coin, btc = by_key[(COIN, direction)], by_key[(BTC, direction)]
        assert [coin[flag] for flag in assoc.ELIGIBILITY_FLAGS] == [True] * 4
        assert coin["bridge_reason"] is None
        assert btc["universe_member"] is False and btc["candidate_eligible"] is False
        assert btc["bridge_reason"] == SELF_RESIDUAL

    labels = grades_to_association_labels(mature.values(), v2_contract_sha256=CONTRACT)
    report = directional.exposure_report(labels, slots, asof_ts_ms=END + 1)
    for direction in ("up", "down"):
        board = report["boards"][direction]
        assert board["recorded_slot_count"] == 2
        assert board["decision_eligible_slot_count"] == 1
        assert board["exclusions_by_first_failed_flag"]["universe_member"] == 1
        assert board["horizons"]["300"]["gradable_slot_count"] == 1
    assert report["universe_size_by_cutoff"] == [[CUTOFF, 1]]


def test_unadapted_delayed_eligibility_still_fails_the_exposure_report(graded):
    cohort, _, _ = graded
    raw = [
        dict(
            product_id=row["product_id"],
            direction=row["direction"],
            ts_ms=cohort["cutoff_ts_ms"],
            available_ts_ms=cohort["knowledge_asof_ts_ms"],
            universe_member=True,
            warmup_complete=True,
            health_verified=True,
            candidate_eligible=row["complete_vector_candidate"],
        )
        for row in cohort["rows"]
    ]
    with pytest.raises(ValueError, match="known by its cutoff"):
        directional.exposure_report([], raw, asof_ts_ms=END + 1)


def test_wait_is_inclusive_and_late_cohorts_stay_in_the_denominator(graded):
    cohort, _, _ = graded
    _, on_time = slots_by_key(cohort, 180)  # known exactly at the deadline
    assert on_time[(COIN, "up")]["candidate_eligible"] is True
    slots, late = slots_by_key(cohort, 179)  # one millisecond past it
    assert len(slots) == 4
    for row in slots:
        assert row["ts_ms"] == row["available_ts_ms"] == CUTOFF
        assert row["known_within_allowed_wait"] is False
        assert not row["warmup_complete"] and not row["health_verified"]
        assert row["candidate_eligible"] is False
    assert late[(COIN, "up")]["universe_member"] is True
    assert late[(COIN, "up")]["bridge_reason"] == "known_after_allowed_wait"
    report = directional.exposure_report([], slots, asof_ts_ms=END + 1)
    board = report["boards"]["up"]
    assert board["recorded_slot_count"] == 2
    assert board["decision_eligible_slot_count"] == 0
    assert board["exclusions_by_first_failed_flag"]["warmup_complete"] == 1


def test_unready_and_missing_decisions_are_never_eligible():
    tape = feature_tape()
    early = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=CUTOFF + 1)
    cohort = assess_cohort(tape.rec, CUTOFF, asof=CUTOFF + 1, decisions=[early])
    _, by_key = slots_by_key(cohort, 1500)
    unready, missing = by_key[(COIN, "up")], by_key[(COIN, "down")]
    assert unready["bridge_reason"] == "input_unavailable"  # F2 proof not yet in
    assert unready["warmup_complete"] is True and unready["health_verified"] is False
    assert missing["bridge_reason"] == "decision_missing"
    assert missing["warmup_complete"] is False
    assert not unready["candidate_eligible"] and not missing["candidate_eligible"]
    assert unready["known_at_ts_ms"] == CUTOFF + 1


def test_bridge_leaves_its_input_untouched_and_rejects_bad_cohorts(graded):
    cohort, _, _ = graded
    before = copy.deepcopy(cohort)

    def adapt(*cohorts, wait=180):
        return delayed_eligibility_to_directional_slots(cohorts, allowed_wait_ms=wait)

    adapt(cohort)
    assert cohort == before
    with pytest.raises(ValueError, match="duplicate cohort cutoff"):
        adapt(cohort, cohort)
    with pytest.raises(ValueError, match="nonnegative integer"):
        adapt(cohort, wait=-1)
    with pytest.raises(ValueError, match="nonnegative integer"):
        adapt(cohort, wait=1.5)
    with pytest.raises(ValueError, match="unsupported delayed eligibility version"):
        adapt(dict(cohort, version="other"))
    with pytest.raises(ValueError, match="before its cutoff"):
        adapt(dict(cohort, knowledge_asof_ts_ms=CUTOFF - 1))
    with pytest.raises(ValueError, match="5s grid"):
        adapt(dict(cohort, cutoff_ts_ms=CUTOFF + 1, knowledge_asof_ts_ms=ASOF))
    with pytest.raises(ValueError, match="both directions required"):
        adapt(dict(cohort, rows=cohort["rows"][:1]))
    with pytest.raises(ValueError, match="duplicate delayed eligibility slot"):
        adapt(dict(cohort, rows=cohort["rows"] + cohort["rows"][:1]))
    promoted = [dict(row, complete_vector_candidate=True) for row in cohort["rows"]]
    with pytest.raises(ValueError, match="inconsistent delayed eligibility row"):
        adapt(dict(cohort, rows=promoted))
    relabeled = [dict(row, role="non_benchmark") for row in cohort["rows"]]
    with pytest.raises(ValueError, match="unsupported delayed eligibility row"):
        adapt(dict(cohort, rows=relabeled))


def test_provenance_marks_adapted_rows_as_evaluation_only():
    meta = provenance()
    assert meta["bridge_version"] == "instant-delayed-bridge-v1-draft"
    assert meta["evaluation_only"] is True and meta["fitting_allowed"] is False
    assert meta["live_integration"] is False and meta["study_eligible"] is False
    assert len(meta["adapted_evaluator_sha256"]) == 64
