#!/usr/bin/env python3
"""
Rate Limiter and Cache Manager utilities
Handles API rate limiting and caching for the sentiment pipeline
"""

import asyncio
import time
import logging
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
import redis
import aiofiles
import os

class RateLimiter:
    """Rate limiter to manage API calls and avoid hitting limits"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.call_history = defaultdict(deque)  # API -> deque of timestamps
        self.rate_limits = {
            'reddit': {'calls': 60, 'window': 60},      # 60 calls per minute
            'lunarcrush': {'calls': 100, 'window': 3600},  # 100 calls per hour
            'stockgeist': {'calls': 1000, 'window': 3600}, # 1000 calls per hour
            'telegram': {'calls': 20, 'window': 60},       # 20 calls per minute
            'weibo': {'calls': 30, 'window': 3600},        # 30 calls per hour
            'custom_scrape': {'calls': 60, 'window': 3600}, # 60 calls per hour
            'default': {'calls': 100, 'window': 3600}      # Default limit
        }
        
        # Burst allowances for short spikes
        self.burst_allowances = {
            'reddit': 10,
            'lunarcrush': 5,
            'stockgeist': 20,
            'telegram': 5,
            'default': 5
        }
        
        self.burst_usage = defaultdict(int)
        self.burst_reset_times = defaultdict(float)
    
    def _clean_old_calls(self, api_name: str):
        """Remove old API calls outside the time window"""
        if api_name not in self.call_history:
            return
        
        limit_config = self.rate_limits.get(api_name, self.rate_limits['default'])
        window_seconds = limit_config['window']
        cutoff_time = time.time() - window_seconds
        
        # Remove old calls
        while (self.call_history[api_name] and 
               self.call_history[api_name][0] < cutoff_time):
            self.call_history[api_name].popleft()
    
    def _reset_burst_if_needed(self, api_name: str):
        """Reset burst allowance if enough time has passed"""
        current_time = time.time()
        reset_time = self.burst_reset_times.get(api_name, 0)
        
        # Reset burst every hour
        if current_time - reset_time > 3600:
            self.burst_usage[api_name] = 0
            self.burst_reset_times[api_name] = current_time
    
    async def check_rate_limit(self, api_name: str) -> Dict[str, Any]:
        """Check if API call is within rate limits"""
        self._clean_old_calls(api_name)
        self._reset_burst_if_needed(api_name)
        
        limit_config = self.rate_limits.get(api_name, self.rate_limits['default'])
        max_calls = limit_config['calls']
        window_seconds = limit_config['window']
        
        current_calls = len(self.call_history[api_name])
        burst_allowance = self.burst_allowances.get(api_name, self.burst_allowances['default'])
        burst_used = self.burst_usage[api_name]
        
        # Check regular rate limit
        if current_calls < max_calls:
            return {
                'allowed': True,
                'current_calls': current_calls,
                'max_calls': max_calls,
                'reset_in_seconds': window_seconds,
                'burst_used': False
            }
        
        # Check burst allowance
        if burst_used < burst_allowance:
            self.burst_usage[api_name] += 1
            self.logger.warning(f"Using burst allowance for {api_name} ({burst_used + 1}/{burst_allowance})")
            return {
                'allowed': True,
                'current_calls': current_calls,
                'max_calls': max_calls,
                'reset_in_seconds': window_seconds,
                'burst_used': True,
                'burst_remaining': burst_allowance - burst_used - 1
            }
        
        # Rate limit exceeded
        return {
            'allowed': False,
            'current_calls': current_calls,
            'max_calls': max_calls,
            'reset_in_seconds': window_seconds,
            'burst_used': True,
            'burst_remaining': 0
        }
    
    async def record_api_call(self, api_name: str):
        """Record an API call"""
        current_time = time.time()
        self.call_history[api_name].append(current_time)
        
        # Log rate limit status
        rate_check = await self.check_rate_limit(api_name)
        if rate_check['current_calls'] > rate_check['max_calls'] * 0.8:
            self.logger.warning(f"Rate limit warning for {api_name}: "
                              f"{rate_check['current_calls']}/{rate_check['max_calls']} calls used")
    
    async def wait_if_needed(self, api_name: str) -> float:
        """Wait if rate limit would be exceeded, return wait time"""
        rate_check = await self.check_rate_limit(api_name)
        
        if not rate_check['allowed']:
            # Calculate wait time until oldest call expires
            if self.call_history[api_name]:
                oldest_call = self.call_history[api_name][0]
                limit_config = self.rate_limits.get(api_name, self.rate_limits['default'])
                wait_time = oldest_call + limit_config['window'] - time.time() + 1  # +1 for safety
                
                if wait_time > 0:
                    self.logger.info(f"Rate limit hit for {api_name}, waiting {wait_time:.1f} seconds")
                    await asyncio.sleep(wait_time)
                    return wait_time
        
        return 0.0
    
    def get_rate_limit_status(self) -> Dict[str, Dict]:
        """Get current rate limit status for all APIs"""
        status = {}
        
        for api_name in self.call_history.keys():
            self._clean_old_calls(api_name)
            limit_config = self.rate_limits.get(api_name, self.rate_limits['default'])
            
            status[api_name] = {
                'current_calls': len(self.call_history[api_name]),
                'max_calls': limit_config['calls'],
                'window_seconds': limit_config['window'],
                'burst_used': self.burst_usage[api_name],
                'burst_max': self.burst_allowances.get(api_name, self.burst_allowances['default'])
            }
        
        return status


class CacheManager:
    """Cache manager for storing and retrieving processed data"""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, 
                 cache_dir: str = 'cache'):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = cache_dir
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0
        }
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Try to connect to Redis
        try:
            self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            self.redis_available = True
            self.logger.info("Redis cache connected")
        except Exception as e:
            self.logger.warning(f"Redis not available, using file/memory cache: {e}")
            self.redis_client = None
            self.redis_available = False
        
        # Default cache TTL (time to live) settings
        self.default_ttl = {
            'rss_content': 1800,      # 30 minutes
            'reddit_posts': 3600,     # 1 hour
            'social_api': 1800,       # 30 minutes
            'sentiment_analysis': 7200, # 2 hours
            'translations': 86400,    # 24 hours
            'aggregated_data': 3600,  # 1 hour
            'default': 3600
        }
    
    def _get_cache_key(self, namespace: str, key: str) -> str:
        """Generate a cache key"""
        return f"crypto_sentiment:{namespace}:{key}"
    
    def _hash_data(self, data: Any) -> str:
        """Generate hash for data to use as cache key"""
        if isinstance(data, str):
            content = data.encode('utf-8')
        else:
            content = json.dumps(data, sort_keys=True).encode('utf-8')
        
        return hashlib.md5(content).hexdigest()
    
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get data from cache"""
        cache_key = self._get_cache_key(namespace, key)
        
        # Try memory cache first
        if cache_key in self.memory_cache:
            data, expiry = self.memory_cache[cache_key]
            if time.time() < expiry:
                self.cache_stats['hits'] += 1
                return data
            else:
                del self.memory_cache[cache_key]
        
        # Try Redis cache
        if self.redis_available:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    self.cache_stats['hits'] += 1
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Redis get error: {e}")
        
        # Try file cache
        try:
            file_path = os.path.join(self.cache_dir, f"{namespace}_{key}.json")
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    cached_data = json.loads(content)
                    
                    # Check if expired
                    if 'expiry' in cached_data and time.time() < cached_data['expiry']:
                        self.cache_stats['hits'] += 1
                        return cached_data['data']
                    else:
                        # Remove expired file
                        os.remove(file_path)
        except Exception as e:
            self.logger.error(f"File cache get error: {e}")
        
        self.cache_stats['misses'] += 1
        return None
    
    async def set(self, namespace: str, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Set data in cache"""
        if ttl is None:
            ttl = self.default_ttl.get(namespace, self.default_ttl['default'])
        
        cache_key = self._get_cache_key(namespace, key)
        expiry_time = time.time() + ttl
        
        # Store in memory cache
        self.memory_cache[cache_key] = (data, expiry_time)
        
        # Store in Redis cache
        if self.redis_available:
            try:
                serialized_data = json.dumps(data, default=str)
                self.redis_client.setex(cache_key, ttl, serialized_data)
            except Exception as e:
                self.logger.error(f"Redis set error: {e}")
        
        # Store in file cache
        try:
            file_path = os.path.join(self.cache_dir, f"{namespace}_{key}.json")
            cache_data = {
                'data': data,
                'expiry': expiry_time,
                'created': time.time()
            }
            
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(cache_data, default=str))
        except Exception as e:
            self.logger.error(f"File cache set error: {e}")
        
        self.cache_stats['sets'] += 1
        return True
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete data from cache"""
        cache_key = self._get_cache_key(namespace, key)
        
        # Remove from memory cache
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
        
        # Remove from Redis cache
        if self.redis_available:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                self.logger.error(f"Redis delete error: {e}")
        
        # Remove from file cache
        try:
            file_path = os.path.join(self.cache_dir, f"{namespace}_{key}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            self.logger.error(f"File cache delete error: {e}")
        
        return True
    
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all data in a namespace"""
        cleared_count = 0
        
        # Clear from memory cache
        keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(f"crypto_sentiment:{namespace}:")]
        for key in keys_to_remove:
            del self.memory_cache[key]
            cleared_count += 1
        
        # Clear from Redis cache
        if self.redis_available:
            try:
                pattern = self._get_cache_key(namespace, "*")
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    cleared_count += len(keys)
            except Exception as e:
                self.logger.error(f"Redis clear error: {e}")
        
        # Clear from file cache
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith(f"{namespace}_"):
                    file_path = os.path.join(self.cache_dir, filename)
                    os.remove(file_path)
                    cleared_count += 1
        except Exception as e:
            self.logger.error(f"File cache clear error: {e}")
        
        return cleared_count
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries"""
        cleaned_count = 0
        current_time = time.time()
        
        # Clean memory cache
        expired_keys = [
            key for key, (data, expiry) in self.memory_cache.items() 
            if current_time >= expiry
        ]
        for key in expired_keys:
            del self.memory_cache[key]
            cleaned_count += 1
        
        # Clean file cache
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        async with aiofiles.open(file_path, 'r') as f:
                            content = await f.read()
                            cache_data = json.loads(content)
                            
                        if current_time >= cache_data.get('expiry', 0):
                            os.remove(file_path)
                            cleaned_count += 1
                    except:
                        # Remove corrupted files
                        os.remove(file_path)
                        cleaned_count += 1
        except Exception as e:
            self.logger.error(f"File cache cleanup error: {e}")
        
        return cleaned_count
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0
        
        stats = {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'sets': self.cache_stats['sets'],
            'hit_rate': hit_rate,
            'memory_cache_size': len(self.memory_cache),
            'redis_available': self.redis_available
        }
        
        # Add file cache stats
        try:
            file_count = len([f for f in os.listdir(self.cache_dir) if f.endswith('.json')])
            stats['file_cache_entries'] = file_count
        except:
            stats['file_cache_entries'] = 0
        
        return stats
    
    async def get_cache_content_hash(self, content: str) -> str:
        """Get cache key based on content hash"""
        return self._hash_data(content)
    
    async def cache_sentiment_result(self, content: str, result: Dict) -> str:
        """Cache sentiment analysis result"""
        content_hash = await self.get_cache_content_hash(content)
        await self.set('sentiment_analysis', content_hash, result, self.default_ttl['sentiment_analysis'])
        return content_hash
    
    async def get_cached_sentiment(self, content: str) -> Optional[Dict]:
        """Get cached sentiment analysis result"""
        content_hash = await self.get_cache_content_hash(content)
        return await self.get('sentiment_analysis', content_hash)


# Test functions
async def test_rate_limiter():
    """Test rate limiter functionality"""
    limiter = RateLimiter()
    
    print("Rate Limiter Test:")
    print("=" * 30)
    
    # Test normal operation
    for i in range(5):
        rate_check = await limiter.check_rate_limit('test_api')
        print(f"Call {i+1}: Allowed = {rate_check['allowed']}, "
              f"Current calls = {rate_check['current_calls']}")
        
        if rate_check['allowed']:
            await limiter.record_api_call('test_api')
        
        await asyncio.sleep(0.1)
    
    # Test rate limit status
    status = limiter.get_rate_limit_status()
    print(f"\nRate limit status: {status}")

async def test_cache_manager():
    """Test cache manager functionality"""
    cache = CacheManager()
    
    print("\nCache Manager Test:")
    print("=" * 30)
    
    # Test set and get
    test_data = {'sentiment': 0.75, 'confidence': 0.8}
    await cache.set('test', 'sample_key', test_data)
    
    retrieved_data = await cache.get('test', 'sample_key')
    print(f"Cached data: {retrieved_data}")
    
    # Test cache miss
    missing_data = await cache.get('test', 'missing_key')
    print(f"Missing data: {missing_data}")
    
    # Test sentiment caching
    content = "Bitcoin is going to the moon!"
    sentiment_result = {'score': 0.85, 'confidence': 0.9}
    
    content_hash = await cache.cache_sentiment_result(content, sentiment_result)
    cached_sentiment = await cache.get_cached_sentiment(content)
    
    print(f"Sentiment cached: {cached_sentiment}")
    
    # Test cache stats
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")

if __name__ == "__main__":
    async def main():
        await test_rate_limiter()
        await test_cache_manager()
    
    asyncio.run(main())