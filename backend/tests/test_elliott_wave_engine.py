"""Tests for elliott_wave_engine: synthetic candles only, no network."""

import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import elliott_wave_engine as engine
from elliott_wave_engine import (
    analyze_wave_structure,
    detect_pivots,
    resample_candles,
)

STEP = 3600
T0 = 1_700_000_000 - 1_700_000_000 % 14400
PAD = 0.1


def path(legs, start=100.0, t0=T0, step=STEP):
    """Candles walking straight legs. ``legs`` is ``[(bars, end_price, volume)]``."""
    candles, price, ts = [], start, t0
    for bars, end, volume in legs:
        delta = (end - price) / bars
        for _ in range(bars):
            open_, close = price, price + delta
            low, high = min(open_, close) - PAD, max(open_, close) + PAD
            candles.append([ts, low, high, open_, close, volume])
            price, ts = close, ts + step
    return candles


def mirrored(candles, around=200.0):
    return [
        [ts, around - high, around - low, around - o, around - c, v]
        for ts, low, high, o, c, v in candles
    ]


# Decline to an origin low, advance to P0, then A down, B up, C down, bounce.
ABC_LEGS = [
    (40, 90.0, 1000),  # decline into the origin low
    (20, 110.0, 1000),  # prior advance, ends at P0
    (8, 102.0, 1000),  # wave A
    (6, 106.0, 800),  # wave B, 50% of A
    (9, 97.0, 500),  # wave C, 1.125 x A, on lighter volume
    (5, 102.0, 900),  # bounce that confirms C
]
BULL_ABC = path(ABC_LEGS)


def higher_tf(last_base_ts, rising=True, bars=40, step=14400):
    """Closed higher-timeframe bars ending at or before the last base close."""
    end = (last_base_ts + STEP) // step * step
    out = []
    for k in range(bars):
        ts = end - (bars - k) * step
        mid = 100.0 + (k if rising else -k) * 0.8
        out.append([ts, mid - 1.0, mid + 1.0, mid - 0.4, mid + 0.4, 5000])
    return out


def factor(result, name):
    return next(f for f in result["confluence_factors"] if f["name"] == name)


# ─── pivots: causal and non-repainting ───────────────────────────────────────


def random_walk(n=400, seed=7):
    rng = random.Random(seed)
    candles, price = [], 100.0
    for k in range(n):
        open_ = price
        close = max(1.0, open_ + rng.gauss(0, 1.0))
        high = max(open_, close) + abs(rng.gauss(0, 0.3))
        low = max(0.5, min(open_, close) - abs(rng.gauss(0, 0.3)))
        candles.append([T0 + k * STEP, low, high, open_, close, 1000 + rng.random()])
        price = close
    return candles


def test_pivots_alternate_and_are_confirmed_by_a_later_close():
    candles = random_walk()
    pivots = detect_pivots(candles)
    assert len(pivots) >= 8
    for a, b in zip(pivots, pivots[1:]):
        assert a.kind != b.kind
        assert a.index < b.index
        assert a.confirmed_at_index < b.confirmed_at_index
    for p in pivots:
        assert p.confirmed_at_index >= p.index
        assert p.ts == candles[p.index][0]
        col = 2 if p.kind == "high" else 1
        assert p.price == candles[p.index][col]
        # Knowable at the close of the confirming bar, never earlier.
        assert p.confirmed_at_ts == candles[p.confirmed_at_index][0] + STEP


def test_pivots_never_repaint_as_bars_arrive():
    candles = random_walk()
    full = detect_pivots(candles)
    for k in range(engine.ATR_PERIOD + 2, len(candles)):
        seen = detect_pivots(candles[: k + 1])
        assert seen == [p for p in full if p.confirmed_at_index <= k]


def test_pivot_is_not_reported_before_its_reversal_bar():
    full = detect_pivots(BULL_ABC)
    last = full[-1]
    before = detect_pivots(BULL_ABC[: last.confirmed_at_index])
    assert last not in before
    assert before == full[:-1]


def test_reversal_needs_the_atr_multiple():
    assert len(detect_pivots(BULL_ABC, atr_mult=2.2)) >= 5
    # No swing in this series is 50 ATRs deep.
    assert detect_pivots(BULL_ABC, atr_mult=50.0) == []


