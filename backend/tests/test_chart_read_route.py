from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chart_reader
import app as backend_app
import catalyst_sentiment
import pytest


@pytest.fixture(autouse=True)
def offline_catalyst(monkeypatch):
    class Unavailable:
        def symbol(self, symbol):
            return {}

        def source_health(self):
            return {"trending": {"status": "unavailable"}}

    monkeypatch.setattr(catalyst_sentiment, "get_service", lambda: Unavailable())
    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", lambda product, years=3: [])


def test_chart_read_route_forwards_event_context(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        backend_app,
        "_fetch_coinbase_candles",
        lambda *args, **kwargs: [
            [10, 150, 155, 151, 153, 1000],
            [20, 151, 156, 153, 155, 900],
            [30, 152, 157, 155, 156, 1100],
            [40, 153, 159, 156, 158, 950],
            [50, 155, 161, 158, 160, 800],
        ],
    )

    def fake_analyze_candles(candles, symbol, timeframe="1h", event_context=None):
        captured["candles"] = candles
        captured["symbol"] = symbol
        captured["timeframe"] = timeframe
        captured["event_context"] = event_context
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "summary": "ok",
            "direction": {"label": "up", "basic_text": "up"},
            "lower_area": {
                "zone": [1, 2],
                "basic_text": "support",
                "technical_label": "support",
            },
            "upper_area": {
                "zone": [3, 4],
                "basic_text": "resistance",
                "technical_label": "resistance",
            },
            "trading_activity": {"label": "normal", "basic_text": "normal"},
            "confidence": "medium",
            "watch_next": [],
            "not_financial_advice": True,
            "candle_count": 5,
            "window_hours": 5.0,
        }

    monkeypatch.setattr(chart_reader, "analyze_candles", fake_analyze_candles)

    with backend_app.app.test_request_context(
        "/api/chart-read/SOL?event_type=BREAKOUT&event_window=3m&event_price=148.2&event_pct=5.8"
    ):
        response = backend_app.get_chart_read("SOL")

    assert response.status_code == 200
    assert captured["symbol"] == "SOL"
    assert captured["timeframe"] == "1h"
    assert captured["event_context"] == {
        "type_key": "BREAKOUT",
        "evidence": {
            "window": "3m",
            "price": 148.2,
            "pct": 5.8,
        },
    }


def test_chart_read_route_keeps_no_context_behavior(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_fetch_coinbase_candles",
        lambda *args, **kwargs: [
            [10, 150, 155, 151, 153, 1000],
            [20, 151, 156, 153, 155, 900],
            [30, 152, 157, 155, 156, 1100],
            [40, 153, 159, 156, 158, 950],
            [50, 155, 161, 158, 160, 800],
        ],
    )

    calls = []

    def fake_analyze_candles(candles, symbol, timeframe="1h", event_context=None):
        calls.append(event_context)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "summary": "ok",
            "direction": {"label": "up", "basic_text": "up"},
            "lower_area": {
                "zone": [1, 2],
                "basic_text": "support",
                "technical_label": "support",
            },
            "upper_area": {
                "zone": [3, 4],
                "basic_text": "resistance",
                "technical_label": "resistance",
            },
            "trading_activity": {"label": "normal", "basic_text": "normal"},
            "confidence": "medium",
            "watch_next": [],
            "not_financial_advice": True,
            "candle_count": 5,
            "window_hours": 5.0,
        }

    monkeypatch.setattr(chart_reader, "analyze_candles", fake_analyze_candles)

    with backend_app.app.test_request_context("/api/chart-read/SOL"):
        response = backend_app.get_chart_read("SOL")

    assert response.status_code == 200
    assert calls == [None]


def _history(count=120, step=3600, t0=1_699_992_000):
    """Completed 1h candles, newest first like the Coinbase API."""
    legs = [(40, 90.0), (20, 110.0), (8, 102.0), (6, 106.0), (9, 97.0), (5, 102.0)]
    legs.append((count - 88, 104.0))
    out, price, ts = [], 100.0, t0
    for bars, end in legs:
        delta = (end - price) / bars
        for _ in range(bars):
            o, c = price, price + delta
            out.append([ts, min(o, c) - 0.1, max(o, c) + 0.1, o, c, 1000])
            price, ts = c, ts + step
    return out[::-1]


