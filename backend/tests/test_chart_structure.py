"""Tests for chart_structure: synthetic candles only, no network."""

import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chart_structure as cs
from chart_reader import build_wave_analysis
from elliott_wave_engine import detect_pivots

STEP = 3600
T0 = 1_700_000_000 - 1_700_000_000 % 14400
PAD = 0.1

# Words a reader without charting vocabulary would not know.
JARGON = (
    "wave",
    "fib",
    "a-b-c",
    "abc",
    "rsi",
    "macd",
    "ema",
    "bollinger",
    "impulse",
    "retrace",
    "divergence",
    "confluence",
)
ADVICE = ("buy ", "sell ", "entry", "exit", "should", "will ")


def path(legs, start=100.0, t0=T0, step=STEP):
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


ABC_LEGS = [
    (40, 90.0, 1000),
    (20, 110.0, 1000),  # prior advance
    (8, 102.0, 1000),  # first dip
    (6, 106.0, 800),  # bounce
    (9, 97.0, 500),  # second dip, on lighter volume
    (5, 102.0, 900),  # turn back up
]
BULL_ABC = path(ABC_LEGS)
IMPULSE = path(
    [
        (40, 90.0, 1000),
        (10, 100.0, 1000),
        (6, 94.0, 1000),
        (16, 116.0, 1000),
        (7, 108.0, 1000),
        (10, 121.0, 1000),
        (5, 116.0, 1000),
    ]
)


def trend_bars(last_base_ts, rising=True, bars=40, step=14400):
    end = (last_base_ts + STEP) // step * step
    out = []
    for k in range(bars):
        ts = end - (bars - k) * step
        mid = 100.0 + (k if rising else -k) * 0.8
        out.append([ts, mid - 1.0, mid + 1.0, mid - 0.4, mid + 0.4, 5000])
    return out


def swings(prices, first="low"):
    other = {"low": "high", "high": "low"}
    kind, out = first, []
    for i, price in enumerate(prices):
        out.append({"ts": T0 + i * STEP, "price": price, "kind": kind})
        kind = other[kind]
    return out


def story_text(story):
    parts = [story["headline"]]
    for step in story["steps"]:
        parts += [step["title"], step["text"]]
    parts += [w["plain"] for w in story["why_it_matters"]]
    return " ".join(parts).lower()


# ─── swing history ────────────────────────────────────────────────────────────


def test_rising_swings_form_a_floor_of_higher_lows():
    out = cs.swing_history(swings([90, 100, 95, 108, 99, 112]))
    assert [s["label"] for s in out["swings"]] == [
        "Swing low",
        "Swing high",
        "Higher low",
        "Higher high",
        "Higher low",
        "Higher high",
    ]
    assert (out["trend"], out["higher_lows"], out["higher_highs"]) == ("up", 2, 2)
    assert [p["price"] for p in out["floor"]["points"]] == [90, 95, 99]
    assert out["floor"]["count"] == 2 and out["ceiling"] is None
    assert out["watch_level"] == 99
    assert out["headline"].startswith("2 higher lows in a row")
    assert "$99.00" in out["why"]


def test_falling_swings_form_a_ceiling_of_lower_highs():
    out = cs.swing_history(swings([120, 100, 115, 96, 110, 92], first="high"))
    assert (out["trend"], out["lower_highs"], out["lower_lows"]) == ("down", 2, 2)
    assert [p["price"] for p in out["ceiling"]["points"]] == [120, 115, 110]
    assert out["floor"] is None
    assert out["headline"].startswith("2 lower highs in a row")


def test_a_lower_low_restarts_the_run():
    out = cs.swing_history(swings([90, 100, 95, 104, 93, 106, 97, 109]))
    assert [s["relation"] for s in out["swings"] if s["kind"] == "low"] == [
        "first",
        "higher",
        "lower",
        "higher",
    ]
    assert out["higher_lows"] == 1
    assert [p["price"] for p in out["floor"]["points"]] == [93, 97]
    assert out["headline"] == (
        "The last dip stopped at a higher price than the one before it."
    )


def test_a_low_at_the_same_level_counts_as_a_hold():
    out = cs.swing_history(swings([90, 100, 90.3, 101, 95, 104]))
    lows = [s for s in out["swings"] if s["kind"] == "low"]
    assert lows[1]["relation"] == "equal"
    assert lows[1]["label"] == "Held the prior low"
    assert out["higher_lows"] == 2  # a hold keeps the floor intact


