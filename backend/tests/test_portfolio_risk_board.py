import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app
import portfolio_mode
import watchlist
from portfolio_risk import build_risk_board, normalize_holdings

LEVELS = {
    "support": 95,
    "resistance": 112,
    "atr": 2,
    "band_low": 98,
    "range_position_pct": 60,
    "range_zone": "mid_range",
    "momentum_1h_pct": 1,
    "volume_ratio": 1,
    "window_hours": 50,
    "candle_count": 50,
    "chart": {"candles": [[1, 90, 110, 99, 100, 10]], "granularity_seconds": 3600},
}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    monkeypatch.setattr(backend_app, "_risk_level_signal_context", lambda symbol: {})
    monkeypatch.setattr(
        backend_app.sell_plan_outcome_store, "record_plan", lambda plan: "plan-id"
    )
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: None)
    monkeypatch.setattr(
        backend_app,
        "last_current_prices",
        {"timestamp": time.time(), "data": {"BTC": 100, "ETH": 100}},
    )
    return backend_app.app.test_client()


def test_guest_never_reads_private_holdings_or_counts_a_position_size(api, monkeypatch):
    private = Mock(side_effect=AssertionError("Guest reached a private portfolio"))
    monkeypatch.setattr(portfolio_mode, "portfolio_snapshot", private)
    gather = Mock(return_value={"BTC": LEVELS})
    monkeypatch.setattr(backend_app, "_gather_levels_for_symbols", gather)
    response = api.get("/api/risk-levels/portfolio?symbols=BTC,BTC-USD,ETH&user_id=1")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source"] == "watchlist"
    assert len(payload["rows"]) == 2
    assert payload["summary"]["counts"]["unavailable"] == 1
    assert payload["summary"]["capital_to_stop_usd"] is None
    assert all(row["quantity"] is None for row in payload["rows"])
    gather.assert_called_once_with(
        {"BTC", "ETH"}, {"BTC": 100, "ETH": 100}, include_chart=True
    )
    private.assert_not_called()
    assert response.headers["Cache-Control"] == "private, no-store"


def test_portfolio_uses_real_holdings_prices_even_outside_board_sample(
    api, monkeypatch
):
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: {"id": 7})
    monkeypatch.setattr(
        portfolio_mode,
        "portfolio_snapshot",
        lambda: backend_app.jsonify(
            {
                "status": "live",
                "updated_at": "2026-09-06T12:00:00+00:00",
                "holdings": [
                    {"symbol": "AMP", "quantity": 2, "price_usd": 100},
                    {"symbol": "AMP", "quantity": 1, "price_usd": 100},
                    {"symbol": "ETH", "quantity": 4, "price_usd": 100},
                    {"symbol": "USD", "quantity": 500, "price_usd": 1, "is_cash": True},
                ],
            }
        ),
    )
    from portfolio_risk import timestamp

    monkeypatch.setattr(
        backend_app.time, "time", lambda: timestamp("2026-09-06T12:00:00+00:00")
    )
    gather = Mock(return_value={"AMP": LEVELS})
    monkeypatch.setattr(backend_app, "_gather_levels_for_symbols", gather)
    response = api.get("/api/risk-levels/portfolio?symbols=BTC")
    payload = response.get_json()
    assert payload["source"] == "portfolio"
    assert [row["symbol"] for row in payload["rows"]] == ["AMP", "ETH"]
    assert payload["rows"][0]["quantity"] == 3
    assert payload["rows"][0]["market_value_usd"] == 300
    assert payload["summary"]["capital_to_stop_usd"] == pytest.approx(16.2)
    assert payload["summary"]["excluded_symbols"] == ["ETH"]
    assert payload["rows"][0]["plan"]["chart"]["product_id"] == "AMP-USD"
    gather.assert_called_once()