def test_chart_read_route_adds_wave_analysis_from_the_long_history(monkeypatch):
    history, asked = _history(), {}

    def fake_fetch(product_id, granularity=60, count=70):
        asked.update(product_id=product_id, granularity=granularity, count=count)
        return history[:count]

    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", fake_fetch)

    with backend_app.app.test_request_context("/api/chart-read/sol"):
        response = backend_app.get_chart_read("sol")

    assert response.status_code == 200
    assert asked == {"product_id": "SOL-USD", "granularity": 3600, "count": 300}
    body = response.get_json()
    # The basic read still covers the newest 50 candles only.
    assert body["candle_count"] == 50 and body["window_hours"] == 50.0
    for key in ("summary", "direction", "lower_area", "upper_area", "watch_next"):
        assert key in body
    wave = body["wave_analysis"]
    assert wave["available"] is True
    assert wave["candle_count"] == len(history)
    assert wave["timeframe"] == "1h"
    assert len(wave["pivots"]) >= 5
    assert wave["chart"]["candles"][-1][0] == history[0][0]


def test_chart_read_route_survives_a_wave_failure(monkeypatch):
    monkeypatch.setattr(
        backend_app, "_fetch_coinbase_candles", lambda *a, **k: _history()
    )

    def boom(*args, **kwargs):
        raise RuntimeError("engine down")

    import elliott_wave_engine

    monkeypatch.setattr(elliott_wave_engine, "analyze_wave_structure", boom)

    with backend_app.app.test_request_context("/api/chart-read/SOL"):
        response = backend_app.get_chart_read("SOL")

    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "SOL" and body["candle_count"] == 50
    assert body["wave_analysis"]["available"] is False
    assert body["wave_analysis"]["reason"] == "engine_error"


# ─── horizons ─────────────────────────────────────────────────────────────────


def test_chart_read_route_defaults_to_the_swing_horizon(monkeypatch):
    monkeypatch.setattr(
        backend_app, "_fetch_coinbase_candles", lambda *a, **k: _history()
    )
    for url in ("/api/chart-read/SOL", "/api/chart-read/SOL?horizon=bogus"):
        with backend_app.app.test_request_context(url):
            body = backend_app.get_chart_read("SOL").get_json()
        assert body["horizon"] == "swing" and body["timeframe"] == "1h"
        assert [h["key"] for h in body["horizons"]] == ["short", "swing", "macro", "cycle"]
        wave = body["wave_analysis"]
        assert wave["story"]["steps"] and "swings" in wave["swing_history"]
        assert len(wave["swing_history"]["swings"]) == len(wave["pivots"])


def test_cycle_route_uses_daily_and_weekly_history(monkeypatch):
    history = _history(count=120, step=86400, t0=1_699_920_000)
    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", lambda product, years=3: history)
    with backend_app.app.test_request_context("/api/chart-read/SOL?horizon=cycle"):
        response = backend_app.get_chart_read("SOL")
    assert response.status_code == 200
    body = response.get_json()
    assert body["horizon"] == "cycle"
    assert body["wave_analysis"]["timeframe"] == "1d"
    assert body["multi_year_context"]["candle_count"] == 120
    assert body["multi_year_context"]["weekly_wave_analysis"]["timeframe"] == "1w"
    assert body["catalyst_sentiment"]["status"] == "unavailable"
    assert body["catalyst_sentiment"]["posture"] is None
    assert "paper_order_ticket" not in body


@pytest.mark.parametrize("horizon", ["swing", "cycle"])
def test_swing_and_cycle_expose_top_down_context(monkeypatch, horizon):
    hourly = _history()
    daily = [[1_600_041_600 + i * 86400, 50, 200, 100, 100, 10] for i in range(400)][::-1]
    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", lambda *a, **k: hourly)
    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", lambda product, years=3: daily)
    with backend_app.app.test_request_context(f"/api/chart-read/SOL?horizon={horizon}"):
        body = backend_app.get_chart_read("SOL").get_json()
    assert body["top_down_confluence"]["available"] is True
    assert body["multi_year_context"]["log_fib_retracements"]["0.5"] == pytest.approx(100)


