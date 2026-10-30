"""Independent Claude review probes for the v2 draft (8b5b266). Synthetic only; no fitting."""

from dataclasses import replace
import importlib.util
import math
import random
import subprocess
import sys

import pytest

from test_instant_targets import ANCHOR, ROOT, baseline, samples, target

V1_REFERENCE_COMMIT = "cb7034a48d5a533153dfe1d113921318db82f3ec"  # v1 implementation before any v2 change
V2_KEYS = {
    "evaluator_sha256", "primary_pointwise_target", "physical_onset_defined", "pre_window_reference_ts_ms",
    "pre_window_reference_is_physical_origin", "pre_window_reference_status", "pre_window_reference_reason",
    "pre_window_peak_ts_ms", "pre_window_peak_residual_log",
}


def reference_v1(tmp_path):
    try:
        src = subprocess.run(["git", "show", f"{V1_REFERENCE_COMMIT}:scripts/scoring_experiment/instant_targets.py"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("v1 reference commit not available")
    path = tmp_path / "instant_targets_v1_ref.py"
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("instant_targets_v1_ref", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.CONTRACT_PATH = target.CONTRACT_PATH  # same pinned v1 contract file
    return mod


def random_path(seed):
    rng = random.Random(seed)
    knots = [rng.gauss(0, 0.006) for _ in range(12)]
    drift = rng.choice([0.0, 0.01, 0.025, -0.02])

    def residual(elapsed):
        i = int((elapsed + 180) // 90) % len(knots)
        return knots[i] * 0.3 + drift * max(min(elapsed / 300, 1), 0) + 0.002 * math.sin(elapsed / 7)

    return residual


def rows_for(seed, direction):
    rows = samples(direction, residual=random_path(seed))
    rng = random.Random(seed + 1)
    return [replace(r, trade_count=rng.randint(0, 4), trade_count_at_bucket_start=0, quote_volume_usd=rng.uniform(0, 60))
            for r in rows]


def v2_base(anchor=ANCHOR, **kw):
    return baseline(end_ts_ms=(anchor - 35000) // 60000 * 60000, pace_end_ts_ms=anchor - 30000, **kw)


# 1. v1 valid-label behaviour is unchanged ------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_v1_outputs_identical_to_pre_v2_reference(seed, tmp_path):
    ref = reference_v1(tmp_path)
    for direction in ("up", "down"):
        rows = rows_for(seed, direction)
        ref_rows = [ref.Sample(**r.__dict__) for r in rows]
        for horizon in (300, 900):
            new = target.TargetEvaluator(rows).evaluate(ANCHOR, baseline(), direction, horizon, ANCHOR + horizon * 1000)
            old = ref.TargetEvaluator(ref_rows).evaluate(ANCHOR, ref.Baseline(**baseline().__dict__), direction, horizon,
                                                         ANCHOR + horizon * 1000)
            assert new == old
            if new.get("verified_onset"):
                for pub in (ANCHOR - 60000, ANCHOR, ANCHOR + 7000, new["peak_ts_ms"]):
                    assert target.TargetEvaluator(rows).alert_timing(new, pub) == \
                        ref.TargetEvaluator(ref_rows).alert_timing(old, pub)


# 2. the v2 delta is only the baseline cutoff and added named keys -------------------------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_v2_differs_from_v1_only_by_cutoff_and_added_keys(seed):
    for direction in ("up", "down"):
        rows = rows_for(seed, direction)
        for horizon in (300, 900):
            v1 = target.TargetEvaluator(rows).evaluate(ANCHOR, baseline(), direction, horizon, ANCHOR + horizon * 1000)
            v2 = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH).evaluate(
                ANCHOR, v2_base(), direction, horizon, ANCHOR + horizon * 1000)
            assert set(v2) - set(v1) <= V2_KEYS
            strip = {k: v for k, v in v2.items() if k not in V2_KEYS | {"contract_version", "contract_sha256"}}
            assert strip == {k: v for k, v in v1.items() if k not in ("contract_version", "contract_sha256")}


@pytest.mark.parametrize("offset_s", [0, 5, 30, 34, 35, 36, 55])
def test_v2_rejects_the_v1_cutoff_when_they_differ(offset_s):
    anchor = 60000 * 63 + offset_s * 1000
    anchor -= anchor % 5000
    v1_end, v2_end = anchor // 60000 * 60000, (anchor - 35000) // 60000 * 60000
    engine = target.TargetEvaluator(samples(), contract_path=target.V2_CONTRACT_PATH)
    assert engine._baseline_quality(v2_base(anchor), anchor) is None
    if v1_end != v2_end:
        assert engine._baseline_quality(replace(v2_base(anchor), end_ts_ms=v1_end), anchor) == "baseline_window_misaligned"


# 3. pre-window and post-anchor peaks, including earlier wicks ------------------------------------------------------

@pytest.mark.parametrize("seed", range(60))
def test_pre_window_peak_equals_forward_peak_unless_an_earlier_wick_is_higher(seed):
    """log additivity: residual(ref, ts) = residual(ref, anchor) + residual(anchor, ts) for ts >= anchor."""
    for direction in ("up", "down"):
        engine = target.TargetEvaluator(rows_for(seed, direction), contract_path=target.V2_CONTRACT_PATH)
        lab = engine.evaluate(ANCHOR, v2_base(), direction, 300, ANCHOR + 300000)
        if lab["status"] != "ready" or lab["pre_window_reference_status"] != "ready":
            continue
        lead = engine._residual(ANCHOR - 30000, ANCHOR, lab["beta"], 1 if direction == "up" else -1)
        if lab["pre_window_peak_ts_ms"] >= ANCHOR:
            assert lab["pre_window_peak_ts_ms"] == lab["peak_ts_ms"]
            assert abs(lab["pre_window_peak_residual_log"] - (lead + lab["peak_residual_log"])) < 1e-12
        else:
            assert lab["pre_window_peak_residual_log"] > lead + lab["peak_residual_log"]


def wick_rows(direction):
    """Verified strict onset whose highest point is a wick inside the 30s activity window."""
    def residual(elapsed):
        if elapsed < 0:
            return 0.045 if elapsed == -10 else 0.0     # 4.5% one-point wick at anchor-10s; flat otherwise, so the
        return 0.004 + 0.02 * min(elapsed / 300, 1)        # crossing happens in the last 5s; forward leg +2%, no retrace
    rows = samples(direction, residual=residual)
    return [replace(r, trade_count=3) for r in rows]


@pytest.mark.parametrize("direction", ["up", "down"])
def test_earlier_wick_makes_every_strict_publication_late(direction):
    engine = target.TargetEvaluator(wick_rows(direction), contract_path=target.V2_CONTRACT_PATH)
    lab = engine.evaluate(ANCHOR, v2_base(), direction, 300, ANCHOR + 300000)
    assert lab["verified_onset"] is True
    assert lab["pre_window_peak_ts_ms"] == ANCHOR - 10000 < ANCHOR <= lab["peak_ts_ms"]
    timing = engine.alert_timing(lab, ANCHOR)
    assert timing["timing"] == "late_after_activity_trigger"
    assert timing["lead_to_pre_window_peak_seconds"] < 0
    assert 0 < timing["pre_window_consumed_fraction"] < 0.5     # under half consumed, yet classified late
    assert engine.forward_alert_timing(lab, ANCHOR)["timing"] == "within_forward_window_before_peak"


# 4. mirror symmetry of up/down on arbitrary paths -----------------------------------------------------------------

@pytest.mark.parametrize("seed", range(30))
def test_up_and_down_labels_mirror(seed):
    up = target.TargetEvaluator(rows_for(seed, "up"), contract_path=target.V2_CONTRACT_PATH).evaluate(
        ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)
    dn = target.TargetEvaluator(rows_for(seed, "down"), contract_path=target.V2_CONTRACT_PATH).evaluate(
        ANCHOR, v2_base(), "down", 300, ANCHOR + 300000)
    for k in ("status", "verified_forward", "verified_onset", "peak_ts_ms", "pre_window_peak_ts_ms", "breakout_ts_ms"):
        assert up.get(k) == dn.get(k), k
    for k in ("terminal_residual_log", "peak_residual_log", "adverse_residual_log", "pre_window_peak_residual_log"):
        assert abs(up[k] - dn[k]) < 1e-9, k


# 5. maturity and missingness ---------------------------------------------------------------------------------------

def test_maturity_boundary_and_reference_does_not_extend_it():
    engine = target.TargetEvaluator(samples(), contract_path=target.V2_CONTRACT_PATH)
    assert engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 299999)["status"] == "pending"
    assert engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)["status"] == "ready"


def test_gap_only_before_the_pre_window_keeps_reference_but_removes_onset():
    rows = [r for r in samples() if r.ts_ms != ANCHOR - 35000]
    lab = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH).evaluate(
        ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)
    assert lab["status"] == "ready" and lab["pre_window_reference_status"] == "ready"
    assert lab["onset_status"] == "unavailable" and lab["verified_onset"] is None   # missing, never False


def test_mixed_quote_provenance_inside_pre_window_is_unavailable_not_false():
    rows = [replace(r, price_source="last_trade") if r.ts_ms == ANCHOR - 15000 else r for r in samples()]
    engine = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH)
    lab = engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)
    assert lab["status"] == "ready"
    assert (lab["pre_window_reference_status"], lab["pre_window_reference_reason"]) == ("unavailable", "price_fallback")
    assert lab["onset_status"] == "unavailable" and lab["verified_onset"] is None


