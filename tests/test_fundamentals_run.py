"""Synthetic tests for the fundamentals comparison driver. Labels here are random numbers; no market data is read.

Run: python -m unittest discover -s tests -p test_fundamentals_run.py -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "scoring_experiment"))
import fundamentals as fd  # noqa: E402
import fundamentals_run as fr  # noqa: E402
import panel  # noqa: E402

T0 = int(pd.Timestamp("2024-01-01").timestamp())


def setup_world(tmp: Path, n_prod=22, n_days=300, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2024-01-01", periods=n_days)
    prods = [f"P{i}-USD" for i in range(n_prod)]
    idx = pd.MultiIndex.from_product([days, prods], names=["date", "product"])
    base = pd.DataFrame({"y1": rng.normal(size=len(idx)), "y7": rng.normal(size=len(idx)), "btc30": 0.0}, index=idx)
    for f in panel.FEATURES:
        base["z_" + f] = rng.normal(size=len(idx))
    cohort = []
    for i, p in enumerate(prods):
        chart = [[T0 + k * 86400, float(100 + rng.uniform(0, 50))] for k in range(n_days)]
        path = tmp / f"{p}.json"
        path.write_text(json.dumps({"slug": p, "totalDataChart": chart}), encoding="utf-8")
        cohort.append({"product_id": p, "status": "approved", "scope": "chain" if i == 0 else "protocol",
                       "series_files": {"fees": path.name}, "series_sha256": {"fees": fd.sha256(path)}})
    return base, cohort


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_matched_rows_respect_lag_and_day_rule(self):
        base, cohort = setup_world(self.t)
        dm, _ = fr.build_matched(base, cohort, self.t, lag=2, min_n=20)
        first = dm.index.get_level_values("date").min()
        # 25 present days in the recent half and in the half 30 days earlier -> first defined on day 24 + 30, then the 2-day lag
        self.assertEqual(first, pd.Timestamp("2024-01-01") + pd.Timedelta(days=24 + 30 + 2))
        self.assertTrue((dm["n_matched_day"] >= 20).all())
        held = [dict(cohort[0], status="held")] + cohort[1:]
        dm2, _ = fr.build_matched(base, held, self.t, lag=2, min_n=22)
        self.assertEqual(len(dm2), 0)  # 21 approved coins never reach a 22-coin day

    def test_rows_without_s0_are_dropped_not_zero_filled(self):
        base, cohort = setup_world(self.t)
        dm, _ = fr.build_matched(base, cohort, self.t, lag=2, min_n=20)
        s0 = pd.Series(np.random.default_rng(1).normal(size=len(dm)), index=dm.index)
        s0.iloc[::7] = np.nan
        d = fr.horizon_rows(dm, s0, 7, 20)
        self.assertFalse(d["z_s0_7"].isna().any())
        self.assertTrue(d.index.isin(s0.dropna().index).all())
        self.assertTrue((d.groupby(level="date").size() >= 20).all())

    def test_first_fit_readiness_uses_availability_and_embargo(self):
        days = pd.date_range("2024-01-01", "2024-06-30")
        idx = pd.MultiIndex.from_product([days, [f"P{i}" for i in range(30)]], names=["date", "product"])
        d = pd.DataFrame({"z_a": 0.0, "y7": 1.0}, index=idx)
        # 30 rows/day: 5,000 rows need 167 days dated before (month start - 8 days)
        self.assertEqual(fr.first_fit_readiness(d, 7, "2024-01-01", "2024-07-01", ["a"])["first_fit_month"], "2024-07-01")
        d.loc[d.index.get_level_values("date") < "2024-02-01", "y7"] = np.nan   # labels not available
        self.assertIsNone(fr.first_fit_readiness(d, 7, "2024-01-01", "2024-07-01", ["a"])["first_fit_month"])
        d2 = pd.DataFrame({"z_a": 0.0, "y7": -5.0}, index=idx)  # label values do not matter, only presence
        self.assertEqual(fr.first_fit_readiness(d2, 7, "2024-01-01", "2024-07-01", ["a"])["first_fit_month"], "2024-07-01")

    def test_verdict_rules(self):
        good = {"mean": 0.03, "lo": 0.01, "hi": 0.05, "moving_block": {"lo": 0.005}}
        self.assertEqual(fr.verdict(good, 0.01, 0.02, True), "supportive")
        self.assertEqual(fr.verdict(good, -0.01, 0.02, True), "inconclusive")
        self.assertEqual(fr.verdict(good, 0.01, 0.02, False), "inconclusive")
        self.assertEqual(fr.verdict({**good, "moving_block": {"lo": -0.001}}, 0.01, 0.02, True), "inconclusive")
        self.assertEqual(fr.verdict({"mean": 0.0, "lo": -0.01, "hi": 0.015}, 0.01, 0.02, True), "ruled out")
        self.assertEqual(fr.verdict({"mean": None, "lo": None, "hi": None}, 0.01, 0.02, True), "inconclusive")

    def test_test_phase_refuses_without_matching_discovery(self):
        p = self.t / "disc.json"
        with self.assertRaises(SystemExit):
            fr.require_discovery(p, "h", "c")
        for bad in ({"phase": "discovery", "provenance": {"combined_hash": "other"}, "code_commit": "c"},
                    {"phase": "discovery", "provenance": {"combined_hash": "h"}, "code_commit": "old"},
                    {"phase": "readiness", "provenance": {"combined_hash": "h"}, "code_commit": "c"}):
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(SystemExit):
                fr.require_discovery(p, "h", "c")
        p.write_text(json.dumps({"phase": "discovery", "provenance": {"combined_hash": "h"}, "code_commit": "c"}), encoding="utf-8")
        self.assertEqual(fr.require_discovery(p, "h", "c")["phase"], "discovery")

    def test_provenance_rejects_changed_capture_and_uses_frozen_level(self):
        _, cohort = setup_world(self.t, n_prod=3)
        cpath = self.t / "cohort.json"
        cpath.write_text(json.dumps(cohort), encoding="utf-8")
        cfg, fcfg = panel.load_config(), fr.fcfg_load()
        p = fr.provenance(cfg, fcfg, cpath, cohort, self.t)
        self.assertEqual(len(p["fee_file_sha256"]), 3)
        self.assertEqual(fr.eval_cfg(cfg, fcfg)["bootstrap"]["level"], 0.95)
        self.assertEqual(cfg["bootstrap"]["level"], 0.975)  # baseline config untouched
        (self.t / cohort[1]["series_files"]["fees"]).write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            fr.provenance(cfg, fcfg, cpath, cohort, self.t)

    def test_run_lag_produces_paired_and_secondary_results(self):
        base, cohort = setup_world(self.t, n_days=330)
        cfg = {**panel.load_config(), "horizons_days": [7]}
        ecfg = fr.eval_cfg(cfg, fr.fcfg_load())
        full = {7: pd.Series(np.random.default_rng(3).normal(size=len(base)), index=base.index)}
        res = fr.run_lag(base, full, cohort, self.t, cfg, ecfg, {}, 2, ("2024-01-01", "2024-11-25"), "2024-01-01", "2024-11-01",
                         [-1.0, 1.0], primary=True)
        h = res["horizons"]["h7"]
        self.assertIn("incremental_ic_s1_minus_s0", h)
        self.assertIn("matched_trained_secondary", h)
        self.assertGreater(h["rows"]["scored_in_period"], 0)


if __name__ == "__main__":
    unittest.main()
