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
try:
    import tweepy  # type: ignore
except Exception:
    tweepy = None
try:
    import redis  # type: ignore
except Exception:
    redis = None
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Import new handlers
CHINESE_SOURCES_AVAILABLE = False
CHINESE_SOURCES_IMPORT_ERROR = None
ChineseSourceHandler = None
try:
    from backend.chinese_sources import ChineseSourceHandler
    CHINESE_SOURCES_AVAILABLE = True
except Exception as _e:
    CHINESE_SOURCES_IMPORT_ERROR = str(_e)
    try:
        from chinese_sources import ChineseSourceHandler
        CHINESE_SOURCES_AVAILABLE = True
    except Exception as _e2:
        CHINESE_SOURCES_IMPORT_ERROR = CHINESE_SOURCES_IMPORT_ERROR or str(_e2)
        ChineseSourceHandler = None

try:
    from backend.telegram_handler import TelegramHandler
except ImportError:
    try:
        from telegram_handler import TelegramHandler
    except ImportError:
        TelegramHandler = None

try:
    from backend.custom_scrapers import CustomScraperHandler
except ImportError:
    try:
        from custom_scrapers import CustomScraperHandler
    except ImportError:
        CustomScraperHandler = None

try:
    from backend.reddit_handler import RedditHandler
except ImportError:
    try:
        from reddit_handler import RedditHandler
    except ImportError:
        RedditHandler = None

try:
    from backend.stocktwits_handler import StockTwitsHandler
except ImportError:
    try:
        from stocktwits_handler import StockTwitsHandler
    except ImportError:
        StockTwitsHandler = None


# ----------------------------
# Custom Exceptions
# ----------------------------

class SentimentAggregatorError(Exception):
    """Base exception for sentiment aggregator errors."""
    pass


class SourceFetchError(SentimentAggregatorError):
    """Raised when a data source fetch operation fails."""
    def __init__(self, source_name: str, message: str, original_error: Optional[Exception] = None):
        self.source_name = source_name
        self.original_error = original_error
        super().__init__(f"{source_name}: {message}")


class CacheError(SentimentAggregatorError):
    """Raised when cache operations fail."""
    pass


class ConfigError(SentimentAggregatorError):
    """Raised when configuration loading or validation fails."""
    pass


class SymbolNormalizationError(SentimentAggregatorError):
    """Raised when symbol normalization fails."""
    pass


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
# Circuit Breaker for Source Reliability
# ----------------------------

class CircuitBreaker:
    """Circuit breaker to prevent repeated calls to failing sources."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}
        self._lock = threading.Lock()

    def record_success(self, source_name: str) -> None:
        """Record a successful call."""
        with self._lock:
            self.failures.pop(source_name, None)
            self.opened_at.pop(source_name, None)

    def record_failure(self, source_name: str) -> None:
        """Record a failed call."""
        with self._lock:
            self.failures[source_name] = self.failures.get(source_name, 0) + 1
            if self.failures[source_name] >= self.failure_threshold:
                self.opened_at[source_name] = time.time()
                logger.warning(
                    f"Circuit breaker OPEN for {source_name} "
                    f"(failures={self.failures[source_name]}, cooldown={self.timeout_seconds}s)"
                )

    def is_open(self, source_name: str) -> bool:
        """Check if circuit is open (should skip calls)."""
        with self._lock:
            if source_name not in self.opened_at:
                return False

            # Check if cooldown period has elapsed
            if time.time() - self.opened_at[source_name] > self.timeout_seconds:
                logger.info(f"Circuit breaker attempting half-open for {source_name}")
                self.failures[source_name] = self.failure_threshold - 1  # Allow retry
                self.opened_at.pop(source_name, None)
                return False

            return True


_CIRCUIT_BREAKER = CircuitBreaker()


# ----------------------------
# Sentiment History Storage
# ----------------------------

class SentimentHistory:
    """Store sentiment history snapshots for trending analysis."""

    def __init__(self, max_snapshots: int = 100):
        self.max_snapshots = max_snapshots
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def add_snapshot(self, symbol: str, score: float, fear_greed: Optional[int] = None) -> None:
        """Add a sentiment snapshot for a symbol."""
        with self._lock:
            if symbol not in self._history:
                self._history[symbol] = []

            snapshot = {
                "timestamp": int(time.time()),
                "score": float(score),
                "fear_greed": fear_greed
            }

            self._history[symbol].append(snapshot)

            # Keep only recent snapshots (circular buffer)
            if len(self._history[symbol]) > self.max_snapshots:
                self._history[symbol] = self._history[symbol][-self.max_snapshots:]

            logger.debug(f"Added sentiment snapshot for {symbol}: score={score:.3f}")

    def get_history(self, symbol: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get sentiment history for the last N hours."""
        with self._lock:
            if symbol not in self._history:
                return []

            cutoff = time.time() - (hours * 3600)
            recent = [
                s for s in self._history[symbol]
                if s["timestamp"] >= cutoff
            ]

            logger.debug(f"Retrieved {len(recent)} history snapshots for {symbol} (last {hours}h)")
            return recent


_SENTIMENT_HISTORY = SentimentHistory()


