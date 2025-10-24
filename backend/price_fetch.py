import time, requests, logging, os, threading, random, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from config import CONFIG
from reliability import CircuitBreaker
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, ConnectTimeout, ReadTimeout
from pathlib import Path

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

_FIXTURE_CACHE = {}


def _load_fixture(name: str):
    if not CONFIG.get('USE_FIXTURES'):
        return None
    base = CONFIG.get('FIXTURE_DIR', os.path.join(os.path.dirname(__file__), 'fixtures'))
    path = Path(base) / name
    try:
        if not path.exists():
            logging.warning("price_fetch fixture missing: %s", path)
            return None
        cache_bypass = os.environ.get('FIXTURE_CACHE_BYPASS') in {'1', 'true', 'True'}
        if cache_bypass or name not in _FIXTURE_CACHE:
            with path.open('r', encoding='utf-8') as fh:
                _FIXTURE_CACHE[name] = json.load(fh)
        return _FIXTURE_CACHE[name]
    except Exception as exc:
        logging.error("price_fetch fixture load failed %s: %s", name, exc)
        return None

# Configure a session with reasonable retry/backoff to reduce transient connection failures
_SESSION = requests.Session()
_RETRY_STRATEGY = Retry(
    total=int(os.environ.get('PRICE_FETCH_REQUEST_RETRIES','3')),  # a couple retries
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(['GET']),
    backoff_factor=float(os.environ.get('PRICE_FETCH_RETRY_BACKOFF','0.5')),
    raise_on_status=False,
)
# Increase the adapter pool so bursty fetches do not exhaust urllib3's
# default (10) connection pool and spam the console with warnings.
_ADAPTER = HTTPAdapter(
    pool_connections=int(os.environ.get('PRICE_FETCH_POOL_CONNECTIONS', '32')),
    pool_maxsize=int(os.environ.get('PRICE_FETCH_POOL_MAXSIZE', '64')),
    max_retries=_RETRY_STRATEGY,
    pool_block=True,
)
_SESSION.mount('https://', _ADAPTER)
_SESSION.mount('http://', _ADAPTER)

# Timeouts: allow a longer connect and read timeout (connect, read)
# Use explicit env vars for connect/read to keep behaviour clear
API_TIMEOUT_CONNECT = int(CONFIG.get('API_TIMEOUT_CONNECT', os.environ.get('API_TIMEOUT_CONNECT', '5')))
API_TIMEOUT_READ = int(CONFIG.get('API_TIMEOUT_READ', os.environ.get('API_TIMEOUT_READ', '10')))
API_TIMEOUT: Tuple[int,int] = (API_TIMEOUT_CONNECT, API_TIMEOUT_READ)
TICKER_TIMEOUT_CONNECT = int(os.environ.get('TICKER_TIMEOUT_CONNECT', '5'))
TICKER_TIMEOUT_READ = int(os.environ.get('TICKER_TIMEOUT_READ', '10'))
TICKER_TIMEOUT: Tuple[int,int] = (TICKER_TIMEOUT_CONNECT, TICKER_TIMEOUT_READ)

# Max workers for concurrent ticker fetches (cap to avoid connection storms)
MAX_WORKERS = int(os.environ.get('PRICE_FETCH_MAX_WORKERS', '4'))

# Semaphore to guard simultaneous outbound connections (extra safety)
_semaphore = threading.BoundedSemaphore(MAX_WORKERS)

# Metrics (simple counters; not high-concurrency critical but guarded for safety)
_metrics_lock = threading.Lock()
_metrics = {
    'total_calls': 0,
    'snapshot_served': 0,
    'products_cache_hits': 0,
    'rate_limit_failures': 0,
    'last_fetch_duration_ms': 0.0,
    'last_success_time': 0.0,
    'errors': 0,  # total error events (rate limits, non-2xx, exceptions, ticker errors)
    'durations_ms': [],  # rolling window of recent fetch durations
}

# Bound the rolling durations list to avoid unbounded memory usage
_DURATIONS_MAX = int(os.environ.get('PRICE_FETCH_DURATIONS_MAX','200'))

