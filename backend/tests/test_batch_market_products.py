"""Prices come from one market/products batch, with WebSocket on top and /ticker as fallback."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import app as backend_app
except Exception:  # pragma: no cover - fallback import path
    from backend import app as backend_app

import pytest

BATCH_URL = backend_app.COINBASE_MARKET_PRODUCTS_URL
TICKER_PREFIX = "https://api.exchange.coinbase.com/products/"


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.content = b"x"
        self.headers = {}

    def json(self):
        return self._payload


def _batch_row(pid, price, **extra):
    row = {
        "product_id": pid,
        "quote_currency_id": pid.rsplit("-", 1)[-1],
        "status": "online",
        "is_disabled": False,
        "trading_disabled": False,
        "price": str(price),
        "volume_24h": "999999",
    }
    row.update(extra)
    return row


class _Session:
    """Fake pooled session: serves the batch and per-coin /ticker calls."""

    def __init__(self, batch_status=200, batch_rows=None, ticker_prices=None):
        self.batch_status = batch_status
        self.batch_rows = batch_rows or []
        self.ticker_prices = ticker_prices or {}
        self.batch_calls = 0
        self.ticker_calls = []

    def get(self, url, params=None, timeout=None):
        if url == BATCH_URL:
            self.batch_calls += 1
            return _Resp(self.batch_status, {"products": self.batch_rows})
        if url.startswith(TICKER_PREFIX) and url.endswith("/ticker"):
            pid = url[len(TICKER_PREFIX) : -len("/ticker")]
            self.ticker_calls.append(pid)
            price = self.ticker_prices.get(pid)
            if price is None:
                return _Resp(404, {})
            return _Resp(200, {"price": str(price)})
        raise AssertionError(f"unexpected URL {url}")


class _Feed:
    def __init__(self, prices):
        self.prices = prices
        self.products = None

    def set_products(self, products):
        self.products = list(products)

    def fresh_prices(self, max_age):
        return dict(self.prices)


@pytest.fixture
def wire(monkeypatch):
    """Install a fake session, optional WS feed and /products endpoint."""

    def _wire(session, ws_prices=None, products_listing=None):
        monkeypatch.setattr(backend_app, "_coinbase_http", lambda: session)
        feed = _Feed(ws_prices) if ws_prices is not None else None
        monkeypatch.setattr(
            backend_app,
            "coinbase_ws_get_feed",
            (lambda: feed) if feed is not None else None,
        )
        listing_calls = []

        def fake_requests_get(url, timeout=None, **kwargs):
            assert url == backend_app.COINBASE_PRODUCTS_URL, url
            listing_calls.append(url)
            if products_listing is None:
                return _Resp(503, [])
            return _Resp(200, products_listing)

        monkeypatch.setattr(backend_app.requests, "get", fake_requests_get)
        monkeypatch.delenv("COINBASE_BATCH_PRICES", raising=False)
        return feed, listing_calls

    return _wire


UNIVERSE = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "WLD-USD"]
PRICES = {
    "BTC-USD": 58000.0,
    "ETH-USD": 1630.0,
    "SOL-USD": 67.4,
    "LINK-USD": 8.6,
    "WLD-USD": 0.229,
}


def test_batch_prices_the_whole_universe_with_no_ticker_calls(wire):
    session = _Session(batch_rows=[_batch_row(p, PRICES[p]) for p in UNIVERSE])
    _, listing_calls = wire(session)

    prices = backend_app.get_coinbase_prices()

    assert prices == {p.split("-")[0]: PRICES[p] for p in UNIVERSE}
    assert session.batch_calls == 1
    assert session.ticker_calls == []
    assert listing_calls == []  # the batch also replaces the /products listing
    lcp = backend_app.last_current_prices
    assert lcp["price_source"] == "batch"
    assert lcp["batch_hits"] == len(UNIVERSE)
    assert lcp["ok"] == lcp["submitted"] == len(UNIVERSE)
    assert lcp["ok_ratio"] == 1.0
    assert lcp["partial"] is False


def test_websocket_prices_win_over_the_cached_batch(wire):
    session = _Session(batch_rows=[_batch_row(p, PRICES[p]) for p in UNIVERSE])
    feed, _ = wire(session, ws_prices={"WLD": 0.2295, "BTC": 58010.0})

    prices = backend_app.get_coinbase_prices()

    assert prices["WLD"] == 0.2295  # tick-fresh, not the edge-cached 0.229
    assert prices["BTC"] == 58010.0
    assert prices["ETH"] == PRICES["ETH-USD"]
    assert set(feed.products) == set(UNIVERSE)
    lcp = backend_app.last_current_prices
    assert lcp["ws_hits"] == 2 and lcp["batch_hits"] == 3
    assert lcp["ok"] == len(UNIVERSE)


def test_products_the_batch_cannot_price_fall_through_to_ticker(wire):
    rows = [_batch_row(p, PRICES[p]) for p in UNIVERSE if p != "LINK-USD"]
    rows.append(_batch_row("LINK-USD", ""))
    session = _Session(batch_rows=rows, ticker_prices={"LINK-USD": 8.61})
    wire(session)

    prices = backend_app.get_coinbase_prices()

    assert session.ticker_calls == ["LINK-USD"]
    assert prices["LINK"] == 8.61
    lcp = backend_app.last_current_prices
    assert lcp["rest_submitted"] == 1 and lcp["rest_ok"] == 1
    assert lcp["ok"] == len(UNIVERSE)


def test_batch_failure_falls_back_to_products_and_ticker(wire):
    session = _Session(batch_status=503, ticker_prices=PRICES)
    listing = [{"id": p, "quote_currency": "USD", "status": "online"} for p in UNIVERSE]
    _, listing_calls = wire(session, products_listing=listing)

    prices = backend_app.get_coinbase_prices()

    assert prices == {p.split("-")[0]: PRICES[p] for p in UNIVERSE}
    assert listing_calls == [backend_app.COINBASE_PRODUCTS_URL]
    assert sorted(session.ticker_calls) == sorted(UNIVERSE)
    assert backend_app.last_current_prices["price_source"] == "ticker"


def test_batch_can_be_switched_off(wire, monkeypatch):
    session = _Session(batch_rows=[_batch_row(p, PRICES[p]) for p in UNIVERSE])
    listing = [{"id": p, "quote_currency": "USD", "status": "online"} for p in UNIVERSE]
    session.ticker_prices = PRICES
    wire(session, products_listing=listing)
    monkeypatch.setenv("COINBASE_BATCH_PRICES", "0")

    backend_app.get_coinbase_prices()

    assert session.batch_calls == 0
    assert sorted(session.ticker_calls) == sorted(UNIVERSE)


def test_parser_keeps_only_online_tradable_rows_and_never_volume(monkeypatch):
    rows = [
        _batch_row("BTC-USD", 58000),
        _batch_row("OLD-USD", 1.0, status="delisted", trading_disabled=True),
        _batch_row("OFF-USD", 1.0, is_disabled=True),
        _batch_row("BAD-USD", "not-a-number"),
        _batch_row("ZERO-USD", 0),
        "junk",
    ]
    monkeypatch.setattr(
        backend_app, "_coinbase_http", lambda: _Session(batch_rows=rows)
    )
    monkeypatch.delenv("COINBASE_BATCH_PRICES", raising=False)

    out = backend_app._fetch_market_products_batch(5)

    assert set(out) == {"BTC-USD", "BAD-USD", "ZERO-USD"}
    assert out["BTC-USD"]["price"] == 58000.0
    assert out["BAD-USD"]["price"] is None  # listed, but priced via /ticker
    assert out["ZERO-USD"]["price"] is None
    for row in out.values():
        assert set(row) == {"id", "quote_currency", "status", "price"}


def test_parser_returns_none_on_errors(monkeypatch):
    class Boom:
        def get(self, *a, **k):
            raise ConnectionError("down")

    monkeypatch.delenv("COINBASE_BATCH_PRICES", raising=False)
    monkeypatch.setattr(backend_app, "_coinbase_http", lambda: Boom())
    assert backend_app._fetch_market_products_batch(5) is None
    monkeypatch.setattr(
        backend_app, "_coinbase_http", lambda: _Session(batch_status=429)
    )
    assert backend_app._fetch_market_products_batch(5) is None
    monkeypatch.setattr(backend_app, "_coinbase_http", lambda: _Session(batch_rows=[]))
    assert backend_app._fetch_market_products_batch(5) is None
