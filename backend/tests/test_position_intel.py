import os
import sys

import pytest

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
    signal = _signal("SOL", "Moonwalking", "up", 85, "BUY WATCH")
    intel = _assess_holding(_holding("SOL", 150.0, 300.0, 15.0), signal, None, None)
    assert intel["posture"] == "momentum_favorable"
    assert intel["signal"]["state"] == "Moonwalking"
    assert intel["signal"]["label"] == "BUY WATCH"


def test_holding_no_signal():
    intel = _assess_holding(_holding("COTI", 0.01, 10.0, 0.5), None, None, None)
    assert intel["posture"] == "no_signal"


def test_holding_adverse_pressure():
    signal = _signal("BILL", "Building", "down", 72)
    intel = _assess_holding(_holding("BILL", 0.02, 20.0, 1.0), signal, None, None)
    assert intel["posture"] == "pressure_adverse"


@pytest.mark.parametrize(
    ("state", "direction", "confidence", "expected_posture"),
    [
        pytest.param("Building", "up", 48, "developing", id="building-up"),
        pytest.param("Building", "down", 48, "developing", id="building-down-low"),
        pytest.param(
            "Building", "down", 60, "pressure_adverse", id="building-down-active"
        ),
        pytest.param("Building", "neutral", 48, "developing", id="building-neutral"),
        pytest.param("Breakout", "up", 66, "momentum_favorable", id="breakout-up"),
        pytest.param("Breakout", "down", 66, "pressure_adverse", id="breakout-down"),
        pytest.param("Breakout", "neutral", 66, "neutral", id="breakout-neutral"),
        pytest.param(
            "Moonwalking", "up", 82, "momentum_favorable", id="moonwalking-up"
        ),
        pytest.param(
            "Moonwalking", "down", 82, "pressure_adverse", id="moonwalking-down"
        ),
        pytest.param("Moonwalking", "neutral", 82, "neutral", id="moonwalking-neutral"),
        pytest.param("Reversal Risk", "up", 72, "momentum_fading", id="reversal-up"),
        pytest.param(
            "Reversal Risk", "down", 72, "momentum_fading", id="reversal-down"
        ),
        pytest.param(
            "Reversal Risk", "neutral", 72, "momentum_fading", id="reversal-neutral"
        ),
    ],
)
def test_canonical_event_state_posture_table(
    state, direction, confidence, expected_posture
):
    signal = _signal("SOL", state, direction, confidence)
    intel = _assess_holding(_holding("SOL", 150.0, 300.0, 15.0), signal, None, None)
    assert intel["posture"] == expected_posture


def test_unknown_state_with_neutral_direction_remains_neutral():
    signal = _signal("SOL", "", "neutral", 0)
    intel = _assess_holding(_holding("SOL", 150.0, 300.0, 15.0), signal, None, None)
    assert intel["posture"] == "neutral"


def test_holding_with_outcome_history():
    signal = _signal("SOL", "Breakout", "up", 85)
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
    signal = _signal("COTI", "Reversal Risk", "up", 72)
    assessment = _assess_order(_order("COTI", "SELL", 0.008), 0.01, signal, None)
    assert assessment["order_type_hint"] == "stop_loss"
    assert assessment["buffer_pct"] > 0
    assert "tightening" in assessment.get("context", "").lower()


def test_take_profit_order_with_breakout_upside():
    signal = _signal("SOL", "Breakout", "up", 88)
    assessment = _assess_order(_order("SOL", "SELL", 180.0), 150.0, signal, None)
    assert assessment["order_type_hint"] == "take_profit"
    assert "reachable" in assessment.get("context", "").lower()


def test_stop_loss_order_with_breakout_downside():
    signal = _signal("SOL", "Breakout", "down", 66)
    assessment = _assess_order(_order("SOL", "SELL", 120.0), 150.0, signal, None)
    assert "downside pressure" in assessment.get("context", "").lower()


def test_stop_loss_order_with_moonwalking_upside():
    signal = _signal("SOL", "Moonwalking", "up", 82)
    assessment = _assess_order(_order("SOL", "SELL", 120.0), 150.0, signal, None)
    assert "breathing room" in assessment.get("context", "").lower()


