import React, { useContext, useEffect, useState } from 'react';
import useSWR from 'swr';
import { API_ENDPOINTS, swrFetcher, getWatchlist, addToWatchlist } from '../api.js';
import { WebSocketContext } from '../context/websocketcontext.jsx';
import { formatPercentage, truncateSymbol } from '../utils/formatters.js';
import StarIcon from './StarIcon';

const LosersTable = ({ refreshTrigger }) => {
  // Inject animation styles for pop/fade effects (watchlist add feedback)
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
  // Fetch initial losers data via SWR
  const { data: initialResponse, error: initialError } = useSWR(
    API_ENDPOINTS.losersTable,
    swrFetcher,
    { refreshInterval: 60000, revalidateOnFocus: false }
  );
  const initialData = initialResponse?.data ?? [];
  // Use WebSocketContext for real-time updates if available
  const { latestData } = useContext(WebSocketContext) || {};
  // Prefer structured losers payload when backend sends { gainers, losers, banner }
  const wsLosers = Array.isArray(latestData?.crypto_meta?.losers)
    ? latestData.crypto_meta.losers
    : [];
  const mergedData = wsLosers.length > 0 ? wsLosers : initialData;
  // loading when there's no initial REST response and no WS losers data yet
  const loading = !initialResponse && mergedData.length === 0;
  const error = initialError;
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

  // Data for display
  const displayData = mergedData.slice(0, 7).map((item, index) => ({
    // visible rank normalized to 1..7 for the displayed slice
    rank: index + 1,
    // preserve backend global rank separately
    backendRank: item.rank ?? null,
    symbol: item.symbol?.replace('-USD', '') || 'N/A',
    price: item.current_price ?? item.price ?? 0,
    change: item.price_change_percentage_3min ?? item.change ?? 0,
    badge: getBadgeText(Math.abs(item.price_change_percentage_3min ?? item.change ?? 0))
  }));

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

  if (loading && displayData.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-pink font-mono">Loading losers...</div>
      </div>
    );
  }

  if (error && displayData.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No data (backend error)</div>
      </div>
    );
  }

  if (!loading && displayData.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No losers data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0">
      {displayData.map((r) => {
        const isInWatchlist = watchlist.includes(r.symbol);
        const isPopping = popStar === r.symbol;
        const showAdded = addedBadge === r.symbol;
        const prev = (typeof r.price === 'number' && typeof r.change === 'number' && r.change !== 0)
          ? (r.price / (1 + r.change / 100))
          : null;
        const url = `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD`;

        return (
          <div key={r.symbol} className="px-2 py-1 mb-1">
            <a href={url} target="_blank" rel="noopener noreferrer" className="block group">
              <div className="relative overflow-hidden rounded-xl p-4 box-border hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform">

                {/* Glow (orange-gold to match gainers) - contained inset to avoid overflow */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span
                    className="block rounded-xl transition-transform duration-500 opacity-0 group-hover:opacity-90 transform-gpu scale-100 group-hover:scale-105 w-full h-full"
                    style={{
                      background: 'radial-gradient(circle at 50% 50%, rgba(255,96,132,0.20) 0%, rgba(255,96,132,0.12) 45%, rgba(255,180,197,0.08) 70%, transparent 100%)',
                      position: 'absolute', inset: 0
                    }}
                  />
                </span>

                {/* MAIN ROW — GRID: [minmax(0,1fr) | 152px | 108px | 28px] */}
                <div className="relative z-10 w-full grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">

                  {/* LEFT flexible: rank + symbol */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-pink/40 text-pink font-bold text-sm shrink-0">{r.rank}</div>
                    <div className="min-w-0">
                      <div className="font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(r.symbol, 6)}</div>
                    </div>
                  </div>

                  {/* Col2: Price (stack current + previous) */}
                  <div className="w-[152px] pr-6 text-right">
                    <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {Number.isFinite(r.price) ? `$${r.price < 1 && r.price > 0 ? r.price.toFixed(4) : r.price.toFixed(2)}` : 'N/A'}
                    </div>
                    <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                      {prev !== null
                        ? `$${prev < 1 && prev > 0 ? prev.toFixed(4) : prev.toFixed(2)}`
                        : '--'}
                    </div>
                  </div>

                  {/* Col3: % (stack % → Peak → interval) */}
                  <div className="w-[108px] pr-1.5 text-right align-top">
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap ${r.change > 0 ? 'text-[#C026D3]' : 'text-pink'}`}> 
                      {r.change > 0 && '+'}{typeof r.change === 'number' ? formatPercentage(r.change) : 'N/A'}
                    </div>
                    {typeof r.peakCount === 'number' && r.peakCount > 0 && (
                      <div className="text-xs text-gray-400 leading-tight">Peak x{r.peakCount}</div>
                    )}
                    <div className="text-xs text-gray-400 leading-tight">3-min</div>
                  </div>

                  {/* Col4: Star (tight) */}
                  <div className="w-[28px] flex items-center justify-end">
                    <button
                      onClick={(e)=>{e.preventDefault(); handleToggleWatchlist(r.symbol, r.price);}}
                      className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end"
                      style={{ minWidth:'24px', minHeight:'24px' }}
                      aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                    >
                      <StarIcon
                        filled={isInWatchlist}
                        className={(isInWatchlist ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80') + (isPopping ? ' animate-star-pop' : '')}
                        style={{ width:'16px', height:'16px', transition:'transform .2s' }}
                      />
                    </button>
                  </div>
                </div>

                {/* subtle, soft underline — thin and edge-faded so it's gentle */}
                <span
                  aria-hidden
                  className="pointer-events-none"
                  style={{
                    zIndex: 9,
                    left: '1rem',
                    right: '1rem',
                    bottom: '0.5rem',
                    height: '2px',
                    position: 'absolute',
                    borderRadius: '999px',
                    background: (r.change > 0)
                      ? 'linear-gradient(90deg, rgba(192,38,211,0.18) 0%, rgba(192,38,211,0.12) 30%, rgba(192,38,211,0.06) 60%, rgba(192,38,211,0.02) 80%, transparent 100%)'
                      : 'linear-gradient(90deg, rgba(236,72,153,0.14) 0%, rgba(236,72,153,0.10) 30%, rgba(236,72,153,0.05) 60%, rgba(236,72,153,0.02) 80%, transparent 100%)',
                    opacity: 0.85,
                    transition: 'opacity .25s ease'
                  }}
                />

                {/* meta strip removed; info moved into main cells */}
              </div>
            </a>
          </div>
        );
      })}
    </div>
  );
};

export default LosersTable;
