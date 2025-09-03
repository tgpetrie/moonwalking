/* eslint-disable react/prop-types */
/* eslint-disable sonarjs/cognitive-complexity */
/* eslint-disable complexity */
import React, { useEffect, useState, memo } from 'react';
import PropTypes from 'prop-types';
import { motion, useReducedMotion } from 'framer-motion';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { formatPercent, truncateSymbol, formatPrice } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import { updateStreaks } from '../logic/streaks';
import useKeyboardNavigation from '../hooks/useKeyboardNavigation.js';

const GainersTable = ({ refreshTrigger, initialRows = 7, maxRows = 13, expanded }) => {
  const shouldReduce = useReducedMotion();
  // Inject animation styles for pop/fade effects (watchlist add feedback)
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
  const { send, gainers3mTop } = useWebSocket();
  const [data, setData] = useState([]);
  const [visibleCount, setVisibleCount] = useState(initialRows);
  const [loading, setLoading] = useState(true);
  const [watchlist, setWatchlist] = useState([]);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [actionBadge, setActionBadge] = useState(null); // watchlist feedback badge

  // Keyboard navigation
  const visibleData = data.slice(0, visibleCount);
  const navigation = useKeyboardNavigation(visibleData, {
    onSelect: (item) => item && handleToggleWatchlist(item.symbol),
    onEscape: () => navigation.resetNavigation()
  });

  const getBadgeText = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) {
      return 'STRONG HIGH';
    }
    if (absChange >= 2) {
      return 'STRONG';
    }
    return '';
  };

  // Prefer real-time derived list; fallback to REST every 30s if empty
  useEffect(() => {
    let cancelled = false;
    const hydrateFromContext = () => {
      if (Array.isArray(gainers3mTop) && gainers3mTop.length) {
        setData(gainers3mTop.map(r => ({ ...r, badge: getBadgeText(Math.abs(r.change3m||0)) })));
        setLoading(false);
        return true;
      }
      return false;
    };
    if (hydrateFromContext()) {
      return () => { cancelled = true; };
    }
    const fetchFallback = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.gainersTable);
        if (!cancelled && response?.data?.length) {
          const next = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price ?? item.price ?? 0,
            change3m: item.price_change_percentage_3min ?? item.change3m ?? item.change ?? 0,
            peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
            badge: getBadgeText(Math.abs((item.price_change_percentage_3min ?? 0)))
          }));
          setData(next);
        } else if (!cancelled) {
          setData([]);
        }
      } catch (err) {
        if (!cancelled) {
          setData([]);
        }
        console.error('Error fetching gainers data (fallback):', err);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    fetchFallback();
    const interval = setInterval(fetchFallback, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [refreshTrigger, gainers3mTop]);

  // React to later arrival of context data (first empty -> then filled)
  useEffect(() => {
    if (data.length === 0 && Array.isArray(gainers3mTop) && gainers3mTop.length) {
      setData(gainers3mTop.map(r => ({ ...r, badge: getBadgeText(Math.abs(r.change3m||0)) })));
      setLoading(false);
    }
  }, [gainers3mTop, data.length]);

  // Sync visible rows with an external expanded control if provided
  useEffect(() => {
    if (typeof expanded === 'boolean') {
      setVisibleCount(expanded ? Math.min(maxRows, data.length || maxRows) : initialRows);
    }
  }, [expanded, data.length, initialRows, maxRows]);

  useEffect(() => {
    async function fetchWatchlist() {
      const data = await getWatchlist();
      setWatchlist(data);
    }
    fetchWatchlist();
  }, [refreshTrigger]);

  const handleToggleWatchlist = async (symbol) => {
    const exists = watchlist.some(it => (typeof it === 'string' ? it === symbol : it.symbol === symbol));
    setPopStar(symbol);
    setTimeout(() => setPopStar(null), 350);
    let updated;
    if (exists) {
      setActionBadge({ symbol, text: 'Removed!' });
      setTimeout(() => setActionBadge(null), 1200);
      updated = await removeFromWatchlist(symbol);
      send && send('watchlist_update', { action: 'remove', symbol });
    } else {
      setActionBadge({ symbol, text: 'Added!' });
      setTimeout(() => setActionBadge(null), 1200);
      const item = data.find(d => d.symbol === symbol);
      updated = await addToWatchlist(symbol, item ? item.price : 0);
      send && send('watchlist_update', { action: 'add', symbol });
    }
    setWatchlist(updated);
  };

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-[#C026D3] font-mono">Loading gainers...</div>
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

  // Update 3m streaks for current gainers set (no placeholders)
  const rows = data.slice(0, Math.min(visibleCount, maxRows));
  const get3m = updateStreaks('3m', rows.map(d => ({ symbol: d.symbol })));

  return (
    <div className="w-full h-full min-h-[420px] px-0">
      {rows.map((r, idx) => (
        <GainerRow
          key={r ? r.symbol : `placeholder-${idx}`}
          row={r}
          idx={idx}
          shouldReduce={shouldReduce}
          get3m={get3m}
          watchlist={watchlist}
          actionBadge={actionBadge}
          popStar={popStar}
          onToggle={handleToggleWatchlist}
          keyboardProps={navigation.getItemProps(idx)}
          isKeyboardSelected={navigation.selectedIndex === idx}
        />
      ))}
      {/* Show More / Less (uncontrolled only) */}
      {typeof expanded !== 'boolean' && data.length > initialRows && (
        <div className="w-full flex justify-center mt-2 mb-1">
          <button
            onClick={() => setVisibleCount(c => (c > initialRows ? initialRows : Math.min(maxRows, data.length)))}
            className="px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
            aria-pressed={visibleCount > initialRows}
          >
            {visibleCount > initialRows ? 'Show Less' : 'Show More'}
          </button>
        </div>
      )}
    </div>
  );
};

const GainerRow = memo(function GainerRow({ row: r, idx, shouldReduce, get3m, watchlist, actionBadge, popStar, onToggle, keyboardProps, isKeyboardSelected }) {
  const isPlaceholder = !r;
  const entranceDelay = (idx % 12) * 0.035;
  const loopDelay = ((idx % 8) * 0.12);
  const breathAmt = 0.006;
  const isInWatchlist = r ? watchlist.some(it => (typeof it === 'string' ? it === r.symbol : it.symbol === r.symbol)) : false;
  const isPopping = r ? (popStar === r.symbol) : false;
  const showBadge = r ? (actionBadge && actionBadge.symbol === r.symbol) : false;
  const prev = r && (typeof r.price === 'number' && typeof r.change3m === 'number' && r.change3m !== 0)
    ? (r.price / (1 + r.change3m / 100))
    : null;
  const url = r ? `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD` : '#';
  return (
    <div className="px-0 py-1 mb-1" {...keyboardProps}>
      <a href={url} onClick={(e)=>{ if(isPlaceholder){ e.preventDefault(); } }} target={isPlaceholder ? undefined : "_blank"} rel={isPlaceholder ? undefined : "noopener noreferrer"} className={`block group ${isKeyboardSelected ? 'keyboard-focused' : ''}`}>
        <motion.div
          className="relative overflow-hidden rounded-xl p-4 h-[96px] hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform will-change-transform"
          initial={shouldReduce ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut', delay: entranceDelay }}
          whileHover={shouldReduce ? {} : { scale: 1.012 }}
          whileTap={shouldReduce ? {} : { scale: 0.985 }}
        >
          {!shouldReduce && (
            <motion.div
              aria-hidden
              className="absolute inset-0 pointer-events-none"
              animate={{ scale: [1, 1 + breathAmt, 1] }}
              transition={{ duration: 3.6, repeat: Infinity, ease: 'easeInOut', delay: loopDelay }}
            />
          )}
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
            <span
              className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
              style={{
                background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                position: 'absolute', top: '-15%', left: '-15%'
              }}
            />
          </span>
          <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
            <span
              className="block w-full h-full"
              style={{
                background:
                  'radial-gradient(ellipse at 50% 140%, rgba(192,38,211,0.18) 0%, rgba(192,38,211,0.10) 35%, rgba(192,38,211,0.04) 60%, transparent 85%)'
              }}
            />
          </span>
          {/* Mobile */}
          <div className="sm:hidden relative z-10">
            <div className="flex items-center justify-between py-3 px-2">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm">{r ? r.rank : 0}</div>
                <div>
                  <div className="font-bold text-white text-xl mb-1">{r ? truncateSymbol(r.symbol, 8) : '—'}</div>
                  <div className="text-base color-lock-teal font-mono font-bold">${r && Number.isFinite(r.price) ? formatPrice(r.price) : '0.00'}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className={`text-2xl font-bold ${r && r.change3m > 0 ? 'color-lock-purple' : 'color-lock-pink'}`}>{r && r.change3m > 0 && '+'}{r && typeof r.change3m === 'number' ? formatPercent(r.change3m, { fromFraction: false, max: 2 }) : '0.00%'}</div>
                <button
                  onClick={(e)=>{ e.preventDefault(); e.stopPropagation(); if(!isPlaceholder && r){ onToggle(r.symbol); } }}
                  className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-center"
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
          </div>
          {/* Desktop */}
          <div className="hidden sm:grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
            <div className="flex items-center gap-3 sm:gap-4 min-w-0">
              <div className={"flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0 " + (isPlaceholder ? 'opacity-0' : '')}>{r ? r.rank : 0}</div>
              <div className={"min-w-0 flex items-center gap-2 " + (isPlaceholder ? 'opacity-0' : '')}>
                <div className="font-bold text-white text-lg tracking-wide truncate">{r ? truncateSymbol(r.symbol, 6) : '—'}</div>
                {!isPlaceholder && showBadge && (
                  <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">{actionBadge.text}</span>
                )}
              </div>
            </div>
            <div className={"w-[152px] pr-6 text-right " + (isPlaceholder ? 'opacity-0' : '')}>
              <div className="text-base sm:text-lg md:text-xl font-bold color-lock-teal font-mono tabular-nums leading-none whitespace-nowrap">{r && Number.isFinite(r.price) ? formatPrice(r.price) : 'N/A'}</div>
              <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">{prev !== null ? formatPrice(prev) : '--'}</div>
            </div>
            <div className={"w-[108px] pr-1.5 text-right align-top " + (isPlaceholder ? 'opacity-0' : '')}>
              <div className={`text-lg sm:text-xl md:text-2xl font-bold tabular-nums leading-none whitespace-nowrap ${r && r.change3m > 0 ? 'color-lock-purple' : 'color-lock-pink'}`}>{r && r.change3m > 0 && '+'}{r && typeof r.change3m === 'number' ? formatPercent(r.change3m, { fromFraction: false, max: 2 }) : 'N/A'}</div>
              {(() => { const { level } = r ? get3m(r.symbol) : { level: 0 }; return level > 0 ? (<div className="text-xs text-gray-300 leading-tight mt-1 subline-badge num">Px{level}</div>) : null; })()}
            </div>
            <div className="w-[28px] text-right">
              <button
                onClick={(e)=>{ e.preventDefault(); e.stopPropagation(); if(!isPlaceholder && r){ onToggle(r.symbol); } }}
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
        </motion.div>
      </a>
    </div>
  );
});

export default GainersTable;

GainersTable.propTypes = {
  refreshTrigger: PropTypes.any,
  initialRows: PropTypes.number,
  maxRows: PropTypes.number,
  expanded: PropTypes.bool
};

GainerRow.propTypes = {
  row: PropTypes.shape({
    symbol: PropTypes.string,
    rank: PropTypes.number,
    price: PropTypes.number,
    change3m: PropTypes.number
  }),
  idx: PropTypes.number.isRequired,
  shouldReduce: PropTypes.bool,
  get3m: PropTypes.func.isRequired,
  watchlist: PropTypes.array.isRequired,
  actionBadge: PropTypes.shape({ symbol: PropTypes.string, text: PropTypes.string }),
  popStar: PropTypes.string,
  onToggle: PropTypes.func.isRequired
};
