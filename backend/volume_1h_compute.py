import logging
from typing import Optional, Dict

from .volume_1h_store import fetch_window

logger = logging.getLogger(__name__)


def _symbol_from_product(product_id: str) -> str:
    try:
        return product_id.split("-")[0].upper()
    except Exception:
        return product_id.upper() if product_id else ""


def compute_volume_1h(product_id: str, now_ts: int) -> Optional[Dict]:
    window_start = now_ts - 120 * 60
    rows = fetch_window(product_id, window_start, now_ts)
    if not rows:
        return None

    # Require at least ~110 minutes to trust the comparison
    distinct_minutes = {r.get("minute_ts") for r in rows}
    if len(distinct_minutes) < 110:
        return None

    prev_cut = now_ts - 60 * 60
    vol_prev = 0.0
    vol_now = 0.0

    for r in rows:
        ts = r.get("minute_ts")
        vol = r.get("vol_base") or 0.0
        if ts is None:
            continue
        if ts < prev_cut:
            vol_prev += float(vol)
        else:
            vol_now += float(vol)

    pct = None
    if vol_prev > 0:
        pct = ((vol_now - vol_prev) / vol_prev) * 100.0

    return {
        "product_id": product_id,
        "symbol": _symbol_from_product(product_id),
        "volume_1h_now": vol_now,
        "volume_1h_prev": vol_prev,
        "volume_change_1h_pct": pct,
    }