def test_mixed_or_missing_swings_say_so_without_raising():
    mixed = cs.swing_history(swings([100, 110, 96, 108]))
    assert mixed["trend"] == "mixed" and mixed["watch_level"] is not None
    for bad in (None, [], [{"ts": "x"}], [{"ts": 1, "price": -5, "kind": "low"}]):
        out = cs.swing_history(bad)
        assert out["swings"] == [] and out["floor"] is None
        assert out["trend"] == "mixed"


def test_earlier_labels_do_not_change_when_swings_are_added():
    rng = random.Random(11)
    candles, price = [], 100.0
    for k in range(400):
        open_ = price
        close = max(1.0, open_ + rng.gauss(0, 1.0))
        high, low = max(open_, close) + 0.3, max(0.5, min(open_, close) - 0.3)
        candles.append([T0 + k * STEP, low, high, open_, close, 1000])
        price = close
    pivots = [p.to_dict() for p in detect_pivots(candles)]
    assert len(pivots) >= 8
    full = cs.swing_history(pivots)["swings"]
    for k in range(1, len(pivots)):
        assert cs.swing_history(pivots[:k])["swings"] == full[:k]


# ─── plain-English story ──────────────────────────────────────────────────────


def test_bullish_pullback_reads_as_advance_dip_zone_and_recovery_target():
    wave = build_wave_analysis(BULL_ABC, "1h", trend_bars(BULL_ABC[-1][0]))
    story = wave["story"]
    assert wave["active_pattern"] == "abc_complete"
    assert story["kind"] == "pullback_in_advance"
    assert [s["key"] for s in story["steps"]] == [
        "prior_move",
        "zone",
        "target",
        "breaks",
    ]
    advance, zone, target, breaks = story["steps"]
    assert advance["title"] == "Prior advance" and "Rose 22.5%" in advance["text"]
    assert zone["title"] == "Pullback / dip zone"
    assert zone["low"] == wave["projected_c_zone"]["low"]
    assert "ended inside it" in zone["text"]
    assert target["title"] == "Recovery target"
    assert target["price"] == wave["target_price"]
    assert target["prior_extreme"] == pytest.approx(110 + PAD)
    assert breaks["title"] == f"Setup breaks below ${wave['invalidation_price']:.2f}"
    assert breaks["price"] == wave["invalidation_price"]
    assert [s.get("number") for s in story["steps"]] == [1, 2, 3, None]


def test_bearish_bounce_is_the_mirror_story():
    wave = build_wave_analysis(mirrored(BULL_ABC), "1h", [])
    story = wave["story"]
    assert story["kind"] == "bounce_in_decline"
    assert [s["title"] for s in story["steps"][:3]] == [
        "Prior decline",
        "Relief bounce zone",
        "Downside target",
    ]
    assert story["steps"][3]["title"].startswith("Setup breaks above $")
    assert story["steps"][3]["side"] == "above"


def test_zone_text_follows_price_into_the_zone():
    texts = []
    for k in range(60, len(BULL_ABC)):
        wave = build_wave_analysis(BULL_ABC[: k + 1], "1h", [])
        if wave["active_pattern"] != "abc_in_progress":
            continue
        zone = next(s for s in wave["story"]["steps"] if s["key"] == "zone")
        tail = zone["text"].split(". ", 1)[1]
        if not texts or texts[-1] != tail:
            texts.append(tail)
        inside = wave["status"] == "in_c_zone"
        assert ("inside the usual dip zone" in wave["story"]["headline"]) == inside
    assert texts == ["Price has not reached it yet.", "Price is inside it now."]


def test_finished_run_reads_as_extended():
    wave = build_wave_analysis(IMPULSE, "1h", [])
    story = wave["story"]
    assert wave["active_pattern"] == "impulse_complete"
    assert story["kind"] == "run_up"
    assert story["headline"] == "Extended run: a five-step advance looks complete"
    assert [s["key"] for s in story["steps"]] == ["prior_move", "stage", "breaks"]
    assert story["steps"][1]["title"] == "Run looks finished"


