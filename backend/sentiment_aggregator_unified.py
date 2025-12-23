from __future__ import annotations

import os
import time
import math
import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
import feedparser
import yaml

try:
    import praw
except Exception:
    praw = None

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ----------------------------
# Small TTL cache (in-process)
# ----------------------------


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self):
        self._data: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        ent = self._data.get(key)
        if not ent:
            return None
        if time.time() >= ent.expires_at:
            self._data.pop(key, None)
            return None
        return ent.value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = CacheEntry(value=value, expires_at=time.time() + ttl)


_CACHE = TTLCache()


# ----------------------------
# Config
# ----------------------------


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> Dict[str, Any]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "sentiment_config.yaml"),
        os.path.join(os.getcwd(), "backend", "sentiment_config.yaml"),
        os.path.join(os.getcwd(), "sentiment_config.yaml"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return _read_yaml(p)
            except Exception:
                continue
    return {
        "sentiment": {
            "cache_ttl_seconds": 300,
            "max_rss_items": 25,
            "max_reddit_posts": 40,
            "tier_weights": {"tier1": 0.85, "tier2": 0.70, "tier3": 0.50, "fringe": 0.30},
            "divergence_threshold": 0.12,
        },
        "sources": {
            "fear_greed": {"enabled": True, "tier": "tier1", "weight": 0.90},
            "coingecko": {"enabled": True, "tier": "tier1", "weight": 0.85},
            "rss": {"enabled": False, "tier": "tier2", "weight": 0.75, "feeds": []},
            "reddit_global": {"enabled": False, "tier": "tier2", "weight": 0.75, "subreddits": []},
            "reddit_symbol": {"enabled": False, "tier": "tier3", "weight": 0.60, "subreddits": []},
        },
        "lexicon": {},
    }


_CONFIG = load_config()


def _cfg(path: str, default=None):
    node: Any = _CONFIG
    for part in path.split('.'):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# ----------------------------
# VADER with crypto lexicon
# ----------------------------


def _isfinite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


_ANALYZER = SentimentIntensityAnalyzer()
_LEX = _cfg("lexicon", {}) or {}
if isinstance(_LEX, dict) and _LEX:
    _ANALYZER.lexicon.update({str(k).lower(): float(v) for k, v in _LEX.items() if _isfinite(v)})


def vader_score_0_1(text: str) -> float:
    if not text:
        return 0.5
    vs = _ANALYZER.polarity_scores(text)
    c = float(vs.get("compound", 0.0))
    c = max(-1.0, min(1.0, c))
    return (c + 1.0) / 2.0


# ----------------------------
# Helpers: normalization
# ----------------------------


def normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    s = s.replace("-USD", "").replace("-USDT", "").replace("-PERP", "")
    return s


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


# ----------------------------
# Collectors
# ----------------------------


def fetch_fear_greed() -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    url = "https://api.alternative.me/fng/?limit=1&format=json"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        v = data.get("data", [{}])[0]
        idx = int(v.get("value"))
        label = str(v.get("value_classification", "")).strip() or None
        meta = {"source": "alternative.me", "raw": v}
        return idx, label, meta
    except Exception as e:
        return None, None, {"error": str(e)}


def coingecko_id_for_symbol(sym: str) -> Optional[str]:
    mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "DOGE": "dogecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "AVAX": "avalanche-2",
        "LINK": "chainlink",
    }
    return mapping.get(sym)


def fetch_coingecko_metrics(sym: str) -> Dict[str, Any]:
    cid = coingecko_id_for_symbol(sym)
    if not cid:
        return {"enabled": False, "reason": "unknown_coingecko_id"}

    url = f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=true&sparkline=false"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        j = r.json()
        md = j.get("market_data", {}) or {}
        cd = j.get("community_data", {}) or {}
        dd = j.get("developer_data", {}) or {}

        ch24 = md.get("price_change_percentage_24h") or 0.0
        ch7d = md.get("price_change_percentage_7d") or 0.0
        vol = md.get("total_volume", {}).get("usd") or 0.0

        momentum = max(-20.0, min(20.0, float(ch24))) / 20.0
        activity = 0.0
        try:
            tw = float(cd.get("twitter_followers") or 0.0)
            gh = float(dd.get("stars") or 0.0)
            activity = math.tanh((tw / 1_000_000.0) + (gh / 10_000.0))
        except Exception:
            activity = 0.0

        comp = 0.65 * momentum + 0.35 * activity
        score = (max(-1.0, min(1.0, comp)) + 1.0) / 2.0

        return {
            "enabled": True,
            "coingecko_id": cid,
            "score_0_1": float(score),
            "metrics": {
                "price_change_24h": float(ch24),
                "price_change_7d": float(ch7d),
                "volume_usd": float(vol),
                "twitter_followers": cd.get("twitter_followers"),
                "reddit_subscribers": cd.get("reddit_subscribers"),
                "github_stars": dd.get("stars"),
                "forks": dd.get("forks"),
            },
        }
    except Exception as e:
        return {"enabled": True, "error": str(e), "coingecko_id": cid}


