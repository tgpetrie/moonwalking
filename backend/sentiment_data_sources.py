import logging
import requests

log = logging.getLogger(__name__)

FNG_URL = "https://api.alternative.me/fng/"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Minimal map - extend as needed or import your existing map elsewhere
COINGECKO_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
}


def fetch_fear_and_greed_index():
    """
    Returns a dict with keys: value (int 0-100), classification (str), timestamp (int|None), source
    or None on failure.
    """
    try:
        resp = requests.get(FNG_URL, timeout=5)
        resp.raise_for_status()
        payload = resp.json() or {}
        data_list = payload.get("data") or []
        if not data_list:
            return None
        data = data_list[0]

        value_raw = data.get("value")
        value = int(value_raw) if value_raw is not None else None
        classification = data.get("value_classification")
        ts_raw = data.get("timestamp")
        ts = int(ts_raw) if ts_raw is not None else None

        if value is None:
            return None

        return {
            "value": value,
            "classification": classification,
            "timestamp": ts,
            "source": "alternative.me",
        }
    except Exception as e:
        log.warning("Failed to fetch Fear & Greed index: %s", e)
        return None


def fetch_coingecko_social(coin_id: str):
    """
    Fetch per-asset community + sentiment data from CoinGecko.

    Returns a dict with keys: coin_id, sentiment_votes_up_percentage, reddit_subscribers,
    reddit_posts_48h, reddit_comments_48h; or None on failure.
    """
    if not coin_id:
        return None

    url = f"{COINGECKO_BASE}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "true",
        "developer_data": "false",
        "sparkline": "false",
    }

    try:
        resp = requests.get(url, params=params, timeout=7)
        resp.raise_for_status()
        data = resp.json() or {}

        community = data.get("community_data") or {}
        sentiment_up = data.get("sentiment_votes_up_percentage")

        return {
            "coin_id": coin_id,
            "sentiment_votes_up_percentage": sentiment_up,
            "reddit_subscribers": community.get("reddit_subscribers"),
            "reddit_posts_48h": community.get("reddit_average_posts_48h"),
            "reddit_comments_48h": community.get("reddit_average_comments_48h"),
        }
    except Exception as e:
        log.warning("Failed to fetch CoinGecko community data for %s: %s", coin_id, e)
        return None