# Histogram buckets (milliseconds) for historical latency distribution (cumulative style for Prometheus emission)
_HIST_BUCKETS_MS = [int(x) for x in os.environ.get('PRICE_FETCH_DURATION_BUCKETS','50,100,200,400,800,1600,3200,6400').split(',') if x.strip()]
_hist_lock = threading.Lock()
_hist_duration_counts = {b: 0 for b in _HIST_BUCKETS_MS}  # per-bucket (non-cumulative) counts
_hist_overflow = 0  # > max bucket
_hist_sum = 0.0
_hist_count = 0

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
    try:
        r = requests.get(COINBASE_PRODUCTS_URL, timeout=API_TIMEOUT)
    except RequestException as e:  # network error
        with _metrics_lock:
            _metrics['errors'] += 1
        logging.warning(f"Products fetch exception {e}; using cached list")
        return _products_cache['items']
    if r.status_code == 200:
        try:
            _products_cache['items'] = r.json()
        except Exception:
            logging.warning('price_fetch.products_invalid_json; using cached list')
            with _metrics_lock:
                _metrics['errors'] += 1
            return _products_cache['items']
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
                _metrics['errors'] += 1
            _cb.record_failure()
        else:
            with _metrics_lock:
                _metrics['errors'] += 1
        logging.warning(f"Products fetch status {r.status_code}; using cached list")
    return _products_cache['items']


def fetch_prices() -> Dict[str,float]:
    start = time.time()
    now = time.time()
    with _metrics_lock:
        _metrics['total_calls'] += 1
    if CONFIG.get('USE_FIXTURES'):
        fixture = _load_fixture('top_movers_3m.json')
        price_map: Dict[str, float] = {}
        if isinstance(fixture, dict):
            combined = []
            for key in ('gainers', 'losers', 'top24h'):
                val = fixture.get(key, [])
                if isinstance(val, list):
                    combined.extend(val)
            for entry in combined:
                if not isinstance(entry, dict):
                    continue
                symbol = str(entry.get('symbol', '') or '').upper()
                if not symbol:
                    continue
                raw_price = entry.get('current') if entry.get('current') is not None else entry.get('current_price')
                try:
                    price_val = float(raw_price)
                except (TypeError, ValueError):
                    continue
                candidates = [symbol, f"{symbol}-USD"]
                for candidate in candidates:
                    if candidate and candidate not in price_map:
                        price_map[candidate] = price_val
        if price_map:
            _last_snapshot['data'] = dict(price_map)
            _last_snapshot['fetched_at'] = now
            return price_map
        logging.warning("Fixtures enabled but top_movers_3m.json missing price payload; returning cached snapshot")
        if _last_snapshot['data']:
            return dict(_last_snapshot['data'])
        return {}
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
    # compute workers but cap by MAX_WORKERS
    workers = max(2, min(MAX_WORKERS, 8 - _rate['failures']*2))

    def _ticker(sym: str):
        # Limit concurrent outbound sockets using semaphore to avoid bursts
        acquired = _semaphore.acquire(timeout=10)
        try:
            # Use requests.get directly here so tests that monkeypatch requests.get behave
            # predictably (avoids _SESSION being a shared object with internal state
            # that some tests may not patch). Keep the same timeout contract.
            r = requests.get(f"https://api.exchange.coinbase.com/products/{sym}/ticker", timeout=TICKER_TIMEOUT)
            if r.status_code == 200:
                data = r.json(); price = float(data.get('price') or 0)
                if price > 0:
                    return sym, price
            elif r.status_code == 429:
                with _metrics_lock:
                    _metrics['errors'] += 1
                    _metrics['rate_limit_failures'] += 1
                return '__RL__', None
            else:
                with _metrics_lock:
                    _metrics['errors'] += 1
        except (ConnectTimeout, ReadTimeout) as e:
            # connection timed out - count and debug. Increase visibility because timeouts were observed.
            logging.warning(f"ticker {sym} timeout {e}")
            with _metrics_lock:
                _metrics['errors'] += 1
        except RequestException as e:
            logging.debug(f"ticker {sym} err {e}")
            with _metrics_lock:
                _metrics['errors'] += 1
        except Exception as e:
            logging.debug(f"ticker {sym} unexpected {e}")
            with _metrics_lock:
                _metrics['errors'] += 1
            return None, None
        finally:
            if acquired:
                # add a tiny jittered sleep before releasing to spread connection attempts
                time.sleep(random.uniform(0.01, 0.05))
                _semaphore.release()

    # limit how many targets we attempt in one pass to reduce load
    targets_to_fetch = targets[:50]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_ticker, p['id']): p for p in targets_to_fetch}
        for f in as_completed(futs):
            try:
                sym, pr = f.result()
            except Exception as e:
                logging.debug(f"ticker future err: {e}")
                with _metrics_lock:
                    _metrics['errors'] += 1
                continue
            if sym == '__RL__':
                _rate['failures'] = min(_rate['failures']+1,10)
                continue
            if sym and pr:
                prices[sym]=pr
    # If no live prices were obtained, try a fixture fallback (useful in dev or when upstream is flaky)
    if not prices:
        try:
            fixture = _load_fixture('top_movers_3m.json')
            if isinstance(fixture, dict):
                logging.warning('price_fetch: no live prices collected; attempting fixture fallback')
                price_map = {}
                for key in ('gainers', 'losers', 'top24h'):
                    for entry in fixture.get(key, []) or []:
                        if not isinstance(entry, dict):
                            continue
                        symbol = str(entry.get('symbol', '') or '').upper()
                        if not symbol:
                            continue
                        raw_price = entry.get('current') if entry.get('current') is not None else entry.get('current_price')
                        try:
                            price_val = float(raw_price)
                        except (TypeError, ValueError):
                            continue
                        candidates = [symbol, f"{symbol}-USD"]
                        for candidate in candidates:
                            if candidate and candidate not in price_map:
                                price_map[candidate] = price_val
                if price_map:
                    prices.update(price_map)
                    # mark snapshot so other callers can reuse
                    _last_snapshot['data'] = dict(prices)
                    _last_snapshot['fetched_at'] = time.time()
        except Exception:
            pass
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
        arr = _metrics['durations_ms']
        arr.append(dur_ms)
        if len(arr) > _DURATIONS_MAX:
            # trim oldest slice
            del arr[: len(arr) - _DURATIONS_MAX]
    # histogram update (separate lock to reduce contention scope)
    global _hist_count, _hist_sum, _hist_overflow
    with _hist_lock:
        _hist_count += 1
        _hist_sum += dur_ms
        placed = False
        for edge in _HIST_BUCKETS_MS:
            if dur_ms <= edge:
                _hist_duration_counts[edge] += 1
                placed = True
                break
        if not placed:
            _hist_overflow += 1
    return prices


