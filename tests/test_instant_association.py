"""Association/exposure reporting probes: synthetic only, no fitting or live code."""

import copy
import json
import sys

import pytest

from test_instant_targets import ROOT, target

sys.path.insert(0, str(ROOT / "scripts/scoring_experiment"))
import instant_association as assoc
import reproduce_instant_study_choices as repro


B = 3_600_000  # Base cutoff; hand oracles use offsets from here in ms.
PRODUCT = "A-USD"


def label(
    offset,
    *,
    verified=True,
    status="ready",
    product=PRODUCT,
    direction="up",
    horizon=300,
    peak=60_000,
    reason=None,
):
    anchor = B + offset
    ready = status == "ready"
    return dict(
        contract_version="instant-target-v2-draft",
        contract_sha256="contract",
        evaluator_sha256="evaluator",
        product_id=product,
        anchor_ts_ms=anchor,
        direction=direction,
        horizon_seconds=horizon,
        status=status,
        reason=reason,
        verified_forward=verified if ready else None,
        label_maturity_ts_ms=anchor + horizon * 1000,
        peak_ts_ms=anchor + peak if ready else None,
    )


def alert(pid, published, *, anchor=None, inputs=None, product=PRODUCT, direction="up"):
    anchor = B + (published if anchor is None else anchor)
    return dict(
        publication_id=pid,
        product_id=product,
        direction=direction,
        anchor_ts_ms=anchor,
        inputs_available_ts_ms=anchor if inputs is None else B + inputs,
        published_ts_ms=B + published,
    )


def synthetic_alert(pid, anchor, published=None):
    """Absolute clocks for labels graded by the real v2 evaluator."""
    published = anchor if published is None else published
    return dict(
        publication_id=pid,
        product_id="SYNTHETIC-USD",
        direction="up",
        anchor_ts_ms=anchor,
        inputs_available_ts_ms=anchor,
        published_ts_ms=published,
    )


def slot(product, offset, **flags):
    base = dict(
        universe_member=True,
        warmup_complete=True,
        health_verified=True,
        candidate_eligible=True,
    )
    return dict(product_id=product, ts_ms=B + offset, **{**base, **flags})


ASOF = B + 3_000_000


def oracle_labels(direction, horizon):
    """Three verified windows spaced one horizon apart, with censor context."""
    h = horizon * 1000
    return [
        label(0, direction=direction, horizon=horizon),
        label(h - 5000, verified=False, direction=direction, horizon=horizon),
        label(h, direction=direction, horizon=horizon),
        label(
            2 * h - 5000,
            status="unavailable",
            reason="missing_grid_point",
            direction=direction,
            horizon=horizon,
        ),
        label(2 * h, direction=direction, horizon=horizon),
    ]


def oracle_alerts(direction, horizon):
    h = horizon * 1000
    return [
        alert("too_early", -185_000, anchor=-185_000, direction=direction),
        alert("edge", -180_000, anchor=-180_000, direction=direction),
        alert("between", 10_000, direction=direction),
        alert("tie_b", h + 60_000, direction=direction),
        alert("tie_a", h + 60_000, direction=direction),
    ]


# 1. Hand-calculated matching oracle across both directions and horizons ----------


@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize("horizon", [300, 900])
def test_matching_oracle_by_hand(direction, horizon):
    out = assoc.association_report(
        oracle_labels(direction, horizon),
        oracle_alerts(direction, horizon),
        asof_ts_ms=ASOF,
    )
    table = out["horizons"][str(horizon)]["forward_window_coverage"]
    h = horizon * 1000
    assert table["window_count"] == 3
    assert [
        (w["anchor_ts_ms"] - B, w["covering_publication_id"])
        for w in table["covered_windows"]
    ] == [
        (0, "edge"),
        (h, "tie_a"),
    ]
    assert [w["anchor_ts_ms"] - B for w in table["uncovered_windows"]] == [2 * h]
    assert table["uncovered_forward_window_rate"] == pytest.approx(1 / 3)
    assert table["conditional_catalog_coverage_rate"] == pytest.approx(2 / 3)
    assert table["alerts_without_forward_window"] == ["too_early", "between", "tie_b"]
    assert table["physical_missed_move_rate"] is None
    censored = {
        w["anchor_ts_ms"] - B: w["left_censor_reason"]
        for w in table["covered_windows"] + table["uncovered_windows"]
    }
    assert censored == {0: "previous_anchor_missing", h: None, 2 * h: "unavailable"}
    assert table["left_censored_window_count"] == 2
    other = out["horizons"][str(900 if horizon == 300 else 300)]
    assert other["forward_window_coverage"]["window_count"] == 0
    assert other["forward_window_coverage"]["uncovered_forward_window_rate"] is None
    assert out["physical_onset_defined"] is False
    assert out["operational_missed_move_rates_enabled"] is False
    json.dumps(out, allow_nan=False)


