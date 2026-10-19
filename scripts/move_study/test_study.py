"""Tests for the move study's statistics. Run: python -I -m pytest scripts/move_study -q"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402


def events(effect: float, n_days: int = 120, per_day: int = 5, seed: int = 1, horizon: int = 1) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    days = np.arange(20000, 20000 + n_days)
    rows = [{"day": d, "product": f"C{i}-USD", f"m{horizon}": effect + rng.normal(0, 0.05)} for d in days for i in range(per_day)]
    return pd.DataFrame(rows), days


def test_bootstrap_detects_a_real_effect():
    ev, days = events(-0.02)
    out = cs.summarise(ev, days, 1, (int(days[0]), int(days[-1])), np.random.default_rng(0), col="m")
    assert out["mean_excess_pct"] < -1.5 and out["p_raw"] < 0.01 and out["ci95_pct"][1] < 0


def test_bootstrap_does_not_invent_an_effect():
    ev, days = events(0.0)
    out = cs.summarise(ev, days, 1, (int(days[0]), int(days[-1])), np.random.default_rng(0), col="m")
    assert out["p_raw"] > 0.05 and out["ci95_pct"][0] < 0 < out["ci95_pct"][1]


def test_embargo_drops_events_whose_window_crosses_the_boundary():
    ev, days = events(-0.02, n_days=30, horizon=7)
    end = int(days[10])
    out = cs.summarise(ev, days, 7, (int(days[0]), end), np.random.default_rng(0), col="m")
    assert out["events"] == 5 * (10 - 7 + 1)  # days 0..3 only


def test_p_value_floor_is_one_over_resamples():
    ev, days = events(-0.5, per_day=10)
    out = cs.summarise(ev, days, 1, (int(days[0]), int(days[-1])), np.random.default_rng(0), col="m")
    assert out["p_raw"] == round(1 / cs.BOOT, 5)


def test_robustness_stats_trims_and_winsorises():
    import robustness as rb
    x = pd.Series([-0.1] * 18 + [5.0, 6.0])
    s = rb.stats(x)
    assert s["n"] == 20 and s["median_pct"] == -10.0
    assert s["trimmed10_pct"] == -10.0  # the two outliers are trimmed away
    assert s["mean_pct"] > s["winsor5_pct"] > s["median_pct"]
