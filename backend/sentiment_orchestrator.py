#!/usr/bin/env python3
"""
Crypto Sentiment Data Orchestrator
Coordinates all sentiment data collection from multiple sources
"""

import asyncio
import logging
import yaml
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import aiohttp
import redis
from concurrent.futures import ThreadPoolExecutor

# Import our custom modules
from feeds.rss_handler import RSSHandler
from feeds.reddit_handler import RedditHandler
from feeds.social_apis import SocialAPIHandler
from feeds.custom_scrapers import CustomScraperHandler
from feeds.chinese_sources import ChineseSourceHandler
from feeds.telegram_handler import TelegramHandler
from analysis.sentiment_analyzer import SentimentAnalyzer
from analysis.aggregator import DataAggregator
from utils.rate_limiter import RateLimiter
from utils.cache_manager import CacheManager

@dataclass
class SentimentData:
    source: str
    source_type: str
    content: str
    sentiment_score: float
    confidence: float
    base_trust: float
    timestamp: datetime
    symbols: List[str]
    language: str = "en"
    metadata: Dict = None

class SentimentOrchestrator:
    def __init__(self, config_path: str = "config/sentiment_config.yaml"):
        self.config = self._load_config(config_path)
        self.setup_logging()
        
        # Initialize components
        self.cache = CacheManager()
        self.rate_limiter = RateLimiter()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.aggregator = DataAggregator(self.config)
        
        # Initialize data handlers
        self.rss_handler = RSSHandler(self.config['news_rss'])
        self.reddit_handler = RedditHandler(self.config['reddit'])
        self.social_handler = SocialAPIHandler(self.config['sentiment_apis'])
        self.custom_scraper = CustomScraperHandler(self.config['fringe_forums'])
        self.chinese_handler = ChineseSourceHandler(self.config['chinese_sources'])
        self.telegram_handler = TelegramHandler(self.config['telegram_channels'])
        
        # Processing settings
        self.processing_config = self.config.get('processing', {})
        self.symbol_map = self.config.get('symbol_map', {})
        
        # Storage
        self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.data_storage = []
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/sentiment_collector.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def collect_all_sources(self) -> List[SentimentData]:
        """Collect data from all configured sources"""
        self.logger.info("Starting data collection from all sources...")
        
        # Create tasks for all data sources
        tasks = []
        
        # RSS Feeds
        tasks.append(self._collect_rss_data())
        
        # Reddit
        tasks.append(self._collect_reddit_data())
        
        # Social APIs
        tasks.append(self._collect_social_api_data())
        
        # Custom scrapers (4chan, forums)
        tasks.append(self._collect_custom_scraper_data())
        
        # Chinese sources
        tasks.append(self._collect_chinese_data())
        
        # Telegram
        tasks.append(self._collect_telegram_data())
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and filter out exceptions
        all_data = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Collection error: {result}")
            elif isinstance(result, list):
                all_data.extend(result)
        
        self.logger.info(f"Collected {len(all_data)} sentiment data points")
        return all_data
    
    async def _collect_rss_data(self) -> List[SentimentData]:
        """Collect data from RSS feeds"""
        try:
            rss_data = await self.rss_handler.fetch_all_feeds()
            processed_data = []
            
            for item in rss_data:
                # Analyze sentiment
                sentiment_result = await self.sentiment_analyzer.analyze(
                    item['content'], 
                    item['language']
                )
                
                # Extract symbols
                symbols = self._extract_symbols(item['content'])
                
                sentiment_data = SentimentData(
                    source=item['source'],
                    source_type='rss',
                    content=item['content'],
                    sentiment_score=sentiment_result['score'],
                    confidence=sentiment_result['confidence'],
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    language=item['language'],
                    metadata={'url': item.get('url')}
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"RSS collection error: {e}")
            return []
    
    async def _collect_reddit_data(self) -> List[SentimentData]:
        """Collect data from Reddit sources"""
        try:
            reddit_data = await self.reddit_handler.fetch_all_subreddits()
            processed_data = []
            
            for item in reddit_data:
                sentiment_result = await self.sentiment_analyzer.analyze(
                    item['content'], 
                    'en'
                )
                
                symbols = self._extract_symbols(item['content'])
                
                sentiment_data = SentimentData(
                    source=f"r/{item['subreddit']}",
                    source_type='reddit',
                    content=item['content'],
                    sentiment_score=sentiment_result['score'],
                    confidence=sentiment_result['confidence'],
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    metadata={
                        'score': item.get('score'),
                        'comments': item.get('comments'),
                        'url': item.get('url')
                    }
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"Reddit collection error: {e}")
            return []
    
    async def _collect_social_api_data(self) -> List[SentimentData]:
        """Collect data from social APIs (LunarCrush, StockGeist)"""
        try:
            social_data = await self.social_handler.fetch_all_apis()
            processed_data = []
            
            for item in social_data:
                # Some APIs provide pre-calculated sentiment
                if 'sentiment_score' in item:
                    sentiment_score = item['sentiment_score']
                    confidence = item.get('confidence', 0.7)
                else:
                    sentiment_result = await self.sentiment_analyzer.analyze(
                        item['content'], 
                        'en'
                    )
                    sentiment_score = sentiment_result['score']
                    confidence = sentiment_result['confidence']
                
                symbols = item.get('symbols', self._extract_symbols(item['content']))
                
                sentiment_data = SentimentData(
                    source=item['source'],
                    source_type='social_api',
                    content=item['content'],
                    sentiment_score=sentiment_score,
                    confidence=confidence,
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    metadata=item.get('metadata', {})
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"Social API collection error: {e}")
            return []
    
    async def _collect_custom_scraper_data(self) -> List[SentimentData]:
        """Collect data from custom scrapers (4chan, forums)"""
        try:
            scraper_data = await self.custom_scraper.fetch_all_sources()
            processed_data = []
            
            for item in scraper_data:
                sentiment_result = await self.sentiment_analyzer.analyze(
                    item['content'], 
                    item.get('language', 'en')
                )
                
                symbols = self._extract_symbols(item['content'])
                
                sentiment_data = SentimentData(
                    source=item['source'],
                    source_type='custom_scraper',
                    content=item['content'],
                    sentiment_score=sentiment_result['score'],
                    confidence=sentiment_result['confidence'],
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    language=item.get('language', 'en'),
                    metadata=item.get('metadata', {})
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"Custom scraper collection error: {e}")
            return []
    
    async def _collect_chinese_data(self) -> List[SentimentData]:
        """Collect data from Chinese sources"""
        try:
            chinese_data = await self.chinese_handler.fetch_all_sources()
            processed_data = []
            
            for item in chinese_data:
                # Chinese sources require translation
                translated_content = await self.chinese_handler.translate_content(
                    item['content']
                )
                
                sentiment_result = await self.sentiment_analyzer.analyze(
                    translated_content, 
                    'en'  # Analyze translated content
                )
                
                symbols = self._extract_symbols(translated_content)
                
                sentiment_data = SentimentData(
                    source=item['source'],
                    source_type='chinese',
                    content=translated_content,
                    sentiment_score=sentiment_result['score'],
                    confidence=sentiment_result['confidence'] * 0.8,  # Lower confidence for translations
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    language='zh',
                    metadata={
                        'original_content': item['content'],
                        'translation_confidence': item.get('translation_confidence', 0.8)
                    }
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"Chinese sources collection error: {e}")
            return []
    
    async def _collect_telegram_data(self) -> List[SentimentData]:
        """Collect data from Telegram channels"""
        try:
            telegram_data = await self.telegram_handler.fetch_all_channels()
            processed_data = []
            
            for item in telegram_data:
                sentiment_result = await self.sentiment_analyzer.analyze(
                    item['content'], 
                    item.get('language', 'en')
                )
                
                symbols = self._extract_symbols(item['content'])
                
                sentiment_data = SentimentData(
                    source=item['source'],
                    source_type='telegram',
                    content=item['content'],
                    sentiment_score=sentiment_result['score'],
                    confidence=sentiment_result['confidence'],
                    base_trust=item['base_trust'],
                    timestamp=item['timestamp'],
                    symbols=symbols,
                    language=item.get('language', 'en'),
                    metadata=item.get('metadata', {})
                )
                processed_data.append(sentiment_data)
            
            return processed_data
        except Exception as e:
            self.logger.error(f"Telegram collection error: {e}")
            return []
    
    def _extract_symbols(self, content: str) -> List[str]:
        """Extract cryptocurrency symbols from content"""
        symbols = []
        content_lower = content.lower()
        
        for pattern, symbol in self.symbol_map.items():
            if pattern.lower() in content_lower:
                if symbol not in symbols:
                    symbols.append(symbol)
        
        return symbols
    
    async def process_and_aggregate(self, sentiment_data: List[SentimentData]) -> Dict:
        """Process and aggregate all sentiment data"""
        self.logger.info("Processing and aggregating sentiment data...")
        
        # Store raw data
        await self._store_raw_data(sentiment_data)
        
        # Aggregate by different dimensions
        aggregated = await self.aggregator.aggregate_sentiment(sentiment_data)
        
        # Detect divergences
        divergences = await self.aggregator.detect_divergences(sentiment_data)
        
        # Calculate overall metrics
        overall_metrics = await self.aggregator.calculate_overall_metrics(sentiment_data)
        
        result = {
            'timestamp': datetime.now(),
            'total_data_points': len(sentiment_data),
            'aggregated_sentiment': aggregated,
            'divergences': divergences,
            'overall_metrics': overall_metrics,
            'source_breakdown': self._get_source_breakdown(sentiment_data)
        }
        
        # Store aggregated results
        await self._store_aggregated_results(result)
        
        return result
    
    async def _store_raw_data(self, sentiment_data: List[SentimentData]):
        """Store raw sentiment data"""
        timestamp = datetime.now().isoformat()
        
        for data in sentiment_data:
            key = f"sentiment:raw:{timestamp}:{data.source}"
            value = json.dumps(asdict(data), default=str)
            self.redis_client.setex(key, 86400, value)  # 24 hour expiry
    
    async def _store_aggregated_results(self, results: Dict):
        """Store aggregated results"""
        timestamp = datetime.now().isoformat()
        key = f"sentiment:aggregated:{timestamp}"
        value = json.dumps(results, default=str)
        self.redis_client.setex(key, 86400 * 7, value)  # 7 day expiry
    
    def _get_source_breakdown(self, sentiment_data: List[SentimentData]) -> Dict:
        """Get breakdown of data by source type"""
        breakdown = {}
        for data in sentiment_data:
            source_type = data.source_type
            if source_type not in breakdown:
                breakdown[source_type] = {
                    'count': 0,
                    'avg_sentiment': 0,
                    'avg_confidence': 0,
                    'sources': []
                }
            
            breakdown[source_type]['count'] += 1
            breakdown[source_type]['avg_sentiment'] += data.sentiment_score
            breakdown[source_type]['avg_confidence'] += data.confidence
            
            if data.source not in breakdown[source_type]['sources']:
                breakdown[source_type]['sources'].append(data.source)
        
        # Calculate averages
        for source_type in breakdown:
            count = breakdown[source_type]['count']
            breakdown[source_type]['avg_sentiment'] /= count
            breakdown[source_type]['avg_confidence'] /= count
        
        return breakdown
    
    async def run_collection_cycle(self):
        """Run a complete collection and processing cycle"""
        start_time = datetime.now()
        self.logger.info("Starting sentiment collection cycle...")
        
        try:
            # Collect data from all sources
            sentiment_data = await self.collect_all_sources()
            
            if not sentiment_data:
                self.logger.warning("No sentiment data collected")
                return None
            
            # Process and aggregate
            results = await self.process_and_aggregate(sentiment_data)
            
            # Log completion
            duration = datetime.now() - start_time
            self.logger.info(f"Collection cycle completed in {duration.total_seconds():.2f} seconds")
            self.logger.info(f"Processed {len(sentiment_data)} data points")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Collection cycle error: {e}")
            return None
    
    async def start_continuous_collection(self, interval_minutes: int = 60):
        """Start continuous sentiment collection"""
        self.logger.info(f"Starting continuous collection every {interval_minutes} minutes...")
        
        while True:
            try:
                results = await self.run_collection_cycle()
                
                if results:
                    # Check for alerts
                    await self._check_alerts(results)
                
                # Wait for next cycle
                await asyncio.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                self.logger.info("Collection stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Continuous collection error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _check_alerts(self, results: Dict):
        """Check for alert conditions"""
        overall_sentiment = results['overall_metrics'].get('weighted_sentiment', 0)
        divergences = results['divergences']
        
        alerts = []
        
        # Extreme sentiment alerts
        if overall_sentiment <= 0.2:
            alerts.append({
                'type': 'extreme_fear',
                'message': f"Extreme fear detected: {overall_sentiment:.2f}",
                'severity': 'high'
            })
        elif overall_sentiment >= 0.8:
            alerts.append({
                'type': 'extreme_greed',
                'message': f"Extreme greed detected: {overall_sentiment:.2f}",
                'severity': 'high'
            })
        
        # Divergence alerts
        for divergence in divergences:
            if divergence['magnitude'] > 0.3:
                alerts.append({
                    'type': 'divergence',
                    'message': f"Significant divergence: {divergence['description']}",
                    'severity': 'medium',
                    'details': divergence
                })
        
        # Log alerts
        for alert in alerts:
            self.logger.warning(f"ALERT: {alert['message']}")
        
        # Store alerts
        if alerts:
            timestamp = datetime.now().isoformat()
            key = f"sentiment:alerts:{timestamp}"
            value = json.dumps(alerts, default=str)
            self.redis_client.setex(key, 86400 * 7, value)  # 7 day expiry

async def main():
    """Main entry point"""
    orchestrator = SentimentOrchestrator()
    
    # Run single collection for testing
    # results = await orchestrator.run_collection_cycle()
    # print(json.dumps(results, indent=2, default=str))
    
    # Start continuous collection
    await orchestrator.start_continuous_collection(interval_minutes=30)

if __name__ == "__main__":
    asyncio.run(main())