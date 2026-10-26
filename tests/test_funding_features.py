"""Synthetic tests for the funding features: lag alignment, print minimum, no forward-fill, duplicates, look-ahead.

No real funding or return data is read. Run: python -m unittest discover -s tests -p test_funding_features.py -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "scripts" / "scoring_experiment"
sys.path.insert(0, str(ROOT))
import funding  # noqa: E402
import panel  # noqa: E402

DAY = 86_400_000
HOUR = 3_600_000
FCFG = json.loads((ROOT / "funding_config.json").read_text(encoding="utf-8"))
T0 = int(pd.Timestamp("2024-01-01").timestamp() * 1000)


def write_pages(folder: Path, stamps, rates):
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{"coin": "X", "fundingRate": repr(float(r)), "premium": "0.0", "time": int(t)} for t, r in zip(stamps, rates)]
    for n, i in enumerate(range(0, len(rows), 500), 1):
        (folder / f"page_{n:04d}.json").write_text(json.dumps({"response_text": json.dumps(rows[i:i + 500])}), encoding="utf-8")
    (folder / "COMPLETE").write_text("x", encoding="utf-8")


def hourly(days, drop=()):
    stamps = [T0 + i * HOUR + 37 for i in range(days * 24) if i not in set(drop)]  # a few ms after the hour
    return stamps


def base_frame(days, products):
    idx = pd.MultiIndex.from_product([pd.date_range("2024-01-01", periods=days), products], names=["date", "product"])
    n = len(idx)
    return pd.DataFrame({"r1": 0.0, "thin": 0.0}, index=idx)


class FundingFeatureTests(unittest.TestCase):
    def test_daily_mean_needs_the_minimum_number_of_prints_and_never_fills(self):
        stamps = hourly(3, drop=range(24, 24 + 6))  # day 2 loses six hours -> 18 prints
        d = pd.DataFrame({"time": stamps, "rate": 1.0, "premium": 0.0, "conflict": False})
        mean, cnt = funding.daily_series(d, 20)
        self.assertEqual(list(cnt), [24, 18, 24])
        self.assertTrue(np.isnan(mean.iloc[1]))
        self.assertEqual(mean.iloc[0], 1.0)

    def test_decision_day_uses_only_the_lagged_funding_day(self):
        days = 80
        rate = np.concatenate([np.full(days * 24, 1e-5)])
        rate[(60 * 24):(61 * 24)] = 5e-4  # a spike only on funding day index 60
        stamps = hourly(days)
        d = pd.DataFrame({"time": stamps, "rate": rate, "premium": 0.0, "conflict": False})
        mean, _ = funding.daily_series(d, 20)
        z = funding.rolling_z(mean, 30, 25)
        lag1 = funding.decision_series(mean, z, 1)
        lag0 = funding.decision_series(mean, z, 0)
        day60 = pd.Timestamp("2024-01-01") + pd.Timedelta(days=60)
        # same-day variant sees the spike on decision day 60; the primary variant first sees it on decision day 61
        self.assertGreater(lag0.loc[day60, "fz_raw"], 3)
        self.assertTrue(np.isnan(lag1.loc[day60, "fz_raw"]) or lag1.loc[day60, "fz_raw"] < 1)
        self.assertGreater(lag1.loc[day60 + pd.Timedelta(days=1), "fz_raw"], 3)

    def test_changing_later_funding_never_changes_earlier_features(self):
        days = 90
        rng = np.random.default_rng(0)
        rate = rng.normal(1e-5, 5e-6, days * 24)
        d1 = pd.DataFrame({"time": hourly(days), "rate": rate, "premium": 0.0, "conflict": False})
        rate2 = rate.copy()
        rate2[70 * 24:] = rng.normal(0.01, 0.01, (days - 70) * 24)
        d2 = d1.assign(rate=rate2)
        z1 = funding.rolling_z(funding.daily_series(d1, 20)[0], 30, 25)
        z2 = funding.rolling_z(funding.daily_series(d2, 20)[0], 30, 25)
        np.testing.assert_allclose(z1.iloc[:70].to_numpy(), z2.iloc[:70].to_numpy(), equal_nan=True)

    def test_build_matched_requires_30_day_warmup_and_no_forward_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            days = 120
            rng = np.random.default_rng(1)
            # product A: continuous; product B: funding stops after day 50 (a delisting tail)
            write_pages(root / "raw" / "A-USD", hourly(days), rng.normal(1e-5, 5e-6, days * 24))
            write_pages(root / "raw" / "B-USD", hourly(50), rng.normal(1e-5, 5e-6, 50 * 24))
            base = base_frame(days, ["A-USD", "B-USD"])
            amap = {"A-USD": {"hyperliquid_name": "A"}, "B-USD": {"hyperliquid_name": "B"}}
            dm, per = funding.build_matched(base, amap, root, FCFG, 1)
            a = dm.xs("A-USD", level="product").index
            b = dm.xs("B-USD", level="product").index
            first = pd.Timestamp("2024-01-01")
            self.assertGreaterEqual((a.min() - first).days, 25 + 1 - 1)  # warm-up: at least 25 valid days + lag
            self.assertLess((b.max() - first).days, 52)                   # nothing carried past the last funding print
            self.assertEqual(per["B-USD"]["raw_rows"], 50 * 24)
            two = dm.groupby(level="date")["r1"].transform("size") >= 2
            self.assertTrue(dm.loc[two, "z_fz"].notna().all())     # rank-normal needs at least two coins that day
            self.assertTrue(dm.loc[~two, "z_fz"].isna().all())

    def test_conflicting_duplicate_stamps_invalidate_the_day(self):
        stamps = hourly(2)
        rates = np.full(48, 1e-5)
        stamps.append(stamps[5])  # the same stamp again with a different rate
        rates = np.append(rates, 9e-4)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_pages(folder, stamps, rates)
            d, st = funding.load_product(folder)
            self.assertEqual(st["conflicting_stamps"], 1)
            mean, _ = funding.daily_series(d, 20)
            self.assertTrue(np.isnan(mean.iloc[0]))
            self.assertFalse(np.isnan(mean.iloc[1]))

    def test_rank_normal_funding_input_is_within_day_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            days = 100
            rng = np.random.default_rng(2)
            prods = [f"P{i}-USD" for i in range(6)]
            for p in prods:
                write_pages(root / "raw" / p, hourly(days), rng.normal(1e-5, 5e-6, days * 24))
            base = base_frame(days, prods)
            amap = {p: {"hyperliquid_name": p} for p in prods}
            dm, _ = funding.build_matched(base, amap, root, FCFG, 1)
            d = dm.index.get_level_values("date")[-1]
            row = dm.xs(d, level="date")["z_fz"]
            self.assertAlmostEqual(float(row.mean()), 0.0, places=6)  # symmetric rank-normal scores


if __name__ == "__main__":
    unittest.main()