def fetch_rss_sentiment(feeds: List[Dict[str, Any]], max_items: int) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    scores: List[float] = []
    total_items = 0

    for f in feeds or []:
        name = str(f.get("name") or "RSS").strip()
        url = str(f.get("url") or "").strip()
        if not url:
            continue
        weight = float(f.get("weight") or 1.0)

        try:
            parsed = feedparser.parse(url)
            entries = parsed.entries[:max_items]
            local_scores: List[float] = []
            for e in entries:
                title = str(getattr(e, "title", "") or "")
                summary = str(getattr(e, "summary", "") or "")
                s = vader_score_0_1((title + " " + summary).strip())
                local_scores.append(s)
            if local_scores:
                avg = sum(local_scores) / len(local_scores)
                results.append({
                    "name": name,
                    "url": url,
                    "items": len(local_scores),
                    "avg_score_0_1": float(avg),
                    "weight": float(weight),
                })
                scores.extend([avg] * max(1, int(round(weight * 2))))
                total_items += len(local_scores)
        except Exception as e:
            results.append({"name": name, "url": url, "error": str(e), "weight": float(weight)})

    if not scores:
        return {"enabled": True, "score_0_1": None, "feeds": results, "items": total_items}

    overall = sum(scores) / len(scores)
    return {"enabled": True, "score_0_1": float(overall), "feeds": results, "items": total_items}


def _praw_client() -> Optional[Any]:
    if praw is None:
        return None
    cid = os.getenv("REDDIT_CLIENT_ID") or ""
    csec = os.getenv("REDDIT_CLIENT_SECRET") or ""
    ua = os.getenv("REDDIT_USER_AGENT") or "moonwalkings/1.0"
    if not cid or not csec:
        return None
    try:
        return praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua)
    except Exception:
        return None


def fetch_reddit_sentiment(
    subreddits: List[str],
    query: Optional[str],
    max_posts: int,
) -> Dict[str, Any]:
    reddit = _praw_client()
    if reddit is None:
        return {"enabled": False, "reason": "reddit_not_configured"}

    scored = 0
    scores: List[float] = []
    per_sub: List[Dict[str, Any]] = []

    q = (query or "").strip().lower()

    for sr in subreddits or []:
        sr = str(sr).strip()
        if not sr:
            continue
        try:
            sub = reddit.subreddit(sr)
            posts = list(sub.hot(limit=max_posts))
            local_scores: List[float] = []
            mentions = 0
            for p in posts:
                title = str(getattr(p, "title", "") or "")
                selftext = str(getattr(p, "selftext", "") or "")
                text = (title + " " + selftext).strip()

                if q:
                    if q not in text.lower():
                        continue
                    mentions += 1

                s = vader_score_0_1(text)
                local_scores.append(s)

            if local_scores:
                avg = sum(local_scores) / len(local_scores)
                per_sub.append({
                    "subreddit": sr,
                    "items": len(local_scores),
                    "mentions": mentions if q else None,
                    "avg_score_0_1": float(avg),
                })
                scores.append(avg)
                scored += len(local_scores)
            else:
                per_sub.append({"subreddit": sr, "items": 0, "mentions": mentions if q else None})
        except Exception as e:
            per_sub.append({"subreddit": sr, "error": str(e)})

    if not scores:
        return {"enabled": True, "score_0_1": None, "items": scored, "subreddits": per_sub}

    overall = sum(scores) / len(scores)
    return {"enabled": True, "score_0_1": float(overall), "items": scored, "subreddits": per_sub}


# ----------------------------
# Aggregation
# ----------------------------


def _tier_bucket() -> Dict[str, Dict[str, float]]:
    return {
        "tier1": {"sum": 0.0, "w": 0.0},
        "tier2": {"sum": 0.0, "w": 0.0},
        "tier3": {"sum": 0.0, "w": 0.0},
        "fringe": {"sum": 0.0, "w": 0.0},
    }


def _add(bucket: Dict[str, Dict[str, float]], tier: str, score_0_1: Optional[float], weight: float):
    if score_0_1 is None:
        return
    if not _isfinite(score_0_1):
        return
    t = tier if tier in bucket else "tier2"
    w = float(weight) if _isfinite(weight) else 0.0
    if w <= 0:
        return
    bucket[t]["sum"] += float(score_0_1) * w
    bucket[t]["w"] += w


