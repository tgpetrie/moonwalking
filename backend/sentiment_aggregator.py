from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import aiohttp  # type: ignore
except Exception:
    aiohttp = None

import requests
try:
    import feedparser  # type: ignore
except Exception:
    feedparser = None
try:
    import yaml  # type: ignore
except Exception:
    yaml = None
try:
    import praw  # type: ignore
except Exception:
    praw = None
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ----------------------------
# Logging Configuration
# ----------------------------

# Configure structured logging for sentiment aggregator
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Set logging level from environment variable if provided
_log_level = os.getenv('SENTIMENT_LOG_LEVEL', 'INFO').upper()
if _log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
    logger.setLevel(getattr(logging, _log_level))


# ----------------------------
# TTL cache (in-process)
# ----------------------------

@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._data: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            ent = self._data.get(key)
            if not ent:
                logger.debug(f"Cache miss: {key}")
                return None
            if time.time() >= ent.expires_at:
                logger.debug(f"Cache expired: {key}")
                self._data.pop(key, None)
                return None
            logger.debug(f"Cache hit: {key}")
            return ent.value

    def set(self, key: str, value: Any, ttl: int) -> None:
        with self._lock:
            self._data[key] = CacheEntry(value=value, expires_at=time.time() + ttl)
            logger.debug(f"Cache set: {key} (TTL={ttl}s)")


_RESULT_CACHE = TTLCache()
_SOURCE_CACHE = TTLCache()


# ----------------------------
# Config loading
# ----------------------------


