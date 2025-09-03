import React, { useEffect, useRef, useState, useMemo, useContext } from 'react';
import { useReducedMotion } from 'framer-motion';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import WebSocketContext from '../context/websocketcontext.jsx';
import { formatPercent, truncateSymbol, formatPrice } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import { updateStreaks } from '../logic/streaks';
import PropTypes from 'prop-types';
import { isMobileDevice, getMobileOptimizedConfig } from '../utils/mobileDetection.js';
import TableSkeleton from './TableSkeleton.jsx';
import useKeyboardNavigation from '../hooks/useKeyboardNavigation.js';
import usePerformanceMonitor from '../hooks/usePerformanceMonitor.js';

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
  const [expanded, setExpanded] = useState(false);
  // A/B color toggle: 'aqua' (default) or 'teal'
  const safeLocalStorage = (action, key, value) => {
    try {
      if (action === 'get') return localStorage.getItem(key);
      if (action === 'set') return localStorage.setItem(key, value);
    } catch (err) {
      // non-fatal; log at debug level for local troubleshooting
      try { console.debug && console.debug('safeLocalStorage error', err); } catch (_) {}
      return null;
    }
  };

  const [colorVariant, setColorVariant] = useState(() => safeLocalStorage('get', 'gainers1m_color_variant') || 'aqua');
  // Use context directly (won't throw when provider is absent) to satisfy hooks rules
  const wsCtx = useContext(WebSocketContext) || {};
  const {
    latestData = { crypto: [] },
    isConnected = false,
    isPolling = false,
    oneMinThrottleMs = 15000,
    send = () => {},
    gainersTop20 = [],
    debugEnabled = false,
    vLog = () => {}
  } = wsCtx;
  
  const shouldReduce = useReducedMotion();
  const lastRenderRef = useRef(0);
  
  // Mobile optimizations
  const isMobile = isMobileDevice();
  const mobileConfig = getMobileOptimizedConfig();

  const [data, setData] = useState([]); // local displayed dataset (sliced / throttled)
  const [loading, setLoading] = useState(true);
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [popStar, setPopStar] = useState(null);

  // Performance monitoring (hook has internal side-effects; no return value required)
  usePerformanceMonitor('GainersTable1Min', { enabled: process.env.NODE_ENV === 'development' });

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

  // Throttled WS updates (skip when external rows provided)
  useEffect(() => {
    if (Array.isArray(externalRows)) { setData(externalRows); setLoading(false); return; }
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
          const mapped = res.data.slice(0, 20).map((item, idx) => ({
            rank: item.rank || idx + 1,
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price ?? item.price ?? 0,
            change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
            peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
          }))
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

  const toggleColorVariant = () => {
    const next = colorVariant === 'aqua' ? 'teal' : 'aqua';
    setColorVariant(next);
    safeLocalStorage('set', 'gainers1m_color_variant', next);
  };

  // Compute slice by rank or index
  const computeStartIdx = () => {
    if (Array.isArray(externalRows)) return (typeof sliceStart === 'number' ? sliceStart : 0);
    if (typeof sliceStart === 'number') return sliceStart;
    if (typeof startRank === 'number') return Math.max(0, startRank - 1);
    return undefined;
  };
  const startIdx = computeStartIdx();
  const defaultCollapsed = 10;
  const defaultExpanded = 20;
  const computeEndIdx = () => {
    if (Array.isArray(externalRows)) return (typeof sliceEnd === 'number' ? sliceEnd : (externalRows?.length ?? undefined));
    if (typeof sliceEnd === 'number') return sliceEnd;
    if (typeof endRank === 'number') return Math.max(0, endRank);
    return expanded ? defaultExpanded : defaultCollapsed;
  };
  const computedEnd = computeEndIdx();
  const endIdx = computedEnd;
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

  // Keyboard navigation
  const navigation = useKeyboardNavigation(rows, {
    onSelect: (item) => item && handleToggleWatchlist(item.symbol),
    onEscape: () => navigation.resetNavigation()
  });

  // Update 1m streaks for visible rows
  const visibleRows = rows.map(r => ({ symbol: r.symbol }));
  const get1m = updateStreaks('1m', visibleRows);

  // Force show data if WebSocket context has it, even when loading
  const hasContextData = latestData?.crypto && latestData.crypto.length > 0;
  
  if (loading && rows.length === 0 && !hasContextData) {
    return <TableSkeleton rows={10} title="1-MIN GAINERS" />;
  }

  if (!loading && rows.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  const labelId = 'gainers1m-color-toggle';

  return (
    <div className="w-full h-full min-h-[420px] px-0 transition-all duration-300">
      {/* Color A/B toggle for QA: Aqua vs Teal */}
      <div className="flex justify-end items-center gap-2 mb-2">
        <label htmlFor={labelId} className="text-xs text-gray-400">Color:</label>
        <button
          id={labelId}
          onClick={toggleColorVariant}
          className="px-2 py-1 rounded bg-gray-800 text-white text-xs"
          aria-pressed={colorVariant === 'teal'}
          title="Toggle Aqua / Teal for percentage color"
        >
          {colorVariant === 'aqua' ? 'Aqua' : 'Teal'}
        </button>
      </div>
  {rows.map((item, idx) => (
    <GainerRow1
      key={item ? item.symbol : `placeholder-${idx}`}
      item={item}
      idx={idx}
      startIdx={startIdx}
      navigation={navigation}
      shouldReduce={shouldReduce}
      popStar={popStar}
      get1m={get1m}
      handleToggleWatchlist={handleToggleWatchlist}
      watchlist={watchlist}
    />
  ))}
      {/* Show more / less control */}
      {!hideShowMore && (
        <div className="mt-2 flex items-center justify-center">
          <button
            type="button"
            onClick={() => setExpanded((s) => !s)}
            className="text-xs px-3 py-1 rounded bg-purple-700 hover:bg-purple-600 text-white"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        </div>
      )}

      {/* No per-component Show More button when hideShowMore is true */}
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

// extracted memoized row to reduce cognitive complexity in parent
const GainerRow1 = React.memo(function GainerRow1({
  item, idx, startIdx, navigation, shouldReduce, popStar, get1m, handleToggleWatchlist, watchlist
}) {
  const displayRank = (typeof startIdx === 'number') ? (startIdx + idx + 1) : ((item && item.rank) ? item.rank : (idx + 1));
  const PCT = item ? item.change : 0;
  const inWatch = item ? watchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol)) : false;
  const coinbaseUrl = item ? `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD` : '#';
  const isPlaceholder = false;

  return (
    <div key={item ? item.symbol : `placeholder-${idx}`} className="px-0 py-1 mb-1" {...navigation.getItemProps(idx)}>
      <a
        href={coinbaseUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`block group ${navigation.selectedIndex === idx ? 'keyboard-focused' : ''}`}
      >
        <div className="relative overflow-hidden rounded-xl p-4 h-[96px] hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform will-change-transform">
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

          <div className="mw-mobile-only relative z-10">
            <div className="flex items-center justify-between py-3 px-2">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm">
                  {displayRank}
                </div>
                <div>
                  <div className="font-bold text-white text-xl mb-1">{item ? truncateSymbol(item.symbol, 8) : '—'}</div>
                  <div className="text-base color-lock-teal font-mono font-bold">
                    ${item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className={`text-2xl font-bold ${PCT > 0 ? 'color-lock-purple' : 'color-lock-pink'}`}>
                  {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercent(PCT, { fromFraction: false, max: 3 }) : '0.00%'}
                </div>

                <button
                  onClick={(e) => {
                    if (isPlaceholder) { e.preventDefault(); return; }
                    e.preventDefault();
                    e.stopPropagation();
                    handleToggleWatchlist(item && item.symbol);
                  }}
                  disabled={isPlaceholder}
                  aria-label={inWatch ? 'Remove from watchlist' : 'Add to watchlist'}
                  aria-pressed={inWatch}
                  className={isPlaceholder ? 'opacity-0' : (popStar === (item && item.symbol) ? 'animate-star-pop p-1' : 'p-1')}
                  style={{ minWidth: '28px', minHeight: '28px' }}
                >
                  <StarIcon
                    filled={inWatch}
                    className={inWatch ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                    style={{ width: '18px', height: '18px', transition: 'transform .15s' }}
                    aria-hidden="true"
                  />
                </button>
              </div>
            </div>
          </div>

          <div className="mw-desktop-grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
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
              </div>
            </div>

            <div className={"w-[152px] pr-6 text-right " + (isPlaceholder ? 'opacity-0' : '')}>
              <div className="text-lg md:text-xl font-bold color-lock-teal font-mono tabular-nums leading-none whitespace-nowrap">
                {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
              </div>
              <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                {item && typeof item.price === 'number' && typeof PCT === 'number' && PCT !== 0
                  ? (() => { const prev = item.price / (1 + PCT / 100); return formatPrice(prev); })()
                  : '--'}
              </div>
            </div>

            <div className={"w-[108px] pr-1.5 text-right align-top " + (isPlaceholder ? 'opacity-0' : '')}>
              <div className={`text-lg md:text-xl font-bold tabular-nums leading-none whitespace-nowrap ${PCT > 0 ? 'color-lock-purple' : 'color-lock-pink'}`}> 
                {PCT > 0 && '+'}{typeof PCT === 'number' ? formatPercent(PCT, { fromFraction: false, max: 3 }) : '0.00%'}
              </div>
              <div className="text-xs text-gray-300 leading-tight">
                {item ? (() => {
                  const { level } = get1m(item.symbol);
                  return level > 0 ? (<div className="mt-1 subline-badge num">Px{level}</div>) : null;
                })() : (<div className="mt-1 opacity-0 select-none subline-badge num"></div>)}
              </div>
            </div>

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
        </div>
      </a>
    </div>
  );
});
