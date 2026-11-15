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