def _read_yaml(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed (missing dependency: PyYAML).")
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
                config = _read_yaml(p)
                logger.info(f"Loaded sentiment config from: {p}")
                return config
            except Exception as e:
                logger.warning(f"Failed to load config from {p}: {e}")
                continue

    logger.info("Using default sentiment configuration (no config file found)")
    return {
        "sentiment": {
            "cache_ttl_seconds": 300,
            "max_rss_items": 25,
            "max_reddit_posts": 40,
            "tier_weights": {"tier1": 0.85, "tier2": 0.70, "tier3": 0.50, "fringe": 0.30},
            "divergence_threshold": 0.12,
            "source_ttl_seconds": {
                "fear_greed": 3600,
                "coingecko": 300,
                "rss": 900,
                "reddit": 600,
            },
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
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


_SENTIMENT_CFG = _cfg("sentiment", {}) or {}


def _ttl_value(name: str, default: int) -> int:
    source_ttls = _SENTIMENT_CFG.get("source_ttl_seconds")
    if isinstance(source_ttls, dict) and name in source_ttls:
        try:
            return int(source_ttls[name])
        except Exception:
            pass
    cfg_key = _cfg(f"sentiment.{name}_ttl_seconds")
    if cfg_key is not None:
        try:
            return int(cfg_key)
        except Exception:
            pass
    fallback = _SENTIMENT_CFG.get("cache_ttl_seconds")
    if fallback is not None:
        try:
            return int(fallback)
        except Exception:
            pass
    return int(default)


RESULT_TTL = _ttl_value("cache", int(_SENTIMENT_CFG.get("cache_ttl_seconds", 300) or 300))
FG_TTL = _ttl_value("fear_greed", 3600)
CG_TTL = _ttl_value("coingecko", 300)
RSS_TTL = _ttl_value("rss", 900)
REDDIT_TTL = _ttl_value("reddit", 600)


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
    lex_update: Dict[str, float] = {}
    for k, v in _LEX.items():
        try:
            fv = float(v)
            if _isfinite(fv):
                lex_update[str(k).lower()] = fv
        except Exception as e:
            logger.debug(f"Skipping invalid lexicon entry {k}={v}: {e}")
            continue
    if lex_update:
        _ANALYZER.lexicon.update(lex_update)
        logger.info(f"Updated VADER lexicon with {len(lex_update)} crypto-specific terms")


def vader_score_0_1(text: str) -> float:
    if not text:
        return 0.5
    vs = _ANALYZER.polarity_scores(text)
    c = float(vs.get("compound", 0.0))
    c = max(-1.0, min(1.0, c))
    return (c + 1.0) / 2.0


# ----------------------------
# Symbol normalization + CoinGecko IDs
# ----------------------------


def normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    s = s.replace("-USD", "").replace("-USDT", "").replace("-PERP", "")
    return s or "BTC"


_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "PEPE": "pepe",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "XLM": "stellar",
    "ALGO": "algorand",
    "NEAR": "near",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "SUI": "sui",
    "SEI": "sei-network",
    "INJ": "injective-protocol",
    "TIA": "celestia",
    "JUP": "jupiter-exchange-solana",
    "WIF": "dogwifcoin",
    "BONK": "bonk",
    "FLOKI": "floki",
    "RENDER": "render-token",
    "FET": "fetch-ai",
    "RNDR": "render-token",
    "GRT": "the-graph",
    "FIL": "filecoin",
    "IMX": "immutable-x",
    "MKR": "maker",
    "AAVE": "aave",
    "CRV": "curve-dao-token",
    "SNX": "havven",
    "COMP": "compound-governance-token",
    "LDO": "lido-dao",
    "RPL": "rocket-pool",
    "XYO": "xyo-network",
    "JASMY": "jasmycoin",
    "VET": "vechain",
    "HBAR": "hedera-hashgraph",
    "QNT": "quant-network",
    "EGLD": "elrond-erd-2",
    "XTZ": "tezos",
    "EOS": "eos",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "ENJ": "enjincoin",
    "GALA": "gala",
    "CHZ": "chiliz",
    "MASK": "mask-network",
    "1INCH": "1inch",
    "SUSHI": "sushi",
    "YFI": "yearn-finance",
    "BAL": "balancer",
    "ZRX": "0x",
    "ENS": "ethereum-name-service",
    "APE": "apecoin",
    "BLUR": "blur",
    "MAGIC": "magic",
    "GMX": "gmx",
    "DYDX": "dydx",
    "STX": "blockstack",
    "MINA": "mina-protocol",
    "KAS": "kaspa",
    "CFX": "conflux-token",
    "ROSE": "oasis-network",
    "ZIL": "zilliqa",
    "ONE": "harmony",
    "KAVA": "kava",
    "CELO": "celo",
    "FLOW": "flow",
    "ICP": "internet-computer",
    "BNB": "binancecoin",
}


def coingecko_id_for_symbol(sym: str) -> Optional[str]:
    return _COINGECKO_IDS.get(sym)


# ----------------------------
# HTTP helpers (async-first)
# ----------------------------


async def _fetch_json_async(url: str, timeout_s: int = 10) -> Any:
    if aiohttp is None:
        raise RuntimeError("aiohttp not installed")
    t = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=t) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()


def _fetch_json_sync(url: str, timeout_s: int = 10) -> Any:
    r = requests.get(url, timeout=timeout_s)
    r.raise_for_status()
    return r.json()


async def fetch_json(url: str, timeout_s: int = 10) -> Any:
    if aiohttp is not None:
        return await _fetch_json_async(url, timeout_s=timeout_s)
    return _fetch_json_sync(url, timeout_s=timeout_s)


# ----------------------------
# Collectors
# ----------------------------


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


async def fetch_fear_greed() -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    cache_key = _hash_key("fg", "global")
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.alternative.me/fng/?limit=1&format=json"
    try:
        logger.debug("Fetching Fear & Greed Index from alternative.me")
        start_time = time.time()
        data = await fetch_json(url, timeout_s=8)
        elapsed = (time.time() - start_time) * 1000

        v = (data.get("data") or [{}])[0] or {}
        idx = int(v.get("value"))
        label = str(v.get("value_classification", "")).strip() or None
        meta = {"source": "alternative.me", "raw": v}
        result = (idx, label, meta)
        _SOURCE_CACHE.set(cache_key, result, FG_TTL)

        logger.info(f"Fear & Greed Index: {idx} ({label}) [fetched in {elapsed:.0f}ms]")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch Fear & Greed Index: {e}")
        result = (None, None, {"error": str(e)})
        _SOURCE_CACHE.set(cache_key, result, FG_TTL)
        return result


async def fetch_coingecko_metrics(sym: str) -> Dict[str, Any]:
    cid = coingecko_id_for_symbol(sym)
    cache_key = _hash_key("cg", sym)
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if not cid:
        logger.warning(f"Unknown CoinGecko ID for symbol: {sym}")
        result = {"enabled": False, "reason": "unknown_coingecko_id"}
        _SOURCE_CACHE.set(cache_key, result, CG_TTL)
        return result

    url = (
        f"https://api.coingecko.com/api/v3/coins/{cid}"
        "?localization=false&tickers=false&market_data=true&community_data=true&developer_data=true&sparkline=false"
    )
    try:
        logger.debug(f"Fetching CoinGecko metrics for {sym} (id={cid})")
        start_time = time.time()
        j = await fetch_json(url, timeout_s=10)
        elapsed = (time.time() - start_time) * 1000
        md = j.get("market_data", {}) or {}
        cd = j.get("community_data", {}) or {}
        dd = j.get("developer_data", {}) or {}

        ch24 = float(md.get("price_change_percentage_24h") or 0.0)
        ch7d = float(md.get("price_change_percentage_7d") or 0.0)
        vol = float((md.get("total_volume", {}) or {}).get("usd") or 0.0)

        momentum = max(-20.0, min(20.0, ch24)) / 20.0
        activity = 0.0
        try:
            tw = float(cd.get("twitter_followers") or 0.0)
            gh = float(dd.get("stars") or 0.0)
            activity = math.tanh((tw / 1_000_000.0) + (gh / 10_000.0))
        except Exception:
            activity = 0.0

        comp = 0.65 * momentum + 0.35 * activity
        score = (max(-1.0, min(1.0, comp)) + 1.0) / 2.0

        result = {
            "enabled": True,
            "coingecko_id": cid,
            "score_0_1": float(score),
            "metrics": {
                "price_change_24h": ch24,
                "price_change_7d": ch7d,
                "volume_usd": vol,
                "twitter_followers": cd.get("twitter_followers"),
                "reddit_subscribers": cd.get("reddit_subscribers"),
                "github_stars": dd.get("stars"),
                "forks": dd.get("forks"),
            },
        }
        _SOURCE_CACHE.set(cache_key, result, CG_TTL)
        logger.info(f"CoinGecko {sym}: score={score:.3f}, price_24h={ch24:.2f}% [fetched in {elapsed:.0f}ms]")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch CoinGecko metrics for {sym} (id={cid}): {e}")
        result = {"enabled": True, "error": str(e), "coingecko_id": cid}
        _SOURCE_CACHE.set(cache_key, result, CG_TTL)
        return result


def fetch_rss_sentiment(feeds: List[Dict[str, Any]], max_items: int) -> Dict[str, Any]:
    if feedparser is None:
        logger.warning("RSS feeds disabled: feedparser not installed")
        return {"enabled": False, "reason": "feedparser_not_installed"}

    cache_key = _hash_key("rss", json.dumps(feeds, sort_keys=True))
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    logger.debug(f"Fetching {len(feeds or [])} RSS feeds (max_items={max_items})")
    results: List[Dict[str, Any]] = []
    weighted_samples: List[float] = []
    total_items = 0

    for f in feeds or []:
        name = str(f.get("name") or "RSS").strip()
        url = str(f.get("url") or "").strip()
        if not url:
            continue
        weight = float(f.get("weight") or 1.0)

        try:
            parsed = feedparser.parse(url)
            entries = (parsed.entries or [])[:max_items]
            local_scores: List[float] = []

            for e in entries:
                title = str(getattr(e, "title", "") or "")
                summary = str(getattr(e, "summary", "") or "")
                s = vader_score_0_1((title + " " + summary).strip())
                local_scores.append(s)

            if local_scores:
                avg = sum(local_scores) / len(local_scores)
                results.append({"name": name, "url": url, "items": len(local_scores), "avg_score_0_1": float(avg), "weight": weight})
                rep = max(1, int(round(weight * 2)))
                weighted_samples.extend([avg] * rep)
                total_items += len(local_scores)
            else:
                results.append({"name": name, "url": url, "items": 0, "weight": weight})
                logger.debug(f"RSS feed {name} returned no items")
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {name} ({url}): {e}")
            results.append({"name": name, "url": url, "error": str(e), "weight": weight})

    if not weighted_samples:
        result = {"enabled": True, "score_0_1": None, "feeds": results, "items": total_items}
        _SOURCE_CACHE.set(cache_key, result, RSS_TTL)
        return result

    avg_score = float(sum(weighted_samples) / len(weighted_samples))
    result = {
        "enabled": True,
        "score_0_1": avg_score,
        "feeds": results,
        "items": total_items,
    }
    _SOURCE_CACHE.set(cache_key, result, RSS_TTL)
    logger.info(f"RSS sentiment: score={avg_score:.3f}, feeds={len(results)}, items={total_items}")
    return result


def _praw_client() -> Optional[Any]:
    if praw is None:
        return None
    cid = (os.getenv("REDDIT_CLIENT_ID") or "").strip()
    csec = (os.getenv("REDDIT_CLIENT_SECRET") or "").strip()
    ua = (os.getenv("REDDIT_USER_AGENT") or "moonwalkings/1.0").strip()
    if not cid or not csec:
        return None
    try:
        return praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua, check_for_async=False)
    except Exception:
        return None


