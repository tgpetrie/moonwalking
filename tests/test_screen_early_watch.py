"""Synthetic checks for the early-watch screen: no look-ahead in features, outcomes read the future only."""
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ew", ROOT / "scripts/scoring_experiment/screen_early_watch.py")
ew = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ew)


def market(seed=3, products=30, minutes=1700):
    rng = np.random.default_rng(seed)
    close = 10 * np.exp(np.cumsum(rng.normal(0, 0.004, (products, minutes)), axis=1))
    high, low = close * (1 + rng.uniform(0, 0.003, close.shape)), close * (1 - rng.uniform(0, 0.003, close.shape))
    vol = rng.uniform(1, 100, close.shape)
    return close, high, low, vol, np.ones(close.shape), np.ones(products, bool)


def test_features_do_not_read_the_future():
    close, high, low, vol, traded, elig = market()
    base = ew.features(close, high, low, vol, traded, 0, elig)
    j = 1600
    c2, h2, l2, v2 = close.copy(), high.copy(), low.copy(), vol.copy()
    c2[:, j + 1:] *= 3.0
    h2[:, j + 1:] *= 3.0
    l2[:, j + 1:] *= 3.0
    v2[:, j + 1:] *= 7.0
    changed = ew.features(c2, h2, l2, v2, traded, 0, elig)
    for key, value in base.items():
        assert np.array_equal(value[:, : j + 1], changed[key][:, : j + 1], equal_nan=True), key
    assert base["cand"][:, 1500:].any()


def test_candidates_exclude_top_eight_and_need_a_move():
    close, high, low, vol, traded, elig = market()
    f = ew.features(close, high, low, vol, traded, 0, elig)
    assert not (f["cand"] & f["top"]).any()
    assert (f["r3"][f["cand"]] > 0.30).all()
    assert f["top"][:, 1600].sum() >= 8
    assert not f["universe"][:, :3].any()          # no 3-minute return yet


def test_outcomes_use_only_later_closes():
    close = np.full((9, 40), 10.0)
    close[0, 11:] = 10.2                             # +2% from column 11 on
    close[1, 11:] = 9.8
    top = np.zeros(close.shape, bool)
    o = ew.outcomes(close, top)
    assert o["runner"][0, 10] and not o["runner"][0, 11]      # after the jump there is nothing left to gain
    assert o["crasher"][1, 10] and not o["crasher"][0, 10]
    assert not o["gradable"][0, 30]                           # fewer than 15 minutes of future
    past = close.copy()
    past[:, :10] = 1.0
    assert np.array_equal(ew.outcomes(past, top)["runner"][:, 10:], o["runner"][:, 10:])