def test_identical_timestamps_are_ordered_by_publication_id_only():
    swapped = [
        {
            **a,
            "publication_id": {"tie_a": "tie_b", "tie_b": "tie_a"}.get(
                a["publication_id"], a["publication_id"]
            ),
        }
        for a in oracle_alerts("up", 300)
    ]
    out = assoc.association_report(oracle_labels("up", 300), swapped, asof_ts_ms=ASOF)
    covered = out["horizons"]["300"]["forward_window_coverage"]["covered_windows"]
    assert covered[1]["covering_publication_id"] == "tie_a"


def test_one_alert_covers_at_most_one_window_per_horizon_but_both_horizons():
    labels = [
        label(0, peak=200_000),
        label(300_000),
        label(0, horizon=900, peak=200_000),
    ]
    out = assoc.association_report(labels, [alert("only", 150_000)], asof_ts_ms=ASOF)
    five = out["horizons"]["300"]["forward_window_coverage"]
    assert [w["covering_publication_id"] for w in five["covered_windows"]] == ["only"]
    assert [w["anchor_ts_ms"] - B for w in five["uncovered_windows"]] == [300_000]
    fifteen = out["horizons"]["900"]["forward_window_coverage"]
    assert [w["covering_publication_id"] for w in fifteen["covered_windows"]] == [
        "only"
    ]
    assert fifteen["uncovered_count"] == 0


def test_empty_inputs_keep_denominators_explicit():
    out = assoc.report([], [], [], asof_ts_ms=ASOF)
    for horizon in ("300", "900"):
        primary = out["association"]["horizons"][horizon]["primary_pointwise"]
        coverage = out["association"]["horizons"][horizon]["forward_window_coverage"]
        assert primary["alert_count"] == 0 and primary["graded_fraction"] is None
        assert primary["success_rate_among_graded"] is None
        assert coverage["uncovered_forward_window_rate"] is None
        assert (
            out["exposure"]["horizons"][horizon]["gradable_fraction_of_eligible"]
            is None
        )
    assert out["exposure"]["decision_eligible_product_hours"] == 0
    assert out["exposure"]["universe_size_first"] is None
    assert out["association"]["target_contract_sha256"] is None


def test_absent_pending_and_unavailable_labels_stay_ungradable_and_visible():
    labels = [
        label(0),
        label(5000, status="pending", reason="horizon_not_mature"),
        label(10_000, status="unavailable", reason="unverified_coverage"),
        label(15_000, verified=False),
    ]
    alerts = [alert(f"p{i}", i * 5000) for i in range(5)]
    primary = assoc.association_report(labels, alerts, asof_ts_ms=ASOF)["horizons"][
        "300"
    ]["primary_pointwise"]
    assert (
        primary["success_count"],
        primary["failure_count"],
        primary["ungradable_count"],
    ) == (1, 1, 3)
    assert primary["ungradable_reasons"] == {
        "label_missing": 1,
        "pending:horizon_not_mature": 1,
        "unavailable:unverified_coverage": 1,
    }
    assert primary["graded_fraction"] == pytest.approx(2 / 5)
    assert primary["success_rate_among_graded"] == pytest.approx(1 / 2)
    assert [row["verified_forward"] for row in primary["outcomes"]] == [
        True,
        None,
        None,
        False,
        None,
    ]


# 2. Association never forgives a failed pointwise prediction -----------------------


def grade_labels(engine, offsets, horizon):
    return [repro.grade(engine, offset, horizon) for offset in offsets]


@pytest.mark.parametrize("horizon,impulse_start", [(300, 340), (900, 940)])
def test_later_move_is_covered_but_the_alert_stays_a_pointwise_failure(
    horizon, impulse_start
):
    engine = repro.engine(
        lambda seconds: 0.022 * min(max((seconds - impulse_start) / 30, 0), 1)
    )
    labels = grade_labels(engine, range(0, 121, 5), horizon)
    out = assoc.association_report(
        labels,
        [synthetic_alert("radar", repro.ANCHOR)],
        asof_ts_ms=repro.ANCHOR + 2_000_000,
    )
    table = out["horizons"][str(horizon)]
    (row,) = table["primary_pointwise"]["outcomes"]
    assert row["primary_outcome"] == "failure" and row["verified_forward"] is False
    assert table["forward_window_coverage"]["covered_count"] == 1
    assert row["covers_forward_window_anchor_ts_ms"] > repro.ANCHOR
    assert out["failed_alerts_that_cover_a_forward_window"] == 1
    assert table["primary_pointwise"]["failure_count"] == 1
    assert table["primary_pointwise"]["success_count"] == 0