def test_supporting_signs_are_plain_with_the_technical_name_alongside():
    up = build_wave_analysis(BULL_ABC, "1h", trend_bars(BULL_ABC[-1][0]))
    signs = {w["name"]: w for w in up["story"]["why_it_matters"]}
    assert signs["volume_contraction"]["plain"] == "Dipping on lighter volume"
    assert signs["volume_contraction"]["technical"] == "Volume contraction"
    assert signs["higher_tf_trend"]["plain"] == "Bigger trend points up too"
    assert signs["higher_tf_trend"]["technical"] == "4h trend"
    assert all(w["state"] in ("present", "opposed") for w in signs.values())

    down = build_wave_analysis(
        BULL_ABC, "1h", trend_bars(BULL_ABC[-1][0], rising=False)
    )
    against = {w["name"]: w for w in down["story"]["why_it_matters"]}
    assert against["higher_tf_trend"]["state"] == "opposed"
    assert against["higher_tf_trend"]["plain"] == "Bigger trend points down"

    bear = build_wave_analysis(mirrored(BULL_ABC), "1h", [])
    bear_signs = {w["name"]: w for w in bear["story"]["why_it_matters"]}
    assert bear_signs["volume_contraction"]["plain"] == "Bouncing on lighter volume"


def test_story_wording_has_no_jargon_and_no_advice():
    reads = [
        build_wave_analysis(BULL_ABC, "1h", trend_bars(BULL_ABC[-1][0])),
        build_wave_analysis(mirrored(BULL_ABC), "1h", []),
        build_wave_analysis(IMPULSE, "1h", []),
        build_wave_analysis(mirrored(IMPULSE), "1h", []),
        build_wave_analysis(BULL_ABC[:82], "1h", []),  # second dip under way
        build_wave_analysis(IMPULSE[:80], "1h", []),  # run still going
    ]
    assert {r["active_pattern"] for r in reads} >= {
        "abc_complete",
        "abc_in_progress",
        "impulse_complete",
        "impulse_in_progress",
    }
    for wave in reads:
        text = story_text(wave["story"])
        history = (
            wave["swing_history"]["headline"] + " " + wave["swing_history"]["why"]
        ).lower()
        for word in JARGON + ADVICE:
            assert word not in text, (word, text)
            assert word not in history, (word, history)


def test_no_read_gives_an_empty_story_and_history():
    for wave in (None, {}, {"available": False}, {"available": True}):
        story = cs.plain_story(wave)
        assert story["kind"] == "none" and story["steps"] == []
    short = build_wave_analysis(BULL_ABC[:20], "1h")
    assert short["available"] is False
    assert short["story"]["kind"] == "none"
    assert short["swing_history"]["swings"] == []
    json.dumps(build_wave_analysis(BULL_ABC, "1h"))  # stays serializable


def test_wave_read_carries_history_for_every_confirmed_swing():
    wave = build_wave_analysis(BULL_ABC, "1h")
    assert len(wave["swing_history"]["swings"]) == len(wave["pivots"])
    assert len(wave["chart"]["candles"]) == len(BULL_ABC)


# ─── horizons ─────────────────────────────────────────────────────────────────


def test_horizons_cover_short_swing_and_macro():
    keys = [h["key"] for h in cs.horizon_list()]
    assert keys == ["short", "swing", "macro"]
    assert [h["timeframe"] for h in cs.horizon_list()] == ["15m", "1h", "4h"]
    assert cs.DEFAULT_HORIZON == "swing"
    cs.horizon_list()[0]["label"] = "changed"
    assert cs.HORIZONS["short"]["label"] == "Short-term"


# ─── Radar posture ────────────────────────────────────────────────────────────


def read(pattern, status, bias="bullish", factors=()):
    return {
        "available": True,
        "active_pattern": pattern,
        "status": status,
        "bias": bias,
        "confluence_factors": [{"name": n, "state": "present"} for n in factors],
    }


def test_trend_state_uses_the_engine_rule():
    last = BULL_ABC[-1][0]
    assert cs.trend_state(trend_bars(last, rising=True)) == "up"
    assert cs.trend_state(trend_bars(last, rising=False)) == "down"
    assert cs.trend_state(trend_bars(last)[:10]) == "unknown"
    flat = [[T0 + k * 14400, 99, 101, 100, 100, 1] for k in range(40)]
    assert cs.trend_state(flat) == "flat"