def test_take_profit_order_with_reversal_risk_is_cautionary():
    signal = _signal("SOL", "Reversal Risk", "up", 72)
    assessment = _assess_order(_order("SOL", "SELL", 180.0), 150.0, signal, None)
    assert "may not be reached" in assessment.get("context", "").lower()


def test_limit_buy_order():
    assessment = _assess_order(_order("BTC", "BUY", 58000.0), 62000.0, None, None)
    assert assessment["order_type_hint"] == "limit_buy"
    assert assessment["discount_pct"] > 0


def test_holding_with_board_data():
    signal = _signal("SOL", "Moonwalking", "up", 85, "BUY WATCH")
    board = {
        "change_1m": 2.5,
        "change_3m": 4.1,
        "volume_1h_now": 5000000,
        "volume_1h_prev": 3000000,
        "sentiment": {"pressure": "bullish", "direction": "up", "strength": 72},
    }
    intel = _assess_holding(
        _holding("SOL", 150.0, 300.0, 15.0), signal, None, None, board_row=board
    )
    assert intel["posture"] == "momentum_favorable"
    assert "board" in intel
    assert intel["board"]["change_1m"] == 2.5
    assert intel["board"]["change_3m"] == 4.1
    assert intel["board"]["volume_1h_now"] == 5000000
    assert intel["board"]["volume_change_1h_pct"] > 0
    assert intel["board"]["sentiment"]["pressure"] == "bullish"


def test_holding_board_data_no_signal():
    board = {"change_1m": -1.2, "momentum": "moderate"}
    intel = _assess_holding(
        _holding("COTI", 0.01, 10.0, 0.5), None, None, None, board_row=board
    )
    assert intel["posture"] == "no_signal"
    assert intel["board"]["change_1m"] == -1.2


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
    signals = [_signal("SOL", "Moonwalking", "up", 85)]

    enriched = enrich_portfolio(snapshot, signals=signals)

    assert enriched["holdings"][0].get("intel") is not None
    assert enriched["holdings"][0]["intel"]["posture"] == "momentum_favorable"
    assert enriched["holdings"][1].get("intel") is not None
    assert enriched["holdings"][1]["intel"]["posture"] == "no_signal"
    assert "intel" not in enriched["holdings"][2]  # cash skipped
    assert enriched["open_orders"][0].get("intel") is not None
    assert enriched.get("intel_summary") is not None
    assert enriched["intel_summary"]["holdings_with_signals"] == 1


def test_enrich_portfolio_with_board_data():
    snapshot = {
        "holdings": [
            _holding("SOL", 150.0, 300.0, 50.0),
            _holding("COTI", 0.01, 10.0, 2.0),
        ],
        "open_orders": [],
        "summary": {"holding_count": 2},
    }
    board_data = {
        "SOL": {"change_1m": 3.2, "change_3m": 5.0, "momentum": "strong"},
    }
    enriched = enrich_portfolio(snapshot, board_data=board_data)
    assert enriched["holdings"][0]["intel"]["board"]["change_1m"] == 3.2
    assert "board" not in enriched["holdings"][1].get("intel", {})


# --- Descriptive 24h read fallback (coverage for board non-movers) -----------


def _holding_24h(symbol, change_24h_pct):
    h = _holding(symbol, 1.0, 100.0, 1.0)
    h["price_change_24h_pct"] = change_24h_pct
    return h


def test_descriptive_read_up_moderate():
    intel = _assess_holding(_holding_24h("ARX", 4.2), None, None, None)
    assert intel["posture"] == "descriptive_up"
    assert intel["read_source"] == "descriptive"
    assert intel["read"]["source"] == "descriptive"
    assert intel["read"]["change_24h_pct"] == 4.2
    assert "4.2" in intel["read"]["short"]
    # A descriptive read is NOT a real signal.
    assert "signal" not in intel


def test_descriptive_read_down_big():
    intel = _assess_holding(_holding_24h("BILL", -11.5), None, None, None)
    assert intel["posture"] == "descriptive_down_strong"
    assert intel["read"]["tone"] == "danger"


