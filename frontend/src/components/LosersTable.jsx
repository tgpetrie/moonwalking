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
  @keyframes flashUp { 0% { background-color: rgba(16,185,129,0.35);} 100% { background-color: transparent;} }
  @keyframes flashDown { 0% { background-color: rgba(244,63,94,0.35);} 100% { background-color: transparent;} }
  .flash-up { animation: flashUp 0.9s ease-out; }
  .flash-down { animation: flashDown 0.9s ease-out; }
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [data, setData] = useState([]);
  const [flashMap, setFlashMap] = useState({});
  const [priceHistory, setPriceHistory] = useState({}); // {SYM: number[]}
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
            badge: getBadgeText(Math.abs(item.price_change_percentage_3min || 0)),
            trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
            trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
            trendScore: item.trend_score ?? item.trendScore ?? 0
          }));
          // Update rolling history for sparklines (cap 20 points)
          setPriceHistory(prev => {
            const out = { ...prev };
            losersWithRanks.forEach(row => {
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
              losersWithRanks.slice(0,7).forEach(n => {
                const old = prev.find(p => p.symbol === n.symbol);
                if (old && old.price !== n.price) {
                  flashes[n.symbol] = n.price > old.price ? 'up' : 'down';
                }
              });
              setFlashMap(flashes);
              if (Object.keys(flashes).length) setTimeout(()=>setFlashMap({}), 900);
              return losersWithRanks.slice(0,7);
            });
          }
        } else if (isMounted && data.length === 0) {
          setData([]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching losers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          
          setData([]);
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
        <div className="text-muted font-mono">No data (backend error)</div>
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
                    `relative overflow-hidden p-4 rounded-xl transition-all duration-300 cursor-pointer group-hover:scale-[1.03] group-hover:z-10 will-change-transform grid items-center gap-4 grid-cols-[40px,1fr,110px,80px,16px,32px] ` +
                    `group-hover:text-pink group-hover:text-shadow-pink ` +
                    (flashMap[item.symbol] ? (flashMap[item.symbol] === 'up' ? 'flash-up' : 'flash-down') : '')
                  }
                  style={{ boxShadow: '0 2px 16px 0 rgba(255,0,128,0.08)' }}
                >
                  {/* Glow */}
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block rounded-xl opacity-0 group-hover:opacity-90 transition-all duration-500 w-[140%] h-[140%] group-hover:w-[170%] group-hover:h-[170%]"
                      style={{
                        background: 'radial-gradient(circle at 50% 50%, rgba(255,0,128,0.16) 0%, rgba(255,0,128,0.08) 60%, transparent 100%)',
                        top: '-20%', left: '-20%', position: 'absolute'
                      }}
                    />
                  </span>
                  {/* Rank */}
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-pink/40 text-pink font-bold text-sm">
                    {item.rank}
                  </div>
                  {/* Symbol + Added */}
                  <div className="flex items-center gap-3 ml-2 min-w-0">
                    <span className="font-bold text-white text-lg tracking-wide truncate hover:text-pink hover:text-shadow-light-pink">{item.symbol}</span>
                    {showAdded && (
                      <span className="px-2 py-0.5 rounded bg-pink/80 text-white text-xs font-bold animate-fade-in-out shadow-pink-400/30" style={{animation:'fadeInOut 1.2s'}}>Added!</span>
                    )}
                  </div>
                  {/* Price + sparkline */}
                  <div className="flex flex-col items-end min-w-[110px]">
                    {/* tiny sparkline above price on sm+ */}
                    <div className="hidden sm:block mb-1">
            <svg width="80" height="20" viewBox="0 0 80 20" className="opacity-70">
                        {(() => {
                          const ys = (priceHistory[item.symbol] || []).slice(-20);
                          if (ys.length < 2) return null;
                          const min = Math.min(...ys);
                          const max = Math.max(...ys);
                          const range = max - min || 1;
                          const step = 80 / (ys.length - 1);
                          const d = ys.map((p,i)=>`${i===0?'M':'L'} ${i*step} ${20 - ((p - min)/range)*20}`).join(' ');
              const positive = (item.change || 0) >= 0;
              return <path d={d} fill="none" stroke={positive ? '#7FFFD4' : '#FF7F98'} strokeWidth="2" />;
                        })()}
                      </svg>
                    </div>
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
                  {/* Dot */}
                  <div className={`w-3 h-3 rounded-full ${getDotStyle(item.badge)} justify-self-center`}></div>
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

export default LosersTable;