def test_finished_run_is_flagged_as_pullback_risk_on_any_timeframe():
    for tf in ("15m", "1h", "4h"):
        out = cs.radar_posture({tf: read("impulse_complete", "complete")}, "up")
        assert out["key"] == "extended_run" and out["tone"] == "risk"
        assert out["label"] == "Extended run · pullback risk"
        assert out["timeframe"] == tf
        assert "not been confirmed on new data" in out["detail"]
    # A finished run down is not a blow-off top.
    assert (
        cs.radar_posture({"1h": read("impulse_complete", "complete", "bearish")}, "up")
        is None
    )


def test_falling_four_hour_trend_is_flagged():
    out = cs.radar_posture({"1h": read("abc_complete", "confirmed")}, "down")
    assert out["key"] == "fighting_downtrend" and out["tone"] == "risk"
    assert out["label"] == "Fighting 4h downtrend"


def test_constructive_postures():
    bounce = cs.radar_posture({"1h": read("abc_complete", "confirmed")}, "up")
    assert bounce["key"] == "bounce_in_uptrend"
    assert bounce["label"] == "Bounce in 1h uptrend"
    assert bounce["tone"] == "constructive"

    in_zone = read("abc_in_progress", "in_c_zone", factors=("ema_reclaim",))
    reclaim = cs.radar_posture({"1h": in_zone}, "flat")
    assert reclaim["key"] == "reclaiming_zone"
    assert reclaim["label"] == "Reclaiming pullback zone"
    band = read("abc_in_progress", "in_c_zone", factors=("bollinger_reclaim",))
    assert cs.radar_posture({"4h": band}, "up")["timeframe"] == "4h"


def test_no_badge_without_a_clear_posture():
    quiet = [
        {},
        {"1h": None},
        {"1h": {"available": False}},
        {"1h": read("none", "none", "neutral")},
        {"1h": read("abc_in_progress", "in_c_zone")},  # in the zone, no reclaim yet
        {"1h": read("abc_in_progress", "awaiting_c_zone", factors=("ema_reclaim",))},
        {"1h": read("abc_complete", "target_reached")},
        {"1h": read("abc_complete", "confirmed", "bearish")},
        {"15m": read("abc_complete", "confirmed")},  # 15m alone is not enough
        {"1h": read("impulse_in_progress", "wave_5_underway")},
    ]
    for reads in quiet:
        assert cs.radar_posture(reads, "up") is None
        assert cs.radar_posture(reads, "unknown") is None


def test_risk_outranks_constructive():
    reads = {
        "15m": read("impulse_complete", "complete"),
        "1h": read("abc_complete", "confirmed"),
    }
    assert cs.radar_posture(reads, "down")["key"] == "extended_run"
    del reads["15m"]
    assert cs.radar_posture(reads, "down")["key"] == "fighting_downtrend"
    assert cs.radar_posture(reads, "flat")["key"] == "bounce_in_uptrend"


def test_radar_structure_reads_real_candles_end_to_end():
    bounce = cs.radar_structure([], BULL_ABC)
    assert bounce["reads"]["1h"]["active_pattern"] == "abc_complete"
    assert bounce["posture"]["key"] == "bounce_in_uptrend"
    assert bounce["outcome_validated"] is False

    quarter = path(
        [(b, end, vol) for b, end, vol in [(40, 90.0, 1), (10, 100.0, 1)]], step=900
    )
    run = cs.radar_structure(quarter, IMPULSE)
    assert run["posture"]["key"] == "extended_run"
    assert run["posture"]["timeframe"] == "1h"
    json.dumps(run)


def test_radar_structure_ignores_a_forming_candle_and_never_raises():
    closes_at = BULL_ABC[-1][0] + STEP
    forming = BULL_ABC + [[closes_at, 1.0, 400.0, 102.0, 1.0, 9]]
    steady = cs.radar_structure([], BULL_ABC, as_of_ts=closes_at)
    assert cs.radar_structure([], forming, as_of_ts=closes_at + 60) == steady
    for bad in (None, [], [[1, 2]], "junk"):
        out = cs.radar_structure(bad, bad)
        assert out["posture"] is None and out["reads"] == {}


