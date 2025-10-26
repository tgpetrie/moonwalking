import React, { useEffect, useRef, useState, useMemo } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import { updateStreaks } from '../logic/streaks';
import PropTypes from 'prop-types';
import { isMobileDevice, getMobileOptimizedConfig } from '../utils/mobileDetection.js';

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
  rows: externalRows,
}) {
  let wsContextData;
  try {
    wsContextData = useWebSocket();
  } catch (error) {
    console.error('[GainersTable1Min] WebSocket context error:', error);
    wsContextData = { latestData: { crypto: [] }, isConnected: false, isPolling: false, oneMinThrottleMs: 15000, send: () => {} };
  }
  
  const { latestData, isConnected, isPolling, oneMinThrottleMs, send, gainersTop20, debugEnabled, vLog } = wsContextData;
  
  const shouldReduce = useReducedMotion();
  const lastRenderRef = useRef(0);
  const prevDataRef = useRef([]); // retained for potential local diffing, though context handles merge
  
  // Mobile optimizations
  const isMobile = isMobileDevice();
  const mobileConfig = getMobileOptimizedConfig();

  const [data, setData] = useState([]); // local displayed dataset (sliced / throttled)
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [popStar, setPopStar] = useState(null);
  const [actionBadge, setActionBadge] = useState(null); // {symbol,text}

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
     
  }, [topWatchlist]);

  // Throttled WS updates (skip when external rows provided)
  useEffect(() => {
    // Only override with external rows when they contain data.
    if (Array.isArray(externalRows) && externalRows.length > 0) { setData(externalRows); setLoading(false); return; }
    if (Array.isArray(gainersTop20) && gainersTop20.length) {
      const now = Date.now();
      const throttleMs = typeof oneMinThrottleMs === 'number' ? oneMinThrottleMs : (isMobile ? mobileConfig.throttleMs : 15000);
      const since = now - (lastRenderRef.current || 0);
      if (debugEnabled) {
        vLog(`[GainersTable1Min] Throttle check: ${since}ms elapsed (limit ${throttleMs}ms), incoming top20 length: ${gainersTop20.length}`);
      }
      if (since < throttleMs) {
        if (debugEnabled) {
          vLog('[GainersTable1Min] THROTTLED - skip render update');
        }
        return;
      }
      lastRenderRef.current = now;
      // Data already normalized & ranked in context
      setData(gainersTop20);
      setLoading(false);
      setError(null);
    }
  }, [gainersTop20, externalRows, oneMinThrottleMs, debugEnabled, vLog, isMobile, mobileConfig.throttleMs]);

  // Debug: Log whenever latestData.crypto changes
  useEffect(() => {
    if (debugEnabled) {
      vLog('[GainersTable1Min] latestData.crypto changed:', latestData?.crypto?.length || 0, 'items');
    }
  }, [latestData.crypto, debugEnabled, vLog]);

  // REST fallback when WS is empty/inactive (skip with external rows)
  useEffect(() => {
    if (Array.isArray(externalRows)) {
      return;
    }
    let cancelled = false;
    const fetch1m = async () => {
      if (latestData.crypto && latestData.crypto.length > 0) {
        return;
      }
      try {
        const res = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (!cancelled && res?.data?.length) {
          const mapped = res.data.slice(0, 20).map((item, idx) => {
            // Normalize percent units and preserve initial price when available
            const rawChange = item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0;
            const abs = Math.abs(Number(rawChange) || 0);
            const needsScale = abs > 0 && abs < 0.02; // treat 0..1 as fraction -> percent
            const pct = needsScale ? Number(rawChange) * 100 : Number(rawChange) || 0;
            return ({
              rank: item.rank || idx + 1,
              symbol: item.symbol?.replace('-USD', '') || 'N/A',
              price: item.current_price ?? item.price ?? 0,
              change: pct,
              initial_price_1min: item.initial_price_1min ?? item.initial_1min ?? null,
              peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
            });
          })
          // Ensure strict ranking by current change (desc) for display consistency
          .sort((a,b)=> b.change - a.change)
          .slice(0, 20)
          .map((it, i) => ({ ...it, rank: i + 1 }));
          setData(mapped);
        }
        if (!cancelled) {
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) { setLoading(false); setError(e.message); }
      }
    };

    if (!isConnected && !isPolling) {
      fetch1m();
      const id = setInterval(fetch1m, 15000);
      return () => { cancelled = true; clearInterval(id); };
    } else {
      if (data.length === 0) {
        fetch1m();
      }
      return () => { cancelled = true; };
    }
  }, [refreshTrigger, isConnected, isPolling, latestData.crypto]);

  const handleToggleWatchlist = async (symbol) => {
    const exists = watchlist.some((it) => (typeof it === 'string' ? it === symbol : it.symbol === symbol));
    setPopStar(symbol);
    setTimeout(() => setPopStar(null), 350);
    let updated;
    if (exists) {
      setActionBadge({ symbol, text: 'Removed!' });
      setTimeout(() => setActionBadge(null), 1200);
      updated = await removeFromWatchlist(symbol);
      send && send('watchlist_update', { action: 'remove', symbol });
    } else {
      const coin = data.find((c) => c.symbol === symbol);
      const currentPrice = coin ? coin.price : null;
      setActionBadge({ symbol, text: 'Added!' });
      setTimeout(() => setActionBadge(null), 1200);
      updated = await addToWatchlist(symbol, currentPrice);
      send && send('watchlist_update', { action: 'add', symbol, price: currentPrice });
    }
    setWatchlist(updated);
    onWatchlistChange && onWatchlistChange(updated);
  };

  // Compute slice by rank or index
  const startIdx = Array.isArray(externalRows)
    ? (typeof sliceStart === 'number' ? sliceStart : 0)
    : (typeof sliceStart === 'number' ? sliceStart : (typeof startRank === 'number' ? Math.max(0, startRank - 1) : undefined));
  const endIdx   = Array.isArray(externalRows)
    ? (typeof sliceEnd === 'number' ? sliceEnd : (externalRows?.length ?? undefined))
    : (typeof sliceEnd === 'number'   ? sliceEnd   : (typeof endRank === 'number'   ? Math.max(0, endRank)         : undefined));
  // Use WebSocket context data if it has more items than component data
  const rows = useMemo(() => {
    const src = Array.isArray(externalRows) ? externalRows : data;
    if (!Array.isArray(src)) {
      return [];
    }
    if (typeof startIdx === 'number' || typeof endIdx === 'number') {
      return src.slice(startIdx ?? 0, endIdx ?? src.length);
    }
    return src;
  }, [externalRows, data, startIdx, endIdx]);

  // Update 1m streaks for visible rows
  const visibleRows = rows.map(r => ({ symbol: r.symbol }));
  const get1m = updateStreaks('1m', visibleRows);

  // Force show data if WebSocket context has it, even when loading
  const hasContextData = latestData?.crypto && latestData.crypto.length > 0;
  
  if (loading && rows.length === 0 && !hasContextData) {
    return (
      <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="animate-pulse text-[#C026D3] font-mono">Loading 1-min gainers...</div>
        {/* Debug: Show why we're stuck loading */}
        {window.location.search.includes('debug') && (
          <div style={{ background: 'orange', color: 'white', fontSize: '12px', padding: '10px', margin: '10px' }}>
            STUCK LOADING: WS Connected: {isConnected}, Polling: {isPolling}, Has Context Data: {hasContextData}<br/>
            latestData: {JSON.stringify(latestData?.crypto?.slice(0,2) || [])}
          </div>
        )}
      </div>
    );
  }

  if (!loading && rows.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300">
  {rows.map((item, idx) => {
        const displayRank = (typeof startIdx === 'number') ? (startIdx + idx + 1) : ((item && item.rank) ? item.rank : (idx + 1));
        const isPlaceholder = false; // placeholders removed
        const entranceDelay = (idx % 12) * 0.035;
        const loopDelay = ((idx % 8) * 0.12);
        const breathAmt = 0.006;
        const PCT = item ? (typeof item.change === 'number' ? item.change : 0) : 0;
        // Use server-provided initial price when available; otherwise derive from PCT and current price
        const prevPrice = (item && (typeof item.initial_price_1min === 'number'))
          ? item.initial_price_1min
          : (item && typeof item.price === 'number' && typeof PCT === 'number' && PCT !== 0)
            ? (item.price / (1 + PCT / 100))
            : null;
        const coinbaseUrl = item ? `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD` : '#';
        const inWatch = item ? watchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol)) : false;

        return (
          <div key={item ? item.symbol : `placeholder-${idx}`} className="px-0 py-1 mb-1">
            <a
              href={coinbaseUrl}
              target="_blank"
              rel="noopener noreferrer"
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

                {/* Bottom edge subtle diamond glow (purple) */}
                <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
                  <span
                    className="block w-full h-full"
                    style={{
                      background:
                        'radial-gradient(ellipse at 50% 140%, rgba(192,38,211,0.18) 0%, rgba(192,38,211,0.10) 35%, rgba(192,38,211,0.04) 60%, transparent 85%)'
                    }}
                  />
                </span>

                {/* Mobile Card Layout */}
                <div className="sm:hidden relative z-10">
                  <div className="flex items-center justify-between py-3 px-2">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm">
                        {displayRank}
                      </div>
                      <div>
                        <div className="font-bold text-white text-xl mb-1">{item ? truncateSymbol(item.symbol, 8) : '—'}</div>
                        <div className="text-base text-teal font-mono font-bold">
                          ${item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                        </div>
                      </div>
                    </div>
                    <div className={`text-2xl font-bold ${PCT > 0 ? 'text-[#C026D3]' : 'text-pink'}`}>
                      {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercentage(PCT) : '0.00%'}
                    </div>
                  </div>
                </div>

                {/* Desktop Grid Layout */}
                <div className="hidden sm:grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                  {/* Col1: rank + symbol */}
                  <div className="flex items-center gap-4 min-w-0">
                    <div className={"flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0 " + (isPlaceholder ? 'opacity-0' : '')}>
                      {displayRank}
                    </div>
                    <div className={"min-w-0 flex items-center gap-3 " + (isPlaceholder ? 'opacity-0' : '')}>
                      <span className="font-bold text-white text-lg tracking-wide truncate">{item ? truncateSymbol(item.symbol, 6) : '—'}</span>
                      {item && item.peakCount > 1 && (
                        <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
                          {Array.from({ length: Math.min(3, item.peakCount) }).map((_, i) => (
                            <span key={i} className="w-1.5 h-1.5 rounded-full bg-[#C026D3]"></span>
                          ))}
                        </span>
                      )}
                      {actionBadge && actionBadge.symbol === (item && item.symbol) && (
                        <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">{actionBadge.text}</span>
                      )}
                    </div>
                  </div>

                  {/* Col2: price/current + previous */}
                  <div className={"w-[152px] pr-6 text-right " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className="text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                    </div>
                    <div className="text-sm leading-tight text-white/80 font-mono tabular-nums whitespace-nowrap">
                      {Number.isFinite(prevPrice) ? formatPrice(prevPrice) : '--'}
                    </div>
                  </div>

                  {/* Col3: % + Px (no label) */}
                  <div className={"w-[108px] pr-1.5 text-right align-top " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className={`text-lg md:text-xl font-bold tabular-nums leading-none whitespace-nowrap ${PCT > 0 ? 'text-[#C026D3]' : 'text-pink'}`}>
                      {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercentage(PCT) : '0.00%'}
                    </div>
                    {/* Streak Px subline */}
                    <div className="text-xs text-gray-300 leading-tight">
                      {item ? (() => {
                        const { level } = get1m(item.symbol);
                        return level > 0 ? (<div className="mt-1 subline-badge num">Px{level}</div>) : null;
                      })() : (<div className="mt-1 opacity-0 select-none subline-badge num"></div>)}
                    </div>
                  </div>

                  {/* Col4: star */}
                  <div className="w-[28px] text-right">
                    <button
                      onClick={(e)=>{ if(isPlaceholder){ e.preventDefault(); return; } e.preventDefault(); e.stopPropagation(); handleToggleWatchlist(item.symbol); }}
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
  {/* Show More logic retained if external slicing scenario; simplified since rows is final */}
  {!hideShowMore && false && (
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
