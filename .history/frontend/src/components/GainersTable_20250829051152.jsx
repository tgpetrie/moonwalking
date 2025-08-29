import React, { useEffect, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist } from '../api.js';
import { formatPercentage, truncateSymbol } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import TableShell from './TableShell';
import PriceFlash from './PriceFlash';
import { useStaggeredPolling } from '../hooks/useStaggeredPolling';
import { useStaggeredRows } from '../hooks/useStaggeredRows';

// --- helpers to robustly read fields regardless of backend aliasing ---
const toNum = (v) => {
  if (typeof v === 'number') {
    return Number.isFinite(v) ? v : null;
  }
  if (typeof v === 'string') {
    const x = parseFloat(v);
    return Number.isFinite(x) ? x : null;
  }
  return null;
};

const pickNumber = (obj, keys) => {
  for (const k of keys) {
    const v = toNum(obj?.[k]);
    if (v != null) {
      return v;
    }
  }
  return null;
};

const GainersTable = ({ refreshTrigger }) => {
  // Inject animation styles for pop/fade effects (watchlist add feedback)
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('gainers-table-animations')) {
      const style = document.createElement('style');
      style.id = 'gainers-table-animations';
      style.innerHTML = `
        @keyframes starPop { 0% { transform: scale(1); } 40% { transform: scale(1.35); } 70% { transform: scale(0.92); } 100% { transform: scale(1); } }
        .animate-star-pop { animation: starPop 0.35s cubic-bezier(.4,2,.6,1) both; }
        @keyframes fadeInOut { 0% { opacity: 0; transform: translateY(-8px) scale(0.9); } 10% { opacity: 1; transform: translateY(0) scale(1.05); } 80% { opacity: 1; transform: translateY(0) scale(1.05); } 100% { opacity: 0; transform: translateY(-8px) scale(0.9); } }
        .animate-fade-in-out { animation: fadeInOut 1.2s cubic-bezier(.4,2,.6,1) both; }
        @keyframes flashUp { 0% { background-color: rgba(16,185,129,0.35);} 100% { background-color: transparent;} }
        @keyframes flashDown { 0% { background-color: rgba(244,63,94,0.35);} 100% { background-color: transparent;} }
        .flash-up { animation: flashUp 0.9s ease-out; }
        .flash-down { animation: flashDown 0.9s ease-out; }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const [data, setData] = useState([]); // full current dataset
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [addedBadge, setAddedBadge] = useState(null); // symbol for 'Added!' badge
  const prevMapRef = useRef({});

  // Fetcher used by staggered polling
  const fetcher = async () => {
    const response = await fetchData(API_ENDPOINTS.gainersTable);
    if (!response || !Array.isArray(response.data)) {
      return [];
    }
    const next = response.data
      .map((item, index) => {
        const symbol = (item.symbol || '').replace('-USD', '') || 'N/A';
        const price = pickNumber(item, ['current_price', 'price']);
        const prev3mRaw = pickNumber(item, ['initial_price_3min', 'prev_price_3m', 'prev3m', 'previous']);
        let pct3m = pickNumber(item, ['price_change_percentage_3min', 'pct_change_3m', 'change3m', 'gain', 'percentage']);
        if (pct3m == null && typeof price === 'number' && typeof prev3mRaw === 'number' && prev3mRaw !== 0) {
          pct3m = ((price - prev3mRaw) / prev3mRaw) * 100;
        }
        const prev3m = (typeof prev3mRaw === 'number')
          ? prev3mRaw
          : (typeof price === 'number' && typeof pct3m === 'number' && pct3m !== 0
              ? price / (1 + pct3m / 100)
              : null);
        return {
          rank: item.rank || (index + 1),
          symbol,
          price,
          change3m: (typeof pct3m === 'number' && !Number.isNaN(pct3m)) ? pct3m : null,
          prev3m: (typeof prev3m === 'number' && Number.isFinite(prev3m)) ? prev3m : null,
          peakCount: item.peak_count ?? item.peaks ?? null,
        };
      })
      .filter(r => typeof r.change3m === 'number' && r.change3m > 0)
      .sort((a, b) => b.change3m - a.change3m)
      .slice(0, 7);
    // annotate with diff direction for change cell
    const annotated = next.map(row => {
      const prev = prevMapRef.current[row.symbol];
      const diffDir = prev && typeof prev.change3m === 'number' && typeof row.change3m === 'number'
        ? (row.change3m > prev.change3m ? 'up' : row.change3m < prev.change3m ? 'down' : 'flat')
        : 'flat';
      return { ...row, diffDir };
    });
    // update prev map
    const newMap = {};
    annotated.forEach(r => { newMap[r.symbol] = r; });
    prevMapRef.current = newMap;
    return annotated;
  };

  const { data: polled, error: pollError, loading: pollLoading } = useStaggeredPolling(fetcher, {
    interval: 30000, // 30s for 3-min table
    offset: 0,       // first table fires immediately
    jitter: 1200,    // slight random spread each cycle
    active: true
  });

  // Apply staggered row reveal when dataset changes
  const visibleRows = useStaggeredRows(polled || [], 45, 0);

  useEffect(() => {
    if (pollError) {
      setError(pollError.message || 'Fetch error');
    }
    if (Array.isArray(polled)) {
      setData(polled);
    }
    setLoading(pollLoading && (!polled || polled.length === 0));
  }, [polled, pollError, pollLoading]);

  // Remove old interval logic; polling handled by hook. Still respond to external refreshTrigger by forcing a manual refresh of prev map signature.
  useEffect(() => {
    // On external trigger clear prev map so next diff shows neutral until next change.
    prevMapRef.current = {};
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
      const updated = await addToWatchlist(symbol);
      setWatchlist(updated);
    }
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

  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0">
      {visibleRows.map((r) => {
        const isInWatchlist = watchlist.includes(r.symbol);
        const isPopping = popStar === r.symbol;
        const url = `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD`;
        const changeFlashClass = r.diffDir === 'up' ? 'value-flash-up' : r.diffDir === 'down' ? 'value-flash-down' : '';

        return (
          <div key={r.symbol} className="px-2 py-1 mb-1 row-stagger-enter">
            <a href={url} target="_blank" rel="noopener noreferrer" className="block group">
              <div className="relative overflow-hidden rounded-xl p-4 hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform">
                {/* PURPLE inner glow (#C026D3) */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span
                    className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                    style={{
                      background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                      position: 'absolute', top: '-15%', left: '-15%'
                    }}
                  />
                </span>

                {/* MAIN ROW — use TableShell for consistent column sizing */}
                <TableShell>

                  {/* LEFT flexible: rank + symbol */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0">{r.rank}</div>
                    <div className="min-w-0">
                      <div className="font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(r.symbol, 8)}</div>
                    </div>
                  </div>

                  {/* Col2: Price (stack current + previous) */}
                  <div className="w-[152px] pr-6 text-right">
                    {Number.isFinite(r.price) ? (
                      <PriceFlash
                        value={r.price}
                        precision={r.price < 1 && r.price > 0 ? 4 : 2}
                        className="text-teal font-mono text-base sm:text-lg md:text-xl font-bold tabular-nums leading-none"
                      />
                    ) : (
                      <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none">N/A</div>
                    )}
                    <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                      {typeof r.prev3m === 'number'
                        ? `$${r.prev3m < 1 && r.prev3m > 0 ? r.prev3m.toFixed(4) : r.prev3m.toFixed(2)}`
                        : '--'}
                    </div>
                  </div>

                  {/* Col3: % change over 3-minutes */}
                  <div className={`w-[108px] pr-1.5 text-right align-top`}>
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap ${r.change3m != null && r.change3m < 0 ? 'text-pink' : 'text-[#C026D3]'} ${changeFlashClass}` }>
                      {typeof r.change3m === 'number' ? `${r.change3m > 0 ? '+' : ''}${formatPercentage(r.change3m)}` : 'N/A'}
                    </div>
                    {typeof r.peakCount === 'number' && r.peakCount > 0 && (
                      <span className="badge-peak badge-peak--compact" aria-hidden>{r.peakCount <= 1 ? 'x' : `x${r.peakCount}`}</span>
                    )}
                    <div className="text-xs text-gray-400 leading-tight">3-min</div>
                  </div>

                  {/* Col4: Star (action area) */}
                  <div className="w-[48px] text-right">
                    <button
                      onClick={(e)=>{e.preventDefault(); /* symbol only for now */ setPopStar(r.symbol); setTimeout(()=>setPopStar(null), 350); }}
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
                </TableShell>
              </div>
            </a>
          </div>
        );
      })}
    </div>
  );
};

export default GainersTable;