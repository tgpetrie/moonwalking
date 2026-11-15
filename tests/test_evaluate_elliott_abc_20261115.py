"""Synthetic checks for the Elliott ABC evaluation driver. No market data."""

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts/scoring_experiment/evaluate_elliott_abc_20261115.py"
spec = importlib.util.spec_from_file_location("elliott_eval", ROOT / SCRIPT)
ev = importlib.util.module_from_spec(spec)
sys.modules["elliott_eval"] = ev
spec.loader.exec_module(ev)

HOUR = 3600
# Hours per leg and the price each leg ends at: decline, advance, A, B, C, then up.
LEGS = [
    (40, 90.0),
    (20, 110.0),
    (8, 102.0),
    (6, 106.0),
    (9, 97.0),
    (5, 102.0),
    (40, 112.0),
]


def minutes_for(legs=LEGS, t0=ev.A_START - 70 * HOUR, start=100.0, pad=0.02):
    """One-minute candles walking the legs in straight lines."""
    rows, price, ts = [], start, t0
    for hours, end in legs:
        step = (end - price) / (hours * 60)
        for _ in range(hours * 60):
            o, c = price, price + step
            rows.append([ts, min(o, c) - pad, max(o, c) + pad, o, c, 10.0])
            price, ts = c, ts + 60
    return np.asarray(rows)


MINUTES = minutes_for()
BARS = ev.resample(MINUTES, HOUR)
HBARS = ev.resample(MINUTES, 4 * HOUR)


def walk(minutes=MINUTES):
    bars, hbars = ev.resample(minutes, HOUR), ev.resample(minutes, 4 * HOUR)
    return ev.walk_events(bars, HOUR, hbars, 4 * HOUR, ev.A_START, ev.A_END)


def test_windows_keep_every_outcome_before_the_seal():
    assert ev.A_END == ev.SEAL - 24 * HOUR
    assert ev.A_START == ev.screen.stamp("2026-10-13")
    first, second = ev.A_HALVES["first_half"], ev.A_HALVES["second_half"]
    assert first[0] == ev.A_START and first[1] == second[0] and second[1] == ev.A_END
    assert (first[1] - first[0]) == (second[1] - second[0]) == 15 * 86400
    assert ev.RANK_WINDOW[1] <= ev.A_START  # the universe is ranked on earlier dates
    with pytest.raises(SystemExit, match="seal"):
        ev.outcome(MINUTES, ev.A_END + 60, 100.0, 99.0, 101.0, 1)


def test_resample_and_reads_use_closed_bars_only():
    hour = MINUTES[:60]
    bar = ev.resample(hour, HOUR)[0]
    assert bar[0] == hour[0, 0]
    assert (bar[1], bar[2]) == (hour[:, 1].min(), hour[:, 2].max())
    assert (bar[3], bar[4], bar[5]) == (hour[0, 3], hour[-1, 4], hour[:, 5].sum())
    cut = BARS[100, 0] + HOUR
    assert ev.closed_count(BARS, HOUR, cut) == 101
    assert ev.closed_count(BARS, HOUR, cut - 1) == 100  # the forming bar is not counted
    # A read at `cut` is the same whether or not later candles exist.
    past = MINUTES[MINUTES[:, 0] < cut]
    seen = ev.read_at(
        ev.resample(past, HOUR), HOUR, ev.resample(past, 4 * HOUR), 4 * HOUR, cut
    )
    assert seen == ev.read_at(BARS, HOUR, HBARS, 4 * HOUR, cut)


def test_complete_signal_fires_on_the_bar_that_confirms_wave_c():
    events, pivot_bars, tally = walk()
    done = [e for e in events if e["type"] == "complete"]
    assert len(done) == 1 and tally["reads"] > 0
    e = done[0]
    assert (e["bias"], e["sgn"]) == ("bullish", 1)
    assert e["entry_ts"] == BARS[e["k"], 0] + HOUR  # knowable at that bar's close
    assert e["entry"] == BARS[e["k"], 4]
    assert e["stop"] == pytest.approx(97.0, abs=0.05)  # the wave C low
    assert e["target"] == pytest.approx(106.0, abs=0.05)  # the wave B high
    assert e["stop"] < e["entry"] < e["target"]
    assert e["k"] in pivot_bars["low"]
    c_bar = int(np.argmin(BARS[:, 1]))
    assert e["k"] > c_bar  # confirmed after the low, never on it
    # A zone signal for the same count came earlier, while wave C was still falling.
    zone = [z for z in events if z["type"] == "zone"]
    assert len(zone) == 1 and zone[0]["entry_ts"] < e["entry_ts"]
    assert zone[0]["stop"] < e["stop"]