def test_short_horizon_reads_15m_candles_with_a_4h_trend_check(monkeypatch):
    asked = []

    def fake_fetch(product_id, granularity=60, count=70):
        asked.append(granularity)
        return _history(count=300, step=granularity)[:count]

    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", fake_fetch)
    with backend_app.app.test_request_context("/api/chart-read/SOL?horizon=short"):
        response = backend_app.get_chart_read("SOL")

    assert response.status_code == 200
    assert sorted(asked) == [900, 3600]
    body = response.get_json()
    assert body["horizon"] == "short" and body["timeframe"] == "15m"
    assert body["window_hours"] == 12.5  # 50 fifteen-minute candles
    wave = body["wave_analysis"]
    assert wave["timeframe"] == "15m" and wave["bar_seconds"] == 900
    assert wave["higher_timeframe"] == "4h"
    assert wave["chart"]["granularity_seconds"] == 900


def test_macro_horizon_pages_back_and_reads_4h_candles(monkeypatch):
    hourly = _history(count=720)  # newest first, 30 days of 1h candles
    pages = []

    def fake_fetch(product_id, granularity=60, count=70):
        if granularity == 86400:
            return []
        assert granularity == 3600
        return hourly[:count]

    def fake_before(product_id, granularity, end_ts, count=300):
        pages.append(end_ts)
        older = [c for c in hourly if c[0] <= end_ts]
        return older[:count]

    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", fake_fetch)
    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles_before", fake_before)
    with backend_app.app.test_request_context("/api/chart-read/SOL?horizon=macro"):
        response = backend_app.get_chart_read("SOL")

    assert response.status_code == 200
    # Two more pages, each ending one bar before the oldest candle already held.
    assert pages == [hourly[299][0] - 3600, hourly[599][0] - 3600]
    body = response.get_json()
    assert body["horizon"] == "macro" and body["timeframe"] == "4h"
    assert body["window_hours"] == 200.0  # 50 four-hour candles
    wave = body["wave_analysis"]
    assert wave["timeframe"] == "4h" and wave["bar_seconds"] == 14400
    assert wave["candle_count"] == 180  # 720 hourly candles in closed 4h buckets
    assert wave["chart"]["candles"][-1][0] == hourly[0][0] - 3 * 3600


def test_macro_horizon_still_reads_when_paging_fails(monkeypatch):
    hourly = _history(count=300)
    monkeypatch.setattr(
        backend_app,
        "_fetch_coinbase_candles",
        lambda product_id, granularity=60, count=70: (
            [] if granularity == 86400 else hourly[:count]
        ),
    )
    monkeypatch.setattr(
        backend_app, "_fetch_coinbase_candles_before", lambda *a, **k: None
    )
    with backend_app.app.test_request_context("/api/chart-read/SOL?horizon=macro"):
        body = backend_app.get_chart_read("SOL").get_json()
    assert body["wave_analysis"]["candle_count"] == 75
    assert body["wave_analysis"]["available"] is True


# ─── structure posture for board rows ─────────────────────────────────────────


def _posture(monkeypatch, url, fetch):
    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", fetch)
    with backend_app.app.test_request_context(url):
        return backend_app.get_structure_posture().get_json()


def test_structure_posture_reads_each_symbol_once_and_caches_it(monkeypatch):
    backend_app._STRUCTURE_POSTURE_CACHE.clear()
    calls = []

    def fetch(product_id, granularity=60, count=70):
        calls.append((product_id, granularity))
        if product_id.startswith("GONE"):
            return None
        return _history()[:count] if granularity == 3600 else []

    url = "/api/structure-posture?symbols=sol,BTC,sol,bad!sym,GONE"
    body = _posture(monkeypatch, url, fetch)

    assert sorted(body["postures"]) == ["BTC", "SOL"]  # GONE has no candles
    assert body["pending"] == []
    assert body["blocks_alerts"] is False and body["outcome_validated"] is False
    sol = body["postures"]["SOL"]
    assert sol["reads"]["1h"]["active_pattern"] == "abc_complete"
    assert set(sol["posture"]) >= {"key", "tone", "label", "short_label", "detail"}
    assert sorted(set(calls)) == [
        ("BTC-USD", 900),
        ("BTC-USD", 3600),
        ("GONE-USD", 3600),
        ("SOL-USD", 900),
        ("SOL-USD", 3600),
    ]

    calls.clear()
    again = _posture(monkeypatch, url, fetch)
    assert again["postures"] == body["postures"]
    assert calls == []  # every symbol, including the miss, came from the cache
    backend_app._STRUCTURE_POSTURE_CACHE.clear()


