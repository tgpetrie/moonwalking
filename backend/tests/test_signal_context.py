from __future__ import annotations

try:
    from signal_context import build_signal_context
except Exception:  # pragma: no cover
    from backend.signal_context import build_signal_context


def test_breaking_away_is_relative_to_full_universe():
    prices = {
        "BTC": {"pct_3m": 0.10},
        "ETH": {"pct_3m": 0.12},
        "SOL": {"pct_3m": 0.08},
        "KITE": {"pct_3m": 1.40},
    }

    context = build_signal_context(prices)

    assert context["KITE"]["market_relation"] == "breaking_away"
    assert context["KITE"]["market_relation_label"] == "BREAKING AWAY"


def test_market_carried_requires_a_real_market_move():
    prices = {
        "BTC": {"pct_3m": 0.60},
        "ETH": {"pct_3m": 0.55},
        "SOL": {"pct_3m": 0.58},
        "KITE": {"pct_3m": 0.57},
    }

    context = build_signal_context(prices)

    assert context["KITE"]["market_relation"] == "market_carried"


def test_tape_badges_require_minimum_trade_coverage():
    prices = {"KITE": {"pct_1m": 0.6}}
    tape = {
        "KITE": {
            "trade_imbalance": 0.8,
            "observed_quote_usd": 50_000,
            "trade_count": 8,
            "spread_bps": 95,
        }
    }

    context = build_signal_context(prices, tape)

    assert context["KITE"]["spot_pressure_label"] == "SPOT BUYING"
    assert context["KITE"]["liquidity_label"] == "THIN AIR"
    assert [badge["label"] for badge in context["KITE"]["badges"]] == [
        "SPOT BUYING",
        "THIN AIR",
    ]


def test_tape_does_not_guess_from_tiny_sample():
    context = build_signal_context(
        {"KITE": {"pct_1m": 0.2}},
        {"KITE": {"trade_imbalance": 1.0, "observed_quote_usd": 100, "trade_count": 1}},
    )

    assert context["KITE"]["spot_pressure"] == "neutral"
