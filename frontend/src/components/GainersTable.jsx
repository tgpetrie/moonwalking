import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import StarIcon from './StarIcon';

const GainersTable = ({ refreshTrigger }) => {
  // Inject animation styles for pop/fade effects
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('gainers-table-animations')) {
      const style = document.createElement('style');
      style.id = 'gainers-table-animations';
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
  @keyframes flashUp { 0% { background-color: rgba(16,185,129,0.35);} 100% { background-color: transparent;} }
  @keyframes flashDown { 0% { background-color: rgba(244,63,94,0.35);} 100% { background-color: transparent;} }
  .flash-up { animation: flashUp 0.9s ease-out; }
  .flash-down { animation: flashDown 0.9s ease-out; }
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [data, setData] = useState([]);
  const [flashMap, setFlashMap] = useState({}); // symbol-> 'up' | 'down'
  const [priceHistory, setPriceHistory] = useState({}); // {SYM: number[]}
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [addedBadge, setAddedBadge] = useState(null); // symbol for 'Added!' badge


  useEffect(() => {
    let isMounted = true;
    const fetchGainersData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.gainersTable);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const next = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_3min || 0,
            trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
            trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
            trendScore: item.trend_score ?? item.trendScore ?? 0
          }));
          // Update rolling history for sparklines (cap 20 points)
          setPriceHistory(prev => {
            const out = { ...prev };
            next.forEach(row => {
              const arr = (out[row.symbol] || []).slice(-19);
              if (typeof row.price === 'number' && Number.isFinite(row.price)) {
                arr.push(row.price);
                out[row.symbol] = arr;
              }
            });
            return out;
          });
          if (isMounted) {
            setData(prev => {
              const flashes = {};
              next.slice(0,7).forEach(n => {
                const old = prev.find(p => p.symbol === n.symbol);
                if (old && old.price !== n.price) {
                  flashes[n.symbol] = n.price > old.price ? 'up' : 'down';
                }
              });
              setFlashMap(flashes);
              if (Object.keys(flashes).length) {
                setTimeout(() => setFlashMap({}), 900);
              }
              return next.slice(0,7);
            });
          }
        } else if (isMounted) {
          setData([]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching gainers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          setData([]);
        }
      }
    };
    fetchGainersData();
    const interval = setInterval(fetchGainersData, 30000);
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
        <div className="animate-pulse text-blue font-mono">Loading gainers...</div>
      </div>
    );
  }

  if (error && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No data (backend error)</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No gainers data available</div>
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
        const getArrowStyle = (score, dir) => {
          const s = Math.max(0, Math.min(3, Number(score) || 0));
          let fontSize = '0.8em';
          if (s >= 1.5) fontSize = '1.25em'; else if (s >= 0.5) fontSize = '1.05em';
          let color;
          if (dir === 'up') {
            color = s >= 1.5 ? '#10B981' : s >= 0.5 ? '#34D399' : '#9AE6B4';
          } else {
            color = s >= 1.5 ? '#EF4444' : s >= 0.5 ? '#F87171' : '#FEB2B2';
          }
          return { fontSize, color };
        };
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
                    `relative overflow-hidden p-4 rounded-xl transition-all duration-300 cursor-pointer group-hover:scale-[1.03] group-hover:z-10 will-change-transform grid items-center gap-4 grid-cols-[40px,1fr,110px,80px,32px] ` +
                    `group-hover:text-amber-500 ` +
                    (flashMap[item.symbol] ? (flashMap[item.symbol] === 'up' ? 'flash-up' : 'flash-down') : '')
                  }
                  style={{ boxShadow: '0 2px 16px 0 rgba(129,9,150,0.10)' }}
                >
                  {/* Glow */}
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block rounded-2xl opacity-0 group-hover:opacity-100 transition-all duration-150 w-[120%] h-[120%] group-hover:w-[160%] group-hover:h-[160%]"
                      style={{
                        background: 'radial-gradient(circle at 50% 50%, rgba(129,9,150,0.28) 0%, rgba(129,9,150,0.18) 35%, rgba(129,9,150,0.10) 60%, rgba(129,9,150,0.04) 80%, transparent 100%)',
                        top: '-30%', left: '-30%', position: 'absolute', filter: 'blur(1.5px)'
                      }}
                    />
                  </span>
                  {/* Rank */}
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue/40 text-blue font-bold text-sm">
                    {item.rank}
                  </div>
                  {/* Symbol + Added */}
                  <div className="flex items-center gap-3 ml-2 min-w-0">
                    <span className="font-bold text-white text-lg tracking-wide truncate hover:text-cyan-400 hover:text-shadow-cyan-400">{item.symbol}</span>
                    {showAdded && (
                      <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30" style={{animation:'fadeInOut 1.2s'}}>Added!</span>
                    )}
                  </div>
                  {/* Price */}
                  <div className="flex flex-col items-end min-w-[110px]">
                    <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text">
                      {typeof item.price === 'number' && Number.isFinite(item.price)
                        ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}`
                        : 'N/A'}
                    </span>
                    <span className="text-xs sm:text-sm font-light text-gray-400 select-text">
                      {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                        ? (() => { const prevPrice = item.price / (1 + item.change / 100); return `$${prevPrice < 1 && prevPrice > 0 ? prevPrice.toFixed(4) : prevPrice.toFixed(2)}`; })()
                        : '--'}
                    </span>
                  </div>
                  {/* Change */}
                  <div className="flex flex-col items-end min-w-[80px]">
                    <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${item.change > 0 ? 'text-blue' : 'text-pink'}`}> 
                      <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      {item.trendDirection && item.trendDirection !== 'flat' && (
                        <span
                          className="font-semibold"
                          style={getArrowStyle(item.trendScore, item.trendDirection)}
                          title={`trend: ${item.trendDirection}${item.trendStreak ? ` x${item.trendStreak}` : ''} • score ${Number(item.trendScore||0).toFixed(2)}`}
                          aria-label={`trend ${item.trendDirection}`}
                        >
                          {item.trendDirection === 'up' ? '↑' : '↓'}
                        </span>
                      )}
                      {typeof item.trendStreak === 'number' && item.trendStreak >= 2 && (
                        <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle">x{item.trendStreak}</span>
                      )}
                    </div>
                    <span className="text-xs sm:text-sm font-light text-gray-400">3-Min</span>
                  </div>
                  {/* Star */}
                  <button
                    onClick={e => { e.preventDefault(); handleToggleWatchlist(item.symbol); }}
                    tabIndex={0}
                    aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                    aria-pressed={isInWatchlist}
                    className="bg-transparent border-none p-0 m-0 cursor-pointer w-8 h-8 flex items-center justify-center"
                  >
                    <StarIcon
                      filled={isInWatchlist}
                      className={(isInWatchlist ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80') + (isPopping ? ' animate-star-pop' : '')}
                      style={{ minWidth: '20px', minHeight: '20px', transition: 'transform 0.2s' }}
                      aria-hidden="true"
                    />
                  </button>
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
  );
};

export default GainersTable;