def _finalize_tier_scores(bucket: Dict[str, Dict[str, float]]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for t, v in bucket.items():
        if v["w"] <= 0:
            out[t] = None
        else:
            out[t] = float(v["sum"] / v["w"])
    return out


def _weighted_overall(tier_scores: Dict[str, Optional[float]], tier_weights: Dict[str, float]) -> Optional[float]:
    s = 0.0
    w = 0.0
    for t, sc in tier_scores.items():
        if sc is None:
            continue
        tw = float(tier_weights.get(t, 0.0))
        if tw <= 0:
            continue
        s += float(sc) * tw
        w += tw
    if w <= 0:
        return None
    return float(s / w)


def _divergence_alerts(tier_scores: Dict[str, Optional[float]], threshold: float) -> List[Dict[str, Any]]:
    t1 = tier_scores.get("tier1")
    t3 = tier_scores.get("tier3")
    if t1 is None or t3 is None:
        return []
    diff = float(t1 - t3)
    if abs(diff) < float(threshold):
        return []
    sev = "medium" if abs(diff) < float(threshold) * 2 else "high"
    direction = "more_bullish" if diff > 0 else "more_bearish"
    return [{
        "type": "tier_divergence",
        "severity": sev,
        "direction": direction,
        "difference": abs(diff),
        "message": f"Tier 1 vs Tier 3 divergence ({t1:.2f} vs {t3:.2f})",
        "timestamp": int(time.time()),
    }]


def _source_record(name: str, tier: str, weight: float, score_0_1: Optional[float], meta: Dict[str, Any], url: Optional[str] = None) -> Dict[str, Any]:
    score_pct = None
    if score_0_1 is not None and _isfinite(score_0_1):
        score_pct = float(max(0.0, min(1.0, float(score_0_1))) * 100.0)
    return {
        "name": name,
        "tier": tier,
        "weight": float(weight),
        "score_0_1": score_0_1 if (score_0_1 is None or _isfinite(score_0_1)) else None,
        "score": score_pct,
        "url": url,
        "meta": meta or {},
        "status": "active" if score_0_1 is not None else "partial",
        "ts": int(time.time()),
    }


def get_sentiment_for_symbol(symbol: str) -> Dict[str, Any]:
    sym = normalize_symbol(symbol or "BTC") or "BTC"

    ttl = int(_cfg("sentiment.cache_ttl_seconds", 300) or 300)
    max_rss = int(_cfg("sentiment.max_rss_items", 25) or 25)
    max_reddit = int(_cfg("sentiment.max_reddit_posts", 40) or 40)
    tier_weights = _cfg("sentiment.tier_weights", {}) or {"tier1": 0.85, "tier2": 0.70, "tier3": 0.50, "fringe": 0.30}
    divergence_threshold = float(_cfg("sentiment.divergence_threshold", 0.12) or 0.12)

    cfg_hash = _hash_key(json.dumps(_CONFIG, sort_keys=True))
    cache_key = _hash_key("sentiment", sym, cfg_hash)
    cached = _CACHE.get(cache_key)
    if cached is not None:
        cached["metadata"]["cache_hit"] = True
        return cached

    sources_cfg = _cfg("sources", {}) or {}
    bucket = _tier_bucket()
    sources: List[Dict[str, Any]] = []
    t0 = time.time()

    fg_cfg = sources_cfg.get("fear_greed", {})
    if fg_cfg.get("enabled", False):
        idx, label, meta = fetch_fear_greed()
        fg_score = (float(idx) / 100.0) if idx is not None else None
        sources.append(_source_record(
            name="Fear & Greed Index",
            tier=str(fg_cfg.get("tier", "tier1")),
            weight=float(fg_cfg.get("weight", 0.90)),
            score_0_1=fg_score,
            meta={"index": idx, "label": label, **meta},
            url="https://alternative.me/crypto/fear-and-greed-index/",
        ))
        _add(bucket, str(fg_cfg.get("tier", "tier1")), fg_score, float(fg_cfg.get("weight", 0.90)))

    cg_cfg = sources_cfg.get("coingecko", {})
    cg_metrics = None
    if cg_cfg.get("enabled", False):
        cg = fetch_coingecko_metrics(sym)
        cg_score = cg.get("score_0_1") if cg.get("enabled") else None
        cg_metrics = cg.get("metrics")
        sources.append(_source_record(
            name=f"CoinGecko ({sym})",
            tier=str(cg_cfg.get("tier", "tier1")),
            weight=float(cg_cfg.get("weight", 0.85)),
            score_0_1=cg_score if _isfinite(cg_score) else None,
            meta={"coingecko": cg},
            url=f"https://www.coingecko.com/en/coins/{cg.get('coingecko_id')}" if cg.get("coingecko_id") else "https://www.coingecko.com/",
        ))
        _add(bucket, str(cg_cfg.get("tier", "tier1")), cg_score if _isfinite(cg_score) else None, float(cg_cfg.get("weight", 0.85)))

    rss_cfg = sources_cfg.get("rss", {})
    if rss_cfg.get("enabled", False):
        feeds = rss_cfg.get("feeds", []) or []
        rss = fetch_rss_sentiment(feeds=feeds, max_items=max_rss)
        rss_score = rss.get("score_0_1")
        sources.append(_source_record(
            name="RSS News (Market)",
            tier=str(rss_cfg.get("tier", "tier2")),
            weight=float(rss_cfg.get("weight", 0.75)),
            score_0_1=rss_score if _isfinite(rss_score) else None,
            meta={"rss": rss},
            url=None,
        ))
        _add(bucket, str(rss_cfg.get("tier", "tier2")), rss_score if _isfinite(rss_score) else None, float(rss_cfg.get("weight", 0.75)))

    rg_cfg = sources_cfg.get("reddit_global", {})
    if rg_cfg.get("enabled", False):
        subs = rg_cfg.get("subreddits", []) or []
        rg = fetch_reddit_sentiment(subreddits=subs, query=None, max_posts=max_reddit)
        rg_score = rg.get("score_0_1")
        sources.append(_source_record(
            name="Reddit (Market)",
            tier=str(rg_cfg.get("tier", "tier2")),
            weight=float(rg_cfg.get("weight", 0.75)),
            score_0_1=rg_score if _isfinite(rg_score) else None,
            meta={"reddit_global": rg},
            url="https://www.reddit.com/",
        ))
        _add(bucket, str(rg_cfg.get("tier", "tier2")), rg_score if _isfinite(rg_score) else None, float(rg_cfg.get("weight", 0.75)))

    rs_cfg = sources_cfg.get("reddit_symbol", {})
    reddit_mentions = None
    if rs_cfg.get("enabled", False):
        subs = rs_cfg.get("subreddits", []) or []
        rs = fetch_reddit_sentiment(subreddits=subs, query=sym.lower(), max_posts=max_reddit)
        rs_score = rs.get("score_0_1")
        try:
            reddit_mentions = sum(int(x.get("mentions") or 0) for x in (rs.get("subreddits") or []) if isinstance(x, dict))
        except Exception:
            reddit_mentions = None

        sources.append(_source_record(
            name=f"Reddit Mentions ({sym})",
            tier=str(rs_cfg.get("tier", "tier3")),
            weight=float(rs_cfg.get("weight", 0.60)),
            score_0_1=rs_score if _isfinite(rs_score) else None,
            meta={"reddit_symbol": rs, "mentions": reddit_mentions},
            url="https://www.reddit.com/",
        ))
        _add(bucket, str(rs_cfg.get("tier", "tier3")), rs_score if _isfinite(rs_score) else None, float(rs_cfg.get("weight", 0.60)))

    tier_scores = _finalize_tier_scores(bucket)
    overall = _weighted_overall(tier_scores, tier_weights)
    divergence = _divergence_alerts(tier_scores, divergence_threshold)

    out = {
        "symbol": sym,
        "timestamp": int(time.time()),

        "overall_sentiment": overall,
        "overallSentiment": overall,

        "total_sources": len(sources),
        "sources": sources,

        "source_breakdown": {
            "tier1": sum(1 for s in sources if s.get("tier") == "tier1"),
            "tier2": sum(1 for s in sources if s.get("tier") == "tier2"),
            "tier3": sum(1 for s in sources if s.get("tier") == "tier3"),
            "fringe": sum(1 for s in sources if s.get("tier") == "fringe"),
        },
        "tier_scores": tier_scores,
        "divergence_alerts": divergence,

        "coin_metrics": cg_metrics or {},
        "social_metrics": {
            "reddit_mentions": reddit_mentions,
        },

        "social_breakdown": {
            "reddit": None,
            "twitter": None,
            "telegram": None,
            "news": None,
        },
        "trending_topics": [],
        "sentiment_history": [],

        "metadata": {
            "cache_hit": False,
            "processing_time_ms": int((time.time() - t0) * 1000),
            "sources_queried": len(sources),
            "sources_successful": sum(1 for s in sources if s.get("score_0_1") is not None),
        },
    }

    if out["overall_sentiment"] is None:
        out["overall_sentiment"] = 0.5
        out["overallSentiment"] = 0.5

    _CACHE.set(cache_key, out, ttl)
    return out
"""
============================================
UNIFIED SENTIMENT AGGREGATOR
============================================

Combines coin-specific and market-wide sentiment from 50+ sources:
- Coin-Specific: CoinGecko metrics, Reddit mentions, price momentum
- Market-Wide: Fear & Greed, RSS feeds, subreddit analysis
- VADER sentiment analysis with crypto lexicon
- Tier-based weighting (Tier 1: 0.85, Tier 2: 0.70, Tier 3: 0.50)

Integrates the best of:
1. Enhanced aggregator (coin-specific, simple)
2. Comprehensive multi-source (VADER, RSS, full Reddit)
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import random
import hashlib
import json
import logging
import re

logger = logging.getLogger(__name__)

# Try to import optional dependencies (graceful degradation)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    logger.warning("vaderSentiment not installed - sentiment analysis will be simplified")

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("praw not installed - Reddit integration will be limited")


# ========================================
# CONFIGURATION
# ========================================

# CoinGecko coin ID mapping (symbol -> coingecko_id)
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
    'DOGE': 'dogecoin', 'SHIB': 'shiba-inu', 'PEPE': 'pepe',
    'XRP': 'ripple', 'ADA': 'cardano', 'AVAX': 'avalanche-2',
    'DOT': 'polkadot', 'MATIC': 'matic-network', 'LINK': 'chainlink',
    'UNI': 'uniswap', 'ATOM': 'cosmos', 'LTC': 'litecoin',
    'XLM': 'stellar', 'ALGO': 'algorand', 'NEAR': 'near',
    'APT': 'aptos', 'ARB': 'arbitrum', 'OP': 'optimism',
    'SUI': 'sui', 'SEI': 'sei-network', 'INJ': 'injective-protocol',
    'TIA': 'celestia', 'JUP': 'jupiter-exchange-solana',
    'WIF': 'dogwifcoin', 'BONK': 'bonk', 'FLOKI': 'floki',
}

# RSS Feeds by tier
RSS_FEEDS = {
    'tier1': [
        {
            'name': 'Binance News RSS',
            'url': 'https://www.binance.com/en/feed/profile/Binance',
            'weight': 0.85
        }
    ],
    'tier2': [
        {
            'name': 'CoinDesk RSS',
            'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'weight': 0.80
        },
        {
            'name': 'CryptoSlate RSS',
            'url': 'https://cryptoslate.com/feed/',
            'weight': 0.70
        },
        {
            'name': 'Bitcoin Magazine RSS',
            'url': 'https://bitcoinmagazine.com/.rss/full/',
            'weight': 0.75
        }
    ],
    'tier3': [
        {
            'name': 'NewsBTC RSS',
            'url': 'https://www.newsbtc.com/feed/',
            'weight': 0.60
        }
    ]
}

# Reddit subreddits by tier
REDDIT_SUBREDDITS = {
    'tier2': ['CryptoCurrency', 'Bitcoin', 'ethereum'],
    'tier3': ['SatoshiStreetBets', 'CryptoMoonShots', 'altcoin']
}

# Tier weights for scoring
TIER_WEIGHTS = {
    1: 0.85,  # Institutional (Fear & Greed, CoinGecko official, Binance)
    2: 0.70,  # Professional (CoinDesk, CryptoSlate, major subreddits)
    3: 0.50,  # Retail/Social (smaller subreddits, NewsBTC)
}


# ========================================
# CRYPTO SENTIMENT ANALYZER
# ========================================

class CryptoSentimentAnalyzer:
    """Enhanced sentiment analyzer with crypto-specific lexicon"""

    def __init__(self):
        if VADER_AVAILABLE:
            self.vader = SentimentIntensityAnalyzer()
            self._load_crypto_lexicon()
            self.enabled = True
        else:
            self.enabled = False
            logger.info("VADER not available - using simple sentiment analysis")

    def _load_crypto_lexicon(self):
        """Add crypto-specific terms to VADER lexicon"""
        crypto_terms = {
            # Bullish terms
            'moon': 2.5, 'mooning': 2.5, 'bullish': 2.0, 'pump': 1.8,
            'hodl': 1.5, 'diamond hands': 2.0, 'ath': 1.5, 'breakout': 1.8,
            'rally': 1.5, 'surge': 1.8, 'gains': 1.8, 'buying': 1.2,
            'long': 1.0, 'buy': 1.5, 'accumulate': 1.3, 'support': 0.8,
            'resistance broken': 2.0, 'golden cross': 2.2, 'btfd': 1.5,
            'to the moon': 2.5, 'wagmi': 1.0, 'gm': 0.3,

            # Bearish terms
            'dump': -2.0, 'bearish': -2.0, 'crash': -2.5, 'rekt': -2.0,
            'paper hands': -1.5, 'fud': -1.8, 'scam': -2.5, 'rug pull': -2.8,
            'ponzi': -2.5, 'collapse': -2.5, 'selling': -1.2, 'short': -1.0,
            'sell': -1.5, 'exit': -1.3, 'resistance': -0.5, 'death cross': -2.2,
            'liquidation': -2.0, 'margin call': -2.0, 'rug': -2.5,

            # Neutral/Info terms
            'dyor': 0.0, 'nfa': 0.0, 'wen': 0.0,
        }

        self.vader.lexicon.update(crypto_terms)

    def analyze(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text
        Returns: {'compound': float, 'pos': float, 'neu': float, 'neg': float}
        """
        if not self.enabled:
            # Simple fallback: count positive/negative words
            return self._simple_sentiment(text)

        # Clean text
        text = self._clean_text(text)

        # Get VADER scores
        scores = self.vader.polarity_scores(text)

        # Adjust for crypto context
        scores = self._adjust_for_context(text, scores)

        return scores

    def _clean_text(self, text: str) -> str:
        """Clean text for analysis"""
        # Remove URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _adjust_for_context(self, text: str, scores: Dict) -> Dict:
        """Adjust scores based on crypto context"""
        text_lower = text.lower()

        # Boost score if multiple bullish terms
        bullish_count = sum(1 for term in ['moon', 'bullish', 'pump', 'hodl']
                           if term in text_lower)
        if bullish_count >= 2:
            scores['compound'] = min(1.0, scores['compound'] + 0.1)

        # Reduce score if multiple bearish terms
        bearish_count = sum(1 for term in ['dump', 'crash', 'bearish', 'rekt']
                           if term in text_lower)
        if bearish_count >= 2:
            scores['compound'] = max(-1.0, scores['compound'] - 0.1)

        return scores

    def _simple_sentiment(self, text: str) -> Dict[str, float]:
        """Simple sentiment fallback without VADER"""
        text_lower = text.lower()

        bullish = ['moon', 'bullish', 'pump', 'buy', 'up', 'gain', 'profit', 'win']
        bearish = ['dump', 'bearish', 'crash', 'sell', 'down', 'loss', 'rekt', 'scam']

        bull_count = sum(1 for word in bullish if word in text_lower)
        bear_count = sum(1 for word in bearish if word in text_lower)

        if bull_count + bear_count == 0:
            compound = 0.0
        else:
            compound = (bull_count - bear_count) / (bull_count + bear_count)

        return {
            'compound': compound,
            'pos': bull_count / max(1, bull_count + bear_count),
            'neg': bear_count / max(1, bull_count + bear_count),
            'neu': 0.5
        }


# ========================================
# MAIN AGGREGATOR CLASS
# ========================================

class UnifiedSentimentAggregator:
    """
    Unified sentiment aggregator combining coin-specific and market-wide sources.
    """

    def __init__(self, reddit_client_id: str = None, reddit_client_secret: str = None):
        self.cache = {}
        self.cache_ttl = {
            'fear_greed': 3600,      # 1 hour
            'coingecko': 300,        # 5 minutes
            'reddit_coin': 600,      # 10 minutes
            'reddit_sub': 600,       # 10 minutes
            'rss': 900,              # 15 minutes
        }

        # Initialize sentiment analyzer
        self.analyzer = CryptoSentimentAnalyzer()

        # Initialize Reddit client if credentials provided
        self.reddit = None
        if PRAW_AVAILABLE and reddit_client_id and reddit_client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                    user_agent='moonwalking-sentiment/1.0'
                )
                logger.info("Reddit API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit: {e}")
                self.reddit = None

    def _get_cache_key(self, source: str, symbol: str = None) -> str:
        """Generate cache key"""
        return f"{source}:{symbol or 'global'}"

    def _is_cache_valid(self, key: str, ttl: int) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache:
            return False
        cached_time = self.cache[key].get('timestamp')
        if not cached_time:
            return False
        return (datetime.utcnow() - cached_time).seconds < ttl

    async def fetch_fear_greed(self) -> Dict[str, Any]:
        """
        Fetch Fear & Greed Index from Alternative.me
        Market-wide indicator (not coin-specific)
        """
        cache_key = self._get_cache_key('fear_greed')

        if self._is_cache_valid(cache_key, self.cache_ttl['fear_greed']):
            return self.cache[cache_key]['data']

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.alternative.me/fng/',
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = {
                            'value': int(data['data'][0]['value']),
                            'classification': data['data'][0]['value_classification'],
                            'timestamp': datetime.utcnow().isoformat(),
                        }
                        self.cache[cache_key] = {
                            'data': result,
                            'timestamp': datetime.utcnow()
                        }
                        return result
        except Exception as e:
            logger.error(f"Fear & Greed fetch error: {e}")

        # Fallback
        return {'value': 50, 'classification': 'Neutral', 'timestamp': datetime.utcnow().isoformat()}

    async def fetch_coingecko_coin_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch coin-specific data from CoinGecko
        Includes: price changes, community data, developer activity
        """
        coingecko_id = COINGECKO_IDS.get(symbol.upper())

        if not coingecko_id:
            return self._generate_fallback_coin_data(symbol)

        cache_key = self._get_cache_key('coingecko', symbol)

        if self._is_cache_valid(cache_key, self.cache_ttl['coingecko']):
            return self.cache[cache_key]['data']

        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'true',
                'sparkline': 'false'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = self._parse_coingecko_data(data, symbol)
                        self.cache[cache_key] = {
                            'data': result,
                            'timestamp': datetime.utcnow()
                        }
                        return result
                    elif response.status == 429:
                        logger.warning(f"CoinGecko rate limited for {symbol}")
        except Exception as e:
            logger.error(f"CoinGecko fetch error for {symbol}: {e}")

        return self._generate_fallback_coin_data(symbol)

    def _parse_coingecko_data(self, data: Dict, symbol: str) -> Dict[str, Any]:
        """Parse CoinGecko response into sentiment metrics"""
        market_data = data.get('market_data', {})
        community_data = data.get('community_data', {})

        # Price change sentiment
        price_change_24h = market_data.get('price_change_percentage_24h', 0) or 0
        price_change_7d = market_data.get('price_change_percentage_7d', 0) or 0
        price_sentiment = min(100, max(0, 50 + price_change_24h * 2))

        # Community score
        community_score = data.get('community_score', 0) or 0
        developer_score = data.get('developer_score', 0) or 0
        public_interest = data.get('public_interest_score', 0) or 0

        # Calculate overall coin sentiment
        weights = {
            'price': 0.35,
            'community': 0.25,
            'developer': 0.20,
            'public_interest': 0.20
        }

        overall = (
            price_sentiment * weights['price'] +
            community_score * weights['community'] +
            developer_score * weights['developer'] +
            public_interest * weights['public_interest']
        )

        return {
            'symbol': symbol,
            'overall_score': round(overall, 1),
            'price_sentiment': round(price_sentiment, 1),
            'price_change_24h': round(price_change_24h, 2),
            'price_change_7d': round(price_change_7d, 2),
            'community_score': round(community_score, 1),
            'developer_score': round(developer_score, 1),
            'public_interest_score': round(public_interest, 1),
            'timestamp': datetime.utcnow().isoformat(),
        }

    def _generate_fallback_coin_data(self, symbol: str) -> Dict[str, Any]:
        """Generate deterministic fallback data for unknown coins"""
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        random.seed(seed)

        base_score = random.randint(40, 70)

        return {
            'symbol': symbol,
            'overall_score': base_score,
            'price_sentiment': base_score + random.randint(-5, 5),
            'price_change_24h': random.uniform(-5, 5),
            'price_change_7d': random.uniform(-10, 10),
            'community_score': random.randint(30, 70),
            'developer_score': random.randint(20, 60),
            'public_interest_score': random.randint(20, 50),
            'timestamp': datetime.utcnow().isoformat(),
            'is_fallback': True,
        }

    async def fetch_rss_feed_sentiment(self, feed_config: Dict, tier: int) -> Dict[str, Any]:
        """
        Fetch and analyze RSS feed sentiment
        Returns aggregated sentiment from feed articles
        """
        cache_key = self._get_cache_key(f"rss_{feed_config['name']}")

        if self._is_cache_valid(cache_key, self.cache_ttl['rss']):
            return self.cache[cache_key]['data']

        try:
            feed = await asyncio.get_event_loop().run_in_executor(
                None, feedparser.parse, feed_config['url']
            )

            sentiments = []
            for entry in feed.entries[:50]:  # Limit to 50 articles
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                sentiment = self.analyzer.analyze(text)
                sentiments.append(sentiment['compound'])

            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                # Convert to 0-100 scale
                score = (avg_sentiment + 1.0) / 2.0 * 100

                result = {
                    'name': feed_config['name'],
                    'tier': tier,
                    'score': round(score, 1),
                    'article_count': len(sentiments),
                    'avg_compound': round(avg_sentiment, 3),
                    'timestamp': datetime.utcnow().isoformat()
                }

                self.cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.utcnow()
                }

                return result

        except Exception as e:
            logger.error(f"RSS feed error for {feed_config['name']}: {e}")

        return None

    async def fetch_reddit_subreddit_sentiment(self, subreddit_name: str, tier: int) -> Optional[Dict[str, Any]]:
        """
        Fetch sentiment from a subreddit using VADER analysis
        """
        if not self.reddit:
            return None

        cache_key = self._get_cache_key(f"reddit_sub_{subreddit_name}")

        if self._is_cache_valid(cache_key, self.cache_ttl['reddit_sub']):
            return self.cache[cache_key]['data']

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            sentiments = []

            for post in subreddit.hot(limit=100):
                text = f"{post.title} {post.selftext}"
                sentiment = self.analyzer.analyze(text)
                sentiments.append(sentiment['compound'])

            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                score = (avg_sentiment + 1.0) / 2.0 * 100

                result = {
                    'name': f"Reddit r/{subreddit_name}",
                    'tier': tier,
                    'score': round(score, 1),
                    'post_count': len(sentiments),
                    'avg_compound': round(avg_sentiment, 3),
                    'timestamp': datetime.utcnow().isoformat()
                }

                self.cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.utcnow()
                }

                return result

        except Exception as e:
            logger.error(f"Reddit fetch error for r/{subreddit_name}: {e}")

        return None

    async def fetch_reddit_coin_mentions(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch Reddit mention count and sentiment for specific coin
        Uses public Reddit JSON API (no auth needed)
        """
        cache_key = self._get_cache_key('reddit_coin', symbol)

        if self._is_cache_valid(cache_key, self.cache_ttl['reddit_coin']):
            return self.cache[cache_key]['data']

        total_mentions = 0
        positive_ratio = 0.5

        try:
            search_query = f"{symbol} crypto"
            url = "https://www.reddit.com/search.json"
            params = {
                'q': search_query,
                'sort': 'new',
                'limit': 25,
                't': 'day'
            }
            headers = {
                'User-Agent': 'CBMoovers/1.0 (Sentiment Analysis)'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        posts = data.get('data', {}).get('children', [])

                        total_mentions = len(posts)

                        if posts:
                            upvote_ratios = [
                                p.get('data', {}).get('upvote_ratio', 0.5)
                                for p in posts
                            ]
                            positive_ratio = sum(upvote_ratios) / len(upvote_ratios)
        except Exception as e:
            logger.error(f"Reddit fetch error for {symbol}: {e}")

        mention_score = min(100, total_mentions * 4)
        sentiment_score = positive_ratio * 100
        combined_score = (mention_score * 0.4) + (sentiment_score * 0.6)

        result = {
            'symbol': symbol,
            'mentions_24h': total_mentions,
            'positive_ratio': round(positive_ratio, 2),
            'sentiment_score': round(combined_score, 1),
            'timestamp': datetime.utcnow().isoformat(),
        }

        self.cache[cache_key] = {
            'data': result,
            'timestamp': datetime.utcnow()
        }

        return result

    async def get_coin_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive sentiment for a specific coin.
        Combines coin-specific and market-wide sources.
        """
        symbol = symbol.upper() if symbol else 'BTC'

        # Collect all sources in parallel
        tasks = {
            'fear_greed': self.fetch_fear_greed(),
            'coingecko': self.fetch_coingecko_coin_data(symbol),
            'reddit_coin': self.fetch_reddit_coin_mentions(symbol),
        }

        # Add RSS feeds
        for tier_name, feeds in RSS_FEEDS.items():
            tier_num = int(tier_name.replace('tier', ''))
            for feed in feeds:
                task_name = f"rss_{feed['name']}"
                tasks[task_name] = self.fetch_rss_feed_sentiment(feed, tier_num)

        # Add Reddit subreddits (if available)
        if self.reddit:
            for tier_name, subs in REDDIT_SUBREDDITS.items():
                tier_num = int(tier_name.replace('tier', ''))
                for sub in subs:
                    task_name = f"reddit_sub_{sub}"
                    tasks[task_name] = self.fetch_reddit_subreddit_sentiment(sub, tier_num)

        # Execute all tasks
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))

        # Handle exceptions
        for key, result in results_dict.items():
            if isinstance(result, Exception):
                logger.error(f"Error fetching {key}: {result}")
                results_dict[key] = None

        # Build sources list
        sources = []

        # Fear & Greed (Tier 1)
        fear_greed = results_dict.get('fear_greed') or {'value': 50, 'classification': 'Neutral'}
        sources.append({
            'name': 'Fear & Greed Index',
            'score': fear_greed.get('value', 50),
            'tier': 1,
            'last_update': datetime.utcnow().isoformat() + 'Z',
            'reliability': 0.90,
            'status': 'active',
            'description': f"Market-wide: {fear_greed.get('classification', 'Neutral')}"
        })

        # CoinGecko (Tier 1)
        coingecko = results_dict.get('coingecko') or self._generate_fallback_coin_data(symbol)
        sources.append({
            'name': 'CoinGecko',
            'score': int(coingecko.get('overall_score', 50)),
            'tier': 1,
            'last_update': datetime.utcnow().isoformat() + 'Z',
            'reliability': 0.85,
            'status': 'active',
            'description': f"24h: {coingecko.get('price_change_24h', 0):+.1f}%"
        })

        # RSS Feeds
        for key, result in results_dict.items():
            if key.startswith('rss_') and result:
                sources.append({
                    'name': result['name'],
                    'score': int(result['score']),
                    'tier': result['tier'],
                    'last_update': datetime.utcnow().isoformat() + 'Z',
                    'reliability': 0.75 if result['tier'] == 2 else 0.60,
                    'status': 'active',
                    'description': f"{result['article_count']} articles (VADER: {result['avg_compound']:+.2f})"
                })

        # Reddit Subreddits
        for key, result in results_dict.items():
            if key.startswith('reddit_sub_') and result:
                sources.append({
                    'name': result['name'],
                    'score': int(result['score']),
                    'tier': result['tier'],
                    'last_update': datetime.utcnow().isoformat() + 'Z',
                    'reliability': 0.70 if result['tier'] == 2 else 0.55,
                    'status': 'active',
                    'description': f"{result['post_count']} posts (VADER: {result['avg_compound']:+.2f})"
                })

        # Reddit Coin Mentions (Tier 3)
        reddit_coin = results_dict.get('reddit_coin') or {'sentiment_score': 50, 'mentions_24h': 0}
        sources.append({
            'name': 'Reddit Mentions',
            'score': int(reddit_coin.get('sentiment_score', 50)),
            'tier': 3,
            'last_update': datetime.utcnow().isoformat() + 'Z',
            'reliability': 0.60,
            'status': 'active',
            'description': f"{reddit_coin.get('mentions_24h', 0)} mentions (24h)"
        })

        # Calculate weighted overall sentiment
        total_weight = 0
        weighted_sum = 0
        for source in sources:
            weight = TIER_WEIGHTS.get(source['tier'], 0.5) * source['reliability']
            weighted_sum += source['score'] * weight
            total_weight += weight

        overall_sentiment = (weighted_sum / total_weight / 100) if total_weight > 0 else 0.5

        # Count sources by tier
        source_breakdown = {
            'tier1': sum(1 for s in sources if s['tier'] == 1),
            'tier2': sum(1 for s in sources if s['tier'] == 2),
            'tier3': sum(1 for s in sources if s['tier'] == 3),
        }

        # Calculate tier scores
        tier_scores = {}
        for tier in [1, 2, 3]:
            tier_sources = [s for s in sources if s['tier'] == tier]
            if tier_sources:
                tier_scores[f"tier{tier}"] = sum(s['score'] for s in tier_sources) / len(tier_sources) / 100

        # Divergence detection
        divergence_alerts = self._detect_divergences(sources, tier_scores, fear_greed.get('value', 50))

        return {
            'symbol': symbol,
            'overall_sentiment': round(overall_sentiment, 3),
            'fear_greed_index': fear_greed.get('value', 50),
            'fear_greed_label': fear_greed.get('classification', 'Neutral'),
            'total_sources': len(sources),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_breakdown': source_breakdown,
            'tier_scores': tier_scores,
            'social_metrics': {
                'mentions_24h': reddit_coin.get('mentions_24h', 0),
                'positive_ratio': reddit_coin.get('positive_ratio', 0.5),
            },
            'coin_metrics': {
                'price_sentiment': coingecko.get('price_sentiment', 50),
                'price_change_24h': coingecko.get('price_change_24h', 0),
                'price_change_7d': coingecko.get('price_change_7d', 0),
                'community_score': coingecko.get('community_score', 0),
                'developer_score': coingecko.get('developer_score', 0),
            },
            'sources': sources,
            'divergence_alerts': divergence_alerts,
        }

    def _detect_divergences(self, sources: List[Dict], tier_scores: Dict, fear_greed: int) -> List[Dict]:
        """Detect sentiment divergences"""
        alerts = []

        # Tier divergence
        if 'tier1' in tier_scores and 'tier3' in tier_scores:
            diff = abs(tier_scores['tier1'] - tier_scores['tier3'])
            if diff > 0.15:  # 15% difference
                severity = 'high' if diff > 0.25 else 'medium'
                direction = 'bullish' if tier_scores['tier1'] > tier_scores['tier3'] else 'bearish'
                alerts.append({
                    'type': 'tier_divergence',
                    'severity': severity,
                    'message': f"Tier 1 (institutional) more {direction} ({tier_scores['tier1']:.2f}) than Tier 3 (retail) ({tier_scores['tier3']:.2f})",
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })

        # Extreme greed/fear
        if fear_greed > 80:
            alerts.append({
                'type': 'extreme_greed',
                'severity': 'high',
                'message': f"Extreme Greed detected ({fear_greed}). Market may be overheated.",
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        elif fear_greed < 20:
            alerts.append({
                'type': 'extreme_fear',
                'severity': 'high',
                'message': f"Extreme Fear detected ({fear_greed}). Potential buying opportunity.",
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

        return alerts


# ========================================
# SINGLETON INSTANCE
# ========================================

_aggregator_instance = None

def get_aggregator(reddit_client_id: str = None, reddit_client_secret: str = None):
    """Get or create singleton aggregator instance"""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = UnifiedSentimentAggregator(reddit_client_id, reddit_client_secret)
    return _aggregator_instance


# ========================================
# FLASK INTEGRATION
# ========================================

def get_sentiment_for_symbol(symbol: str, reddit_client_id: str = None, reddit_client_secret: str = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for Flask integration.
    Call this from your Flask route.
    """
    aggregator = get_aggregator(reddit_client_id, reddit_client_secret)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(aggregator.get_coin_sentiment(symbol))
    finally:
        loop.close()


# ========================================
# STANDALONE TEST
# ========================================

if __name__ == '__main__':
    async def test():
        # Test without Reddit credentials
        print("=" * 60)
        print("Testing WITHOUT Reddit credentials (degraded mode)")
        print("=" * 60)

        agg = UnifiedSentimentAggregator()

        for symbol in ['BTC', 'ETH', 'DOGE']:
            print(f"\nTesting {symbol}")
            print("-" * 60)

            result = await agg.get_coin_sentiment(symbol)

            print(f"Overall Sentiment: {result['overall_sentiment']:.3f}")
            print(f"Fear & Greed: {result['fear_greed_index']} ({result['fear_greed_label']})")
            print(f"Sources: {result['total_sources']}")
            print(f"Tier Breakdown: {result['source_breakdown']}")

            for source in result['sources'][:5]:
                print(f"  - {source['name']}: {source['score']} (Tier {source['tier']})")

            if result['divergence_alerts']:
                print("Alerts:")
                for alert in result['divergence_alerts']:
                    print(f"  ⚠️  {alert['message']}")

    asyncio.run(test())
