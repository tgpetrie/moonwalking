"""Tests for chart_structure: synthetic candles only, no network."""

import json
import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chart_structure as cs
import cycle_analysis as ca
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


def test_cycle_context_math_and_historical_shelves():
    candles = [
        [86400 * i, 50 if i == 0 else 60, 200 if i == 2 else 120, 100, 92, 10 + i]
        for i in range(5)
    ]
    context = cs.multi_year_context(candles)
    assert context["cycle_low"] == {"price": 50, "timestamp": 0}
    assert context["cycle_high"] == {"price": 200, "timestamp": 172800}
    assert context["pct_from_cycle_high"] == -54
    assert context["cycle_range_position_pct"] == 28
    assert context["macro_fib_levels"]["0.5"] == 125
    assert context["log_fib_retracements"]["0.5"] == pytest.approx(100)
    assert context["log_fib_retracements"]["0.886"] == pytest.approx(200 ** 0.114 * 50 ** 0.886)
    assert any(z["kind"] == "support" and z["touches"] == 4 for z in context["major_historical_zones"])
    assert context["missing_days"] == 0
    assert cs.multi_year_context([])["available"] is False


def test_top_down_support_boxes_and_wave_b_pivot():
    cycle = cs.multi_year_context([[86400 * i, 50, 200, 100, 100, 1] for i in range(365)])
    wave = {"available": True, "bias": "bullish", "active_pattern": "abc_in_progress",
            "wave_points": [{"label": "start", "price": 60}, {"label": "0", "price": 140}, {"label": "B", "price": 125}],
            "projected_c_zone": {"low": 80, "high": 90}}
    out = cs.top_down_confluence(cycle, {"1h": wave}, 150)
    assert out["at_multi_year_support"] is True
    assert out["micro_support_box"] == pytest.approx({"low": 77.12, "high": 100})
    assert out["micro_breakout_pivot"] == 125
    assert cs.top_down_confluence(cycle, {}, 190)["at_multi_year_support"] is False
    assert cs.top_down_confluence({"available": False}, {}, 100)["available"] is False
    wave = {"available": True, "bias": "bullish", "active_pattern": "impulse_in_progress",
            "pivots": [{"kind": "low", "price": 60}, {"kind": "high", "price": 140}]}
    out = cs.top_down_confluence(cycle, {"4h": wave}, 190)
    assert out["micro_timeframe"] == "4h"
    assert out["micro_support_box"] == pytest.approx({"low": 77.12, "high": 100})


def test_cycle_weekly_bars_require_complete_monday_weeks():
    from chart_reader import aggregate_weekly_candles

    monday = 4 * 86400
    days = [[monday + i * 86400, 9, 12, 10, 11, i + 1] for i in range(8)]
    assert aggregate_weekly_candles(days) == [[float(monday), 9, 12, 10, 11, 28]]
    assert aggregate_weekly_candles(days[:3] + days[4:]) == []


def test_cycle_loader_pages_caches_and_excludes_forming_day(monkeypatch, tmp_path):
    from datetime import datetime
    import chart_reader

    now = 20000 * 86400 + 100
    monkeypatch.setattr(chart_reader.time, "time", lambda: now)
    monkeypatch.setenv("MW_CYCLE_HISTORY_DB", str(tmp_path / "history.sqlite"))
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return self.bars

    def fake_get(url, *, params, timeout):
        begin = datetime.fromisoformat(params["start"]).timestamp()
        end = datetime.fromisoformat(params["end"]).timestamp()
        assert end - begin < 300 * 86400
        calls.append((begin, end))
        response = Response()
        response.bars = [[begin, 9, 12, 10, 11, 1]]
        return response

    monkeypatch.setattr(chart_reader.requests, "get", fake_get)
    first = chart_reader.fetch_multi_year_daily_candles("BTC-USD")
    assert len(calls) == 4
    assert len(first) == 4 and first == sorted(first, reverse=True)
    assert first[0][0] < now - 100
    assert chart_reader.fetch_multi_year_daily_candles("BTC-USD") == first
    assert len(calls) == 4


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


def test_horizons_cover_short_swing_macro_and_cycle():
    keys = [h["key"] for h in cs.horizon_list()]
    assert keys == ["short", "swing", "macro", "cycle"]
    assert [h["timeframe"] for h in cs.horizon_list()] == ["15m", "1h", "4h", "1d"]
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


