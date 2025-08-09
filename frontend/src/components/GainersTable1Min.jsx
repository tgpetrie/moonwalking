import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import StarIcon from './StarIcon';

// Accept onWatchlistChange and topWatchlist for proper state sync
import PropTypes from 'prop-types';

const GainersTable1Min = ({ refreshTrigger, onWatchlistChange, topWatchlist }) => {
  const { latestData, isConnected, isPolling } = useWebSocket();
  // Inject animation styles for pop/fade effects
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('gainers-1min-table-animations')) {
      const style = document.createElement('style');
      style.id = 'gainers-1min-table-animations';
      style.innerHTML = `
        @keyframes starPop {
          0% { transform: scale(1); }
          40% { transform: scale(1.35); }
          70% { transform: scale(0.92); }
          100% { transform: scale(1); }
        }
        .animate-star-pop {
          animation: starPop 0.35s cubic-bezier(.4,2,.6,1) both;
        }
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(-8px) scale(0.9); }
          10% { opacity: 1; transform: translateY(0) scale(1.05); }
          80% { opacity: 1; transform: translateY(0) scale(1.05); }
          100% { opacity: 0; transform: translateY(-8px) scale(0.9); }
        }
        .animate-fade-in-out {
          animation: fadeInOut 1.2s cubic-bezier(.4,2,.6,1) both;
        }
        @keyframes breatheCard {
          0% { transform: scale(1); box-shadow: 0 1px 8px 0 rgba(0,176,255,0.06); }
          50% { transform: scale(1.005); box-shadow: 0 2px 10px 0 rgba(0,176,255,0.08); }
          100% { transform: scale(1); box-shadow: 0 1px 8px 0 rgba(0,176,255,0.06); }
        }
        .animate-breathe-card {
          animation: breatheCard 5s cubic-bezier(.4,1.6,.6,1) infinite;
        }
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Only use local watchlist for UI feedback, but display logic uses topWatchlist from parent
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [addedBadge, setAddedBadge] = useState(null); // symbol for 'Added!' badge
  const [showAll, setShowAll] = useState(false); // expand/collapse for gainers list

  // Return a purple dot style for strong signals only, else empty
  const getDotStyle = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) return 'bg-green-400'; // Strong high (buy)
    if (absChange >= 2) return 'bg-blue-400'; // Strong (buy)
    return '';
  };

  const getBadgeText = (change) => {
    // Badge logic not needed for 1-min table (matching 3-min table format)
    return null;
  };

  // Update data from WebSocket context when available
  useEffect(() => {
    if (latestData.crypto && Array.isArray(latestData.crypto)) {
      console.log('📊 Using WebSocket data for 1-min gainers:', latestData.crypto.length, 'items');
      const sorted = latestData.crypto
        .sort((a, b) => (b.price_change_percentage_1min || 0) - (a.price_change_percentage_1min || 0))
        .slice(0, 10)
        .map((item, index) => ({
          rank: item.rank || (index + 1),
          symbol: item.symbol?.replace('-USD', '') || 'N/A',
          price: item.current_price || 0,
          change: item.price_change_percentage_1min || 0
        }));
      setData(sorted);
      setLoading(false);
      setError(null);
    }
  }, [latestData.crypto]);

  // Fallback API fetch when WebSocket data is not available
  useEffect(() => {
    let isMounted = true;
    const fetchGainersData = async () => {
      // Only fetch if we don't have WebSocket data
      if (latestData.crypto && latestData.crypto.length > 0) {
        console.log('⏩ Skipping API fetch - using WebSocket data');
        return;
      }
      
      try {
        console.log('🌐 Fetching 1-min gainers data via API');
        const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          // Sort by 1-min change descending, take top 10
          const sorted = response.data
            .sort((a, b) => (b.price_change_percentage_1min || 0) - (a.price_change_percentage_1min || 0))
            .slice(0, 10)
            .map((item, index) => ({
              rank: item.rank || (index + 1),
              symbol: item.symbol?.replace('-USD', '') || 'N/A',
              price: item.current_price || 0,
              change: item.price_change_percentage_1min || 0
            }));
          if (isMounted) {
            setData(sorted);
          }
  }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching gainers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
        }
      }
    };
    
    // Only start interval if not connected to WebSocket and not already polling
    if (!isConnected && !isPolling) {
      fetchGainersData();
      const interval = setInterval(fetchGainersData, 30000);
      return () => { isMounted = false; clearInterval(interval); };
    } else {
      // Initial fetch if needed
      if (data.length === 0) fetchGainersData();
    }
    
    return () => { isMounted = false; };
  }, [refreshTrigger, isConnected, isPolling, latestData.crypto]);

  // Always sync local watchlist to topWatchlist if provided
  useEffect(() => {
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
    } else {
      async function fetchWatchlist() {
        const data = await getWatchlist();
        setWatchlist(data);
        if (onWatchlistChange) onWatchlistChange(data);
      }
      fetchWatchlist();
    }
    // eslint-disable-next-line
  }, [refreshTrigger, topWatchlist]);

  const handleToggleWatchlist = async (symbol) => {
    // Check if symbol exists in watchlist (handle both string and object formats)
    const existsInWatchlist = watchlist.some(item => 
      typeof item === 'string' ? item === symbol : item.symbol === symbol
    );
    
    if (!existsInWatchlist) {
      setPopStar(symbol);
      setAddedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setAddedBadge(null), 1200);
      
      // Find current price for this symbol from data
      const coinData = data.find(coin => coin.symbol === symbol);
      const currentPrice = coinData ? coinData.price : null;
      
      console.log('Adding to watchlist:', symbol, 'at price:', currentPrice);
      const updated = await addToWatchlist(symbol, currentPrice);
      console.log('Added to watchlist, new list:', updated);
      setWatchlist(updated);
      if (onWatchlistChange) onWatchlistChange(updated);
    } else {
      console.log('Symbol already in watchlist, not adding:', symbol);
    }
  };

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-blue font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if (error && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">Backend unavailable (no data)</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  // Determine if watchlist is present (from topWatchlist)
  const isWatchlistVisible = topWatchlist && topWatchlist.length > 0;
  // Show only top 4 gainers by default, expand/collapse for up to 10
  const rowsToShow = showAll ? data.length : Math.min(4, data.length);

  return (
    <div className="flex flex-col space-y-1 w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 align-stretch transition-all duration-300">
      {data.slice(0, rowsToShow).map((item, idx) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        // Check if symbol is in watchlist (handle both string and object formats)
        const isInWatchlist = watchlist.some(watchlistItem => 
          typeof watchlistItem === 'string' ? watchlistItem === item.symbol : watchlistItem.symbol === item.symbol
        );
        const isPopping = popStar === item.symbol;
        const showAdded = addedBadge === item.symbol;
        return (
          <React.Fragment key={item.symbol}>
            <div className={`crypto-row flex items-center px-2 py-1 rounded-lg mb-1 hover:bg-gray-800 transition`}>
              <a href={coinbaseUrl} target="_blank" rel="noopener noreferrer" className="block flex-1">
                <div
                  className="flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group hover:text-amber-500 hover:scale-[1.035] hover:z-10"
                  style={{
                    boxShadow: 'none', // Remove shadow/border
                    background: 'rgba(10, 10, 18, 0.18)' // Transparent fill
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
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue/40 text-blue font-bold text-sm">{item.rank}</div>
                    <div className="flex-1 flex items-center gap-3 ml-4">
                      <span className="font-bold text-white text-lg tracking-wide">{item.symbol}</span>
                      {showAdded && <span className="ml-2 px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Added!</span>}
                    </div>
                  </div>
                  <div className="flex flex-row flex-wrap items-center gap-2 sm:gap-4 ml-0 sm:ml-4 w-full sm:w-auto">
                    <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px] ml-2 sm:ml-4">
                      <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text">
                        {typeof item.price === 'number' && Number.isFinite(item.price)
                          ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}`
                          : 'N/A'}
                      </span>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 select-text">
                        {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                          ? `$${(item.price / (1 + item.change / 100)).toFixed(2)}`
                          : '--'}
                      </span>
                    </div>
                    <div className="flex flex-col items-end min-w-[56px] sm:min-w-[60px]">
                      <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${item.change > 0 ? 'text-blue' : 'text-pink'}`}> 
                        <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">1-Min</span>
                    </div>
                    {getDotStyle(item.change) && (
                      <div className={`w-3 h-3 rounded-full ${getDotStyle(item.change)}`}></div>
                    )}
                    <button
                      onClick={e => { e.preventDefault(); handleToggleWatchlist(item.symbol); }}
                      tabIndex={0}
                      aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                      aria-pressed={isInWatchlist}
                      className="bg-transparent border-none p-0 m-0 cursor-pointer"
                      style={{ minWidth: '24px', minHeight: '24px' }}
                    >
                      <StarIcon
                        filled={isInWatchlist}
                        className={(isInWatchlist ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80') + (isPopping ? ' animate-star-pop' : '')}
                        style={{ minWidth: '20px', minHeight: '20px', maxWidth: '28px', maxHeight: '28px', transition: 'transform 0.2s' }}
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </a>
            </div>
            {idx < rowsToShow - 1 && (
              <div
                className="mx-auto my-0.5"
                style={{
                  height: '2px',
                  width: '60%',
                  background: 'linear-gradient(90deg,rgba(0,176,255,0.10) 0%,rgba(10,10,18,0.38) 50%,rgba(0,176,255,0.10) 100%)',
                  borderRadius: '2px'
                }}
              ></div>
            )}
          </React.Fragment>
        );
      })}
      {/* Show More/Show Less button if more than 4 items */}
      {Array.isArray(data) && data.length > 4 && (
        <button
          className="mt-2 mx-auto px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
          style={{ width: 'fit-content' }}
          onClick={() => setShowAll(s => !s)}
        >
          {showAll ? 'Show Less' : `Show More (${Math.min(10, data.length) - 4})`}
        </button>
      )}
    </div>
  );
}

GainersTable1Min.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array
};

export default GainersTable1Min;