def test_structure_posture_limits_new_reads_per_call(monkeypatch):
    backend_app._STRUCTURE_POSTURE_CACHE.clear()
    monkeypatch.setattr(backend_app, "STRUCTURE_POSTURE_MAX_FRESH", 2)

    def fetch(product_id, granularity=60, count=70):
        return _history()[:count] if granularity == 3600 else []

    url = "/api/structure-posture?symbols=AAA,BBB,CCC"
    first = _posture(monkeypatch, url, fetch)
    assert sorted(first["postures"]) == ["AAA", "BBB"] and first["pending"] == ["CCC"]
    second = _posture(monkeypatch, url, fetch)
    assert sorted(second["postures"]) == ["AAA", "BBB", "CCC"]
    assert second["pending"] == []
    empty = _posture(monkeypatch, "/api/structure-posture", fetch)
    assert empty["postures"] == {} and empty["pending"] == []
    backend_app._STRUCTURE_POSTURE_CACHE.clear()


def test_structure_posture_survives_a_read_failure(monkeypatch):
    backend_app._STRUCTURE_POSTURE_CACHE.clear()

    def boom(sym):
        raise RuntimeError("reader down")

    monkeypatch.setattr(backend_app, "_structure_posture_for", boom)
    with backend_app.app.test_request_context("/api/structure-posture?symbols=SOL"):
        response = backend_app.get_structure_posture()
    assert response.status_code == 200
    assert response.get_json()["postures"] == {}
    backend_app._STRUCTURE_POSTURE_CACHE.clear()


# ─── cycle read: momentum stack, targets and the industry gate ────────────────


@pytest.fixture
def macro_scan_state():
    """An empty industry scan cache before and after the test."""

    def reset():
        backend_app._MACRO_SCAN_STATE.update(
            payload=None, computed_at=0.0, day=None, products=(), running=False,
            supplements={}, supplement_day=None, retry_after=0.0,
        )

    reset()
    yield backend_app._MACRO_SCAN_STATE
    reset()


def _hourly_near(price):
    """The 1h test history rescaled so its last close sits near ``price``."""
    scale = price / 104.0
    return [[ts, lo * scale, hi * scale, o * scale, c * scale, v] for ts, lo, hi, o, c, v in _history()]


def _cycle_read(monkeypatch, daily, horizon="cycle", asked=None):
    def fetch(product, years=3):
        if asked is not None:
            asked.append((product, years))
        return daily[::-1]  # newest first, like the loader

    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", fetch)
    monkeypatch.setattr(
        backend_app, "_fetch_coinbase_candles", lambda *a, **k: _hourly_near(daily[-1][4])
    )
    with backend_app.app.test_request_context(f"/api/chart-read/THETA?horizon={horizon}"):
        response = backend_app.get_chart_read("THETA")
    assert response.status_code == 200
    return response.get_json()


def test_cycle_route_returns_the_momentum_stack_and_both_target_tiers(
    monkeypatch, cycle_fixture, macro_scan_state
):
    asked = []
    body = _cycle_read(monkeypatch, cycle_fixture("theta_wxy_confluence_fixture"), asked=asked)
    # Four years are loaded; the range is read from the trailing three.
    assert asked == [("THETA-USD", chart_reader.CYCLE_HISTORY_YEARS)]
    assert chart_reader.CYCLE_HISTORY_YEARS == 4

    cycle = body["multi_year_context"]
    assert cycle["candle_count"] == 1096
    assert set(cycle["rsi_regimes"]) == {"1d", "1w", "1m"}
    assert cycle["rsi_regimes"]["1w"]["regime"] == "oversold_compression"
    assert {"weekly_stoch_rsi_k", "weekly_stoch_rsi_d", "direction"} <= set(cycle["weekly_stoch_rsi"])
    assert "monthly_bearish_streak" in cycle["monthly_cycle_exhaustion"]
    assert {"daily_macd_kiss", "weekly_macd_bullish_cross", "macro_bullish_divergence"} <= set(
        cycle["macd_signals"]
    )
    assert {"sma_50w", "sma_100w", "sma_200w"} <= set(cycle["weekly_sma_ladder"])
    assert cycle["flash_wick_filter"]["applied"] is True
    assert cycle["raw_cycle_low"]["price"] < cycle["cycle_low"]["price"]
    assert cycle["weekly_wave_analysis"]["timeframe"] == "1w"

    top = body["top_down_confluence"]
    assert top["at_multi_year_support"] is True
    assert top["cycle_pattern"]["kind"] == "wxy_terminal_sweep"
    assert top["low_confirmation_pivot"]["message"] == "Break above $1.07 signals cycle low is in"
    assert top["accumulation_invalidation_stop"]["stop_price"] < cycle["cycle_low"]["price"]
    assert top["accumulation_invalidation_stop"]["stop_distance_pct"] > 0
    assert len(top["fib_confluence_clusters"]) == 2
    assert top["rollover_target_box"]["available"] is True
    assert top["full_extension_targets"]["available"] is True

    # No industry scan yet: the conservative tier stays active and nothing is invented.
    assert body["macro_industry_regime"] == {"available": False, "reason": "warming"}
    assert top["active_target_tier"] == "rollover_target_box"
    assert top["macro_regime_gate"] is None
    assert macro_scan_state["running"] is False


