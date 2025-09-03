import time
import functools

# Simple in-process TTL cache for low-traffic environments (dev/test). Not distributed.
# Use small TTL (seconds) to keep UI snappy while avoiding frequent external API calls.

def _make_key(args, kwargs):
    # Prefer a stable, hashable representation; fall back to id if unhashable.
    try:
        return (tuple(args), tuple(sorted(kwargs.items())))
    except Exception:
        return ('__unhashable__', id(args))

def ttl_cache(ttl=6):
    def deco(fn):
        store = {}

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            key = _make_key(args, kwargs)
            now = time.time()
            entry = store.get(key)
            if entry is not None:
                val, ts = entry
                if now - ts < ttl:
                    return val
            val = fn(*args, **kwargs)
            store[key] = (val, now)
            return val

        def _cache_clear():
            store.clear()

        # Small helper attached for runtime clearing in tests or admin endpoints.
        wrapped._cache_clear = _cache_clear
        return wrapped

    return deco
