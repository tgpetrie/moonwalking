"""Independent synthetic regressions for the pre-discovery driver review."""

import json
from pathlib import Path
import sys
import subprocess
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
import fundamentals_run as fr
import panel
import run as base_run
from test_fundamentals_run import setup_world


def test_availability_uses_presence_without_fitting_or_label_magnitudes(tmp_path):
    base, _ = setup_world(tmp_path, n_days=330)
    cfg = panel.load_config()
    predicted = fr.walk_forward(base, 7, cfg, "2024-01-01", "2024-11-01")[0]
    with patch.object(fr, "walk_forward", side_effect=AssertionError("must not fit")):
        mask = fr.prediction_availability(base, 7, "2024-01-01", "2024-11-01")
        changed = base.copy()
        changed["y7"] = changed["y7"] * -1000000
        other = fr.prediction_availability(changed, 7, "2024-01-01", "2024-11-01")
    pd.testing.assert_series_equal(mask.notna(), predicted.notna())
    pd.testing.assert_series_equal(mask, other)


def mock_main_world(tmp_path, monkeypatch):
    base, cohort = setup_world(tmp_path, n_days=125)
    cp = tmp_path / "cohort.json"
    cp.write_text(json.dumps(cohort), encoding="utf-8")
    cfg = panel.load_config()
    cfg["discovery"] = ["2024-01-01", "2024-04-30"]
    fcfg = fr.fcfg_load()
    fcfg.update(cohort=str(cp), captures=str(tmp_path))
    monkeypatch.setattr(fr, "WORK", tmp_path / "work")
    monkeypatch.setattr(fr, "OUT", tmp_path / "out")
    monkeypatch.setattr(fr, "MIN_TRAIN_ROWS", 5)
    monkeypatch.setattr(panel, "load_config", lambda: cfg)
    monkeypatch.setattr(fr, "fcfg_load", lambda: fcfg)
    monkeypatch.setattr(
        fr,
        "provenance",
        lambda *a, **k: {
            "combined_hash": "inputs",
            "baseline_input_sha256": {"panel_MANIFEST.json": "panel"},
        },
    )
    monkeypatch.setattr(fr, "experiment_identity", lambda: {"combined_hash": "code"})
    monkeypatch.setattr(fr, "git_state", lambda: ("commit", False))
    monkeypatch.setattr(
        base_run,
        "load_long",
        lambda *a: (base, {"provenance": {"manifest_sha256": "panel"}}),
    )
    monkeypatch.setattr(
        fr.gate, "coverage", lambda *a, **k: {"per_day_counts": {}, "problems": []}
    )
    monkeypatch.setattr(
        fr.gate,
        "evaluate_gate",
        lambda *a: {
            "gate_passed": True,
            **{k: {"pass": True} for k in ("G1", "G2", "G3", "G4", "G5")},
        },
    )
    return base


def test_readiness_main_cannot_fit_and_preserves_shared_artifacts(
    tmp_path, monkeypatch
):
    mock_main_world(tmp_path, monkeypatch)
    destination = tmp_path / "review_readiness.json"
    with patch.object(
        fr, "walk_forward", side_effect=AssertionError("readiness fitted a model")
    ):
        assert fr.main(["readiness", "--readiness-report", str(destination)]) == 0
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert result["ready"] and result["model_fits_run"] is False
    assert not fr.WORK.exists() and not fr.OUT.exists()


def test_missing_discovery_refuses_before_data_load_or_any_fit(tmp_path, monkeypatch):
    mock_main_world(tmp_path, monkeypatch)
    with patch.object(
        base_run, "load_long", side_effect=AssertionError("loaded heldout data")
    ), patch.object(
        fr, "walk_forward", side_effect=AssertionError("fitted before guard")
    ):
        with pytest.raises(SystemExit, match="no fundamentals discovery"):
            fr.main(["test"])