def test_history_says_when_price_has_already_slipped_under_the_floor():
    rising = swings([90, 100, 95, 108, 99, 112])
    held = cs.swing_history(rising, last_price=104)
    assert held["floor"]["intact"] is True
    assert "watches for the next dip to hold above $99.00" in held["why"]
    slipped = cs.swing_history(rising, last_price=97)
    assert slipped["floor"]["intact"] is False
    assert slipped["headline"] == held["headline"]  # confirmed swings are unchanged
    assert "now below the latest of them ($99.00)" in slipped["why"]

    falling = swings([120, 100, 115, 96, 110, 92], first="high")
    assert cs.swing_history(falling, last_price=105)["ceiling"]["intact"] is True
    over = cs.swing_history(falling, last_price=111)
    assert over["ceiling"]["intact"] is False
    assert "now above the latest of them ($110.00)" in over["why"]


# ─── one-line header ──────────────────────────────────────────────────────────


def test_short_headline_names_the_zone_and_the_target_while_price_is_in_it():
    wave = build_wave_analysis(BULL_ABC[:82], "1h", [])
    zone, target = wave["projected_c_zone"], wave["target_price"]
    assert wave["status"] == "in_c_zone"
    assert wave["short_headline"] == (
        f"Inside dip zone (${zone['low']:.2f}–${zone['high']:.2f}) · "
        f"watching for a bounce toward ${target:.2f}"
    )
    early = build_wave_analysis(BULL_ABC[:77], "1h", [])
    assert early["status"] == "awaiting_c_zone"
    assert early["short_headline"].startswith("Pulling back toward dip zone ($")
    assert early["short_headline"].endswith(f"recovery target ${target:.2f}")


def test_short_headline_for_finished_pullbacks_and_runs():
    done = build_wave_analysis(BULL_ABC, "1h", [])
    assert done["short_headline"] == (
        f"Dip looks finished near ${done['invalidation_price']:.2f} · "
        f"recovery target ${done['target_price']:.2f}"
    )
    bear = build_wave_analysis(mirrored(BULL_ABC), "1h", [])
    assert bear["short_headline"].startswith("Bounce looks finished near $")
    assert "downside target $" in bear["short_headline"]

    run = build_wave_analysis(IMPULSE, "1h", [])
    assert run["short_headline"] == (
        "Extended run · five-step advance looks complete · breaks below $89.90"
    )
    going = build_wave_analysis(IMPULSE[:84], "1h", [])
    assert going["short_headline"].startswith(
        "Stair-step advance · intact while above $"
    )
    fall = build_wave_analysis(mirrored(IMPULSE[:84]), "1h", [])
    assert fall["short_headline"].startswith(
        "Stair-step decline · intact while below $"
    )


def test_short_headline_falls_back_to_the_run_of_swings_then_to_nothing():
    base = {"available": True, "active_pattern": "none"}
    lower = cs.swing_history(swings([120, 100, 115, 96, 110, 92], first="high"))
    assert cs.short_headline({**base, "swing_history": lower}) == (
        "2 lower highs in a row · needs a break above $110.00"
    )
    higher = cs.swing_history(swings([90, 100, 95, 108, 99, 112]))
    assert cs.short_headline({**base, "swing_history": higher}) == (
        "2 higher lows in a row · floor at $99.00"
    )
    mixed = cs.swing_history(swings([100, 110, 96, 108]))
    assert cs.short_headline({**base, "swing_history": mixed}) == (
        "No clear setup in the recent swings"
    )
    for wave in (None, {}, {"available": False}, base, {**base, "swing_history": {}}):
        assert cs.short_headline(wave) is None
    assert build_wave_analysis(BULL_ABC[:20], "1h")["short_headline"] is None


def test_short_headline_has_no_jargon_and_no_advice():
    lines = [
        build_wave_analysis(candles, "1h", [])["short_headline"]
        for candles in (
            BULL_ABC,
            BULL_ABC[:77],
            BULL_ABC[:82],
            mirrored(BULL_ABC),
            mirrored(BULL_ABC[:82]),
            IMPULSE,
            IMPULSE[:80],
            mirrored(IMPULSE),
        )
    ]
    assert all(lines)
    for line in lines:
        for word in JARGON + ADVICE:
            assert word not in line.lower(), (word, line)
