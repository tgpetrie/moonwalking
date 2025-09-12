/* eslint-disable sonarjs/no-ignored-exceptions */
/* eslint-disable sonarjs/cognitive-complexity */
/* eslint-disable complexity */
import React, { useEffect, useRef, useState, useMemo } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import WatchStar from './WatchStar.jsx';
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
  sliceStart,
  sliceEnd,
  startRank,
  endRank,
  fixedRows,
  hideShowMore,
  rows: externalRows,
}) {
  const ws = useWebSocket();
  const oneMinThrottleMs = ws?.oneMinThrottleMs ?? 15000;
  const gainersTop20 = ws?.gainersTop20 || [];
  const debugEnabled = ws?.debugEnabled ?? false;
  const vLog = ws?.vLog || (() => {});
  
  const shouldReduce = useReducedMotion();
  const lastRenderRef = useRef(0);
  // prevDataRef removed; context handles merge
  
  // Mobile optimizations
  const isMobile = isMobileDevice();
  const mobileConfig = getMobileOptimizedConfig();

  const [data, setData] = useState([]); // local displayed dataset (sliced / throttled)
  const [loading, setLoading] = useState(true);
  // local error state removed; fallback sets loading only
  const [popStar, setPopStar] = useState(null);
  const [actionBadge, setActionBadge] = useState(null);

  // This effect handles both throttled WS updates and a one-time REST fallback.
  useEffect(() => {
    // Only override with external rows when they contain data.
    if (Array.isArray(externalRows) && externalRows.length > 0) { setData(externalRows); setLoading(false); return; }

    // Use throttled data from WebSocket context if available
    if (Array.isArray(gainersTop20) && gainersTop20.length) {
      const now = Date.now();
  const throttleDefault = isMobile ? mobileConfig.throttleMs : 15000;
  const throttleMs = typeof oneMinThrottleMs === 'number' ? oneMinThrottleMs : throttleDefault;
      const since = now - (lastRenderRef.current || 0);
      if (debugEnabled) {
        vLog(`[GainersTable1Min] Throttle check: ${since}ms elapsed (limit ${throttleMs}ms), incoming top20 length: ${gainersTop20.length}`);
      }
      // Always render immediately on first data arrival (no prior render timestamp)
      if (lastRenderRef.current !== 0 && since < throttleMs) {
        if (debugEnabled) vLog('[GainersTable1Min] THROTTLED - skip render update');
        return;
      }
      lastRenderRef.current = now;
      // Data already normalized & ranked in context
      setData(gainersTop20);
      setLoading(false);
    } else {
      // Context is empty, perform a one-time fetch as a fallback.
      let cancelled = false;
      const fetchFallback = async () => {
        setLoading(true);
        try {
          const res = await fetchData(API_ENDPOINTS.gainersTable1Min);
          let arr = [];
          if (Array.isArray(res?.rows)) {
            arr = res.rows;
          } else if (Array.isArray(res?.data)) {
            arr = res.data;
          }
          if (!cancelled && arr.length) {
            const limit = typeof endRank === 'number' ? Math.min(20, endRank) : 20;
            const mapped = arr.slice(0, limit).map((item, idx) => {
              const rawChange = item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0;
              const pct = Number(rawChange) || 0;
              return ({
                rank: item.rank || idx + 1,
                symbol: item.symbol?.replace('-USD', '') || 'N/A',
                price: item.current_price ?? item.price ?? 0,
                change: pct,
                initial_price_1min: item.initial_price_1min ?? item.initial_1min ?? null,
                peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
              });
            }).sort((a, b) => b.change - a.change).map((it, i) => ({ ...it, rank: i + 1 }));
            setData(mapped);
          }
        } catch (e) {
          console.error('[GainersTable1Min] fallback fetch error', e);
        } finally {
          if (!cancelled) { setLoading(false); }
        }
      };
      fetchFallback();
      return () => { cancelled = true; };
    }
  }, [gainersTop20, externalRows, oneMinThrottleMs, debugEnabled, vLog, isMobile, mobileConfig.throttleMs]);

  const handleStarFeedback = (active, symbol) => {
    setPopStar(symbol);
    setTimeout(() => setPopStar(null), 350);
    setActionBadge({ symbol, text: active ? 'Added!' : 'Removed!' });
    setTimeout(() => setActionBadge(null), 1200);
  };

  // Decide whether to use external slice or internal data
  const useExternal = Array.isArray(externalRows) && externalRows.length > 0;

  // Compute slice indices based on props (used for both external and internal sources)
  const sIdx = useMemo(() => {
    if (typeof sliceStart === 'number') return sliceStart;
    if (typeof startRank === 'number') return Math.max(0, startRank - 1);
    return 0;
  }, [sliceStart, startRank]);
  const eIdx = useMemo(() => {
    if (typeof sliceEnd === 'number') return sliceEnd;
    if (typeof endRank === 'number') return Math.max(0, endRank);
    return undefined;
  }, [sliceEnd, endRank]);

  // Prefer internal context data when external slice is empty; apply slicing consistently
  const rows = useMemo(() => {
    const src = useExternal ? externalRows : data;
    if (!Array.isArray(src)) return [];
  // If parent already provided a sliced subset (externalRows), don't re-slice by absolute ranks
  if (useExternal) return src;
  return src.slice(sIdx, eIdx ?? src.length);
  }, [useExternal, externalRows, data, sIdx, eIdx]);

  // If this component renders a later slice (right column) and global data hasn't filled that slice yet,
  // show a loading state rather than an empty message.
  const sliceWaiting = useMemo(() => {
    const src = useExternal ? externalRows : data;
    if (!Array.isArray(src) || useExternal) return false;
    const total = src.length;
    const needStart = sIdx || 0;
    return rows.length === 0 && total > 0 && total <= needStart;
  }, [useExternal, externalRows, data, rows.length, sIdx]);

  // Update 1m streaks for visible rows
  const visibleRows = rows.map(r => ({ symbol: r.symbol }));
  const get1m = updateStreaks('1m', visibleRows);

  // Force show data if WebSocket context has it, even when loading
  const hasContextData = gainersTop20 && gainersTop20.length > 0;
  
  if (loading && rows.length === 0 && !hasContextData) {
    return (
      <div className="w-full h-full min-h-[400px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="animate-pulse text-muted font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if ((!loading && rows.length === 0) && !sliceWaiting) {
    return (
      <div className="w-full h-full min-h-[400px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[400px] px-0 transition-all duration-300">
  {rows.map((item, idx) => {
        let displayRank = idx + 1;
        if (typeof sIdx === 'number' && !Number.isNaN(sIdx)) {
          displayRank = sIdx + idx + 1;
        } else if (item && item.rank) {
          displayRank = item.rank;
        }
        const isPlaceholder = false; // placeholders removed
        const entranceDelay = (idx % 12) * 0.035;
        const loopDelay = ((idx % 8) * 0.12);
        const breathAmt = 0.006;
        let PCT = 0;
        if (item && typeof item.change === 'number') PCT = item.change;
        // Use server-provided initial price when available; otherwise derive from PCT and current price
        let prevPrice = null;
        if (item && typeof item.initial_price_1min === 'number') {
          prevPrice = item.initial_price_1min;
        } else if (item && typeof item.price === 'number' && typeof PCT === 'number' && PCT !== 0) {
          prevPrice = item.price / (1 + PCT / 100);
        }
        const coinbaseUrl = item ? `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD` : '#';

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

                {/* Orange glow for gainers */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span
                    className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                    style={{
                      background: 'radial-gradient(circle at 50% 50%, rgba(254,164,0,0.20) 0%, rgba(254,164,0,0.10) 45%, rgba(254,164,0,0.05) 70%, transparent 100%)',
                      top: '-15%',
                      left: '-15%',
                      position: 'absolute',
                    }}
                  />
                </span>

                {/* Bottom edge subtle glow (orange) */}
                <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
                  <span
                    className="block w-full h-full"
                    style={{
                      background:
                        'radial-gradient(ellipse at 50% 140%, rgba(254,164,0,0.18) 0%, rgba(254,164,0,0.10) 35%, rgba(254,164,0,0.04) 60%, transparent 85%)'
                    }}
                  />
                </span>

                {/* Mobile Card Layout (temporarily disabled to guarantee desktop visibility across breakpoints) */}
                <div className="hidden relative z-10">
                  <div className="flex items-center justify-between py-3 px-2">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm">
                        {displayRank}
                      </div>
                      <div>
                        <div className="font-headline font-bold text-white text-xl mb-1">{item ? truncateSymbol(item.symbol, 8) : '—'}</div>
                        <div className="text-base text-teal font-mono font-bold">
                          {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className={`text-2xl font-bold font-mono text-right ${PCT > 0 ? 'text-pos' : 'text-neg'}`} data-pct={PCT > 0 ? 'pos' : 'neg'}>
                        {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercentage(PCT) : '0.00%'}
                      </div>
                      {!isPlaceholder && (
                        <WatchStar productId={item.symbol} className={popStar === (item && item.symbol) ? 'animate-star-pop' : ''} onToggled={handleStarFeedback} />
                      )}
                    </div>
                  </div>
                </div>

                {/* Desktop Grid Layout - always enabled to avoid breakpoint hiding issues */}
                <div className="grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                  {/* Col1: rank + symbol */}
                  <div className="flex items-center gap-4 min-w-0">
                    <div className={"flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm shrink-0 " + (isPlaceholder ? 'opacity-0' : '')} style={{ background:'rgba(254,164,0,0.28)', color:'var(--pos)' }}>
                      {displayRank}
                    </div>
                    <div className={"min-w-0 flex items-center gap-3 " + (isPlaceholder ? 'opacity-0' : '')}>
                      <span className="font-headline font-bold text-white text-lg tracking-wide truncate">{item ? truncateSymbol(item.symbol, 6) : '—'}</span>
                      {item && item.peakCount > 1 && (
                        <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
              {Array.from({ length: Math.min(3, item.peakCount) }).map((_, i) => (
                <span key={`${item.symbol}-dot-${i}`} className="w-1.5 h-1.5 rounded-full bg-[#C026D3]"></span>
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
                    <div className={`text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${PCT > 0 ? 'text-orange' : 'text-neg'}`} data-pct={PCT > 0 ? 'pos' : 'neg'}>
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
                    {!isPlaceholder && (
                      <WatchStar productId={item.symbol} className={popStar === (item && item.symbol) ? 'animate-star-pop' : ''} onToggled={handleStarFeedback} />
                    )}
                  </div>
                </div>
              </motion.div>
            </a>
          </div>
        );
      })}

      {/* No per-component Show More button when hideShowMore is true */}
  {/* Show More logic retained if external slicing scenario; simplified since rows is final */}
  {/* Show More intentionally omitted for 1-min table */}
    </div>
  );
}

GainersTable1Min.propTypes = {
  sliceStart: PropTypes.number,
  sliceEnd: PropTypes.number,
  startRank: PropTypes.number,
  endRank: PropTypes.number,
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool,
  rows: PropTypes.array,
};
