import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import requests
import time
from datetime import datetime, timedelta

class TechnicalAnalysis:
    """Technical analysis calculations for cryptocurrency data"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return None
            
        prices = np.array(prices)
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow + signal:
            return {"macd": None, "signal": None, "histogram": None}
            
        prices = pd.Series(prices)
        
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": round(macd_line.iloc[-1], 6),
            "signal": round(signal_line.iloc[-1], 6),
            "histogram": round(histogram.iloc[-1], 6)
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Dict:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {"upper": None, "middle": None, "lower": None}
            
        prices = np.array(prices)
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        return {
            "upper": round(sma + (std * std_dev), 4),
            "middle": round(sma, 4),
            "lower": round(sma - (std * std_dev), 4)
        }
    
    @staticmethod
    def calculate_volume_profile(prices: List[float], volumes: List[float]) -> Dict:
        """Calculate basic volume analysis"""
        if not volumes or len(volumes) != len(prices):
            return {"avg_volume": None, "volume_trend": "neutral"}
            
        recent_vol = np.mean(volumes[-5:]) if len(volumes) >= 5 else volumes[-1]
        avg_vol = np.mean(volumes)
        
        if recent_vol > avg_vol * 1.5:
            trend = "high"
        elif recent_vol < avg_vol * 0.5:
            trend = "low"
        else:
            trend = "normal"
            
        return {
            "avg_volume": round(avg_vol, 2),
            "recent_volume": round(recent_vol, 2),
            "volume_trend": trend
        }

class CoinbaseDataFetcher:
    """Fetch historical data from Coinbase Pro API"""
    
    BASE_URL = "https://api.exchange.coinbase.com"
    
    @classmethod
    def get_historical_data(cls, symbol: str, hours: int = 24) -> Optional[Dict]:
        """Fetch historical price data for technical analysis"""
        try:
            # Convert hours to granularity (seconds per candle)
            if hours <= 6:
                granularity = 300  # 5-minute candles
            elif hours <= 24:
                granularity = 900  # 15-minute candles
            else:
                granularity = 3600  # 1-hour candles
                
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            url = f"{cls.BASE_URL}/products/{symbol}-USD/candles"
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'granularity': granularity
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            candles = response.json()
            if not candles:
                return None
                
            # Sort by timestamp (ascending)
            candles.sort(key=lambda x: x[0])
            
            # Extract OHLCV data
            timestamps = [candle[0] for candle in candles]
            opens = [float(candle[3]) for candle in candles]
            highs = [float(candle[2]) for candle in candles]
            lows = [float(candle[1]) for candle in candles]
            closes = [float(candle[4]) for candle in candles]
            volumes = [float(candle[5]) for candle in candles]
            
            return {
                'timestamps': timestamps,
                'opens': opens,
                'highs': highs,
                'lows': lows,
                'closes': closes,
                'volumes': volumes,
                'symbol': symbol,
                'granularity_minutes': granularity // 60
            }
            
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return None

def get_technical_analysis(symbol: str) -> Dict:
    """Get complete technical analysis for a symbol"""
    # Fetch historical data
    historical_data = CoinbaseDataFetcher.get_historical_data(symbol, hours=72)  # 3 days for better indicators
    
    if not historical_data:
        return {
            'symbol': symbol,
            'error': 'Unable to fetch historical data',
            'rsi': None,
            'macd': None,
            'bollinger': None,
            'volume_analysis': None,
            'recommendation': 'No data available'
        }
    
    closes = historical_data['closes']
    volumes = historical_data['volumes']
    
    # Calculate indicators
    ta = TechnicalAnalysis()
    rsi = ta.calculate_rsi(closes)
    macd = ta.calculate_macd(closes)
    bollinger = ta.calculate_bollinger_bands(closes)
    volume_analysis = ta.calculate_volume_profile(closes, volumes)
    
    # Generate simple recommendation
    recommendation = generate_recommendation(rsi, macd, closes[-1], bollinger)
    
    return {
        'symbol': symbol,
        'current_price': closes[-1],
        'rsi': rsi,
        'macd': macd,
        'bollinger_bands': bollinger,
        'volume_analysis': volume_analysis,
        'recommendation': recommendation,
        'last_updated': datetime.now().isoformat(),
        'data_points': len(closes)
    }

def generate_recommendation(rsi: Optional[float], macd: Dict, current_price: float, bollinger: Dict) -> str:
    """Generate a simple trading recommendation based on indicators"""
    signals = []
    
    # RSI signals
    if rsi:
        if rsi > 70:
            signals.append("RSI overbought")
        elif rsi < 30:
            signals.append("RSI oversold")
        else:
            signals.append("RSI neutral")
    
    # MACD signals
    if macd['macd'] and macd['signal']:
        if macd['macd'] > macd['signal']:
            signals.append("MACD bullish")
        else:
            signals.append("MACD bearish")
    
    # Bollinger Bands
    if bollinger['upper'] and bollinger['lower']:
        if current_price > bollinger['upper']:
            signals.append("Above upper Bollinger Band")
        elif current_price < bollinger['lower']:
            signals.append("Below lower Bollinger Band")
        else:
            signals.append("Within Bollinger Bands")
    
    # Simple recommendation logic
    bullish_count = sum(1 for s in signals if any(word in s.lower() for word in ['bullish', 'oversold', 'below lower']))
    bearish_count = sum(1 for s in signals if any(word in s.lower() for word in ['bearish', 'overbought', 'above upper']))
    
    if bullish_count > bearish_count:
        recommendation = "🟢 Cautiously Bullish"
    elif bearish_count > bullish_count:
        recommendation = "🔴 Cautiously Bearish"
    else:
        recommendation = "🟡 Neutral - Wait for clearer signals"
    
    return f"{recommendation} | {' | '.join(signals[:3])}"  # Limit to 3 signals