def test_publication_at_a_completed_window_endpoint_is_still_a_failure():
    engine = repro.engine(
        lambda seconds: 0.002 + 0.02 * min(seconds / 300, 1) if seconds >= 0 else 0
    )
    labels = grade_labels(engine, range(0, 301, 5), 300)
    out = assoc.association_report(
        labels,
        [synthetic_alert("endpoint", repro.ANCHOR + 300_000)],
        asof_ts_ms=repro.ANCHOR + 2_000_000,
    )
    table = out["horizons"]["300"]
    (row,) = table["primary_pointwise"]["outcomes"]
    (window,) = table["forward_window_coverage"]["covered_windows"]
    assert window["anchor_ts_ms"] == repro.ANCHOR
    assert (
        window["forward_peak_ts_ms"] == repro.ANCHOR + 300_000 == row["published_ts_ms"]
    )
    assert row["primary_outcome"] == "failure"
    assert out["failed_alerts_that_cover_a_forward_window"] == 1


def test_real_v2_labels_round_trip_with_provenance():
    engine = repro.engine(lambda seconds: 0.002 + 0.02 * min(max(seconds / 300, 0), 1))
    labels = grade_labels(engine, range(0, 61, 5), 300)
    out = assoc.association_report(
        labels,
        [synthetic_alert("own", repro.ANCHOR)],
        asof_ts_ms=repro.ANCHOR + 1_000_000,
    )
    assert out["target_contract_sha256"] == engine.contract_sha256
    assert out["target_evaluator_sha256"] == engine.implementation_sha256
    primary = out["horizons"]["300"]["primary_pointwise"]
    assert primary["success_count"] == 1
    assert out["horizons"]["300"]["forward_window_coverage"]["covered_count"] == 1


# 3. Clocks and provenance are validated, never coerced -------------------------------


@pytest.mark.parametrize(
    "edit",
    [
        lambda a: {**a, "inputs_available_ts_ms": a["anchor_ts_ms"] - 5000},
        lambda a: {**a, "published_ts_ms": a["inputs_available_ts_ms"] - 1},
        lambda a: {**a, "published_ts_ms": ASOF + 1},
        lambda a: {**a, "anchor_ts_ms": a["anchor_ts_ms"] + 1},
        lambda a: {**a, "direction": "sideways"},
        lambda a: {**a, "publication_id": ""},
        lambda a: {**a, "published_ts_ms": True},
        lambda a: {k: v for k, v in a.items() if k != "inputs_available_ts_ms"},
    ],
)
def test_malformed_or_non_causal_alerts_are_rejected(edit):
    with pytest.raises(ValueError):
        assoc.association_report([label(0)], [edit(alert("x", 0))], asof_ts_ms=ASOF)


def test_duplicate_publication_identity_is_rejected():
    with pytest.raises(ValueError, match="duplicate publication"):
        assoc.association_report([], [alert("x", 0), alert("x", 5000)], asof_ts_ms=ASOF)


def test_late_inputs_are_retained_not_backdated():
    out = assoc.association_report(
        [label(0)], [alert("late", 7000, anchor=0, inputs=6000)], asof_ts_ms=ASOF
    )
    (row,) = out["horizons"]["300"]["primary_pointwise"]["outcomes"]
    assert row["anchor_ts_ms"] == B and row["inputs_available_ts_ms"] == B + 6000
    assert row["published_ts_ms"] == B + 7000
    assert (row["input_lag_ms"], row["publication_delay_ms"]) == (6000, 7000)
    assert row["inputs_known_at_anchor"] is False
    assert row["primary_outcome"] == "success"  # graded at the declared cutoff anchor


@pytest.mark.parametrize(
    "edit",
    [
        lambda l: {**l, "contract_version": "instant-target-v1"},
        lambda l: {**l, "verified_forward": None},
        lambda l: {**l, "verified_forward": 1},
        lambda l: {**l, "status": "pending", "verified_forward": False},
        lambda l: {**l, "status": "done"},
        lambda l: {**l, "label_maturity_ts_ms": l["anchor_ts_ms"] + 1000},
        lambda l: {**l, "peak_ts_ms": l["label_maturity_ts_ms"] + 5000},
        lambda l: {**l, "peak_ts_ms": None},
        lambda l: {
            **l,
            "anchor_ts_ms": l["anchor_ts_ms"] + 1,
            "label_maturity_ts_ms": l["label_maturity_ts_ms"] + 1,
        },
        lambda l: {
            **l,
            "horizon_seconds": 600,
            "label_maturity_ts_ms": l["anchor_ts_ms"] + 600_000,
        },
        lambda l: {**l, "product_id": ""},
        lambda l: {k: v for k, v in l.items() if k != "evaluator_sha256"},
    ],
)
def test_malformed_labels_are_rejected(edit):
    with pytest.raises(ValueError):
        assoc.association_report([edit(label(0))], [], asof_ts_ms=ASOF)