def test_signals_do_not_change_when_the_future_is_removed():
    events, _, _ = walk()
    for e in events:
        past = MINUTES[MINUTES[:, 0] < e["entry_ts"]]
        again, _, _ = walk(past)
        assert e in again


def test_outcome_reads_only_candles_at_or_after_entry():
    e = [x for x in walk()[0] if x["type"] == "complete"][0]
    args = (e["entry_ts"], e["entry"], e["stop"], e["target"], 1)
    base = ev.outcome(MINUTES, *args)
    assert base["hit_24h"] == 1.0 and base["stop_24h"] == 0.0
    assert base["R_24h"] == pytest.approx(base["rr"])
    assert base["Rnet_24h"] == pytest.approx(
        base["rr"] - ev.COST * e["entry"] / (e["entry"] - e["stop"])
    )
    assert base["mfe_24h"] > 0 >= base["mae_24h"]
    assert (
        base["hit_4h"] == 0.0 and -1.0 < base["R_4h"] < base["rr"]
    )  # still open at 4h
    before = MINUTES.copy()
    before[before[:, 0] < e["entry_ts"], 1] = (
        1.0  # a crash before entry changes nothing
    )
    assert ev.outcome(before, *args) == base
    after = MINUTES.copy()
    after[np.searchsorted(after[:, 0], e["entry_ts"]), 1] = (
        1.0  # the first forward minute
    )
    assert ev.outcome(after, *args)["stop_24h"] == 1.0


def forward(rows, t0=ev.A_START):
    """Minutes `[low, high, close]` starting at t0."""
    return np.asarray(
        [[t0 + 60 * i, lo, hi, c, c, 1.0] for i, (lo, hi, c) in enumerate(rows)]
    )


def test_outcome_first_touch_rules():
    t0 = ev.A_START
    target_first = forward([(99.5, 100.5, 100), (99.6, 102.5, 102), (97, 99, 98)])
    assert ev.outcome(target_first, t0, 100.0, 98.0, 102.0, 1)[
        "R_24h"
    ] == pytest.approx(1.0)
    stop_first = forward([(97.5, 100.5, 98), (99, 103, 102)])
    assert ev.outcome(stop_first, t0, 100.0, 98.0, 102.0, 1)["R_24h"] == -1.0
    same_minute = forward([(97.5, 102.5, 100)])
    out = ev.outcome(same_minute, t0, 100.0, 98.0, 102.0, 1)
    assert (out["hit_24h"], out["stop_24h"], out["R_24h"]) == (0.0, 1.0, -1.0)
    # Touching the stop exactly is not a break; trading through it is.
    at_stop = forward([(98.0, 100.5, 99.0)])
    still_open = ev.outcome(at_stop, t0, 100.0, 98.0, 102.0, 1)
    assert (still_open["hit_24h"], still_open["stop_24h"]) == (0.0, 0.0)
    assert still_open["R_24h"] == pytest.approx(-0.5)  # marked at the last close
    assert still_open["mae_24h"] == pytest.approx(-0.02)
    assert still_open["mfe_24h"] == pytest.approx(0.005)
    nothing = ev.outcome(forward([]).reshape(0, 6), t0, 100.0, 98.0, 102.0, 1)
    assert nothing["R_24h"] == 0.0 and nothing["Rnet_24h"] < 0


def test_bearish_outcome_is_the_mirror():
    t0 = ev.A_START
    rows = [(99.5, 100.5, 100), (99.6, 101.5, 101), (97.5, 99, 98)]
    bull = ev.outcome(forward(rows), t0, 100.0, 97.0, 101.0, 1)
    flipped = [(200 - hi, 200 - lo, 200 - c) for lo, hi, c in rows]
    bear = ev.outcome(forward(flipped), t0, 100.0, 103.0, 99.0, -1)
    for key in ("hit_24h", "stop_24h", "R_24h", "mfe_24h", "mae_24h", "rr"):
        assert bear[key] == pytest.approx(bull[key])
    assert bull["hit_24h"] == 1.0 and bull["mfe_24h"] > 0 > bull["mae_24h"]


