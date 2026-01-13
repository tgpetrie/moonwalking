# sentiment_source_mapper.py
"""
Maps your actual sentiment pipeline data to SourceValue format
for compute_final_sentiment.py
"""

from compute_final_sentiment import SourceValue, compute_final_sentiment
from typing import Dict, List, Any, Optional
import time


def map_pipeline_to_sources(sentiment_data: Dict[str, Any]) -> List[SourceValue]:
    """
    Takes output from /sentiment/latest and maps to SourceValue list.

    Your pipeline outputs:
    {
        'overall_sentiment': 0.35,
        'fear_greed_index': 71,
        'social_breakdown': {
            'reddit': 0.79,
            'twitter': 0.78,
            'telegram': 0.77,
            'chan': 0.42
        },
        'source_breakdown': {
            'tier1': 3,
            'tier2': 3,
            'tier3': 3,
            'fringe': 2
        }
    }
    """
    sources: List[SourceValue] = []
    now = time.time()

    # Parse timestamp if available
    ts_str = sentiment_data.get('timestamp')
    if ts_str:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            asof = dt.timestamp()
        except:
            asof = now
    else:
        asof = now

    # 1. Fear & Greed Index (0-100 -> normalize to 0-1 unsigned)
    fg_value = sentiment_data.get('fear_greed_index')
    if fg_value is not None:
        sources.append(SourceValue(
            name="fear_greed",
            ok=True,
            value=float(fg_value) / 100.0,  # 0-100 -> 0-1
            asof_ts=asof,
            weight=1.2,  # High importance
            kind="unsigned",
            meta={"raw_value": fg_value}
        ))

    # 2. Overall sentiment (treat as composite news/social blend)
    overall = sentiment_data.get('overall_sentiment')
    if overall is not None:
        sources.append(SourceValue(
            name="social",
            ok=True,
            value=(float(overall) - 0.5) * 2,  # 0-1 -> -1 to +1 signed
            asof_ts=asof,
            weight=0.9,
            kind="signed",
            meta={"source": "overall_composite"}
        ))

    # 3. Social breakdown - individual platforms
    social = sentiment_data.get('social_breakdown', {})

    # Reddit (tier2-ish, mainstream)
    if social.get('reddit') is not None:
        sources.append(SourceValue(
            name="social",
            ok=True,
            value=(float(social['reddit']) - 0.5) * 2,
            asof_ts=asof,
            weight=0.75,
            kind="signed",
            meta={"platform": "reddit", "tier": "tier2"}
        ))

    # Twitter (varies by source quality)
    if social.get('twitter') is not None:
        sources.append(SourceValue(
            name="social",
            ok=True,
            value=(float(social['twitter']) - 0.5) * 2,
            asof_ts=asof,
            weight=0.70,
            kind="signed",
            meta={"platform": "twitter"}
        ))

    # Telegram (tier3, alpha feeds)
    if social.get('telegram') is not None:
        sources.append(SourceValue(
            name="social",
            ok=True,
            value=(float(social['telegram']) - 0.5) * 2,
            asof_ts=asof,
            weight=0.60,
            kind="signed",
            meta={"platform": "telegram", "tier": "tier3"}
        ))

    # 4chan (fringe, lower weight but still informative)
    if social.get('chan') is not None:
        sources.append(SourceValue(
            name="social",
            ok=True,
            value=(float(social['chan']) - 0.5) * 2,
            asof_ts=asof,
            weight=0.45,
            kind="signed",
            meta={"platform": "4chan", "tier": "fringe"}
        ))

    return sources


def map_market_features(symbol: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps your price/candle data to market_features format.

    Expects price_data like:
    {
        'price': 42500.0,
        'change_1m': 0.5,   # percent
        'change_3m': 1.2,
        'change_15m': 2.1,
        'change_1h': 3.5,
        'volume_24h': 1500000000,
        'volume_avg': 1200000000,
        'volatility': 0.03,
        'timestamp': 1705180800,
        'streak': 3  # consecutive positive 1m closes
    }
    """
    now = time.time()

    # Volume z-score approximation
    vol_24h = price_data.get('volume_24h', 0)
    vol_avg = price_data.get('volume_avg', vol_24h)
    vol_z = ((vol_24h / vol_avg) - 1) * 2 if vol_avg > 0 else 0

    # Breakout indicator: if 15m change > 3%, consider it a breakout
    change_15m = price_data.get('change_15m', 0)
    breakout = 1.0 if abs(change_15m) > 3.0 else 0.0

    return {
        "mom_1m": price_data.get('change_1m', 0),
        "mom_3m": price_data.get('change_3m', 0),
        "mom_15m": change_15m,
        "mom_1h": price_data.get('change_1h', 0),
        "vol_z_1h": vol_z,
        "rv_15m": price_data.get('volatility', 0.02),
        "breakout_15m": breakout,
        "streak_1m": price_data.get('streak', 0),
        "asof_ts": price_data.get('timestamp', now)
    }


def compute_token_sentiment(
    symbol: str,
    sentiment_data: Dict[str, Any],
    price_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Full integration: computes final sentiment for a token.

    Args:
        symbol: Token symbol (BTC, ETH, etc.)
        sentiment_data: From /sentiment/latest
        price_data: From price feed

    Returns:
        compute_final_sentiment output with score, tier, confidence
    """
    # Map sources
    sources = map_pipeline_to_sources(sentiment_data)

    # Map market features
    market_features = map_market_features(symbol, price_data)

    # Compute final sentiment
    result = compute_final_sentiment(
        symbol=symbol,
        market_features=market_features,
        sources=sources
    )

    return result


def tier_to_severity(tier: str, confidence: float) -> str:
    """
    Convert tier + confidence to alert severity.

    Maps:
    - extreme tier + confidence > 0.75 → CRITICAL
    - strong tier + confidence > 0.65 → HIGH
    - moderate tier + confidence > 0.50 → MEDIUM
    - watch tier or lower confidence → INFO
    """
    if tier == "extreme" and confidence > 0.75:
        return "CRITICAL"
    elif tier == "strong" and confidence > 0.65:
        return "HIGH"
    elif tier == "moderate" and confidence > 0.50:
        return "MEDIUM"
    else:
        return "INFO"
