import requests
import pytest
import watchlist_market as market


def test_24h_uses_exchange_open_and_rejects_missing_or_nonfinite_prices():
    result = market.normalize_stats({
        "BTC-USD": {"stats_24hour": {"open": "100", "last": "110"}},
        "ETH-USD": {"stats_24hour": {"open": "100", "last": "100"}},
        "BAD-USD": {"stats_24hour": {"open": "0", "last": "110"}},
        "NAN-USD": {"stats_24hour": {"open": "100", "last": "nan"}},
        "BTC-EUR": {"stats_24hour": {"open": "100", "last": "110"}},
        "EMPTY-USD": {},
    })
    assert set(result) == {"BTC-USD", "ETH-USD"}
    assert result["BTC-USD"]["pct_24h"] == pytest.approx(10)
    assert result["ETH-USD"]["pct_24h"] == 0


def test_outage_retains_last_good_but_marks_it_stale_and_limits_retries(monkeypatch):
    monkeypatch.setattr(market, "_cache", {"products": {"BTC-USD": {"price": 100}}, "updated_at": 100})
    monkeypatch.setattr(market, "_last_attempt", 0)
    monkeypatch.setattr(market.time, "time", lambda: 300)
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise requests.Timeout()
    monkeypatch.setattr(market.requests, "get", fail)
    assert market.get_market_24h()["stale"] is True
    assert market.get_market_24h()["products"]["BTC-USD"]["price"] == 100
    assert len(calls) == 1
