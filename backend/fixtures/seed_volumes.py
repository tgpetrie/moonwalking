"""Dev fixture loader for seeding volume history used during local development.

Public API:
- load_dev_volume_fixture(hist_map, symbols=None, minutes=60, logger=None)

The loader is intentionally small, deterministic, and idempotent. It appends
chronological `(ts, vol)` tuples into each symbol's deque in `hist_map`.
If `symbols` is None, it seeds a small fallback set to avoid noisy startups.
"""
from collections import deque
import time
import os
import json

DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD"]


def load_dev_volume_fixture(hist_map, symbols=None, minutes=60, logger=None):
    """Seed `hist_map` (mapping symbol->deque) with `minutes` historical points.

    Args:
        hist_map: mapping (like defaultdict(lambda: deque(maxlen=180))) to populate.
        symbols: optional iterable of symbols to seed. If None, DEFAULT_SYMBOLS are used.
        minutes: number of minutes / points to seed (default 60).
        logger: optional logger (used for info/debug messages).

    Returns:
        dict: summary {"seeded_symbols": n, "points_each": minutes}
    """
    # If a JSON fixture exists, prefer its symbols/bases/minutes unless caller provided symbols
    fixture_path = os.path.join(os.path.dirname(__file__), 'seed_volumes.json')
    fixture = None
    if os.path.exists(fixture_path):
        try:
            with open(fixture_path, 'r') as fh:
                fixture = json.load(fh)
        except Exception:
            fixture = None

    if symbols is None:
        if fixture and isinstance(fixture.get('symbols'), list):
            symbols = fixture.get('symbols')
        else:
            symbols = DEFAULT_SYMBOLS

    # allow fixture to override minutes and bases
    if fixture:
        minutes = fixture.get('minutes', minutes)
        bases = fixture.get('bases', {})
    else:
        bases = {}

    now = time.time()
    seeded = 0

    for sym in symbols:
        try:
            # Ensure the target has a deque-like container
            dq = hist_map.get(sym)
            if dq is None:
                # Create a deque with a sensible maxlen if hist_map supports assignment
                try:
                    from collections import deque as _dq
                    dq = _dq(maxlen=180)
                    hist_map[sym] = dq
                except Exception:
                    # If hist_map doesn't support item assignment, skip
                    continue

            # Seed oldest -> newest
            for i in range(minutes, 0, -1):
                ts = now - (i * 60)
                # Choose base volume from fixture bases or fallback heuristics
                base = bases.get(sym, None)
                if base is None:
                    base = 1.0e7 if sym.startswith("BTC") else (6.0e6 if sym.startswith("ETH") else 1.0e6)
                vol = float(base * (1.0 + i * 0.001))
                try:
                    dq.append((ts, vol))
                except Exception:
                    # best-effort append
                    try:
                        dq.append((ts, float(vol)))
                    except Exception:
                        pass

            seeded += 1
        except Exception:
            if logger:
                try:
                    logger.debug(f"Failed to seed symbol {sym}")
                except Exception:
                    pass
            continue

    if logger:
        try:
            logger.info(f"Seeded dev volume history for {seeded} symbols with {minutes} points each.")
        except Exception:
            pass

    return {"seeded_symbols": seeded, "points_each": minutes}
