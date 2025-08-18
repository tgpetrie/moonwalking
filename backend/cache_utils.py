import time
import threading
from functools import wraps

_cache_store = {}          # key -> (expiry_ts, response)
_inflight = {}             # key -> threading.Event
_cache_lock = threading.RLock()

def cache_and_dedupe(ttl: float = 1.0):
    """Cache successful responses for `ttl` seconds and de-duplicate concurrent calls."""
    def deco(fn):
        key_base = fn.__name__
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (key_base,)
            now = time.time()
            with _cache_lock:
                hit = _cache_store.get(key)
                if hit and hit[0] > now:
                    return hit[1]
                evt = _inflight.get(key)
                if evt:
                    _cache_lock.release()
                    try:
                        evt.wait(timeout=3.0)
                    finally:
                        _cache_lock.acquire()
                    hit = _cache_store.get(key)
                    if hit and hit[0] > time.time():
                        return hit[1]
                evt = threading.Event()
                _inflight[key] = evt
            try:
                resp = fn(*args, **kwargs)
                status = getattr(resp, "status_code", 200)
                if 200 <= int(status) < 500:
                    with _cache_lock:
                        _cache_store[key] = (time.time() + ttl, resp)
                return resp
            finally:
                with _cache_lock:
                    e = _inflight.pop(key, None)
                    if e:
                        e.set()
        return wrapper
    return deco
