import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import re
from collections import defaultdict

class SocialSentimentAnalyzer:
    """
    Social sentiment analysis for cryptocurrencies
    Note: This is a mock implementation. In production, you would integrate with:
    - Twitter API v2
    - Reddit API
    - Discord APIs
    - Telegram APIs
    - News sentiment APIs
    """
    
    def __init__(self):
        self.sentiment_cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def get_social_sentiment(self, symbol: str) -> Dict:
        """Get social sentiment analysis for a cryptocurrency"""
        cache_key = f"sentiment_{symbol}"
        now = datetime.now()
        
        # Check cache first
        if cache_key in self.sentiment_cache:
            cached_data, cache_time = self.sentiment_cache[cache_key]
            if (now - cache_time).total_seconds() < self.cache_duration:
                return cached_data
        
        # Generate mock sentiment data (replace with real API calls)
        sentiment_data = self._generate_mock_sentiment(symbol)
        
        # Cache the result
        self.sentiment_cache[cache_key] = (sentiment_data, now)
        
        return sentiment_data
    
    def _generate_mock_sentiment(self, symbol: str) -> Dict:
        """Generate mock sentiment data for demonstration"""
        import random
        
        # Simulate different sentiment patterns for different coins
        base_sentiment = 0.5  # Neutral starting point
        
        # Adjust base sentiment for well-known coins
        if symbol.upper() in ['BTC', 'BITCOIN']:
            base_sentiment = 0.65  # Generally positive
        elif symbol.upper() in ['ETH', 'ETHEREUM']:
            base_sentiment = 0.6
        elif symbol.upper() in ['DOGE', 'DOGECOIN']:
            base_sentiment = 0.55  # Meme coin volatility
        
        # Add some randomness
        sentiment_score = base_sentiment + random.uniform(-0.2, 0.2)
        sentiment_score = max(0, min(1, sentiment_score))  # Clamp to 0-1
        
        # Generate mock social metrics
        twitter_mentions = random.randint(50, 5000)
        reddit_posts = random.randint(10, 500)
        telegram_messages = random.randint(100, 2000)
        
        # Generate sentiment distribution
        positive_ratio = sentiment_score * 0.8 + random.uniform(0, 0.2)
        negative_ratio = (1 - sentiment_score) * 0.6 + random.uniform(0, 0.2)
        neutral_ratio = 1 - positive_ratio - negative_ratio
        
        # Ensure ratios are valid
        total = positive_ratio + negative_ratio + neutral_ratio
        positive_ratio /= total
        negative_ratio /= total
        neutral_ratio /= total
        
        # Generate mock trending topics/keywords
        trending_keywords = self._get_trending_keywords(symbol)
        
        # Generate mock influencer mentions
        influencer_mentions = self._get_mock_influencer_mentions(symbol)
        
        return {
            'symbol': symbol.upper(),
            'overall_sentiment': {
                'score': round(sentiment_score, 3),
                'label': self._get_sentiment_label(sentiment_score),
                'confidence': round(random.uniform(0.7, 0.95), 3)
            },
            'sentiment_distribution': {
                'positive': round(positive_ratio, 3),
                'negative': round(negative_ratio, 3),
                'neutral': round(neutral_ratio, 3)
            },
            'social_metrics': {
                'twitter': {
                    'mentions_24h': twitter_mentions,
                    'sentiment_score': round(sentiment_score + random.uniform(-0.1, 0.1), 3),
                    'trending_rank': random.randint(1, 100) if twitter_mentions > 500 else None
                },
                'reddit': {
                    'posts_24h': reddit_posts,
                    'comments_24h': reddit_posts * random.randint(3, 15),
                    'sentiment_score': round(sentiment_score + random.uniform(-0.15, 0.15), 3),
                    'top_subreddits': [f'r/{symbol}', 'r/CryptoCurrency', 'r/altcoins'][:random.randint(1, 3)]
                },
                'telegram': {
                    'messages_24h': telegram_messages,
                    'active_groups': random.randint(5, 50),
                    'sentiment_score': round(sentiment_score + random.uniform(-0.1, 0.1), 3)
                }
            },
            'trending_topics': trending_keywords,
            'influencer_mentions': influencer_mentions,
            'fear_greed_index': random.randint(20, 80),
            'volume_correlation': round(random.uniform(0.3, 0.8), 3),
            'price_correlation': round(random.uniform(-0.2, 0.7), 3),
            'last_updated': datetime.now().isoformat(),
            'data_sources': ['Twitter', 'Reddit', 'Telegram', 'Discord'],
            'note': 'Mock data for demonstration - integrate with real social APIs'
        }
    
    def _get_sentiment_label(self, score: float) -> str:
        """Convert numerical sentiment score to label"""
        if score >= 0.7:
            return 'Very Bullish'
        elif score >= 0.6:
            return 'Bullish'
        elif score >= 0.4:
            return 'Neutral'
        elif score >= 0.3:
            return 'Bearish'
        else:
            return 'Very Bearish'
    
    def _get_trending_keywords(self, symbol: str) -> List[Dict]:
        """Generate mock trending keywords"""
        import random
        
        base_keywords = [
            f'${symbol.upper()}', f'{symbol.upper()}USD', 'hodl', 'buy', 'sell', 
            'moon', 'dip', 'pump', 'dump', 'bullish', 'bearish'
        ]
        
        # Add symbol-specific keywords
        if symbol.upper() == 'BTC':
            base_keywords.extend(['bitcoin', 'btc', 'digital gold', 'store of value'])
        elif symbol.upper() == 'ETH':
            base_keywords.extend(['ethereum', 'defi', 'smart contracts', 'gas fees'])
        elif symbol.upper() == 'DOGE':
            base_keywords.extend(['dogecoin', 'meme coin', 'elon', 'tesla'])
        
        # Generate trending data
        trending = []
        selected_keywords = random.sample(base_keywords, min(8, len(base_keywords)))
        
        for keyword in selected_keywords:
            trending.append({
                'keyword': keyword,
                'mentions': random.randint(10, 1000),
                'sentiment_score': round(random.uniform(0.2, 0.8), 2),
                'growth_24h': round(random.uniform(-50, 200), 1)  # Percentage change
            })
        
        return sorted(trending, key=lambda x: x['mentions'], reverse=True)[:6]
    
    def _get_mock_influencer_mentions(self, symbol: str) -> List[Dict]:
        """Generate mock influencer mentions"""
        import random
        
        mock_influencers = [
            {'name': 'CryptoAnalyst', 'followers': 145000, 'verified': True},
            {'name': 'BlockchainExpert', 'followers': 89000, 'verified': True},
            {'name': 'AltcoinDaily', 'followers': 230000, 'verified': False},
            {'name': 'CoinBureau', 'followers': 180000, 'verified': True},
            {'name': 'TheCryptoDog', 'followers': 95000, 'verified': False}
        ]
        
        mentions = []
        num_mentions = random.randint(1, 3)
        
        for influencer in random.sample(mock_influencers, num_mentions):
            sentiment_options = ['bullish', 'bearish', 'neutral']
            sentiment = random.choice(sentiment_options)
            
            mentions.append({
                'influencer': influencer['name'],
                'followers': influencer['followers'],
                'verified': influencer['verified'],
                'sentiment': sentiment,
                'engagement': random.randint(50, 5000),
                'timestamp': (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat(),
                'preview': f"Just analyzed {symbol.upper()} and I'm feeling {sentiment} about the current setup..."
            })
        
        return mentions

# Global instance
social_analyzer = SocialSentimentAnalyzer()

def get_social_sentiment(symbol: str) -> Dict:
    """Get social sentiment analysis for a symbol"""
    return social_analyzer.get_social_sentiment(symbol)