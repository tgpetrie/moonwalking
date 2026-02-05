#!/usr/bin/env python3
"""
Social APIs Handler for Crypto Sentiment Collection
Integrates with LunarCrush, StockGeist, and other sentiment APIs
"""

import asyncio
import aiohttp
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import websockets
import time
from urllib.parse import urlencode


LUNARCRUSH_API_PLACEHOLDER = "YOUR_LUNARCRUSH_API_KEY"  # pragma: allowlist secret
STOCKGEIST_API_PLACEHOLDER = "YOUR_STOCKGEIST_API_KEY"  # pragma: allowlist secret
SANTIMENT_API_PLACEHOLDER = "YOUR_SANTIMENT_API_KEY"  # pragma: allowlist secret

class SocialAPIHandler:
    def __init__(self, apis_config: List[Dict]):
        self.apis_config = apis_config
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.rate_limits = {}
        
        # API Keys (set these in your environment)
        self.api_keys = {
            'lunarcrush': LUNARCRUSH_API_PLACEHOLDER,
            'stockgeist': STOCKGEIST_API_PLACEHOLDER,
            'santiment': SANTIMENT_API_PLACEHOLDER
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'CryptoSentimentBot/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _check_rate_limit(self, api_name: str, limit_per_hour: int) -> bool:
        """Check if API call is within rate limits"""
        now = time.time()
        hour_ago = now - 3600
        
        if api_name not in self.rate_limits:
            self.rate_limits[api_name] = []
        
        # Remove calls older than 1 hour
        self.rate_limits[api_name] = [
            call_time for call_time in self.rate_limits[api_name] 
            if call_time > hour_ago
        ]
        
        # Check if we can make another call
        if len(self.rate_limits[api_name]) >= limit_per_hour:
            return False
        
        # Record this call
        self.rate_limits[api_name].append(now)
        return True
    
    async def _fetch_lunarcrush_data(self) -> List[Dict]:
        """Fetch sentiment data from LunarCrush API"""
        if not self._check_rate_limit('lunarcrush', 100):  # 100 calls per hour
            self.logger.warning("LunarCrush rate limit reached")
            return []
        
        api_key = self.api_keys.get('lunarcrush')
        if not api_key or api_key == LUNARCRUSH_API_PLACEHOLDER:
            self.logger.warning("LunarCrush API key not configured")
            return []
        
        try:
            self.logger.info("Fetching LunarCrush data")
            
            # Market overview endpoint
            market_params = {
                'data': 'market',
                'type': 'fast',
                'key': api_key
            }
            
            async with self.session.get(
                'https://api.lunarcrush.com/v2',
                params=market_params
            ) as response:
                if response.status != 200:
                    self.logger.error(f"LunarCrush API error: {response.status}")
                    return []
                
                market_data = await response.json()
            
            # Assets endpoint for individual cryptos
            assets_params = {
                'data': 'assets',
                'symbol': 'BTC,ETH,SOL,AVAX,ADA,MATIC',
                'time_series_indicators': 'sentiment',
                'key': api_key
            }
            
            async with self.session.get(
                'https://api.lunarcrush.com/v2',
                params=assets_params
            ) as response:
                if response.status != 200:
                    self.logger.error(f"LunarCrush assets API error: {response.status}")
                    assets_data = {'data': []}
                else:
                    assets_data = await response.json()
            
            items = []
            
            # Process market data
            if 'data' in market_data:
                market_info = market_data['data']
                
                content = f"Overall crypto market sentiment. Social volume: {market_info.get('social_volume', 0)}, " \
                         f"Market sentiment: {market_info.get('sentiment', 'neutral')}"
                
                item = {
                    'source': 'LunarCrush Market',
                    'content': content,
                    'sentiment_score': self._normalize_lunarcrush_sentiment(market_info.get('sentiment', 0)),
                    'confidence': 0.75,
                    'base_trust': 0.60,
                    'timestamp': datetime.now(),
                    'symbols': ['BTC', 'ETH'],  # General market
                    'metadata': {
                        'social_volume': market_info.get('social_volume', 0),
                        'market_cap': market_info.get('market_cap', 0),
                        'volume_24h': market_info.get('volume_24h', 0)
                    }
                }
                items.append(item)
            
            # Process individual assets
            for asset in assets_data.get('data', []):
                symbol = asset.get('symbol', '').upper()
                
                content = f"{asset.get('name', symbol)} sentiment analysis. " \
                         f"Social mentions: {asset.get('social_mentions', 0)}, " \
                         f"Social sentiment: {asset.get('sentiment', 'neutral')}, " \
                         f"Price change: {asset.get('percent_change_24h', 0):.2f}%"
                
                item = {
                    'source': f'LunarCrush {symbol}',
                    'content': content,
                    'sentiment_score': self._normalize_lunarcrush_sentiment(asset.get('sentiment', 0)),
                    'confidence': 0.80,
                    'base_trust': 0.60,
                    'timestamp': datetime.now(),
                    'symbols': [symbol],
                    'metadata': {
                        'social_mentions': asset.get('social_mentions', 0),
                        'social_impact_score': asset.get('social_impact_score', 0),
                        'correlation_rank': asset.get('correlation_rank', 0),
                        'price_score': asset.get('price_score', 0)
                    }
                }
                items.append(item)
            
            self.logger.info(f"Collected {len(items)} items from LunarCrush")
            return items
            
        except Exception as e:
            self.logger.error(f"LunarCrush API error: {str(e)}")
            return []
    
    def _normalize_lunarcrush_sentiment(self, sentiment_value) -> float:
        """Normalize LunarCrush sentiment to 0-1 scale"""
        if isinstance(sentiment_value, str):
            sentiment_map = {
                'very_bearish': 0.1,
                'bearish': 0.25,
                'neutral': 0.5,
                'bullish': 0.75,
                'very_bullish': 0.9
            }
            return sentiment_map.get(sentiment_value.lower(), 0.5)
        elif isinstance(sentiment_value, (int, float)):
            # Assume sentiment is on a scale like -100 to 100
            return max(0, min(1, (sentiment_value + 100) / 200))
        else:
            return 0.5
    
    async def _fetch_stockgeist_data(self) -> List[Dict]:
        """Fetch sentiment data from StockGeist API"""
        if not self._check_rate_limit('stockgeist', 1000):  # 1000 calls per hour
            self.logger.warning("StockGeist rate limit reached")
            return []
        
        try:
            self.logger.info("Fetching StockGeist data")
            
            # StockGeist crypto sentiment endpoint
            headers = {
                'Authorization': f'Bearer {self.api_keys.get("stockgeist", "")}',
                'Content-Type': 'application/json'
            }
            
            # Get sentiment for major cryptos
            symbols = ['BTC', 'ETH', 'SOL', 'AVAX', 'ADA']
            items = []
            
            for symbol in symbols:
                params = {
                    'symbol': symbol,
                    'timeframe': '24h',
                    'sources': 'twitter,reddit,telegram'
                }
                
                async with self.session.get(
                    'https://api.stockgeist.ai/sentiment/crypto',
                    params=params,
                    headers=headers
                ) as response:
                    
                    if response.status != 200:
                        self.logger.warning(f"StockGeist error for {symbol}: {response.status}")
                        continue
                    
                    data = await response.json()
                    
                    if 'sentiment' in data:
                        sentiment_data = data['sentiment']
                        
                        content = f"{symbol} social sentiment analysis. " \
                                 f"Overall sentiment: {sentiment_data.get('overall', 'neutral')}, " \
                                 f"Volume: {sentiment_data.get('volume', 0)}, " \
                                 f"Trending score: {sentiment_data.get('trending_score', 0)}"
                        
                        item = {
                            'source': f'StockGeist {symbol}',
                            'content': content,
                            'sentiment_score': sentiment_data.get('score', 0.5),
                            'confidence': sentiment_data.get('confidence', 0.7),
                            'base_trust': 0.55,
                            'timestamp': datetime.now(),
                            'symbols': [symbol],
                            'metadata': {
                                'volume': sentiment_data.get('volume', 0),
                                'trending_score': sentiment_data.get('trending_score', 0),
                                'sources_breakdown': sentiment_data.get('sources', {})
                            }
                        }
                        items.append(item)
                
                # Small delay between requests
                await asyncio.sleep(0.1)
            
            self.logger.info(f"Collected {len(items)} items from StockGeist")
            return items
            
        except Exception as e:
            self.logger.error(f"StockGeist API error: {str(e)}")
            return []
    
    async def _connect_stockgeist_websocket(self) -> List[Dict]:
        """Connect to StockGeist real-time sentiment WebSocket"""
        try:
            self.logger.info("Connecting to StockGeist WebSocket")
            
            uri = "wss://api.stockgeist.ai/ws/sentiment"
            items = []
            
            async with websockets.connect(uri) as websocket:
                # Subscribe to crypto sentiment updates
                subscribe_msg = {
                    'action': 'subscribe',
                    'symbols': ['BTC', 'ETH', 'SOL', 'AVAX'],
                    'auth_token': self.api_keys.get('stockgeist', '')
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                
                # Listen for messages for a short time
                try:
                    async with asyncio.timeout(30):  # 30 second timeout
                        while len(items) < 10:  # Collect up to 10 real-time updates
                            message = await websocket.recv()
                            data = json.loads(message)
                            
                            if data.get('type') == 'sentiment_update':
                                symbol = data.get('symbol', 'UNKNOWN')
                                sentiment = data.get('sentiment', {})
                                
                                content = f"Real-time {symbol} sentiment update. " \
                                         f"Score: {sentiment.get('score', 0.5):.2f}, " \
                                         f"Change: {sentiment.get('change', 0):.3f}"
                                
                                item = {
                                    'source': f'StockGeist RT {symbol}',
                                    'content': content,
                                    'sentiment_score': sentiment.get('score', 0.5),
                                    'confidence': 0.8,
                                    'base_trust': 0.55,
                                    'timestamp': datetime.now(),
                                    'symbols': [symbol],
                                    'metadata': {
                                        'real_time': True,
                                        'change': sentiment.get('change', 0),
                                        'volume_spike': sentiment.get('volume_spike', False)
                                    }
                                }
                                items.append(item)
                
                except asyncio.TimeoutError:
                    self.logger.info("StockGeist WebSocket timeout reached")
            
            self.logger.info(f"Collected {len(items)} real-time items from StockGeist")
            return items
            
        except Exception as e:
            self.logger.error(f"StockGeist WebSocket error: {str(e)}")
            return []
    
    async def _fetch_crypto_fear_greed(self) -> List[Dict]:
        """Fetch Fear & Greed Index"""
        try:
            self.logger.info("Fetching Crypto Fear & Greed Index")
            
            async with self.session.get('https://api.alternative.me/fng/') as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
            
            if 'data' in data and len(data['data']) > 0:
                fng_data = data['data'][0]
                
                value = int(fng_data['value'])
                classification = fng_data['value_classification']
                
                content = f"Crypto Fear & Greed Index: {value}/100 ({classification}). " \
                         f"Market sentiment indicator based on volatility, volume, social media, " \
                         f"surveys, dominance, and trends."
                
                # Convert to 0-1 scale
                sentiment_score = value / 100.0
                
                item = {
                    'source': 'Fear & Greed Index',
                    'content': content,
                    'sentiment_score': sentiment_score,
                    'confidence': 0.85,
                    'base_trust': 0.75,
                    'timestamp': datetime.fromtimestamp(int(fng_data['timestamp'])),
                    'symbols': ['BTC', 'ETH'],  # General market indicator
                    'metadata': {
                        'raw_value': value,
                        'classification': classification,
                        'time_until_update': fng_data.get('time_until_update')
                    }
                }
                
                return [item]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Fear & Greed Index error: {str(e)}")
            return []
    
    async def _fetch_santiment_data(self) -> List[Dict]:
        """Fetch sentiment data from Santiment API (if available)"""
        api_key = self.api_keys.get('santiment')
        if not api_key or api_key == SANTIMENT_API_PLACEHOLDER:
            self.logger.warning("Santiment API key not configured")
            return []
        
        try:
            self.logger.info("Fetching Santiment data")
            
            # Santiment GraphQL endpoint
            query = """
            {
              getMetric(metric: "social_sentiment_positive_total") {
                timeseriesData(
                  slug: "bitcoin"
                  from: "utc_now-1d"
                  to: "utc_now"
                  interval: "1h"
                ) {
                  datetime
                  value
                }
              }
            }
            """
            
            headers = {
                'Authorization': f'Apikey {api_key}',
                'Content-Type': 'application/json'
            }
            
            async with self.session.post(
                'https://api.santiment.net/graphql',
                json={'query': query},
                headers=headers
            ) as response:
                
                if response.status != 200:
                    self.logger.error(f"Santiment API error: {response.status}")
                    return []
                
                data = await response.json()
            
            items = []
            timeseries = data.get('data', {}).get('getMetric', {}).get('timeseriesData', [])
            
            if timeseries:
                latest = timeseries[-1]
                sentiment_value = latest.get('value', 0)
                
                content = f"Bitcoin social sentiment analysis from Santiment. " \
                         f"Positive sentiment score: {sentiment_value:.2f}"
                
                item = {
                    'source': 'Santiment BTC',
                    'content': content,
                    'sentiment_score': min(1.0, sentiment_value / 100.0),  # Normalize
                    'confidence': 0.80,
                    'base_trust': 0.70,
                    'timestamp': datetime.fromisoformat(latest['datetime'].replace('Z', '+00:00')).replace(tzinfo=None),
                    'symbols': ['BTC'],
                    'metadata': {
                        'raw_sentiment_value': sentiment_value,
                        'data_points_count': len(timeseries)
                    }
                }
                items.append(item)
            
            return items
            
        except Exception as e:
            self.logger.error(f"Santiment API error: {str(e)}")
            return []
    
    async def fetch_all_apis(self) -> List[Dict]:
        """Fetch data from all configured social APIs"""
        if not self.session:
            async with self:
                return await self._fetch_all_apis_internal()
        else:
            return await self._fetch_all_apis_internal()
    
    async def _fetch_all_apis_internal(self) -> List[Dict]:
        """Internal method to fetch from all APIs"""
        tasks = [
            self._fetch_lunarcrush_data(),
            self._fetch_stockgeist_data(),
            self._fetch_crypto_fear_greed(),
            self._fetch_santiment_data(),
        ]
        
        # Add real-time data if configured
        if any(api.get('method') == 'websocket' for api in self.apis_config):
            tasks.append(self._connect_stockgeist_websocket())
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        all_items = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"API fetch error: {result}")
            elif isinstance(result, list):
                all_items.extend(result)
        
        self.logger.info(f"Total social API items collected: {len(all_items)}")
        return all_items
    
    def get_api_stats(self) -> Dict:
        """Get statistics about API usage"""
        stats = {
            'configured_apis': len(self.apis_config),
            'rate_limits_status': {},
            'api_keys_configured': []
        }
        
        # Check rate limit status
        for api_name, calls in self.rate_limits.items():
            hour_ago = time.time() - 3600
            recent_calls = [call for call in calls if call > hour_ago]
            stats['rate_limits_status'][api_name] = {
                'calls_last_hour': len(recent_calls),
                'remaining_capacity': 'varies'  # Depends on specific API limits
            }
        
        # Check configured API keys (without revealing the keys)
        for api_name, key in self.api_keys.items():
            if key and not key.startswith('YOUR_'):
                stats['api_keys_configured'].append(api_name)
        
        return stats

# Test function
async def test_social_apis():
    """Test social APIs handler"""
    test_config = [
        {
            'name': 'LunarCrush',
            'base_trust': 0.60
        },
        {
            'name': 'Fear & Greed',
            'base_trust': 0.75
        }
    ]
    
    async with SocialAPIHandler(test_config) as handler:
        items = await handler.fetch_all_apis()
        
        print(f"Collected {len(items)} items from social APIs")
        for item in items:
            print(f"\nSource: {item['source']}")
            print(f"Content: {item['content']}")
            print(f"Sentiment: {item['sentiment_score']:.2f}")
            print(f"Symbols: {item['symbols']}")

if __name__ == "__main__":
    asyncio.run(test_social_apis())