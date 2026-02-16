import logging
import os
from statistics import median
from typing import Optional, Dict

from .volume_1h_store import fetch_window

logger = logging.getLogger(__name__)

MIN_FULL_MINUTES = int(os.getenv("VOLUME_1H_MIN_FULL_MINUTES", "110"))
MIN_BOOTSTRAP_MINUTES = int(os.getenv("VOLUME_1H_MIN_BOOTSTRAP_MINUTES", "70"))
MIN_BOOTSTRAP_PREV_MINUTES = int(
    os.getenv("VOLUME_1H_MIN_BOOTSTRAP_PREV_MINUTES", "10")
)


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

    # Require minimum warmup before attempting a bootstrap baseline.
    distinct_minutes = {r.get("minute_ts") for r in rows}
    if len(distinct_minutes) < MIN_BOOTSTRAP_MINUTES:
        return None

    prev_cut = now_ts - 60 * 60
    vol_prev = 0.0
    vol_now = 0.0
    prev_minute_vols = []
    now_minutes = 0
    prev_minutes = 0

    for r in rows:
        ts = r.get("minute_ts")
        vol = r.get("vol_base") or 0.0
        if ts is None:
            continue
        if ts < prev_cut:
            vol_f = float(vol)
            vol_prev += vol_f
            prev_minute_vols.append(vol_f)
            prev_minutes += 1
        else:
            vol_now += float(vol)
            now_minutes += 1

    baseline_mode = "full"
    baseline_minutes = prev_minutes
    pct = ((vol_now - vol_prev) / vol_prev) * 100.0 if vol_prev > 0 else None

    needs_bootstrap = (
        len(distinct_minutes) < MIN_FULL_MINUTES
        or vol_prev <= 0
        or prev_minutes < MIN_BOOTSTRAP_PREV_MINUTES
    )
    if needs_bootstrap:
        if len(prev_minute_vols) >= MIN_BOOTSTRAP_PREV_MINUTES:
            baseline_per_min = float(median(prev_minute_vols))
            vol_prev_bootstrap = baseline_per_min * 60.0
            if vol_prev_bootstrap > 0:
                vol_prev = vol_prev_bootstrap
                pct = ((vol_now - vol_prev) / vol_prev) * 100.0
                baseline_mode = "bootstrap"
                baseline_minutes = len(prev_minute_vols)
        else:
            return None

    return {
        "product_id": product_id,
        "symbol": _symbol_from_product(product_id),
        "volume_1h_now": vol_now,
        "volume_1h_prev": vol_prev,
        "volume_change_1h_pct": pct,
        "baseline_ready": True,
        "baseline_mode": baseline_mode,
        "baseline_minutes": baseline_minutes,
        "window_minutes": len(distinct_minutes),
        "minutes_now": now_minutes,
        "minutes_prev": prev_minutes,
    }
