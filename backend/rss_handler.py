#!/usr/bin/env python3
"""
RSS Feed Handler for Crypto Sentiment Collection
Handles all RSS feed sources with rate limiting and caching
"""

import asyncio
import aiohttp
import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin
import hashlib
import json
from bs4 import BeautifulSoup
import re

class RSSHandler:
    def __init__(self, rss_config: List[Dict]):
        self.rss_config = rss_config
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.cache = {}
        self.rate_limits = {}
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'CryptoSentimentBot/1.0 (https://example.com/contact)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _clean_content(self, content: str) -> str:
        """Clean HTML and extract readable text"""
        if not content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection based on common patterns"""
        # Spanish indicators
        spanish_words = ['el', 'la', 'de', 'en', 'un', 'para', 'con', 'por', 'bitcoin', 'criptomoneda']
        spanish_count = sum(1 for word in spanish_words if word.lower() in text.lower())
        
        # Chinese indicators
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        
        if chinese_chars:
            return 'zh'
        elif spanish_count > 3:
            return 'es'
        else:
            return 'en'
    
    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key for URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def _fetch_feed(self, feed_config: Dict) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        url = feed_config['url']
        name = feed_config['name']
        base_trust = feed_config['base_trust']
        
        try:
            # Check rate limiting
            now = datetime.now()
            if url in self.rate_limits:
                last_fetch = self.rate_limits[url]
                if now - last_fetch < timedelta(minutes=5):  # 5 minute minimum between fetches
                    self.logger.debug(f"Rate limiting {name}, skipping")
                    return []
            
            self.logger.info(f"Fetching RSS feed: {name}")
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"HTTP {response.status} for {name}")
                    return []
                
                content = await response.text()
                
            # Update rate limit tracking
            self.rate_limits[url] = now
            
            # Parse feed
            feed = feedparser.parse(content)
            
            if not feed.entries:
                self.logger.warning(f"No entries found in {name}")
                return []
            
            items = []
            for entry in feed.entries[:10]:  # Limit to recent 10 items
                # Extract content
                content_text = ""
                if hasattr(entry, 'content') and entry.content:
                    content_text = entry.content[0].value
                elif hasattr(entry, 'description'):
                    content_text = entry.description
                elif hasattr(entry, 'summary'):
                    content_text = entry.summary
                
                # Clean content
                clean_content = self._clean_content(content_text)
                
                if len(clean_content) < 50:  # Skip very short content
                    continue
                
                # Parse date
                published = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                
                # Skip old articles (older than 24 hours)
                if now - published > timedelta(days=1):
                    continue
                
                # Detect language
                language = self._detect_language(clean_content)
                
                item = {
                    'source': name,
                    'title': getattr(entry, 'title', ''),
                    'content': clean_content,
                    'url': getattr(entry, 'link', ''),
                    'timestamp': published,
                    'base_trust': base_trust,
                    'language': language
                }
                items.append(item)
            
            self.logger.info(f"Collected {len(items)} items from {name}")
            return items
            
        except Exception as e:
            self.logger.error(f"Error fetching {name}: {str(e)}")
            return []
    
    async def _fetch_cryptopanic_api(self, config: Dict) -> List[Dict]:
        """Fetch from CryptoPanic API (special handling)"""
        if config.get('method') != 'api':
            return []
        
        url = config['url']
        name = config['name']
        base_trust = config['base_trust']
        
        try:
            # CryptoPanic API parameters
            api_key = os.environ.get('CRYPTOPANIC_API_KEY')
            if not api_key:
                self.logger.warning("CRYPTOPANIC_API_KEY not found in environment")
                return []

            params = {
                'auth_token': api_key,
                'public': 'true',
                'kind': 'news',
                'filter': 'hot',
                'page': 1
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    self.logger.error(f"CryptoPanic API error: {response.status}")
                    return []
                
                data = await response.json()
            
            items = []
            for article in data.get('results', [])[:15]:  # Limit to 15 items
                published = datetime.fromisoformat(
                    article['published_at'].replace('Z', '+00:00')
                )
                
                # Skip old articles
                if datetime.now() - published.replace(tzinfo=None) > timedelta(days=1):
                    continue
                
                content = f"{article['title']}. {article.get('description', '')}"
                clean_content = self._clean_content(content)
                
                if len(clean_content) < 30:
                    continue
                
                item = {
                    'source': name,
                    'title': article['title'],
                    'content': clean_content,
                    'url': article['url'],
                    'timestamp': published.replace(tzinfo=None),
                    'base_trust': base_trust,
                    'language': 'en',
                    'metadata': {
                        'votes': article.get('votes', {}),
                        'currencies': [c['code'] for c in article.get('currencies', [])]
                    }
                }
                items.append(item)
            
            self.logger.info(f"Collected {len(items)} items from CryptoPanic API")
            return items
            
        except Exception as e:
            self.logger.error(f"CryptoPanic API error: {str(e)}")
            return []
    
    async def fetch_all_feeds(self) -> List[Dict]:
        """Fetch all configured RSS feeds"""
        if not self.session:
            async with self:
                return await self._fetch_all_feeds_internal()
        else:
            return await self._fetch_all_feeds_internal()
    
    async def _fetch_all_feeds_internal(self) -> List[Dict]:
        """Internal method to fetch all feeds"""
        tasks = []
        
        for feed_config in self.rss_config:
            if feed_config.get('method') == 'api':
                # Special handling for API-based feeds
                tasks.append(self._fetch_cryptopanic_api(feed_config))
            else:
                # Regular RSS feeds
                tasks.append(self._fetch_feed(feed_config))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        all_items = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Feed fetch error: {result}")
            elif isinstance(result, list):
                all_items.extend(result)
        
        self.logger.info(f"Total RSS items collected: {len(all_items)}")
        return all_items
    
    def get_feed_stats(self) -> Dict:
        """Get statistics about RSS feed collection"""
        stats = {
            'total_feeds_configured': len(self.rss_config),
            'rate_limited_feeds': len(self.rate_limits),
            'cache_size': len(self.cache)
        }
        
        # Group by trust level
        trust_groups = {}
        for config in self.rss_config:
            trust = config['base_trust']
            trust_range = f"{int(trust * 10) / 10:.1f}"
            trust_groups[trust_range] = trust_groups.get(trust_range, 0) + 1
        
        stats['feeds_by_trust_level'] = trust_groups
        return stats

# Test function
async def test_rss_handler():
    """Test RSS handler with sample configuration"""
    test_config = [
        {
            'name': 'CoinDesk',
            'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'base_trust': 0.85
        },
        {
            'name': 'CoinTelegraph',
            'url': 'https://cointelegraph.com/rss',
            'base_trust': 0.80
        }
    ]
    
    async with RSSHandler(test_config) as handler:
        items = await handler.fetch_all_feeds()
        
        print(f"Collected {len(items)} items")
        for item in items[:3]:  # Show first 3 items
            print(f"\nSource: {item['source']}")
            print(f"Title: {item['title']}")
            print(f"Content: {item['content'][:200]}...")
            print(f"Trust: {item['base_trust']}")
            print(f"Language: {item['language']}")

if __name__ == "__main__":
    asyncio.run(test_rss_handler())