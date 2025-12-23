"""
Shared pytest fixtures for sentiment aggregator tests.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch


# ============================================================================
# Mock Data Fixtures
# ============================================================================

@pytest.fixture
def mock_fear_greed_response():
    """Mock Fear & Greed Index API response."""
    return {
        "name": "Fear and Greed Index",
        "data": [{
            "value": "65",
            "value_classification": "Greed",
            "timestamp": "1703232000",
            "time_until_update": "43200"
        }],
        "metadata": {
            "error": None
        }
    }


@pytest.fixture
def mock_coingecko_btc_response():
    """Mock CoinGecko API response for BTC."""
    return {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "market_data": {
            "current_price": {"usd": 43250.50},
            "price_change_percentage_24h": 3.2,
            "price_change_percentage_7d": 8.5,
            "total_volume": {"usd": 25000000000},
            "market_cap": {"usd": 845000000000}
        },
        "community_data": {
            "facebook_likes": None,
            "twitter_followers": 5234567,
            "reddit_average_posts_48h": 145.2,
            "reddit_average_comments_48h": 892.5,
            "reddit_subscribers": 4567890,
            "reddit_accounts_active_48h": 12345
        },
        "developer_data": {
            "forks": 35678,
            "stars": 67890,
            "subscribers": 3456,
            "total_issues": 12345,
            "closed_issues": 11234,
            "pull_requests_merged": 23456,
            "pull_request_contributors": 789,
            "commit_count_4_weeks": 234
        },
        "sentiment_votes_up_percentage": 72.5,
        "sentiment_votes_down_percentage": 27.5
    }


@pytest.fixture
def mock_rss_feed_response():
    """Mock RSS feed response."""
    return {
        "feed": {
            "title": "CoinDesk",
            "link": "https://www.coindesk.com"
        },
        "entries": [
            {
                "title": "Bitcoin ETF Approval Sends Crypto Market Soaring",
                "link": "https://www.coindesk.com/article1",
                "published": "Wed, 22 Dec 2025 10:00:00 GMT",
                "summary": "The SEC approved the first Bitcoin spot ETF, causing bullish sentiment."
            },
            {
                "title": "Ethereum Upgrade Faces Unexpected Delay",
                "link": "https://www.coindesk.com/article2",
                "published": "Wed, 22 Dec 2025 09:00:00 GMT",
                "summary": "Developers postpone the upgrade due to security concerns."
            },
            {
                "title": "Major Exchange Launches New Trading Features",
                "link": "https://www.coindesk.com/article3",
                "published": "Wed, 22 Dec 2025 08:00:00 GMT",
                "summary": "Binance announces innovative trading tools for institutional investors."
            }
        ]
    }


@pytest.fixture
def mock_reddit_response():
    """Mock Reddit API response."""
    return [
        Mock(
            title="Bitcoin just hit new all-time high! 🚀",
            selftext="This is amazing news for the crypto community",
            score=1250,
            num_comments=345,
            created_utc=datetime.now().timestamp() - 3600,
            url="https://reddit.com/r/cryptocurrency/post1"
        ),
        Mock(
            title="Concerns about upcoming regulation",
            selftext="The new crypto regulations might impact the market negatively",
            score=890,
            num_comments=234,
            created_utc=datetime.now().timestamp() - 7200,
            url="https://reddit.com/r/cryptocurrency/post2"
        ),
        Mock(
            title="ETH staking rewards increasing",
            selftext="Great time to stake your Ethereum holdings",
            score=567,
            num_comments=123,
            created_utc=datetime.now().timestamp() - 10800,
            url="https://reddit.com/r/cryptocurrency/post3"
        )
    ]


@pytest.fixture
def mock_vader_scores():
    """Mock VADER sentiment scores."""
    return {
        "positive": {
            "neg": 0.0,
            "neu": 0.25,
            "pos": 0.75,
            "compound": 0.78
        },
        "negative": {
            "neg": 0.70,
            "neu": 0.25,
            "pos": 0.05,
            "compound": -0.65
        },
        "neutral": {
            "neg": 0.10,
            "neu": 0.80,
            "pos": 0.10,
            "compound": 0.0
        }
    }


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_sentiment_config():
    """Mock sentiment configuration."""
    return {
        "sentiment": {
            "cache_ttl_seconds": 300,
            "max_rss_items": 25,
            "max_reddit_posts": 40,
            "tier_weights": {
                "tier1": 0.85,
                "tier2": 0.70,
                "tier3": 0.50,
                "fringe": 0.30
            },
            "divergence_threshold": 0.12
        },
        "sources": {
            "fear_greed": {"enabled": True},
            "coingecko": {"enabled": True},
            "rss": {"enabled": True},
            "reddit_global": {"enabled": True},
            "reddit_symbol": {"enabled": True}
        },
        "rss_feeds": [
            {
                "name": "CoinDesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "tier": 2,
                "weight": 0.80
            }
        ],
        "reddit_subreddits": ["CryptoCurrency", "Bitcoin", "ethereum"],
        "lexicon": {
            "bullish": 2.0,
            "bearish": -2.0,
            "moon": 2.2,
            "dump": -2.2,
            "rug": -2.5,
            "scam": -2.5,
            "hack": -2.0,
            "fud": -1.5
        }
    }


# ============================================================================
# Cache Fixtures
# ============================================================================

@pytest.fixture
def mock_cache():
    """Mock in-memory cache."""
    cache_data = {}

    def get(key):
        entry = cache_data.get(key)
        if entry and entry["expires_at"] > datetime.now():
            return entry["data"]
        return None

    def set(key, data, ttl=300):
        cache_data[key] = {
            "data": data,
            "expires_at": datetime.now() + timedelta(seconds=ttl)
        }

    def clear():
        cache_data.clear()

    mock = Mock()
    mock.get = get
    mock.set = set
    mock.clear = clear
    return mock


# ============================================================================
# Symbol Fixtures
# ============================================================================

@pytest.fixture
def common_symbols():
    """Common cryptocurrency symbols for testing."""
    return ["BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "ADA", "DOGE"]


@pytest.fixture
def edge_case_symbols():
    """Edge case symbols for testing normalization."""
    return [
        "BTC/USD",  # With slash
        "BTC-USD",  # With hyphen
        "btc",      # Lowercase
        "  BTC  ",  # With whitespace
        "UNKNOWN_COIN_2025"  # Unknown symbol
    ]


# ============================================================================
# Async Fixtures
# ============================================================================

@pytest.fixture
async def mock_aiohttp_session():
    """Mock aiohttp ClientSession."""
    session = AsyncMock()

    async def mock_get(url, *args, **kwargs):
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={})
        response.text = AsyncMock(return_value="")
        return response

    session.get = mock_get
    return session


# ============================================================================
# Error Simulation Fixtures
# ============================================================================

@pytest.fixture
def simulate_network_error():
    """Simulate network connectivity issues."""
    def _simulate(exception_type=Exception, message="Network error"):
        return exception_type(message)
    return _simulate


@pytest.fixture
def simulate_rate_limit():
    """Simulate API rate limiting."""
    def _simulate():
        error = Exception("429 Too Many Requests")
        error.status_code = 429
        return error
    return _simulate


@pytest.fixture
def simulate_invalid_json():
    """Simulate invalid JSON response."""
    return json.JSONDecodeError("Expecting value", "", 0)
