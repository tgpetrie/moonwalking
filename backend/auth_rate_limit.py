"""In-process sliding-window rate limiting for authentication endpoints.

Deliberately separate from ``utils.rate_limiter``, which paces *outbound*
exchange API calls. This one throttles *inbound* auth requests and shares
no state with it.

Single-process only: counters live in memory and reset on restart. That is
adequate for the current single-Flask-process deployment; a multi-process
deployment would need a shared store (Redis) behind the same interface.
"""

import threading
import time
from collections import defaultdict, deque

# (max_events, window_seconds)
RESET_REQUEST_PER_EMAIL = (3, 15 * 60)
RESET_REQUEST_PER_IP = (10, 60 * 60)
RESET_CONFIRM_PER_IP = (10, 15 * 60)


class SlidingWindowLimiter:
    """Counts events per key inside a moving time window."""

    def __init__(self):
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int, *, now=None) -> bool:
        """Record an attempt for ``key``.

        Returns True when the attempt is within budget, False when it should
        be throttled. A throttled attempt is not recorded, so a caller that
        is already over budget cannot extend its own penalty window forever.
        """
        stamp = time.monotonic() if now is None else now
        cutoff = stamp - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(stamp)
            return True

    def reset(self, key: str | None = None) -> None:
        """Clear counters. Used by tests and by successful auth transitions."""
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)


# Module-level limiter shared by the auth routes.
limiter = SlidingWindowLimiter()


def client_ip() -> str:
    """Best-effort client address for rate-limit bucketing."""
    from flask import request

    forwarded = str(request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or str(request.remote_addr or "unknown")


def allow_reset_request(email_key: str) -> tuple[bool, bool]:
    """Budget check for a forgot-password submission.

    Returns ``(ip_ok, email_ok)``. The caller must keep the response neutral
    when ``email_ok`` is False, since per-email throttling would otherwise
    reveal whether an address is registered.
    """
    ip_ok = limiter.check("reset-ip:%s" % client_ip(), *RESET_REQUEST_PER_IP)
    if not ip_ok:
        return False, False
    email_ok = limiter.check("reset-email:%s" % email_key, *RESET_REQUEST_PER_EMAIL)
    return True, email_ok


def allow_reset_confirm() -> bool:
    """Budget check for submitting a reset token, to slow token guessing."""
    return limiter.check("reset-confirm-ip:%s" % client_ip(), *RESET_CONFIRM_PER_IP)