def test_mixed_provenance_and_duplicate_labels_are_rejected():
    with pytest.raises(ValueError, match="mix"):
        assoc.association_report(
            [label(0), {**label(5000), "evaluator_sha256": "other"}],
            [],
            asof_ts_ms=ASOF,
        )
    with pytest.raises(ValueError, match="mix"):
        assoc.association_report(
            [label(0), {**label(5000), "contract_sha256": "other"}], [], asof_ts_ms=ASOF
        )
    with pytest.raises(ValueError, match="duplicate label"):
        assoc.association_report(
            [label(0), label(0, verified=False)], [], asof_ts_ms=ASOF
        )


def test_ready_label_cannot_mature_after_asof():
    with pytest.raises(ValueError, match="as-of"):
        assoc.association_report([label(0)], [], asof_ts_ms=B + 299_999)


def test_inputs_are_not_mutated():
    labels, alerts = oracle_labels("up", 300), oracle_alerts("up", 300)
    before = copy.deepcopy((labels, alerts))
    assoc.association_report(labels, alerts, asof_ts_ms=ASOF)
    assert (labels, alerts) == before


# 4. Exposure oracle by hand -----------------------------------------------------------


def oracle_slots():
    return [
        slot(PRODUCT, 0),
        slot(PRODUCT, 5000),
        slot(PRODUCT, 10_000, health_verified=False),
        slot("B-USD", 0, universe_member=False),
        slot("B-USD", 5000),
        slot("B-USD", 10_000, warmup_complete=False, candidate_eligible=False),
    ]


def oracle_exposure_labels():
    return [
        label(0, direction="up"),
        label(0, direction="down", verified=False),
        label(5000, direction="up"),  # A-USD at 5000 lacks a down label.
        label(5000, direction="up", product="B-USD"),
        label(
            5000,
            direction="down",
            product="B-USD",
            status="unavailable",
            reason="stale_or_future_quote",
        ),
    ]


def test_exposure_oracle_by_hand():
    out = assoc.exposure_report(
        oracle_exposure_labels(),
        oracle_slots(),
        asof_ts_ms=ASOF,
        ranker_slots={
            "r1": [
                (PRODUCT, B),
                (PRODUCT, B + 5000),
                ("B-USD", B + 5000),
                ("B-USD", B),
            ],
            "r2": [(PRODUCT, B), ("B-USD", B + 5000)],
        },
    )
    hour = 5 / 3600
    assert out["recorded_slot_count"] == 6
    assert out["decision_eligible_slot_count"] == 3
    assert out["decision_eligible_product_hours"] == pytest.approx(3 * hour)
    assert out["board_wall_clock_hours_with_any_eligible_product"] == pytest.approx(
        2 * hour
    )
    assert out["board_wall_clock_hours_with_any_verified_health"] == pytest.approx(
        3 * hour
    )
    assert out["exclusions_by_first_failed_flag"] == {
        "universe_member": 1,
        "warmup_complete": 1,
        "health_verified": 1,
        "candidate_eligible": 0,
    }
    assert out["universe_size_by_cutoff"] == [[B, 1], [B + 5000, 2], [B + 10_000, 2]]
    five = out["horizons"]["300"]
    assert five["gradable_slot_count"] == 1
    assert five["gradable_product_hours"] == pytest.approx(hour)
    assert five["ungradable_reasons"] == {
        "label_missing:down": 1,
        "unavailable:down:stale_or_future_quote": 1,
    }
    assert five["gradable_fraction_of_eligible"] == pytest.approx(1 / 3)
    assert five["comparison"]["identical_complete_row_count"] == 1
    assert five["comparison"]["natural_ranker_coverage"] == {
        "r1": dict(eligible_scored_slot_count=3, gradable_scored_slot_count=1),
        "r2": dict(eligible_scored_slot_count=2, gradable_scored_slot_count=1),
    }
    fifteen = out["horizons"]["900"]
    assert fifteen["gradable_slot_count"] == 0
    assert fifteen["ungradable_reasons"] == {"label_missing:up": 3}