def test_cycle_route_applies_the_cached_industry_gate(monkeypatch, cycle_fixture, macro_scan_state):
    macro_scan_state.update(
        payload={
            "industry": {
                "available": True,
                "liquidity_rotation_stage": "stage_3_alt_index_breakout",
                "stage_label": "Stage 3 · Alt index breakout",
                "macro_regime_gate": "risk_on_aligned",
                "active_target_tier": "full_extension_targets",
            },
            "computed_at": 1234.5,
        },
        computed_at=1234.5,
    )
    daily = cycle_fixture("theta_wxy_confluence_fixture")
    body = _cycle_read(monkeypatch, daily)
    assert body["macro_industry_regime"]["liquidity_rotation_stage"] == "stage_3_alt_index_breakout"
    assert body["macro_industry_regime"]["as_of"] == 1234.5
    top = body["top_down_confluence"]
    assert top["macro_regime_gate"] == "risk_on_aligned"
    assert top["liquidity_rotation_stage"] == "stage_3_alt_index_breakout"
    assert top["active_target_tier"] == "full_extension_targets"

    # The swing read carries the gate on its top-down block, not the full regime.
    swing = _cycle_read(monkeypatch, daily, horizon="swing")
    assert "macro_industry_regime" not in swing
    assert swing["top_down_confluence"]["active_target_tier"] == "full_extension_targets"


def _scan(url):
    with backend_app.app.test_request_context(url):
        response = backend_app.get_macro_cycle_scan()
    assert response.status_code == 200
    return response.get_json()


def test_macro_cycle_scan_keeps_request_supplements_out_of_other_responses(
    monkeypatch, cycle_fixture, daily_series, macro_scan_state
):
    up = daily_series(10, [(1461, 60)])
    histories = {
        "BTC-USD": up,
        "ETH-USD": up,
        "SOL-USD": cycle_fixture("render_cycle_fixture"),
        "ADA-USD": cycle_fixture("fet_channel_fixture"),
        "XRP-USD": cycle_fixture("theta_wxy_confluence_fixture"),
        "RENDER-USD": cycle_fixture("render_cycle_fixture"),
        "FET-USD": cycle_fixture("fet_channel_fixture"),
    }
    base = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "XRP-USD"]
    loads = []

    def fetch(product, years=3):
        loads.append((product, years))
        return histories.get(product, [])[::-1]

    monkeypatch.setattr(backend_app, "_macro_scan_universe", lambda: base)
    monkeypatch.setattr(backend_app, "_macro_scan_known_products", lambda: {*histories, "EMPTY-USD"})
    monkeypatch.setattr(chart_reader, "fetch_multi_year_daily_candles", fetch)

    first = _scan("/api/macro-cycle-scan?symbols=render,FET-USD,bad!sym,render")
    assert first["status"] == "ready" and first["blocks_alerts"] is False
    assert first["industry"]["liquidity_rotation_stage"] == "stage_2_btc_majors_lead"
    assert first["industry"]["macro_regime_gate"] == "neutral_chop"
    assert sorted(row["symbol"] for row in first["coins"]) == ["ADA", "BTC", "ETH", "FET", "RENDER", "SOL", "XRP"]
    assert first["breadth"]["coins"] == 7 and first["requested"] == 7 and first["unavailable"] == []
    assert {years for _product, years in loads} == {4}

    count = len(loads)
    second = _scan("/api/macro-cycle-scan?symbols=RENDER,NOPE")
    assert second["computed_at"] == first["computed_at"] and len(loads) == count
    assert second["unavailable"] == ["NOPE-USD"]
    assert "FET-USD" not in {row["product_id"] for row in second["coins"]}
    assert first["industry"] == second["industry"]

    baseline = _scan("/api/macro-cycle-scan")
    assert {row["product_id"] for row in baseline["coins"]} == set(base)
    assert len(loads) == count
    for _ in range(2):
        assert _scan("/api/macro-cycle-scan?symbols=EMPTY")["unavailable"] == ["EMPTY-USD"]
    assert loads.count(("EMPTY-USD", 4)) == 1


