import React, { useContext, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { API_ENDPOINTS, swrFetcher, getWatchlist, addToWatchlist, fetchData } from '../api.js';
import { formatPercentage, truncateSymbol } from '../utils/formatters.js';
import { WebSocketContext } from '../context/websocketcontext.jsx';
import { useWebSocket } from '../context/websocketcontext.jsx';
import StarIcon from './StarIcon';
import PeakBadge from './PeakBadge.jsx';
import PropTypes from 'prop-types';

/**
 * GainersTable1Min — REBUILD (alignment-stable)
 * - No arrows in main row
 * - Purple inner-glow hover (#C026D3)
 * - Fixed column widths across ALL tables
 * - Meta strip below numbers hosts PeakBadge (keeps top row perfectly aligned)
 */
const GainersTable1Min = ({ refreshTrigger, onWatchlistChange, topWatchlist, sliceStart, sliceEnd, fixedRows, hideShowMore }) => {
  const { latestData } = useContext(WebSocketContext);
  const { isConnected, isPolling, oneMinThrottleMs, getPrice } = useWebSocket();
  const lastRenderRef = useRef(0);

  // inject minimal animations only once
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('gainers-1min-table-animations')) {
      const style = document.createElement('style');
      style.id = 'gainers-1min-table-animations';
      style.innerHTML = `
        @keyframes starPop { 0%{transform:scale(1)} 40%{transform:scale(1.35)} 70%{transform:scale(.92)} 100%{transform:scale(1)} }
        .animate-star-pop { animation: starPop .35s cubic-bezier(.4,2,.6,1) both; }
        @keyframes fadeInOut { 0%{opacity:0; transform:translateY(-8px) scale(.9)} 10%{opacity:1; transform:translateY(0) scale(1.05)} 80%{opacity:1} 100%{opacity:0; transform:translateY(-8px) scale(.9)} }
        .animate-fade-in-out { animation: fadeInOut 1.2s cubic-bezier(.4,2,.6,1) both; }
      `;
      document.head.appendChild(style);
    }
  }, []);

  // Note: API_ENDPOINTS key is `gainersTable1Min` (not `gainers1Min`) — use correct key so REST fallback works.
  const { data: initialResponse, error: initialError } = useSWR(API_ENDPOINTS.gainersTable1Min, swrFetcher, {
    refreshInterval: 60000,
    revalidateOnFocus: false
  });
  const initialData = initialResponse?.data ?? [];
  const wsData = latestData?.prices ?? {};

  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [popStar, setPopStar] = useState(null);
  const [addedBadge, setAddedBadge] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // throttle WebSocket updates for stability
  useEffect(() => {
    const now = Date.now();
    const throttleMs = typeof oneMinThrottleMs === 'number' ? oneMinThrottleMs : 7000;
    if (now - (lastRenderRef.current || 0) < throttleMs) return;
    lastRenderRef.current = now;

    // For 1-minute gainers, prefer the compact `latestData.prices` map emitted by backend (lightweight)
    // Fallbacks: structured payload crypto_meta.gainers or legacy latestData.crypto array
    const pricesMap = latestData?.prices ?? {};
    const wsGainersFromPrices = Object.keys(pricesMap).length > 0
      ? Object.keys(pricesMap).map((sym, idx) => ({
          rank: idx + 1,
          symbol: sym.replace('-USD', ''),
          current_price: pricesMap[sym].price ?? pricesMap[sym].current ?? 0,
          price_change_percentage_1min: pricesMap[sym].change ?? 0,
        }))
      : [];

    const cryptoArr = wsGainersFromPrices.length > 0
      ? wsGainersFromPrices
      : (Array.isArray(latestData?.crypto_meta?.gainers)
          ? latestData.crypto_meta.gainers
          : (Array.isArray(latestData?.crypto) ? latestData.crypto : []));

    if (cryptoArr && Array.isArray(cryptoArr)) {
      const mapped = cryptoArr.slice(0, 20).map((item, index) => ({
        rank: item.rank || index + 1,
        symbol: item.symbol?.replace('-USD', '') || 'N/A',
        price: item.current_price ?? item.price ?? 0,
        change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
        peakCount: typeof item.peak_count === 'number' ? item.peak_count : (typeof item.trend_streak === 'number' ? item.trend_streak : 0),
      }));

      // Keep only positive 1-min gainers and sort descending (match GainersTable behavior)
      const positive = mapped
        .filter((it) => typeof it.change === 'number' && it.change > 0)
        .sort((a, b) => b.change - a.change);

      setData(positive);
      setLoading(false);
      setError(null);
    }
  }, [latestData.prices, oneMinThrottleMs]);

  // Fallback REST polling when WS not active
  useEffect(() => {
    let isMounted = true;
    const fetchGainersData = async () => {
      // If compact prices map is present from WS, skip REST polling
      if (latestData.prices && Object.keys(latestData.prices).length > 0) return;
      try {
        const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (response?.data?.length) {
          const mapped = response.data.slice(0, 20).map((item, index) => ({
            rank: item.rank || index + 1,
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price ?? item.price ?? 0,
            change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
            peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
          }));
          if (isMounted) setData(mapped);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        if (isMounted) { setLoading(false); setError(err.message); }
      }
    };

    if (!isConnected && !isPolling) {
      fetchGainersData();
      const interval = setInterval(fetchGainersData, 30000);
      return () => { isMounted = false; clearInterval(interval); };
    } else {
      if (data.length === 0) fetchGainersData();
    }
    return () => { isMounted = false; };
  }, [refreshTrigger, isConnected, isPolling, latestData.prices]);

  useEffect(() => {
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
      onWatchlistChange && onWatchlistChange(topWatchlist);
    } else {
      (async () => {
        const w = await getWatchlist();
        setWatchlist(w);
        onWatchlistChange && onWatchlistChange(w);
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger, topWatchlist]);

  const handleToggleWatchlist = async (symbol) => {
    const exists = watchlist.some((it) => (typeof it === 'string' ? it === symbol : it.symbol === symbol));
    if (!exists) {
      setPopStar(symbol);
      setAddedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setAddedBadge(null), 1200);
      const coin = data.find((c) => c.symbol === symbol);
      const currentPrice = coin ? coin.price : null;
      const updated = await addToWatchlist(symbol, currentPrice);
      setWatchlist(updated);
      onWatchlistChange && onWatchlistChange(updated);
    }
  };

  // If WS prices map exists, prefer it; convert map -> array
  let wsArray = [];
  if (latestData?.prices && Object.keys(latestData.prices).length > 0) {
    wsArray = Object.keys(latestData.prices).map((sym, idx) => ({
      rank: idx + 1,
      symbol: sym.replace('-USD', ''),
      price: latestData.prices[sym].price ?? latestData.prices[sym].current ?? 0,
      change: latestData.prices[sym].change ?? 0,
      peakCount: latestData.prices[sym].peak_count ?? 0
    }))
    // keep only positive 1-min gainers and sort descending
    .filter(it => typeof it.change === 'number' && it.change > 0)
    .sort((a, b) => b.change - a.change);
  }

  const sourceData = wsArray.length > 0 ? wsArray : (Array.isArray(data) && data.length > 0 ? data : initialData);
  const visibleData = typeof sliceStart === 'number' || typeof sliceEnd === 'number'
    ? sourceData.slice(sliceStart ?? 0, sliceEnd ?? sourceData.length)
    : sourceData;

  const rowsToShow = typeof fixedRows === 'number' && fixedRows > 0
    ? Math.min(fixedRows, visibleData.length)
    : Math.min(4, visibleData.length);

  // Always render table; SWR handles loading state
  const displayData = sourceData;

  if (!Array.isArray(visibleData) || visibleData.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300">
      {visibleData.slice(0, rowsToShow).map((item) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        const isInWatchlist = watchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol));
        const isPopping = popStar === item.symbol;
        const showAdded = addedBadge === item.symbol;
        const PCT = item.change;
        const INTERVAL_LABEL = '1-min';
        const inWatch = isInWatchlist;
        const toggleWatch = (sym) => handleToggleWatchlist(sym);

        return (
          <div key={item.symbol} className="px-2 py-1 mb-1">
            <a href={coinbaseUrl} target="_blank" rel="noopener noreferrer" className="block group">
              <div className="relative overflow-hidden rounded-xl p-4 box-border hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform">

                {/* PURPLE INNER GLOW (#C026D3) */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  {/* contained inner glow: use inset with transform scale on hover to avoid overflowing neighboring columns */}
                  <span
                    className="block rounded-xl transition-transform duration-500 opacity-0 group-hover:opacity-90 transform-gpu scale-100 group-hover:scale-105 w-full h-full"
                    style={{
                      background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                      position: 'absolute', inset: 0
                    }}
                  />
                </span>

                {/* MAIN ROW — GRID: [minmax(0,1fr) | 152px | 108px | 28px] */}
                <div className="relative z-10 w-full grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">

                  {/* LEFT flexible: rank + symbol */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0">{item.rank}</div>
                    <div className="min-w-0">
                      <div className="font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(item.symbol, 6)}</div>
                    </div>
                  </div>

                  {/* Col2: Price (stack current + previous) */}
                  <div className="w-[152px] pr-6 text-right">
                    <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {Number.isFinite(item.price) ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}` : 'N/A'}
                    </div>
                    <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                      {typeof item.price === 'number' && typeof PCT === 'number' && PCT !== 0
                        ? (() => { const prev = item.price / (1 + PCT / 100); return `$${prev < 1 && prev > 0 ? prev.toFixed(4) : prev.toFixed(2)}`; })()
                        : '--'}
                    </div>
                  </div>

                  {/* Col3: % (stack % → Peak → interval) */}
                  <div className="w-[108px] pr-1.5 text-right align-top">
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap ${PCT > 0 ? 'text-[#C026D3]' : 'text-pink'}`}> 
                      {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercentage(PCT) : 'N/A'}
                    </div>
                    {typeof item.peakCount === 'number' && item.peakCount > 0 && (
                      <div className="text-xs text-gray-400 leading-tight">Peak x{item.peakCount}</div>
                    )}
                    <div className="text-xs text-gray-400 leading-tight">{INTERVAL_LABEL}</div>
                  </div>

                  {/* Col4: Star (tight) */}
                  <div className="w-[28px] flex items-center justify-end">
                    <button
                      onClick={(e)=>{e.preventDefault(); toggleWatch(item.symbol);}}
                      className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end"
                      style={{ minWidth:'24px', minHeight:'24px' }}
                      aria-label={inWatch ? 'Remove from watchlist' : 'Add to watchlist'}
                      aria-pressed={inWatch}
                    >
                      <StarIcon
                        filled={inWatch}
                        className={inWatch ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                        style={{ width:'16px', height:'16px', transition:'transform .2s' }}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </a>
          </div>
        );
      })}

      {!hideShowMore && Array.isArray(visibleData) && visibleData.length > 8 && (
        <button
          className="mt-2 mx-auto px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
          style={{ width: 'fit-content' }}
          onClick={() => setShowAll((s) => !s)}
        >
          {showAll ? 'Show Less' : `Show More (${Math.min(12, visibleData.length) - 8})`}
        </button>
      )}
    </div>
  );
};

GainersTable1Min.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array,
  sliceStart: PropTypes.number,
  sliceEnd: PropTypes.number,
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool,
};

export default GainersTable1Min;