def test_placebo_is_distance_matched_seeded_and_skips_the_signal_bar():
    e = dict([x for x in walk()[0] if x["type"] == "complete"][0], seconds=HOUR)
    calls = []
    real = ev.outcome

    def spy(minutes, ts, entry, stop, target, sgn):
        calls.append((ts, entry, stop, target, sgn))
        return real(minutes, ts, entry, stop, target, sgn)

    ev.outcome = spy
    try:
        pool = [k for k in range(60, 100) if k != e["k"]][:25]
        a = ev.placebo(
            MINUTES, BARS, list(pool) + [e["k"]], e, np.random.default_rng(5)
        )
        first = list(calls)
        b = ev.placebo(
            MINUTES, BARS, list(pool) + [e["k"]], e, np.random.default_rng(5)
        )
    finally:
        ev.outcome = real
    assert a == b and set(a) == set(ev.METRICS)
    assert len(first) == min(ev.PLACEBOS, len(pool))
    for ts, entry, stop, target, sgn in first:
        k = int(np.searchsorted(BARS[:, 0], ts - HOUR))
        assert k in pool and k != e["k"]
        assert entry == BARS[k, 4] and sgn == 1
        assert stop / entry == pytest.approx(e["stop"] / e["entry"])
        assert target / entry == pytest.approx(e["target"] / e["entry"])
    none = ev.placebo(MINUTES, BARS, [e["k"]], e, np.random.default_rng(5))
    assert all(math.isnan(v) for v in none.values())


def test_universe_ranks_usd_products_and_drops_pegs():
    rows = [
        ("BIG-USD", 9e9, 10.0, 20.0),
        ("MID-USD", 5e9, 1.0, 1.5),
        ("PEG-USD", 8e9, 0.999, 1.001),
        ("EUR-EUR", 7e9, 1.0, 2.0),
        ("GONE-USD", 6e9, 1.0, 2.0),
        ("SMALL-USD", 1e3, 1.0, 2.0),
    ]
    uni = ev.rank_universe(
        rows, {"BIG-USD", "MID-USD", "PEG-USD", "EUR-EUR", "SMALL-USD"}
    )
    assert uni["products"] == ["BIG-USD", "MID-USD", "SMALL-USD"]
    assert uni["pegged_excluded"] == ["PEG-USD"]
    assert uni["core"] == uni["products"][: ev.CORE_N]


def test_merge_keeps_the_first_store_at_a_shared_minute_and_refuses_the_seal():
    archive = np.array([[120, 1, 2, 1, 2, 5.0], [60, 1, 2, 1, 2, 5.0]])
    backfill = np.array(
        [[120, 9, 9, 9, 9, 9.0], [180, 3, 4, 3, 4, 5.0], [ev.SEAL, 1, 2, 1, 2, 1.0]]
    )
    bad = np.array([[240, 0, 2, 1, 2, 5.0], [301, 1, 2, 1, 2, 5.0]])
    merged = ev.merge_minutes([archive, backfill, bad])
    assert merged[:, 0].tolist() == [60, 120, 180]
    assert merged[1, 4] == 2  # the archive row, not the backfill's
    assert ev.merge_minutes([]).shape == (0, 6)


def test_block_bootstrap_is_seeded_and_signed():
    ts = ev.A_START + np.arange(30) * 86400
    chunk = ev.chunk_of(ts)
    assert chunk.min() == 0 and chunk.max() == 9 and (np.bincount(chunk) == 3).all()
    up = np.linspace(0.5, 1.5, 30)
    one = ev.boot_diff(chunk, up)
    assert one == ev.boot_diff(chunk, up)
    assert one["mean"] == pytest.approx(1.0) and 0 < one["lo"] < 1.0 < one["hi"]
    two = ev.boot_diff(chunk, up, chunk, up - 0.25)
    assert two["mean"] == pytest.approx(0.25) and two["lo"] > 0 and two["n_other"] == 30
    assert ev.positive(two) and not ev.positive(ev.boot_diff(chunk, -up))
    with_gap = np.r_[up[:-1], np.nan]
    assert ev.boot_diff(chunk, with_gap)["n"] == 29
    assert ev.boot_diff(chunk[:0], up[:0])["mean"] is None