# 6. backward publication lookup ------------------------------------------------------------------------------------

def verified_v2():
    rows = [replace(r, trade_count=3) for r in samples()]
    engine = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH)
    lab = engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)
    assert lab["verified_forward"] is True
    return rows, engine, lab


def test_publication_uses_the_grid_point_at_or_before_it_never_the_next():
    _, engine, lab = verified_v2()
    for pub in (ANCHOR + 60000, ANCHOR + 64999):
        assert engine.forward_alert_timing(lab, pub)["price_snapshot_ts_ms"] == ANCHOR + 60000


def test_quote_age_is_measured_at_publication_not_at_the_grid_point():
    rows, _, lab = verified_v2()
    ts = ANCHOR + 60000
    rows = [replace(r, quote_ts_ms=ts - 6000) if r.ts_ms == ts else r for r in rows]
    engine = target.TargetEvaluator(rows, contract_path=target.V2_CONTRACT_PATH)
    lab = engine.evaluate(ANCHOR, v2_base(), "up", 300, ANCHOR + 300000)
    assert engine.forward_alert_timing(lab, ts)["timing"] != "unavailable"          # 6.0s old at publication
    assert engine.forward_alert_timing(lab, ts + 4999) == dict(
        evaluation_only=True, timing="unavailable", reason="stale_alert_quote")     # 10.999s old


