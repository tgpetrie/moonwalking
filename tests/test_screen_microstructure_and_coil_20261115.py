"""Hand-calculated checks for the microstructure gate and coil screen. No market data."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts/scoring_experiment/screen_microstructure_and_coil_20261115.py"
spec = importlib.util.spec_from_file_location("mc", ROOT / SCRIPT)
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)


def bars(rows):
    """(open time, open, close, volume) rows as the per-product candle tuple."""
    a = np.array(sorted(rows), dtype=float)
    return a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 2] * a[:, 3]


# ---------- Part A features ----------


def test_anchor_is_the_last_candle_closed_before_entry():
    assert mc.anchor_minute(6030) == 5940
    assert mc.anchor_minute(6000) == 5940  # the 5940 bar closes exactly at 6000
    assert mc.anchor_minute(5999) == 5880
    assert mc.anchor_minute(6030, delay_minutes=1) == 5880


def test_d3_sums_three_closed_minutes_and_missing_bars_are_zero():
    candles = bars(
        [
            (5760, 1.0, 1.0, 1000.0),  # m0 - 180: before the 3m window
            (5820, 2.0, 2.0, 10.0),  # 20 dollars
            # 5880 has no row: no trade, zero dollars
            (5940, 2.5, 2.5, 4.0),  # 10 dollars
            (6000, 99.0, 99.0, 1000.0),  # not closed at entry: must not be read
        ]
    )
    f = mc.entry_features(6030, 1.0, candles)
    assert f["D3"] == 30.0 and f["n3"] == 2
    assert f["n60"] == 1 and f["A"] == 0.0  # under 10 traded baseline minutes
    assert mc.entry_features(6000, 1.0, candles)["D3"] == 30.0
    assert mc.entry_features(5999, 1.0, candles)["D3"] == 1020.0  # 5760, 5820, 5880
    assert mc.entry_features(6030, 1.0, candles, delay_minutes=1)["D3"] == 1020.0


def test_entry_without_candles_stays_in_the_denominator_with_zeros():
    f = mc.entry_features(6030, 2.0, None)
    assert f["D3"] == 0.0 and f["A"] == 0.0 and f["n60"] == 0


def absorption_bars(drop=0):
    m0 = 5940
    rows = [(2160, 100.0, 100.0, 1e9)]  # m0 - 3780: one minute before the baseline
    edge = [2220 + 60 * i for i in range(11)] + [m0 - 180]  # both inclusive ends
    for i, ts in enumerate(edge[: len(edge) - drop]):
        if i < 6:
            rows.append((ts, 100.0, 100.1, 10.0))  # 1001 dollars per 0.1% = 10010
        else:
            rows.append(
                (ts, 100.0, 100.0, 5.0)
            )  # 500 dollars at the 0.05% floor = 10000
    rows += [(m0 - 120, 100.0, 100.0, 30.0), (m0, 100.0, 101.0, 20.0)]  # 3000 + 2020
    return bars(rows)


def test_absorption_multiple_by_hand():
    f = mc.entry_features(6000, 0.5, absorption_bars())
    assert f["n60"] == 12 and np.isclose(f["D3"], 5020.0)
    assert np.isclose(f["K_base"], 10005.0)  # median of six 10000s and six 10010s
    assert np.isclose(f["K3"], 10040.0)  # 5020 / 0.5
    assert np.isclose(f["A"], 10040.0 / 10005.0)
    assert np.isclose(mc.entry_features(6000, -0.5, absorption_bars())["A"], f["A"])
    floored = mc.entry_features(6000, 0.04, absorption_bars())  # |pct_3m| floor 0.10
    assert np.isclose(floored["A"], 50200.0 / 10005.0)


def test_absorption_is_zero_under_ten_traded_baseline_minutes():
    f = mc.entry_features(6000, 0.5, absorption_bars(drop=3))
    assert f["n60"] == 9 and f["A"] == 0.0 and np.isclose(f["D3"], 5020.0)
    assert mc.entry_features(6000, math.nan, absorption_bars())["A"] == 0.0


def test_labels_and_directional_snapshot_move():
    df = pd.DataFrame(
        {
            "board": ["confirmation_3m_up", "ignition_1m", "confirmation_3m_down"],
            "direction": ["up", "up", "down"],
            "entered_ts": [mc.START, mc.START + 1, mc.START + 86400],
            "pct_1m": [1.0, 2.0, -3.0],
            "pct_3m": [4.0, 5.0, -6.0],
            "r5": [0.0, -0.6, -0.1],
            "r15": [1.2, 1.2, -1.2],
            "r30": [0.0, 2.0, -2.0],
            "fav15": [1.5, 2.0, 0.0],
            "adv15": [0.0, 0.0, -0.5],
        }
    )
    out = mc.add_labels(df)
    assert out["runner"].tolist() == [1, 0, 0]  # row 2 fails the 5m floor
    assert out["crasher"].tolist() == [0, 0, 1]
    assert out["S"].tolist() == [4.0, 2.0, 6.0]
    assert out["day"].tolist() == ["2026-09-07", "2026-09-07", "2026-09-08"]


# ---------- Part A arms ----------


def test_same_day_arms_by_hand():
    rank = np.array([8.0, 7, 6, 5, 4, 3, 2, 1])
    d3 = np.array([0.0, 5, 50, 60, 70, 80, 0, 0])  # median 27.5, 30th percentile 0.5
    amult = np.array([9.0, 9, 1, 2, 1, 1, 9, 9])
    arms = mc.same_day_arms(rank, d3, amult, np.arange(1, 9))
    flagged = {name: np.flatnonzero(mask).tolist() for name, mask in arms.items()}
    assert flagged["gate"] == [2, 3, 4, 5] and flagged["strict"] == [3]
    assert flagged["a0"] == [0, 1]
    assert flagged["a1"] == [2, 3]
    assert flagged["a1_q30"] == [1, 2]
    assert flagged["a2"] == [3, 5]  # one strict pass, then the highest D3 * A_mult
    assert flagged["a2_backfill"] == [5]
    assert flagged["a3"] == []  # both A0 flags fail the dollar gate
    for name in ("a0", "a1", "a1_q30", "a2"):
        assert arms[name].sum() == 2  # identical budget, floor(0.25 * 8)


def test_same_day_ties_break_by_smaller_id():
    arms = mc.same_day_arms(
        np.full(4, 5.0), np.ones(4), np.ones(4), np.array([4, 3, 2, 1])
    )
    assert np.flatnonzero(arms["a0"]).tolist() == [3]


PRIOR = [(1.0, 0.0, 0.0), (2.0, 10.0, 2.0), (3.0, 20.0, 2.0), (4.0, 30.0, 1.0)]
TODAY = [(4.0, 30.0, 1.0), (3.3, 20.0, 2.0), (10.0, 0.0, 0.0), (3.4, 12.0, 5.0)]


def causal_board(prior=PRIOR, today=TODAY, future=TODAY, skip=()):
    """Seven prior days, 2026-09-14 as the scored day, and one later day."""
    days = [d for d in pd.date_range("2026-09-07", "2026-09-15").strftime("%Y-%m-%d")]
    rows = []
    for day in days:
        if day in skip:
            continue
        values = (
            today if day == "2026-09-14" else future if day > "2026-09-14" else prior
        )
        for i, (b0, d3, a) in enumerate(values):
            rows.append(
                {
                    "id": len(rows),
                    "day": day,
                    "entered_ts": mc.stamp(day) + i,
                    "B0": b0,
                    "D3": d3,
                    "A": a,
                    "runner": 0,
                    "crasher": 0,
                }
            )
    return pd.DataFrame(rows)


def causal_flags(board, day="2026-09-14"):
    f = mc.build_flags(board)
    f = f[f["day"] == day]
    return {arm: f[f"ca_{arm}"].tolist() for arm in mc.ARMS}, f["scored"].tolist()


def test_causal_thresholds_by_hand():
    # Trailing 28 rows: Q75(B0) = 3.25; median D3 = 15; 30th percentile D3 = 10.
    # Dollar gate passes half, so A1 needs B0 >= median of passers' B0 = 3.5.
    # Wide gate passes three quarters, so A1-30 needs B0 >= their Q(2/3) = 3.3333.
    # Strict gate passes exactly a quarter: every strict pass flags, nothing backfills.
    flags, scored = causal_flags(causal_board())
    assert scored == [True] * 4
    assert flags["a0"] == [True, True, True, True]
    assert flags["gate"] == [True, True, False, False]
    assert flags["a1"] == [True, False, False, False]
    assert flags["a1_q30"] == [True, False, False, True]
    assert flags["strict"] == [False, True, False, False]
    assert flags["a2"] == [False, True, False, False]
    assert flags["a2_backfill"] == [False] * 4
    assert flags["a3"] == [True, True, False, False]


def test_causal_flags_ignore_same_day_and_later_rows():
    reference, _ = causal_flags(causal_board())
    wild = [(9e9, 9e9, 9e9)] * 40
    later, _ = causal_flags(causal_board(future=wild))
    assert later == reference
    crowd = TODAY + wild  # other entries on the scored day cannot move a threshold
    same_day, _ = causal_flags(causal_board(today=crowd))
    assert {arm: v[:4] for arm, v in same_day.items()} == reference
    earlier = [(100.0, d3, a) for _, d3, a in PRIOR]  # the trailing days do set it
    moved, _ = causal_flags(causal_board(prior=earlier))
    assert moved["a0"] == [False] * 4


def test_causal_day_is_unscored_without_all_seven_prior_days():
    board = causal_board()
    first = mc.build_flags(board)
    assert not first.loc[first["day"] < "2026-09-14", "scored"].any()
    flags, scored = causal_flags(causal_board(skip=("2026-09-10",)))
    assert scored == [False] * 4 and not any(flags["a0"]) and not any(flags["a2"])


def test_causal_backfill_uses_the_trailing_cutoff_pair():
    # No trailing row passes the strict gate. The budget of 7 goes to the best
    # dollar-gate-only rows by D3 * A_mult then B0: the seven (30, 4.0) rows.
    prior = [(1.0, 0.0, 0.0), (2.0, 10.0, 2.0), (3.0, 20.0, 1.0), (4.0, 30.0, 1.0)]
    today = [
        (4.0, 30.0, 1.0),  # equals the cutoff pair: flagged
        (5.0, 20.0, 1.0),  # lower score: not flagged
        (1.0, 40.0, 1.0),  # higher score: flagged whatever its move
        (3.9, 30.0, 1.0),  # tied score, smaller move: not flagged
        (2.0, 16.0, 3.0),  # strict pass: flagged, not a backfill
    ]
    flags, _ = causal_flags(causal_board(prior=prior, today=today))
    assert flags["a2"] == [True, False, True, False, True]
    assert flags["a2_backfill"] == [True, False, True, False, False]


# ---------- Part A metrics ----------


def test_paired_rates_and_veto_counts_by_hand():
    n = 20
    f = pd.DataFrame(
        {
            "day": ["2026-09-07"] * n,
            "runner": [1, 1, 0, 0, 0] + [0] * 15,
            "crasher": [0, 0, 1, 1, 0] + [0] * 15,
            "sd_a0": [True] * 5 + [False] * 15,
            "sd_a3": [True, True] + [False] * 18,
            "scored": [False] * n,
        }
    )
    out = mc.compare(f, "sd", "a0", "a3", "2026-09-07", "2026-09-07")
    assert out["days_scored"] == 1 and out["flags"] == {
        "base": 5,
        "arm": 2,
        "base_share": 0.25,
        "arm_share": 0.1,
        "base_per_day": {"mean": 5.0, "min": 5, "max": 5},
        "arm_per_day": {"mean": 2.0, "min": 2, "max": 2},
    }
    assert np.isclose(out["rates"]["runner_base"], 0.4)
    assert np.isclose(out["rates"]["crasher_base"], 0.4)
    assert np.isclose(out["delta_P"]["mean"], 0.6)
    assert np.isclose(out["delta_C"]["mean"], -0.4)
    assert np.isclose(out["delta_N"]["mean"], 1.0)
    assert out["veto"] == {
        "flags_dropped": 3,
        "runners_missed": 0,
        "crashers_avoided": 2,
        "runner_recall": 1.0,
        "crashers_avoided_share": 1.0,
        "crashers_avoided_per_runner_missed": None,
    }


def test_same_day_mode_skips_days_with_fewer_than_two_runners():
    f = pd.DataFrame(
        {
            "day": ["2026-09-07"] * 20,
            "runner": [1] + [0] * 19,
            "crasher": [0] * 20,
            "sd_a0": [True] * 5 + [False] * 15,
            "sd_a1": [True] * 5 + [False] * 15,
            "ca_a0": [True] * 5 + [False] * 15,
            "ca_a1": [True] * 5 + [False] * 15,
            "scored": [True] * 20,
        }
    )
    day = ("2026-09-07", "2026-09-07")
    assert mc.compare(f, "sd", "a0", "a1", *day)["days_scored"] == 0
    assert mc.compare(f, "ca", "a0", "a1", *day)["days_scored"] == 1


def test_block_bootstrap_is_deterministic_and_bounded():
    assert mc.boot(np.full(9, 0.01), 3) == {"lo": 0.01, "hi": 0.01}
    assert mc.boot(np.arange(5.0), 3) == {"lo": None, "hi": None}
    v = np.array([0.0, 0.1, 0.2, -0.1, 0.05, 0.0, 0.3, -0.2, 0.1])
    first, again = mc.boot(v, 3), mc.boot(v, 3)
    assert (
        first == again and v.min() <= first["lo"] <= v.mean() <= first["hi"] <= v.max()
    )


# ---------- Part B features ----------

WIDTH, M0 = 1500, 1460


def empty_market(n=1):
    shape = (n, WIDTH)
    close, dollar = np.full(shape, np.nan), np.zeros(shape)
    return close, np.full(shape, -np.inf), np.full(shape, np.inf), dollar


def test_coil_ratio_and_volume_pace_by_hand():
    close, high, low, dollar = empty_market(2)
    high[0, M0 - 1444], low[0, M0 - 1444] = 1000.0, 1.0  # one minute before 24h
    high[0, M0 - 1443], low[0, M0 - 1443] = 110.0, 100.0  # first 24h minute
    high[0, M0 - 243], low[0, M0 - 243] = 104.0, 102.0  # first 4h minute
    high[0, M0 - 3], low[0, M0 - 3] = 105.0, 103.0  # last minute before the 3m window
    high[0, M0 - 2], low[0, M0 - 2] = 500.0, 50.0  # inside the 3m window: excluded
    dollar[0, M0 - 255] = 9999.0  # one minute before the 4h volume baseline
    dollar[0, M0 - 254], dollar[0, M0 - 15] = (
        100.0,
        60.0,
    )  # baseline 160 over 240 minutes
    dollar[0, M0 - 14], dollar[0, M0] = 20.0, 10.0  # recent 15 minutes: 30
    dollar[0, M0 + 1] = 9999.0  # after the last usable bar: must not be read
    high[0, M0 + 1], low[0, M0 + 1] = 9999.0, 0.001
    mk = mc.market(["A-USD", "B-USD"], close, high, low, dollar)
    f = mc.coil_features(mk, M0, np.array([0, 1]))
    assert f["H4"][0] == 105.0
    expected = math.log(105 / 102) / (math.sqrt(4 / 24) * math.log(110 / 100))
    assert np.isclose(f["C_ratio"][0], expected)
    assert np.isclose(f["V_pace"][0], 30.0 / (160.0 / 16.0))  # 3.0
    assert np.isnan(f["C_ratio"][1]) and np.isnan(f["V_pace"][1])  # no bars: undefined


def test_coil_is_undefined_for_a_zero_24h_range():
    close, high, low, dollar = empty_market()
    high[0, M0 - 500], low[0, M0 - 500] = 7.0, 7.0
    high[0, M0 - 100], low[0, M0 - 100] = 7.0, 7.0
    mk = mc.market(["A-USD"], close, high, low, dollar)
    assert np.isnan(mc.coil_features(mk, M0, np.array([0]))["C_ratio"][0])


def test_grind_return_and_range_position_by_hand():
    close, high, low, dollar = empty_market(2)
    close[0, M0 - 15], high[0, M0 - 15], low[0, M0 - 15] = (
        10.3,
        99.0,
        1.0,
    )  # endpoint only
    high[0, M0 - 14], low[0, M0 - 14] = 10.4, 10.0
    close[0, M0], high[0, M0], low[0, M0] = 10.4, 10.5, 10.3
    close[1, M0 - 15], close[1, M0] = 5.0, 5.0
    high[1, M0], low[1, M0] = 5.0, 5.0  # flat range: position undefined
    mk = mc.market(["A-USD", "B-USD"], close, high, low, dollar)
    f = mc.grind_features(mk, M0, np.array([0, 1]))
    assert np.isclose(f["r15"][0], 10.4 / 10.3 - 1)
    assert np.isclose(f["position"][0], 0.8)  # (10.4 - 10.0) / (10.5 - 10.0)
    assert np.isnan(f["position"][1])


def synthetic_board():
    """Twelve products trading every minute at 100, then shaped at the last bars."""
    n = 12
    close = np.full((n, WIDTH), 100.0)
    dollar = np.ones((n, WIDTH))
    for i in range(8):  # eight leaders fill the synthetic top eight on 1m and 3m
        close[i, M0] = 100.0 * (1 + 0.01 * (10 - i))
    close[8, M0] = 100.5  # ninth largest move, above +0.30%: the baseline candidate
    close[9, M0 - 15], close[9, M0] = 100.1, 100.2  # coil breakout, +0.20% over 3m
    close[10, M0 - 14 : M0] = np.linspace(100.0, 100.5, 14)  # steady 15m grind
    close[10, M0 - 3], close[10, M0 - 1], close[10, M0] = 100.5, 100.55, 100.6
    close[11, M0 - 59 : M0 + 1] = np.nan  # no trade in the last hour: inactive
    high, low = close.copy(), close.copy()
    high[np.isnan(close)], low[np.isnan(close)] = -np.inf, np.inf
    high[9, M0 - 1000], low[9, M0 - 1000] = 110.0, 95.0  # wide day, tight last 4h
    high[10, M0] = 100.7
    dollar[9, M0 - 14 : M0 + 1] = 4.0  # pace 60 / (240 / 16) = 4
    dollar[10, M0 - 14 : M0 + 1] = 5.0  # pace 5
    dollar[11, M0 - 59 : M0 + 1] = 0.0
    names = [f"P{i:02d}-USD" for i in range(n)]
    return mc.market(names, close, high, low, dollar)


def test_each_arm_picks_its_own_candidate_outside_the_top_eight():
    picked = mc.cutoff_candidates(synthetic_board(), M0 + 2)
    assert picked["baseline"].tolist() == [8]
    assert picked["b1"].tolist() == [9]
    assert picked["b2"].tolist() == [10]


def test_candidates_do_not_read_bars_after_the_usable_minute():
    mk = synthetic_board()
    before = {k: v.tolist() for k, v in mc.cutoff_candidates(mk, M0 + 2).items()}
    for array in (mk.close, mk.high, mk.low):
        array[:, M0 + 1 :] *= 50.0
    later = mc.market(
        mk.products, mk.close, mk.high, mk.low, np.full(mk.close.shape, 7.0)
    )
    later.dollar_sum[:, : M0 + 2] = mk.dollar_sum[:, : M0 + 2]
    after = {k: v.tolist() for k, v in mc.cutoff_candidates(later, M0 + 2).items()}
    assert after == before


def test_replay_flags_one_product_per_cutoff_with_an_hour_cooldown():
    candidates = {
        0: np.array([3, 1]),
        5: np.array([3, 1]),
        60: np.array([3]),
        65: np.array([3]),
    }
    flags = mc.replay(candidates, range(0, 70, 5), 5)
    assert flags == [(0, 3), (5, 1), (60, 3)]  # 3 is cooling at 5 and again at 65


# ---------- Part B live board ----------


def test_live_graduation_lead_counts_only_entries_after_the_flag():
    span = (np.array([1000, 2000, 2900, 2901]), np.array([1100, 2050, 2950, 2960]))
    assert mc.live_graduation(span, 2000) == (
        True,
        900,
    )  # entry at t itself is not a lead
    assert mc.live_graduation(span, 1999) == (False, 1)
    assert mc.live_graduation(span, 1099) == (True, None)  # next entry is 901s away
    assert mc.live_graduation(span, 999) == (False, 1)
    assert mc.live_graduation(span, 2901) == (True, None)  # nothing later
    assert mc.live_graduation(None, 2000) == (False, None)


def test_live_index_keeps_up_boards_only_and_orders_entries():
    hist = pd.DataFrame(
        {
            "board": [
                "ignition_1m",
                "confirmation_3m_up",
                "confirmation_3m_down",
                "ignition_1m",
            ],
            "product_id": ["A-USD", "A-USD", "A-USD", "B-USD"],
            "direction": ["up", "up", "down", "up"],
            "entered_ts": [
                mc.START + 500,
                mc.START + 100,
                mc.START + 200,
                mc.START + 300,
            ],
            "last_seen_ts": [
                mc.START + 560,
                mc.START + 150,
                mc.START + 260,
                mc.START + 330,
            ],
            "exited_ts": [mc.START + 600, None, mc.START + 270, None],
            "entry_rank": [1, 2, 3, 4],
        }
    )
    spans, _ = mc.live_index(hist)
    entered, end = spans["A-USD"]
    assert (entered - mc.START).tolist() == [
        100,
        500,
    ]  # the down-board entry is not a graduation
    assert (end - mc.START).tolist() == [
        150,
        600,
    ]  # last seen stands in for a missing exit
    assert mc.live_graduation(spans["A-USD"], mc.START + 120) == (True, 380)


def test_flags_are_unobservable_across_a_capture_gap():
    entered = mc.START + np.concatenate([np.arange(0, 3001, 100), [4000]])
    gaps = mc.capture_gaps(entered)
    assert (gaps - mc.START).tolist()[1] == [3000, 4000]
    assert mc.live_observable(gaps, mc.START + 100)  # window ends at 1000
    assert not mc.live_observable(gaps, mc.START + 2200)  # window runs into the gap
    assert not mc.live_observable(gaps, mc.START + 3999)
    assert not mc.live_observable(gaps, mc.START - 2000)  # before the first entry


def test_pooled_difference_and_block_interval_by_hand():
    days = [f"2026-09-{d:02d}" for d in range(7, 13)]
    arm = pd.DataFrame({"runners": [1] * 6, "graded": [2] * 6}, index=days)
    base = pd.DataFrame({"runners": [0] * 6, "graded": [4] * 6}, index=days)
    out = mc.pooled_delta(arm, base, "runners", "graded")
    assert out == {"delta": 0.5, "block3": {"lo": 0.5, "hi": 0.5}}
    empty = pd.DataFrame({"runners": [0] * 6, "graded": [0] * 6}, index=days)
    assert mc.pooled_delta(arm, empty, "runners", "graded")["delta"] is None


def test_results_json_has_no_nan():
    cleaned = mc.clean(
        {"a": np.float64("nan"), "b": [np.int64(3), np.bool_(True), math.inf]}
    )
    assert cleaned == {"a": None, "b": [3, True, None]}


# ---------- post hoc descriptives ----------


def test_live_base_counts_cover_every_universe_product():
    mk = synthetic_board()
    cutoff = M0 + 2
    t = (mc.FIRST_MINUTE + cutoff) * 60
    spans = {
        "P08-USD": (np.array([t + 100]), np.array([t + 160])),  # graduates
        "P10-USD": (
            np.array([t - 50, t + 2000]),
            np.array([t + 30, t + 2100]),
        ),  # on board
        "P00-USD": (
            np.array([t + 5]),
            np.array([t + 9]),
        ),  # a leader: not in the universe
    }
    found = mc.cutoff_candidates(mk, cutoff)["baseline"]
    none = np.empty((0, 2))
    counts = mc.live_base_counts(mk, spans, none, {cutoff: found}, [cutoff])
    row = counts.iloc[0].to_dict()
    assert row["universe_seen"] == 3 and row["universe_grads"] == 1  # P08, P09, P10
    assert row["universe_fresh_seen"] == 2 and row["universe_fresh_grads"] == 1
    assert (
        row["baseline_candidates_seen"] == 1 and row["baseline_candidates_grads"] == 1
    )
    hidden = np.array([[t + 10, t + 5000]])  # collector gap inside the window
    assert mc.live_base_counts(mk, spans, hidden, {cutoff: found}, [cutoff]).empty


def test_flag_inputs_report_medians_of_each_arm():
    # One scored day: rows (B0, D3) = (4, 30), (3.3, 20), (10, 0), (3.4, 12).
    board = causal_board(future=[]).assign(stratum="confirmation_3m_up/up")
    flags = {b: mc.build_flags(board) for b in mc.BOARDS}
    out = mc.flag_inputs(board, flags)["screen"]["confirmation_3m_up/up"]
    assert out["all_entries"] == {
        "flags": 4,
        "median_B0_pct": 3.7,
        "median_D3_usd": 16.0,
    }
    assert out["a1"] == {"flags": 1, "median_B0_pct": 4.0, "median_D3_usd": 30.0}
    dropped = {"flags": 2, "median_B0_pct": 6.7, "median_D3_usd": 6.0}  # rows 3 and 4
    assert out["a0_dropped_by_gate"] == dropped
    empty = mc.flag_inputs(board, flags)["check"]["confirmation_3m_up/up"]["a0"]
    assert empty == {"flags": 0, "median_B0_pct": None, "median_D3_usd": None}
