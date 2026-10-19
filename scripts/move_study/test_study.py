"""Tests for the move study's statistics. Run: python -I -m pytest scripts/move_study -q"""

from __future__ import annotations

import json
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


# ---- volume profile study ------------------------------------------------

import volume_profile_study as vp  # noqa: E402


def test_causal_legs_keep_the_leg_as_first_drawn():
    piv = [{"type": "low", "price": 1.0, "week": 0, "confirmed": 21},
           {"type": "high", "price": 2.0, "week": 28, "confirmed": 49},
           {"type": "high", "price": 3.0, "week": 56, "confirmed": 77}]   # more extreme high replaces the last
    legs = vp.causal_legs(piv)
    assert [(l["low"], l["high"], l["from"]) for l in legs] == [(1.0, 2.0, 49), (1.0, 3.0, 77)]
    assert all(l["direction"] == "up" for l in legs)
    # a less extreme same-type pivot changes nothing
    assert len(vp.causal_legs(piv + [{"type": "high", "price": 2.5, "week": 84, "confirmed": 105}])) == 2


def test_profile_conserves_volume_inside_the_range_and_drops_outside():
    prof = vp.build_profile(np.array([1.0, 1.5]), np.array([2.0, 2.5]), np.array([100.0, 100.0]), 1.0, 2.0, bins=10)
    assert abs(prof.sum() - 150.0) < 1e-9          # first bar fully inside, half of the second
    assert abs(prof[0] - 10.0) < 1e-9 and abs(prof[9] - 20.0) < 1e-9


def test_value_area_and_poc():
    prof = np.array([1, 1, 2, 10, 30, 20, 5, 1, 1, 1], float)
    assert vp.poc_index(prof) == 4
    lo, hi = vp.value_area(prof, 0.70)
    assert (lo, hi) == (3, 5)                      # 30 + 20 + 10 = 60 of 72 = 83% >= 70%


def test_nodes_hvn_and_lvn_need_interior_and_flanks():
    prof = np.linspace(1.0, 2.0, 100)  # no ties, so percentiles bite
    prof[20:25] = 50.0   # high-volume run
    prof[60:63] = 40.0   # second high-volume run
    prof[40:43] = 0.1    # valley between them
    hvn, lvn = vp.nodes(prof)
    assert 22.0 in hvn and 61.0 in hvn
    assert 41.0 in lvn


# ---- absorption study ----------------------------------------------------

import absorption_study as ab  # noqa: E402


def _hours(n=30):
    ts = 1_790_000_000 - (1_790_000_000 % 3600) + 3600 * np.arange(n)
    o = np.full(n, 10.0); h = np.full(n, 10.2); l = np.full(n, 9.8); c = np.full(n, 10.0); v = np.full(n, 100.0)
    return ts, o, h, l, c, v


def _frame(ts, o, h, l, c, v):
    return pd.DataFrame({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})


def test_bullish_two_step_trigger_and_its_rules():
    ts, o, h, l, c, v = _hours()
    i = 25
    o[i], h[i], l[i], c[i], v[i] = 9.9, 10.0, 9.0, 9.8, 300.0      # new 24h low, 3x volume, long lower wick, upper-half close
    o[i + 1], h[i + 1], l[i + 1], c[i + 1] = 9.8, 10.1, 9.5, 10.0   # dips, holds above 9.0, closes up and above 9.8
    t = ab.find_triggers(_frame(ts, o, h, l, c, v))
    assert len(t) == 1 and t[0]["direction"] == "bull" and t[0]["ts"] == ts[i + 1] and t[0]["ref"] == 9.0
    # undercutting bar 1's low before the confirming bar kills it
    l2 = l.copy(); l2[i + 1] = 8.9
    assert ab.find_triggers(_frame(ts, o, h, l2, c, v)) == []
    # not enough volume: no trigger
    v2 = v.copy(); v2[i] = 150.0
    assert ab.find_triggers(_frame(ts, o, h, l, c, v2)) == []
    # a gap in the prior 24 hours: no trigger
    ts2 = ts.copy(); ts2[10:] += 3600
    assert ab.find_triggers(_frame(ts2, o, h, l, c, v)) == []


