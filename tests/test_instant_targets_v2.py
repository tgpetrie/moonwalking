"""Review counterexamples and the opt-in v2 draft; no empirical fitting."""

from dataclasses import replace
import hashlib
import math

import pytest

from test_instant_targets import ANCHOR, baseline, samples, target


def grade_v2(rows=None, direction="up", horizon=300, base=None, anchor=ANCHOR):
    engine = target.TargetEvaluator(
        rows if rows is not None else samples(direction),
        contract_path=target.V2_CONTRACT_PATH,
    )
    base = base or baseline(
        end_ts_ms=(anchor - 35000) // 60000 * 60000,
        pace_end_ts_ms=anchor - 30000,
    )
    return engine, engine.evaluate(
        anchor, base, direction, horizon, anchor + horizon * 1000
    )


def one_bps_dip(direction="up"):
    rows = samples(direction)
    at_anchor = next(row for row in rows if row.ts_ms == ANCHOR)
    # A favorable-direction negative residual of exactly 1 bp at +5s.
    sign = 1 if direction == "up" else -1
    price = at_anchor.mid * math.exp(-sign * 0.0001)
    return [
        (
            replace(row, bid=price * (1 - 0.0001), ask=price * (1 + 0.0001))
            if row.ts_ms == ANCHOR + 5000
            else row
        )
        for row in rows
    ]


def test_v1_contract_and_default_remain_pinned():
    raw = target.CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")
    assert (
        hashlib.sha256(raw).hexdigest()
        == "35d9b8a286d051aff08148a2af9987b379d65e92d57c3bea76112be52cfca7a4"
    )
    engine = target.TargetEvaluator(samples())
    label = engine.evaluate(ANCHOR, baseline(), "up", 300, ANCHOR + 300000)
    assert label["contract_version"] == "instant-target-v1"
    assert engine.alert_timing(label, ANCHOR)["consumed_fraction"] == 0
    assert "evaluator_sha256" not in label


@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize("horizon", [300, 900])
def test_named_reference_metrics_count_the_pre_trigger_leg(direction, horizon):
    engine, label = grade_v2(direction=direction, horizon=horizon)
    timing = engine.alert_timing(label, ANCHOR)
    assert timing["post_anchor_consumed_fraction"] == 0
    assert timing["pre_window_consumed_fraction"] == pytest.approx(0.002 / 0.022)
    assert timing["pre_window_reference_ts_ms"] == ANCHOR - 30000
    assert timing["physical_onset_defined"] is False
    assert timing["pre_window_reference_is_physical_origin"] is False
    assert "consumed_fraction" not in timing
    assert timing["timing"] == "early_after_activity_trigger"


@pytest.mark.parametrize("direction", ["up", "down"])
def test_forward_catalog_retains_real_moves_with_small_retracement(direction):
    engine, label = grade_v2(one_bps_dip(direction), direction=direction)
    assert label["verified_forward"] is True
    assert label["verified_onset"] is False
    assert target.event_catalog([label]) == []
    forward = target.forward_event_catalog([label])
    assert len(forward) == 1
    assert forward[0]["catalog_kind"] == "forward_window_not_physical_impulse"
    timing = engine.forward_alert_timing(forward[0], ANCHOR)
    assert timing["association_kind"] == "forward_window_not_physical_impulse"
    assert timing["timing"] == "within_forward_window_before_peak"
    assert "pre_onset_prediction" not in timing.values()
    with pytest.raises(ValueError, match="verified label"):
        engine.alert_timing(label, ANCHOR)
    legacy = target.TargetEvaluator(one_bps_dip(direction))
    v1 = legacy.evaluate(ANCHOR, baseline(), direction, 300, ANCHOR + 300000)
    assert v1["verified_forward"] is True and v1["verified_onset"] is False
    assert target.event_catalog([v1]) == []


def test_forward_target_and_catalog_do_not_require_activity_gate():
    engine, label = grade_v2(
        base=baseline(
            end_ts_ms=ANCHOR - 60000,
            pace_trade_median_30s=6,
            pace_quote_usd_median_30s=60,
        )
    )
    assert label["verified_forward"] is True
    assert label["onset_candidate"] is False
    assert len(target.forward_event_catalog([label])) == 1
    assert (
        engine.forward_alert_timing(label, ANCHOR)["pre_window_consumed_fraction"] > 0
    )


