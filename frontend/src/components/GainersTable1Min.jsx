import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import PropTypes from 'prop-types';

/**
 * 1‑MIN Gainers (alignment‑stable)
 * - Uses same inner grid as 3‑min tables: [minmax(0,1fr) | 152px | 108px | 28px]
 * - Fixed row height h-[96px]
 * - Supports rank‑based slicing via startRank/endRank (end exclusive)
 * - Renders placeholder rows to keep both halves equal height
 */
export default function GainersTable1Min({
  refreshTrigger,
  onWatchlistChange,
  topWatchlist,
  sliceStart,
  sliceEnd,
  startRank,
  endRank,
  fixedRows,
  hideShowMore,
}) {
  const { latestData, isConnected, isPolling, oneMinThrottleMs } = useWebSocket();
  const shouldReduce = useReducedMotion();
  const lastRenderRef = useRef(0);

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [popStar, setPopStar] = useState(null);
  const [addedBadge, setAddedBadge] = useState(null);

  // Prime watchlist
  useEffect(() => {
    (async () => {
      try {
        const w = Array.isArray(topWatchlist) ? topWatchlist : await getWatchlist();
        setWatchlist(w);
        onWatchlistChange && onWatchlistChange(w);
      } catch {
        /* ignore */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topWatchlist]);

  // Throttled WS updates for stability
  useEffect(() => {
    if (latestData.crypto && Array.isArray(latestData.crypto)) {
      const now = Date.now();
      const throttleMs = typeof oneMinThrottleMs === 'number' ? oneMinThrottleMs : 7000;
      if (now - (lastRenderRef.current || 0) < throttleMs) return;
      lastRenderRef.current = now;

      const mapped = latestData.crypto.slice(0, 20).map((item, idx) => ({
        rank: item.rank || idx + 1,
        symbol: item.symbol?.replace('-USD', '') || 'N/A',
        price: item.current_price ?? item.price ?? 0,
        change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
        peakCount: typeof item.peak_count === 'number' ? item.peak_count : (typeof item.trend_streak === 'number' ? item.trend_streak : 0),
      }));
      setData(mapped);
      setLoading(false);
      setError(null);
    }
  }, [latestData.crypto, oneMinThrottleMs]);

  // REST fallback when WS is empty/inactive
  useEffect(() => {
    let cancelled = false;
    const fetch1m = async () => {
      if (latestData.crypto && latestData.crypto.length > 0) return;
      try {
        const res = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (!cancelled && res?.data?.length) {
          const mapped = res.data.slice(0, 20).map((item, idx) => ({
            rank: item.rank || idx + 1,
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price ?? item.price ?? 0,
            change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
            peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
          }));
          setData(mapped);
        }
        if (!cancelled) setLoading(false);
      } catch (e) {
        if (!cancelled) { setLoading(false); setError(e.message); }
      }
    };

    if (!isConnected && !isPolling) {
      fetch1m();
      const id = setInterval(fetch1m, 30000);
      return () => { cancelled = true; clearInterval(id); };
    } else {
      if (data.length === 0) fetch1m();
      return () => { cancelled = true; };
    }
  }, [refreshTrigger, isConnected, isPolling, latestData.crypto]);

  const handleToggleWatchlist = async (symbol) => {
    const exists = watchlist.some((it) => (typeof it === 'string' ? it === symbol : it.symbol === symbol));
    if (exists) return;
    setPopStar(symbol);
    setAddedBadge(symbol);
    setTimeout(() => setPopStar(null), 350);
    setTimeout(() => setAddedBadge(null), 1200);
    const coin = data.find((c) => c.symbol === symbol);
    const currentPrice = coin ? coin.price : null;
    const updated = await addToWatchlist(symbol, currentPrice);
    setWatchlist(updated);
    onWatchlistChange && onWatchlistChange(updated);
  };

  // Compute slice by rank or index
  const startIdx = typeof sliceStart === 'number' ? sliceStart : (typeof startRank === 'number' ? Math.max(0, startRank - 1) : undefined);
  const endIdx   = typeof sliceEnd === 'number'   ? sliceEnd   : (typeof endRank === 'number'   ? Math.max(0, endRank)         : undefined);
  const sliced   = Array.isArray(data)
    ? (typeof startIdx === 'number' || typeof endIdx === 'number' ? data.slice(startIdx ?? 0, endIdx ?? data.length) : data)
    : [];

  // Pad to fixed rows for perfect column alignment with 3‑min tables
  const desiredRows = typeof fixedRows === 'number' && fixedRows > 0 ? fixedRows : 4;
  const rows = Array.from({ length: desiredRows }, (_, i) => sliced[i] ?? null);

  if (loading && sliced.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="animate-pulse text-[#C026D3] font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if (!loading && sliced.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300">
      {rows.map((item, idx) => {
        const isPlaceholder = !item;
        const entranceDelay = (idx % 12) * 0.035;
        const loopDelay = ((idx % 8) * 0.12);
        const breathAmt = 0.006;
        const PCT = item ? item.change : 0;
        const coinbaseUrl = item ? `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD` : '#';
        const inWatch = item ? watchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol)) : false;

        return (
          <div key={item ? item.symbol : `placeholder-${idx}`} className="px-0 py-1 mb-1">
            <a
              href={coinbaseUrl}
              onClick={(e)=>{ if(isPlaceholder){ e.preventDefault(); } }}
              target={isPlaceholder ? undefined : "_blank"}
              rel={isPlaceholder ? undefined : "noopener noreferrer"}
              className="block group"
            >
              <motion.div
                className="relative overflow-hidden rounded-xl p-4 h-[96px] hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform will-change-transform"
                initial={shouldReduce ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: 'easeOut', delay: entranceDelay }}
                whileHover={shouldReduce || isPlaceholder ? {} : { scale: 1.012 }}
                whileTap={shouldReduce || isPlaceholder ? {} : { scale: 0.985 }}
              >
                {!shouldReduce && (
                  <motion.div
                    aria-hidden
                    className="absolute inset-0 pointer-events-none"
                    animate={{ scale: [1, 1 + breathAmt, 1] }}
                    transition={{ duration: 3.6, repeat: Infinity, ease: 'easeInOut', delay: loopDelay }}
                  />
                )}

                {/* Purple glow */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span
                    className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                    style={{
                      background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                      top: '-15%',
                      left: '-15%',
                      position: 'absolute',
                    }}
                  />
                </span>

                {/* MAIN ROW — fixed grid */}
                <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                  {/* Col1: rank + symbol */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className={"flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0 " + (isPlaceholder ? 'opacity-0' : '')}>
                      {item ? item.rank : 0}
                    </div>
                    <div className={"min-w-0 flex items-center gap-3 " + (isPlaceholder ? 'opacity-0' : '')}>
                      <span className="font-bold text-white text-lg tracking-wide truncate">{item ? truncateSymbol(item.symbol, 6) : '—'}</span>
                      {addedBadge === (item && item.symbol) && (
                        <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Added!</span>
                      )}
                    </div>
                  </div>

                  {/* Col2: price/current + previous */}
                  <div className={"w-[152px] pr-6 text-right " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                    </div>
                    <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                      {item && typeof item.price === 'number' && typeof PCT === 'number' && PCT !== 0
                        ? (() => { const prev = item.price / (1 + PCT / 100); return formatPrice(prev); })()
                        : '--'}
                    </div>
                  </div>

                  {/* Col3: % + Peak + interval */}
                  <div className={"w-[108px] pr-1.5 text-right align-top " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${PCT > 0 ? 'text-[#C026D3]' : 'text-pink'}`}>
                      {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercentage(PCT) : '0.00%'}
                    </div>
                    <div className="text-xs text-gray-400 leading-tight">
                      {item && typeof item.peakCount === 'number' && item.peakCount > 0
                        ? `Peak x${item.peakCount}`
                        : <span className="opacity-0 select-none">Peak x0</span>}
                    </div>
                    <div className="text-xs text-gray-400 leading-tight">1-min</div>
                  </div>

                  {/* Col4: star */}
                  <div className="w-[28px] text-right">
                    <button
                      onClick={(e)=>{ if(isPlaceholder){ e.preventDefault(); return; } e.preventDefault(); handleToggleWatchlist(item.symbol); }}
                      disabled={isPlaceholder}
                      className={"bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end " + (isPlaceholder ? 'opacity-0' : (popStar === (item && item.symbol) ? ' animate-star-pop' : ''))}
                      style={{ minWidth:'24px', minHeight:'24px' }}
                      aria-label={inWatch ? 'Remove from watchlist' : 'Add to watchlist'}
                      aria-pressed={inWatch}
                    >
                      <StarIcon
                        filled={inWatch}
                        className={inWatch ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                        style={{ width:'16px', height:'16px', transition:'transform .2s' }}
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </motion.div>
            </a>
          </div>
        );
      })}

      {/* No per-component Show More button when hideShowMore is true */}
      {!hideShowMore && sliced.length > rows.length && (
        <div className="w-full flex justify-center mt-2 mb-1">
          <button className="px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition">
            Show More
          </button>
        </div>
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
  startRank: PropTypes.number,
  endRank: PropTypes.number,
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool,
};