def test_non_owner_falls_back_only_to_their_own_watchlist(api, monkeypatch):
    user = {"id": 42, "email": "other@example.test"}
    monkeypatch.setattr(watchlist, "get_authenticated_user", lambda: user)
    monkeypatch.setattr(portfolio_mode, "get_authenticated_user", lambda: user)
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "owner@example.test")
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr(watchlist, "_db_connect", lambda: connection)
    scoped = Mock(return_value=[{"items": [{"itemKey": "ETH"}]}])
    monkeypatch.setattr(watchlist, "_serialize_watchlists", scoped)
    service = Mock(side_effect=AssertionError("Other user reached owner service"))
    monkeypatch.setattr(portfolio_mode, "get_portfolio_service", service)
    monkeypatch.setattr(
        backend_app, "_gather_levels_for_symbols", lambda *args, **kw: {"ETH": LEVELS}
    )
    payload = api.get("/api/risk-levels/portfolio?symbols=BTC&user_id=1").get_json()
    assert payload["source"] == "watchlist"
    assert [row["symbol"] for row in payload["rows"]] == ["ETH"]
    scoped.assert_called_once_with(connection, 42)
    service.assert_not_called()


@pytest.mark.parametrize(
    "symbols", ["BTC-EUR", "../ETH", "BTC;ETH", ",".join(f"C{i}" for i in range(251))]
)
def test_guest_input_is_bounded_and_validated(api, symbols):
    assert (
        api.get(
            "/api/risk-levels/portfolio", query_string={"symbols": symbols}
        ).status_code
        == 400
    )


def test_stale_quotes_cannot_produce_fresh_plans(api, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "last_current_prices",
        {"timestamp": time.time() - 600, "data": {"BTC": 100}},
    )
    gather = Mock(side_effect=AssertionError("Stale quote should not fetch candles"))
    monkeypatch.setattr(backend_app, "_gather_levels_for_symbols", gather)
    payload = api.get("/api/risk-levels/portfolio?symbols=BTC").get_json()
    assert payload["rows"][0]["plan"]["available"] is False
    assert "fresh quote" in payload["rows"][0]["plan"]["reason"]
    gather.assert_not_called()


def test_risk_order_and_missing_sizes_remain_honest():
    holdings = normalize_holdings(
        [
            {"symbol": "AAA", "price_usd": 100, "quantity": None},
            {"symbol": "BBB", "price_usd": 100, "quantity": 2},
            {"symbol": "CCC", "price_usd": None, "quantity": 3},
        ],
        positions=True,
    )
    result = build_risk_board(
        holdings,
        {
            "AAA": LEVELS,
            "BBB": {**LEVELS, "momentum_1h_pct": -1, "range_position_pct": 90},
        },
        {"BBB": {"primary_state": "Reversal Risk"}},
        source="portfolio",
        quote_as_of=1000,
        now=1001,
    )
    assert [row["symbol"] for row in result["rows"]] == ["BBB", "AAA", "CCC"]
    assert result["summary"]["excluded_symbols"] == ["AAA", "CCC"]
    assert result["summary"]["sized_plan_count"] == 1


def test_one_failed_candle_fetch_does_not_erase_the_rest(api, monkeypatch):
    monkeypatch.setattr(backend_app, "_LEVELS_CANDLE_CACHE", {})

    def candles(product, **kwargs):
        if product == "BTC-USD":
            raise RuntimeError("Provider failed")
        return [[time.time() - 7200, 90, 110, 99, 100, 10]]

    monkeypatch.setattr(backend_app, "_fetch_coinbase_candles", candles)
    import position_levels

    monkeypatch.setattr(
        position_levels, "compute_levels", lambda *args, **kwargs: LEVELS
    )
    result = backend_app._gather_levels_for_symbols(
        {"BTC", "ETH"}, {"BTC": 100, "ETH": 100}, include_chart=True
    )
    assert set(result) == {"ETH"}


def test_empty_guest_watchlist_is_an_explicit_empty_board(api):
    payload = api.get("/api/risk-levels/portfolio").get_json()
    assert payload["rows"] == []
    assert payload["source"] == "watchlist"
    assert payload["summary"]["capital_to_stop_usd"] is None
