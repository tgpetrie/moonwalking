#!/usr/bin/env python3
"""
Sentiment Data Sources - Real Data Collection
Fetches sentiment from multiple sources across all tiers
"""

import asyncio
import aiohttp
import feedparser
import praw
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re
import os

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class SentimentData:
    """Single sentiment data point"""
    source: str
    tier: str
    sentiment_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    text: str
    timestamp: datetime
    metadata: Dict


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment across sources"""
    overall_score: float
    tier_scores: Dict[str, float]
    source_scores: Dict[str, float]
    total_samples: int
    timestamp: datetime


# ============================================================================
# SENTIMENT ANALYZER
# ============================================================================

class CryptoSentimentAnalyzer:
    """Enhanced sentiment analyzer with crypto-specific lexicon"""
    
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self._load_crypto_lexicon()
    
    def _load_crypto_lexicon(self):
        """Add crypto-specific terms to VADER lexicon"""
        crypto_terms = {
            # Bullish terms
            'moon': 2.5, 'mooning': 2.5, 'bullish': 2.0, 'pump': 1.8,
            'hodl': 1.5, 'diamond hands': 2.0, 'ath': 1.5, 'breakout': 1.8,
            'rally': 1.5, 'surge': 1.8, 'gains': 1.8, 'buying': 1.2,
            'long': 1.0, 'buy': 1.5, 'accumulate': 1.3, 'support': 0.8,
            'resistance broken': 2.0, 'golden cross': 2.2, 'btfd': 1.5,
            
            # Bearish terms
            'dump': -2.0, 'bearish': -2.0, 'crash': -2.5, 'rekt': -2.0,
            'paper hands': -1.5, 'fud': -1.8, 'scam': -2.5, 'rug pull': -2.8,
            'ponzi': -2.5, 'collapse': -2.5, 'selling': -1.2, 'short': -1.0,
            'sell': -1.5, 'exit': -1.3, 'resistance': -0.5, 'death cross': -2.2,
            'liquidation': -2.0, 'margin call': -2.0,
            
            # Neutral/Info terms
            'dyor': 0.0, 'nfa': 0.0, 'wagmi': 0.5, 'gm': 0.2, 'wen': 0.0,
        }
        
        self.vader.lexicon.update(crypto_terms)
    
    def analyze(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text
        Returns: {'compound': float, 'pos': float, 'neu': float, 'neg': float}
        """
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
    
    def get_sentiment_label(self, compound_score: float) -> str:
        """Convert compound score to label"""
        if compound_score >= 0.6:
            return "Very Bullish"
        elif compound_score >= 0.2:
            return "Bullish"
        elif compound_score >= -0.2:
            return "Neutral"
        elif compound_score >= -0.6:
            return "Bearish"
        else:
            return "Very Bearish"


# ============================================================================
# DATA SOURCE COLLECTORS
# ============================================================================

