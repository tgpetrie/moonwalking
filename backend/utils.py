import socket

def find_available_port(start_port=5001, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available ports found")


# --- Snapshot-based 1-hour volume helpers (working913 additions) -----------
from collections import deque
import threading
import time

# Expected to be populated elsewhere by your price/volume poller.
# Structure: VOLUME_SNAPSHOTS[symbol] = deque([(ts, volume_float), ...], maxlen=120)
try:
    VOLUME_SNAPSHOTS  # type: ignore[name-defined]
except NameError:
    VOLUME_SNAPSHOTS = {}

_SNAPSHOT_LOCK = threading.Lock()

def _latest_and_ago(deq, window_sec: int = 3600):
    """Return (now_volume, ago_volume) within ~window_sec if available."""
    if not deq:
        return None, None
    now_ts = time.time()
    now_val = deq[-1][1]
    target = now_ts - window_sec
    ago_val = None
    for ts, val in reversed(deq):
        if ts <= target:
            ago_val = val
            break
    if ago_val is None and deq:
        ago_val = deq[0][1]
    return now_val, ago_val

def get_1h_volume_weighted_data(limit: int = 50):
    """Compute 1h volume % change rows from VOLUME_SNAPSHOTS.

    Returns: list of dicts {symbol, volume_now, volume_1h_ago, volume_change_pct, percent_change}
    """
    out = []
    with _SNAPSHOT_LOCK:
        items = list(VOLUME_SNAPSHOTS.items())
    for symbol, deq in items:
        if not isinstance(deq, deque) or len(deq) < 2:
            continue
        vol_now, vol_ago = _latest_and_ago(deq)
        if vol_now is None or vol_ago is None:
            continue
        if not isinstance(vol_now, (int, float)) or not isinstance(vol_ago, (int, float)) or vol_ago <= 0:
            continue
        pct = ((vol_now - vol_ago) / vol_ago) * 100.0
        out.append({
            "symbol": symbol,
            "volume_now": vol_now,
            "volume_1h_ago": vol_ago,
            "volume_change_pct": pct,
            "percent_change": pct,
        })
    out.sort(key=lambda r: abs(r.get("volume_change_pct", 0.0)), reverse=True)
    return out[:limit]