@pytest.mark.parametrize("offset", [0, 5000, 30000, 35000, 55000])
def test_v2_baseline_cutoff_ends_before_both_velocity_windows(offset):
    anchor = ANCHOR + offset
    expected = (anchor - 35000) // 60000 * 60000
    engine, label = grade_v2(anchor=anchor)
    assert expected <= anchor - 35000
    assert label["status"] == "ready"
    if anchor // 60000 * 60000 > expected:
        bad = baseline(end_ts_ms=anchor // 60000 * 60000, pace_end_ts_ms=anchor - 30000)
        result = engine.evaluate(anchor, bad, "up", 300, anchor + 300000)
        assert result["reason"] == "baseline_window_misaligned"


@pytest.mark.parametrize("peak", [0, -1, None, float("nan"), float("inf")])
def test_invalid_external_peak_is_rejected_before_division(peak):
    engine, label = grade_v2()
    with pytest.raises(ValueError, match="positive finite"):
        engine.forward_alert_timing({**label, "peak_residual_log": peak}, ANCHOR)


def test_pre_window_peak_includes_the_pre_trigger_path():
    # A previous wick exceeds the subsequent peak. Do not erase it by
    # merely shifting the post-anchor peak upward by the pre-anchor return.
    rows = samples()
    price = 100 * math.exp(0.04)
    rows = [
        (
            replace(row, bid=price * (1 - 0.0001), ask=price * (1 + 0.0001))
            if row.ts_ms == ANCHOR - 10000
            else row
        )
        for row in rows
    ]
    engine, label = grade_v2(rows)
    assert label["verified_forward"] is True
    assert label["pre_window_peak_ts_ms"] == ANCHOR - 10000
    timing = engine.forward_alert_timing(label, ANCHOR)
    assert timing["pre_window_consumed_fraction"] == pytest.approx(0.002 / 0.04)
    assert timing["lead_to_pre_window_peak_seconds"] == -10


def test_reference_missingness_does_not_erase_complete_forward_label():
    rows = [row for row in samples() if row.ts_ms != ANCHOR - 30000]
    engine, label = grade_v2(rows)
    assert label["verified_forward"] is True
    assert label["pre_window_reference_status"] == "unavailable"
    timing = engine.forward_alert_timing(label, ANCHOR)
    assert timing["pre_window_consumed_fraction"] is None
    assert timing["post_anchor_consumed_fraction"] == 0


def test_reference_may_have_no_positive_peak_for_an_independent_forward_move():
    # A deep pre-anchor decline followed by a qualifying rebound. The
    # forward label remains valid while this reference has no positive peak.
    rows = samples(residual=lambda t: 0.05 if t < 0 else 0.02 * min(t / 300, 1))
    engine, label = grade_v2(rows)
    assert label["verified_forward"] is True
    assert label["pre_window_peak_residual_log"] == 0
    assert (
        engine.forward_alert_timing(label, ANCHOR)["pre_window_consumed_fraction"]
        is None
    )


def test_crossing_does_not_algebraically_force_positive_F1_acceleration():
    def path(t):
        if t < -30:
            return 0.012 * (t + 180) / 150
        if t < 0:
            return 0.012
        return 0.014 + 0.02 * min(t / 300, 1)

    engine, label = grade_v2(samples(residual=path))
    assert label["verified_onset"] is True
    fast = engine._residual(ANCHOR - 30000, ANCHOR, 1, 1)
    prior = engine._residual(ANCHOR - 180000, ANCHOR - 30000, 1, 1)
    assert fast - prior / 5 < 0


def test_trade_count_pace_can_trigger_while_volume_pace_is_below_two():
    _, label = grade_v2(
        base=baseline(end_ts_ms=ANCHOR - 60000, pace_quote_usd_median_30s=100)
    )
    assert label["verified_onset"] is True
    assert label["pace_multiple"] == 3  # 6 trades / median 2
    assert 60 / 100 < 2  # volume ratio does not have to exceed 2


def test_forged_implementation_and_mixed_catalog_versions_are_rejected():
    engine, label = grade_v2()
    other = {**label, "evaluator_sha256": "different"}
    with pytest.raises(ValueError, match="this evaluator"):
        engine.forward_alert_timing(other, ANCHOR)
    with pytest.raises(ValueError, match="implementations"):
        target.forward_event_catalog([label, other])


def test_v2_stays_opt_in_and_operational_metrics_remain_gated():
    engine, _ = grade_v2()
    assert engine.cfg["fitting_allowed"] is False
    assert engine.cfg["targets"]["primary_pointwise"] == "verified_forward"
    assert (
        engine.cfg["reference_metrics"][
            "operational_false_alert_and_missed_move_rates_enabled"
        ]
        is False
    )


def test_trigger_timing_uses_the_declared_pre_window_halfway_boundary():
    engine, label = grade_v2()
    before = engine.alert_timing(label, ANCHOR - 5000)
    assert before["timing"] == "before_activity_trigger"
    assert "pre_onset_prediction" not in before.values()
    half = engine.alert_timing(label, ANCHOR + 135000)
    assert half["pre_window_consumed_fraction"] == pytest.approx(0.5)
    assert half["post_anchor_consumed_fraction"] == pytest.approx(0.45)
    assert half["timing"] == "late_after_activity_trigger"


def test_forward_catalog_flags_events_dated_after_a_data_gap():
    def ramp(t):
        return 0.002 + 0.06 * min(max(t / 900, 0), 1) if t >= 0 else 0

    def catalog(rows):
        engine = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH)
        return target.forward_event_catalog(
            engine.evaluate(
                anchor,
                baseline(
                    end_ts_ms=(anchor - 35000) // 60000 * 60000,
                    pace_end_ts_ms=anchor - 30000,
                    available_ts_ms=anchor,
                    beta_available_ts_ms=anchor,
                    pace_available_ts_ms=anchor,
                ),
                "up",
                300,
                anchor + 300_000,
            )
            for anchor in range(ANCHOR - 120_000, ANCHOR + 400_000, 5000)
        )

    # Forward windows may start before the jump; -105s is the first to qualify.
    complete = catalog(samples(residual=ramp))
    assert complete[0]["anchor_ts_ms"] == ANCHOR - 105_000
    assert complete[0]["previous_anchor_status"] == "ready"
    assert complete[0]["left_censored"] is False
    # One missing snapshot at +150s voids every anchor in [-150s, +150s].
    gap = catalog(
        [row for row in samples(residual=ramp) if row.ts_ms != ANCHOR + 150_000]
    )
    assert gap[0]["anchor_ts_ms"] == ANCHOR + 155_000
    assert gap[0]["previous_anchor_status"] == "unavailable"
    assert gap[0]["left_censored"] is True
