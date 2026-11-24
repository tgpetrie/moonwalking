import watchlist_market as market
import pytest


def test_requested_symbols_are_normalized_and_deduplicated():
    assert market.normalize_symbols(["btc-usd", " BTC ", "", "ETH-USD"]) == ["BTC", "ETH"]


def test_spot_quote_cache_avoids_repeating_a_fresh_request(monkeypatch):
    market._quote_cache = {}
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"amount": "100"}}

    monkeypatch.setattr(market.requests, "get", lambda *args, **kwargs: calls.append(args[0]) or Response())
    first = market.get_spot_quotes(["BTC"])
    second = market.get_spot_quotes(["BTC"])
    assert first["quotes"]["BTC"] == 100
    assert second["quotes"]["BTC"] == 100
    assert len(calls) == 1


def test_equity_quote_uses_previous_close_for_24h(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"chart": {"result": [{"meta": {"regularMarketPrice": 110, "previousClose": 100}}]}}

    monkeypatch.setattr(market.requests, "get", lambda *args, **kwargs: Response())
    assert market.get_equity_quotes(["TSLA"])["TSLA"]["pct_24h"] == pytest.approx(10)
