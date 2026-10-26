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
            self.assertTrue(any("overlaps" in p for p in cov["problems"]))
            first = pd.Timestamp(cov["per_product"]["A-USD"]["first_counting"])
            self.assertGreaterEqual((first - pd.Timestamp("2024-01-01")).days, 30 + 24 + 2)  # 25 present days in each half, then the 2-day lag


def approved(pid, slug, path, family=None, **kw):
    e = {"product_id": pid, "status": "approved", "scope": "protocol", "source_ids": {"fees": slug},
         "source_metrics": {"fees": "dailyFees"}, "source_urls": {"fees": f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees"},
         "series_files": {"fees": path.name}, "series_sha256": {"fees": fd.sha256(path)}, "source_family": family or slug,
         "identity_evidence": "synthetic", "reviewer": "test", "reviewed_at": "2026-10-26"}
    e.update(kw)
    return e


class HardenedGateTests(unittest.TestCase):
    """Regressions for the 2026-10-26 review counterexamples."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        self.n = 400
        self.chart = [[T0 + i * 86400, 100 + i] for i in range(self.n)]
        self.days = pd.date_range("2024-01-01", periods=self.n)

    def tearDown(self):
        self.tmp.cleanup()

    def fee(self, slug, **extra):
        return write(self.t / f"{slug}.json", {"slug": slug, "id": slug, "name": slug, "totalDataChart": self.chart, **extra})

    def test_one_product_twenty_entries_is_rejected(self):
        idx = pd.MultiIndex.from_product([self.days, ["A-USD"]], names=["date", "product"])
        f = self.fee("a")
        cohort = [approved("A-USD", "a", f, family=f"claimed-{i}") for i in range(20)]
        with self.assertRaises(ValueError):
            gate.coverage(cohort, self.t, idx)

    def test_cross_section_counts_distinct_products(self):
        idx = pd.MultiIndex.from_product([self.days, ["A-USD", "B-USD"]], names=["date", "product"])
        cohort = [approved("A-USD", "a", self.fee("a")), approved("B-USD", "b", self.fee("b"))]
        cov = gate.coverage(cohort, self.t, idx)
        self.assertEqual(cov["problems"], [])
        self.assertEqual(int(cov["per_day_counts"].max()), 2)

    def test_approved_without_review_provenance_fails_g5(self):
        idx = pd.MultiIndex.from_product([self.days, ["A-USD"]], names=["date", "product"])
        f = self.fee("a")
        e = {"product_id": "A-USD", "status": "approved", "source_ids": {"fees": "a"},
             "series_files": {"fees": f.name}, "series_sha256": {"fees": fd.sha256(f)}}
        cov = gate.coverage([e], self.t, idx)
        self.assertGreater(cov["per_product"]["A-USD"]["counting_rows"], 0)
        for field in ("identity_evidence", "reviewer", "reviewed_at", "source_family"):
            self.assertTrue(any(field in p for p in cov["problems"]), field)
        self.assertTrue(any("source_metrics" in p for p in cov["problems"]))
        self.assertFalse(gate.evaluate_gate(cov["per_day_counts"], cov["problems"])["G5"]["pass"])

    def test_source_id_must_match_capture_and_metric(self):
        idx = pd.MultiIndex.from_product([self.days, ["A-USD"]], names=["date", "product"])
        f = self.fee("a")
        wrong = approved("A-USD", "zzz", f)
        wrong["source_urls"] = {"fees": "https://api.llama.fi/summary/fees/zzz?dataType=dailyRevenue"}
        probs = gate.coverage([wrong], self.t, idx)["problems"]
        self.assertTrue(any("does not match" in p for p in probs))
        self.assertTrue(any("does not request" in p for p in probs))

    def test_parent_child_overlap_is_flagged(self):
        idx = pd.MultiIndex.from_product([self.days, ["A-USD", "B-USD"]], names=["date", "product"])
        parent = self.fee("aero", id="parent#aero", childProtocols=[{"name": "velo"}])
        child = self.fee("velo")
        cohort = [approved("A-USD", "aero", parent, scope="parent"), approved("B-USD", "velo", child)]
        probs = gate.coverage(cohort, self.t, idx)["problems"]
        self.assertTrue(any("overlaps" in p for p in probs))

    def test_g3_counts_only_rows_before_the_embargoed_first_fit(self):
        # 5,000 rows before June 1 (200 days x 25 coins), but only 4,800 before the embargoed May 24 first-fit cutoff
        boundary = pd.Series(25, index=pd.date_range("2023-11-14", "2024-05-31"))
        self.assertEqual(int(boundary[boundary.index < "2024-06-01"].sum()), 5000)
        g3 = gate.evaluate_gate(boundary, [])["G3"]
        self.assertEqual(g3["first_fit_cutoff"], "2024-05-24")
        self.assertEqual(g3["counting_rows_before_first_fit_cutoff_on_20_coin_days"], 4800)
        self.assertFalse(g3["pass"])

    def test_interval_level_is_frozen_explicitly(self):
        cfg = json.loads((Path(gate.HERE) / "fundamentals_config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["bootstrap"]["level"], 0.95)
        self.assertEqual(cfg["primary_horizon_days"], 7)


if __name__ == "__main__":
    unittest.main()