def fetch_reddit_sentiment(subreddits: List[str], query: Optional[str], max_posts: int) -> Dict[str, Any]:
    cache_key = _hash_key("reddit", ",".join(subreddits or []), query or "")
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    reddit = _praw_client()
    if reddit is None:
        result = {"enabled": False, "reason": "reddit_not_configured"}
        _SOURCE_CACHE.set(cache_key, result, REDDIT_TTL)
        return result

    q = (query or "").strip().lower()
    per_sub: List[Dict[str, Any]] = []
    scores: List[float] = []
    scored = 0
    total_mentions = 0

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

                if q and q not in text.lower():
                    continue
                if q:
                    mentions += 1

                local_scores.append(vader_score_0_1(text))

            if local_scores:
                avg = sum(local_scores) / len(local_scores)
                per_sub.append({"subreddit": sr, "items": len(local_scores), "mentions": mentions if q else None, "avg_score_0_1": float(avg)})
                scores.append(avg)
                scored += len(local_scores)
                total_mentions += mentions
            else:
                per_sub.append({"subreddit": sr, "items": 0, "mentions": mentions if q else None})
        except Exception as e:
            per_sub.append({"subreddit": sr, "error": str(e)})

    if not scores:
        result = {"enabled": True, "score_0_1": None, "items": scored, "mentions": total_mentions if q else None, "subreddits": per_sub}
        _SOURCE_CACHE.set(cache_key, result, REDDIT_TTL)
        return result

    result = {
        "enabled": True,
        "score_0_1": float(sum(scores) / len(scores)),
        "items": scored,
        "mentions": total_mentions if q else None,
        "subreddits": per_sub,
    }
    _SOURCE_CACHE.set(cache_key, result, REDDIT_TTL)
    return result