class MetricsTracker:
    """Track performance metrics for observability."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        self._requests_total = 0
        self._requests_last_hour = []
        self._response_times = []  # Last 100 response times
        self._source_failures: Dict[str, int] = {}
        self._source_successes: Dict[str, int] = {}

    def record_cache_hit(self):
        """Record a cache hit."""
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        with self._lock:
            self._cache_misses += 1

    def record_request(self, response_time_ms: float):
        """Record a request with response time."""
        with self._lock:
            self._requests_total += 1
            self._requests_last_hour.append(int(time.time()))
            self._response_times.append(response_time_ms)

            # Keep only last 100 response times
            if len(self._response_times) > 100:
                self._response_times = self._response_times[-100:]

            # Prune old requests (older than 1 hour)
            cutoff = time.time() - 3600
            self._requests_last_hour = [t for t in self._requests_last_hour if t >= cutoff]

    def record_source_failure(self, source_name: str):
        """Record a source fetch failure."""
        with self._lock:
            self._source_failures[source_name] = self._source_failures.get(source_name, 0) + 1

    def record_source_success(self, source_name: str):
        """Record a source fetch success."""
        with self._lock:
            self._source_successes[source_name] = self._source_successes.get(source_name, 0) + 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            total_cache_ops = self._cache_hits + self._cache_misses
            cache_hit_rate = (self._cache_hits / total_cache_ops) if total_cache_ops > 0 else 0.0

            avg_response_time = (
                sum(self._response_times) / len(self._response_times)
                if self._response_times
                else 0.0
            )

            # Calculate source availability (successes / total attempts)
            source_availability = {}
            all_sources = set(self._source_failures.keys()) | set(self._source_successes.keys())
            for source in all_sources:
                failures = self._source_failures.get(source, 0)
                successes = self._source_successes.get(source, 0)
                total_attempts = failures + successes
                availability = (successes / total_attempts) if total_attempts > 0 else 0.0
                source_availability[source] = round(availability, 3)

            return {
                "cache_hit_rate": round(cache_hit_rate, 3),
                "avg_response_time_ms": round(avg_response_time, 1),
                "requests_last_hour": len(self._requests_last_hour),
                "requests_total": self._requests_total,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "source_availability": source_availability,
                "source_failures": dict(self._source_failures),
                "source_successes": dict(self._source_successes),
            }


_METRICS = MetricsTracker()


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


class RedisCache:
    """Redis-backed cache with automatic fallback to in-memory TTL cache."""

    def __init__(self, redis_url: str, key_prefix: str = "", fallback_to_memory: bool = True):
        self.key_prefix = key_prefix
        self.fallback_to_memory = fallback_to_memory
        self._memory_cache = TTLCache() if fallback_to_memory else None
        self._redis_client: Optional[Any] = None
        self._redis_available = False

        if redis is None:
            logger.warning("Redis library not installed, using in-memory cache")
            return

        try:
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # We'll handle encoding/decoding manually
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info(f"Redis cache initialized: {redis_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {redis_url}: {e}")
            if not fallback_to_memory:
                raise CacheError(f"Redis connection failed and fallback disabled: {e}")
            logger.info("Falling back to in-memory cache")

    def _make_key(self, key: str) -> str:
        """Add prefix to cache key."""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (tries Redis, falls back to memory)."""
        prefixed_key = self._make_key(key)

        # Try Redis first if available
        if self._redis_available and self._redis_client:
            try:
                data = self._redis_client.get(prefixed_key)
                if data is None:
                    logger.debug(f"Redis cache miss: {key}")
                    return None
                # Deserialize from JSON
                value = json.loads(data.decode('utf-8'))
                logger.debug(f"Redis cache hit: {key}")
                return value
            except Exception as e:
                logger.error(f"Redis get error for {key}: {e}")
                self._redis_available = False  # Mark as unavailable
                # Fall through to memory cache

        # Fallback to memory cache
        if self._memory_cache:
            return self._memory_cache.get(key)

        return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache (tries Redis, falls back to memory)."""
        prefixed_key = self._make_key(key)

        # Try Redis first if available
        if self._redis_available and self._redis_client:
            try:
                # Serialize to JSON
                data = json.dumps(value).encode('utf-8')
                self._redis_client.setex(prefixed_key, ttl, data)
                logger.debug(f"Redis cache set: {key} (TTL={ttl}s)")
                return
            except Exception as e:
                logger.error(f"Redis set error for {key}: {e}")
                self._redis_available = False  # Mark as unavailable
                # Fall through to memory cache

        # Fallback to memory cache
        if self._memory_cache:
            self._memory_cache.set(key, value, ttl)

    def clear(self) -> None:
        """Clear all cache entries (pattern-based for Redis)."""
        if self._redis_available and self._redis_client:
            try:
                pattern = f"{self.key_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = self._redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
                logger.info(f"Cleared Redis cache with prefix: {self.key_prefix}")
            except Exception as e:
                logger.error(f"Redis clear error: {e}")

        if self._memory_cache:
            self._memory_cache._data.clear()
            logger.info("Cleared in-memory cache")


def _create_cache_backend() -> Any:
    """Create cache backend based on configuration."""
    cache_config = _CONFIG.get("cache", {})
    backend = cache_config.get("backend", "memory")

    if backend == "redis":
        redis_url = cache_config.get("redis_url", "redis://localhost:6379/0")
        key_prefix = cache_config.get("key_prefix", "sentiment:")
        fallback = cache_config.get("fallback_to_memory", True)
        return RedisCache(redis_url, key_prefix, fallback)
    else:
        logger.info("Using in-memory cache (configured backend: memory)")
        return TTLCache()


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

# Initialize cache backends after config is loaded
_RESULT_CACHE = _create_cache_backend()
_SOURCE_CACHE = _create_cache_backend()

# HTTP connection pooling
_HTTP_SESSION: Optional[Any] = None
_HTTP_SESSION_LOCK = threading.Lock()


def _get_http_session() -> Optional[Any]:
    """Get or create persistent aiohttp ClientSession with connection pooling."""
    global _HTTP_SESSION

    if aiohttp is None:
        return None

    with _HTTP_SESSION_LOCK:
        if _HTTP_SESSION is None or _HTTP_SESSION.closed:
            # Create session with connection pooling
            connector = aiohttp.TCPConnector(
                limit=100,  # Max 100 concurrent connections
                limit_per_host=30,  # Max 30 per host
                ttl_dns_cache=300,  # DNS cache for 5 minutes
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            _HTTP_SESSION = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                raise_for_status=False,  # We'll handle status manually
            )
            logger.info("Created persistent HTTP session with connection pooling (limit=100, per_host=30)")

        return _HTTP_SESSION


async def _close_http_session() -> None:
    """Close the persistent HTTP session (for cleanup)."""
    global _HTTP_SESSION

    with _HTTP_SESSION_LOCK:
        if _HTTP_SESSION is not None and not _HTTP_SESSION.closed:
            await _HTTP_SESSION.close()
            logger.info("Closed persistent HTTP session")
            _HTTP_SESSION = None


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
# Trending Topics Extraction
# ----------------------------

def extract_trending_topics(rss_data: Dict[str, Any], reddit_data: Dict[str, Any], max_topics: int = 10) -> List[Dict[str, Any]]:
    """Extract trending crypto topics from RSS and Reddit content."""
    from collections import Counter
    import re

    # Crypto-related keywords to look for
    crypto_keywords = {
        "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
        "defi", "nft", "web3", "metaverse", "dao", "mining",
        "staking", "yield", "token", "coin", "altcoin", "memecoin",
        "binance", "bnb", "solana", "sol", "cardano", "ada",
        "ripple", "xrp", "dogecoin", "doge", "shiba", "polygon",
        "matic", "avalanche", "avax", "polkadot", "dot",
        "etf", "sec", "regulation", "halving", "bullish", "bearish",
        "pump", "dump", "moon", "hodl", "fud", "fomo"
    }

    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is", "was", "are", "be", "been", "being"}

    topic_counter = Counter()
    topic_sentiment: Dict[str, List[float]] = {}

    # Extract from RSS feeds
    if rss_data.get("enabled") and rss_data.get("feeds"):
        for feed in rss_data.get("feeds", []):
            for item in feed.get("entries", []):
                title = str(item.get("title", "")).lower()
                words = re.findall(r'\b\w+\b', title)
                for word in words:
                    if word in crypto_keywords and word not in stopwords:
                        topic_counter[word] += 1
                        if word not in topic_sentiment:
                            topic_sentiment[word] = []
                        # Score the full title for context
                        topic_sentiment[word].append(vader_score_0_1(title))

    # Extract from Reddit
    if reddit_data.get("enabled") and reddit_data.get("subreddits"):
        for subreddit in reddit_data.get("subreddits", []):
            for post in subreddit.get("posts", []):
                title = str(post.get("title", "")).lower()
                words = re.findall(r'\b\w+\b', title)
                for word in words:
                    if word in crypto_keywords and word not in stopwords:
                        topic_counter[word] += 1
                        if word not in topic_sentiment:
                            topic_sentiment[word] = []
                        topic_sentiment[word].append(vader_score_0_1(title))

    # Build trending topics list
    trending = []
    for topic, mentions in topic_counter.most_common(max_topics):
        avg_sentiment = sum(topic_sentiment[topic]) / len(topic_sentiment[topic]) if topic_sentiment.get(topic) else 0.5
        trending.append({
            "topic": topic.capitalize(),
            "mentions": mentions,
            "sentiment": round(avg_sentiment, 3)
        })

    logger.debug(f"Extracted {len(trending)} trending topics (from {len(topic_counter)} unique keywords)")
    return trending


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

    session = _get_http_session()
    if session is None:
        raise RuntimeError("Failed to get HTTP session")

    # Override timeout for this specific request
    t = aiohttp.ClientTimeout(total=timeout_s)
    async with session.get(url, timeout=t) as resp:
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


# ----------------------------
# Additional Free Sentiment APIs
# ----------------------------

# CoinyBubble TTL - shorter because updates more frequently (~1 min)
COINYBUBBLE_TTL = _ttl_value("coinybubble", 120)
CFGI_TTL = _ttl_value("cfgi", 300)
LUNARCRUSH_TTL = _ttl_value("lunarcrush", 600)
CG_GLOBAL_TTL = _ttl_value("coingecko_global", 300)


async def fetch_coinybubble_fng() -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    """Fetch Fear & Greed Index from CoinyBubble (more frequent updates than alternative.me).

    API: https://production.api.coinmarketcap.com/v1/global-metrics/quotes/latest
    Alternative free endpoint that mirrors Binance methodology with ~1 minute updates.
    """
    cache_key = _hash_key("coinybubble_fng", "global")
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # CoinyBubble uses a public endpoint - no auth required
    url = "https://api.coinybubble.com/v1/fear-greed"
    fallback_url = "https://fear-greed-index.p.rapidapi.com/v1/fgi"

    try:
        logger.debug("Fetching Fear & Greed Index from CoinyBubble")
        start_time = time.time()

        try:
            data = await fetch_json(url, timeout_s=5)
        except Exception:
            # Fallback: calculate from market data if CoinyBubble is down
            logger.debug("CoinyBubble unavailable, using alternative calculation")
            data = None

        if data and "value" in data:
            idx = int(data.get("value", 50))
            label = str(data.get("classification", "")).strip() or _fng_label(idx)
            meta = {"source": "coinybubble", "raw": data, "update_frequency": "1min"}
        else:
            # Return None to indicate source unavailable
            result = (None, None, {"error": "coinybubble_unavailable", "source": "coinybubble"})
            _SOURCE_CACHE.set(cache_key, result, 60)  # Short TTL for retry
            return result

        elapsed = (time.time() - start_time) * 1000
        result = (idx, label, meta)
        _SOURCE_CACHE.set(cache_key, result, COINYBUBBLE_TTL)

        logger.info(f"CoinyBubble F&G: {idx} ({label}) [fetched in {elapsed:.0f}ms]")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch CoinyBubble F&G: {e}")
        result = (None, None, {"error": str(e), "source": "coinybubble"})
        _SOURCE_CACHE.set(cache_key, result, 60)
        return result


def _fng_label(value: int) -> str:
    """Convert F&G index value to label."""
    if value <= 20:
        return "Extreme Fear"
    elif value <= 40:
        return "Fear"
    elif value <= 60:
        return "Neutral"
    elif value <= 80:
        return "Greed"
    else:
        return "Extreme Greed"


async def fetch_cfgi_fng(symbol: str = "BTC") -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    """Fetch Fear & Greed Index from CFGI.io (multi-currency, 10 AI algorithms).

    API: https://cfgi.io/api - Free, no auth required
    Supports: BTC, ETH, and other major coins with individual F&G scores.
    """
    cache_key = _hash_key("cfgi_fng", symbol)
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # CFGI.io provides per-coin fear & greed
    url = f"https://cfgi.io/api/public/fgi/{symbol.lower()}"

    try:
        logger.debug(f"Fetching CFGI.io F&G for {symbol}")
        start_time = time.time()
        data = await fetch_json(url, timeout_s=8)
        elapsed = (time.time() - start_time) * 1000

        # CFGI returns: {"fgi": 62, "classification": "Greed", "timestamp": ...}
        idx = int(data.get("fgi", data.get("value", 50)))
        label = str(data.get("classification", "")).strip() or _fng_label(idx)

        meta = {
            "source": "cfgi.io",
            "symbol": symbol,
            "raw": data,
            "features": "10 AI algorithms, multi-currency"
        }

        result = (idx, label, meta)
        _SOURCE_CACHE.set(cache_key, result, CFGI_TTL)

        logger.info(f"CFGI.io F&G ({symbol}): {idx} ({label}) [fetched in {elapsed:.0f}ms]")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch CFGI.io F&G for {symbol}: {e}")
        result = (None, None, {"error": str(e), "source": "cfgi.io", "symbol": symbol})
        _SOURCE_CACHE.set(cache_key, result, 60)
        return result


async def fetch_lunarcrush_sentiment(symbol: str) -> Dict[str, Any]:
    """Fetch social sentiment from LunarCrush free API.

    LunarCrush tracks social volume across Twitter, Reddit, TikTok, YouTube, etc.
    Free tier: Some endpoints don't require API key (v2 discover endpoints).

    Metrics returned:
    - Galaxy Score (0-100): Overall social health
    - AltRank: Relative ranking vs other coins
    - Social Volume: Total mentions across platforms
    - Sentiment: Bullish vs Bearish ratio
    """
    cache_key = _hash_key("lunarcrush", symbol)
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # Try free public endpoint first (no key required for some data)
    # V3 requires key, but V2 discover data may be available
    api_key = os.getenv("LUNARCRUSH_API_KEY", "").strip()

    # LunarCrush coin symbol mapping (they use different identifiers)
    lc_symbol = symbol.upper()

    try:
        logger.debug(f"Fetching LunarCrush sentiment for {symbol}")
        start_time = time.time()

        # Try V2 public endpoint (limited free access)
        if api_key:
            url = f"https://lunarcrush.com/api4/public/coins/{lc_symbol}/v1"
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            # Fallback to checking if public endpoint works
            url = f"https://api.lunarcrush.com/v2?data=assets&symbol={lc_symbol}"
            headers = {}

        if aiohttp is not None:
            session = _get_http_session()
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}")
        else:
            # Sync fallback
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()

        elapsed = (time.time() - start_time) * 1000

        # Parse LunarCrush response
        # V2 format: {"data": [{"symbol": "BTC", "galaxy_score": 75, ...}]}
        # V4 format: {"data": {"symbol": "BTC", "galaxy_score": 75, ...}}

        asset_data = None
        if isinstance(data.get("data"), list) and data["data"]:
            asset_data = data["data"][0]
        elif isinstance(data.get("data"), dict):
            asset_data = data["data"]
        elif "galaxy_score" in data:
            asset_data = data

        if not asset_data:
            result = {"enabled": False, "reason": "no_data", "source": "lunarcrush"}
            _SOURCE_CACHE.set(cache_key, result, 300)
            return result

        # Extract key metrics
        galaxy_score = asset_data.get("galaxy_score") or asset_data.get("gs")
        alt_rank = asset_data.get("alt_rank") or asset_data.get("acr")
        social_volume = asset_data.get("social_volume") or asset_data.get("sv")
        social_score = asset_data.get("social_score") or asset_data.get("ss")

        # Sentiment ratio (bullish vs bearish mentions)
        bullish = float(asset_data.get("bullish", asset_data.get("bullish_sentiment", 0)) or 0)
        bearish = float(asset_data.get("bearish", asset_data.get("bearish_sentiment", 0)) or 0)

        # Calculate sentiment score (0-1)
        if bullish + bearish > 0:
            sentiment_score = bullish / (bullish + bearish)
        elif galaxy_score is not None:
            # Use galaxy score as proxy (0-100 -> 0-1)
            sentiment_score = float(galaxy_score) / 100.0
        else:
            sentiment_score = None

        result = {
            "enabled": True,
            "source": "lunarcrush",
            "symbol": symbol,
            "score_0_1": sentiment_score,
            "galaxy_score": galaxy_score,
            "alt_rank": alt_rank,
            "social_volume": social_volume,
            "social_score": social_score,
            "bullish_bearish_ratio": {
                "bullish": bullish,
                "bearish": bearish,
            },
            "raw": asset_data,
        }

        _SOURCE_CACHE.set(cache_key, result, LUNARCRUSH_TTL)
        logger.info(f"LunarCrush {symbol}: score={sentiment_score:.3f if sentiment_score else 'N/A'}, "
                   f"galaxy={galaxy_score}, social_vol={social_volume} [fetched in {elapsed:.0f}ms]")
        return result

    except Exception as e:
        logger.warning(f"LunarCrush fetch failed for {symbol}: {e}")
        result = {
            "enabled": True,
            "source": "lunarcrush",
            "symbol": symbol,
            "score_0_1": None,
            "error": str(e),
        }
        _SOURCE_CACHE.set(cache_key, result, 300)
        return result


async def fetch_coingecko_global() -> Dict[str, Any]:
    """Fetch global market metrics from CoinGecko for market-wide sentiment signal.

    Uses market cap change, volume change, and BTC dominance as sentiment indicators.
    Free API: 30 calls/min, no auth required.
    """
    cache_key = _hash_key("cg_global", "market")
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.coingecko.com/api/v3/global"

    try:
        logger.debug("Fetching CoinGecko global market data")
        start_time = time.time()
        data = await fetch_json(url, timeout_s=10)
        elapsed = (time.time() - start_time) * 1000

        gd = data.get("data", {})

        # Extract key metrics
        total_mcap = float(gd.get("total_market_cap", {}).get("usd", 0))
        total_volume = float(gd.get("total_volume", {}).get("usd", 0))
        mcap_change_24h = float(gd.get("market_cap_change_percentage_24h_usd", 0))
        btc_dominance = float(gd.get("market_cap_percentage", {}).get("btc", 0))
        active_coins = gd.get("active_cryptocurrencies", 0)

        # Calculate market sentiment score based on 24h change
        # -10% to +10% maps to 0.0 to 1.0
        change_clamped = max(-10.0, min(10.0, mcap_change_24h))
        market_score = (change_clamped + 10.0) / 20.0

        # Volume/MCap ratio as activity indicator
        vol_mcap_ratio = (total_volume / total_mcap) if total_mcap > 0 else 0

        result = {
            "enabled": True,
            "source": "coingecko_global",
            "score_0_1": market_score,
            "metrics": {
                "total_market_cap_usd": total_mcap,
                "total_volume_24h_usd": total_volume,
                "market_cap_change_24h_pct": mcap_change_24h,
                "btc_dominance_pct": btc_dominance,
                "active_cryptocurrencies": active_coins,
                "volume_mcap_ratio": vol_mcap_ratio,
            },
            "interpretation": {
                "market_trend": "bullish" if mcap_change_24h > 2 else ("bearish" if mcap_change_24h < -2 else "neutral"),
                "activity_level": "high" if vol_mcap_ratio > 0.1 else ("low" if vol_mcap_ratio < 0.05 else "normal"),
            },
        }

        _SOURCE_CACHE.set(cache_key, result, CG_GLOBAL_TTL)
        logger.info(f"CoinGecko Global: score={market_score:.3f}, mcap_chg={mcap_change_24h:.2f}%, "
                   f"btc_dom={btc_dominance:.1f}% [fetched in {elapsed:.0f}ms]")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch CoinGecko global: {e}")
        result = {"enabled": True, "source": "coingecko_global", "score_0_1": None, "error": str(e)}
        _SOURCE_CACHE.set(cache_key, result, 60)
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


def _tweepy_client() -> Optional[Any]:
    """Create Twitter API v2 client using Bearer token."""
    if tweepy is None:
        return None
    bearer_token = (os.getenv("TWITTER_BEARER_TOKEN") or "").strip()
    if not bearer_token:
        return None
    try:
        return tweepy.Client(bearer_token=bearer_token)
    except Exception:
        return None


async def fetch_twitter_sentiment_async(symbol: str, max_tweets: int = 50) -> Dict[str, Any]:
    """Fetch Twitter sentiment for a symbol using Twitter API v2."""
    cache_key = _hash_key("twitter", symbol)
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    client = _tweepy_client()
    if client is None:
        result = {"enabled": False, "reason": "twitter_not_configured"}
        _SOURCE_CACHE.set(cache_key, result, 600)  # Cache disabled status for 10 min
        return result

    # Build search query with multiple term variations
    search_terms = [symbol, f"${symbol}", f"#{symbol}"]
    query = " OR ".join(search_terms) + " -is:retweet lang:en"

    try:
        logger.debug(f"Fetching Twitter sentiment for {symbol} (max_tweets={max_tweets})")
        start_time = time.time()

        # Search recent tweets (last 7 days)
        # Note: tweepy v4 uses synchronous calls, so we run in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.search_recent_tweets(
                query=query,
                max_results=min(max_tweets, 100),  # API limit is 100
                tweet_fields=["public_metrics", "created_at"],
            )
        )

        elapsed = (time.time() - start_time) * 1000

        if not response.data:
            result = {"enabled": True, "score_0_1": None, "tweets": 0, "mentions": 0}
            _SOURCE_CACHE.set(cache_key, result, 600)
            logger.info(f"Twitter {symbol}: no tweets found")
            return result

        tweets = response.data
        scores: List[float] = []
        weighted_scores: List[float] = []

        for tweet in tweets:
            text = tweet.text
            sentiment = vader_score_0_1(text)
            scores.append(sentiment)

            # Weight by engagement (likes + retweets)
            metrics = tweet.public_metrics or {}
            likes = metrics.get("like_count", 0)
            retweets = metrics.get("retweet_count", 0)
            engagement = likes + (retweets * 2)  # Retweets count double

            # Add engagement-weighted samples
            weight_multiplier = min(1 + (engagement / 100), 5)  # Cap at 5x weight
            for _ in range(int(weight_multiplier)):
                weighted_scores.append(sentiment)

        avg_score = sum(scores) / len(scores) if scores else 0.5
        weighted_avg = sum(weighted_scores) / len(weighted_scores) if weighted_scores else avg_score

        result = {
            "enabled": True,
            "score_0_1": float(weighted_avg),
            "tweets": len(tweets),
            "mentions": len(tweets),
            "avg_score": float(avg_score),
            "weighted_avg": float(weighted_avg),
        }
        _SOURCE_CACHE.set(cache_key, result, 600)
        logger.info(f"Twitter {symbol}: score={weighted_avg:.3f}, tweets={len(tweets)} [fetched in {elapsed:.0f}ms]")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch Twitter sentiment for {symbol}: {e}")
        result = {"enabled": True, "score_0_1": None, "tweets": 0, "error": str(e)}
        _SOURCE_CACHE.set(cache_key, result, 600)
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
        _METRICS.record_cache_hit()
        return cached

    logger.debug(f"Cache miss for {sym}, fetching from sources")
    _METRICS.record_cache_miss()
    sources_cfg = _cfg("sources", {}) or {}
    bucket = _tier_bucket()
    sources: List[Dict[str, Any]] = []
    t0 = time.time()

    # Launch all async tasks in parallel for tier1 sources
    fg_task = asyncio.create_task(fetch_fear_greed()) if sources_cfg.get("fear_greed", {}).get("enabled", False) else None
    cg_task = asyncio.create_task(fetch_coingecko_metrics(sym)) if sources_cfg.get("coingecko", {}).get("enabled", False) else None

    # New free API sources (tier1)
    coinybubble_task = asyncio.create_task(fetch_coinybubble_fng()) if sources_cfg.get("coinybubble_fng", {}).get("enabled", False) else None
    cfgi_task = asyncio.create_task(fetch_cfgi_fng(sym)) if sources_cfg.get("cfgi", {}).get("enabled", False) else None
    cg_global_task = asyncio.create_task(fetch_coingecko_global()) if sources_cfg.get("coingecko_global", {}).get("enabled", False) else None

    # Tier2 social aggregator
    lunarcrush_task = asyncio.create_task(fetch_lunarcrush_sentiment(sym)) if sources_cfg.get("lunarcrush", {}).get("enabled", False) else None

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

    # CoinyBubble Fear & Greed (more frequent updates)
    coinybubble_idx = coinybubble_label = None
    if coinybubble_task:
        coinybubble_idx, coinybubble_label, cb_meta = await coinybubble_task
        cb_score = (float(coinybubble_idx) / 100.0) if coinybubble_idx is not None else None
        cb_cfg = sources_cfg.get("coinybubble_fng", {})
        sources.append(_source_record(
            name="CoinyBubble F&G",
            tier=str(cb_cfg.get("tier", "tier1")),
            weight=float(cb_cfg.get("weight", 0.85)),
            score_0_1=cb_score,
            meta={"index": coinybubble_idx, "label": coinybubble_label, **cb_meta},
            url="https://coinybubble.com/",
        ))
        _add(bucket, str(cb_cfg.get("tier", "tier1")), cb_score, float(cb_cfg.get("weight", 0.85)))

    # CFGI.io Fear & Greed (per-coin, AI-powered)
    cfgi_idx = cfgi_label = None
    if cfgi_task:
        cfgi_idx, cfgi_label, cfgi_meta = await cfgi_task
        cfgi_score = (float(cfgi_idx) / 100.0) if cfgi_idx is not None else None
        cfgi_cfg = sources_cfg.get("cfgi", {})
        sources.append(_source_record(
            name=f"CFGI.io F&G ({sym})",
            tier=str(cfgi_cfg.get("tier", "tier1")),
            weight=float(cfgi_cfg.get("weight", 0.80)),
            score_0_1=cfgi_score,
            meta={"index": cfgi_idx, "label": cfgi_label, **cfgi_meta},
            url="https://cfgi.io/",
        ))
        _add(bucket, str(cfgi_cfg.get("tier", "tier1")), cfgi_score, float(cfgi_cfg.get("weight", 0.80)))

    # CoinGecko Global Market (market-wide sentiment signal)
    cg_global_metrics: Dict[str, Any] = {}
    if cg_global_task:
        cg_global = await cg_global_task
        cg_global_score = cg_global.get("score_0_1") if cg_global.get("enabled") else None
        cg_global_metrics = cg_global.get("metrics") or {}
        cgg_cfg = sources_cfg.get("coingecko_global", {})
        sources.append(_source_record(
            name="CoinGecko Global Market",
            tier=str(cgg_cfg.get("tier", "tier1")),
            weight=float(cgg_cfg.get("weight", 0.75)),
            score_0_1=cg_global_score if _isfinite(cg_global_score) else None,
            meta={"coingecko_global": cg_global},
            url="https://www.coingecko.com/en/global_charts",
        ))
        _add(bucket, str(cgg_cfg.get("tier", "tier1")), cg_global_score if _isfinite(cg_global_score) else None, float(cgg_cfg.get("weight", 0.75)))

    # LunarCrush Social Sentiment (Galaxy Score, social volume)
    lunarcrush_score = None
    lunarcrush_data: Dict[str, Any] = {}
    if lunarcrush_task:
        lc = await lunarcrush_task
        lunarcrush_score = lc.get("score_0_1") if lc.get("enabled") else None
        lunarcrush_data = lc
        lc_cfg = sources_cfg.get("lunarcrush", {})
        sources.append(_source_record(
            name=f"LunarCrush ({sym})",
            tier=str(lc_cfg.get("tier", "tier2")),
            weight=float(lc_cfg.get("weight", 0.75)),
            score_0_1=lunarcrush_score if _isfinite(lunarcrush_score) else None,
            meta={
                "galaxy_score": lc.get("galaxy_score"),
                "alt_rank": lc.get("alt_rank"),
                "social_volume": lc.get("social_volume"),
                "bullish_bearish": lc.get("bullish_bearish_ratio"),
            },
            url="https://lunarcrush.com/",
        ))
        _add(bucket, str(lc_cfg.get("tier", "tier2")), lunarcrush_score if _isfinite(lunarcrush_score) else None, float(lc_cfg.get("weight", 0.75)))

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

    # Twitter sentiment (async)
    tw_cfg = sources_cfg.get("twitter", {})
    twitter_score = None
    twitter_mentions = None
    if tw_cfg.get("enabled", False):
        max_tweets = int(tw_cfg.get("max_tweets", 50) or 50)
        tw = await fetch_twitter_sentiment_async(sym, max_tweets=max_tweets)
        twitter_score = tw.get("score_0_1")
        twitter_mentions = tw.get("mentions")
        sources.append(_source_record(
            name=f"Twitter ({sym})",
            tier=str(tw_cfg.get("tier", "tier2")),
            weight=float(tw_cfg.get("weight", 0.70)),
            score_0_1=twitter_score if _isfinite(twitter_score) else None,
            meta={"twitter": tw, "mentions": twitter_mentions},
            url="https://twitter.com/",
        ))
        _add(bucket, str(tw_cfg.get("tier", "tier2")), twitter_score if _isfinite(twitter_score) else None, float(tw_cfg.get("weight", 0.70)))

    # StockTwits (Async)
    st_cfg = sources_cfg.get("stocktwits", {})
    st_score = None
    if st_cfg.get("enabled", True) and StockTwitsHandler:
        try:
            async with StockTwitsHandler([sym]) as handler:
                st_results = await handler.fetch_symbol_sentiment(sym)
            
            if st_results:
                st_score = st_results.get("sentiment")
                
                sources.append(_source_record(
                    name=f"StockTwits ({sym})",
                    tier=str(st_cfg.get("tier", "tier3")),
                    weight=float(st_cfg.get("weight", 0.60)),
                    score_0_1=st_score if _isfinite(st_score) else None,
                    meta={"stocktwits": st_results},
                    url=f"https://stocktwits.com/symbol/{sym}.X",
                ))
                _add(bucket, str(st_cfg.get("tier", "tier3")), st_score if _isfinite(st_score) else None, float(st_cfg.get("weight", 0.60)))
        except Exception as e:
            logger.error(f"Error fetching StockTwits: {e}")

    # Chinese Sources (Async)
    cn_cfg = sources_cfg.get("chinese", {})
    cn_score = None
    if cn_cfg.get("enabled", False) and CHINESE_SOURCES_AVAILABLE and ChineseSourceHandler:
        try:
            cn_sources = cn_cfg.get("sources", [])
            async with ChineseSourceHandler(cn_sources) as handler:
                cn_results = await handler.fetch_all_sources()
                
            if cn_results:
                # Calculate average sentiment
                valid_scores = [float(r.get("sentiment", 0)) for r in cn_results if r.get("sentiment") is not None]
                if valid_scores:
                    avg_compound = sum(valid_scores) / len(valid_scores)
                    cn_score = (avg_compound + 1.0) / 2.0  # Convert -1..1 to 0..1
            
            sources.append(_source_record(
                name="Chinese Markets",
                tier=str(cn_cfg.get("tier", "tier2")),
                weight=float(cn_cfg.get("weight", 0.70)),
                score_0_1=cn_score if _isfinite(cn_score) else None,
                meta={"count": len(cn_results), "sources": [r.get("source") for r in cn_results]},
                url=None,
            ))
            _add(bucket, str(cn_cfg.get("tier", "tier2")), cn_score if _isfinite(cn_score) else None, float(cn_cfg.get("weight", 0.70)))
        except Exception as e:
            logger.error(f"Error fetching Chinese sources: {e}")

    # Telegram Channels (Async)
    tg_cfg = sources_cfg.get("telegram", {})
    tg_score = None
    if tg_cfg.get("enabled", False) and TelegramHandler:
        try:
            tg_channels = tg_cfg.get("channels", [])
            # TelegramHandler might need API keys from env, ensure they are set or handled inside
            async with TelegramHandler(tg_channels) as handler:
                tg_results = await handler.fetch_all_channels()
                
            if tg_results:
                valid_scores = [float(r.get("sentiment", 0)) for r in tg_results if r.get("sentiment") is not None]
                if valid_scores:
                    avg_compound = sum(valid_scores) / len(valid_scores)
                    tg_score = (avg_compound + 1.0) / 2.0
            
            sources.append(_source_record(
                name="Telegram Channels",
                tier=str(tg_cfg.get("tier", "tier3")),
                weight=float(tg_cfg.get("weight", 0.60)),
                score_0_1=tg_score if _isfinite(tg_score) else None,
                meta={"count": len(tg_results), "channels": list(set(r.get("channel") for r in tg_results))},
                url="https://web.telegram.org/",
            ))
            _add(bucket, str(tg_cfg.get("tier", "tier3")), tg_score if _isfinite(tg_score) else None, float(tg_cfg.get("weight", 0.60)))
        except Exception as e:
            logger.error(f"Error fetching Telegram sources: {e}")

    # Custom Scrapers (4chan, Forums)
    custom_cfg = sources_cfg.get("custom_scrapers", {})
    custom_score = None
    if custom_cfg.get("enabled", False) and CustomScraperHandler:
        try:
            custom_sources = custom_cfg.get("sources", [])
            async with CustomScraperHandler(custom_sources) as handler:
                custom_results = await handler.fetch_all_sources()
            
            if custom_results:
                # Custom scrapers return 'calculated_sentiment' in metadata (0..1)
                valid_scores = []
                for item in custom_results:
                    meta = item.get('metadata', {})
                    if 'calculated_sentiment' in meta:
                        valid_scores.append(float(meta['calculated_sentiment']))
                
                if valid_scores:
                    custom_score = sum(valid_scores) / len(valid_scores)
            
            sources.append(_source_record(
                name="Custom Scrapers (4chan/Forums)",
                tier=str(custom_cfg.get("tier", "tier3")),
                weight=float(custom_cfg.get("weight", 0.50)),
                score_0_1=custom_score if _isfinite(custom_score) else None,
                meta={"count": len(custom_results), "sources": list(set(r.get("source") for r in custom_results))},
                url=None,
            ))
            _add(bucket, str(custom_cfg.get("tier", "tier3")), custom_score if _isfinite(custom_score) else None, float(custom_cfg.get("weight", 0.50)))
        except Exception as e:
            logger.error(f"Error fetching Custom Scrapers: {e}")

    tier_scores = _finalize_tier_scores(bucket)
    overall = _weighted_overall(tier_scores, tier_weights)
    divergence = _divergence_alerts(tier_scores, divergence_threshold)

    # Extract trending topics from RSS and Reddit
    trending_topics = extract_trending_topics(
        rss if rss_cfg.get("enabled", False) else {},
        rg if rg_cfg.get("enabled", False) else {}
    )

    # Populate social_breakdown with actual values
    social_breakdown = {
        "reddit": rg_score if rg_cfg.get("enabled", False) and _isfinite(rg_score) else None,
        "twitter": twitter_score if tw_cfg.get("enabled", False) and _isfinite(twitter_score) else None,
        "telegram": tg_score if tg_cfg.get("enabled", False) and _isfinite(tg_score) else None,
        "stocktwits": st_score if st_cfg.get("enabled", True) and _isfinite(st_score) else None,
        "lunarcrush": lunarcrush_score if sources_cfg.get("lunarcrush", {}).get("enabled", False) and _isfinite(lunarcrush_score) else None,
        "custom": custom_score if custom_cfg.get("enabled", False) and _isfinite(custom_score) else None,
        "news": rss_score if rss_cfg.get("enabled", False) and _isfinite(rss_score) else None,
    }

    # Multi-source Fear & Greed consensus (average all F&G sources)
    fng_sources = []
    if idx is not None:
        fng_sources.append(("alternative_me", idx))
    if coinybubble_idx is not None:
        fng_sources.append(("coinybubble", coinybubble_idx))
    if cfgi_idx is not None:
        fng_sources.append(("cfgi", cfgi_idx))

    fng_consensus = None
    if fng_sources:
        fng_consensus = sum(v for _, v in fng_sources) / len(fng_sources)

    # Get sentiment history for this symbol
    sentiment_history = _SENTIMENT_HISTORY.get_history(sym, hours=24)

    # Store current sentiment snapshot in history
    if overall is not None:
        _SENTIMENT_HISTORY.add_snapshot(sym, overall, fear_greed=idx)

    out: Dict[str, Any] = {
        "symbol": sym,
        "timestamp": int(time.time()),
        "overall_sentiment": overall if overall is not None else 0.5,
        "overallSentiment": overall if overall is not None else 0.5,
        "fear_greed_index": idx,
        "fear_greed_label": label,
        "fear_greed_consensus": int(round(fng_consensus)) if fng_consensus is not None else None,
        "fear_greed_sources": {name: val for name, val in fng_sources} if fng_sources else {},
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
        "market_metrics": cg_global_metrics or {},
        "social_metrics": {
            "reddit_mentions": reddit_mentions,
            "twitter_mentions": twitter_mentions,
            "lunarcrush_galaxy_score": lunarcrush_data.get("galaxy_score") if lunarcrush_data else None,
            "lunarcrush_alt_rank": lunarcrush_data.get("alt_rank") if lunarcrush_data else None,
            "lunarcrush_social_volume": lunarcrush_data.get("social_volume") if lunarcrush_data else None,
        },
        "social_breakdown": social_breakdown,
        "trending_topics": trending_topics,
        "sentiment_history": sentiment_history,
        "metadata": {
            "cache_hit": False,
            "processing_time_ms": int((time.time() - t0) * 1000),
            "sources_queried": len(sources),
            "sources_successful": sum(1 for s in sources if s.get("score_0_1") is not None),
            "using_aiohttp": aiohttp is not None,
            "fng_source_count": len(fng_sources),
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

    # Record metrics
    _METRICS.record_request(elapsed_ms)

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


def get_sentiment_for_symbol(symbol: str, timeout_s: float = None) -> Dict[str, Any]:
    """Sync-friendly entrypoint for Flask routes.

    Uses a shared background event loop to avoid creating a new loop per request.
    If called from an async context, it will still leverage the same background
    loop to keep behavior consistent.
    """
    logger.debug(f"get_sentiment_for_symbol called with symbol={symbol}")
    _ensure_bg_loop()
    fut = asyncio.run_coroutine_threadsafe(_compute_sentiment_async(symbol), _BG_LOOP)
    if timeout_s is None:
        return fut.result()
    return fut.result(timeout=timeout_s)


def get_metrics() -> Dict[str, Any]:
    """Get observability metrics for monitoring.

    Returns:
        Dictionary containing:
        - cache_hit_rate: Percentage of cache hits (0.0-1.0)
        - avg_response_time_ms: Average response time in milliseconds
        - requests_last_hour: Number of requests in the last hour
        - requests_total: Total requests since startup
        - cache_hits/cache_misses: Cache hit/miss counts
        - source_availability: Availability percentage per source
        - source_failures/source_successes: Per-source failure/success counts
    """
    return _METRICS.get_metrics()