# ─── ABC corrections ─────────────────────────────────────────────────────────


def test_bullish_abc_complete_has_fib_ratios_target_and_invalidation():
    out = analyze_wave_structure(BULL_ABC)
    assert out["available"] is True
    assert (out["active_pattern"], out["status"]) == ("abc_complete", "confirmed")
    assert out["bias"] == "bullish"
    labels = [p["label"] for p in out["wave_points"]]
    assert labels == ["start", "0", "A", "B", "C"]
    prices = {p["label"]: p["price"] for p in out["wave_points"]}
    assert prices["0"] == pytest.approx(110 + PAD)
    assert prices["A"] == pytest.approx(102 - PAD)
    assert prices["B"] == pytest.approx(106 + PAD)
    assert prices["C"] == pytest.approx(97 - PAD)
    a_len = prices["0"] - prices["A"]
    fib = out["fib_ratios"]
    assert fib["b_retrace_of_a"] == pytest.approx(
        (prices["B"] - prices["A"]) / a_len, abs=1e-4
    )
    assert fib["c_projection_of_a"] == pytest.approx(
        (prices["B"] - prices["C"]) / a_len, abs=1e-4
    )
    assert out["invalidation_price"] == prices["C"]
    assert out["target_price"] == prices["B"]
    assert all(p["confirmed"] for p in out["wave_points"])
    assert out["outcome_validated"] is False
    json.dumps(out, allow_nan=False)


def test_projected_c_zone_levels_are_fib_multiples_of_a():
    out = analyze_wave_structure(BULL_ABC)
    prices = {p["label"]: p["price"] for p in out["wave_points"]}
    a_len = prices["0"] - prices["A"]
    zone = out["projected_c_zone"]
    for key, k in (
        ("0.618", 0.618),
        ("1.000", 1.0),
        ("1.272", 1.272),
        ("1.618", 1.618),
    ):
        assert zone["levels"][key] == pytest.approx(prices["B"] - k * a_len)
    assert zone["high"] == pytest.approx(prices["B"] - 0.618 * a_len)
    assert zone["low"] == pytest.approx(prices["B"] - 1.618 * a_len)
    assert zone["extended"]["high"] == pytest.approx(prices["B"] - 1.272 * a_len)
    assert zone["low"] < prices["C"] < zone["high"]


def test_abc_in_progress_moves_from_awaiting_to_inside_the_c_zone():
    statuses = []
    for k in range(len(BULL_ABC)):
        out = analyze_wave_structure(BULL_ABC[: k + 1])
        if out["active_pattern"] == "abc_in_progress":
            statuses.append(out["status"])
            zone, c = out["projected_c_zone"], out["wave_points"][-1]
            assert c["label"] == "C" and c["confirmed"] is False
            assert out["bias"] == "bullish"
            assert (c["price"] <= zone["high"]) == (out["status"] == "in_c_zone")
            # Breaks at the 1.618 extension or the prior origin, whichever is nearer.
            assert out["invalidation_price"] == pytest.approx(zone["low"])
    assert statuses and statuses[0] == "awaiting_c_zone"
    assert statuses[-1] == "in_c_zone"
    assert statuses == sorted(statuses)  # awaiting first, then in zone, no flip back


def test_bearish_abc_is_the_mirror_image():
    out = analyze_wave_structure(mirrored(BULL_ABC))
    bull = analyze_wave_structure(BULL_ABC)
    assert (out["active_pattern"], out["bias"]) == ("abc_complete", "bearish")
    assert out["fib_ratios"] == bull["fib_ratios"]
    assert out["invalidation_price"] == pytest.approx(200 - bull["invalidation_price"])
    assert out["target_price"] == pytest.approx(200 - bull["target_price"])
    assert out["projected_c_zone"]["direction"] == "up"


def test_count_breaks_when_price_trades_through_c():
    broken = path(ABC_LEGS + [(1, 96.0, 900)])
    out = analyze_wave_structure(broken)
    assert out["active_pattern"] != "abc_complete"


def test_return_to_wave_b_marks_the_target_reached():
    out = analyze_wave_structure(path(ABC_LEGS[:-1] + [(10, 107.0, 900)]))
    assert (out["active_pattern"], out["status"]) == ("abc_complete", "target_reached")


