import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import StarIcon from './StarIcon';

const LosersTable = ({ refreshTrigger }) => {
  // Inject animation styles for pop/fade effects
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('losers-table-animations')) {
      const style = document.createElement('style');
      style.id = 'losers-table-animations';
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
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [addedBadge, setAddedBadge] = useState(null); // symbol for 'Added!' badge

  const getDotStyle = (badge) => {
    if (badge === 'STRONG HIGH') {
      return 'bg-red-400 shadow-red-400/50';
    } else if (badge === 'STRONG') {
      return 'bg-orange-400 shadow-orange-400/50';
    } else {
      return 'bg-yellow-400 shadow-yellow-400/50';
    }
  };

  const getBadgeText = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
    return 'MODERATE';
  };

  useEffect(() => {
    let isMounted = true;
    const fetchLosersData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.losersTable);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const losersWithRanks = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_3min || 0,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3min || 0))
          }));
          if (isMounted) setData(losersWithRanks.slice(0, 7));
        } else if (isMounted && data.length === 0) {
          // Fallback data showing some crypto with negative/low gains
          setData([
            { rank: 1, symbol: 'PEPE', price: 0.00000996, change: -2.45, badge: 'MODERATE' },
            { rank: 2, symbol: 'SHIB', price: 0.00002156, change: -1.82, badge: 'MODERATE' },
            { rank: 3, symbol: 'FLOKI', price: 0.000234, change: -0.95, badge: 'MODERATE' },
            { rank: 4, symbol: 'BONK', price: 0.00001717, change: -0.67, badge: 'MODERATE' },
            { rank: 5, symbol: 'WIF', price: 2.543, change: -0.23, badge: 'MODERATE' },
            { rank: 6, symbol: 'NEW1', price: 1.234, change: -0.45, badge: 'MODERATE' },
            { rank: 7, symbol: 'NEW2', price: 0.567, change: -0.32, badge: 'MODERATE' }
          ]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching losers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          
          // Fallback mock data when backend is offline
          const fallbackData = [
            { rank: 1, symbol: 'SEI-USD', current_price: 0.2244, price_change_percentage_3m: -12.89 },
            { rank: 2, symbol: 'AVAX-USD', current_price: 24.56, price_change_percentage_3m: -8.45 },
            { rank: 3, symbol: 'DOT-USD', current_price: 4.78, price_change_percentage_3m: -6.23 },
            { rank: 4, symbol: 'ATOM-USD', current_price: 7.89, price_change_percentage_3m: -9.34 },
            { rank: 5, symbol: 'NEAR-USD', current_price: 3.45, price_change_percentage_3m: -5.67 },
            { rank: 6, symbol: 'NEW1', current_price: 1.234, price_change_percentage_3m: -0.45 },
            { rank: 7, symbol: 'NEW2', current_price: 0.567, price_change_percentage_3m: -0.32 }
          ].map(item => ({
            ...item,
            price: item.current_price,
            change: item.price_change_percentage_3m,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3m))
          }));
          setData(fallbackData);
        }
      }
    };
    fetchLosersData();
    const interval = setInterval(fetchLosersData, 30000);
    return () => { isMounted = false; clearInterval(interval); };
  }, [refreshTrigger]);

  useEffect(() => {
    async function fetchWatchlist() {
      const data = await getWatchlist();
      setWatchlist(data);
    }
    fetchWatchlist();
  }, [refreshTrigger]);

  const handleToggleWatchlist = async (symbol) => {
    if (!watchlist.includes(symbol)) {
      setPopStar(symbol);
      setAddedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setAddedBadge(null), 1200);
      console.log('Adding to watchlist:', symbol);
      const updated = await addToWatchlist(symbol);
      console.log('Added to watchlist, new list:', updated);
      setWatchlist(updated);
    } else {
      console.log('Symbol already in watchlist, not adding:', symbol);
    }
  };

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-pink font-mono">Loading losers...</div>
      </div>
    );
  }

  if (error && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">Backend offline - using demo data</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No losers data available</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-1 w-full h-full min-h-[420px] max-w-2xl mx-auto px-1 sm:px-3 md:px-0 align-stretch">
      {data.map((item, idx) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        const isInWatchlist = watchlist.includes(item.symbol);
        const isPopping = popStar === item.symbol;
        const showAdded = addedBadge === item.symbol;
        return (
          <React.Fragment key={item.symbol}>
            <div className="relative group">
              <a
                href={coinbaseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block group flex-1"
              >
                <div
                  className={
                    `flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group-hover:text-pink group-hover:text-shadow-pink ` +
                    `group-hover:scale-[1.035] group-hover:z-10 ` +
                    `will-change-transform`
                  }
                  style={{ boxShadow: '0 2px 16px 0 rgba(255,0,128,0.08)' }}
                >
                  {/* Diamond inner glow effect (always visible, expands on hover) */}
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className={
                        `block rounded-xl transition-all duration-500 ` +
                        `opacity-0 group-hover:opacity-90 ` +
                        `group-hover:w-[170%] group-hover:h-[170%] w-[140%] h-[140%]`
                      }
                      style={{
                        background:
                          'radial-gradient(circle at 50% 50%, rgba(255,0,128,0.16) 0%, rgba(255,0,128,0.08) 60%, transparent 100%)',
                        top: '-20%',
                        left: '-20%',
                        position: 'absolute',
                      }}
                    />
                  </span>
                  <div className="flex items-center gap-4">
                    {/* Rank Badge */}
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-pink/40 text-pink font-bold text-sm hover:text-pink hover:text-shadow-light-pink">
                      {item.rank}
                    </div>
                    {/* Symbol */}
                    <div className="flex-1 flex items-center gap-3 ml-4">
                      <span className="font-bold text-white text-lg tracking-wide hover:text-pink hover:text-shadow-light-pink">
                        {item.symbol}
                      </span>
                      {showAdded && (
                        <span className="ml-2 px-2 py-0.5 rounded bg-pink/80 text-white text-xs font-bold animate-fade-in-out shadow-pink-400/30" style={{animation:'fadeInOut 1.2s'}}>Added!</span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-row flex-wrap items-center gap-2 sm:gap-4 ml-0 sm:ml-4 w-full sm:w-auto">
                    {/* Price Column (current and previous price, teal, right-aligned) */}
                    <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px] ml-2 sm:ml-4">
                      <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text">
                        {typeof item.price === 'number' && Number.isFinite(item.price)
                          ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}`
                          : 'N/A'}
                      </span>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 select-text">
                        {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                          ? (() => {
                               const prevPrice = item.price / (1 + item.change / 100);
                               return `$${prevPrice < 1 && prevPrice > 0 ? prevPrice.toFixed(4) : prevPrice.toFixed(2)}`;
                             })()
                          : '--'}
                      </span>
                    </div>
                    {/* Change Percentage and Dot */}
                    <div className="flex flex-col items-end min-w-[56px] sm:min-w-[60px]">
                      <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${item.change > 0 ? 'text-blue' : 'text-pink'}`}> 
                        <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">
                        3-Min
                      </span>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${getDotStyle(item.badge)}`}></div>
                    <span className="relative">
                      <span
                        onClick={e => { e.preventDefault(); handleToggleWatchlist(item.symbol); }}
                        style={{ display: 'inline-block', minWidth: '24px', minHeight: '24px' }}
                        tabIndex={0}
                        role="button"
                        aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                        aria-pressed={isInWatchlist}
                        onKeyDown={e => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleToggleWatchlist(item.symbol);
                          }
                        }}
                      >
                        <StarIcon
                          filled={isInWatchlist}
                          className={
                            (isInWatchlist ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80') +
                            (isPopping ? ' animate-star-pop' : '')
                          }
                          style={{ minWidth: '20px', minHeight: '20px', maxWidth: '28px', maxHeight: '28px', cursor: 'pointer', transition: 'transform 0.2s' }}
                          aria-hidden="true"
                        />
                      </span>
                    </span>
                  </div>
                </div>
              </a>
            </div>
            {/* Purple divider, not full width, only between cards */}
            {idx < data.length - 1 && (
              <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(129,9,150,0.18) 0%,rgba(129,9,150,0.38) 50%,rgba(129,9,150,0.18) 100%)',borderRadius:'2px'}}></div>
            )}
          </React.Fragment>
        );
      })}
    </div>
// Inject animation styles for pop/fade effects


  );
}

export default LosersTable;