# ─── multi-timeframe cycle read ───────────────────────────────────────────────


RETRACEMENT_KEYS = ["0.236", "0.309", "0.382", "0.5", "0.618", "0.702", "0.786", "0.886"]
EXTENSION_KEYS = ["1.272", "1.618", "2.618", "3.618", "4.236"]


def _top_down(context):
    return cs.top_down_confluence(context, {}, context["current_price"])


def test_wilder_rsi_matches_a_hand_calculation():
    # Alternating +2 / -1: average gain 1.0 and average loss 0.5 after 14 changes.
    closes = [100.0]
    for i in range(15):
        closes.append(closes[-1] + (2.0 if i % 2 == 0 else -1.0))
    rsi = ca.wilder_rsi(closes)
    assert rsi[:14] == [None] * 14
    assert rsi[14] == pytest.approx(100 - 100 / (1 + 1.0 / 0.5))
    gain, loss = (1.0 * 13 + 2.0) / 14, 0.5 * 13 / 14
    assert rsi[15] == pytest.approx(100 - 100 / (1 + gain / loss))
    assert ca.wilder_rsi([float(i) for i in range(1, 30)])[-1] == 100.0
    assert ca.wilder_rsi([5.0] * 30)[-1] == 50.0
    assert ca.wilder_rsi([1.0, 2.0]) == [None, None]


def test_rsi_regime_boundaries_and_bull_support_flag():
    assert ca.rsi_regime(39.99)["regime"] == "oversold_compression"
    assert ca.rsi_regime(40.0)["regime"] == "no_mans_land"
    assert ca.rsi_regime(60.0)["regime"] == "no_mans_land"
    assert ca.rsi_regime(60.01)["regime"] == "growth_expansion"
    assert ca.rsi_regime(None) == {"regime": "unavailable", "near_bull_support": False}
    for value, expected in ((37.9, False), (38.0, True), (41.0, True), (44.0, True), (44.1, False)):
        assert ca.rsi_regime(value, uptrend=True)["near_bull_support"] is expected
    # 38-40 is still oversold by regime, and never bull support in a downtrend.
    assert ca.rsi_regime(39.0, uptrend=True)["regime"] == "oversold_compression"
    assert ca.rsi_regime(41.0, uptrend=False)["near_bull_support"] is False


def test_macd_and_stoch_rsi_warm_up_then_stay_in_range():
    closes = [100.0 + 10.0 * math.sin(i / 5.0) for i in range(80)]
    line, signal, hist = ca.macd(closes)
    assert line[24] is None and line[25] is not None
    assert signal[32] is None and signal[33] is not None
    assert hist[40] == pytest.approx(line[40] - signal[40])
    flat_line, flat_signal, flat_hist = ca.macd([7.0] * 60)
    assert flat_line[-1] == pytest.approx(0) and flat_hist[-1] == pytest.approx(0)
    k, d = ca.stoch_rsi(closes)
    assert k[28] is None and k[29] is not None
    assert d[30] is None and d[31] is not None
    assert all(0.0 <= v <= 100.0 for v in k + d if v is not None)
    assert d[-1] == pytest.approx(sum(k[-3:]) / 3)


def test_weekly_and_monthly_bars_leave_out_the_forming_period():
    monday = 4 * 86400  # 5 January 1970
    days = [(monday + i * 86400, 9.0, 12.0 + i, 10.0, 11.0 + i, 1.0) for i in range(17)]
    weeks = ca.weekly_bars(days)
    assert [w[0] for w in weeks] == [monday, monday + 7 * 86400]
    assert weeks[0][1:] == (9.0, 18.0, 10.0, 17.0, 7.0)
    january = [(i * 86400, 9.0, 12.0, 10.0, 11.0 + i, 1.0) for i in range(45)]
    months = ca.monthly_bars(january)
    assert len(months) == 1 and months[0][0] == 0 and months[0][4] == 41.0
    assert ca.weekly_bars([]) == [] and ca.monthly_bars([]) == []


