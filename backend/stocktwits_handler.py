import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("sentiment.stocktwits")

class StockTwitsHandler:
    """
    Handler for fetching sentiment data from StockTwits public API.
    No API key required for public streams.
    """
    
    BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol"
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ["BTC", "ETH", "SOL"]
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def fetch_symbol_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch messages for a symbol and calculate basic sentiment.
        StockTwits messages often have a 'entities.sentiment' field (Bullish/Bearish).
        """
        # StockTwits crypto symbols usually end with .X (e.g. BTC.X)
        query_symbol = f"{symbol.upper()}.X" if not symbol.endswith(".X") else symbol.upper()
        url = f"{self.BASE_URL}/{query_symbol}.json"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 404:
                    # Try without .X just in case
                    url = f"{self.BASE_URL}/{symbol.upper()}.json"
                    async with self.session.get(url) as response2:
                        if response2.status != 200:
                            return None
                        data = await response2.json()
                elif response.status != 200:
                    logger.warning(f"StockTwits error {response.status} for {symbol}")
                    return None
                else:
                    data = await response.json()
                    
            messages = data.get('messages', [])
            if not messages:
                return None
                
            bullish_count = 0
            bearish_count = 0
            total_with_sentiment = 0
            
            for msg in messages:
                entities = msg.get('entities', {})
                sentiment = entities.get('sentiment', {})
                if sentiment:
                    basic = sentiment.get('basic')
                    if basic == 'Bullish':
                        bullish_count += 1
                        total_with_sentiment += 1
                    elif basic == 'Bearish':
                        bearish_count += 1
                        total_with_sentiment += 1
            
            # Calculate score 0..1 (0.5 is neutral)
            if total_with_sentiment > 0:
                # Simple ratio: Bullish / Total
                score = bullish_count / total_with_sentiment
            else:
                score = 0.5 # Neutral if no explicit sentiment tags
                
            return {
                "source": "StockTwits",
                "symbol": symbol,
                "sentiment": score,
                "message_count": len(messages),
                "sentiment_tagged_count": total_with_sentiment,
                "bullish": bullish_count,
                "bearish": bearish_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching StockTwits for {symbol}: {e}")
            return None

    async def fetch_all_symbols(self) -> List[Dict[str, Any]]:
        """Fetch sentiment for all configured symbols"""
        tasks = [self.fetch_symbol_sentiment(sym) for sym in self.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for res in results:
            if isinstance(res, dict):
                valid_results.append(res)
            elif isinstance(res, Exception):
                logger.error(f"Task failed: {res}")
                
        return valid_results
