import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from position_intel import enrich_portfolio, _assess_order, _assess_holding


def _signal(symbol, state, direction, confidence, label=None):
    read = {"label": label} if label else {}
    return {
        "symbol": f"{symbol}-USD",
        "primary_state": state,
        "direction": direction,
        "confidence": confidence,
        "severity": "moderate",
        "the_read": read,
    }


def _holding(symbol, price, value, alloc):
    return {
        "symbol": symbol,
        "price_usd": price,
        "market_value_usd": value,
        "allocation_pct": alloc,
        "is_cash": False,
        "cost_basis": {"status": "partial"},
    }


def _order(symbol, side, limit_price):
    return {
        "symbol": symbol,
        "product_id": f"{symbol}-USD",
        "side": side,
        "limit_price": limit_price,
    }


def test_holding_gets_signal_context():
    signal = _signal("SOL", "Confirmed", "up", 85, "BUY WATCH")
    intel = _assess_holding(_holding("SOL", 150.0, 300.0, 15.0), signal, None, None)
    assert intel["posture"] == "momentum_favorable"
    assert intel["signal"]["state"] == "Confirmed"
    assert intel["signal"]["label"] == "BUY WATCH"


def test_holding_no_signal():
    intel = _assess_holding(_holding("COTI", 0.01, 10.0, 0.5), None, None, None)
    assert intel["posture"] == "no_signal"


def test_holding_adverse_pressure():
    signal = _signal("BILL", "Building", "down", 72)
    intel = _assess_holding(_holding("BILL", 0.02, 20.0, 1.0), signal, None, None)
    assert intel["posture"] == "pressure_adverse"


def test_holding_with_outcome_history():
    signal = _signal("SOL", "Confirmed", "up", 85)
    stats = {
        "sample_size": 50,
        "follow_through_rate": 0.62,
        "median_favorable_pct": 2.1,
        "median_adverse_pct": -0.8,
        "horizon_minutes": 60,
    }
    intel = _assess_holding(_holding("SOL", 150.0, 300.0, 15.0), signal, stats, None)
    assert intel["history"]["follow_through_pct"] == 62.0
    assert intel["history"]["sample_size"] == 50


def test_stop_loss_order_assessment():
    signal = _signal("COTI", "Weakening", "up", 45)
    assessment = _assess_order(_order("COTI", "SELL", 0.008), 0.01, signal, None)
    assert assessment["order_type_hint"] == "stop_loss"
    assert assessment["buffer_pct"] > 0
    assert "tightening" in assessment.get("context", "").lower()


def test_take_profit_order_with_confirmed_upside():
    signal = _signal("SOL", "Confirmed", "up", 88)
    assessment = _assess_order(_order("SOL", "SELL", 180.0), 150.0, signal, None)
    assert assessment["order_type_hint"] == "take_profit"
    assert "reachable" in assessment.get("context", "").lower()


def test_limit_buy_order():
    assessment = _assess_order(_order("BTC", "BUY", 58000.0), 62000.0, None, None)
    assert assessment["order_type_hint"] == "limit_buy"
    assert assessment["discount_pct"] > 0


def test_enrich_portfolio_adds_intel():
    snapshot = {
        "holdings": [
            _holding("SOL", 150.0, 300.0, 50.0),
            _holding("COTI", 0.01, 10.0, 2.0),
            {"symbol": "USD", "is_cash": True, "market_value_usd": 500.0},
        ],
        "open_orders": [
            _order("SOL", "SELL", 180.0),
        ],
        "summary": {"holding_count": 2},
    }
    signals = [_signal("SOL", "Confirmed", "up", 85)]

    enriched = enrich_portfolio(snapshot, signals=signals)

    assert enriched["holdings"][0].get("intel") is not None
    assert enriched["holdings"][0]["intel"]["posture"] == "momentum_favorable"
    assert enriched["holdings"][1].get("intel") is not None
    assert enriched["holdings"][1]["intel"]["posture"] == "no_signal"
    assert "intel" not in enriched["holdings"][2]  # cash skipped
    assert enriched["open_orders"][0].get("intel") is not None
    assert enriched.get("intel_summary") is not None
    assert enriched["intel_summary"]["holdings_with_signals"] == 1
