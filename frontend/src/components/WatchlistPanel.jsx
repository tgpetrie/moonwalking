import React, { useState, useEffect } from 'react';
import { getWatchlist, removeFromWatchlist } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import StarIcon from './StarIcon';

const WatchlistPanel = ({ onWatchlistChange, topWatchlist }) => {
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [animatingRemoval, setAnimatingRemoval] = useState(null);
  const { latestData, fetchPricesForSymbols, isConnected, isPolling } = useWebSocket();

  // Sync with parent watchlist
  useEffect(() => {
    if (topWatchlist) {
      setWatchlist(topWatchlist);
    } else {
      // Fetch from localStorage if no parent data
      getWatchlist().then(setWatchlist);
    }
  }, [topWatchlist]);

  // Get real-time prices for watchlist symbols
  const getWatchlistWithPrices = () => {
    if (!watchlist || watchlist.length === 0) return [];

    return watchlist.map(item => {
      const symbol = typeof item === 'string' ? item : item.symbol;
      const priceAtAdd = typeof item === 'object' ? item.priceAtAdd : 0;
      
      // Try to get current price from WebSocket data first
      let currentPrice = priceAtAdd;
      if (latestData.prices && latestData.prices[symbol]) {
        currentPrice = latestData.prices[symbol].price;
      } else if (latestData.crypto && Array.isArray(latestData.crypto)) {
        // Fallback to crypto data
        const cryptoData = latestData.crypto.find(coin => 
          coin.symbol === symbol || coin.symbol === `${symbol}-USD`
        );
        if (cryptoData) {
          currentPrice = cryptoData.current_price || cryptoData.price || priceAtAdd;
        }
      }

      const change = priceAtAdd > 0 ? ((currentPrice - priceAtAdd) / priceAtAdd) * 100 : 0;

      return {
        symbol,
        priceAtAdd: priceAtAdd || 0,
        currentPrice: currentPrice || 0,
        change,
        timestamp: Date.now()
      };
    });
  };

  const handleRemove = async (symbol) => {
    setAnimatingRemoval(symbol);
    setTimeout(async () => {
      const updated = await removeFromWatchlist(symbol);
      setWatchlist(updated);
      if (onWatchlistChange) onWatchlistChange(updated);
      setAnimatingRemoval(null);
    }, 300);
  };

  const watchlistWithPrices = getWatchlistWithPrices();

  // Connection status indicator
  const getConnectionStatus = () => {
    if (isConnected) {
      return { text: 'Live', color: 'text-green-400', icon: '🔗' };
    } else if (isPolling) {
      return { text: 'Polling', color: 'text-yellow-400', icon: '🔄' };
    } else {
      return { text: 'Offline', color: 'text-red-400', icon: '📡' };
    }
  };

  if (!watchlist || watchlist.length === 0) {
    return (
      <div className="flex flex-col space-y-4 w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0">
        <div className="text-center py-8">
          <div className="text-muted font-mono text-sm">No coins in watchlist</div>
          <div className="text-muted font-mono text-xs mt-2">Click ⭐ to add coins</div>
        </div>
      </div>
    );
  }

  const status = getConnectionStatus();

  return (
    <div className="flex flex-col space-y-1 w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 align-stretch transition-all duration-300">
      {/* Connection Status Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400">MY WATCHLIST</span>
          <div className={`flex items-center gap-1 text-xs font-mono ${status.color}`}>
            <span>{status.icon}</span>
            <span>{status.text}</span>
          </div>
        </div>
        <div className="text-xs font-mono text-gray-500">
          {watchlistWithPrices.length} coin{watchlistWithPrices.length !== 1 ? 's' : ''}
        </div>
      </div>

      {watchlistWithPrices.map((item, idx) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        const isRemoving = animatingRemoval === item.symbol;
        const changeColor = item.change > 0 ? 'text-blue' : item.change < 0 ? 'text-pink' : 'text-gray-400';
        
        return (
          <React.Fragment key={item.symbol}>
            <div className={`crypto-row flex items-center px-2 py-1 rounded-lg mb-1 hover:bg-gray-800 transition ${isRemoving ? 'opacity-50 scale-95' : ''}`}>
              <a href={coinbaseUrl} target="_blank" rel="noopener noreferrer" className="block flex-1">
                <div
                  className="flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group hover:text-amber-500 hover:scale-[1.035] hover:z-10"
                  style={{
                    boxShadow: 'none',
                    background: 'rgba(10, 10, 18, 0.18)'
                  }}
                >
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block rounded-2xl transition-all duration-150 opacity-0 group-hover:opacity-100 group-hover:w-[160%] group-hover:h-[160%] w-[120%] h-[120%]"
                      style={{
                        background: 'radial-gradient(circle at 50% 50%, rgba(129,9,150,0.28) 0%, rgba(129,9,150,0.18) 35%, rgba(129,9,150,0.10) 60%, rgba(129,9,150,0.04) 80%, transparent 100%)',
                        top: '-30%',
                        left: '-30%',
                        position: 'absolute',
                        filter: 'blur(1.5px)'
                      }}
                    />
                  </span>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-600/40 text-purple-300 font-bold text-sm">
                      ⭐
                    </div>
                    <div className="flex-1 flex items-center gap-3 ml-4">
                      <span className="font-bold text-white text-lg tracking-wide">{item.symbol}</span>
                    </div>
                  </div>
                  <div className="flex flex-row flex-wrap items-center gap-2 sm:gap-4 ml-0 sm:ml-4 w-full sm:w-auto">
                    <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px] ml-2 sm:ml-4">
                      <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text">
                        ${item.currentPrice > 0 
                          ? (item.currentPrice < 1 && item.currentPrice > 0 
                             ? item.currentPrice.toFixed(4) 
                             : item.currentPrice.toFixed(2))
                          : 'N/A'}
                      </span>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 select-text">
                        ${item.priceAtAdd > 0 ? item.priceAtAdd.toFixed(2) : '--'}
                      </span>
                    </div>
                    <div className="flex flex-col items-end min-w-[56px] sm:min-w-[80px]">
                      <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${changeColor}`}>
                        <span>{item.change !== 0 ? `${item.change > 0 ? '+' : ''}${item.change.toFixed(2)}%` : '--'}</span>
                      </div>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">Since Add</span>
                    </div>
                    <button
                      onClick={e => { e.preventDefault(); handleRemove(item.symbol); }}
                      tabIndex={0}
                      aria-label="Remove from watchlist"
                      className="bg-transparent border-none p-0 m-0 cursor-pointer"
                      style={{ minWidth: '24px', minHeight: '24px' }}
                    >
                      <StarIcon
                        filled={true}
                        className="opacity-80 hover:opacity-100"
                        style={{ 
                          minWidth: '20px', 
                          minHeight: '20px', 
                          maxWidth: '28px', 
                          maxHeight: '28px', 
                          transition: 'transform 0.2s' 
                        }}
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </a>
            </div>
            {idx < watchlistWithPrices.length - 1 && (
              <div
                className="mx-auto my-0.5"
                style={{
                  height: '2px',
                  width: '60%',
                  background: 'linear-gradient(90deg,rgba(0,176,255,0.10) 0%,rgba(10,10,18,0.38) 50%,rgba(0,176,255,0.10) 100%)',
                  borderRadius: '2px'
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default WatchlistPanel;