@pytest.mark.parametrize(
    "legs",
    [
        # B exceeds the start of A.
        [
            (40, 90.0, 1),
            (20, 110.0, 1),
            (8, 102.0, 1),
            (9, 111.0, 1),
            (12, 99.0, 1),
            (5, 104.0, 1),
        ],
        # C breaks the origin of the prior advance.
        [
            (40, 90.0, 1),
            (10, 100.0, 1),
            (8, 92.0, 1),
            (6, 96.0, 1),
            (9, 87.0, 1),
            (5, 92.0, 1),
        ],
    ],
)
def test_invalid_corrections_are_not_called_abc(legs):
    for k in range(60, sum(n for n, _, _ in legs) + 1):
        out = analyze_wave_structure(path(legs)[:k])
        assert not (
            out["active_pattern"] == "abc_complete" and out["bias"] == "bullish"
        )


# ─── impulses ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "prices, complete, ok",
    [
        ([100, 110, 104, 125, 116, 132], True, True),
        ([100, 110, 99, 125, 116, 132], True, False),  # wave 2 retraces > 100%
        ([100, 110, 104, 125, 109, 132], True, False),  # wave 4 overlaps wave 1
        ([100, 112, 104, 115, 113, 127], True, False),  # wave 3 is the shortest
        ([100, 110, 104, 125, 116, 124], True, False),  # wave 5 fails past wave 3
        ([100, 110, 104, 125, 116], False, True),
        ([100, 110, 104, 125, 110], False, False),
        ([100, 110, 104, 109], False, False),  # wave 3 has not passed wave 1
    ],
)
def test_impulse_hard_rules(prices, complete, ok):
    assert engine._impulse_ok([float(p) for p in prices], complete) is ok


IMPULSE_LEGS = [
    (40, 90.0, 1000),
    (10, 100.0, 1000),  # wave 1
    (6, 94.0, 1000),  # wave 2
    (16, 116.0, 1000),  # wave 3
    (7, 108.0, 1000),  # wave 4, stays above wave 1
    (10, 121.0, 1000),  # wave 5
    (5, 116.0, 1000),  # pullback that confirms wave 5
]


def test_five_wave_advance_is_tracked_then_completed():
    seen = []
    candles = path(IMPULSE_LEGS)
    for k in range(60, len(candles) + 1):
        out = analyze_wave_structure(candles[:k])
        if out["active_pattern"].startswith("impulse"):
            assert out["bias"] == "bullish"
            if not seen or seen[-1] != out["status"]:
                seen.append(out["status"])
    assert seen == ["wave_4_underway", "wave_5_underway", "complete"]
    final = analyze_wave_structure(candles)
    assert [p["label"] for p in final["wave_points"]] == ["0", "1", "2", "3", "4", "5"]
    assert final["invalidation_price"] == pytest.approx(90 - PAD)


def test_wave_four_overlap_invalidates_the_impulse_at_wave_one():
    legs = IMPULSE_LEGS[:4] + [(7, 108.0, 1000), (4, 112.0, 1000)]
    live = analyze_wave_structure(path(legs))
    assert (live["active_pattern"], live["status"]) == (
        "impulse_in_progress",
        "wave_5_underway",
    )
    assert live["invalidation_price"] == pytest.approx(100 + PAD)  # top of wave 1
    overlapped = analyze_wave_structure(path(legs + [(13, 99.0, 1000)]))
    assert not overlapped["active_pattern"].startswith("impulse")


# ─── confluence ──────────────────────────────────────────────────────────────


def test_higher_timeframe_trend_ranks_pullbacks_above_falling_knives():
    last_ts = BULL_ABC[-1][0]
    with_trend = analyze_wave_structure(
        BULL_ABC, higher_tf_candles=higher_tf(last_ts, True)
    )
    against = analyze_wave_structure(
        BULL_ABC, higher_tf_candles=higher_tf(last_ts, False)
    )
    alone = analyze_wave_structure(BULL_ABC)
    assert factor(with_trend, "higher_tf_trend")["state"] == "present"
    assert factor(against, "higher_tf_trend")["state"] == "opposed"
    assert factor(alone, "higher_tf_trend")["state"] == "unavailable"
    assert with_trend["confidence"] > alone["confidence"] > against["confidence"]
    assert with_trend["confluence_score"] > against["confluence_score"]
    assert against["confluence_confirmed"] is False
    assert "against this read" in against["summary"]


