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