def test_macro_cycle_scan_route_reports_warming_while_a_worker_loads(monkeypatch, macro_scan_state):
    started = []

    class Worker:
        def __init__(self, target=None, args=(), **kwargs):
            self.target, self.args = target, args

        def start(self):
            started.append(self)

    monkeypatch.setattr(backend_app, "_macro_scan_inline", lambda: False)
    monkeypatch.setattr(backend_app, "_macro_scan_universe", lambda symbols=(): ["BTC-USD"])
    # The stub only covers the route's own worker: the scan's thread pool needs
    # the real class back before the captured target runs below.
    with monkeypatch.context() as patch:
        patch.setattr(backend_app.threading, "Thread", Worker)
        first = _scan("/api/macro-cycle-scan")
        assert first["status"] == "warming" and first["coins"] == [] and first["buckets"] == {}
        assert first["industry"] == {"available": False, "reason": "warming"}
        assert len(started) == 1 and macro_scan_state["running"] is True
        # A second request while the worker runs does not start another.
        assert _scan("/api/macro-cycle-scan")["status"] == "warming" and len(started) == 1

    # When the worker finishes, the result is served and the flag clears.
    monkeypatch.setattr(
        chart_reader, "fetch_multi_year_daily_candles", lambda product, years=3: []
    )
    started[0].target(*started[0].args)
    assert macro_scan_state["running"] is False
    done = _scan("/api/macro-cycle-scan")
    assert done["status"] == "ready" and done["unavailable"] == ["BTC-USD"]
    assert done["industry"]["available"] is False


def test_macro_scan_universe_uses_core_then_liquid(monkeypatch):
    import macro_industry_scanner

    monkeypatch.setattr(
        backend_app,
        "latest_quote_volume_by_product",
        lambda now: {
            "AAA-USD": {"quote_volume_usd": 5.0},
            "BBB-USD": {"quote_volume_usd": 50.0},
            "CCC-USDC": {"quote_volume_usd": 500.0},
            "RENDER-USD": {"quote_volume_usd": 1.0},
        },
    )
    products = backend_app._macro_scan_universe()
    core = list(macro_industry_scanner.MAJORS) + list(macro_industry_scanner.ALT_INDEX_MEMBERS)
    assert products[: len(core)] == core
    assert products[len(core):] == ["BBB-USD", "AAA-USD", "RENDER-USD"]
    assert len(products) == len(set(products)) <= backend_app.MACRO_SCAN_MAX_PRODUCTS


def test_cached_cycle_products_lists_what_the_loader_already_has(monkeypatch, tmp_path):
    import sqlite3

    path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MW_CYCLE_HISTORY_DB", str(path))
    assert chart_reader.cached_cycle_products() == []
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE cycle_history (product TEXT, years INTEGER, day_end INTEGER, "
            "candles TEXT NOT NULL, PRIMARY KEY(product, years))"
        )
        conn.executemany(
            "INSERT INTO cycle_history VALUES (?, ?, ?, '[]')",
            [("FET-USD", 4, 100), ("RENDER-USD", 4, 200), ("OLD-USD", 3, 300)],
        )
    conn.close()
    assert chart_reader.cached_cycle_products() == ["RENDER-USD", "FET-USD"]
    assert chart_reader.cached_cycle_products(years=3) == ["OLD-USD"]
