import React, { useEffect, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import StarIcon from './StarIcon';

// Accept onWatchlistChange and topWatchlist for proper state sync
import PropTypes from 'prop-types';

const GainersTable1Min = ({ refreshTrigger, onWatchlistChange, topWatchlist, sliceStart, sliceEnd, fixedRows, hideShowMore }) => {
  const { latestData, isConnected, isPolling, oneMinThrottleMs } = useWebSocket();
  const lastRenderRef = useRef(0);
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
      const now = Date.now();
  const throttleMs = typeof oneMinThrottleMs === 'number' ? oneMinThrottleMs : 7000;
  if (now - (lastRenderRef.current || 0) < throttleMs) return; // throttle to reduce churn
      lastRenderRef.current = now;
      console.log('📊 Using WebSocket data for 1-min gainers:', latestData.crypto.length, 'items');
      // Respect backend ordering (already peak-held and sorted there)
      const mapped = latestData.crypto
        .slice(0, 20)
        .map((item, index) => ({
          rank: item.rank || (index + 1),
          symbol: item.symbol?.replace('-USD', '') || 'N/A',
          price: item.current_price ?? item.price ?? 0,
          change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
          isPeak: typeof item.peak_gain === 'number',
          trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
          trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
          trendScore: item.trend_score ?? item.trendScore ?? 0
        }));
      setData(mapped);
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
          // Respect backend ordering; take top 10
  const mapped = response.data
    .slice(0, 20)
      .map((item, index) => ({
              rank: item.rank || (index + 1),
              symbol: item.symbol?.replace('-USD', '') || 'N/A',
              price: item.current_price ?? item.price ?? 0,
        change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
        isPeak: typeof item.peak_gain === 'number',
    trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
    trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
    trendScore: item.trend_score ?? item.trendScore ?? 0
            }));
          if (isMounted) {
            setData(mapped);
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

  // Apply optional slicing for two-column layouts
  const visibleData = Array.isArray(data)
    ? (typeof sliceStart === 'number' || typeof sliceEnd === 'number')
      ? data.slice(sliceStart ?? 0, sliceEnd ?? data.length)
      : data
    : [];

  if (loading && visibleData.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-[#C026D3] font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if (visibleData.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  // Determine if watchlist is present (from topWatchlist)
  const isWatchlistVisible = topWatchlist && topWatchlist.length > 0;
  // Show a fixed count per instance when used in two-column layout
  const rowsToShow = typeof fixedRows === 'number' && fixedRows > 0
    ? Math.min(fixedRows, visibleData.length)
    : Math.min(4, visibleData.length);

  return (
    <div className="flex flex-col space-y-1 w-full h-full min-h-[380px] sm:min-h-[420px] px-2 sm:px-3 md:px-0 align-stretch transition-all duration-300">
  {visibleData.slice(0, rowsToShow).map((item, idx) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        // Check if symbol is in watchlist (handle both string and object formats)
        const isInWatchlist = watchlist.some(watchlistItem => 
          typeof watchlistItem === 'string' ? watchlistItem === item.symbol : watchlistItem.symbol === item.symbol
        );
        const isPopping = popStar === item.symbol;
        const showAdded = addedBadge === item.symbol;
        return (
          <React.Fragment key={item.symbol}>
    <div className={`crypto-row flex items-center px-2 py-1 rounded-lg mb-1 transition`}>
              <a href={coinbaseUrl} target="_blank" rel="noopener noreferrer" className="block group flex-1">
                <div
                  className="flex items-center justify-between p-3 sm:p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group hover:scale-[1.02] sm:hover:scale-[1.035] hover:z-10"
                  style={{
                    boxShadow: 'none',
                    background: 'transparent'
                  }}
                >
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                      style={{
                        background: 'radial-gradient(circle at 50% 50%, rgba(236,167,155,0.18) 0%, rgba(236,167,155,0.10) 45%, rgba(255,209,180,0.06) 70%, transparent 100%)',
                        top: '-15%',
                        left: '-15%',
                        position: 'absolute',
                        mixBlendMode: 'normal'
                      }}
                    />
                  </span>
                  <div className="flex items-center gap-3 sm:gap-4">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm">{item.rank}</div>
                    <div className="flex-1 flex items-center gap-3 ml-4">
                      <span className="font-bold text-white text-lg tracking-wide">{item.symbol}</span>
                      {showAdded && <span className="ml-2 px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Added!</span>}
                    </div>
                  </div>
                  <div className="ml-0 sm:ml-4 flex items-center gap-3 justify-end w-full md:w-[360px]">
                    {/* Price Column (current and previous price, right-aligned) */}
                    <div className="flex flex-col items-end w-[110px] sm:w-[120px] md:w-[130px] shrink-0">
                      <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text tabular-nums whitespace-nowrap font-mono text-right">
                        {typeof item.price === 'number' && Number.isFinite(item.price)
                          ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}`
                          : 'N/A'}
                      </span>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 select-text tabular-nums whitespace-nowrap text-right">
                        {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                          ? (() => {
                               const prevPrice = item.price / (1 + item.change / 100);
                               return `$${prevPrice < 1 && prevPrice > 0 ? prevPrice.toFixed(4) : prevPrice.toFixed(2)}`;
                             })()
                          : '--'}
                      </span>
                    </div>
                    {/* Change Percentage and timeframe (two-line: percent on top, arrow+chips+timeframe below) */}
                    <div className="flex flex-col items-end w-[120px] sm:w-[140px] md:w-[160px] shrink-0">
                      <div className={`font-bold text-base sm:text-lg md:text-xl ${item.change > 0 ? 'text-[#C026D3]' : 'text-pink'}`}> 
                        {item.change > 0 && <span className="font-mono mr-0.5">+</span>}
                        <span className="tabular-nums whitespace-nowrap font-mono">{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <div className="flex items-center justify-end gap-1 mt-0.5 whitespace-nowrap">
                        {/* Trend arrow */}
                        {item.trendDirection && item.trendDirection !== 'flat' && (() => {
                          const s = Math.max(0, Math.min(3, Number(item.trendScore) || 0));
                          let fontSize = '0.9em';
                          if (s >= 1.5) fontSize = '1.2em'; else if (s >= 0.5) fontSize = '1.0em';
                          const color = item.trendDirection === 'up'
                            ? (s >= 1.5 ? '#10B981' : s >= 0.5 ? '#34D399' : '#9AE6B4')
                            : (s >= 1.5 ? '#EF4444' : s >= 0.5 ? '#F87171' : '#FEB2B2');
                          return (
                            <span
                              className="font-semibold"
                              style={{ fontSize, color }}
                              title={`trend: ${item.trendDirection}${item.trendStreak ? ` x${item.trendStreak}` : ''} \u2022 score ${Number(item.trendScore||0).toFixed(2)}`}
                              aria-label={`trend ${item.trendDirection}`}
                            >
                              {item.trendDirection === 'up' ? '↑' : '↓'}
                            </span>
                          );
                        })()}
                        {/* Peak badge */}
                        {item.isPeak && (
                          <span className="px-1.5 py-0.5 rounded bg-purple-700/40 text-purple-200 text-[10px] leading-none font-semibold align-middle">
                            peak
                          </span>
                        )}
                        {/* Streak chip (only if >=2) */}
                        {typeof item.trendStreak === 'number' && item.trendStreak >= 2 && (
                          <span className="px-1 py-0.5 rounded bg-[#6B0C86]/30 text-[#E9C5F2] text-[10px] leading-none font-semibold align-middle">
                            x{item.trendStreak}
                          </span>
                        )}
                        <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">1-Min</span>
                      </div>
                    </div>
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
    {/* Show More/Show Less button is typically handled by the parent two-column section. Keep hidden unless explicitly enabled. */}
  {!hideShowMore && Array.isArray(visibleData) && visibleData.length > 8 && (
        <button
          className="mt-2 mx-auto px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
          style={{ width: 'fit-content' }}
          onClick={() => setShowAll(s => !s)}
        >
    {showAll ? 'Show Less' : `Show More (${Math.min(12, visibleData.length) - 8})`}
        </button>
      )}
    </div>
  );
}

GainersTable1Min.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array,
  sliceStart: PropTypes.number,
  sliceEnd: PropTypes.number,
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool
};

export default GainersTable1Min;