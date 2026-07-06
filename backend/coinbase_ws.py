"""Coinbase Exchange WebSocket ticker feed.

Maintains a live, thread-safe last-price store fed by the public
``wss://ws-feed.exchange.coinbase.com`` ticker channel, so the board's price
path can serve tick-fresh prices instead of fanning out ~120 REST calls per
cycle. REST remains the fallback for anything the feed hasn't seen recently,
so the /data payload shape and failure behavior are unchanged.

Enabled via ENABLE_COINBASE_WS=1 (see get_feed()).
"""

import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

WS_URL = os.environ.get("COINBASE_WS_URL", "wss://ws-feed.exchange.coinbase.com")

# If the socket goes silent for this long while we have subscriptions, we
# assume a dead connection and force a reconnect.
_SILENCE_TIMEOUT_S = float(os.environ.get("COINBASE_WS_SILENCE_TIMEOUT_S", "30"))

# Reconnect backoff schedule (seconds); the last value repeats.
_BACKOFF_STEPS = (1.0, 2.0, 5.0, 10.0, 30.0)


class TickerStore:
    """Thread-safe {symbol: (price, monotonic_ts)} store with staleness."""

    def __init__(self):
        self._lock = threading.Lock()
        self._prices = {}

    def update(self, symbol, price, ts=None):
        if not symbol:
            return
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            return
        if price_f <= 0:
            return
        with self._lock:
            self._prices[symbol.upper()] = (
                price_f,
                ts if ts is not None else time.monotonic(),
            )

    def fresh_prices(self, max_age_s, now=None):
        """Return {symbol: price} for entries younger than max_age_s."""
        cutoff = (now if now is not None else time.monotonic()) - max_age_s
        with self._lock:
            return {
                sym: price for sym, (price, ts) in self._prices.items() if ts >= cutoff
            }

    def size(self):
        with self._lock:
            return len(self._prices)


class CoinbaseTickerFeed:
    """Background thread consuming the Coinbase ticker channel.

    - ``set_products(ids)`` declares the product universe to track; the feed
      diff-subscribes on the live socket (no reconnect needed).
    - ``fresh_prices(max_age_s)`` returns recently ticked symbol prices.
    - Reconnects with exponential backoff and resubscribes automatically.
    """

    def __init__(self, url=WS_URL):
        self.url = url
        self.store = TickerStore()
        self._desired = set()
        self._subscribed = set()
        self._sub_lock = threading.Lock()
        self._ws = None
        self._ws_lock = threading.Lock()
        self._started = False
        self._start_lock = threading.Lock()
        self._last_msg_ts = 0.0
        self._connected = threading.Event()
        self._msg_count = 0
        self._reconnects = 0

    # -- public API ---------------------------------------------------------

    def start(self):
        with self._start_lock:
            if self._started:
                return
            self._started = True
        thread = threading.Thread(
            target=self._run_forever, name="coinbase-ws-feed", daemon=True
        )
        thread.start()

    def set_products(self, product_ids):
        """Declare the product universe (e.g. ["BTC-USD", ...]) to track."""
        wanted = {p for p in product_ids if isinstance(p, str) and p}
        with self._sub_lock:
            if wanted == self._desired:
                return
            self._desired = wanted
        self._sync_subscriptions()

    def fresh_prices(self, max_age_s):
        return self.store.fresh_prices(max_age_s)

    def status(self):
        with self._sub_lock:
            desired = len(self._desired)
            subscribed = len(self._subscribed)
        return {
            "connected": self._connected.is_set(),
            "desired_products": desired,
            "subscribed_products": subscribed,
            "stored_symbols": self.store.size(),
            "messages": self._msg_count,
            "reconnects": self._reconnects,
            "last_msg_age_s": (
                round(time.monotonic() - self._last_msg_ts, 1)
                if self._last_msg_ts
                else None
            ),
        }

    # -- subscription plumbing ----------------------------------------------

    def _sync_subscriptions(self):
        """Send subscribe/unsubscribe diffs for the current desired set."""
        with self._ws_lock:
            ws = self._ws
        if ws is None or not self._connected.is_set():
            return  # _on_open resubscribes everything on (re)connect
        with self._sub_lock:
            to_add = sorted(self._desired - self._subscribed)
            to_remove = sorted(self._subscribed - self._desired)
        try:
            if to_add:
                ws.send(
                    json.dumps(
                        {
                            "type": "subscribe",
                            "product_ids": to_add,
                            "channels": ["ticker"],
                        }
                    )
                )
            if to_remove:
                ws.send(
                    json.dumps(
                        {
                            "type": "unsubscribe",
                            "product_ids": to_remove,
                            "channels": ["ticker"],
                        }
                    )
                )
        except Exception as exc:  # socket died mid-send; reconnect loop handles it
            logger.warning("coinbase-ws: subscription sync failed: %s", exc)
            return
        with self._sub_lock:
            self._subscribed |= set(to_add)
            self._subscribed -= set(to_remove)

    # -- websocket callbacks --------------------------------------------------

    def _on_open(self, ws):
        self._connected.set()
        self._last_msg_ts = time.monotonic()
        with self._sub_lock:
            self._subscribed = set()
        logger.info("coinbase-ws: connected")
        self._sync_subscriptions()

    def _on_message(self, ws, raw):
        self._last_msg_ts = time.monotonic()
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            return
        msg_type = msg.get("type")
        if msg_type == "ticker":
            self._msg_count += 1
            product_id = msg.get("product_id") or ""
            symbol = product_id.split("-", 1)[0]
            self.store.update(symbol, msg.get("price"))
        elif msg_type == "error":
            logger.warning("coinbase-ws: server error: %s", msg.get("message"))

    def _on_close(self, ws, *_args):
        self._connected.clear()

    def _on_error(self, ws, error):
        logger.warning("coinbase-ws: socket error: %s", error)

    # -- connection loop -------------------------------------------------------

    def _run_forever(self):
        import websocket  # websocket-client; imported here to keep module import light

        attempt = 0
        while True:
            ws = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            with self._ws_lock:
                self._ws = ws
            try:
                # ping keeps NATs/proxies from silently dropping the socket.
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                logger.warning("coinbase-ws: run_forever crashed: %s", exc)
            finally:
                self._connected.clear()
                with self._ws_lock:
                    self._ws = None

            self._reconnects += 1
            attempt = min(attempt + 1, len(_BACKOFF_STEPS) - 1)
            delay = _BACKOFF_STEPS[attempt]
            # A healthy long-lived connection resets the backoff.
            if self._last_msg_ts and (time.monotonic() - self._last_msg_ts) < 60:
                attempt = 0
                delay = _BACKOFF_STEPS[0]
            logger.info("coinbase-ws: reconnecting in %.0fs", delay)
            time.sleep(delay)


_feed = None
_feed_lock = threading.Lock()


def ws_enabled():
    return os.environ.get("ENABLE_COINBASE_WS", "1") == "1"


def get_feed():
    """Singleton feed, started lazily on first call. None when disabled."""
    if not ws_enabled():
        return None
    global _feed
    with _feed_lock:
        if _feed is None:
            _feed = CoinbaseTickerFeed()
            _feed.start()
    return _feed
