"""Reliability primitives: circuit breaker + stale-while-revalidate decorator.

Designed to be lightweight and self-contained (no external deps).
"""
from __future__ import annotations
import threading, time, functools, logging
from typing import Any, Callable, Dict, Tuple
from alerting import AlertNotifier


class CircuitBreaker:
    """Simple circuit breaker.

    States:
      CLOSED: normal operation
      OPEN: short-circuit calls until open_until epoch
      HALF_OPEN: after cooldown, allow a single trial call
    """

    def __init__(self, fail_threshold: int, reset_seconds: float):
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds
        self._lock = threading.Lock()
        self.failures = 0
        self.state = 'CLOSED'
        self.open_until = 0.0
        self._half_open_trial_inflight = False

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            if self.state == 'OPEN':
                if now >= self.open_until:
                    # Move to HALF_OPEN (one trial allowed)
                    self.state = 'HALF_OPEN'
                    self._half_open_trial_inflight = False
                else:
                    return False
            if self.state == 'HALF_OPEN':
                if self._half_open_trial_inflight:
                    return False
                self._half_open_trial_inflight = True
            return True

    def record_success(self):
        with self._lock:
            prev_state = self.state
            self.failures = 0
            self.state = 'CLOSED'
            self.open_until = 0.0
            self._half_open_trial_inflight = False
        if prev_state in ('OPEN','HALF_OPEN'):
            logging.info('circuit_breaker.reset', extra={'event':'circuit_reset','prev_state':prev_state})
            try:
                _ALERTER.send('breaker_reset', {'prev_state': prev_state})
            except Exception:
                pass

    def record_failure(self):
        now = time.time()
        with self._lock:
            self.failures += 1
            if self.state == 'HALF_OPEN':
                # Immediate reopen on half-open failure
                self.state = 'OPEN'
                self.open_until = now + self.reset_seconds
                self._half_open_trial_inflight = False
                logging.warning('circuit_breaker.reopen', extra={'event':'circuit_reopen','state':'OPEN','failures':self.failures})
                try:
                    _ALERTER.send('breaker_reopen', {'failures': self.failures, 'open_until': self.open_until})
                except Exception:
                    pass
                return
            if self.failures >= self.fail_threshold and self.state == 'CLOSED':
                self.state = 'OPEN'
                self.open_until = now + self.reset_seconds
                logging.warning('circuit_breaker.open', extra={'event':'circuit_open','failures':self.failures,'open_until':self.open_until})
                try:
                    _ALERTER.send('breaker_open', {'failures': self.failures, 'open_until': self.open_until})
                except Exception:
                    pass

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'state': self.state,
                'failures': self.failures,
                'open_until': self.open_until,
            }


def stale_while_revalidate(ttl: float, stale_window: float):
    """Decorator implementing stale-while-revalidate.

    Cache entry lifecycle:
      fresh (< ttl): serve cached
      stale but within ttl+stale_window: serve cached & spawn background refresh
      beyond ttl+stale_window: block & recompute synchronously
    """
    def decorator(fn: Callable):
        lock = threading.Lock()
        cache: Dict[str, Any] = {'value': None, 'ts': 0.0, 'refreshing': False}
        stats: Dict[str, Any] = {
            'total_calls': 0,
            'served_cached': 0,
            'served_fresh': 0,
            'background_refreshes': 0,
            'last_refresh_duration_sec': None,
        }

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            now = time.time()
            age = now - cache['ts'] if cache['ts'] else None
            stats['total_calls'] += 1
            # Fast path: fresh
            if cache['value'] is not None and age is not None and age < ttl:
                wrapper._swr_cache_ts = cache['ts']
                wrapper._swr_last_age = age
                wrapper._swr_last_served_cached = True
                stats['served_cached'] += 1
                return cache['value']
            # Stale but within window -> async refresh
            if cache['value'] is not None and age is not None and age < (ttl + stale_window):
                if not cache['refreshing']:
                    def _refresh():
                        t0 = time.time()
                        try:
                            v = fn(*args, **kwargs)
                            with lock:
                                cache['value'] = v
                                cache['ts'] = time.time()
                                stats['last_refresh_duration_sec'] = cache['ts'] - t0
                        except Exception as e:  # pragma: no cover
                            logging.warning('swr.refresh_error', extra={'event':'swr_refresh_error','error':str(e)})
                        finally:
                            with lock:
                                cache['refreshing'] = False
                    with lock:
                        if not cache['refreshing']:
                            cache['refreshing'] = True
                            stats['background_refreshes'] += 1
                            threading.Thread(target=_refresh, daemon=True).start()
                wrapper._swr_cache_ts = cache['ts']
                wrapper._swr_last_age = age
                wrapper._swr_last_served_cached = True
                stats['served_cached'] += 1
                return cache['value']
            # Expired: recompute synchronously
            t0 = time.time()
            result = fn(*args, **kwargs)
            with lock:
                cache['value'] = result
                cache['ts'] = time.time()
                stats['served_fresh'] += 1
                stats['last_refresh_duration_sec'] = cache['ts'] - t0
            wrapper._swr_cache_ts = cache['ts']
            wrapper._swr_last_age = 0.0
            wrapper._swr_last_served_cached = False
            return result

        # instrumentation attributes
        wrapper._swr_cache_ts = 0.0
        wrapper._swr_last_age = None
        wrapper._swr_last_served_cached = False
        wrapper._swr_stats = stats  # expose counters
        return wrapper
    return decorator

_ALERTER = AlertNotifier.from_env()

__all__ = ['CircuitBreaker','stale_while_revalidate']