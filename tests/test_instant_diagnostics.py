"""Reporting diagnostics preserve label semantics and show missingness explicitly."""

import copy
import sys

import pytest

from test_instant_targets import ROOT, ANCHOR, target, samples
from test_instant_targets_v2_review import v2_base, wick_rows

sys.path.insert(0, str(ROOT / "scripts/scoring_experiment"))
import instant_diagnostics as diag


def grade(rows=None):
    engine = target.TargetEvaluator(
        rows or samples(), contract_path=target.V2_CONTRACT_PATH
    )
    return engine, engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)


def test_wick_is_retained_and_forward_peak_gets_a_separate_name():
    engine, label = grade(wick_rows("up"))
    before = copy.deepcopy(label)
    original = engine.alert_timing(label, ANCHOR)
    report = diag.alert_report(engine, label, ANCHOR, strict_trigger=True)
    assert all(report[k] == v for k, v in original.items())
    assert report["timing"] == "late_after_activity_trigger"
    assert report["whole_window_peak_precedes_anchor"] is True
    assert report["pre_window_consumed_fraction"] == pytest.approx(0.004 / 0.045)
    assert report["pre_window_to_forward_peak_consumed_fraction"] == pytest.approx(
        0.004 / 0.024
    )
    assert report["pre_window_consumed_fraction_reason"] is None
    assert report["diagnostic_version"] == "instant-diagnostics-v1-draft"
    assert label == before


def test_missing_reference_reason_is_preserved_without_erasing_forward_outcome():
    engine, label = grade([r for r in samples() if r.ts_ms != ANCHOR - 30000])
    report = diag.alert_report(engine, label, ANCHOR)
    assert label["verified_forward"] is True
    assert report["pre_window_consumed_fraction"] is None
    assert report["pre_window_consumed_fraction_reason"] == "missing_grid_point"
    assert (
        report["pre_window_to_forward_peak_consumed_fraction_reason"]
        == "missing_grid_point"
    )


def test_nonpositive_reference_peak_is_diagnostic_not_false_outcome():
    engine, label = grade(
        samples(residual=lambda t: 0.03 if t < 0 else 0.02 * min(t / 300, 1))
    )
    report = diag.alert_report(engine, label, ANCHOR)
    assert label["verified_forward"] is True
    assert report["pre_window_consumed_fraction"] is None
    assert (
        report["pre_window_consumed_fraction_reason"] == "nonpositive_pre_window_peak"
    )
    assert (
        report["pre_window_to_forward_peak_consumed_fraction_reason"]
        == "nonpositive_pre_window_peak"
    )


def test_fraction_is_not_clamped_and_stale_publication_keeps_its_reason():
    engine, label = grade(wick_rows("up"))
    assert (
        diag.alert_report(engine, label, ANCHOR - 10000)[
            "pre_window_to_forward_peak_consumed_fraction"
        ]
        > 1
    )
    report = diag.alert_report(engine, label, ANCHOR + 901000)
    assert report["timing"] == "outside_event_window"
    assert report["pre_window_to_forward_peak_consumed_fraction"] is None


def test_report_rejects_wrong_contract_and_forged_evaluator():
    with pytest.raises(ValueError):
        diag.alert_report(target.TargetEvaluator(samples()), {}, ANCHOR)
    engine, label = grade()
    with pytest.raises(ValueError):
        diag.alert_report(engine, {**label, "evaluator_sha256": "other"}, ANCHOR)


def test_unavailable_publication_has_explicit_null_fields_even_in_strict_mode():
    rows = [r for r in wick_rows("up") if r.ts_ms != ANCHOR - 100000]
    engine, label = grade(rows)
    report = diag.alert_report(engine, label, ANCHOR - 100000, strict_trigger=True)
    assert report["timing"] == "unavailable"
    assert report["pre_window_consumed_fraction"] is None
    assert report["pre_window_consumed_fraction_reason"] == "missing_grid_point"
    assert report["pre_window_to_forward_peak_consumed_fraction"] is None


def test_catalog_gap_flag_does_not_change_selection_and_rejects_duplicates():
    _, label = grade()
    selected = target.forward_event_catalog([label])
    missing = diag.forward_catalog_report([label])[0]
    assert missing["anchor_ts_ms"] == selected[0]["anchor_ts_ms"]
    assert missing["left_censored"] is True
    previous = {
        **label,
        "anchor_ts_ms": ANCHOR - 5000,
        "verified_forward": False,
        "status": "ready",
    }
    assert diag.forward_catalog_report([previous, label])[0]["left_censored"] is False
    previous["status"] = "unavailable"
    assert (
        diag.forward_catalog_report([previous, label])[0]["left_censor_reason"]
        == "unavailable"
    )
    with pytest.raises(ValueError, match="duplicate"):
        diag.forward_catalog_report([label, label])
