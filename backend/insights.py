import logging
from sentiment_data_sources import fetch_fear_and_greed_index, fetch_coingecko_social, COINGECKO_ID_MAP

log = logging.getLogger(__name__)


def pct_change(cur, prev):
    try:
        if prev is None or prev == 0:
            return None
        return (float(cur) - float(prev)) / float(prev) * 100.0
    except Exception:
        return None


def build_asset_insights(symbol: str, current_price: float, snapshots: dict, coingecko_id_map: dict = COINGECKO_ID_MAP, fear_greed: dict | None = None):
    """
    Build a consistent insights payload for the frontend.
    snapshots expected keys: price_1m_ago, price_3m_ago, volume_1h_now, volume_1h_prev
    """
    price_1m = snapshots.get("price_1m_ago")
    price_3m = snapshots.get("price_3m_ago")
    vol_1h_now = snapshots.get("volume_1h_now")
    vol_1h_prev = snapshots.get("volume_1h_prev")

    change_1m = pct_change(current_price, price_1m)
    change_3m = pct_change(current_price, price_3m)
    vol_change_1h = pct_change(vol_1h_now, vol_1h_prev)

    heat_score = 50.0
    if change_3m is not None:
        heat_score += max(min(change_3m, 20.0), -20.0)
    if vol_change_1h is not None:
        heat_score += max(min(vol_change_1h / 5.0, 15.0), -15.0)
    heat_score = max(0.0, min(100.0, heat_score))

    trend_label = "FLAT"
    if change_3m is not None:
        if change_3m > 0.5:
            trend_label = "UP"
        elif change_3m < -0.5:
            trend_label = "DOWN"

    base_symbol = symbol.split("-")[0]
    cg_id = coingecko_id_map.get(base_symbol.upper()) if coingecko_id_map else None
    social = fetch_coingecko_social(cg_id) if cg_id else None

    fg = fear_greed or fetch_fear_and_greed_index()

    return {
        "symbol": symbol,
        "price": current_price,
        "change_1m": change_1m,
        "change_3m": change_3m,
        "volume_change_1h": vol_change_1h,
        "heat_score": heat_score,
        "trend": trend_label,
        "social": social,
        "market_sentiment": fg,
        "sources": {
            "price_volume": "coinbase_snapshots",
            "social": "coingecko" if social else "derived",
            "macro": "alternative.me" if fg else "none",
        },
    }
