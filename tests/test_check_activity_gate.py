"""Synthetic checks for the activity gate test. No market data."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = load("check_activity_gate")


def candles(ts, usd):
    return (np.array(ts), np.array(usd, float))


def whole(lo, hi):
    return g.merge_windows([lo], [hi])


def test_reads_only_minutes_closed_before_entry():
    t = 6000 + 30  # k = 5940; the 6000 candle is still open
    c = candles([5760, 5820, 5880, 5940, 6000], [1000.0, 1.0, 2.0, 4.0, 999.0])
    a = g.activity(t, c, whole(0, 9000))
    assert a["D3"] == 7.0 and a["n3"] == 3 and not a["unknown"]
    delayed = g.activity(t, c, whole(0, 9000), 1)
    assert delayed["D3"] == 1003.0  # 5760, 5820, 5880


def test_fetched_minute_without_trades_is_zero_but_unfetched_minute_is_unknown():
    c = candles([5940], [5.0])
    known = g.activity(6030, c, whole(5000, 7000))
    assert known["D3"] == 5.0 and known["n3"] == 1 and not known["unknown"]
    gap = g.activity(6030, c, whole(5880, 7000))  # 5820 lies outside every fetch window
    assert gap["D3"] == 5.0 and gap["unknown"]
    never = g.activity(6030, None, None)
    assert never["D3"] == 0.0 and never["n3"] == 0 and never["unknown"]


def test_adjacent_fetch_windows_merge_and_gaps_stay_gaps():
    starts, ends = g.merge_windows([0, 300, 1200], [240, 540, 1500])
    assert list(starts) == [0, 1200] and list(ends) == [540, 1500]
    assert g.covered((starts, ends), 540) and not g.covered((starts, ends), 600) and g.covered((starts, ends), 1200)


def frame(days=10, per_day=400, seed=1):
    rng = np.random.default_rng(seed)
    n = days * per_day
    day = np.repeat(pd.date_range("2026-01-01", periods=days).strftime("%Y-%m-%d"), per_day)
    d3 = np.where(rng.random(n) < 0.3, 0.0, rng.lognormal(5, 2, n))
    return pd.DataFrame({"id": np.arange(n), "entered_ts": np.arange(n), "day": day, "B0": rng.lognormal(0, 1, n), "D3": d3,
                         "unknown": rng.random(n) < 0.05, "n3": 3, "runner": 0, "crasher": 0})


@pytest.mark.parametrize("gate", ["M", "Z"])
def test_both_rules_aim_at_the_same_budget(gate):
    f = g.build_flags(frame(), "D3", "unknown", gate, "zero")
    s = f[f["scored"]]
    assert set(s["day"]) == {"2026-01-08", "2026-01-09", "2026-01-10"}  # needs seven earlier days
    assert abs(s["a0"].mean() - 0.25) < 0.04 and abs(s["a1"].mean() - 0.25) < 0.04
    assert not (s["a1"] & ~s["pass"]).any() and (s.loc[s["pass"], "D3"] > 0).all()
    per_day = s.groupby("day")[["a0_full_day", "a1_full_day"]].sum()
    assert (per_day == 100).all().all()


def test_entry_time_flags_ignore_the_rest_of_the_day_and_later_days():
    base = frame()
    a = g.build_flags(base, "D3", "unknown", "M", "zero")
    changed = base.copy()
    last = changed["day"] == "2026-01-10"
    keep = a.index[last & a["a0_full_day"] & a["a0"]][0]  # frame() is already in entry order, so indexes line up
    other = last & (changed.index != keep)
    changed.loc[other, "B0"] *= 100
    changed.loc[other, "D3"] *= 100
    b = g.build_flags(changed, "D3", "unknown", "M", "zero")
    before = a["day"] < "2026-01-10"
    for col in ("a0", "a1", "pass"):
        assert (a.loc[before, col] == b.loc[before, col]).all()
        assert a.loc[keep, col] == b.loc[keep, col]
    assert a.loc[keep, "a0_full_day"] and not b.loc[keep, "a0_full_day"]  # the full-day ranking does look ahead


def test_unknown_gap_policies():
    act, unk = np.array([0.0, 0.0, 5.0, 50.0]), np.array([True, False, False, False])
    assert list(g.passes(act, unk, 10.0, "M", "zero")) == [False, False, False, True]
    assert list(g.passes(act, unk, 10.0, "M", "pass")) == [True, False, False, True]
    assert list(g.passes(act, unk, 10.0, "Z", "zero")) == [False, False, True, True]
    f = frame()
    assert not g.run_variant(f, "gate_M_unknown_gaps_removed")["unknown"].any()


def test_runners_missed_and_reversals_avoided_are_counted():
    n = 24
    f = pd.DataFrame({"day": "2026-01-08", "scored": True, "runner": 0, "crasher": 0, "pass": True, "a0": False, "a1": False}, index=range(n))
    f.loc[0:5, "a0"] = True          # rows 0-5 flagged by the baseline
    f.loc[2:7, "a1"] = True          # rows 2-7 flagged by the gated rule
    f.loc[[0, 1], "pass"] = False    # rows 0 and 1 fail the gate
    f.loc[[0, 2], "runner"] = 1
    f.loc[[1, 3, 6], "crasher"] = 1
    s = g.summarize(f, "a0", "a1", "2026-01-01", "2026-01-31", True)
    c = s["counts"]
    assert s["alerts"]["a0_total"] == 6 and s["alerts"]["a1_total"] == 6
    assert c["a0_only_removed"] == {"alerts": 2, "runners": 1, "crashers": 1}
    assert c["a1_only_added"] == {"alerts": 2, "runners": 0, "crashers": 1}
    assert c["net_runners_missed"] == 1 and c["net_reversals_avoided"] == 0
    assert c["veto_without_replacement"]["runners"] == 1 and c["veto_without_replacement"]["runner_recall"] == 0.5
    assert np.isclose(s["delta_P"]["mean"], 1 / 6 - 2 / 6) and np.isclose(s["delta_C"]["mean"], 0.0)


def test_labels_match_step_one():
    s = load("screen_runner_signals")
    rng = np.random.default_rng(3)
    n = 500
    df = pd.DataFrame({"id": np.arange(n), "board": "confirmation_3m_up", "product_id": "A-USD", "direction": "up",
                       "entered_ts": 1_790_000_000 + np.arange(n) * 4000, "start_change_pct": 1.0, "pct_1m": 0.5, "pct_3m": 1.0,
                       "vol": 0.0, "liquidity": "normal", "trend_streak": 0.0, "bull": 0.0, "bear": 0.0,
                       "r5": rng.normal(0, 1, n), "r15": rng.normal(0, 2, n), "r30": rng.normal(0, 2, n),
                       "fav15": np.abs(rng.normal(0, 2, n)), "adv15": -np.abs(rng.normal(0, 2, n))})
    want = s.add_signals(df.copy(), df[["id", "board", "product_id", "direction", "entered_ts"]])
    got = g.add_labels(df.copy())
    assert (got["runner"] == want["runner"]).all() and (got["crasher"] == want["crasher"]).all()
    assert got["runner"].sum() > 0 and got["crasher"].sum() > 0 and (got["day"] == want["day"]).all()


def test_seal_refuses_reserved_entries():
    g.assert_sealed(np.array([g.SEAL - 1]))
    with pytest.raises(SystemExit):
        g.assert_sealed(np.array([g.SEAL]))
    assert g.SEAL == 1794528000 and max(hi for _, hi in g.WINDOWS.values()) < "2026-11-13"