def get_price_fetch_metrics():
    with _metrics_lock:
        # return shallow copy to avoid external mutation
        data = dict(_metrics)
    # enrich with dynamic state
    now = time.time()
    # Compute p95 duration (copy list without lock contention)
    durations = data.get('durations_ms') or []
    p95 = None
    if durations:
        sorted_d = sorted(durations)
        idx = int(len(sorted_d) * 0.95) - 1
        idx = max(0, min(idx, len(sorted_d)-1))
        p95 = sorted_d[idx]
    total_calls = data.get('total_calls', 0)
    errors = data.get('errors', 0)
    error_rate_pct = (errors / total_calls * 100.0) if total_calls else 0.0
    backoff_remaining = max(0.0, _rate['next'] - now) if _rate['next'] else 0.0
    data.update({
        'rate_failures': _rate['failures'],
        'rate_next_epoch': _rate['next'],
        'has_snapshot': bool(_last_snapshot['data']),
        'snapshot_age_sec': (now - _last_snapshot['fetched_at']) if _last_snapshot['fetched_at'] else None,
        'p95_fetch_duration_ms': p95,
        'error_rate_percent': round(error_rate_pct, 4),
        'backoff_seconds_remaining': round(backoff_remaining, 3),
    })
    # Snapshot histogram (non-cumulative raw counts + overflow) for JSON
    with _hist_lock:
        data['fetch_duration_hist_buckets'] = {str(edge): _hist_duration_counts[edge] for edge in _HIST_BUCKETS_MS}
        data['fetch_duration_hist_overflow'] = _hist_overflow
        data['fetch_duration_sum_ms'] = round(_hist_sum, 3)
        data['fetch_duration_count'] = _hist_count
    # Circuit breaker snapshot
    try:
        data['circuit_breaker'] = _cb.snapshot()
    except Exception:
        pass
    return data
