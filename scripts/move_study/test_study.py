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


# ---- level study ---------------------------------------------------------

import level_study as ls  # noqa: E402


def _weeks(highs, lows, start=20000 - 3):
    idx = [start + 7 * i for i in range(len(highs))]
    return pd.DataFrame({"high": highs, "low": lows, "n": 7}, index=idx)


def test_pivot_confirmed_two_weeks_later_and_strict():
    w = _weeks([1, 2, 5, 3, 2, 2], [0.5, 1, 4, 2, 1, 1])
    piv = ls.confirmed_pivots(w)
    hi = [p for p in piv if p["type"] == "high"]
    assert len(hi) == 1 and hi[0]["price"] == 5 and hi[0]["confirmed"] == w.index[4] + 7
    assert ls.confirmed_pivots(_weeks([1, 2, 5, 5, 2, 1], [0.5, 1, 4, 4, 1, 0.5])) == [] or \
        all(p["price"] != 5 for p in ls.confirmed_pivots(_weeks([1, 2, 5, 5, 2, 1], [0.5, 1, 4, 4, 1, 0.5])))


def test_arrival_needs_approach_from_the_other_side():
    days = np.arange(100, 106)
    hi = np.array([1.0, 1.5, 2.1, 2.3, 1.8, 2.05])
    lo = np.array([0.9, 1.2, 1.9, 2.05, 1.5, 1.7])
    lv = [{"family": "pivot", "placebo": False, "ratio": None, "price": 2.0, "from": 101, "until": 10**9, "pivot_type": "high"}]
    a = ls.arrivals_for("X-USD", lv, days, hi, lo)
    below = [x for x in a if x["side"] == "below"]
    assert [x["day"] for x in below] == [102, 105]          # rises through 2.0 on day 102, again on 105
    assert [x["touch"] for x in a] == list(range(1, len(a) + 1))
    assert any(x["side"] == "above" and x["day"] == 104 for x in a)  # falls back through 2.0 on day 104


def test_macro_versions_use_only_confirmed_pivots_in_order():
    piv = [{"type": "high", "price": 10.0, "week": 1, "confirmed": 15},
           {"type": "low", "price": 2.0, "week": 50, "confirmed": 64},
           {"type": "low", "price": 1.0, "week": 90, "confirmed": 104}]
    v = ls.macro_versions(piv)
    assert [(x["high"], x["low"], x["from"]) for x in v] == [(10.0, 2.0, 64), (10.0, 1.0, 104)]
    assert v[0]["until"] == 104