# 7. provenance on both catalogs ------------------------------------------------------------------------------------

def test_forward_catalog_refuses_v1_labels_like_forward_timing_does():
    """Reproduced at 8b5b266: forward_event_catalog accepted v1 labels and stamped them as v2 forward windows,
    although forward_alert_timing refuses v1. Fixed on claude/instant-radar-v2-review."""
    rows = [replace(r, trade_count=3) for r in samples()]
    v1 = target.TargetEvaluator(rows)
    lab = v1.evaluate(ANCHOR, baseline(), "up", 300, ANCHOR + 300000)
    assert lab["contract_version"] == "instant-target-v1" and lab["verified_forward"] is True
    with pytest.raises(ValueError):
        v1.forward_alert_timing(lab, ANCHOR)
    with pytest.raises(ValueError):
        target.forward_event_catalog([lab])
    assert target.forward_event_catalog([]) == []
    assert len(target.event_catalog([lab], target="verified_forward")) == 1   # v1 generic catalog unchanged


def test_catalog_rejects_v2_labels_with_and_without_evaluator_hash():
    _, _, lab = verified_v2()
    forged = {k: v for k, v in lab.items() if k != "evaluator_sha256"}
    with pytest.raises(ValueError):
        target.forward_event_catalog([lab, {**forged, "anchor_ts_ms": ANCHOR + 400000}])
