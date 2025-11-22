#!/usr/bin/env python3
"""
Telegram Handler for Crypto Sentiment Collection
Monitors public Telegram channels for crypto sentiment
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import re
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import time

class TelegramHandler:
    def __init__(self, telegram_config: List[Dict]):
        self.telegram_config = telegram_config
        self.logger = logging.getLogger(__name__)
        
        # Telegram API credentials (get from https://my.telegram.org)
        self.api_id = 'YOUR_API_ID'  # Replace with your API ID
        self.api_hash = 'YOUR_API_HASH'  # Replace with your API hash
        self.phone = 'YOUR_PHONE_NUMBER'  # Replace with your phone number
        
        self.client = None
        self.channels_cache = {}
        self.message_cache = set()  # To avoid duplicate messages
        
        # Crypto-related keywords for filtering
        self.crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'altcoin',
            'pump', 'dump', 'moon', 'hodl', 'defi', 'nft', 'solana',
            'avalanche', 'cardano', 'polygon', 'trading', 'signal',
            'buy', 'sell', 'long', 'short', 'bullish', 'bearish'
        ]
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.api_id or self.api_id == 'YOUR_API_ID':
            self.logger.warning("Telegram API credentials not configured")
            return self
        
        try:
            self.client = TelegramClient('crypto_sentiment_session', self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            
            if not await self.client.is_user_authorized():
                self.logger.error("Telegram client not authorized")
                return self
            
            self.logger.info("Telegram client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram client: {e}")
            self.client = None
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.disconnect()
    
    def _clean_telegram_content(self, text: str) -> str:
        """Clean Telegram message content"""
        if not text:
            return ""
        
        # Remove Telegram formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'__(.*?)__', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        text = re.sub(r'~~(.*?)~~', r'\1', text)      # Strikethrough
        
        # Remove links and mentions
        text = re.sub(r'https?://[^\s]+', '[LINK]', text)
        text = re.sub(r'@[\w\d_]+', '', text)
        text = re.sub(r'#[\w\d_]+', '', text)
        
        # Clean whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _is_crypto_related(self, text: str) -> bool:
        """Check if message is crypto-related"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.crypto_keywords)
    
    def _extract_crypto_mentions(self, text: str) -> List[str]:
        """Extract cryptocurrency mentions from text"""
        mentions = []
        text_lower = text.lower()
        
        crypto_patterns = {
            'BTC': ['btc', 'bitcoin', '₿'],
            'ETH': ['eth', 'ethereum', 'ether'],
            'SOL': ['sol', 'solana'],
            'AVAX': ['avax', 'avalanche'],
            'ADA': ['ada', 'cardano'],
            'MATIC': ['matic', 'polygon'],
            'LINK': ['link', 'chainlink'],
            'DOT': ['dot', 'polkadot'],
            'DOGE': ['doge', 'dogecoin'],
            'SHIB': ['shib', 'shiba']
        }
        
        for crypto, patterns in crypto_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    mentions.append(crypto)
                    break
        
        return list(set(mentions))
    
    def _analyze_message_sentiment_signals(self, text: str) -> Dict:
        """Analyze sentiment signals in message"""
        text_lower = text.lower()
        
        signals = {
            'bullish_signals': 0,
            'bearish_signals': 0,
            'urgency_signals': 0,
            'volume_signals': 0
        }
        
        # Bullish indicators
        bullish_terms = ['moon', 'pump', 'bull', 'buy', 'long', 'hodl', 'up', 'rise', 'green']
        signals['bullish_signals'] = sum(1 for term in bullish_terms if term in text_lower)
        
        # Bearish indicators
        bearish_terms = ['dump', 'crash', 'bear', 'sell', 'short', 'down', 'fall', 'red', 'rekt']
        signals['bearish_signals'] = sum(1 for term in bearish_terms if term in text_lower)
        
        # Urgency indicators
        urgency_terms = ['urgent', 'breaking', 'alert', 'now', 'quick', 'asap', 'immediate']
        signals['urgency_signals'] = sum(1 for term in urgency_terms if term in text_lower)
        
        # Volume/activity indicators
        volume_terms = ['volume', 'spike', 'surge', 'massive', 'huge', 'big', 'whale']
        signals['volume_signals'] = sum(1 for term in volume_terms if term in text_lower)
        
        return signals
    
    async def _fetch_channel_messages(self, channel_config: Dict) -> List[Dict]:
        """Fetch recent messages from a Telegram channel"""
        if not self.client:
            return []
        
        channel_name = channel_config.get('channel', '')
        base_trust = channel_config.get('base_trust', 0.35)
        
        try:
            self.logger.info(f"Fetching messages from {channel_name}")
            
            # Get channel entity
            try:
                channel = await self.client.get_entity(channel_name)
            except Exception as e:
                self.logger.error(f"Could not find channel {channel_name}: {e}")
                return []
            
            # Fetch recent messages (last 6 hours)
            since_time = datetime.now() - timedelta(hours=6)
            messages = []
            
            async for message in self.client.iter_messages(channel, limit=50):
                if message.date < since_time:
                    break
                
                if not message.text:
                    continue
                
                # Skip if we've already processed this message
                message_id = f"{channel.id}_{message.id}"
                if message_id in self.message_cache:
                    continue
                
                self.message_cache.add(message_id)
                
                # Clean and filter content
                clean_text = self._clean_telegram_content(message.text)
                
                if len(clean_text) < 20:
                    continue
                
                if not self._is_crypto_related(clean_text):
                    continue
                
                # Extract crypto mentions and signals
                crypto_mentions = self._extract_crypto_mentions(clean_text)
                sentiment_signals = self._analyze_message_sentiment_signals(clean_text)
                
                # Calculate basic sentiment score
                bull_score = sentiment_signals['bullish_signals']
                bear_score = sentiment_signals['bearish_signals']
                total_signals = bull_score + bear_score
                
                if total_signals > 0:
                    sentiment_score = bull_score / total_signals
                else:
                    sentiment_score = 0.5  # Neutral
                
                # Adjust trust based on channel activity and message quality
                adjusted_trust = base_trust
                if sentiment_signals['urgency_signals'] > 2:
                    adjusted_trust *= 0.8  # Lower trust for overly urgent messages
                
                message_data = {
                    'source': f"Telegram {channel_name}",
                    'content': clean_text,
                    'timestamp': message.date.replace(tzinfo=None),
                    'base_trust': adjusted_trust,
                    'symbols': crypto_mentions,
                    'metadata': {
                        'channel_id': channel.id,
                        'message_id': message.id,
                        'views': getattr(message, 'views', 0),
                        'forwards': getattr(message, 'forwards', 0),
                        'replies': getattr(message.replies, 'replies', 0) if message.replies else 0,
                        'sentiment_signals': sentiment_signals,
                        'calculated_sentiment': sentiment_score,
                        'has_media': bool(message.media)
                    }
                }
                messages.append(message_data)
            
            self.logger.info(f"Collected {len(messages)} messages from {channel_name}")
            return messages
            
        except FloodWaitError as e:
            self.logger.warning(f"Telegram rate limit hit, waiting {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            self.logger.error(f"Error fetching from {channel_name}: {str(e)}")
            return []
    
    async def _monitor_channel_live(self, channel_config: Dict, duration_minutes: int = 30) -> List[Dict]:
        """Monitor a channel for live messages for a specified duration"""
        if not self.client:
            return []
        
        channel_name = channel_config.get('channel', '')
        base_trust = channel_config.get('base_trust', 0.35)
        
        try:
            channel = await self.client.get_entity(channel_name)
            messages = []
            
            self.logger.info(f"Starting live monitoring of {channel_name} for {duration_minutes} minutes")
            
            @self.client.on(events.NewMessage(chats=[channel]))
            async def new_message_handler(event):
                try:
                    message = event.message
                    
                    if not message.text:
                        return
                    
                    clean_text = self._clean_telegram_content(message.text)
                    
                    if len(clean_text) < 20:
                        return
                    
                    if not self._is_crypto_related(clean_text):
                        return
                    
                    crypto_mentions = self._extract_crypto_mentions(clean_text)
                    sentiment_signals = self._analyze_message_sentiment_signals(clean_text)
                    
                    bull_score = sentiment_signals['bullish_signals']
                    bear_score = sentiment_signals['bearish_signals']
                    total_signals = bull_score + bear_score
                    
                    sentiment_score = bull_score / total_signals if total_signals > 0 else 0.5
                    
                    message_data = {
                        'source': f"Telegram Live {channel_name}",
                        'content': clean_text,
                        'timestamp': message.date.replace(tzinfo=None),
                        'base_trust': base_trust,
                        'symbols': crypto_mentions,
                        'metadata': {
                            'channel_id': channel.id,
                            'message_id': message.id,
                            'sentiment_signals': sentiment_signals,
                            'calculated_sentiment': sentiment_score,
                            'live_monitoring': True
                        }
                    }
                    messages.append(message_data)
                    
                    self.logger.info(f"Live message from {channel_name}: {sentiment_score:.2f} sentiment")
                    
                except Exception as e:
                    self.logger.error(f"Error processing live message: {e}")
            
            # Monitor for specified duration
            await asyncio.sleep(duration_minutes * 60)
            
            # Remove the event handler
            self.client.remove_event_handler(new_message_handler)
            
            self.logger.info(f"Live monitoring completed, collected {len(messages)} messages")
            return messages
            
        except Exception as e:
            self.logger.error(f"Error in live monitoring {channel_name}: {str(e)}")
            return []
    
    async def _get_channel_statistics(self, channel_config: Dict) -> Dict:
        """Get statistics about a Telegram channel"""
        if not self.client:
            return {}
        
        channel_name = channel_config.get('channel', '')
        
        try:
            channel = await self.client.get_entity(channel_name)
            
            # Get channel info
            channel_info = await self.client.get_entity(channel)
            
            stats = {
                'channel_name': channel_name,
                'channel_id': channel.id,
                'channel_title': getattr(channel, 'title', ''),
                'subscribers_count': getattr(channel, 'participants_count', 0),
                'channel_type': 'channel' if hasattr(channel, 'broadcast') else 'group'
            }
            
            # Get recent message statistics
            message_count = 0
            crypto_message_count = 0
            
            async for message in self.client.iter_messages(channel, limit=100):
                message_count += 1
                if message.text and self._is_crypto_related(message.text):
                    crypto_message_count += 1
            
            stats.update({
                'recent_messages_sample': message_count,
                'crypto_related_percentage': (crypto_message_count / message_count * 100) if message_count > 0 else 0
            })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting stats for {channel_name}: {str(e)}")
            return {'error': str(e)}
    
    async def fetch_all_channels(self) -> List[Dict]:
        """Fetch messages from all configured Telegram channels"""
        if not self.client:
            self.logger.error("Telegram client not available")
            return []
        
        all_messages = []
        
        for channel_config in self.telegram_config:
            try:
                # Fetch recent messages
                messages = await self._fetch_channel_messages(channel_config)
                all_messages.extend(messages)
                
                # Small delay between channels to avoid rate limits
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error fetching channel {channel_config.get('channel', '')}: {e}")
                continue
        
        self.logger.info(f"Total Telegram messages collected: {len(all_messages)}")
        return all_messages
    
    async def start_live_monitoring(self, duration_minutes: int = 60) -> List[Dict]:
        """Start live monitoring of all configured channels"""
        if not self.client:
            self.logger.error("Telegram client not available")
            return []
        
        self.logger.info(f"Starting live monitoring for {duration_minutes} minutes")
        
        # Start monitoring tasks for all channels
        tasks = []
        for channel_config in self.telegram_config:
            task = self._monitor_channel_live(channel_config, duration_minutes)
            tasks.append(task)
        
        # Run all monitoring tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        all_messages = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Live monitoring error: {result}")
            elif isinstance(result, list):
                all_messages.extend(result)
        
        self.logger.info(f"Live monitoring completed, total messages: {len(all_messages)}")
        return all_messages
    
    async def get_all_channel_stats(self) -> Dict:
        """Get statistics for all configured channels"""
        if not self.client:
            return {'error': 'Telegram client not available'}
        
        stats = {
            'configured_channels': len(self.telegram_config),
            'channels': {}
        }
        
        for channel_config in self.telegram_config:
            channel_name = channel_config.get('channel', '')
            channel_stats = await self._get_channel_statistics(channel_config)
            stats['channels'][channel_name] = channel_stats
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        return stats
    
    def get_telegram_stats(self) -> Dict:
        """Get general Telegram handler statistics"""
        stats = {
            'configured_channels': len(self.telegram_config),
            'message_cache_size': len(self.message_cache),
            'client_status': 'connected' if self.client else 'disconnected',
            'api_configured': bool(self.api_id and self.api_id != 'YOUR_API_ID')
        }
        
        # Group channels by trust level
        trust_groups = {}
        for config in self.telegram_config:
            trust = config.get('base_trust', 0.35)
            trust_range = f"{int(trust * 10) / 10:.1f}"
            if trust_range not in trust_groups:
                trust_groups[trust_range] = []
            trust_groups[trust_range].append(config.get('channel', ''))
        
        stats['channels_by_trust_level'] = trust_groups
        return stats

# Test function
async def test_telegram_handler():
    """Test Telegram handler with sample configuration"""
    test_config = [
        {
            'channel': '@cryptonews',  # Example public channel
            'base_trust': 0.50
        },
        {
            'channel': '@bitcoin',  # Example public channel
            'base_trust': 0.45
        }
    ]
    
    async with TelegramHandler(test_config) as handler:
        if handler.client:
            # Get channel statistics
            stats = await handler.get_all_channel_stats()
            print("Channel statistics:")
            print(json.dumps(stats, indent=2, default=str))
            
            # Fetch recent messages
            messages = await handler.fetch_all_channels()
            print(f"\nCollected {len(messages)} messages")
            
            for message in messages[:3]:  # Show first 3 messages
                print(f"\nSource: {message['source']}")
                print(f"Content: {message['content'][:150]}...")
                print(f"Sentiment: {message['metadata']['calculated_sentiment']:.2f}")
                print(f"Symbols: {message['symbols']}")
        else:
            print("Telegram client not available - check API credentials")

if __name__ == "__main__":
    asyncio.run(test_telegram_handler())