def test_descriptive_read_quiet_band():
    intel = _assess_holding(_holding_24h("COTI", 1.4), None, None, None)
    assert intel["posture"] == "descriptive_flat"
    assert intel["read"]["tone"] == "muted"


def test_descriptive_band_boundaries():
    # Exactly at the quiet/moving boundary counts as moving.
    assert _assess_holding(_holding_24h("A", 2.0), None, None, None)["posture"] == (
        "descriptive_up"
    )
    assert _assess_holding(_holding_24h("B", 1.99), None, None, None)["posture"] == (
        "descriptive_flat"
    )
    # Exactly at the big-move boundary counts as big.
    assert _assess_holding(_holding_24h("C", 8.0), None, None, None)["posture"] == (
        "descriptive_up_strong"
    )
    assert _assess_holding(_holding_24h("D", -8.0), None, None, None)["posture"] == (
        "descriptive_down_strong"
    )


def test_no_signal_and_no_price_change_stays_no_signal():
    # No signal and no 24h field -> genuinely no read.
    intel = _assess_holding(_holding("XYZ", 0.01, 10.0, 0.5), None, None, None)
    assert intel["posture"] == "no_signal"
    assert intel["read_source"] == "none"
    assert "read" not in intel


def test_real_signal_marks_read_source_signal():
    signal = _signal("SOL", "Moonwalking", "up", 85, "BUY WATCH")
    intel = _assess_holding(_holding_24h("SOL", 4.2), signal, None, None)
    # A live signal wins over the descriptive fallback.
    assert intel["posture"] == "momentum_favorable"
    assert intel["read_source"] == "signal"
    assert "read" not in intel


def test_levels_attach_and_enrich_descriptive_read():
    snapshot = {
        "holdings": [_holding_24h("ARX", 4.2)],
        "open_orders": [],
        "summary": {"holding_count": 1},
    }
    levels = {
        "ARX": {
            "support": 0.5,
            "resistance": 1.0,
            "range_zone": "near_resistance",
            "outcome_validated": False,
        }
    }
    enriched = enrich_portfolio(snapshot, levels_data=levels)
    holding = enriched["holdings"][0]
    # Levels are attached at the holding level.
    assert holding["levels"]["range_zone"] == "near_resistance"
    assert holding["levels"]["outcome_validated"] is False
    # The descriptive read gains recent-range context.
    assert "resistance" in holding["intel"]["read"]["short"].lower()


def test_levels_do_not_touch_a_signal_read():
    signal = _signal("SOL", "Moonwalking", "up", 85, "BUY WATCH")
    snapshot = {
        "holdings": [_holding_24h("SOL", 4.2)],
        "open_orders": [],
        "summary": {"holding_count": 1},
    }
    levels = {"SOL": {"range_zone": "near_resistance"}}
    enriched = enrich_portfolio(snapshot, signals=[signal], levels_data=levels)
    holding = enriched["holdings"][0]
    assert holding["levels"]["range_zone"] == "near_resistance"
    # A real signal read is untouched (no descriptive "read" dict to enrich).
    assert holding["intel"]["read_source"] == "signal"
    assert "read" not in holding["intel"]


def test_summary_keeps_signal_coverage_pure():
    snapshot = {
        "holdings": [
            _holding_24h("SOL", 4.2),  # real signal below
            _holding_24h("ARX", -3.1),  # descriptive only
            _holding_24h("COTI", 0.3),  # descriptive only (quiet)
            {"symbol": "USD", "is_cash": True, "market_value_usd": 500.0},
        ],
        "open_orders": [],
        "summary": {"holding_count": 3},
    }
    signals = [_signal("SOL", "Moonwalking", "up", 85)]
    enriched = enrich_portfolio(snapshot, signals=signals)

    summary = enriched["intel_summary"]
    # Only SOL has a real signal.
    assert summary["holdings_with_signals"] == 1
    assert summary["signal_coverage_pct"] == round(1 / 3 * 100, 1)
    # All three non-cash holdings have a read (1 signal + 2 descriptive).
    assert summary["holdings_with_read"] == 3
    assert summary["read_coverage_pct"] == 100.0
