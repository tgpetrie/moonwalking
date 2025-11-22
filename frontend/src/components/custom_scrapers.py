#!/usr/bin/env python3
"""
Custom Scrapers Handler for Crypto Sentiment Collection
Handles 4chan, forums, and other sources without APIs
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
import json
import time
import random
from urllib.parse import urljoin, urlparse

class CustomScraperHandler:
    def __init__(self, scrapers_config: List[Dict]):
        self.scrapers_config = scrapers_config
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.scraped_content_cache = {}
        
        # Rotating user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=3)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=45),
            headers={'User-Agent': random.choice(self.user_agents)}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _clean_text_content(self, text: str) -> str:
        """Clean scraped text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common board artifacts
        text = re.sub(r'>>\d+', '', text)  # Remove post references
        text = re.sub(r'Anonymous \d{2}/\d{2}/\d{2}', '', text)  # Remove anonymous headers
        text = re.sub(r'No\.\d+', '', text)  # Remove post numbers
        
        # Remove URLs for privacy/safety
        text = re.sub(r'https?://[^\s]+', '[URL]', text)
        
        return text.strip()
    
    def _extract_crypto_signals(self, content: str) -> Dict:
        """Extract crypto-related signals from content"""
        content_lower = content.lower()
        
        signals = {
            'bull_indicators': 0,
            'bear_indicators': 0,
            'crypto_mentions': [],
            'urgency_level': 0,
            'speculation_level': 0
        }
        
        # Bull indicators
        bull_keywords = ['moon', 'pump', 'bullish', 'buy', 'long', 'hodl', 'diamond hands', 'to the moon']
        signals['bull_indicators'] = sum(1 for keyword in bull_keywords if keyword in content_lower)
        
        # Bear indicators
        bear_keywords = ['dump', 'crash', 'bearish', 'sell', 'short', 'rekt', 'bear market', 'dead cat']
        signals['bear_indicators'] = sum(1 for keyword in bear_keywords if keyword in content_lower)
        
        # Crypto mentions
        crypto_patterns = ['btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana', 'avax', 'ada', 'matic', 'doge']
        for pattern in crypto_patterns:
            if pattern in content_lower:
                signals['crypto_mentions'].append(pattern.upper())
        
        # Urgency indicators
        urgency_keywords = ['urgent', 'breaking', 'happening', 'now', 'alert', 'immediate']
        signals['urgency_level'] = sum(1 for keyword in urgency_keywords if keyword in content_lower)
        
        # Speculation level
        spec_keywords = ['prediction', 'forecast', 'target', 'analysis', 'TA', 'chart', 'pattern']
        signals['speculation_level'] = sum(1 for keyword in spec_keywords if keyword in content_lower)
        
        return signals
    
    async def _scrape_4chan_biz(self) -> List[Dict]:
        """Scrape 4chan /biz/ board for crypto sentiment"""
        try:
            self.logger.info("Scraping 4chan /biz/")
            
            # Get catalog page first
            catalog_url = "https://boards.4channel.org/biz/catalog.json"
            
            async with self.session.get(catalog_url) as response:
                if response.status != 200:
                    self.logger.error(f"4chan catalog fetch failed: {response.status}")
                    return []
                
                catalog_data = await response.json()
            
            # Find crypto-related threads
            crypto_threads = []
            for page in catalog_data:
                for thread in page.get('threads', []):
                    if 'sub' in thread or 'com' in thread:
                        title = thread.get('sub', '') + ' ' + thread.get('com', '')
                        if self._is_crypto_related(title):
                            crypto_threads.append({
                                'no': thread['no'],
                                'title': thread.get('sub', 'No title'),
                                'replies': thread.get('replies', 0),
                                'images': thread.get('images', 0)
                            })
            
            # Sort by activity and take top threads
            crypto_threads.sort(key=lambda x: x['replies'], reverse=True)
            top_threads = crypto_threads[:5]  # Top 5 most active crypto threads
            
            items = []
            
            for thread in top_threads:
                try:
                    # Fetch thread content
                    thread_url = f"https://a.4cdn.org/biz/thread/{thread['no']}.json"
                    
                    async with self.session.get(thread_url) as response:
                        if response.status != 200:
                            continue
                        
                        thread_data = await response.json()
                    
                    # Process posts in thread
                    posts = thread_data.get('posts', [])[:20]  # First 20 posts
                    
                    for post in posts:
                        if 'com' not in post:
                            continue
                        
                        content = BeautifulSoup(post['com'], 'html.parser').get_text()
                        clean_content = self._clean_text_content(content)
                        
                        if len(clean_content) < 30:
                            continue
                        
                        if not self._is_crypto_related(clean_content):
                            continue
                        
                        # Extract signals
                        signals = self._extract_crypto_signals(clean_content)
                        
                        # Calculate sentiment based on signals
                        bull_score = signals['bull_indicators']
                        bear_score = signals['bear_indicators']
                        total_signals = bull_score + bear_score
                        
                        if total_signals > 0:
                            sentiment_score = bull_score / total_signals
                        else:
                            sentiment_score = 0.5  # Neutral
                        
                        post_time = datetime.fromtimestamp(post.get('time', time.time()))
                        
                        item = {
                            'source': '4chan /biz/',
                            'content': clean_content,
                            'timestamp': post_time,
                            'base_trust': 0.40,  # Low trust for 4chan
                            'symbols': signals['crypto_mentions'],
                            'metadata': {
                                'thread_title': thread['title'],
                                'post_no': post.get('no'),
                                'replies_count': thread['replies'],
                                'signals': signals,
                                'calculated_sentiment': sentiment_score
                            }
                        }
                        items.append(item)
                    
                    # Delay between thread requests
                    await asyncio.sleep(random.uniform(1, 3))
                
                except Exception as e:
                    self.logger.error(f"Error processing 4chan thread {thread['no']}: {e}")
                    continue
            
            self.logger.info(f"Collected {len(items)} items from 4chan /biz/")
            return items
            
        except Exception as e:
            self.logger.error(f"4chan scraping error: {str(e)}")
            return []
    
    def _is_crypto_related(self, text: str) -> bool:
        """Check if text is crypto-related"""
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'altcoin',
            'pump', 'dump', 'moon', 'hodl', 'defi', 'nft', 'solana',
            'avalanche', 'cardano', 'polygon', 'chainlink', 'trading'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in crypto_keywords)
    
    async def _scrape_bitcointalk_altcoin(self) -> List[Dict]:
        """Scrape BitcoinTalk altcoin discussion forum"""
        try:
            self.logger.info("Scraping BitcoinTalk Altcoin forum")
            
            # BitcoinTalk altcoin board
            url = "https://bitcointalk.org/index.php?board=67.0"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"BitcoinTalk fetch failed: {response.status}")
                    return []
                
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find topic rows
            topic_rows = soup.find_all('tr', class_='windowbg')
            items = []
            
            for row in topic_rows[:10]:  # Top 10 topics
                try:
                    # Extract topic title and link
                    title_link = row.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text().strip()
                    topic_url = urljoin(url, title_link.get('href', ''))
                    
                    if not self._is_crypto_related(title):
                        continue
                    
                    # Extract post count and last post info
                    stats_cells = row.find_all('td')
                    
                    content = f"BitcoinTalk discussion: {title}"
                    
                    # Extract basic sentiment from title
                    signals = self._extract_crypto_signals(title)
                    bull_score = signals['bull_indicators']
                    bear_score = signals['bear_indicators']
                    total_signals = bull_score + bear_score
                    
                    if total_signals > 0:
                        sentiment_score = bull_score / total_signals
                    else:
                        sentiment_score = 0.5
                    
                    item = {
                        'source': 'BitcoinTalk Altcoin',
                        'content': content,
                        'timestamp': datetime.now(),  # BitcoinTalk timestamps are complex to parse
                        'base_trust': 0.45,
                        'symbols': signals['crypto_mentions'],
                        'metadata': {
                            'topic_url': topic_url,
                            'title': title,
                            'signals': signals,
                            'calculated_sentiment': sentiment_score
                        }
                    }
                    items.append(item)
                
                except Exception as e:
                    self.logger.error(f"Error processing BitcoinTalk topic: {e}")
                    continue
            
            self.logger.info(f"Collected {len(items)} items from BitcoinTalk")
            return items
            
        except Exception as e:
            self.logger.error(f"BitcoinTalk scraping error: {str(e)}")
            return []
    
    async def _scrape_rankia_crypto(self) -> List[Dict]:
        """Scrape Rankia crypto forums (Spanish)"""
        try:
            self.logger.info("Scraping Rankia crypto forum")
            
            url = "https://www.rankia.com/foros/criptomonedas"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"Rankia fetch failed: {response.status}")
                    return []
                
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find forum topics
            topics = soup.find_all('div', class_='topic-item')
            items = []
            
            for topic in topics[:8]:  # Top 8 topics
                try:
                    title_elem = topic.find('h3') or topic.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    if not self._is_crypto_related(title):
                        continue
                    
                    # Extract any preview text
                    preview_elem = topic.find('p') or topic.find('div', class_='preview')
                    preview = preview_elem.get_text().strip() if preview_elem else ""
                    
                    content = f"{title}. {preview}"
                    clean_content = self._clean_text_content(content)
                    
                    if len(clean_content) < 20:
                        continue
                    
                    # Extract signals
                    signals = self._extract_crypto_signals(clean_content)
                    
                    # Calculate sentiment
                    bull_score = signals['bull_indicators']
                    bear_score = signals['bear_indicators']
                    total_signals = bull_score + bear_score
                    
                    if total_signals > 0:
                        sentiment_score = bull_score / total_signals
                    else:
                        sentiment_score = 0.5
                    
                    item = {
                        'source': 'Rankia Crypto',
                        'content': clean_content,
                        'timestamp': datetime.now(),
                        'base_trust': 0.55,
                        'language': 'es',
                        'symbols': signals['crypto_mentions'],
                        'metadata': {
                            'title': title,
                            'signals': signals,
                            'calculated_sentiment': sentiment_score
                        }
                    }
                    items.append(item)
                
                except Exception as e:
                    self.logger.error(f"Error processing Rankia topic: {e}")
                    continue
            
            self.logger.info(f"Collected {len(items)} items from Rankia")
            return items
            
        except Exception as e:
            self.logger.error(f"Rankia scraping error: {str(e)}")
            return []
    
    async def fetch_all_sources(self) -> List[Dict]:
        """Fetch data from all configured custom scrapers"""
        if not self.session:
            async with self:
                return await self._fetch_all_sources_internal()
        else:
            return await self._fetch_all_sources_internal()
    
    async def _fetch_all_sources_internal(self) -> List[Dict]:
        """Internal method to fetch from all custom sources"""
        tasks = []
        
        for scraper_config in self.scrapers_config:
            scraper_name = scraper_config.get('name', '')
            
            if '4chan' in scraper_name.lower():
                tasks.append(self._scrape_4chan_biz())
            elif 'bitcointalk' in scraper_name.lower():
                tasks.append(self._scrape_bitcointalk_altcoin())
            elif 'rankia' in scraper_name.lower():
                tasks.append(self._scrape_rankia_crypto())
        
        # Execute all tasks with delays
        all_items = []
        
        for task in tasks:
            try:
                result = await task
                if isinstance(result, list):
                    all_items.extend(result)
                
                # Delay between different scrapers to be respectful
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                self.logger.error(f"Custom scraper task error: {e}")
        
        self.logger.info(f"Total custom scraper items collected: {len(all_items)}")
        return all_items
    
    def get_scraper_stats(self) -> Dict:
        """Get statistics about custom scrapers"""
        stats = {
            'configured_scrapers': len(self.scrapers_config),
            'cache_size': len(self.scraped_content_cache),
            'scrapers_by_type': {}
        }
        
        # Group by scraper type
        for config in self.scrapers_config:
            scraper_name = config.get('name', 'unknown')
            scraper_type = 'forum' if 'forum' in scraper_name.lower() else 'board'
            
            if scraper_type not in stats['scrapers_by_type']:
                stats['scrapers_by_type'][scraper_type] = []
            stats['scrapers_by_type'][scraper_type].append(scraper_name)
        
        return stats

# Test function
async def test_custom_scrapers():
    """Test custom scrapers handler"""
    test_config = [
        {
            'name': '4chan /biz/',
            'base_trust': 0.40
        },
        {
            'name': 'BitcoinTalk Altcoin',
            'base_trust': 0.45
        }
    ]
    
    async with CustomScraperHandler(test_config) as handler:
        items = await handler.fetch_all_sources()
        
        print(f"Collected {len(items)} items from custom scrapers")
        for item in items[:3]:  # Show first 3 items
            print(f"\nSource: {item['source']}")
            print(f"Content: {item['content'][:200]}...")
            print(f"Trust: {item['base_trust']}")
            print(f"Symbols: {item['symbols']}")

if __name__ == "__main__":
    asyncio.run(test_custom_scrapers())