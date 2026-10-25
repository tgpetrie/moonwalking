"""Tests for the offline baseline: look-ahead, label alignment, purge, scoring, controls.

All tests use small synthetic panels; none reads the real data or any outcome.
Run: python -m unittest discover -s tests -p test_scoring_experiment.py -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "scripts" / "scoring_experiment"
sys.path.insert(0, str(ROOT))
import evaluate as ev  # noqa: E402
import model  # noqa: E402
import panel  # noqa: E402

CFG = panel.load_config()


def synthetic(days=320, coins=30, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=days, freq="D")
    cols = ["BTC-USD"] + [f"C{i}-USD" for i in range(coins)]
    ret = rng.normal(0, 0.03, (days, len(cols)))
    close = 100 * np.exp(np.cumsum(ret, axis=0))
    opn = close * np.exp(rng.normal(0, 0.002, close.shape))
    hi = np.maximum(opn, close) * 1.01
    lo = np.minimum(opn, close) * 0.99
    vol = rng.uniform(1e5, 1e6, close.shape) / close
    f = {k: pd.DataFrame(v, index=idx, columns=cols) for k, v in
         dict(open=opn, high=hi, low=lo, close=close, volume=vol).items()}
    return f


class FeatureTests(unittest.TestCase):
    def test_features_ignore_the_future(self):
        f = synthetic()
        base = panel.build_features(f, CFG)
        cut = 200
        g = {k: v.copy() for k, v in f.items()}
        for k in g:
            g[k].iloc[cut + 1:] = np.random.default_rng(9).uniform(1, 1000, g[k].iloc[cut + 1:].shape)
        alt = panel.build_features(g, CFG)
        d = f["close"].index[cut]
        for k in panel.FEATURES:
            a = base["features"][k].loc[:d].to_numpy()
            b = alt["features"][k].loc[:d].to_numpy()
            np.testing.assert_allclose(a, b, equal_nan=True, err_msg=k)
        self.assertTrue((base["eligible"].loc[:d].to_numpy() == alt["eligible"].loc[:d].to_numpy()).all())
        # labels at the cut date DO depend on later data (they are the future)
        self.assertFalse(np.allclose(base["labels"]["y1"].loc[d].to_numpy(), alt["labels"]["y1"].loc[d].to_numpy(),
                                     equal_nan=True))

    def test_label_uses_next_day_open_to_open_and_btc_residual(self):
        f = synthetic()
        built = panel.build_features(f, CFG)
        d = f["close"].index[250]
        p = "C3-USD"
        o = f["open"]
        i = o.index.get_loc(d)
        coin = np.log(o[p].iloc[i + 2] / o[p].iloc[i + 1])
        btc = np.log(o["BTC-USD"].iloc[i + 2] / o["BTC-USD"].iloc[i + 1])
        beta = built["features"]["beta90"].at[d, p]
        vol = built["features"]["vol30"].at[d, p]
        self.assertAlmostEqual(built["labels"]["y1"].at[d, p], (coin - beta * btc) / vol, places=10)
        self.assertAlmostEqual(built["labels"]["rawret1"].at[d, p], o[p].iloc[i + 2] / o[p].iloc[i + 1] - 1, places=12)

    def test_gaps_are_not_filled_and_block_eligibility(self):
        f = synthetic()
        for k in f:
            f[k].loc[f[k].index[150:175], "C5-USD"] = np.nan  # a 25-day hole
        built = panel.build_features(f, CFG)
        d = f["close"].index[160]
        self.assertTrue(np.isnan(built["features"]["r1"].at[d, "C5-USD"]))
        self.assertFalse(built["eligible"].at[d, "C5-USD"])
        self.assertFalse(built["eligible"]["BTC-USD"].any())

    def test_pegged_coin_is_excluded(self):
        f = synthetic()
        for k in ("open", "high", "low", "close"):
            f[k]["C7-USD"] = 1.0 + np.random.default_rng(3).normal(0, 1e-4, len(f[k]))
        f["high"]["C7-USD"] = f["close"]["C7-USD"] * 1.0001
        f["low"]["C7-USD"] = f["close"]["C7-USD"] * 0.9999
        f["open"]["C7-USD"] = f["close"]["C7-USD"]
        built = panel.build_features(f, CFG)
        self.assertFalse(built["eligible"]["C7-USD"].any())

    def test_rank_normal_uses_only_the_same_day(self):
        f = synthetic()
        b1 = panel.stack_long(panel.build_features(f, CFG), CFG)
        g = {k: v.copy() for k, v in f.items()}
        for k in g:
            g[k].iloc[250:] = g[k].iloc[250:] * 1.7  # change the later days only
        b2 = panel.stack_long(panel.build_features(g, CFG), CFG)
        d = f["close"].index[200]
        a = b1.xs(d, level="date")[["z_r1", "z_relvol"]]
        c = b2.xs(d, level="date")[["z_r1", "z_relvol"]]
        np.testing.assert_allclose(a.to_numpy(), c.to_numpy(), equal_nan=True)

    def test_norm_ppf(self):
        np.testing.assert_allclose(panel.norm_ppf(np.array([0.5, 0.975, 0.025, 0.9, 0.001])),
                                   [0.0, 1.959964, -1.959964, 1.281552, -3.090232], atol=1e-5)


class ModelTests(unittest.TestCase):
    def setUp(self):
        f = synthetic(days=420, coins=40)
        self.cfg = {**CFG, "min_cross_section": 20}
        self.df = panel.stack_long(panel.build_features(f, self.cfg), self.cfg)
        self.df = self.df[self.df["n_day"] >= 20]

    def test_daily_ic_matches_manual_spearman_with_ties(self):
        idx = pd.MultiIndex.from_product([pd.date_range("2024-01-01", periods=3), list("abcdefghijklmnopqrstu")],
                                         names=["date", "product"])
        rng = np.random.default_rng(0)
        p = pd.Series(np.round(rng.normal(size=len(idx)), 1), index=idx)
        y = pd.Series(np.round(rng.normal(size=len(idx)), 1), index=idx)
        got = model.daily_ic(p, y, 5)
        for d, g in pd.DataFrame({"p": p, "y": y}).groupby(level="date"):
            rp, ry = g["p"].rank().to_numpy(), g["y"].rank().to_numpy()
            self.assertAlmostEqual(got[d], float(np.corrcoef(rp, ry)[0, 1]), places=10)

    def test_training_rows_end_before_the_embargo_cutoff(self):
        seen = []
        orig = model._prepare_target

        def spy(df, mask, ycol, pct):
            seen.append(df.index.get_level_values("date")[mask].max())
            return orig(df, mask, ycol, pct)

        model._prepare_target = spy
        try:
            start = "2024-10-01"
            pred, contrib, log = model.walk_forward(self.df, 1, {**self.cfg, "ridge_grid": [10.0, 100.0]},
                                                    start, start)
        finally:
            model._prepare_target = orig
        self.assertTrue(log and seen)
        cutoff = pd.Timestamp(start) - pd.Timedelta(days=8)
        self.assertTrue(all(t < cutoff for t in seen), seen)
        dates = pred.dropna().index.get_level_values("date")
        self.assertGreaterEqual(dates.min(), pd.Timestamp(start))
        self.assertLess(dates.max(), pd.Timestamp("2024-11-01"))

    def test_contributions_sum_to_prediction(self):
        pred, contrib, _ = model.walk_forward(self.df, 1, {**self.cfg, "ridge_grid": [10.0]}, "2024-10-01", "2024-10-01")
        ok = pred.notna()
        np.testing.assert_allclose(contrib[ok].sum(axis=1).to_numpy(), pred[ok].to_numpy(), atol=1e-5)

    def test_score_is_ordinal_one_to_hundred_and_same_day_only(self):
        pred = pd.Series(np.random.default_rng(2).normal(size=len(self.df)), index=self.df.index)
        s = model.to_score(pred)
        self.assertTrue(s.min() >= 1 and s.max() <= 100)
        d = self.df.index.get_level_values("date")[500]
        day = s.xs(d, level="date")
        order = pred.xs(d, level="date").rank()
        self.assertTrue((day.rank() == order).all() or day.corr(order, method="spearman") > 0.999)
        pred2 = pred.copy()
        pred2[self.df.index.get_level_values("date") != d] += 5.0
        s2 = model.to_score(pred2)
        pd.testing.assert_series_equal(s.xs(d, level="date"), s2.xs(d, level="date"))


class EventTests(unittest.TestCase):
    def test_controls_are_same_coin_clean_and_in_period(self):
        f = synthetic(days=420, coins=40)
        cfg = {**CFG, "min_cross_section": 20}
        df = panel.stack_long(panel.build_features(f, cfg), cfg)
        df = df[df["n_day"] >= 20]
        events = ev.flag_events(df, cfg)
        self.assertTrue(set(events.unique()) <= {"", "exhaustion", "continuation", "capitulation", "downside_continuation"})
        sub, meta, pairs = ev.match_controls(df, events, cfg, ("2024-08-01", "2025-01-31"))
        self.assertTrue(pairs)
        gap = pd.Timedelta(days=cfg["event"]["control_min_gap_days"])
        for i, ctrl in pairs[:200]:
            coin = meta.at[i, "prod"]
            ev_dates = meta[(meta["prod"] == coin) & (meta["ev"] != "")]["date"]
            for c in ctrl:
                self.assertEqual(meta.at[c, "prod"], coin)
                self.assertEqual(meta.at[c, "ev"], "")
                self.assertTrue((abs(ev_dates - meta.at[c, "date"]) > gap).all())
                self.assertEqual(meta.at[c, "vq"], meta.at[i, "vq"])


if __name__ == "__main__":
    unittest.main()
