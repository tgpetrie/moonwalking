"""Tests for macro_industry_scanner: synthetic candles only, no network."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import macro_industry_scanner as mis

DAY = 86400


def bars(closes, t0=0):
    """Tight daily bars around a list of closes."""
    out, prior = [], closes[0]
    for i, close in enumerate(closes):
        out.append([t0 + i * DAY, min(prior, close) * 0.99, max(prior, close) * 1.01, prior, close, 10.0])
        prior = close
    return out


@pytest.fixture
def shapes(daily_series, cycle_fixture):
    """Four-year series for each cycle state, plus the three-year fixtures."""

    def breakout(scale):
        legs = [(120, 40 * scale), (1200, 4.2 * scale), (25, 5.0 * scale), (40, 3.5 * scale), (76, 5.4 * scale)]
        return daily_series(30 * scale, legs)

    return {
        "up": daily_series(10, [(1461, 60)]),
        "down": daily_series(60, [(200, 80), (1261, 8)]),
        "rollover": daily_series(5, [(200, 40), (700, 6), (561, 22)]),
        "breakout": breakout,
        "render": cycle_fixture("render_cycle_fixture"),
        "fet": cycle_fixture("fet_channel_fixture"),
        "theta": cycle_fixture("theta_wxy_confluence_fixture"),
    }


# ─── altcoin index ────────────────────────────────────────────────────────────


def test_alt_index_chains_the_average_log_move_of_its_members():
    histories = {
        "AAA-USD": bars([10.0, 11.0, 12.1]),
        "BBB-USD": bars([100.0, 100.0, 90.0]),
        "CCC-USD": bars([1.0, 2.0, 2.0]),
        "BTC-USD": bars([5.0, 50.0, 500.0]),  # majors never join the index
    }
    index = mis.build_alt_index(histories)
    assert index["available"] is True and index["name"] == "ALT_INDEX_3Y"
    assert index["members"] == ["AAA-USD", "BBB-USD", "CCC-USD"]
    candles = index["candles"]
    assert [c[0] for c in candles] == [DAY, 2 * DAY]
    day_one = 100 * math.exp((math.log(1.1) + math.log(1.0) + math.log(2.0)) / 3)
    day_two = day_one * math.exp((math.log(1.1) + math.log(0.9) + math.log(1.0)) / 3)
    assert candles[0][4] == pytest.approx(day_one)
    assert candles[1][4] == pytest.approx(day_two)
    assert candles[1][3] == pytest.approx(day_one)  # opens where the prior day closed
    for _ts, low, high, open_, close, volume in candles:
        assert low <= min(open_, close) <= max(open_, close) <= high and volume > 0
    assert "not market-cap weighted" in index["method"]


def test_alt_index_lets_a_late_listing_join_without_a_jump():
    steady = [10.0 * 1.01**i for i in range(6)]
    histories = {
        "AAA-USD": bars(steady),
        "BBB-USD": bars(steady),
        "CCC-USD": bars(steady),
        "NEW-USD": bars([500.0, 505.0, 510.05], t0=3 * DAY),
    }
    index = mis.build_alt_index(histories)
    closes = [c[4] for c in index["candles"]]
    assert len(closes) == 5 and index["min_members_on_a_day"] == 3
    for before, after in zip(closes, closes[1:]):
        assert after / before == pytest.approx(1.01)


def test_alt_index_needs_three_members_and_prefers_the_named_basket(shapes):
    two = {"AAA-USD": bars([1.0, 2.0, 3.0]), "BBB-USD": bars([1.0, 2.0, 3.0])}
    assert mis.build_alt_index(two) == {
        "available": False,
        "name": "ALT_INDEX_3Y",
        "reason": "too_few_members",
        "members": ["AAA-USD", "BBB-USD"],
    }
    named = {name: bars([1.0, 1.1, 1.2]) for name in ("SOL-USD", "XRP-USD", "ADA-USD")}
    named["ZZZ-USD"] = bars([9.0, 1.0, 9.0])
    assert mis.build_alt_index(named)["members"] == ["ADA-USD", "SOL-USD", "XRP-USD"]
    explicit = mis.build_alt_index(named, members=["SOL-USD", "XRP-USD", "ZZZ-USD"])
    assert explicit["members"] == ["SOL-USD", "XRP-USD", "ZZZ-USD"]
    long_index = mis.build_alt_index({f"{k}-USD": shapes["up"] for k in "ABC"})
    assert long_index["bars"] == mis.ALT_INDEX_WINDOW_DAYS == 1096


# ─── stage and gate ───────────────────────────────────────────────────────────


def _regime(histories):
    scan = mis.scan_universe_cycles(histories)
    return scan["industry"], scan


def test_stage_one_when_everything_is_compressed(shapes):
    regime, scan = _regime(
        {"BTC-USD": shapes["down"], "ETH-USD": shapes["down"],
         "A-USD": shapes["render"], "B-USD": shapes["fet"], "C-USD": shapes["theta"]}
    )
    assert regime["liquidity_rotation_stage"] == "stage_1_macro_compression"
    assert regime["stage_number"] == 1 and regime["stage_label"].startswith("Stage 1")
    assert regime["macro_regime_gate"] == "risk_off_headwind"
    assert regime["active_target_tier"] == "rollover_target_box"
    assert regime["components"]["BTC-USD"]["compressed"] is True
    assert regime["alt_index"]["members"] == ["A-USD", "B-USD", "C-USD"]
    assert "candles" not in regime["alt_index"]
    assert regime["outcome_validated"] is False
    assert all(row["active_target_tier"] == "rollover_target_box" for row in scan["coins"])


def test_stage_two_when_majors_lead_and_the_alt_index_lags(shapes):
    regime, scan = _regime(
        {"BTC-USD": shapes["up"], "ETH-USD": shapes["up"],
         "A-USD": shapes["render"], "B-USD": shapes["fet"], "C-USD": shapes["theta"]}
    )
    assert regime["liquidity_rotation_stage"] == "stage_2_btc_majors_lead"
    assert regime["macro_regime_gate"] == "neutral_chop"
    assert regime["active_target_tier"] == "rollover_target_box"
    assert regime["components"]["BTC-USD"]["expanding"] is True
    assert regime["components"]["ALT_INDEX_3Y"]["breaking_out"] is False
    # THETA has extension targets, but stage 2 keeps the conservative box.
    theta = next(row for row in scan["coins"] if row["symbol"] == "C")
    assert theta["active_target_tier"] == "rollover_target_box"
    assert theta["macro_regime_gate"] == "neutral_chop"


def test_stage_three_when_the_alt_index_breaks_out_below_its_100_week_average(shapes):
    regime, scan = _regime(
        {"BTC-USD": shapes["up"], "ETH-USD": shapes["up"], "A-USD": shapes["breakout"](1),
         "B-USD": shapes["breakout"](2), "C-USD": shapes["breakout"](0.5)}
    )
    alt = regime["components"]["ALT_INDEX_3Y"]
    assert alt["breaking_out"] is True and alt["above_100w_sma"] is False
    assert alt["strong_expansion"] is False
    assert regime["liquidity_rotation_stage"] == "stage_3_alt_index_breakout"
    assert regime["macro_regime_gate"] == "risk_on_aligned"
    assert regime["active_target_tier"] == "full_extension_targets"
    assert [row["symbol"] for row in scan["buckets"]["low_confirmation_breakout"]] == ["A", "B", "C"]
    assert scan["breadth"]["pct_breaking_confirmation_pivot"] == {"pct": 100.0, "count": 3, "of": 3}


def test_stage_four_when_the_alt_index_is_in_full_expansion(shapes):
    regime, scan = _regime(
        {"BTC-USD": shapes["up"], "ETH-USD": shapes["up"], "A-USD": shapes["up"],
         "B-USD": shapes["up"], "C-USD": shapes["rollover"], "D-USD": shapes["theta"]}
    )
    assert regime["liquidity_rotation_stage"] == "stage_4_alt_season_expansion"
    assert regime["components"]["ALT_INDEX_3Y"]["strong_expansion"] is True
    assert regime["macro_regime_gate"] == "risk_on_aligned"
    rows = {row["symbol"]: row for row in scan["coins"]}
    # Stages 3-4 switch a coin to its extension targets when it has them.
    assert rows["D"]["active_target_tier"] == "full_extension_targets"
    assert rows["C"]["active_target_tier"] == "rollover_target_box"  # no Wave X range
    assert rows["D"]["macro_regime_gate"] == "risk_on_aligned"


def test_gate_downgrades_a_breakout_that_breadth_does_not_confirm():
    btc = {"compressed": False, "above_50w_sma": True, "weekly_macd_above_signal": True}
    narrow = {"pct_above_50w_sma": {"pct": 20.0, "count": 2, "of": 10}}
    broad = {"pct_above_50w_sma": {"pct": 60.0, "count": 6, "of": 10}}
    assert mis._gate("stage_3_alt_index_breakout", btc, narrow)[0] == "neutral_chop"
    assert mis._gate("stage_3_alt_index_breakout", btc, broad)[0] == "risk_on_aligned"
    assert mis._gate("stage_4_alt_season_expansion", btc, None)[0] == "neutral_chop"
    assert mis._gate("stage_2_btc_majors_lead", btc, broad)[0] == "neutral_chop"
    assert mis._gate("stage_1_macro_compression", btc, broad)[0] == "neutral_chop"
    weak = {"compressed": False, "above_50w_sma": False, "weekly_macd_above_signal": False}
    assert mis._gate("stage_1_macro_compression", weak, broad)[0] == "risk_off_headwind"


def test_regime_is_unavailable_without_btc_or_enough_altcoins(shapes):
    no_btc = mis.macro_industry_regime({"A-USD": shapes["up"], "B-USD": shapes["up"], "C-USD": shapes["up"]})
    assert no_btc["available"] is False and no_btc["reason"] == "btc_history_unavailable"
    thin = mis.macro_industry_regime({"BTC-USD": shapes["up"], "A-USD": shapes["up"]})
    assert thin["available"] is False and thin["reason"] == "alt_index_unavailable"
    scan = mis.scan_universe_cycles({"BTC-USD": shapes["up"], "A-USD": shapes["up"]})
    assert scan["industry"]["available"] is False
    assert all(row.get("macro_regime_gate") is None for row in scan["coins"])


# ─── rows, breadth and buckets ────────────────────────────────────────────────


def test_each_fixture_lands_in_deep_accumulation_with_its_own_signals(shapes):
    render = mis.cycle_row("RENDER-USD", shapes["render"])
    assert render["symbol"] == "RENDER" and render["available"] is True
    assert render["bucket"] == "deep_accumulation_exhaustion"
    assert render["bucket_label"] == "Deep accumulation · exhaustion"
    assert render["multi_year_oversold_exhaustion"] is True and render["daily_macd_kiss"] is True
    assert render["cycle_pattern"] == "wxy_terminal_sweep"
    assert render["low_confirmation_pivot"]["at_support"] is True
    assert render["low_confirmation_pivot"]["price"] > render["price"]

    fet = mis.cycle_row("FET-USD", shapes["fet"])
    assert fet["bucket"] == "deep_accumulation_exhaustion"
    assert fet["weekly_stoch_direction"] == "oversold_turn_up"
    assert fet["cycle_pattern"] == "abcde_channel_test"
    assert fet["accumulation_invalidation_stop"]["stop_distance_pct"] < 10
    assert fet["above_50w_sma"] is False

    theta = mis.cycle_row("THETA-USD", shapes["theta"])
    assert theta["bucket"] == "deep_accumulation_exhaustion"
    assert theta["fib_confluence_clusters"] == 2
    assert theta["rollover_target_box"]["low"] < theta["rollover_target_box"]["high"]
    # The streak, the exhaustion flag and the MACD kiss rank RENDER first.
    assert render["score"] > fet["score"] and render["score"] > theta["score"]
    assert "_tiers" in render  # internal until the scan applies the stage


def test_the_other_three_buckets(shapes):
    growth = mis.cycle_row("UP-USD", shapes["up"])
    assert growth["bucket"] == "growth_expansion_ride"
    assert growth["weekly_rsi_regime"] == "growth_expansion" and growth["above_50w_sma"] is True
    assert growth["at_multi_year_support"] is False and growth["rollover_target_box"] is None

    rollover = mis.cycle_row("ROLL-USD", shapes["rollover"])
    assert rollover["bucket"] == "rollover_profit_zone"
    assert rollover["price"] > rollover["rollover_target_box"]["low"]

    breakout = mis.cycle_row("BRK-USD", shapes["breakout"](1))
    assert breakout["bucket"] == "low_confirmation_breakout"
    assert breakout["breaking_confirmation_pivot"] is True
    assert breakout["low_confirmation_pivot"] is None  # no swing high left above price


def test_a_coin_without_a_year_of_history_is_skipped(daily_series):
    row = mis.cycle_row("NEW-USD", daily_series(1.0, [(200, 2.0)]))
    assert row == {
        "symbol": "NEW",
        "product_id": "NEW-USD",
        "available": False,
        "reason": "not_enough_daily_history",
        "candle_count": 200,
    }
    assert mis.cycle_row("NONE-USD", [])["available"] is False


def test_breadth_counts_only_the_coins_each_measure_could_read():
    rows = [
        {"available": True, "monthly_bearish_streak": 20, "multi_year_oversold_exhaustion": True,
         "weekly_rsi": 30.0, "above_50w_sma": False, "breaking_confirmation_pivot": False},
        {"available": True, "monthly_bearish_streak": 0, "multi_year_oversold_exhaustion": False,
         "weekly_rsi": 65.0, "above_50w_sma": True, "breaking_confirmation_pivot": True},
        {"available": True, "monthly_bearish_streak": 3, "multi_year_oversold_exhaustion": False,
         "weekly_rsi": 61.0, "above_50w_sma": None, "breaking_confirmation_pivot": False},
        {"available": True, "monthly_bearish_streak": None, "multi_year_oversold_exhaustion": None,
         "weekly_rsi": None, "above_50w_sma": None, "breaking_confirmation_pivot": None},
        {"available": False},
    ]
    breadth = mis.universe_breadth(rows)
    assert breadth["coins"] == 4
    assert breadth["pct_monthly_exhausted"] == {"pct": 33.3, "count": 1, "of": 3}
    assert breadth["pct_weekly_rsi_above_60"] == {"pct": 66.7, "count": 2, "of": 3}
    assert breadth["pct_above_50w_sma"] == {"pct": 50.0, "count": 1, "of": 2}
    assert breadth["pct_breaking_confirmation_pivot"] == {"pct": 33.3, "count": 1, "of": 3}
    assert mis.universe_breadth([])["pct_above_50w_sma"] == {"pct": None, "count": 0, "of": 0}


def test_scan_ranks_buckets_and_reports_skips(shapes, daily_series):
    histories = {
        "BTC-USD": shapes["up"], "ETH-USD": shapes["up"],
        "RENDER-USD": shapes["render"], "FET-USD": shapes["fet"], "THETA-USD": shapes["theta"],
        "ROLL-USD": shapes["rollover"], "NEW-USD": daily_series(1.0, [(200, 2.0)]),
    }
    scan = mis.scan_universe_cycles(histories)
    assert list(scan["buckets"]) == list(mis.BUCKETS)
    assert scan["bucket_labels"] == mis.BUCKETS
    deep = scan["buckets"]["deep_accumulation_exhaustion"]
    assert [row["symbol"] for row in deep][0] == "RENDER"
    assert sorted(row["symbol"] for row in deep) == ["FET", "RENDER", "THETA"]
    assert [row["score"] for row in deep] == sorted((row["score"] for row in deep), reverse=True)
    assert [row["symbol"] for row in scan["buckets"]["growth_expansion_ride"]] == ["BTC", "ETH"]
    assert [row["symbol"] for row in scan["buckets"]["rollover_profit_zone"]] == ["ROLL"]
    assert scan["scanned"] == 6 and scan["skipped"] == ["NEW"]
    assert scan["breadth"]["pct_monthly_exhausted"]["count"] == 1
    assert scan["breadth"]["pct_weekly_rsi_above_60"]["of"] == 6
    assert scan["blocks_alerts"] is False and scan["outcome_validated"] is False
    assert all("_tiers" not in row for row in scan["coins"])
    assert scan["industry"]["breadth"] == scan["breadth"]


def test_scan_survives_one_unreadable_series(shapes, monkeypatch):
    real = mis.cycle_row

    def flaky(product_id, candles):
        if product_id == "BAD-USD":
            raise RuntimeError("bad series")
        return real(product_id, candles)

    monkeypatch.setattr(mis, "cycle_row", flaky)
    scan = mis.scan_universe_cycles({"BAD-USD": shapes["up"], "UP-USD": shapes["up"]})
    assert scan["skipped"] == ["BAD"] and scan["scanned"] == 1
    assert scan["coins"][0]["reason"] == "read_failed"


def test_public_symbols_do_not_change_fixed_industry_breadth(shapes):
    histories = {
        "BTC-USD": shapes["up"],
        "ETH-USD": shapes["up"],
        "AAA-USD": shapes["up"],
        "BBB-USD": shapes["up"],
        "CCC-USD": shapes["up"],
    }
    members = ("AAA-USD", "BBB-USD", "CCC-USD")
    base = mis.scan_universe_cycles(histories, members=members, breadth_products=set(histories))
    more = mis.scan_universe_cycles(
        {**histories, "OTHER-USD": shapes["down"]},
        members=members,
        breadth_products=set(histories),
    )
    assert more["industry"] == base["industry"]
    assert more["breadth"]["pct_above_50w_sma"] == {"pct": 83.3, "count": 5, "of": 6}


def test_short_macro_history_cannot_claim_stage_four(daily_series):
    up = daily_series(10, [(450, 60)])
    histories = {f"{s}-USD": up for s in ("BTC", "AAA", "BBB", "CCC")}
    result = mis.scan_universe_cycles(histories)["industry"]
    assert result["stage_number"] == 3
    assert result["components"]["ALT_INDEX_3Y"]["above_100w_sma"] is None


# ─── rolling universe cycle atlas ─────────────────────────────────────────────

NOON = 20000 * DAY + 12 * 3600


class RateLimited(Exception):
    status_code = 429


class Clock:
    """Each fetch appears to take half of ``step`` seconds."""

    def __init__(self, step=1.0):
        self.now, self.step = 0.0, step

    def __call__(self):
        self.now += self.step / 2
        return self.now


def atlas_universe(count):
    return [f"C{i:03d}-USD" for i in range(count)]


def two_bars(_product=None):
    return bars([1.0, 2.0])


def test_atlas_universe_orders_owner_symbols_before_liquidity_and_drops_stables():
    volumes = {
        "AAA-USD": {"quote_volume_usd": 5.0},
        "BBB-USD": {"quote_volume_usd": 50.0},
        "USDT-USD": {"quote_volume_usd": 9e9},
        "WBTC-USD": 8e9,
        "CBETH-USD": 7e9,
        "CCC-USDC": {"quote_volume_usd": 6e9},
        "bad!-USD": 1.0,
        "ZZZ-USD": {"quote_volume_usd": "nan"},
    }
    universe = mis.select_atlas_universe(
        core=("BTC-USD", "ETH-USD"),
        held=["render", "USDC", "BTC"],
        watchlist=["FET-USD", "RENDER"],
        reload=["SOL"],
        volumes=volumes,
        movers=["PEPE", "AAA-USD", "DAI"],
    )
    assert universe == [
        "BTC-USD", "ETH-USD", "RENDER-USD", "FET-USD", "SOL-USD",
        "BBB-USD", "AAA-USD", "ZZZ-USD", "PEPE-USD",
    ]
    assert not mis.is_atlas_eligible("USDC-USD") and not mis.is_atlas_eligible("cbBTC")
    assert mis.is_atlas_eligible("SOL") and not mis.is_atlas_eligible("SOL-USDC")


def test_atlas_universe_is_capped_at_120_liquid_pairs():
    volumes = {f"C{i:03d}-USD": float(1000 - i) for i in range(300)}
    universe = mis.select_atlas_universe(core=mis.MAJORS, held=["C250"], volumes=volumes)
    assert len(universe) == mis.ATLAS_TARGET_SIZE == 120
    assert universe[:4] == ["BTC-USD", "ETH-USD", "C250-USD", "C000-USD"]
    assert len(set(universe)) == 120
    assert mis.select_atlas_universe(volumes=volumes, limit=5) == atlas_universe(5)


def test_atlas_slice_reads_required_first_then_a_bounded_number_of_cold_products():
    universe = atlas_universe(30)
    calls = []

    def fetch(product):
        calls.append(product)
        return two_bars()

    atlas = mis.CycleAtlas()
    first = mis.refresh_cycle_atlas_slice(
        atlas, universe, fetch, now=NOON, slice_size=8, required=universe[20:22], clock=Clock()
    )
    # Required products are read whatever the budget, then eight more in order.
    assert calls == universe[20:22] + universe[:8]
    assert first["network_reads"] == 8 and first["refreshed"] == calls
    cover = mis.atlas_coverage(atlas, universe, NOON)
    assert cover["target_universe_size"] == 30 and cover["ready_count"] == 10
    assert cover["coverage_pct"] == 33.3 and cover["atlas_pending_count"] == 20

    # Later slices pick up where the last one stopped and never re-read fresh data.
    for _ in range(3):
        mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 60, slice_size=8, clock=Clock())
    assert sorted(calls) == universe and len(calls) == 30
    cover = mis.atlas_coverage(atlas, universe, NOON + 60)
    assert cover["ready_count"] == 30 and cover["coverage_pct"] == 100.0
    assert cover["atlas_pending_count"] == 0 and cover["fresh_count"] == 30
    idle = mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 120, slice_size=8, clock=Clock())
    assert idle["attempted"] == [] and len(calls) == 30
    assert set(atlas.histories(universe)) == set(universe)


def test_atlas_slice_does_not_charge_the_budget_for_locally_cached_reads():
    universe = atlas_universe(30)
    atlas = mis.CycleAtlas()
    done = mis.refresh_cycle_atlas_slice(
        atlas, universe, two_bars, now=NOON, slice_size=2, clock=Clock(step=0.0)
    )
    assert len(done["refreshed"]) == 30 and done["network_reads"] == 0


def test_atlas_reads_expire_by_ttl_and_at_the_utc_day_boundary_but_stay_served():
    universe = atlas_universe(3)
    atlas = mis.CycleAtlas()
    mis.refresh_cycle_atlas_slice(atlas, universe, two_bars, now=NOON, clock=Clock())
    assert atlas.state(universe[0], NOON + 6 * 3600 - 1) == "fresh"
    assert atlas.state(universe[0], NOON + 6 * 3600) == "expired"
    late = 20000 * DAY + 23 * 3600
    mis.refresh_cycle_atlas_slice(atlas, universe, two_bars, now=late, clock=Clock())
    assert atlas.state(universe[0], late + 3599) == "fresh"
    assert atlas.state(universe[0], late + 3600) == "expired"  # a new daily bar has closed
    cover = mis.atlas_coverage(atlas, universe, late + 3600)
    assert cover["ready_count"] == 3 and cover["fresh_count"] == 0 and cover["atlas_pending_count"] == 3
    assert set(atlas.histories(universe)) == set(universe)

    # Cold products are read first, then expired ones, oldest first.
    atlas.entries[universe[1]]["fetched_at"] -= 100
    order = []
    mis.refresh_cycle_atlas_slice(
        atlas, universe + ["NEW-USD"], lambda p: order.append(p) or two_bars(),
        now=late + 3600, slice_size=2, clock=Clock(),
    )
    assert order == ["NEW-USD", universe[1]]


def test_atlas_stops_on_http_429_and_backs_off_with_doubling():
    universe = atlas_universe(10)
    calls = []

    def fetch(product):
        calls.append(product)
        if len(calls) >= 3:
            raise RateLimited()
        return two_bars()

    atlas = mis.CycleAtlas()
    hit = mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON, clock=Clock())
    assert hit["rate_limited"] is True and hit["refreshed"] == universe[:2] and len(calls) == 3
    assert atlas.backoff_until == NOON + 60
    assert mis.atlas_coverage(atlas, universe, NOON)["atlas_retry_at"] == NOON + 60

    # No request at all is made while backing off.
    waiting = mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 59, clock=Clock())
    assert waiting["backing_off"] is True and waiting["attempted"] == [] and len(calls) == 3
    again = mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 60, clock=Clock())
    assert again["rate_limited"] is True and len(calls) == 4
    assert atlas.backoff_until == NOON + 60 + 120
    # The rate-limited product stays cold, so it is retried rather than marked failed.
    assert atlas.state(universe[2], NOON + 60) == "cold"

    ok = mis.refresh_cycle_atlas_slice(atlas, universe, two_bars, now=NOON + 200, slice_size=3, clock=Clock())
    assert ok["refreshed"] == universe[2:5] and atlas.backoff_seconds == 0.0
    assert mis.atlas_coverage(atlas, universe, NOON + 200)["atlas_retry_at"] is None


def test_atlas_failed_reads_wait_an_hour_and_keep_the_last_good_candles():
    universe = ["GOOD-USD", "EMPTY-USD", "BOOM-USD"]
    good = two_bars()
    attempts = []

    def fetch(product):
        attempts.append(product)
        if product == "BOOM-USD":
            raise ValueError("bad page")
        return good if product == "GOOD-USD" else []

    atlas = mis.CycleAtlas()
    first = mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON, clock=Clock())
    assert first["failed"] == ["EMPTY-USD", "BOOM-USD"] and first["rate_limited"] is False
    cover = mis.atlas_coverage(atlas, universe, NOON + 10)
    assert cover["atlas_unavailable"] == ["EMPTY-USD", "BOOM-USD"]
    assert cover["ready_count"] == 1 and cover["atlas_pending_count"] == 0
    mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 3599, clock=Clock())
    assert len(attempts) == 3
    mis.refresh_cycle_atlas_slice(atlas, universe, fetch, now=NOON + 3600, clock=Clock())
    assert attempts[3:] == ["EMPTY-USD", "BOOM-USD"]

    # An expired product whose refresh fails keeps serving its last good read.
    tomorrow = NOON + DAY
    mis.refresh_cycle_atlas_slice(atlas, universe, lambda p: [], now=tomorrow, clock=Clock())
    assert atlas.histories(universe) == {"GOOD-USD": good}
    assert atlas.state("GOOD-USD", tomorrow + 1) == "failed"
    assert atlas.state("GOOD-USD", tomorrow + 3600) == "expired"

    # Products that leave the universe are dropped from the cache.
    mis.refresh_cycle_atlas_slice(atlas, ["EMPTY-USD"], lambda p: [], now=tomorrow, clock=Clock())
    assert set(atlas.entries) == {"EMPTY-USD"}
    assert mis.atlas_coverage(mis.CycleAtlas(), [], NOON)["coverage_pct"] == 0.0
