import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from coinbase_ws import CoinbaseTickerFeed, TickerStore


def test_store_freshness_window():
    store = TickerStore()
    now = time.monotonic()
    store.update("BTC", "50000.5", ts=now)
    store.update("ETH", "3000", ts=now - 30)

    fresh = store.fresh_prices(10, now=now)
    assert fresh == {"BTC": 50000.5}

    wide = store.fresh_prices(60, now=now)
    assert wide == {"BTC": 50000.5, "ETH": 3000.0}


def test_store_rejects_garbage():
    store = TickerStore()
    store.update("BTC", "not-a-number")
    store.update("BTC", "-1")
    store.update("BTC", None)
    store.update("", "100")
    assert store.size() == 0


def test_ticker_message_updates_store():
    feed = CoinbaseTickerFeed()
    raw = json.dumps({"type": "ticker", "product_id": "SOL-USD", "price": "142.37"})
    feed._on_message(None, raw)
    assert feed.fresh_prices(5) == {"SOL": 142.37}
    assert feed.status()["messages"] == 1


def test_non_ticker_messages_ignored():
    feed = CoinbaseTickerFeed()
    feed._on_message(None, json.dumps({"type": "subscriptions"}))
    feed._on_message(None, "not json")
    assert feed.store.size() == 0


class _FakeSocket:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(json.loads(payload))


def test_subscription_diffing():
    feed = CoinbaseTickerFeed()
    sock = _FakeSocket()
    feed._ws = sock
    feed._connected.set()

    feed.set_products(["BTC-USD", "ETH-USD"])
    assert sock.sent[-1]["type"] == "subscribe"
    assert sorted(sock.sent[-1]["product_ids"]) == ["BTC-USD", "ETH-USD"]

    # Adding one and dropping one sends a diff, not the whole set again.
    feed.set_products(["BTC-USD", "SOL-USD"])
    types = [(m["type"], m["product_ids"]) for m in sock.sent[1:]]
    assert ("subscribe", ["SOL-USD"]) in types
    assert ("unsubscribe", ["ETH-USD"]) in types

    # No-op when the desired set is unchanged.
    n = len(sock.sent)
    feed.set_products(["SOL-USD", "BTC-USD"])
    assert len(sock.sent) == n


def test_resubscribes_everything_on_reconnect():
    feed = CoinbaseTickerFeed()
    feed.set_products(["BTC-USD", "ETH-USD"])  # socket not connected yet

    sock = _FakeSocket()
    feed._ws = sock
    feed._on_open(sock)

    assert sock.sent[-1]["type"] == "subscribe"
    assert sorted(sock.sent[-1]["product_ids"]) == ["BTC-USD", "ETH-USD"]
