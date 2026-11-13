"""Synthetic checks for step 2 candle features. No market data."""
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c", ROOT / "scripts/scoring_experiment/screen_runner_candles.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def series(ts, o, cl, v):
    return (np.array(ts), np.array(o, float), np.array(cl, float), np.array(v, float))


def test_no_lookahead():
    t = 6000 + 30  # k = 5940; the 6000 and 6060 candles are not closed and must not be read
    ts = list(range(5940 - 60 * 14, 6061, 60))
    n = len(ts)
    closes = [1.0] * (n - 3) + [1.01, 99.0, 99.0]
    coin = series(ts, [1.0] * n, closes, [10.0] * n)
    btc = series(ts, [100.0] * n, [100.0] * n, [1.0] * n)
    f = c.candle_features(t, coin, btc, 1.0, 2.0)
    assert f["active15"] == 15
    assert np.isclose(f["3B"], np.log1p(10 * (1.0 + 1.0 + 1.01)))
    assert np.isclose(f["5A"], 1.0)  # close(k)/open(k-120) = 1.01, BTC flat
    assert np.isfinite(f["2A"]) and f["2A"] > 0


def test_missing_data_is_unavailable_not_zero():
    assert all(np.isnan(v) for v in c.candle_features(6000, None, None, 1.0, 1.0).values())
    coin = series([5940], [1.0], [1.0], [1.0])  # under 10 traded minutes and no k-120 endpoint
    f = c.candle_features(6030, coin, coin, 1.0, 1.0)
    assert np.isnan(f["2A"]) and np.isnan(f["5A"]) and f["active15"] == 1 and np.isfinite(f["3B"])


def test_btc_wave_zeroes_relative_move():
    ts = [5820, 5880, 5940]
    coin = series(ts, [1.0] * 3, [1.0, 1.0, 1.05], [1.0] * 3)
    btc = series(ts, [100.0] * 3, [100.0, 100.0, 101.0], [1.0] * 3)
    assert c.candle_features(6030, coin, btc, 1.0, 5.0)["5A"] == 0.0