def test_committed_result_and_atomic_marker_both_prevent_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "WORK", tmp_path / "work")
    monkeypatch.setattr(fr, "OUT", tmp_path / "out")
    fr.OUT.mkdir()
    (fr.OUT / "results_test_fundamentals.json").write_text("{}")
    with pytest.raises(SystemExit, match="already exists"):
        fr.assert_phase_unused("test")
    (fr.OUT / "results_test_fundamentals.json").unlink()
    fr.reserve_test("inputs", "code")
    original = (fr.WORK / "test_attempt_fundamentals.json").read_bytes()
    with pytest.raises(SystemExit):
        fr.reserve_test("inputs", "code")
    assert (fr.WORK / "test_attempt_fundamentals.json").read_bytes() == original
    with patch.object(fr, "assert_phase_unused"):
        with pytest.raises(SystemExit, match="concurrent"):
            fr.reserve_test("inputs", "code")


def test_docs_only_commit_is_compatible_but_changed_experiment_is_not(tmp_path):
    path = tmp_path / "discovery.json"
    path.write_text(
        json.dumps(
            {
                "phase": "discovery",
                "provenance": {"combined_hash": "inputs"},
                "code_commit": "old-docs-head",
                "experiment_fingerprint": "same-code",
                "ready": True,
                "frozen": {
                    "btc30_tercile_thresholds": [-1, 1],
                    "fee_coefficient_sign": 1,
                    "discovery_difference_mean": 0.01,
                },
            }
        )
    )
    assert (
        fr.require_discovery(path, "inputs", "same-code")["code_commit"]
        == "old-docs-head"
    )
    with pytest.raises(SystemExit, match="experiment code"):
        fr.require_discovery(path, "inputs", "changed-code")
    with pytest.raises(SystemExit, match="configuration differ"):
        fr.require_discovery(path, "changed-input", "same-code")


def test_baseline_cache_bytes_are_bound_into_input_provenance(tmp_path):
    _, cohort = setup_world(tmp_path, n_prod=3)
    cp = tmp_path / "cohort.json"
    cp.write_text(json.dumps(cohort))
    cache = tmp_path / "cache.pkl"
    cache.write_bytes(b"original")
    cfg, fcfg = panel.load_config(), fr.fcfg_load()
    a = fr.provenance(cfg, fcfg, cp, cohort, tmp_path, {"long_base.pkl": cache})
    cache.write_bytes(b"changed")
    b = fr.provenance(cfg, fcfg, cp, cohort, tmp_path, {"long_base.pkl": cache})
    assert a["combined_hash"] != b["combined_hash"]


def test_missing_labels_and_unscorable_days_are_not_counted_as_scored_rows(
    tmp_path, monkeypatch
):
    base, cohort = setup_world(tmp_path, n_days=130)
    days = base.index.get_level_values("date")
    base.loc[days == days.max(), "y7"] = np.nan
    penultimate = days.unique()[-2]
    base.loc[
        (days == penultimate)
        & (base.index.get_level_values("product").isin(["P0-USD", "P1-USD", "P2-USD"])),
        "y7",
    ] = np.nan

    def fit(d, *a, **kw):
        return d["z_r1"], None, []

    monkeypatch.setattr(fr, "walk_forward", fit)
    cfg = panel.load_config()
    cfg["horizons_days"] = [7]
    res = fr.run_lag(
        base,
        {7: base["z_r7"]},
        cohort,
        tmp_path,
        cfg,
        fr.eval_cfg(cfg, fr.fcfg_load()),
        {},
        2,
        ("2024-01-01", "2024-05-09"),
        "2024-01-01",
        "2024-05-01",
        [-1, 1],
        False,
    )["horizons"]["h7"]
    assert (
        res["rows"]["prediction_rows_in_period"] - res["rows"]["scored_in_period"] == 44
    )
    assert (
        str(days.max().date())
        not in res["incremental_ic_s1_minus_s0"]["paired_daily_ic"]
    )
    assert (
        str(penultimate.date())
        not in res["incremental_ic_s1_minus_s0"]["paired_daily_ic"]
    )


