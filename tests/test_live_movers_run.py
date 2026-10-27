"""Synthetic tests for the live-movers comparison driver. No frozen capture or real outcome is read."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("live_run", ROOT / "scripts/scoring_experiment/live_movers_run.py")
lr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lr)


def frame(n_days=10, per_day=30, direction="up", seed=0, signal=0.0):
    rng = np.random.default_rng(seed)
    n = n_days * per_day
    days = np.repeat(pd.date_range("2026-08-20", periods=n_days).strftime("%Y-%m-%d"), per_day)
    p1, p3, v = rng.normal(size=n), rng.normal(size=n), rng.normal(50, 20, n)
    sign = -1 if direction == "down" else 1
    y = signal * sign * p3 + rng.normal(size=n)
    return pd.DataFrame({"id": np.arange(n), "direction": direction, "day": days, "product_id": [f"P{i % 40}-USD" for i in range(n)],
                         "pct_1m": p1, "pct_3m": p3, "vol": v, "live_score": rng.uniform(0, 100, n),
                         "start_change_pct": sign * np.abs(rng.normal(3, 1, n)), "gross_return_5m": y, "gross_return_15m": y})


def test_preprocessing_uses_fitting_rows_only():
    a, b = frame(seed=1), frame(seed=2)
    b = b.assign(pct_1m=b["pct_1m"] * 1000)  # extreme evaluation rows must not move limits or scales
    d1 = lr.Design(True).fit(lr.aligned(a))
    d2 = lr.Design(True).fit(lr.aligned(a))
    d2.transform(lr.aligned(b))
    assert (d1.lo == d2.lo).all() and (d1.mu == d2.mu).all()
    X = d1.transform(lr.aligned(b))
    assert np.isfinite(X).all()
    assert X[:, 0].max() <= ((d1.hi["a1"] - d1.mu["a1"]) / d1.sd["a1"]) + 1e-9   # clipped at the fitted 99th percentile


def test_direction_alignment_flips_price_returns_only():
    up, down = frame(direction="up"), frame(direction="down")
    au, ad = lr.aligned(up), lr.aligned(down)
    assert np.allclose(au["a3"], up["pct_3m"]) and np.allclose(ad["a3"], -down["pct_3m"])
    assert np.allclose(ad["v"], down["vol"])
    assert np.allclose(lr.baselines(down)["B1"], 100 - down["live_score"])
    assert (lr.baselines(down)["B0"] >= 0).all()


def test_ridge_recovers_signal_on_both_boards():
    for direction in ("up", "down"):
        df = frame(n_days=20, direction=direction, signal=1.0)
        m = lr.fit_ridge(df, "gross_return_5m", 1.0, False)
        assert m["beta"][1] > 0.5   # aligned 3m return carries the signal


def test_daily_groups_are_identical_and_respect_rules():
    df = frame(n_days=4)
    df = df[~((df["day"] == df["day"].iloc[0]) & (df.index % 30 >= 19))]   # day 1 has 19 rows
    preds = {"A": np.random.default_rng(0).normal(size=len(df)), "B": np.ones(len(df))}
    assert len(lr.daily_ics(df, preds, "gross_return_5m")) == 0            # B constant every day -> no day for anyone
    preds["B"] = np.random.default_rng(1).normal(size=len(df))
    ics = lr.daily_ics(df, preds, "gross_return_5m")
    assert len(ics) == 3 and df["day"].iloc[0] not in ics.index and ics.notna().all().all()


def test_alpha_ties_choose_larger():
    tr, dc = frame(seed=3), frame(seed=4)
    tr = tr.assign(pct_1m=0.0, pct_3m=0.0, vol=0.0)   # zero-variance inputs -> every alpha predicts the same constant ranking
    tr["vol"] = np.arange(len(tr), dtype=float)
    sel = lr.select_alphas(tr, dc, "gross_return_5m", [0.1, 1, 10, 100, 1000])
    for name in ("B2", "M1"):
        ics = sel["discovery_ic_by_alpha"][name]
        best = max(ics.values())
        assert sel["alpha"][name] == max(float(a) for a, v in ics.items() if v == best)


def test_moving_block_keeps_gaps_missing():
    s = pd.Series(1.0, index=pd.date_range("2026-10-04", periods=14).strftime("%Y-%m-%d"))
    s = s.drop(s.index[5:8])   # three missing calendar days
    r = lr.boot_moving(s, 500, 1)
    assert r["n_days"] == 11 and r["lo"] == r["hi"] == 1.0   # missing days are not zero
    assert lr.boot_iid(np.array([0.1, 0.2]), 100, 1)["lo"] is None


def test_score_is_ordinal_percentile_against_fixed_reference():
    ref = np.arange(100, dtype=float)
    sc = lr.to_score(np.array([-5.0, 49.5, 1e9]), ref)
    assert list(sc) == [0.0, 50.0, 100.0]


def test_verdict_rules():
    ok = {"iid_daily": {"mean": 0.03, "lo": 0.01, "hi": 0.05}, "moving_block_3d": {"lo": 0.002}}
    assert lr.verdict(ok, 0.01, 0.02) == "historically supportive"
    assert lr.verdict(ok, -0.01, 0.02) == "inconclusive"
    assert lr.verdict({**ok, "moving_block_3d": {"lo": -0.01}}, 0.01, 0.02) == "inconclusive"
    assert lr.verdict({"iid_daily": {"mean": 0.0, "lo": -0.01, "hi": 0.015}, "moving_block_3d": {"lo": -0.02}}, 0.01, 0.02) == \
        "below the minimum effect"


def test_quintiles_report_gross_and_cost_scenarios_without_double_counting():
    df = frame()
    q = lr.quintiles(df, df["pct_3m"].to_numpy(), "gross_return_5m", [0.2, 1.2])
    assert sum(r["n"] for r in q) == len(df)
    assert all(abs(r["mean_gross_minus_0.2pct"] - (r["mean_gross_pct"] - 0.2)) < 1e-12 for r in q)


def test_test_phase_refuses_without_matching_discovery(tmp_path):
    p, h = tmp_path / "d.json", {"x": 1}
    with pytest.raises(SystemExit):
        lr.require_discovery(p, h, "c")
    for bad in ({"phase": "discovery", "inputs": {"x": 2}, "code_commit": "c"},
                {"phase": "discovery", "inputs": h, "code_commit": "old"},
                {"phase": "verify", "inputs": h, "code_commit": "c"}):
        p.write_text(json.dumps(bad))
        with pytest.raises(SystemExit):
            lr.require_discovery(p, h, "c")
    p.write_text(json.dumps({"phase": "discovery", "inputs": h, "code_commit": "c"}))
    assert lr.require_discovery(p, h, "c")["phase"] == "discovery"


def test_changed_capture_is_refused(tmp_path):
    manifest = json.loads((lr.SPEC_DIR / "PRODUCTION_CAPTURE_MANIFEST.json").read_text())
    for name in manifest["files"]:
        (tmp_path / name).write_text("not the frozen bytes")
    with pytest.raises(SystemExit):
        lr.verify_inputs(tmp_path)