def test_render_fixture_is_a_three_leg_decline_with_monthly_exhaustion_and_a_macd_kiss(cycle_fixture):
    context = cs.multi_year_context(cycle_fixture("render_cycle_fixture"))
    assert context["candle_count"] == 1096 and context["is_multi_year"] is True
    assert context["timeframe_bars"] == {"1d": 1096, "1w": 157, "1m": 35}

    # 5-3-5: two lows separated by one rally, the second lower.
    structure = context["corrective_structure"]
    assert structure["kind"] == "wxy_zigzag" and structure["legs"] == 3
    assert [p["kind"] for p in structure["swings"]] == ["low", "high", "low"]

    monthly = context["monthly_cycle_exhaustion"]
    assert monthly["monthly_bearish_streak"] >= 18
    assert monthly["histogram_shrinking"] is True
    assert monthly["monthly_macd_histogram"] > monthly["previous_monthly_macd_histogram"]
    assert monthly["multi_year_oversold_exhaustion"] is True

    signals = context["macd_signals"]
    assert signals["daily_macd_kiss"] is True
    daily = signals["1d"]
    assert daily["previous_histogram"] < daily["histogram"] < 0
    assert abs(daily["histogram"]) < abs(daily["macd"]) * 0.15

    regimes = context["rsi_regimes"]
    assert {tf: regimes[tf]["regime"] for tf in ("1d", "1w", "1m")} == {
        "1d": "oversold_compression",
        "1w": "oversold_compression",
        "1m": "oversold_compression",
    }

    top = _top_down(context)
    assert top["at_multi_year_support"] is True
    assert top["cycle_pattern"]["kind"] == "wxy_terminal_sweep"
    assert top["cycle_pattern"]["terminal_wave_5"] is True
    pivot = top["low_confirmation_pivot"]
    assert pivot["price"] > context["current_price"]
    assert pivot["message"] == "Break above $1.88 signals cycle low is in"
    assert top["active_target_tier"] == "rollover_target_box"


def test_fet_fixture_is_a_channel_double_bottom_with_a_weekly_turn_and_a_tight_stop(cycle_fixture):
    candles = cycle_fixture("fet_channel_fixture")
    context = cs.multi_year_context(candles)

    structure = context["corrective_structure"]
    assert structure["kind"] == "abcde_channel" and structure["legs"] == 5
    channel = structure["channel"]
    assert channel["holds"] is True and channel["testing_now"] is True
    # The E low dips through the line through A and C, by less than the allowance.
    assert channel["overthrow"] is True
    assert -ca.CHANNEL_OVERTHROW * 100 < channel["e_deviation_pct"] < 0
    assert structure["double_bottom_retest"] is True
    assert abs(structure["double_bottom_gap_pct"]) <= ca.DOUBLE_BOTTOM_TOLERANCE * 100

    stoch = context["weekly_stoch_rsi"]
    assert stoch["direction"] == "oversold_turn_up"
    assert stoch["weekly_stoch_rsi_d"] < stoch["weekly_stoch_rsi_k"] < 25

    rows = sorted(tuple(c) for c in candles)
    weekly_closes = [w[4] for w in ca.weekly_bars(rows)]
    ladder = context["weekly_sma_ladder"]
    assert ladder["sma_50w"] == pytest.approx(sum(weekly_closes[-50:]) / 50)
    assert ladder["sma_100w"] == pytest.approx(sum(weekly_closes[-100:]) / 100)
    assert ladder["overhead_resistance"] == ["sma_50w", "sma_100w"]
    assert ladder["reclaimed_support"] == []
    # Three years is 157 closed weeks: the 200-week average is reported as
    # unavailable, never estimated from fewer bars.
    assert ladder["sma_200w"] is None
    assert ladder["levels"][2] == {
        "key": "sma_200w", "period": 200, "value": None, "available": False,
        "role": None, "distance_pct": None, "bars_needed": 200,
    }

    top = _top_down(context)
    assert top["at_multi_year_support"] is True and top["in_accumulation_box"] is True
    assert top["cycle_pattern"]["kind"] == "abcde_channel_test"
    assert top["cycle_pattern"]["double_bottom"] is True
    assert top["cycle_pattern"]["channel_overthrow"] is True
    stop = top["accumulation_invalidation_stop"]
    assert stop["basis"] == "double_bottom_low"
    assert stop["stop_price"] == pytest.approx(stop["reference_low"] * 0.98)
    assert stop["stop_price"] < context["daily_structure"]["structural_low"]["price"]
    assert 0 < stop["stop_distance_pct"] < 10 and stop["tight"] is True
    assert top["low_confirmation_pivot"]["kind"] == "wave_4_swing_high"