def test_calendar_bootstrap_does_not_stitch_missing_weeks():
    cfg = panel.load_config()
    dates = [
        pd.Timestamp("2024-01-01") + pd.Timedelta(weeks=i * 5 + j)
        for i in range(4)
        for j in range(3)
    ]
    keys = [int(d.isocalendar().year) * 100 + int(d.isocalendar().week) for d in dates]
    result = fr.calendar_moving(pd.Series(np.arange(12), index=keys), cfg, 0)
    assert result["valid_calendar_windows"] == 0 and result["lo"] is None
    dates = pd.date_range("2024-12-02", periods=12, freq="7D")
    keys = [int(d.isocalendar().year) * 100 + int(d.isocalendar().week) for d in dates]
    result = fr.calendar_moving(pd.Series(np.arange(12), index=keys), cfg, 0)
    assert result["valid_calendar_windows"] == 9 and result["lo"] is not None


def test_calibration_control_exposes_lift_unrelated_to_fee_information(
    tmp_path, monkeypatch
):
    base, _ = setup_world(tmp_path, n_days=330)
    products = base.index.get_level_values("product")
    codes = pd.Categorical(products).codes.astype(float)
    base["y7"] = codes
    dm = base.assign(fee_raw=1.0, scope="protocol")
    monkeypatch.setattr(fr, "build_matched", lambda *a: (fr.apply_day_rule(dm, 20), {}))
    cfg = panel.load_config()
    cfg["horizons_days"] = [7]
    res = fr.run_lag(
        base,
        {7: -base["y7"]},
        [],
        tmp_path,
        cfg,
        fr.eval_cfg(cfg, fr.fcfg_load()),
        {},
        2,
        ("2024-01-01", "2024-11-25"),
        "2024-01-01",
        "2024-11-01",
        [-1, 1],
        False,
    )["horizons"]["h7"]
    assert res["incremental_ic_s1_minus_s0"]["mean"] > 1.9
    assert res["calibration_only_attribution_control"]["mean"] == pytest.approx(
        0, abs=1e-12
    )


def test_committed_discovery_must_match_local_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REPO", tmp_path)
    monkeypatch.setattr(fr, "OUT", tmp_path / "results")
    disc = {"phase": "discovery", "frozen": {"value": 1}}
    with patch.object(
        fr.subprocess,
        "run",
        return_value=subprocess.CompletedProcess([], 1, "", "missing"),
    ):
        with pytest.raises(SystemExit, match="commit the frozen"):
            fr.require_committed_discovery(disc)
    with patch.object(
        fr.subprocess,
        "run",
        return_value=subprocess.CompletedProcess([], 0, json.dumps(disc), ""),
    ):
        fr.require_committed_discovery(disc)
        with pytest.raises(SystemExit, match="differs"):
            fr.require_committed_discovery({**disc, "changed": True})


def test_incomplete_discovery_is_not_an_authorization_to_fit(tmp_path):
    path = tmp_path / "discovery.json"
    path.write_text(
        json.dumps(
            {
                "phase": "discovery",
                "provenance": {"combined_hash": "i"},
                "experiment_fingerprint": "c",
                "ready": False,
            }
        )
    )
    with pytest.raises(SystemExit, match="incomplete"):
        fr.require_discovery(path, "i", "c")


def test_source_identity_includes_dependencies_but_not_handoff_notes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(fr, "REPO", tmp_path)
    monkeypatch.setattr(fr, "HERE", tmp_path / "scripts/scoring_experiment")
    names = [
        "fundamentals_run.py",
        "fundamentals.py",
        "fundamentals_gate.py",
        "model.py",
        "panel.py",
        "evaluate.py",
        "run.py",
    ]
    for name in names:
        path = fr.HERE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# source\n")
    for name in (
        "scripts/scoring_data/freeze_daily_panel.py",
        "docs/research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("frozen source\n")
    first = fr.experiment_identity()["combined_hash"]
    (tmp_path / "HANDOFF.md").write_text("new review checkpoint")
    assert fr.experiment_identity()["combined_hash"] == first
    (fr.HERE / "model.py").write_text("# changed source\n")
    assert fr.experiment_identity()["combined_hash"] != first
