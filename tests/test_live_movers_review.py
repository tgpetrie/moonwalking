"""Independent regressions from the pre-fit driver review; synthetic data only."""

import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

path = (
    Path(__file__).resolve().parents[1]
    / "scripts/scoring_experiment/live_movers_run.py"
)
spec = importlib.util.spec_from_file_location("reviewed_live_run", path)
lr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lr)


def test_primary_and_secondary_bootstraps_use_the_frozen_seed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        lr, "boot_iid", lambda values, reps, seed: calls.append((reps, seed)) or {}
    )
    monkeypatch.setattr(
        lr, "boot_moving", lambda values, reps, seed: calls.append((reps, seed)) or {}
    )
    frame = pd.DataFrame({"M1": [0.1, 0.2], "B2": [0.0, 0.1]})
    lr.paired(
        frame, "M1", "B2", {}, 100
    )  # offset used for the primary stratum in the submitted driver
    assert calls == [(5000, 20261027), (5000, 20261027)]


def test_identical_scores_cannot_create_quintile_return_spread():
    frame = pd.DataFrame({"gross_return_5m": np.arange(10.0)})
    first = lr.quintiles(frame, np.ones(10), "gross_return_5m", [0.2])
    reversed_rows = lr.quintiles(
        frame.iloc[::-1], np.ones(10), "gross_return_5m", [0.2]
    )
    assert first == reversed_rows
    assert len(first) == 1 and first[0]["n"] == 10
    assert first[0]["mean_gross_pct"] == 4.5


def test_portable_report_and_atomic_attempt_prevent_a_repeat_test(tmp_path):
    work, out = tmp_path / "local", tmp_path / "repo"
    out.mkdir()
    (out / "results_test_live_movers.json").write_text("{}")
    with pytest.raises(SystemExit, match="already"):
        lr.reserve_test(work, out, {"code_commit": "commit"})
    (out / "results_test_live_movers.json").unlink()
    lr.reserve_test(work, out, {"code_commit": "commit"})
    with pytest.raises(SystemExit, match="already"):
        lr.reserve_test(work, out, {"code_commit": "commit"})


def test_discovery_survives_docs_commit_but_refuses_changed_code(tmp_path):
    artifact = tmp_path / "discovery.json"
    code = {"driver": "original"}
    artifact.write_text(
        json.dumps(
            {
                "phase": "discovery",
                "inputs": {"data": "fixed"},
                "code_commit": "before-docs-commit",
                "code_hashes": code,
            }
        )
    )
    assert lr.require_discovery(artifact, {"data": "fixed"}, "after-docs-commit", code)
    with pytest.raises(SystemExit, match="code"):
        lr.require_discovery(
            artifact, {"data": "fixed"}, "after-docs-commit", {"driver": "changed"}
        )


def test_eligible_list_compares_product_identity_not_only_id_and_phase(tmp_path):
    with sqlite3.connect(tmp_path / "board_episodes.sqlite") as con:
        con.execute(
            "create table episodes (id,board,product_id,direction,entered_ts,start_change_pct,gross_return_5m,gross_return_15m)"
        )
        con.execute(
            "insert into episodes values (1,'ignition_1m','BTC-USD','up',100,1,2,3)"
        )
    csv = tmp_path / "eligible_episodes.csv"
    csv.write_text(
        "id,board,product_id,direction,entered_ts,phase\n1,ignition_1m,BTC-USD,up,100,train\n"
    )
    snap = {
        "raw_inputs": {"pct_1m": 1, "pct_3m": 2, "volume_change_1h_pct": 3},
        "live_score": 50,
    }
    freeze = SimpleNamespace(classify=lambda row, cfg, cooldown: ("train", None, snap))
    assert len(lr.load_episodes(tmp_path, {}, freeze)) == 1
    csv.write_text(csv.read_text().replace("BTC-USD", "ETH-USD"))
    with pytest.raises(SystemExit, match="eligible"):
        lr.load_episodes(tmp_path, {}, freeze)


def test_daily_coverage_reports_the_groups_actually_used():
    rng = np.random.default_rng(42)
    n = 90
    frame = pd.DataFrame(
        {
            "day": np.repeat(["2026-01-01", "2026-01-02", "2026-01-03"], 30),
            "direction": "up",
            "product_id": "BTC-USD",
            "pct_1m": rng.normal(size=n),
            "pct_3m": rng.normal(size=n),
            "vol": rng.normal(size=n),
            "live_score": np.r_[np.ones(30), np.arange(60)],
            "start_change_pct": rng.normal(size=n),
            "gross_return_5m": rng.normal(size=n),
        }
    )
    evaluation = frame.drop(index=range(30, 50))
    report = lr.evaluate(
        frame, evaluation, "gross_return_5m", {"B2": 10, "M1": 10}, [0.2], {}, 0
    )
    assert report["days_scored"] == 1 and report["rows_on_scored_days"] == 30
    assert report["excluded_day_groups"]["2026-01-01"]["constant_predictions"] == ["B1"]
    assert report["excluded_day_groups"]["2026-01-02"]["below_minimum_rows"]
    assert list(report["daily_ic"]) == ["2026-01-03"]
