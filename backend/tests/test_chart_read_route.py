from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chart_reader
import app as backend_app


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
        assert [h["key"] for h in body["horizons"]] == ["short", "swing", "macro"]
        wave = body["wave_analysis"]
        assert wave["story"]["steps"] and "swings" in wave["swing_history"]
        assert len(wave["swing_history"]["swings"]) == len(wave["pivots"])


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