def test_weekly_sma_ladder_fills_in_the_200_week_average_with_a_fourth_year(cycle_fixture):
    candles = cycle_fixture("fet_channel_fixture")
    first = candles[0]
    earlier = [
        [first[0] - (365 - i) * 86400, first[1], first[2], first[3], first[3], first[5]]
        for i in range(365)
    ]
    context = cs.multi_year_context(earlier + candles)
    assert context["history_candle_count"] == 1461 and context["candle_count"] == 1096
    ladder = context["weekly_sma_ladder"]
    weekly_closes = [w[4] for w in ca.weekly_bars(sorted(tuple(c) for c in earlier + candles))]
    assert len(weekly_closes) >= 200
    assert ladder["sma_200w"] == pytest.approx(sum(weekly_closes[-200:]) / 200)
    assert ladder["overhead_resistance"] == ["sma_50w", "sma_100w", "sma_200w"]
    assert all(level["role"] == "resistance" for level in ladder["levels"])
    # The range still comes from the trailing three years.
    assert context["first_timestamp"] == first[0]


def test_weekly_sma_ladder_marks_reclaimed_averages_as_support(daily_series):
    context = cs.multi_year_context(daily_series(10, [(1461, 60)]))
    ladder = context["weekly_sma_ladder"]
    assert ladder["overhead_resistance"] == []
    assert ladder["reclaimed_support"] == ["sma_50w", "sma_100w", "sma_200w"]
    assert ladder["levels"][0]["distance_pct"] < 0


def test_theta_fixture_filters_the_flash_wick_and_finds_the_dual_grid_cluster(cycle_fixture):
    fixture = cycle_fixture("theta_wxy_confluence_fixture", full=True)
    context = cs.multi_year_context(fixture["candles"])

    wick = context["flash_wick_filter"]
    assert wick["applied"] is True and wick["threshold_multiple"] == 3.5
    assert [f["timestamp"] for f in wick["filtered"]] == [fixture["flash_wick_timestamp"]]
    assert wick["filtered"][0]["side"] == "low"
    assert wick["filtered"][0]["wick_multiple"] > 3.5
    # The raw extreme is recorded; the grid is anchored on the filtered low.
    assert context["raw_cycle_low"]["timestamp"] == fixture["flash_wick_timestamp"]
    assert context["raw_cycle_low"]["price"] == pytest.approx(wick["filtered"][0]["raw_price"])
    assert context["raw_cycle_low"]["price"] < context["cycle_low"]["price"] * 0.5
    assert context["cycle_low"]["timestamp"] != fixture["flash_wick_timestamp"]

    assert list(context["log_fib_retracements"]) == RETRACEMENT_KEYS
    assert list(context["macro_fib_levels"]) == RETRACEMENT_KEYS
    assert list(context["drawdown_log_retracements"]) == RETRACEMENT_KEYS
    assert list(context["secondary_log_extensions"]) == EXTENSION_KEYS

    low, high = context["cycle_low"]["price"], context["cycle_high"]["price"]
    wave_x = context["secondary_wave_x_high"]
    assert wave_x["kind"] == "wave_x" and low < wave_x["price"] < high
    for ratio in (0.618, 0.702, 0.786):
        assert context["drawdown_log_retracements"][str(ratio)] == pytest.approx(
            low * (high / low) ** ratio
        )
    for ratio in (1.618, 4.236):
        assert context["secondary_log_extensions"][str(ratio)] == pytest.approx(
            low * (wave_x["price"] / low) ** ratio
        )

    clusters = context["fib_confluence_clusters"]
    assert [(c["retracement_ratio"], c["extension_ratio"]) for c in clusters] == [(0.786, 1.618)]
    cluster = clusters[0]
    assert cluster["spread_pct"] < 6 and cluster["conviction"] == "high"
    assert cluster["low"] <= cluster["mid"] <= cluster["high"]
    assert cluster["position"] == "above_price" and 0 < cluster["score"] <= 1

    box = context["rollover_target_box"]
    assert box["label"] == "Conservative / High-Probability Rollover Zone"
    assert list(box["levels"]) == ["0.618", "0.702", "0.786"]
    assert box["low"] == box["levels"]["0.618"] and box["high"] == box["levels"]["0.786"]
    assert box["price_position"] == "below" and box["clusters"] == clusters
    assert [c["source"] for c in box["extension_confluence"]] == ["secondary_range"]

    full = context["full_extension_targets"]
    assert full["label"] == "Full Alt-Season Extension Confluence"
    assert [t["ratio"] for t in full["targets"]] == [1.618, 2.618, 3.618, 4.236]
    assert [t["confluence"] for t in full["targets"]] == [True, False, False, False]

    top = _top_down(context)
    assert context["corrective_structure"]["kind"] == "wxy_zigzag"
    assert context["corrective_structure"]["at_historic_base"] is True
    assert top["cycle_pattern"]["kind"] == "wxy_terminal_sweep"
    assert top["fib_confluence_clusters"] == clusters
    assert top["rollover_target_box"] == box and top["full_extension_targets"] == full