def test_unclosed_higher_timeframe_bars_are_ignored():
    last_ts = BULL_ABC[-1][0]
    closed = higher_tf(last_ts, True)
    # A still-forming bar that crashes must not change the read.
    forming = closed + [[closed[-1][0] + 14400, 1.0, 132.0, 131.0, 1.5, 9e9]]
    a = analyze_wave_structure(BULL_ABC, higher_tf_candles=closed)
    b = analyze_wave_structure(BULL_ABC, higher_tf_candles=forming)
    assert a == b


def test_volume_contraction_compares_wave_c_with_wave_a():
    out = analyze_wave_structure(BULL_ABC)
    vol = factor(out, "volume_contraction")
    assert vol["state"] == "present"
    assert vol["values"]["ratio"] == pytest.approx(0.5)
    loud = [(n, p, 3000 if i == 4 else v) for i, (n, p, v) in enumerate(ABC_LEGS)]
    assert (
        factor(analyze_wave_structure(path(loud)), "volume_contraction")["state"]
        == "absent"
    )


def test_confluence_score_is_the_clamped_sum_of_factor_scores():
    last_ts = BULL_ABC[-1][0]
    out = analyze_wave_structure(BULL_ABC, higher_tf_candles=higher_tf(last_ts, True))
    names = {f["name"] for f in out["confluence_factors"]}
    assert names == set(engine.WEIGHTS)
    total = sum(f["score"] for f in out["confluence_factors"])
    assert out["confluence_score"] == pytest.approx(max(0.0, min(1.0, total)), abs=1e-3)
    assert out["confluence_confirmed"] is (
        out["confluence_score"] >= engine.CONFLUENCE_THRESHOLD
    )
    assert sum(engine.WEIGHTS.values()) == pytest.approx(1.0)
    for f in out["confluence_factors"]:
        assert f["state"] in {"present", "absent", "opposed", "unavailable"}


def test_indicator_factors_survive_sub_cent_prices():
    tiny = [
        [ts, lo * 1e-7, hi * 1e-7, o * 1e-7, c * 1e-7, v]
        for ts, lo, hi, o, c, v in BULL_ABC
    ]
    small, normal = analyze_wave_structure(tiny), analyze_wave_structure(BULL_ABC)
    assert small["active_pattern"] == "abc_complete"
    assert [f["state"] for f in small["confluence_factors"]] == [
        f["state"] for f in normal["confluence_factors"]
    ]


# ─── contract ────────────────────────────────────────────────────────────────


def test_short_or_bad_history_falls_back_without_raising():
    for candles in (None, [], BULL_ABC[:30], [["x", 1, 2, 1, 2, 3]] * 80):
        out = analyze_wave_structure(candles)
        assert out["available"] is False
        assert out["active_pattern"] == "none"
        assert out["bias"] == "neutral"
        assert out["pivots"] == [] and out["invalidation_price"] is None
        json.dumps(out, allow_nan=False)


def test_result_is_deterministic_and_order_independent():
    shuffled = BULL_ABC[::-1]
    assert analyze_wave_structure(BULL_ABC) == analyze_wave_structure(shuffled)


def test_summary_is_descriptive_not_advice():
    for candles in (BULL_ABC, mirrored(BULL_ABC), path(IMPULSE_LEGS), random_walk()):
        text = analyze_wave_structure(candles)["summary"].lower()
        for word in ("buy", "sell", "entry", "exit", "should", "will "):
            assert word not in text


def test_resample_keeps_only_closed_buckets():
    hourly = path([(10, 110.0, 10)], t0=T0)  # ten 1h bars from a 4h boundary
    bars = resample_candles(hourly, 14400)
    assert [b[0] for b in bars] == [T0, T0 + 14400]  # the third bucket is still open
    first = hourly[:4]
    assert bars[0][1] == min(c[1] for c in first)
    assert bars[0][2] == max(c[2] for c in first)
    assert (bars[0][3], bars[0][4]) == (first[0][3], first[-1][4])
    assert bars[0][5] == sum(c[5] for c in first)
    assert len(resample_candles(hourly[:8], 14400)) == 2
