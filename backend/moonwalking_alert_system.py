#!/usr/bin/env python3
"""
Moonwalking Alert System - Advanced Crypto Movement Detection
by bhabit - cbmovers integration with sentiment pipeline
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import aiohttp
import websockets
import redis
from collections import defaultdict, deque

class AlertSeverity(Enum):
    CRITICAL = "🔴 CRITICAL"
    HIGH = "🟠 HIGH"  
    MEDIUM = "🟡 MEDIUM"
    LOW = "🟢 LOW"
    INFO = "🔵 INFO"

class AlertType(Enum):
    MOONSHOT = "🚀 MOONSHOT"           # Massive pump detected
    CRATER = "📉 CRATER"               # Major dump detected  
    SENTIMENT_SPIKE = "🌊 SENTIMENT"    # Social sentiment explosion
    WHALE_MOVE = "🐋 WHALE"            # Large volume anomaly
    DIVERGENCE = "⚖️ DIVERGENCE"       # Price vs sentiment mismatch
    BREAKOUT = "📈 BREAKOUT"           # Technical breakout
    FOMO_ALERT = "🔥 FOMO"             # FOMO/Fear spike detected
    STEALTH_MOVE = "👤 STEALTH"        # Quiet accumulation
    NEWS_CATALYST = "📰 NEWS"          # News-driven movement
    ARBITRAGE = "💰 ARBITRAGE"         # Cross-exchange opportunity

@dataclass
class MoonwalkingAlert:
    id: str
    timestamp: datetime
    symbol: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    
    # Price data
    current_price: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    volume_spike: float
    
    # Sentiment data
    sentiment_score: float
    sentiment_change: float
    social_volume: int
    social_spike: float
    
    # Technical indicators
    momentum_score: float
    volatility: float
    liquidity_score: float
    
    # Alert metadata
    confidence: float
    sources: List[str]
    exchanges: List[str]
    triggers: List[str]
    
    # Action recommendations
    action: str  # "BUY", "SELL", "WATCH", "AVOID"
    target_price: Optional[float]
    stop_loss: Optional[float]
    time_horizon: str  # "5m", "1h", "4h", "1d"
    
    # Additional context
    market_cap: Optional[float]
    related_symbols: List[str]
    news_links: List[str]
    
    # Expiry and lifecycle
    expires_at: datetime
    acknowledged: bool = False
    resolved: bool = False

class MoonwalkingDetector:
    """Advanced crypto movement detection engine"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Data sources
        self.price_feeds = {}
        self.sentiment_pipeline = None
        self.volume_trackers = defaultdict(deque)
        self.price_history = defaultdict(deque)
        
        # Alert management
        self.active_alerts = {}
        self.alert_history = deque(maxlen=1000)
        self.alert_subscribers = set()
        
        # Detection parameters
        self.thresholds = {
            'moonshot_pump': 0.15,      # 15% price spike
            'crater_dump': -0.12,       # 12% price drop
            'volume_spike': 3.0,        # 3x normal volume
            'sentiment_spike': 0.25,    # 25% sentiment change
            'whale_threshold': 1000000, # $1M+ single trade
            'fomo_threshold': 0.8,      # 80%+ sentiment score
            'stealth_volume': 2.0,      # 2x volume, <5% price change
        }
        
        # Market state tracking
        self.market_state = {
            'btc_dominance': 0.5,
            'total_market_cap': 0,
            'fear_greed_index': 50,
            'overall_sentiment': 0.5,
            'active_session': 'US'  # US, EU, ASIA
        }
        
        # Redis for real-time data
        self.redis_client = redis.Redis(decode_responses=True)
        
        # WebSocket connections for real-time feeds
        self.websocket_feeds = []
        
        # Symbol universe
        self.tracked_symbols = config.get('tracked_symbols', [
            'BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ADA', 'DOT', 'LINK',
            'UNI', 'AAVE', 'SUSHI', 'CRV', 'YFI', 'COMP', 'MKR', 'SNX'
        ])
    
    async def initialize(self):
        """Initialize all data feeds and connections"""
        self.logger.info("🌙 Initializing Moonwalking Detection System...")
        
        # Initialize price feeds
        await self._init_price_feeds()
        
        # Initialize sentiment pipeline connection
        await self._init_sentiment_pipeline()
        
        # Start real-time monitoring
        await self._start_realtime_monitoring()
        
        self.logger.info("✅ Moonwalking system ready for liftoff!")
    
    async def _init_price_feeds(self):
        """Initialize cryptocurrency price data feeds"""
        # Binance WebSocket for real-time prices
        self.binance_ws_url = "wss://stream.binance.com:9443/ws/"
        
        # CoinGecko for market data
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        
        # Initialize historical data
        for symbol in self.tracked_symbols:
            await self._load_historical_data(symbol)
    
    async def _load_historical_data(self, symbol: str, days: int = 7):
        """Load historical price and volume data"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get price history
                url = f"{self.coingecko_base}/coins/{symbol.lower()}/market_chart"
                params = {'vs_currency': 'usd', 'days': days}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Store price history
                        prices = data.get('prices', [])
                        volumes = data.get('total_volumes', [])
                        
                        for price_point, volume_point in zip(prices, volumes):
                            timestamp = datetime.fromtimestamp(price_point[0] / 1000)
                            price = price_point[1]
                            volume = volume_point[1]
                            
                            self.price_history[symbol].append({
                                'timestamp': timestamp,
                                'price': price,
                                'volume': volume
                            })
                        
                        self.logger.info(f"📊 Loaded {len(prices)} historical data points for {symbol}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to load historical data for {symbol}: {e}")
    
    async def _init_sentiment_pipeline(self):
        """Connect to the sentiment analysis pipeline"""
        try:
            # Connect to our sentiment orchestrator
            self.sentiment_api_base = "http://localhost:8000"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.sentiment_api_base}/health") as response:
                    if response.status == 200:
                        self.logger.info("🧠 Connected to sentiment pipeline")
                        return True
        except Exception as e:
            self.logger.warning(f"⚠️ Sentiment pipeline not available: {e}")
        
        return False
    
    async def _start_realtime_monitoring(self):
        """Start real-time price and volume monitoring"""
        # Create WebSocket connections for each tracked symbol
        tasks = []
        
        for symbol in self.tracked_symbols:
            task = asyncio.create_task(self._monitor_symbol_realtime(symbol))
            tasks.append(task)
        
        # Start the main detection loop
        detection_task = asyncio.create_task(self._detection_loop())
        tasks.append(detection_task)
        
        self.websocket_feeds = tasks
    
    async def _monitor_symbol_realtime(self, symbol: str):
        """Monitor real-time price data for a specific symbol"""
        stream_name = f"{symbol.lower()}usdt@ticker"
        ws_url = f"{self.binance_ws_url}{stream_name}"
        
        while True:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.logger.info(f"📡 Connected to {symbol} real-time feed")
                    
                    async for message in websocket:
                        data = json.loads(message)
                        await self._process_price_update(symbol, data)
                        
            except Exception as e:
                self.logger.error(f"❌ WebSocket error for {symbol}: {e}")
                await asyncio.sleep(5)  # Reconnect delay
    
    async def _process_price_update(self, symbol: str, data: Dict):
        """Process real-time price update"""
        try:
            current_price = float(data.get('c', 0))  # Current price
            volume_24h = float(data.get('v', 0))     # 24h volume
            price_change_24h = float(data.get('P', 0)) / 100  # 24h change %
            price_change_1h = await self._calculate_1h_change(symbol, current_price)
            
            # Store in Redis for fast access
            price_data = {
                'symbol': symbol,
                'price': current_price,
                'volume_24h': volume_24h,
                'change_24h': price_change_24h,
                'change_1h': price_change_1h,
                'timestamp': datetime.now().isoformat()
            }
            
            self.redis_client.setex(
                f"price:{symbol}", 
                300,  # 5 minute expiry
                json.dumps(price_data)
            )
            
            # Add to price history
            self.price_history[symbol].append({
                'timestamp': datetime.now(),
                'price': current_price,
                'volume': volume_24h
            })
            
            # Keep only recent history
            if len(self.price_history[symbol]) > 1000:
                self.price_history[symbol].popleft()
            
            # Check for alerts
            await self._check_price_alerts(symbol, price_data)
            
        except Exception as e:
            self.logger.error(f"❌ Error processing price update for {symbol}: {e}")
    
    async def _calculate_1h_change(self, symbol: str, current_price: float) -> float:
        """Calculate 1-hour price change"""
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        # Find price from ~1 hour ago
        for data_point in reversed(self.price_history[symbol]):
            if data_point['timestamp'] <= one_hour_ago:
                old_price = data_point['price']
                return (current_price - old_price) / old_price
        
        return 0.0  # No data available
    
    async def _detection_loop(self):
        """Main detection loop - runs every 30 seconds"""
        while True:
            try:
                # Get latest sentiment data
                sentiment_data = await self._get_sentiment_data()
                
                # Check all symbols for alert conditions
                for symbol in self.tracked_symbols:
                    await self._run_symbol_detection(symbol, sentiment_data)
                
                # Update market state
                await self._update_market_state()
                
                # Clean up expired alerts
                await self._cleanup_expired_alerts()
                
                await asyncio.sleep(30)  # Run every 30 seconds
                
            except Exception as e:
                self.logger.error(f"❌ Detection loop error: {e}")
                await asyncio.sleep(10)
    
    async def _get_sentiment_data(self) -> Dict:
        """Get latest sentiment data from pipeline"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.sentiment_api_base}/sentiment/latest") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            self.logger.warning(f"⚠️ Could not fetch sentiment data: {e}")
        
        return {}
    
    async def _run_symbol_detection(self, symbol: str, sentiment_data: Dict):
        """Run all detection algorithms for a symbol"""
        
        # Get current price data
        price_data = await self._get_price_data(symbol)
        if not price_data:
            return
        
        # Get symbol-specific sentiment
        symbol_sentiment = await self._get_symbol_sentiment(symbol, sentiment_data)
        
        detection_tasks = [
            self._detect_moonshot(symbol, price_data, symbol_sentiment),
            self._detect_crater(symbol, price_data, symbol_sentiment),
            self._detect_sentiment_spike(symbol, price_data, symbol_sentiment),
            self._detect_whale_move(symbol, price_data),
            self._detect_divergence(symbol, price_data, symbol_sentiment),
            self._detect_fomo_alert(symbol, price_data, symbol_sentiment),
            self._detect_stealth_move(symbol, price_data),
            self._detect_breakout(symbol, price_data),
        ]
        
        # Run all detections concurrently
        alerts = await asyncio.gather(*detection_tasks, return_exceptions=True)
        
        # Process generated alerts
        for alert in alerts:
            if isinstance(alert, MoonwalkingAlert):
                await self._emit_alert(alert)
    
    async def _detect_moonshot(self, symbol: str, price_data: Dict, sentiment: Dict) -> Optional[MoonwalkingAlert]:
        """Detect massive pump/moonshot events"""
        change_1h = price_data.get('change_1h', 0)
        change_24h = price_data.get('change_24h', 0)
        volume_spike = await self._calculate_volume_spike(symbol, price_data['volume_24h'])
        
        # Moonshot conditions
        if (change_1h > self.thresholds['moonshot_pump'] or 
            change_24h > self.thresholds['moonshot_pump'] * 2):
            
            # Determine severity based on magnitude
            if change_1h > 0.5:  # 50%+ pump
                severity = AlertSeverity.CRITICAL
            elif change_1h > 0.3:  # 30%+ pump
                severity = AlertSeverity.HIGH
            else:
                severity = AlertSeverity.MEDIUM
            
            # Calculate confidence based on volume and sentiment
            confidence = min(0.9, 0.5 + (volume_spike / 10) + (sentiment.get('score', 0.5) - 0.5))
            
            return MoonwalkingAlert(
                id=f"moonshot_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.MOONSHOT,
                severity=severity,
                title=f"🚀 {symbol} MOONSHOT DETECTED",
                message=f"{symbol} pumping {change_1h*100:.1f}% in 1h with {volume_spike:.1f}x volume!",
                current_price=price_data['price'],
                price_change_1h=change_1h,
                price_change_24h=change_24h,
                volume_24h=price_data['volume_24h'],
                volume_spike=volume_spike,
                sentiment_score=sentiment.get('score', 0.5),
                sentiment_change=sentiment.get('change', 0),
                social_volume=sentiment.get('social_volume', 0),
                social_spike=sentiment.get('social_spike', 1.0),
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=confidence,
                sources=['binance', 'sentiment_pipeline'],
                exchanges=['binance'],
                triggers=[f"price_pump_{change_1h*100:.1f}%", f"volume_{volume_spike:.1f}x"],
                action="WATCH" if confidence < 0.7 else "BUY",
                target_price=price_data['price'] * 1.2,  # 20% above current
                stop_loss=price_data['price'] * 0.9,     # 10% below current
                time_horizon="1h",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=2)
            )
        
        return None
    
    async def _detect_crater(self, symbol: str, price_data: Dict, sentiment: Dict) -> Optional[MoonwalkingAlert]:
        """Detect major dump/crater events"""
        change_1h = price_data.get('change_1h', 0)
        change_24h = price_data.get('change_24h', 0)
        volume_spike = await self._calculate_volume_spike(symbol, price_data['volume_24h'])
        
        # Crater conditions
        if (change_1h < self.thresholds['crater_dump'] or 
            change_24h < self.thresholds['crater_dump'] * 2):
            
            # Determine severity
            if change_1h < -0.3:  # 30%+ dump
                severity = AlertSeverity.CRITICAL
            elif change_1h < -0.2:  # 20%+ dump
                severity = AlertSeverity.HIGH
            else:
                severity = AlertSeverity.MEDIUM
            
            confidence = min(0.9, 0.5 + (volume_spike / 10) + abs(sentiment.get('score', 0.5) - 0.5))
            
            return MoonwalkingAlert(
                id=f"crater_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.CRATER,
                severity=severity,
                title=f"📉 {symbol} CRATER DETECTED",
                message=f"{symbol} dumping {abs(change_1h)*100:.1f}% in 1h with {volume_spike:.1f}x volume!",
                current_price=price_data['price'],
                price_change_1h=change_1h,
                price_change_24h=change_24h,
                volume_24h=price_data['volume_24h'],
                volume_spike=volume_spike,
                sentiment_score=sentiment.get('score', 0.5),
                sentiment_change=sentiment.get('change', 0),
                social_volume=sentiment.get('social_volume', 0),
                social_spike=sentiment.get('social_spike', 1.0),
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=confidence,
                sources=['binance', 'sentiment_pipeline'],
                exchanges=['binance'],
                triggers=[f"price_dump_{abs(change_1h)*100:.1f}%", f"volume_{volume_spike:.1f}x"],
                action="SELL" if confidence > 0.7 else "WATCH",
                target_price=price_data['price'] * 0.8,   # 20% below current
                stop_loss=price_data['price'] * 1.1,      # 10% above current (short)
                time_horizon="1h",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=2)
            )
        
        return None
    
    async def _detect_sentiment_spike(self, symbol: str, price_data: Dict, sentiment: Dict) -> Optional[MoonwalkingAlert]:
        """Detect social sentiment spikes"""
        sentiment_change = sentiment.get('change', 0)
        social_spike = sentiment.get('social_spike', 1.0)
        
        if (abs(sentiment_change) > self.thresholds['sentiment_spike'] or 
            social_spike > 3.0):
            
            direction = "🔥 BULLISH" if sentiment_change > 0 else "❄️ BEARISH"
            
            return MoonwalkingAlert(
                id=f"sentiment_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.SENTIMENT_SPIKE,
                severity=AlertSeverity.MEDIUM,
                title=f"🌊 {symbol} SENTIMENT SPIKE",
                message=f"{symbol} {direction} sentiment spike: {sentiment_change*100:.1f}% change, {social_spike:.1f}x social volume!",
                current_price=price_data['price'],
                price_change_1h=price_data.get('change_1h', 0),
                price_change_24h=price_data.get('change_24h', 0),
                volume_24h=price_data['volume_24h'],
                volume_spike=await self._calculate_volume_spike(symbol, price_data['volume_24h']),
                sentiment_score=sentiment.get('score', 0.5),
                sentiment_change=sentiment_change,
                social_volume=sentiment.get('social_volume', 0),
                social_spike=social_spike,
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=min(0.8, 0.3 + abs(sentiment_change) + (social_spike / 10)),
                sources=['sentiment_pipeline', 'reddit', 'telegram'],
                exchanges=[],
                triggers=[f"sentiment_change_{sentiment_change*100:.1f}%", f"social_spike_{social_spike:.1f}x"],
                action="WATCH",
                target_price=None,
                stop_loss=None,
                time_horizon="4h",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=4)
            )
        
        return None
    
    async def _detect_fomo_alert(self, symbol: str, price_data: Dict, sentiment: Dict) -> Optional[MoonwalkingAlert]:
        """Detect FOMO/Fear extremes"""
        sentiment_score = sentiment.get('score', 0.5)
        price_change = price_data.get('change_1h', 0)
        
        # FOMO condition: very high sentiment + price moving up
        if sentiment_score > self.thresholds['fomo_threshold'] and price_change > 0.05:
            return MoonwalkingAlert(
                id=f"fomo_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.FOMO_ALERT,
                severity=AlertSeverity.HIGH,
                title=f"🔥 {symbol} FOMO ALERT",
                message=f"{symbol} hitting FOMO levels: {sentiment_score*100:.0f}% sentiment + {price_change*100:.1f}% price pump!",
                current_price=price_data['price'],
                price_change_1h=price_change,
                price_change_24h=price_data.get('change_24h', 0),
                volume_24h=price_data['volume_24h'],
                volume_spike=await self._calculate_volume_spike(symbol, price_data['volume_24h']),
                sentiment_score=sentiment_score,
                sentiment_change=sentiment.get('change', 0),
                social_volume=sentiment.get('social_volume', 0),
                social_spike=sentiment.get('social_spike', 1.0),
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=0.8,
                sources=['sentiment_pipeline'],
                exchanges=[],
                triggers=[f"fomo_sentiment_{sentiment_score*100:.0f}%", f"price_momentum_{price_change*100:.1f}%"],
                action="AVOID",  # FOMO often means top
                target_price=None,
                stop_loss=None,
                time_horizon="2h",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=3)
            )
        
        # Fear condition: very low sentiment + price dropping
        elif sentiment_score < (1 - self.thresholds['fomo_threshold']) and price_change < -0.05:
            return MoonwalkingAlert(
                id=f"fear_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.FOMO_ALERT,
                severity=AlertSeverity.MEDIUM,
                title=f"😱 {symbol} FEAR EXTREME",
                message=f"{symbol} extreme fear: {sentiment_score*100:.0f}% sentiment + {price_change*100:.1f}% dump!",
                current_price=price_data['price'],
                price_change_1h=price_change,
                price_change_24h=price_data.get('change_24h', 0),
                volume_24h=price_data['volume_24h'],
                volume_spike=await self._calculate_volume_spike(symbol, price_data['volume_24h']),
                sentiment_score=sentiment_score,
                sentiment_change=sentiment.get('change', 0),
                social_volume=sentiment.get('social_volume', 0),
                social_spike=sentiment.get('social_spike', 1.0),
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=0.7,
                sources=['sentiment_pipeline'],
                exchanges=[],
                triggers=[f"fear_sentiment_{sentiment_score*100:.0f}%", f"price_dump_{abs(price_change)*100:.1f}%"],
                action="BUY",  # Fear often means bottom
                target_price=price_data['price'] * 1.15,
                stop_loss=price_data['price'] * 0.95,
                time_horizon="4h",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=6)
            )
        
        return None
    
    async def _detect_stealth_move(self, symbol: str, price_data: Dict) -> Optional[MoonwalkingAlert]:
        """Detect stealth accumulation - high volume, low price change"""
        volume_spike = await self._calculate_volume_spike(symbol, price_data['volume_24h'])
        price_change = abs(price_data.get('change_1h', 0))
        
        # Stealth conditions: high volume but low price movement
        if (volume_spike > self.thresholds['stealth_volume'] and 
            price_change < 0.05):  # Less than 5% price change
            
            return MoonwalkingAlert(
                id=f"stealth_{symbol}_{int(time.time())}",
                timestamp=datetime.now(),
                symbol=symbol,
                alert_type=AlertType.STEALTH_MOVE,
                severity=AlertSeverity.LOW,
                title=f"👤 {symbol} STEALTH ACCUMULATION",
                message=f"{symbol} stealth activity: {volume_spike:.1f}x volume but only {price_change*100:.1f}% price change",
                current_price=price_data['price'],
                price_change_1h=price_data.get('change_1h', 0),
                price_change_24h=price_data.get('change_24h', 0),
                volume_24h=price_data['volume_24h'],
                volume_spike=volume_spike,
                sentiment_score=0.5,  # Unknown sentiment
                sentiment_change=0,
                social_volume=0,
                social_spike=1.0,
                momentum_score=await self._calculate_momentum(symbol),
                volatility=await self._calculate_volatility(symbol),
                liquidity_score=await self._calculate_liquidity(symbol),
                confidence=0.6,
                sources=['binance'],
                exchanges=['binance'],
                triggers=[f"volume_spike_{volume_spike:.1f}x", f"low_price_change_{price_change*100:.1f}%"],
                action="WATCH",
                target_price=None,
                stop_loss=None,
                time_horizon="1d",
                market_cap=None,
                related_symbols=[],
                news_links=[],
                expires_at=datetime.now() + timedelta(hours=12)
            )
        
        return None
    
    # Helper methods for calculations
    async def _get_price_data(self, symbol: str) -> Optional[Dict]:
        """Get current price data for symbol"""
        try:
            data = self.redis_client.get(f"price:{symbol}")
            if data:
                return json.loads(data)
        except Exception as e:
            self.logger.error(f"❌ Error getting price data for {symbol}: {e}")
        return None
    
    async def _get_symbol_sentiment(self, symbol: str, sentiment_data: Dict) -> Dict:
        """Extract symbol-specific sentiment from overall data"""
        by_symbol = sentiment_data.get('aggregated_sentiment', {}).get('by_symbol', {})
        return by_symbol.get(symbol, {'score': 0.5, 'change': 0, 'social_volume': 0, 'social_spike': 1.0})
    
    async def _calculate_volume_spike(self, symbol: str, current_volume: float) -> float:
        """Calculate volume spike compared to historical average"""
        # Get last 7 days of volume data
        volume_history = [d['volume'] for d in list(self.price_history[symbol])[-168:]]  # Last 7 days hourly
        
        if len(volume_history) < 24:
            return 1.0  # Not enough data
        
        avg_volume = np.mean(volume_history)
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    async def _calculate_momentum(self, symbol: str) -> float:
        """Calculate price momentum score"""
        recent_prices = [d['price'] for d in list(self.price_history[symbol])[-24:]]  # Last 24 hours
        
        if len(recent_prices) < 12:
            return 0.0
        
        # Calculate momentum using linear regression slope
        x = np.arange(len(recent_prices))
        slope = np.polyfit(x, recent_prices, 1)[0]
        
        # Normalize slope relative to current price
        current_price = recent_prices[-1]
        momentum = (slope / current_price) * 24  # 24-hour normalized momentum
        
        return max(-1, min(1, momentum))  # Clamp between -1 and 1
    
    async def _calculate_volatility(self, symbol: str) -> float:
        """Calculate price volatility"""
        recent_prices = [d['price'] for d in list(self.price_history[symbol])[-24:]]
        
        if len(recent_prices) < 12:
            return 0.0
        
        returns = np.diff(recent_prices) / recent_prices[:-1]
        return np.std(returns) * np.sqrt(24)  # 24-hour annualized volatility
    
    async def _calculate_liquidity(self, symbol: str) -> float:
        """Calculate liquidity score based on volume and spread"""
        # Simplified liquidity score based on volume
        recent_volumes = [d['volume'] for d in list(self.price_history[symbol])[-24:]]
        
        if len(recent_volumes) < 12:
            return 0.5
        
        avg_volume = np.mean(recent_volumes)
        
        # Normalize to 0-1 scale (assuming $10M+ is high liquidity)
        liquidity_score = min(1.0, avg_volume / 10_000_000)
        
        return liquidity_score
    
    async def _emit_alert(self, alert: MoonwalkingAlert):
        """Emit alert to all subscribers"""
        try:
            # Check for duplicate alerts
            alert_key = f"{alert.symbol}_{alert.alert_type.value}_{alert.severity.value}"
            
            # Don't spam same alerts within 10 minutes
            last_alert_time = self.redis_client.get(f"last_alert:{alert_key}")
            if last_alert_time:
                last_time = datetime.fromisoformat(last_alert_time)
                if datetime.now() - last_time < timedelta(minutes=10):
                    return
            
            # Store this alert
            self.redis_client.setex(f"last_alert:{alert_key}", 600, datetime.now().isoformat())
            
            # Add to active alerts
            self.active_alerts[alert.id] = alert
            self.alert_history.append(alert)
            
            # Store in Redis for API access
            self.redis_client.setex(
                f"alert:{alert.id}",
                7200,  # 2 hour expiry
                json.dumps(asdict(alert), default=str)
            )
            
            # Log the alert
            self.logger.warning(f"🚨 ALERT: {alert.severity.value} {alert.title} - {alert.message}")
            
            # Notify subscribers (WebSocket, webhooks, etc.)
            await self._notify_subscribers(alert)
            
        except Exception as e:
            self.logger.error(f"❌ Error emitting alert: {e}")
    
    async def _notify_subscribers(self, alert: MoonwalkingAlert):
        """Notify all alert subscribers"""
        notification = {
            'type': 'alert',
            'alert': asdict(alert),
            'timestamp': datetime.now().isoformat()
        }
        
        # Send to WebSocket subscribers (implement as needed)
        # Send to Discord/Telegram bots (implement as needed)
        # Send to webhooks (implement as needed)
        
        pass
    
    async def _update_market_state(self):
        """Update overall market state"""
        # This would integrate with broader market data
        pass
    
    async def _cleanup_expired_alerts(self):
        """Clean up expired alerts"""
        current_time = datetime.now()
        expired_alerts = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if alert.expires_at < current_time
        ]
        
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self) -> List[MoonwalkingAlert]:
        """Get all currently active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 50) -> List[MoonwalkingAlert]:
        """Get recent alert history"""
        return list(self.alert_history)[-limit:]
    
    async def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
    
    async def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True


# Test function
async def test_moonwalking_detector():
    """Test the Moonwalking detection system"""
    config = {
        'tracked_symbols': ['BTC', 'ETH', 'SOL'],
        'api_endpoints': {
            'sentiment': 'http://localhost:8000'
        }
    }
    
    detector = MoonwalkingDetector(config)
    await detector.initialize()
    
    print("🌙 Moonwalking Detection System Test")
    print("=" * 50)
    
    # Simulate running for a short time
    await asyncio.sleep(60)
    
    # Get alerts
    active_alerts = detector.get_active_alerts()
    print(f"Active alerts: {len(active_alerts)}")
    
    for alert in active_alerts:
        print(f"- {alert.severity.value} {alert.title}")

if __name__ == "__main__":
    asyncio.run(test_moonwalking_detector())