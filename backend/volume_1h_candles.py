import datetime
import logging
from typing import List, Dict

import requests

try:
    from .volume_1h_store import floor_minute, upsert_minute, prune_older_than
except ImportError:
    # Absolute import fallback
    from volume_1h_store import floor_minute, upsert_minute, prune_older_than

logger = logging.getLogger(__name__)

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"


class RateLimitError(Exception):
    """Raised when Coinbase returns HTTP 429."""


def _iso(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()


def fetch_candles_1m(product_id: str, start_ts: int, end_ts: int) -> List[Dict]:
    params = {
        "granularity": 60,
        "start": _iso(start_ts),
        "end": _iso(end_ts),
    }
    url = COINBASE_CANDLES_URL.format(product_id=product_id)
    resp = requests.get(url, params=params, timeout=8)

    if resp.status_code == 429:
        raise RateLimitError(f"429 for {product_id}")
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code} for {product_id}")

    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected candle payload for {product_id}")

    rows = []
    for entry in data:
        try:
            ts_raw, _low, _high, _open, close, vol = entry
            minute_ts = floor_minute(int(ts_raw))
            rows.append({
                "minute_ts": minute_ts,
                "close": float(close),
                "vol_base": float(vol),
            })
        except Exception:
            continue

    rows.sort(key=lambda r: r["minute_ts"])
    return rows


def refresh_product_minutes(product_id: str, now_ts: int) -> bool:
    try:
        window_start = now_ts - 130 * 60
        window_end = now_ts
        candles = fetch_candles_1m(product_id, window_start, window_end)
        for row in candles:
            upsert_minute(product_id, row["minute_ts"], row["vol_base"], close=row.get("close"))
        prune_older_than(now_ts - 3 * 60 * 60)
        return True
    except RateLimitError:
        raise
    except Exception as e:
        logger.debug(f"[volume1h] refresh failed for {product_id}: {e}")
        return False