def test_missing_future_data_does_not_erase_the_decision_universe():
    with_labels = assoc.exposure_report(
        oracle_exposure_labels(), oracle_slots(), asof_ts_ms=ASOF
    )
    without = assoc.exposure_report([], oracle_slots(), asof_ts_ms=ASOF)
    for key in (
        "decision_eligible_slot_count",
        "decision_eligible_product_hours",
        "board_wall_clock_hours_with_any_eligible_product",
        "universe_size_by_cutoff",
        "exclusions_by_first_failed_flag",
    ):
        assert with_labels[key] == without[key]
    assert without["horizons"]["300"]["gradable_slot_count"] == 0
    assert without["horizons"]["300"]["ungradable_reasons"] == {"label_missing:up": 3}


def test_immature_trailing_horizon_is_visible_not_graded():
    asof = B + 5000 + 300_000  # Slot at 5000 matures exactly now at 5m; 15m does not.
    out = assoc.exposure_report(
        [label(0, direction=d) for d in ("up", "down")]
        + [label(5000, direction=d) for d in ("up", "down")],
        [slot(PRODUCT, 0), slot(PRODUCT, 5000)],
        asof_ts_ms=asof,
    )
    assert out["horizons"]["300"]["gradable_slot_count"] == 2
    assert out["horizons"]["900"]["ungradable_reasons"] == {
        "immature_trailing_horizon": 2
    }
    assert out["decision_eligible_slot_count"] == 2


def test_shrinking_universe_stays_visible():
    slots = [
        slot(p, t, universe_member=(t == 0 or p == PRODUCT))
        for p in (PRODUCT, "B-USD", "C-USD")
        for t in (0, 5000, 10_000)
    ]
    out = assoc.exposure_report([], slots, asof_ts_ms=ASOF)
    assert [size for _, size in out["universe_size_by_cutoff"]] == [3, 1, 1]
    assert (out["universe_size_first"], out["universe_size_last"]) == (3, 1)
    assert out["exclusions_by_first_failed_flag"]["universe_member"] == 4


@pytest.mark.parametrize(
    "edit",
    [
        lambda s: {**s, "health_verified": None},
        lambda s: {**s, "warmup_complete": 1},
        lambda s: {k: v for k, v in s.items() if k != "candidate_eligible"},
        lambda s: {**s, "ts_ms": s["ts_ms"] + 1},
        lambda s: {**s, "ts_ms": ASOF + 5000},
        lambda s: {**s, "product_id": ""},
    ],
)
def test_malformed_eligibility_is_rejected_never_coerced(edit):
    with pytest.raises(ValueError):
        assoc.exposure_report([], [edit(slot(PRODUCT, 0))], asof_ts_ms=ASOF)


def test_duplicate_slots_and_unknown_ranker_slots_are_rejected():
    with pytest.raises(ValueError, match="duplicate or overlapping"):
        assoc.exposure_report(
            [],
            [slot(PRODUCT, 0), slot(PRODUCT, 0, health_verified=False)],
            asof_ts_ms=ASOF,
        )
    with pytest.raises(ValueError, match="ranker slots"):
        assoc.exposure_report(
            [],
            [slot(PRODUCT, 0)],
            asof_ts_ms=ASOF,
            ranker_slots={"r": [(PRODUCT, B + 5000)]},
        )


# 5. Contract and non-interference ----------------------------------------------------


def test_contract_pins_implementation_and_disables_operational_rates():
    prov = assoc.provenance()
    cfg = json.loads(assoc.CONTRACT.read_text(encoding="utf-8"))
    assert cfg["fitting_allowed"] is False and cfg["study_frozen"] is False
    assert cfg["operational_missed_move_rates_enabled"] is False
    assert cfg["physical_onset_defined"] is False
    assert (
        prov["association_contract_sha256"] != prov["association_implementation_sha256"]
    )
    assert (
        cfg["lead_limit_seconds"]
        == target.load_contract(target.V2_CONTRACT_PATH)[0]["events"][
            "prediction_lead_limit_seconds"
        ]
    )


def test_combined_report_nests_both_parts_with_shared_asof():
    out = assoc.report(
        oracle_labels("up", 300),
        oracle_alerts("up", 300),
        [slot(PRODUCT, 0)],
        asof_ts_ms=ASOF,
    )
    assert (
        out["association"]["knowledge_asof_ts_ms"]
        == out["exposure"]["knowledge_asof_ts_ms"]
        == ASOF
    )
    assert out["association"]["association_alters_primary_outcomes"] is False