def test_without_the_wick_filter_the_theta_grid_would_move(cycle_fixture):
    fixture = cycle_fixture("theta_wxy_confluence_fixture", full=True)
    rows = sorted(tuple(c) for c in fixture["candles"])
    lows, highs, info = ca.flash_filtered_extremes(rows)
    index = next(i for i, r in enumerate(rows) if r[0] == fixture["flash_wick_timestamp"])
    assert lows[index] == min(rows[index][3], rows[index][4]) > rows[index][1]
    assert highs == [r[2] for r in rows]
    # An ordinary wick is left alone.
    assert sum(1 for i, r in enumerate(rows) if lows[i] != r[1]) == 1
    assert info["median_weekly_range_pct"] > 0


def test_fib_clusters_need_the_two_grids_within_six_percent(daily_series):
    # The same decline with a smaller Wave X rally: its 1.618 extension lands
    # well below the 0.786 retracement, so there is no cluster.
    legs = [(210, 0.9), (120, 3.7), (240, 1.06), (150, 1.3), (346, 0.76), (30, 0.8)]
    context = cs.multi_year_context(daily_series(0.92, legs))
    assert context["secondary_wave_x_high"]["kind"] == "wave_x"
    assert context["fib_confluence_clusters"] == []
    assert context["full_extension_targets"]["available"] is True
    assert not any(t["confluence"] for t in context["full_extension_targets"]["targets"])


def test_targets_are_unavailable_without_a_macro_drawdown(daily_series):
    context = cs.multi_year_context(daily_series(10, [(1096, 60)]))
    assert context["macro_drawdown"]["available"] is False
    assert context["rollover_target_box"] == {"available": False, "reason": "no_macro_drawdown"}
    assert context["full_extension_targets"]["available"] is False
    assert context["fib_confluence_clusters"] == []
    top = _top_down(context)
    assert top["at_multi_year_support"] is False
    assert top["low_confirmation_pivot"] is None
    assert top["accumulation_invalidation_stop"] is None


def test_weekly_bullish_divergence_on_a_lower_low_and_on_a_retest(daily_series):
    base = [(120, 40), (1011, 12), (60, 6), (70, 8.6)]
    lower = cs.multi_year_context(daily_series(30, base + [(200, 5.9)]))["macd_signals"]
    assert lower["macro_bullish_divergence"] is True
    assert lower["divergence"]["kind"] == "lower_low"
    assert lower["divergence"]["rsi"]["second"] > lower["divergence"]["rsi"]["first"]
    assert "rsi" in lower["divergence"]["confirmed_by"]
    retest = cs.multi_year_context(daily_series(30, base + [(200, 6.15)]))["macd_signals"]
    assert retest["macro_bullish_divergence"] is True
    assert retest["divergence"]["kind"] == "double_bottom_retest"
    # One straight decline has no second low to compare.
    straight = cs.multi_year_context(daily_series(30, [(120, 40), (1131, 14), (70, 17), (140, 6)]))
    assert straight["macd_signals"]["macro_bullish_divergence"] is False
    assert straight["macd_signals"]["divergence"] is None


def test_weekly_macd_cross_is_reported_on_the_week_it_happens():
    falling = [100.0 - i for i in range(60)]
    assert ca._weekly_cross(falling)["weekly_macd_bullish_cross"] is False
    # Extend a decline with a rally until the histogram first turns positive.
    closes = list(falling)
    for step in range(1, 40):
        closes.append(closes[-1] + 2.0)
        state = ca._weekly_cross(closes)
        if state["weekly_macd_above_signal"]:
            break
    assert state["weekly_macd_bullish_cross"] is True
    assert state["weeks_since_weekly_bullish_cross"] == 0
    later = ca._weekly_cross(closes + [closes[-1] + 2.0])
    assert later["weekly_macd_bullish_cross"] is False
    assert later["weekly_macd_above_signal"] is True
    assert later["weeks_since_weekly_bullish_cross"] == 1