# ----------------------------
# Aggregation helpers
# ----------------------------


def _tier_bucket() -> Dict[str, Dict[str, float]]:
    return {
        "tier1": {"sum": 0.0, "w": 0.0},
        "tier2": {"sum": 0.0, "w": 0.0},
        "tier3": {"sum": 0.0, "w": 0.0},
        "fringe": {"sum": 0.0, "w": 0.0},
    }


def _add(bucket: Dict[str, Dict[str, float]], tier: str, score_0_1: Optional[float], weight: float) -> None:
    if score_0_1 is None or not _isfinite(score_0_1):
        return
    w = float(weight) if _isfinite(weight) else 0.0
    if w <= 0:
        return
    t = tier if tier in bucket else "tier2"
    bucket[t]["sum"] += float(score_0_1) * w
    bucket[t]["w"] += w


def _finalize_tier_scores(bucket: Dict[str, Dict[str, float]]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for t, v in bucket.items():
        out[t] = None if v["w"] <= 0 else float(v["sum"] / v["w"])
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
    return None if w <= 0 else float(s / w)


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

    logger.warning(
        f"Divergence alert: Tier1={t1:.3f} vs Tier3={t3:.3f}, "
        f"diff={abs(diff):.3f} ({direction}, severity={sev})"
    )

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


# ----------------------------
# Core async computation
# ----------------------------


async def _compute_sentiment_async(symbol: str) -> Dict[str, Any]:
    sym = normalize_symbol(symbol)
    logger.info(f"Computing sentiment for {symbol} (normalized: {sym})")

    ttl = RESULT_TTL
    max_rss = int(_cfg("sentiment.max_rss_items", 25) or 25)
    max_reddit = int(_cfg("sentiment.max_reddit_posts", 40) or 40)
    tier_weights = _cfg("sentiment.tier_weights", {}) or {"tier1": 0.85, "tier2": 0.70, "tier3": 0.50, "fringe": 0.30}
    divergence_threshold = float(_cfg("sentiment.divergence_threshold", 0.12) or 0.12)

    cfg_hash = _hash_key(json.dumps(_CONFIG, sort_keys=True))
    cache_key = _hash_key("sentiment", sym, cfg_hash)
    cached = _RESULT_CACHE.get(cache_key)
    if cached is not None:
        logger.debug(f"Returning cached sentiment for {sym}")
        cached["metadata"]["cache_hit"] = True
        return cached

    logger.debug(f"Cache miss for {sym}, fetching from sources")
    sources_cfg = _cfg("sources", {}) or {}
    bucket = _tier_bucket()
    sources: List[Dict[str, Any]] = []
    t0 = time.time()

    fg_task = asyncio.create_task(fetch_fear_greed()) if sources_cfg.get("fear_greed", {}).get("enabled", False) else None
    cg_task = asyncio.create_task(fetch_coingecko_metrics(sym)) if sources_cfg.get("coingecko", {}).get("enabled", False) else None

    # Fear & Greed
    idx = label = None
    fg_meta: Dict[str, Any] = {}
    if fg_task:
        idx, label, fg_meta = await fg_task
        fg_score = (float(idx) / 100.0) if idx is not None else None
        fg_cfg = sources_cfg.get("fear_greed", {})
        sources.append(_source_record(
            name="Fear & Greed Index",
            tier=str(fg_cfg.get("tier", "tier1")),
            weight=float(fg_cfg.get("weight", 0.90)),
            score_0_1=fg_score,
            meta={"index": idx, "label": label, **fg_meta},
            url="https://alternative.me/crypto/fear-and-greed-index/",
        ))
        _add(bucket, str(fg_cfg.get("tier", "tier1")), fg_score, float(fg_cfg.get("weight", 0.90)))

    # CoinGecko
    cg_metrics: Dict[str, Any] = {}
    if cg_task:
        cg = await cg_task
        cg_score = cg.get("score_0_1") if cg.get("enabled") else None
        cg_metrics = cg.get("metrics") or {}
        cg_cfg = sources_cfg.get("coingecko", {})
        sources.append(_source_record(
            name=f"CoinGecko ({sym})",
            tier=str(cg_cfg.get("tier", "tier1")),
            weight=float(cg_cfg.get("weight", 0.85)),
            score_0_1=cg_score if _isfinite(cg_score) else None,
            meta={"coingecko": cg},
            url=f"https://www.coingecko.com/en/coins/{cg.get('coingecko_id')}" if cg.get("coingecko_id") else "https://www.coingecko.com/",
        ))
        _add(bucket, str(cg_cfg.get("tier", "tier1")), cg_score if _isfinite(cg_score) else None, float(cg_cfg.get("weight", 0.85)))

    # RSS (sync -> offload to thread)
    rss_cfg = sources_cfg.get("rss", {})
    if rss_cfg.get("enabled", False):
        rss = await asyncio.to_thread(fetch_rss_sentiment, rss_cfg.get("feeds", []) or [], max_rss)
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

    # Reddit market-wide (PRAW, sync)
    rg_cfg = sources_cfg.get("reddit_global", {})
    if rg_cfg.get("enabled", False):
        rg = await asyncio.to_thread(fetch_reddit_sentiment, rg_cfg.get("subreddits", []) or [], None, max_reddit)
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

    # Reddit symbol mentions (PRAW, sync)
    rs_cfg = sources_cfg.get("reddit_symbol", {})
    reddit_mentions = None
    if rs_cfg.get("enabled", False):
        rs = await asyncio.to_thread(fetch_reddit_sentiment, rs_cfg.get("subreddits", []) or [], sym.lower(), max_reddit)
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

    out: Dict[str, Any] = {
        "symbol": sym,
        "timestamp": int(time.time()),
        "overall_sentiment": overall if overall is not None else 0.5,
        "overallSentiment": overall if overall is not None else 0.5,
        "fear_greed_index": idx,
        "fear_greed_label": label,
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
        "social_metrics": {"reddit_mentions": reddit_mentions},
        "social_breakdown": {"reddit": None, "twitter": None, "telegram": None, "news": None},
        "trending_topics": [],
        "sentiment_history": [],
        "metadata": {
            "cache_hit": False,
            "processing_time_ms": int((time.time() - t0) * 1000),
            "sources_queried": len(sources),
            "sources_successful": sum(1 for s in sources if s.get("score_0_1") is not None),
            "using_aiohttp": aiohttp is not None,
        },
    }

    _RESULT_CACHE.set(cache_key, out, ttl)

    # Log summary
    elapsed_ms = out["metadata"]["processing_time_ms"]
    sources_ok = out["metadata"]["sources_successful"]
    total_sources = out["metadata"]["sources_queried"]
    overall_score = out["overall_sentiment"]

    logger.info(
        f"Sentiment computed for {sym}: score={overall_score:.3f}, "
        f"sources={sources_ok}/{total_sources}, elapsed={elapsed_ms}ms, "
        f"tier_scores={tier_scores}"
    )

    return out


# ----------------------------
# Public sync entrypoint
# ----------------------------


_BG_LOOP = asyncio.new_event_loop()
_BG_THREAD: Optional[threading.Thread] = None


def _ensure_bg_loop() -> None:
    global _BG_THREAD
    if _BG_THREAD and _BG_THREAD.is_alive():
        return

    def _run():
        asyncio.set_event_loop(_BG_LOOP)
        _BG_LOOP.run_forever()

    _BG_THREAD = threading.Thread(target=_run, name="sentiment-bg-loop", daemon=True)
    _BG_THREAD.start()


def get_sentiment_for_symbol(symbol: str) -> Dict[str, Any]:
    """Sync-friendly entrypoint for Flask routes.

    Uses a shared background event loop to avoid creating a new loop per request.
    If called from an async context, it will still leverage the same background
    loop to keep behavior consistent.
    """
    logger.debug(f"get_sentiment_for_symbol called with symbol={symbol}")
    _ensure_bg_loop()
    fut = asyncio.run_coroutine_threadsafe(_compute_sentiment_async(symbol), _BG_LOOP)
    return fut.result()
