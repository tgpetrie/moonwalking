"""Synthetic tests for the fundamentals features and the coverage gate. No real series, returns or labels are read.

Run: python -m unittest discover -s tests -p test_fundamentals.py -v
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
import fundamentals_gate as gate  # noqa: E402

T0 = int(pd.Timestamp("2024-01-01").timestamp())


def write(path: Path, doc) -> Path:
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


class ParseTests(unittest.TestCase):
    def test_three_shapes_duplicates_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            fees = write(t / "f.json", {"totalDataChart": [[T0, 1], [T0 + 86400, 2], [T0 + 86400, 5], [T0 + 3 * 86400, 0]]})
            prot = write(t / "p.json", {"tvl": [{"date": T0, "totalLiquidityUSD": 10}, {"date": T0 + 86400, "totalLiquidityUSD": 11}]})
            chain = write(t / "c.json", [{"date": T0, "tvl": 7}, {"date": T0 + 2 * 86400, "tvl": 9}])
            s, info = fd.parse_series(fees)
            self.assertEqual(info["duplicate_dates"], 1)
            self.assertEqual(s.iloc[1], 5)            # last returned value kept
            self.assertTrue(np.isnan(s.iloc[2]))      # absent date stays missing
            self.assertEqual(s.iloc[3], 0)            # explicit zero stays zero
            self.assertEqual(info["missing_inside_span"], 1)
            self.assertEqual(fd.parse_series(prot)[0].iloc[-1], 11)
            c, ci = fd.parse_series(chain)
            self.assertEqual(ci["missing_inside_span"], 1)


class TrendTests(unittest.TestCase):
    def series(self, n=200, seed=0):
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2024-01-01", periods=n, freq="D")
        return pd.Series(rng.uniform(100, 200, n), index=idx)

    def test_definition_matches_manual_computation(self):
        s = self.series()
        t, _ = fd.trend(s)
        L = s.index[150]
        recent = s.loc[L - pd.Timedelta(days=29): L].mean()
        prior = s.loc[L - pd.Timedelta(days=59): L - pd.Timedelta(days=30)].mean()
        self.assertAlmostEqual(t.loc[L], np.log(recent) - np.log(prior), places=12)

    def test_requires_25_present_days_per_half(self):
        s = self.series()
        s.iloc[121:127] = np.nan  # six missing days inside the recent half for L = index 150
        t, r = fd.trend(s)
        self.assertTrue(np.isnan(t.iloc[150]))
        self.assertGreater(r["too_few_present_days"], 0)
        self.assertTrue(np.isfinite(t.iloc[190]))

    def test_pinned_or_zero_series_is_missing(self):
        s = self.series()
        s.iloc[100:200] = 1.25e-5           # pinned at a constant
        t, r = fd.trend(s)
        self.assertTrue(np.isnan(t.iloc[190]))
        z = self.series()
        z.iloc[:] = 0.0
        self.assertTrue(fd.trend(z)[0].isna().all())

    def test_past_only_and_lag(self):
        s = self.series()
        t1, _ = fd.trend(s)
        s2 = s.copy()
        s2.iloc[151:] = s2.iloc[151:] * 50
        t2, _ = fd.trend(s2)
        np.testing.assert_allclose(t1.iloc[:151].to_numpy(), t2.iloc[:151].to_numpy(), equal_nan=True)
        dec = fd.to_decision_dates(t1, 2)
        self.assertEqual(dec.loc[s.index[150] + pd.Timedelta(days=2)], t1.loc[s.index[150]])

    def test_tvl_change_needs_both_dates_and_never_fills(self):
        s = self.series()
        s.iloc[100] = np.nan
        ch = fd.level_change(s)
        self.assertTrue(np.isnan(ch.iloc[130]))   # L-30 missing
        self.assertTrue(np.isnan(ch.iloc[100]))   # L missing
        self.assertAlmostEqual(ch.iloc[140], np.log(s.iloc[140] / s.iloc[110]))


class GateTests(unittest.TestCase):
    def test_gate_passes_only_with_enough_coins_weeks_and_history(self):
        days = pd.date_range("2023-06-01", "2026-10-10", freq="D")
        good = pd.Series(25, index=days)
        res = gate.evaluate_gate(good, [])
        self.assertTrue(res["gate_passed"])
        thin = pd.Series(19, index=days)
        self.assertFalse(gate.evaluate_gate(thin, [])["gate_passed"])
        late = good[good.index >= "2025-01-01"]
        r = gate.evaluate_gate(late, [])
        self.assertFalse(r["G3"]["pass"])
        self.assertFalse(r["G4"]["pass"])
        self.assertFalse(gate.evaluate_gate(good, ["held entry counted"])["gate_passed"])

    def test_coverage_excludes_held_and_flags_hash_and_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            n = 400
            chart = [[T0 + i * 86400, 100 + i] for i in range(n)]
            f = write(t / "a.json", {"totalDataChart": chart})
            idx = pd.MultiIndex.from_product([pd.date_range("2024-01-01", periods=n), ["A-USD", "B-USD", "C-USD"]], names=["date", "product"])
            good = fd.sha256(f)
            cohort = [
                {"product_id": "A-USD", "status": "approved", "source_ids": {"fees": "a"}, "series_files": {"fees": "a.json"}, "series_sha256": {"fees": good}},
                {"product_id": "B-USD", "status": "held", "source_ids": {"fees": "b"}, "series_files": {"fees": "a.json"}, "series_sha256": {"fees": good}},
                {"product_id": "C-USD", "status": "approved", "source_ids": {"fees": "a"}, "series_files": {"fees": "a.json"}, "series_sha256": {"fees": "x"}},
                {"product_id": "BTC-USD", "status": "approved"},
            ]
            cov = gate.coverage(cohort, t, idx)
            self.assertEqual(cov["per_product"]["B-USD"]["excluded"], "not approved")
            self.assertEqual(cov["per_product"]["BTC-USD"]["excluded"], "benchmark")
            self.assertGreater(cov["per_product"]["A-USD"]["counting_rows"], 0)
            self.assertTrue(any("hash mismatch" in p for p in cov["problems"]))
            self.assertTrue(any("also used by" in p for p in cov["problems"]))
            first = pd.Timestamp(cov["per_product"]["A-USD"]["first_counting"])
            self.assertGreaterEqual((first - pd.Timestamp("2024-01-01")).days, 30 + 24 + 2)  # 25 present days in each half, then the 2-day lag


if __name__ == "__main__":
    unittest.main()