def test_bearish_trigger_mirror():
    ts, o, h, l, c, v = _hours()
    i = 25
    o[i], h[i], l[i], c[i], v[i] = 10.1, 11.0, 10.0, 10.2, 300.0
    o[i + 1], h[i + 1], l[i + 1], c[i + 1] = 10.2, 10.6, 9.9, 10.0
    t = ab.find_triggers(_frame(ts, o, h, l, c, v))
    assert len(t) == 1 and t[0]["direction"] == "bear" and t[0]["ref"] == 11.0


# ---- funding study ---------------------------------------------------------

import funding_study as fs  # noqa: E402


def test_funding_regimes_and_multipliers():
    assert fs.regime(-0.00001) == "negative" and fs.regime(0.0) == "neutral"
    assert fs.regime(0.0002) == "neutral" and fs.regime(0.00021) == "crowded" and fs.regime(float("nan")) is None
    assert fs.multiplier("1000PEPEUSDT") == 1e3 and fs.multiplier("1000000MOGUSDT") == 1e6
    assert fs.multiplier("kPEPE") == 1e3 and fs.multiplier("RENDERUSDT") == 1.0


def test_binance_window_is_the_24h_ending_at_the_close(tmp_path):
    (tmp_path / "binance").mkdir()
    day = 20000
    t = lambda h: (day * 86400 + h * 3600) * 1000
    rows = ["calc_time,funding_interval_hours,last_funding_rate",
            f"{t(0)},8,0.9",          # exactly at the day's open: belongs to the previous day
            f"{t(8)},8,0.0001", f"{t(16)},4,0.0001", f"{t(24)},8,0.0003",  # in window; 4h print doubles
            f"{t(32)},8,0.9"]         # after the close
    mo = pd.Timestamp(day * 86400, unit="s").strftime("%Y-%m")
    (tmp_path / "binance" / f"XUSDT-{mo}.csv").write_text("\n".join(rows))
    v = fs.binance_day_funding(tmp_path, "XUSDT", day, {})
    assert abs(v - (0.0001 + 0.0002 + 0.0003) / 3) < 1e-12


def test_hl_window_and_8h_scaling(tmp_path):
    (tmp_path / "hl").mkdir()
    day = 20000
    data = [{"fundingRate": "0.00001", "time": (day * 86400 + 3600) * 1000},
            {"fundingRate": "0.00003", "time": ((day + 1) * 86400) * 1000},
            {"fundingRate": "0.5", "time": (day * 86400) * 1000}]
    (tmp_path / "hl" / f"X-{day}.json").write_text(json.dumps(data))
    assert abs(fs.hl_day_funding(tmp_path, "X", day) - 0.00016) < 1e-12


# ---- profile shape study ---------------------------------------------------

import profile_shape_study as ps  # noqa: E402


def test_match_weights_reproduce_the_event_move_mix():
    ev_ = pd.DataFrame({"ret1": [0.05, 0.05, 0.09]})
    ctl = pd.DataFrame({"ret1": [0.051, 0.052, 0.053, 0.091, 0.15]})
    w = ps.match_weights(ev_, ctl).w.values
    assert np.allclose(w[:3], 2 / 3) and w[3] == 1.0 and w[4] == 0.0   # 2 events in the 4-6% bin, 1 in 8-10%, none in 14-16%


def test_cooldown_keeps_first_event_per_coin_and_type():
    df = pd.DataFrame({"product": ["A", "A", "A", "B"], "day": [10, 15, 18, 11], "etype": ["P", "P", "P", "P"]})
    assert list(ps.cooldown(df).day) == [10, 11, 18]
