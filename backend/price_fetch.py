import time, requests, logging, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict
from config import CONFIG
from reliability import CircuitBreaker

COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
MAJOR_COINS = {
    # Curated major symbols (must exist on Coinbase). Removed 'JUP-USD' per user note.
    'BTC-USD','ETH-USD','SOL-USD','ADA-USD','DOT-USD','LINK-USD','MATIC-USD','AVAX-USD','ATOM-USD','ALGO-USD',
    'XRP-USD','DOGE-USD','SHIB-USD','UNI-USD','AAVE-USD','BCH-USD','LTC-USD','ICP-USD','HYPE-USD','SPX-USD',
    'SEI-USD','PI-USD','KAIA-USD','INJ-USD','ONDO-USD','CRO-USD','FLR-USD','WLD-USD','POL-USD','WBT-USD',
    'SKY-USD','TAO-USD'
}
PRODUCTS_CACHE_TTL = float(os.environ.get('COINBASE_PRODUCTS_CACHE_SECONDS','300'))
_products_cache = {"items": None, "fetched_at": 0.0, "ttl": PRODUCTS_CACHE_TTL}
_last_snapshot = {"data": {}, "fetched_at": 0.0}

BACKOFF_BASE = float(os.environ.get('COINBASE_BACKOFF_BASE','1'))
BACKOFF_MAX = float(os.environ.get('COINBASE_BACKOFF_MAX','30'))
BACKOFF_RESET_MIN = int(os.environ.get('BACKOFF_SUCCESS_RESET_MIN_PRICES','20'))
_rate = {"failures":0,"next":0.0,"last_error":None}

# Metrics (simple counters; not high-concurrency critical but guarded for safety)
_metrics_lock = threading.Lock()
_metrics = {
    'total_calls': 0,
    'snapshot_served': 0,
    'products_cache_hits': 0,
    'rate_limit_failures': 0,
    'last_fetch_duration_ms': 0.0,
    'last_success_time': 0.0,
}

# Circuit breaker (fail fast protecting upstream)
_cb = CircuitBreaker(
    fail_threshold=int(os.environ.get('PRICE_FETCH_CB_FAIL_THRESHOLD','5')),
    reset_seconds=float(os.environ.get('PRICE_FETCH_CB_RESET_SECONDS','20'))
)

def _load_products(now: float):
    if not _cb.allow():
        logging.warning('price_fetch.circuit_open_products', extra={'event':'circuit_open_products'})
        return _products_cache['items']  # may be None
    if _products_cache['items'] and now - _products_cache['fetched_at'] < _products_cache['ttl']:
        with _metrics_lock:
            _metrics['products_cache_hits'] += 1
        return _products_cache['items']
    r = requests.get(COINBASE_PRODUCTS_URL, timeout=CONFIG['API_TIMEOUT'])
    if r.status_code == 200:
        _products_cache['items'] = r.json()
        _products_cache['fetched_at'] = now
        _cb.record_success()
    else:
        if r.status_code in {429,500,502,503,504}:
            prev_failures = _rate['failures']
            _rate['failures'] += 1
            delay = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (_rate['failures']-1)))
            _rate['next'] = now + delay
            _rate['last_error'] = f"products {r.status_code} backoff {delay:.1f}s"
            logging.warning(
                "price_fetch.backoff_escalate", extra={
                    'event': 'backoff_escalate',
                    'status': r.status_code,
                    'prev_failures': prev_failures,
                    'failures': _rate['failures'],
                    'delay_seconds': round(delay,2),
                    'next_epoch': _rate['next']
                }
            )
            with _metrics_lock:
                _metrics['rate_limit_failures'] = _rate['failures']
            _cb.record_failure()
        logging.warning(f"Products fetch status {r.status_code}; using cached list")
    return _products_cache['items']

def fetch_prices() -> Dict[str,float]:
    start = time.time()
    now = time.time()
    with _metrics_lock:
        _metrics['total_calls'] += 1
    if now < _rate['next'] and _last_snapshot['data']:
        # Backoff gate active; serve snapshot
        logging.info(
            "price_fetch.snapshot_due_to_backoff",
            extra={
                'event': 'snapshot_due_to_backoff',
                'failures': _rate['failures'],
                'next_epoch': _rate['next'],
                'snapshot_age_sec': now - _last_snapshot['fetched_at']
            }
        )
        with _metrics_lock:
            _metrics['snapshot_served'] += 1
        return dict(_last_snapshot['data'])
    products = _load_products(now)
    if not products:
        with _metrics_lock:
            _metrics['snapshot_served'] += 1
        return dict(_last_snapshot['data'])
    usd = [p for p in products if p.get('quote_currency')=='USD' and p.get('status')=='online']
    majors = [p for p in usd if p.get('id') in MAJOR_COINS]
    others = [p for p in usd if p.get('id') not in MAJOR_COINS]
    targets = majors + others[: max(0,100-len(majors))]

    prices: Dict[str,float] = {}
    workers = max(2, 8 - _rate['failures']*2)
    def _ticker(sym: str):
        try:
            r = requests.get(f"https://api.exchange.coinbase.com/products/{sym}/ticker", timeout=1.5)
            if r.status_code == 200:
                data = r.json(); price = float(data.get('price') or 0)
                if price>0: return sym, price
            elif r.status_code == 429:
                return '__RL__', None
        except Exception as e:
            logging.debug(f"ticker {sym} err {e}")
        return None, None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_ticker, p['id']): p for p in targets[:50]}
        for f in as_completed(futs):
            sym, pr = f.result()
            if sym == '__RL__':
                _rate['failures'] = min(_rate['failures']+1,10)
                continue
            if sym and pr:
                prices[sym]=pr
    if prices:
        _last_snapshot['data']=prices
        _last_snapshot['fetched_at']=now
        if len(prices) >= BACKOFF_RESET_MIN:
            if _rate['failures'] or _rate['next']:
                logging.info(
                    "price_fetch.backoff_reset",
                    extra={
                        'event': 'backoff_reset',
                        'prev_failures': _rate['failures'],
                        'symbols': len(prices)
                    }
                )
            _rate['failures']=0; _rate['next']=0; _rate['last_error']=None
        with _metrics_lock:
            _metrics['last_success_time'] = now
        _cb.record_success()
    elif _last_snapshot['data'] and now - _last_snapshot['fetched_at'] < 600:
        with _metrics_lock:
            _metrics['snapshot_served'] += 1
        return dict(_last_snapshot['data'])
    # record duration
    dur_ms = (time.time() - start) * 1000.0
    with _metrics_lock:
        _metrics['last_fetch_duration_ms'] = dur_ms
    return prices

def get_price_fetch_metrics():
    with _metrics_lock:
        # return shallow copy to avoid external mutation
        data = dict(_metrics)
    # enrich with dynamic state
    data.update({
        'rate_failures': _rate['failures'],
        'rate_next_epoch': _rate['next'],
        'has_snapshot': bool(_last_snapshot['data']),
        'snapshot_age_sec': (time.time() - _last_snapshot['fetched_at']) if _last_snapshot['fetched_at'] else None,
    })
    # Circuit breaker snapshot
    try:
        data['circuit_breaker'] = _cb.snapshot()
    except Exception:
        pass
    return data
