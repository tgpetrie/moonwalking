"""Independent review probes for the opt-in directional exposure report.

Claude review of Codex 9da4987 at tip f561706. Every expected number below is
computed by hand from the directional contract before running the code. The
reporter consumes caller assertions; nothing here authenticates eligibility or
proves the submitted universe is complete, and the probes say so explicitly.
Synthetic only: no market data, outcomes, fitting or live change.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from test_instant_association import ASOF, B, label, slot
import instant_association as assoc
import instant_directional_exposure as directional

ROOT = Path(__file__).resolve().parents[1]
A, Bp, C = "A-USD", "B-USD", "C-USD"
T0, T1, T2, T3 = B, B + 5000, B + 10000, B + 15000
HOUR = 3_600_000


def rec(product, ts, direction, available=None, **flags):
    row = dict(slot(product, ts - B, **flags), direction=direction)
    row["available_ts_ms"] = ts if available is None else available
    return row


def pair(product, ts, up=None, down=None):
    return [
        rec(product, ts, "up", **(up or {})),
        rec(product, ts, "down", **(down or {})),
    ]


def run(labels, records, asof=ASOF, **kw):
    return directional.exposure_report(labels, records, asof_ts_ms=asof, **kw)


def lab(product, ts, direction, horizon=300, **kw):
    return label(ts - B, product=product, direction=direction, horizon=horizon, **kw)


# --- Hand-built universe: three products, four cutoffs, both boards -------
# Up eligible:   A@T0, A@T1, B@T1, C@T3            -> 4 slots, cutoffs {T0,T1,T3}
# Down eligible: B@T0, B@T2, C@T2                  -> 3 slots, cutoffs {T0,T2}
# Either board:  {T0,T1,T2,T3}                     -> 4 cutoffs, not 3 + 2 = 5
# C@T0 is outside the universe on both boards.
OFF = {"candidate_eligible": False}
WARM = {"warmup_complete": False}
SICK = {"health_verified": False}
OUT = {"universe_member": False}


def universe():
    return (
        pair(A, T0, down=OFF)
        + pair(Bp, T0, up=WARM)
        + pair(C, T0, up=OUT, down=OUT)
        + pair(A, T1, down=SICK)
        + pair(Bp, T1, down=SICK)
        + pair(C, T1, up=SICK, down=SICK)
        + pair(A, T2, up=OFF, down=WARM)
        + pair(Bp, T2, up=OFF)
        + pair(C, T2, up=OFF)
        + pair(A, T3, up=WARM, down=OFF)
        + pair(Bp, T3, up=WARM, down=OFF)
        + pair(C, T3, down=OFF)
    )


def labels_300_900():
    return [
        lab(A, T0, "up"),  # ready success
        lab(A, T1, "up", verified=False),  # ready failure, still gradable
        lab(Bp, T1, "up", status="pending"),
        # C@T3 up: missing on purpose.
        lab(A, T0, "up", horizon=900),
        lab(A, T1, "up", horizon=900, status="unavailable", reason="x"),
        lab(Bp, T0, "down", verified=False),
        lab(Bp, T2, "down"),
        lab(C, T2, "down", status="pending"),
    ]


def test_hand_oracle_product_hours_board_unions_and_either_board_union():
    out = run([], universe())
    up, down = out["boards"]["up"], out["boards"]["down"]
    assert up["recorded_slot_count"] == down["recorded_slot_count"] == 12
    assert up["decision_eligible_slot_count"] == 4
    assert down["decision_eligible_slot_count"] == 3
    assert up["decision_eligible_product_hours"] == pytest.approx(20000 / HOUR)
    assert down["decision_eligible_product_hours"] == pytest.approx(15000 / HOUR)
    assert up["board_wall_clock_hours_with_any_eligible_product"] == pytest.approx(
        15000 / HOUR
    )
    assert down["board_wall_clock_hours_with_any_eligible_product"] == pytest.approx(
        10000 / HOUR
    )
    either = out["wall_clock_hours_with_either_board_eligible"]
    assert either == pytest.approx(20000 / HOUR)
    assert either < (15000 + 10000) / HOUR  # A union, never a sum.
    assert out["universe_size_by_cutoff"] == [[T0, 2], [T1, 3], [T2, 3], [T3, 3]]
    assert up["exclusions_by_first_failed_flag"] == dict(
        universe_member=1, warmup_complete=3, health_verified=1, candidate_eligible=3
    )
    assert down["exclusions_by_first_failed_flag"] == dict(
        universe_member=1, warmup_complete=1, health_verified=3, candidate_eligible=4
    )


def test_hand_oracle_ranker_complete_row_intersections_per_board_and_horizon():
    rankers = {
        "R1": [
            (A, "up", T0),
            (A, "up", T1),
            (Bp, "up", T1),
            (C, "up", T3),
            (Bp, "down", T0),
        ],
        "R2": [
            (A, "up", T1),
            (C, "up", T3),
            (Bp, "up", T0),
            (Bp, "down", T0),
            (Bp, "down", T2),
            (C, "down", T2),
        ],
        "R3": [(A, "up", T0), (A, "up", T1)],
    }
    out = run(labels_300_900(), universe(), ranker_slots=rankers)
    up, down = out["boards"]["up"]["horizons"], out["boards"]["down"]["horizons"]
    # Up board gradable: 300s {A@T0, A@T1}; 900s {A@T0}.
    assert up["300"]["gradable_slot_count"] == 2
    assert up["300"]["ungradable_reasons"] == {
        "label_missing": 1,
        "pending:no_reason": 1,
    }
    assert up["900"]["gradable_slot_count"] == 1
    assert up["900"]["ungradable_reasons"] == {"label_missing": 2, "unavailable:x": 1}
    # Shared up rows R1 ∩ R2 ∩ R3 = {A@T1}.
    assert up["300"]["comparison"]["identical_complete_rows"] == [[A, T1]]
    assert up["900"]["comparison"]["identical_complete_rows"] == []
    cov = up["300"]["comparison"]["natural_ranker_coverage"]
    assert cov["R1"] == dict(eligible_scored_slot_count=4, gradable_scored_slot_count=2)
    assert cov["R2"] == dict(eligible_scored_slot_count=2, gradable_scored_slot_count=1)
    assert cov["R3"] == dict(eligible_scored_slot_count=2, gradable_scored_slot_count=2)
    # Down board: R3 scored nothing there, so no row is scored by every ranker.
    assert down["300"]["gradable_slot_count"] == 2
    assert down["300"]["comparison"]["identical_complete_row_count"] == 0
    dcov = down["300"]["comparison"]["natural_ranker_coverage"]
    assert dcov["R1"] == dict(
        eligible_scored_slot_count=1, gradable_scored_slot_count=1
    )
    assert dcov["R2"] == dict(
        eligible_scored_slot_count=3, gradable_scored_slot_count=2
    )
    assert dcov["R3"] == dict(
        eligible_scored_slot_count=0, gradable_scored_slot_count=0
    )


def test_without_rankers_the_complete_row_table_is_every_gradable_row():
    out = run(labels_300_900(), universe())
    rows = out["boards"]["up"]["horizons"]["300"]["comparison"][
        "identical_complete_rows"
    ]
    assert rows == [[A, T0], [A, T1]]
    empty = run(labels_300_900(), universe(), ranker_slots={"Z": []})
    for board in empty["boards"].values():
        for h in board["horizons"].values():
            assert h["comparison"]["identical_complete_row_count"] == 0


# --- Own-direction gradability --------------------------------------------


@pytest.mark.parametrize("other_board", [{}, OFF, OUT])
def test_opposite_board_state_or_missing_label_never_removes_a_ready_row(other_board):
    records = (
        pair(A, T0, down=other_board)
        if other_board is not OUT
        else pair(A, T0, up=OUT, down=OUT)
    )
    out = run([lab(A, T0, "up", verified=False)], records)
    up = out["boards"]["up"]
    expected = 0 if other_board is OUT else 1
    assert up["decision_eligible_slot_count"] == expected
    assert up["horizons"]["300"]["gradable_slot_count"] == expected
    # The legacy joint report still demands both direction labels.
    joint = assoc.exposure_report(
        [lab(A, T0, "up", verified=False)], [slot(A, 0)], asof_ts_ms=ASOF
    )
    assert joint["horizons"]["300"]["gradable_slot_count"] == 0


def test_both_boards_graded_independently_with_opposite_outcomes():
    out = run([lab(A, T0, "up"), lab(A, T0, "down", verified=False)], pair(A, T0))
    for direction in assoc.DIRECTIONS:
        assert out["boards"][direction]["horizons"]["300"]["gradable_slot_count"] == 1


def test_report_exposes_no_outcome_counts_so_unavailable_cannot_become_negative():
    out = run(
        [
            lab(A, T0, "up", status="unavailable", reason="missing_benchmark"),
            lab(A, T0, "down", verified=False),
        ],
        pair(A, T0),
    )
    text = json.dumps(out)
    for word in ("success", "failure", "negative", "verified_forward"):
        assert word not in text
    assert out["boards"]["up"]["horizons"]["300"]["ungradable_reasons"] == {
        "unavailable:missing_benchmark": 1
    }
    assert out["boards"]["down"]["horizons"]["300"]["gradable_slot_count"] == 1


def test_exposure_is_identical_with_no_labels_and_with_every_label_ready():
    full = []
    for product in (A, Bp, C):
        for ts in (T0, T1, T2, T3):
            for direction in assoc.DIRECTIONS:
                for horizon in assoc.HORIZONS:
                    full.append(
                        lab(product, ts, direction, horizon, verified=(ts == T0))
                    )
    before, after = run([], universe()), run(full, universe())
    strip = lambda board: {k: v for k, v in board.items() if k != "horizons"}
    for direction in assoc.DIRECTIONS:
        assert strip(before["boards"][direction]) == strip(after["boards"][direction])
    for key in (
        "universe_size_by_cutoff",
        "wall_clock_hours_with_either_board_eligible",
    ):
        assert before[key] == after[key]


# --- Horizon maturity boundaries ------------------------------------------


@pytest.mark.parametrize(
    "asof,mature300,mature900",
    [
        (T0 + 299_999, False, False),
        (T0 + 300_000, True, False),
        (T0 + 899_999, True, False),
        (T0 + 900_000, True, True),
    ],
)
def test_each_horizon_matures_exactly_at_anchor_plus_horizon(
    asof, mature300, mature900
):
    rows = [lab(A, T0, "up", h, status="pending") for h in assoc.HORIZONS]
    out = run(rows, pair(A, T0), asof=asof)
    horizons = out["boards"]["up"]["horizons"]
    for h, mature in (("300", mature300), ("900", mature900)):
        reason = "pending:no_reason" if mature else "immature_trailing_horizon"
        assert horizons[h]["ungradable_reasons"] == {reason: 1}
    assert out["boards"]["up"]["decision_eligible_slot_count"] == 1


# --- Clocks, pairing, duplicates, malformed inputs --------------------------


@pytest.mark.parametrize("asof", [True, 1.0, -1, "1", None])
def test_report_asof_must_be_a_nonnegative_integer(asof):
    with pytest.raises(ValueError):
        run([], pair(A, T0), asof=asof)


@pytest.mark.parametrize("available", [True, 1.0, -1, "0", None, T0 + 1])
def test_available_clock_must_be_an_integer_no_later_than_its_cutoff(available):
    records = pair(A, T0)
    records[0]["available_ts_ms"] = available
    with pytest.raises(ValueError):
        run([], records)


def test_cutoff_may_equal_asof_and_availability_may_equal_cutoff():
    records = pair(A, ASOF)
    for r in records:
        r["available_ts_ms"] = ASOF
    out = run([], records)
    assert out["boards"]["up"]["decision_eligible_slot_count"] == 1
    assert out["boards"]["up"]["horizons"]["300"]["ungradable_reasons"] == {
        "immature_trailing_horizon": 1
    }


@pytest.mark.parametrize("ts", [T0 + 1, T0 - 1, True, 5000.0])
def test_off_grid_or_nonint_cutoffs_are_rejected(ts):
    records = pair(A, T0)
    records[0]["ts_ms"] = ts
    with pytest.raises(ValueError):
        run([], records)


def test_pairing_is_per_cutoff_not_per_product():
    records = pair(A, T0) + [rec(A, T1, "up")]
    with pytest.raises(ValueError, match="both directional"):
        run([], records)


@pytest.mark.parametrize("flag", assoc.ELIGIBILITY_FLAGS)
def test_missing_or_integer_flags_are_rejected(flag):
    records = pair(A, T0)
    del records[1][flag]
    with pytest.raises(ValueError, match="explicit boolean"):
        run([], records)
    records = pair(A, T0)
    records[1][flag] = 1
    with pytest.raises(ValueError, match="explicit boolean"):
        run([], records)


@pytest.mark.parametrize("direction", ["UP", "both", None, 1])
def test_unknown_directions_are_rejected(direction):
    records = pair(A, T0)
    records[0]["direction"] = direction
    with pytest.raises(ValueError):
        run([], records)


def test_duplicate_ranker_slots_as_list_and_tuple_are_still_duplicates():
    with pytest.raises(ValueError, match="duplicate directional ranker"):
        run([], pair(A, T0), ranker_slots={"R": [(A, "up", T0), [A, "up", T0]]})


@pytest.mark.parametrize(
    "bad", [(A, "up"), (A, "up", T0, 1), {"product_id": A}, "A-USD"]
)
def test_malformed_ranker_slot_shapes_are_rejected(bad):
    # Shape errors surface as TypeError or ValueError; neither is a false pass.
    with pytest.raises((ValueError, TypeError)):
        run([], pair(A, T0), ranker_slots={"R": [bad]})


def test_ranker_may_score_an_ineligible_recorded_slot_without_adding_exposure():
    out = run(
        [lab(A, T0, "up")], pair(A, T0, up=OFF), ranker_slots={"R": [(A, "up", T0)]}
    )
    up = out["boards"]["up"]
    assert up["decision_eligible_slot_count"] == 0
    cov = up["horizons"]["300"]["comparison"]["natural_ranker_coverage"]["R"]
    assert cov == dict(eligible_scored_slot_count=0, gradable_scored_slot_count=0)


def test_mixed_label_provenance_is_rejected_even_for_an_irrelevant_slot():
    rows = [lab(A, T0, "up"), lab(C, T3, "down", status="pending")]
    rows[1]["contract_sha256"] = "other-contract"
    with pytest.raises(ValueError, match="provenance"):
        run(rows, pair(A, T0))
    rows[1]["contract_sha256"] = rows[0]["contract_sha256"]
    rows[1]["evaluator_sha256"] = "other-evaluator"
    with pytest.raises(ValueError, match="provenance"):
        run(rows, pair(A, T0))


def test_inputs_including_rankers_are_not_mutated():
    rows, records = labels_300_900(), universe()
    rankers = {"R": [(A, "up", T0), [A, "down", T0]]}
    frozen = copy.deepcopy((rows, records, rankers))
    run(rows, records, ranker_slots=rankers)
    assert (rows, records, rankers) == frozen


def test_empty_everything_is_a_valid_zero_report():
    out = run([], [], asof=0, ranker_slots={})
    assert out["universe_size_by_cutoff"] == []
    for board in out["boards"].values():
        assert board["recorded_slot_count"] == 0
        for h in board["horizons"].values():
            assert h["gradable_fraction_of_eligible"] is None
            assert h["comparison"]["identical_complete_rows"] == []


# --- Legacy reporter and provenance ---------------------------------------


def test_directional_report_embeds_the_unchanged_association_provenance():
    out = run([lab(A, T0, "up")], pair(A, T0))
    assert out["association_dependency"] == assoc.provenance()
    src = (
        ROOT / "scripts/scoring_experiment/instant_directional_exposure.py"
    ).read_text("utf-8")
    con = (
        ROOT / "docs/research/INSTANT_DIRECTIONAL_EXPOSURE_CONTRACT_V1_DRAFT.json"
    ).read_text("utf-8")
    assert out["implementation_sha256"] == hashlib.sha256(src.encode()).hexdigest()
    assert out["contract_sha256"] == hashlib.sha256(con.encode()).hexdigest()
    assert out["target_contract_sha256"] == "contract"
    assert out["opposite_direction_label_required"] is False
    assert out["legacy_joint_report_changed"] is False


def test_legacy_joint_reporter_output_shape_is_untouched():
    joint = assoc.exposure_report([], [slot(A, 0)], asof_ts_ms=ASOF)
    assert (
        "boards" not in joint
        and "board_wall_clock_hours_with_any_verified_health" in joint
    )
    assert joint["horizons"]["300"]["comparison"][
        "identical_complete_rows_definition"
    ] == ("decision_eligible_and_gradable_and_scored_by_every_ranker")


# --- The limitation, stated as executable facts ---------------------------


def test_reporter_accepts_unverifiable_assertions_and_says_so():
    """It records caller claims; it cannot authenticate them."""
    records = pair(A, T0)
    for r in records:
        r["available_ts_ms"] = 0  # Claims eligibility was known an hour early.
    out = run([], records)
    assert out["boards"]["up"]["decision_eligible_slot_count"] == 1
    assert (
        out["eligibility_source"] == "caller_assertions_not_authenticated_feed_evidence"
    )
    assert out["eligibility_producer_implemented"] is False


def test_reporter_cannot_see_a_product_omitted_from_both_boards():
    out = run([], pair(A, T0) + pair(Bp, T0))
    assert out["universe_size_by_cutoff"] == [[T0, 2]]  # C is simply absent.
    assert out["boards"]["up"]["recorded_slot_count"] == 2
    cfg = json.loads(directional.CONTRACT.read_text(encoding="utf-8"))
    assert cfg["universe_completeness"].startswith("not_authenticated")
