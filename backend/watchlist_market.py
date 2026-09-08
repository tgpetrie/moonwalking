"""Cached public Coinbase 24-hour references; never substitutes another window."""
import math
import threading
import time

import requests

_lock = threading.Lock()
_cache = {"products": {}, "updated_at": None}
_last_attempt = 0
_quote_cache = {}


def normalize_stats(payload):
    products = {}
    for product_id, value in payload.items():
        if not product_id.endswith("-USD") or not isinstance(value, dict):
            continue
        stats = value.get("stats_24hour") or {}
        try:
            opening, last = float(stats["open"]), float(stats["last"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(n) and n > 0 for n in (opening, last)):
            continue
        products[product_id] = {"price": last, "previous_price": opening, "pct_24h": (last / opening - 1) * 100}
    return products


def get_market_24h():
    global _cache, _last_attempt
    with _lock:
        now = time.time()
        if now - _last_attempt >= 60:
            _last_attempt = now
            try:
                response = requests.get("https://api.exchange.coinbase.com/products/stats", timeout=8)
                response.raise_for_status()
                products = normalize_stats(response.json())
                if products:
                    _cache = {"products": products, "updated_at": time.time()}
            except (requests.RequestException, ValueError, TypeError, AttributeError):
                pass
        age = time.time() - _cache["updated_at"] if _cache["updated_at"] else None
        return {**_cache, "source": "Coinbase", "stale": age is None or age > 120}


def normalize_symbols(values):
    result = []
    for value in values or []:
        symbol = str(value or "").strip().upper().replace("-USD", "")
        if symbol and symbol not in result and len(result) < 250:
            result.append(symbol)
    return result


def get_spot_quotes(symbols):
    """Fetch the requested symbols, rather than the worker's rotating sample."""
    global _quote_cache
    symbols = normalize_symbols(symbols)
    now = time.time()
    key = tuple(sorted(symbols))
    with _lock:
        cached = _quote_cache.get(key)
        if cached and now - cached["updated_at"] < 15:
            return {**cached, "stale": False}

    def fetch(symbol):
        try:
            response = requests.get(
                f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot", timeout=5
            )
            response.raise_for_status()
            amount = float((response.json().get("data") or {}).get("amount"))
            if math.isfinite(amount) and amount > 0:
                return symbol, amount
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            return symbol, None
        return symbol, None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as executor:
        values = dict(executor.map(fetch, symbols))
    quotes = {symbol: price for symbol, price in values.items() if price is not None}
    result = {"quotes": quotes, "updated_at": time.time(), "requested": len(symbols)}
    with _lock:
        _quote_cache[key] = result
    return {**result, "stale": False}


def get_equity_quotes(symbols):
    """Best-effort public stock quotes for symbols that are not Coinbase pairs."""
    result = {}
    for symbol in normalize_symbols(symbols):
        try:
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "1d", "interval": "1m"},
                timeout=6,
                headers={"User-Agent": "Moonwalking local development"},
            )
            response.raise_for_status()
            chart = (response.json().get("chart") or {}).get("result") or []
            if not chart:
                continue
            result_data = chart[0]
            meta = result_data.get("meta") or {}
            price = float(meta.get("regularMarketPrice"))
            previous = float(meta.get("previousClose"))
            if not (math.isfinite(price) and math.isfinite(previous) and price > 0 and previous > 0):
                continue
            result[symbol] = {"price": price, "previous_price": previous, "pct_24h": (price / previous - 1) * 100}
        except (requests.RequestException, ValueError, TypeError, AttributeError, IndexError):
            continue
    return result
