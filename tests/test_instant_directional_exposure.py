"""Hand-calculated directional denominators and causal eligibility boundaries."""

import copy
import json

import pytest

from test_instant_association import ASOF, B, PRODUCT, label, slot
import instant_association as assoc
import instant_directional_exposure as directional


def eligibility(product=PRODUCT, offset=0, **board_flags):
    return [
        dict(
            slot(product, offset, **board_flags.get(direction, {})),
            direction=direction,
            available_ts_ms=B + offset,
        )
        for direction in assoc.DIRECTIONS
    ]


def report(labels, records=None, **kwargs):
    return directional.exposure_report(
        labels,
        eligibility() if records is None else records,
        asof_ts_ms=kwargs.pop("asof_ts_ms", ASOF),
        **kwargs,
    )


@pytest.mark.parametrize("direction", assoc.DIRECTIONS)
@pytest.mark.parametrize("horizon", assoc.HORIZONS)
@pytest.mark.parametrize("other_status", ["missing", "pending", "unavailable"])
def test_other_direction_missingness_never_removes_a_ready_board_row(
    direction, horizon, other_status
):
    other = "down" if direction == "up" else "up"
    rows = [label(0, direction=direction, horizon=horizon, verified=False)]
    if other_status != "missing":
        rows.append(label(0, direction=other, horizon=horizon, status=other_status))
    out = report(rows)
    own, opposite = out["boards"][direction], out["boards"][other]
    assert own["decision_eligible_slot_count"] == 1
    assert opposite["decision_eligible_slot_count"] == 1
    assert own["horizons"][str(horizon)]["gradable_slot_count"] == 1
    assert opposite["horizons"][str(horizon)]["gradable_slot_count"] == 0
    # The existing joint comparator retains its explicitly stricter definition.
    joint = assoc.exposure_report(rows, [slot(PRODUCT, 0)], asof_ts_ms=ASOF)
    assert joint["horizons"][str(horizon)]["gradable_slot_count"] == 0


def test_product_hours_wall_clock_unions_and_directional_flags_by_hand():
    records = eligibility()
    records += eligibility("B-USD", up={"candidate_eligible": False})
    records += eligibility(offset=5000, down={"warmup_complete": False})
    out = report([], records)
    up, down = out["boards"]["up"], out["boards"]["down"]
    # Up: A@0, A@5. Down: A@0, B@0. Two slots per board.
    assert up["decision_eligible_product_hours"] == pytest.approx(10 / 3600)
    assert down["decision_eligible_product_hours"] == pytest.approx(10 / 3600)
    assert up["board_wall_clock_hours_with_any_eligible_product"] == pytest.approx(
        10 / 3600
    )
    assert down["board_wall_clock_hours_with_any_eligible_product"] == pytest.approx(
        5 / 3600
    )
    assert out["wall_clock_hours_with_either_board_eligible"] == pytest.approx(
        10 / 3600
    )
    assert out["universe_size_by_cutoff"] == [[B, 2], [B + 5000, 1]]
    assert up["exclusions_by_first_failed_flag"]["candidate_eligible"] == 1
    assert down["exclusions_by_first_failed_flag"]["warmup_complete"] == 1
    assert up["horizons"]["300"]["ungradable_reasons"] == {"label_missing": 2}


def test_future_label_changes_do_not_change_decision_exposure():
    before = report([])
    after = report([label(0), label(0, direction="down", verified=False)])
    assert before["universe_size_by_cutoff"] == after["universe_size_by_cutoff"]
    for direction in assoc.DIRECTIONS:
        for key in (
            "recorded_slot_count",
            "decision_eligible_slot_count",
            "decision_eligible_product_hours",
            "board_wall_clock_hours_with_any_eligible_product",
            "exclusions_by_first_failed_flag",
        ):
            assert before["boards"][direction][key] == after["boards"][direction][key]


def test_identical_ranker_rows_keep_direction_and_natural_coverage_separate():
    rows = [label(offset) for offset in (0, 5000)]
    rows += [label(0, direction="down")]
    records = eligibility() + eligibility(offset=5000)
    out = report(
        rows,
        records,
        ranker_slots={
            "A": [(PRODUCT, "up", B), (PRODUCT, "up", B + 5000)],
            "B": [(PRODUCT, "up", B + 5000), (PRODUCT, "down", B)],
        },
    )
    up = out["boards"]["up"]["horizons"]["300"]["comparison"]
    down = out["boards"]["down"]["horizons"]["300"]["comparison"]
    assert up["identical_complete_rows"] == [[PRODUCT, B + 5000]]
    assert down["identical_complete_rows"] == []
    assert up["natural_ranker_coverage"]["A"]["eligible_scored_slot_count"] == 2
    assert up["natural_ranker_coverage"]["B"]["gradable_scored_slot_count"] == 1
    assert down["natural_ranker_coverage"]["B"]["gradable_scored_slot_count"] == 1