def test_confirmation_breakout_once_price_closes_above_the_prior_swing_high(daily_series):
    legs = [(120, 40), (1200, 4.2), (25, 5.0), (40, 3.5), (76, 5.4)]
    context = cs.multi_year_context(daily_series(30, legs))
    breakout = context["daily_structure"]["confirmation_breakout"]
    assert breakout["broken"] is True and breakout["recent"] is True
    assert breakout["pivot_price"] < context["current_price"]
    assert breakout["bars_since_break"] <= 30
    assert _top_down(context)["confirmation_breakout"] == breakout


def test_the_cycle_range_uses_the_trailing_three_years_only(daily_series):
    # A deep low in the first of four years is warm-up, not the cycle low, but
    # it is the base the later advance started from.
    candles = daily_series(4.0, [(200, 1.0), (165, 8.0), (300, 40.0), (796, 1.15)])
    context = cs.multi_year_context(candles)
    assert context["history_candle_count"] == 1461 and context["candle_count"] == 1096
    assert context["first_timestamp"] == candles[365][0]
    assert context["cycle_low"]["timestamp"] >= candles[365][0]
    base = context["corrective_structure"]["historic_base"]
    assert base["timestamp"] < candles[365][0]
    assert base["low"] == pytest.approx(min(c[1] for c in candles[:365]))
    assert context["corrective_structure"]["at_historic_base"] is True


def test_macro_gate_switches_the_active_target_tier(cycle_fixture):
    context = cs.multi_year_context(cycle_fixture("theta_wxy_confluence_fixture"))
    for stage, tier in cs.TARGET_TIER_BY_STAGE.items():
        top = cs.apply_macro_regime(
            _top_down(context),
            {"liquidity_rotation_stage": stage, "macro_regime_gate": "neutral_chop"},
        )
        assert top["active_target_tier"] == tier
        assert top["liquidity_rotation_stage"] == stage
        assert top["macro_regime_gate"] == "neutral_chop"
    assert tier == "full_extension_targets"
    none = cs.apply_macro_regime(_top_down(context), None)
    assert none["active_target_tier"] == "rollover_target_box"
    assert none["macro_regime_gate"] is None
    assert cs.apply_macro_regime({"available": False}, {"liquidity_rotation_stage": stage}) == {"available": False}


def test_macro_gate_keeps_the_box_when_a_coin_has_no_extension_targets(cycle_fixture, daily_series):
    context = cs.multi_year_context(daily_series(30, [(120, 40), (976, 4.0)]))
    assert context["full_extension_targets"]["available"] is False
    top = cs.apply_macro_regime(
        _top_down(context),
        {"liquidity_rotation_stage": "stage_4_alt_season_expansion", "macro_regime_gate": "risk_on_aligned"},
    )
    assert top["active_target_tier"] == "rollover_target_box"
    assert top["macro_regime_gate"] == "risk_on_aligned"


def test_cycle_read_on_a_short_history_reports_what_is_missing():
    candles = [[86400 * i, 9.0, 12.0, 10.0, 11.0, 1.0] for i in range(40)]
    context = cs.multi_year_context(candles)
    assert context["available"] is True and context["is_multi_year"] is False
    assert context["rsi_regimes"]["1w"]["regime"] == "unavailable"
    assert context["weekly_stoch_rsi"]["available"] is False
    assert context["monthly_cycle_exhaustion"]["available"] is False
    assert context["monthly_cycle_exhaustion"]["multi_year_oversold_exhaustion"] is False
    assert context["macd_signals"]["daily_macd_kiss"] is False
    assert context["weekly_sma_ladder"]["sma_50w"] is None
    assert context["flash_wick_filter"]["filtered"] == []
    assert context["outcome_validated"] is False
    json.dumps(context)  # the whole read serialises


def test_cycle_fixtures_match_their_generator(cycle_fixture):
    import importlib.util

    path = os.path.join(os.path.dirname(__file__), "fixtures", "build_cycle_fixtures.py")
    spec = importlib.util.spec_from_file_location("build_cycle_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for build in (module.render, module.fet, module.theta):
        built = build()
        stored = cycle_fixture(built["name"], full=True)
        assert stored["candles"] == built["candles"]
        assert len(stored["candles"]) == 1096 and stored["synthetic"] is True
        times = [c[0] for c in stored["candles"]]
        assert times == sorted(times) and times[-1] - times[0] == 1095 * 86400