class FearGreedCollector:
    """Collect Fear & Greed Index (Tier 1)"""
    
    def __init__(self):
        self.url = "https://api.alternative.me/fng/"
        self.tier = "tier1"
    
    async def fetch(self) -> Optional[SentimentData]:
        """Fetch current Fear & Greed Index"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    if response.status == 200:
                        data = await response.json()
                        value = int(data['data'][0]['value'])
                        classification = data['data'][0]['value_classification']
                        
                        # Convert 0-100 scale to -1 to 1
                        sentiment_score = (value - 50) / 50.0
                        
                        return SentimentData(
                            source="Fear & Greed Index",
                            tier=self.tier,
                            sentiment_score=sentiment_score,
                            confidence=0.9,
                            text=f"Fear & Greed Index: {value} ({classification})",
                            timestamp=datetime.now(),
                            metadata={"value": value, "classification": classification}
                        )
        except Exception as e:
            logger.error(f"Fear & Greed fetch error: {e}")
            return None


class RedditCollector:
    """Collect Reddit sentiment (Tier 2/3)"""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.analyzer = CryptoSentimentAnalyzer()
    
    async def fetch_subreddit(
        self, 
        subreddit_name: str, 
        tier: str,
        post_limit: int = 100
    ) -> List[SentimentData]:
        """Fetch sentiment from a subreddit"""
        results = []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Get hot posts
            for post in subreddit.hot(limit=post_limit):
                # Analyze title and body
                text = f"{post.title} {post.selftext}"
                sentiment = self.analyzer.analyze(text)
                
                results.append(SentimentData(
                    source=f"Reddit r/{subreddit_name}",
                    tier=tier,
                    sentiment_score=sentiment['compound'],
                    confidence=abs(sentiment['compound']),
                    text=post.title,
                    timestamp=datetime.fromtimestamp(post.created_utc),
                    metadata={
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "upvote_ratio": post.upvote_ratio
                    }
                ))
            
            logger.info(f"Collected {len(results)} posts from r/{subreddit_name}")
            
        except Exception as e:
            logger.error(f"Reddit fetch error for r/{subreddit_name}: {e}")
        
        return results


class RSSFeedCollector:
    """Collect sentiment from RSS feeds (Tier 1/2)"""
    
    def __init__(self):
        self.analyzer = CryptoSentimentAnalyzer()
    
    async def fetch_feed(
        self, 
        feed_url: str, 
        source_name: str,
        tier: str,
        limit: int = 50
    ) -> List[SentimentData]:
        """Fetch and analyze RSS feed"""
        results = []
        
        try:
            # Parse feed
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:limit]:
                # Analyze title and summary
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                sentiment = self.analyzer.analyze(text)
                
                # Parse date
                timestamp = datetime.now()
                if hasattr(entry, 'published_parsed'):
                    timestamp = datetime(*entry.published_parsed[:6])
                
                results.append(SentimentData(
                    source=source_name,
                    tier=tier,
                    sentiment_score=sentiment['compound'],
                    confidence=abs(sentiment['compound']),
                    text=entry.get('title', ''),
                    timestamp=timestamp,
                    metadata={
                        "link": entry.get('link', ''),
                        "author": entry.get('author', '')
                    }
                ))
            
            logger.info(f"Collected {len(results)} articles from {source_name}")
            
        except Exception as e:
            logger.error(f"RSS feed error for {source_name}: {e}")
        
        return results


class CoinGeckoCollector:
    """Collect sentiment indicators from CoinGecko (Tier 1)"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.tier = "tier1"
    
    async def fetch_market_sentiment(self, coin_id: str = "bitcoin") -> Optional[SentimentData]:
        """Fetch market sentiment indicators"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/coins/{coin_id}"
                params = {
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "true",
                    "developer_data": "false"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract sentiment signals
                        sentiment_votes = data.get('sentiment_votes_up_percentage', 50)
                        
                        # Convert to -1 to 1 scale
                        sentiment_score = (sentiment_votes - 50) / 50.0
                        
                        return SentimentData(
                            source="CoinGecko",
                            tier=self.tier,
                            sentiment_score=sentiment_score,
                            confidence=0.85,
                            text=f"CoinGecko sentiment votes: {sentiment_votes}% bullish",
                            timestamp=datetime.now(),
                            metadata={
                                "sentiment_votes_up": sentiment_votes,
                                "sentiment_votes_down": 100 - sentiment_votes
                            }
                        )
        except Exception as e:
            logger.error(f"CoinGecko fetch error: {e}")
            return None


# ============================================================================
# SENTIMENT AGGREGATOR
# ============================================================================

class SentimentAggregator:
    """Aggregate sentiment from multiple sources with tier-based weighting"""
    
    def __init__(self, tier_weights: Dict[str, float]):
        self.tier_weights = tier_weights
    
    def aggregate(self, sentiment_data: List[SentimentData]) -> AggregatedSentiment:
        """Aggregate sentiment with tier-based weighting"""
        
        if not sentiment_data:
            return AggregatedSentiment(
                overall_score=0.5,
                tier_scores={},
                source_scores={},
                total_samples=0,
                timestamp=datetime.now()
            )
        
        # Group by tier
        tier_groups = {}
        for data in sentiment_data:
            if data.tier not in tier_groups:
                tier_groups[data.tier] = []
            tier_groups[data.tier].append(data)
        
        # Calculate tier scores
        tier_scores = {}
        for tier, data_list in tier_groups.items():
            avg_score = sum(d.sentiment_score for d in data_list) / len(data_list)
            tier_scores[tier] = avg_score
        
        # Calculate overall weighted score
        weighted_sum = 0.0
        weight_total = 0.0
        
        for tier, score in tier_scores.items():
            weight = self.tier_weights.get(tier, 0.5)
            weighted_sum += score * weight
            weight_total += weight
        
        overall_score = weighted_sum / weight_total if weight_total > 0 else 0.0
        
        # Normalize to 0-1 scale (from -1 to 1)
        overall_score = (overall_score + 1.0) / 2.0
        
        # Calculate source scores
        source_scores = {}
        for data in sentiment_data:
            if data.source not in source_scores:
                source_scores[data.source] = []
            source_scores[data.source].append(data.sentiment_score)
        
        source_scores = {
            source: sum(scores) / len(scores)
            for source, scores in source_scores.items()
        }
        
        return AggregatedSentiment(
            overall_score=overall_score,
            tier_scores=tier_scores,
            source_scores=source_scores,
            total_samples=len(sentiment_data),
            timestamp=datetime.now()
        )
    
    def calculate_divergence(self, tier_scores: Dict[str, float]) -> Dict[str, float]:
        """Calculate divergence between tiers"""
        divergences = {}
        
        # Compare Tier 1 vs Tier 3 (institutional vs retail)
        if "tier1" in tier_scores and "tier3" in tier_scores:
            div = abs(tier_scores["tier1"] - tier_scores["tier3"])
            divergences["tier1_vs_tier3"] = div
        
        # Compare Tier 2 vs Tier 3 (mainstream vs retail)
        if "tier2" in tier_scores and "tier3" in tier_scores:
            div = abs(tier_scores["tier2"] - tier_scores["tier3"])
            divergences["tier2_vs_tier3"] = div
        
        return divergences


# ============================================================================
# MAIN SENTIMENT ENGINE
# ============================================================================

class SentimentEngine:
    """Main sentiment collection and aggregation engine"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Initialize collectors
        self.fear_greed = FearGreedCollector()
        self.coingecko = CoinGeckoCollector()
        self.rss_collector = RSSFeedCollector()
        
        # Initialize Reddit if credentials provided
        reddit_config = config.get('reddit', {})
        if reddit_config.get('enabled'):
            self.reddit = RedditCollector(
                client_id=os.getenv('REDDIT_CLIENT_ID', reddit_config.get('client_id', '')),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET', reddit_config.get('client_secret', '')),
                user_agent=reddit_config.get('user_agent', 'moonwalking-sentiment/1.0')
            )
        else:
            self.reddit = None
        
        # Initialize aggregator
        tier_weights = config.get('sentiment', {}).get('tier_weights', {
            'tier1': 0.85,
            'tier2': 0.70,
            'tier3': 0.50,
            'fringe': 0.30
        })
        self.aggregator = SentimentAggregator(tier_weights)
        
        # Cache
        self.cache = {}
        self.cache_ttl = config.get('sentiment', {}).get('cache_ttl', 300)
    
    async def collect_all_sources(self) -> List[SentimentData]:
        """Collect sentiment from all enabled sources"""
        all_data = []
        
        tasks = []
        
        # Tier 1: Fear & Greed
        tasks.append(self._collect_fear_greed())
        
        # Tier 1: CoinGecko
        tasks.append(self._collect_coingecko())
        
        # Tier 1/2: RSS Feeds
        for source in self.config.get('sources', {}).get('tier1', []):
            if source.get('enabled') and 'url' in source:
                tasks.append(self._collect_rss(source))
        
        for source in self.config.get('sources', {}).get('tier2', []):
            if source.get('enabled') and 'url' in source:
                tasks.append(self._collect_rss(source))
        
        # Tier 2/3: Reddit
        if self.reddit:
            reddit_config = self.config.get('reddit', {})
            for subreddit in reddit_config.get('subreddits', {}).get('tier2', []):
                tasks.append(self._collect_reddit(subreddit, 'tier2'))
            
            for subreddit in reddit_config.get('subreddits', {}).get('tier3', []):
                tasks.append(self._collect_reddit(subreddit, 'tier3'))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        for result in results:
            if isinstance(result, list):
                all_data.extend(result)
            elif isinstance(result, SentimentData):
                all_data.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Collection error: {result}")
        
        logger.info(f"Collected {len(all_data)} sentiment data points from {len(set(d.source for d in all_data))} sources")
        
        return all_data
    
    async def _collect_fear_greed(self) -> Optional[SentimentData]:
        """Collect Fear & Greed Index"""
        return await self.fear_greed.fetch()
    
    async def _collect_coingecko(self) -> Optional[SentimentData]:
        """Collect CoinGecko sentiment"""
        return await self.coingecko.fetch_market_sentiment()
    
    async def _collect_rss(self, source_config: Dict) -> List[SentimentData]:
        """Collect RSS feed"""
        return await self.rss_collector.fetch_feed(
            feed_url=source_config['url'],
            source_name=source_config['name'],
            tier=source_config.get('tier', 'tier2'),
            limit=50
        )
    
    async def _collect_reddit(self, subreddit: str, tier: str) -> List[SentimentData]:
        """Collect Reddit sentiment"""
        if not self.reddit:
            return []
        return await self.reddit.fetch_subreddit(subreddit, tier, post_limit=100)
    
    async def get_aggregated_sentiment(self, use_cache: bool = True) -> AggregatedSentiment:
        """Get aggregated sentiment from all sources"""
        
        # Check cache
        if use_cache and 'aggregated' in self.cache:
            cached_data, cache_time = self.cache['aggregated']
            if (datetime.now() - cache_time).total_seconds() < self.cache_ttl:
                logger.info("Returning cached sentiment data")
                return cached_data
        
        # Collect fresh data
        logger.info("Collecting fresh sentiment data from all sources...")
        sentiment_data = await self.collect_all_sources()
        
        # Aggregate
        aggregated = self.aggregator.aggregate(sentiment_data)
        
        # Cache
        self.cache['aggregated'] = (aggregated, datetime.now())
        
        return aggregated