def test_maturity_boundary_is_separate_for_each_horizon():
    rows = [label(0), label(0, horizon=900, status="pending")]
    out = report(rows, asof_ts_ms=B + 300_000)
    horizons = out["boards"]["up"]["horizons"]
    assert horizons["300"]["gradable_slot_count"] == 1
    assert horizons["900"]["ungradable_reasons"] == {"immature_trailing_horizon": 1}
    assert out["boards"]["up"]["decision_eligible_slot_count"] == 1


def test_own_direction_unavailable_retains_reason_without_becoming_failure():
    out = report([label(0, status="unavailable", reason="missing_benchmark")])
    h = out["boards"]["up"]["horizons"]["300"]
    assert h["gradable_slot_count"] == 0
    assert h["ungradable_reasons"] == {"unavailable:missing_benchmark": 1}
    assert h["gradable_fraction_of_eligible"] == 0


@pytest.mark.parametrize("available", [B - 1, B])
def test_asserted_eligibility_known_by_cutoff_is_accepted(available):
    records = eligibility()
    records[0]["available_ts_ms"] = available
    assert report([], records)["boards"]["up"]["decision_eligible_slot_count"] == 1


@pytest.mark.parametrize(
    "field,value", [("available_ts_ms", B + 1), ("ts_ms", ASOF + 5000)]
)
def test_future_eligibility_is_rejected_even_if_labels_are_ready(field, value):
    records = eligibility()
    records[0][field] = value
    with pytest.raises(ValueError, match="known by its cutoff"):
        report([label(0)], records)


@pytest.mark.parametrize("flag", assoc.ELIGIBILITY_FLAGS)
@pytest.mark.parametrize("value", [None, 0, "true"])
def test_unknown_and_coerced_boolean_flags_are_rejected(flag, value):
    records = eligibility()
    records[0][flag] = value
    with pytest.raises(ValueError, match="explicit boolean"):
        report([], records)


def test_missing_board_record_is_not_silently_counted_as_excluded():
    with pytest.raises(ValueError, match="both directional"):
        report([], eligibility()[:1])


def test_universe_membership_is_shared_even_when_candidate_flags_differ():
    records = eligibility()
    records[0]["universe_member"] = False
    with pytest.raises(ValueError, match="share the declared decision universe"):
        report([], records)


def test_duplicate_records_and_duplicate_ranker_rows_are_rejected():
    with pytest.raises(ValueError, match="duplicate directional eligibility"):
        report([], eligibility() * 2)
    with pytest.raises(ValueError, match="duplicate directional ranker"):
        report([], ranker_slots={"A": [(PRODUCT, "up", B)] * 2})


def test_rankers_cannot_add_unrecorded_rows():
    with pytest.raises(ValueError, match="recorded eligibility"):
        report([], ranker_slots={"A": [(PRODUCT, "up", B + 5000)]})


@pytest.mark.parametrize(
    "field", ["product_id", "direction", "ts_ms", "available_ts_ms"]
)
def test_missing_identity_or_clock_is_rejected(field):
    records = eligibility()
    del records[0][field]
    with pytest.raises(ValueError, match="identity, clocks"):
        report([], records)


def test_ready_labels_cannot_restore_excluded_slots_and_first_flag_is_reported():
    records = eligibility(
        up={"warmup_complete": False, "candidate_eligible": False},
        down={"health_verified": False},
    )
    out = report([label(0), label(0, direction="down")], records)
    assert out["universe_size_by_cutoff"] == [[B, 1]]
    up, down = out["boards"]["up"], out["boards"]["down"]
    assert up["exclusions_by_first_failed_flag"]["warmup_complete"] == 1
    assert up["exclusions_by_first_failed_flag"]["candidate_eligible"] == 0
    assert down["exclusions_by_first_failed_flag"]["health_verified"] == 1
    for board in (up, down):
        assert board["decision_eligible_slot_count"] == 0
        assert board["horizons"]["300"]["gradable_slot_count"] == 0


@pytest.mark.parametrize(
    "change", ["version", "provenance", "duplicate", "float_horizon"]
)
def test_label_validation_remains_identical_to_the_association_contract(change):
    rows = [label(0), label(0, direction="down")]
    if change == "version":
        rows[0]["contract_version"] = "instant-target-v1"
    elif change == "provenance":
        rows[0]["evaluator_sha256"] = "other"
    elif change == "duplicate":
        rows += [copy.deepcopy(rows[0])]
    else:
        rows[0]["horizon_seconds"] = 300.0
    with pytest.raises(ValueError):
        report(rows)


def test_inputs_are_unchanged_and_report_is_json_serializable():
    rows, records = [label(0)], eligibility()
    frozen = copy.deepcopy((rows, records))
    out = report(rows, records)
    assert (rows, records) == frozen
    json.dumps(out, allow_nan=False)
    assert out["eligibility_producer_implemented"] is False
    assert out["legacy_joint_report_changed"] is False
    assert out["feed_gate_pass"] is False


def test_no_eligible_rows_has_null_graded_fraction_and_zero_exposure():
    out = report([], [])
    assert out["universe_size_by_cutoff"] == []
    assert out["wall_clock_hours_with_either_board_eligible"] == 0
    for board in out["boards"].values():
        assert board["decision_eligible_product_hours"] == 0
        assert board["horizons"]["300"]["gradable_fraction_of_eligible"] is None
