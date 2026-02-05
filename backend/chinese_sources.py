#!/usr/bin/env python3
"""
Chinese Sources Handler for Crypto Sentiment Collection
Handles Weibo, 8btc, and other Chinese crypto sources with translation
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
from googletrans import Translator
import hashlib

class ChineseSourceHandler:
    def __init__(self, chinese_config: List[Dict]):
        self.chinese_config = chinese_config
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.translator = Translator()
        self.translation_cache = {}
        
        # User agents for Chinese sites
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        ]
        
        # Chinese crypto keywords
        self.chinese_crypto_terms = {
            '比特币': 'Bitcoin',
            '以太坊': 'Ethereum', 
            '加密货币': 'Cryptocurrency',
            '区块链': 'Blockchain',
            '数字货币': 'Digital Currency',
            '虚拟货币': 'Virtual Currency',
            '挖矿': 'Mining',
            '交易所': 'Exchange',
            '钱包': 'Wallet',
            '代币': 'Token',
            '智能合约': 'Smart Contract',
            'DeFi': 'DeFi',
            'NFT': 'NFT'
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(limit=5, limit_per_host=2)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60),
            headers={
                'User-Agent': random.choice(self.user_agents),
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _clean_chinese_text(self, text: str) -> str:
        """Clean Chinese text content"""
        if not text:
            return ""
        
        # Remove common Weibo artifacts
        text = re.sub(r'@[\w\u4e00-\u9fff]+', '', text)  # Remove @mentions
        text = re.sub(r'#[\w\u4e00-\u9fff]+#', '', text)  # Remove hashtags
        text = re.sub(r'https?://[^\s]+', '', text)  # Remove URLs
        text = re.sub(r'【.*?】', '', text)  # Remove bracketed content
        
        # Clean whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _is_crypto_related_chinese(self, text: str) -> bool:
        """Check if Chinese text is crypto-related"""
        return any(term in text for term in self.chinese_crypto_terms.keys())
    
    def _extract_chinese_crypto_mentions(self, text: str) -> List[str]:
        """Extract cryptocurrency mentions from Chinese text"""
        mentions = []
        
        for chinese_term, english_term in self.chinese_crypto_terms.items():
            if chinese_term in text:
                mentions.append(english_term.upper())
        
        # Also check for English terms in Chinese text
        english_patterns = ['BTC', 'ETH', 'Bitcoin', 'Ethereum']
        for pattern in english_patterns:
            if pattern.lower() in text.lower():
                mentions.append(pattern.upper())
        
        return list(set(mentions))  # Remove duplicates
    
    async def translate_content(self, chinese_text: str) -> str:
        """Translate Chinese content to English with caching"""
        if not chinese_text:
            return ""
        
        # Check cache first
        cache_key = hashlib.md5(chinese_text.encode()).hexdigest()
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        try:
            # Use Google Translate
            translated = self.translator.translate(chinese_text, src='zh', dest='en')
            translated_text = translated.text
            
            # Cache the translation
            self.translation_cache[cache_key] = translated_text
            
            # Small delay to avoid hitting rate limits
            await asyncio.sleep(0.1)
            
            return translated_text
            
        except Exception as e:
            self.logger.error(f"Translation error: {str(e)}")
            # Return original text if translation fails
            return chinese_text
    
    async def _scrape_weibo_crypto(self) -> List[Dict]:
        """Scrape Weibo for crypto-related content"""
        try:
            self.logger.info("Scraping Weibo for crypto content")
            
            # Search for Bitcoin hashtag on Weibo
            search_url = "https://m.weibo.cn/api/container/getIndex"
            params = {
                'type': 'wb',
                'queryVal': '比特币',  # Bitcoin in Chinese
                'featurecode': '20000320',
                'luicode': '10000011',
                'lfid': '100103type%3D1%26q%3D比特币'
            }
            
            async with self.session.get(search_url, params=params) as response:
                if response.status != 200:
                    self.logger.error(f"Weibo search failed: {response.status}")
                    return []
                
                try:
                    data = await response.json()
                except:
                    # Weibo might return HTML instead of JSON sometimes
                    self.logger.warning("Weibo returned non-JSON response")
                    return await self._scrape_weibo_html_fallback()
            
            items = []
            cards = data.get('data', {}).get('cards', [])
            
            for card in cards[:10]:  # Limit to 10 posts
                if card.get('card_type') != 9:  # Only text posts
                    continue
                
                mblog = card.get('mblog', {})
                if not mblog:
                    continue
                
                # Extract content
                text = mblog.get('text', '')
                if not text:
                    continue
                
                # Clean HTML tags
                soup = BeautifulSoup(text, 'html.parser')
                clean_text = soup.get_text()
                clean_text = self._clean_chinese_text(clean_text)
                
                if len(clean_text) < 20:
                    continue
                
                if not self._is_crypto_related_chinese(clean_text):
                    continue
                
                # Extract crypto mentions
                crypto_mentions = self._extract_chinese_crypto_mentions(clean_text)
                
                # Get post metadata
                created_at = mblog.get('created_at', '')
                user_info = mblog.get('user', {})
                
                # Translate content
                translated_text = await self.translate_content(clean_text)
                
                item = {
                    'source': 'Weibo',
                    'content': clean_text,
                    'translated_content': translated_text,
                    'timestamp': datetime.now(),  # Weibo timestamps need parsing
                    'base_trust': 0.45,
                    'language': 'zh',
                    'symbols': crypto_mentions,
                    'metadata': {
                        'user_name': user_info.get('screen_name', ''),
                        'user_followers': user_info.get('followers_count', 0),
                        'reposts_count': mblog.get('reposts_count', 0),
                        'comments_count': mblog.get('comments_count', 0),
                        'attitudes_count': mblog.get('attitudes_count', 0),
                        'original_text': clean_text,
                        'translation_confidence': 0.8
                    }
                }
                items.append(item)
            
            self.logger.info(f"Collected {len(items)} items from Weibo")
            return items
            
        except Exception as e:
            self.logger.error(f"Weibo scraping error: {str(e)}")
            return []
    
    async def _scrape_weibo_html_fallback(self) -> List[Dict]:
        """Fallback HTML scraping for Weibo"""
        try:
            # Try the web version
            search_url = "https://s.weibo.com/weibo/%23比特币%23"
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    return []
                
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find post elements (this may need adjustment based on Weibo's current HTML structure)
            posts = soup.find_all('div', class_='card-wrap')
            items = []
            
            for post in posts[:5]:  # Limit to 5 posts
                try:
                    text_elem = post.find('p', class_='txt') or post.find('div', class_='txt')
                    if not text_elem:
                        continue
                    
                    text = text_elem.get_text().strip()
                    clean_text = self._clean_chinese_text(text)
                    
                    if len(clean_text) < 20:
                        continue
                    
                    if not self._is_crypto_related_chinese(clean_text):
                        continue
                    
                    crypto_mentions = self._extract_chinese_crypto_mentions(clean_text)
                    translated_text = await self.translate_content(clean_text)
                    
                    item = {
                        'source': 'Weibo HTML',
                        'content': clean_text,
                        'translated_content': translated_text,
                        'timestamp': datetime.now(),
                        'base_trust': 0.40,  # Lower trust for HTML scraping
                        'language': 'zh',
                        'symbols': crypto_mentions,
                        'metadata': {
                            'scraping_method': 'html_fallback',
                            'original_text': clean_text,
                            'translation_confidence': 0.8
                        }
                    }
                    items.append(item)
                
                except Exception as e:
                    self.logger.error(f"Error processing Weibo post: {e}")
                    continue
            
            return items
            
        except Exception as e:
            self.logger.error(f"Weibo HTML fallback error: {str(e)}")
            return []
    
    async def _scrape_8btc_forum(self) -> List[Dict]:
        """Scrape 8btc.com forum for crypto discussions"""
        try:
            self.logger.info("Scraping 8btc forum")
            
            url = "https://www.8btc.com/"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"8btc fetch failed: {response.status}")
                    return []
                
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find article elements
            articles = soup.find_all('div', class_='article-item') or soup.find_all('article')
            items = []
            
            for article in articles[:8]:  # Limit to 8 articles
                try:
                    # Extract title
                    title_elem = article.find('h3') or article.find('h2') or article.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    # Extract description/summary if available
                    desc_elem = article.find('p') or article.find('div', class_='desc')
                    description = desc_elem.get_text().strip() if desc_elem else ""
                    
                    content = f"{title}. {description}"
                    clean_content = self._clean_chinese_text(content)
                    
                    if len(clean_content) < 20:
                        continue
                    
                    if not self._is_crypto_related_chinese(clean_content):
                        continue
                    
                    crypto_mentions = self._extract_chinese_crypto_mentions(clean_content)
                    translated_content = await self.translate_content(clean_content)
                    
                    item = {
                        'source': '8btc Forum',
                        'content': clean_content,
                        'translated_content': translated_content,
                        'timestamp': datetime.now(),
                        'base_trust': 0.50,
                        'language': 'zh',
                        'symbols': crypto_mentions,
                        'metadata': {
                            'title': title,
                            'original_text': clean_content,
                            'translation_confidence': 0.8
                        }
                    }
                    items.append(item)
                
                except Exception as e:
                    self.logger.error(f"Error processing 8btc article: {e}")
                    continue
            
            self.logger.info(f"Collected {len(items)} items from 8btc")
            return items
            
        except Exception as e:
            self.logger.error(f"8btc scraping error: {str(e)}")
            return []
    
    async def _scrape_jinse_finance(self) -> List[Dict]:
        """Scrape Jinse (金色财经) for crypto news"""
        try:
            self.logger.info("Scraping Jinse Finance")
            
            url = "https://www.jinse.com/"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"Jinse fetch failed: {response.status}")
                    return []
                
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find news items
            news_items = soup.find_all('div', class_='news-item') or soup.find_all('li', class_='item')
            items = []
            
            for news_item in news_items[:6]:  # Limit to 6 news items
                try:
                    # Extract title and content
                    title_elem = news_item.find('h4') or news_item.find('h3') or news_item.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    # Look for summary or description
                    summary_elem = news_item.find('p', class_='summary') or news_item.find('div', class_='desc')
                    summary = summary_elem.get_text().strip() if summary_elem else ""
                    
                    content = f"{title}. {summary}"
                    clean_content = self._clean_chinese_text(content)
                    
                    if len(clean_content) < 15:
                        continue
                    
                    if not self._is_crypto_related_chinese(clean_content):
                        continue
                    
                    crypto_mentions = self._extract_chinese_crypto_mentions(clean_content)
                    translated_content = await self.translate_content(clean_content)
                    
                    item = {
                        'source': 'Jinse Finance',
                        'content': clean_content,
                        'translated_content': translated_content,
                        'timestamp': datetime.now(),
                        'base_trust': 0.55,
                        'language': 'zh',
                        'symbols': crypto_mentions,
                        'metadata': {
                            'title': title,
                            'original_text': clean_content,
                            'translation_confidence': 0.85
                        }
                    }
                    items.append(item)
                
                except Exception as e:
                    self.logger.error(f"Error processing Jinse news: {e}")
                    continue
            
            self.logger.info(f"Collected {len(items)} items from Jinse")
            return items
            
        except Exception as e:
            self.logger.error(f"Jinse scraping error: {str(e)}")
            return []
    
    async def fetch_all_sources(self) -> List[Dict]:
        """Fetch data from all configured Chinese sources"""
        if not self.session:
            async with self:
                return await self._fetch_all_sources_internal()
        else:
            return await self._fetch_all_sources_internal()
    
    async def _fetch_all_sources_internal(self) -> List[Dict]:
        """Internal method to fetch from all Chinese sources"""
        tasks = []
        
        for source_config in self.chinese_config:
            source_name = source_config.get('name', '').lower()
            
            if 'weibo' in source_name:
                tasks.append(self._scrape_weibo_crypto())
            elif '8btc' in source_name:
                tasks.append(self._scrape_8btc_forum())
            elif 'jinse' in source_name:
                tasks.append(self._scrape_jinse_finance())
        
        # Execute tasks with longer delays for Chinese sites
        all_items = []
        
        for task in tasks:
            try:
                result = await task
                if isinstance(result, list):
                    all_items.extend(result)
                
                # Longer delay for Chinese sites to be respectful
                await asyncio.sleep(random.uniform(5, 10))
                
            except Exception as e:
                self.logger.error(f"Chinese source task error: {e}")
        
        self.logger.info(f"Total Chinese source items collected: {len(all_items)}")
        return all_items
    
    def get_chinese_stats(self) -> Dict:
        """Get statistics about Chinese sources collection"""
        stats = {
            'configured_sources': len(self.chinese_config),
            'translation_cache_size': len(self.translation_cache),
            'supported_terms': len(self.chinese_crypto_terms)
        }
        
        return stats

# Test function
async def test_chinese_sources():
    """Test Chinese sources handler"""
    test_config = [
        {
            'name': 'Weibo Crypto',
            'base_trust': 0.45
        },
        {
            'name': '8btc Forums',
            'base_trust': 0.50
        }
    ]
    
    async with ChineseSourceHandler(test_config) as handler:
        items = await handler.fetch_all_sources()
        
        print(f"Collected {len(items)} items from Chinese sources")
        for item in items[:2]:  # Show first 2 items
            print(f"\nSource: {item['source']}")
            print(f"Original: {item['content'][:100]}...")
            print(f"Translated: {item['translated_content'][:100]}...")
            print(f"Symbols: {item['symbols']}")

if __name__ == "__main__":
    asyncio.run(test_chinese_sources())