def test_structure_arms_follow_the_board_direction():
    live = {
        "available": True,
        "active_pattern": "abc_in_progress",
        "status": "in_c_zone",
        "bias": "bullish",
        "confluence_confirmed": True,
    }
    waiting = dict(live, status="awaiting_c_zone")
    resolved = dict(live, active_pattern="abc_complete", status="target_reached")
    assert ev.live_abc(live) and not ev.live_abc(waiting) and not ev.live_abc(resolved)
    assert ev.live_abc(dict(live, active_pattern="abc_complete", status="confirmed"))
    assert ev.structure(None, "1h") == {
        "1h_sgn": 0,
        "1h_abc": False,
        "1h_conf": False,
        "1h_trend": False,
    }
    assert (
        ev.structure(waiting, "1h")["1h_conf"] is False
    )  # confluence needs a live ABC
    reads = pd.DataFrame(
        [
            {"uid": 0, **ev.structure(live, "15m"), **ev.structure(None, "1h")},
            {
                "uid": 1,
                **ev.structure(None, "15m"),
                **ev.structure(dict(live, confluence_confirmed=False), "1h"),
            },
            {
                "uid": 2,
                **ev.structure(dict(live, bias="bearish"), "15m"),
                **ev.structure(None, "1h"),
            },
            {
                "uid": 3,
                **ev.structure(None, "15m"),
                **ev.structure(
                    dict(
                        live,
                        active_pattern="impulse_in_progress",
                        status="wave_5_underway",
                    ),
                    "1h",
                ),
            },
            {"uid": 4, **ev.structure(None, "15m"), **ev.structure(None, "1h")},
        ]
    )
    up = ev.wave_arms(reads, 1)
    assert ev.structure_class(up).tolist() == [
        "abc_with_confluence",
        "abc_geometry_only",
        "opposing_abc",
        "trend_impulse",
        "no_structure",
    ]
    assert up["abc"].tolist() == [True, True, False, False, False]
    down = ev.wave_arms(reads, -1)
    assert ev.structure_class(down).tolist() == [
        "opposing_abc",
        "opposing_abc",
        "abc_with_confluence",
        "no_structure",
        "no_structure",
    ]


def test_readings_apply_the_declared_thresholds():
    yes = {"mean": 0.1, "lo": 0.01, "hi": 0.2}
    no = {"mean": 0.1, "lo": -0.01, "hi": 0.2}

    def cell(n, n_conf, geometry, confluence, adds):
        keys = {
            "geometry_minus_random_placebo": geometry,
            "confluence_minus_random_placebo": confluence,
            "confluence_minus_without": adds,
        }
        return {
            "groups": {
                "abc_geometry_all": {"n": n},
                "abc_with_confluence": {"n": n_conf},
            },
            "compare": {"hit_24h": keys, "R_24h": keys},
        }

    good = ev.reading_a(cell(150, 60, yes, yes, yes))
    assert good["status"] == "read" and good["geometry_beats_random_placebo"]
    assert (
        good["confluence_beats_random_placebo"] and good["confluence_adds_to_geometry"]
    )
    weak = ev.reading_a(cell(150, 60, no, yes, no))
    assert (
        not weak["geometry_beats_random_placebo"]
        and not weak["confluence_adds_to_geometry"]
    )
    thin = ev.reading_a(cell(99, 49, yes, yes, yes))
    assert thin["status"] == "underpowered"
    assert (
        not thin["geometry_beats_random_placebo"]
        and not thin["confluence_beats_random_placebo"]
    )
    assert ev.reading_a(None)["status"] == "underpowered"

    def window(mean, lo, days=25):
        return {
            "days_scored": days,
            "delta_N": {"mean": mean, "block3": {"lo": lo, "hi": 1.0}},
        }

    ok = ev.reading_b(
        {
            "all": window(0.02, 0.001),
            "first_half": window(0.01, None),
            "second_half": window(0.03, None),
        }
    )
    assert ok["improves_a1"] and ok["same_sign_in_both_halves"]
    for bad in (
        window(0.009, 0.001),
        window(0.02, -0.001),
        window(0.02, 0.001, days=19),
    ):
        got = ev.reading_b(
            {
                "all": bad,
                "first_half": window(0.01, None),
                "second_half": window(-0.01, None),
            }
        )
        assert not got["improves_a1"] and not got["same_sign_in_both_halves"]
    assert ev.reading_b({"all": {"days_scored": 0}})["status"] == "no_scored_days"


def test_flag_rows_are_keyed_by_position_not_by_repeating_ids():
    days = pd.date_range("2026-10-01", periods=9).strftime("%Y-%m-%d")
    rows = []
    for d, day in enumerate(days):
        for j in range(25):
            rows.append(
                {
                    "id": j,
                    "day": day,
                    "entered_ts": ev.screen.stamp(day) + 60 * (25 - j),
                    "product_id": f"P{j % 3}-USD",
                    "runner": j % 5 == 0,
                    "crasher": j % 7 == 0,
                    "B0": float(j),
                    "D3": float(j % 4),
                    "A": 1.0 + j % 2,
                }
            )
    g = pd.DataFrame(rows).sample(frac=1.0, random_state=1)
    flags = ev.attach_rows(g)
    assert flags["uid"].tolist() == list(range(len(g)))
    assert flags["id"].duplicated().any()  # ids repeat, as they do across captures
    key = g.set_index(["entered_ts", "id"])["product_id"]
    assert flags["product_id"].tolist() == [
        key[(t, i)] for t, i in zip(flags["entered_ts"], flags["id"])
    ]
    assert flags["entered_ts"].is_monotonic_increasing
