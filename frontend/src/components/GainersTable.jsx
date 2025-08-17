import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist } from '../api.js';
import { formatPercentage, truncateSymbol } from '../utils/formatters.js';
import StarIcon from './StarIcon';

// --- helpers to robustly read fields regardless of backend aliasing ---
const toNum = (v) => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string') {
    const x = parseFloat(v);
    return Number.isFinite(x) ? x : null;
  }
  return null;
};

const pickNumber = (obj, keys) => {
  for (const k of keys) {
    const v = toNum(obj?.[k]);
    if (v != null) return v;
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

  const [data, setData] = useState([]);
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
          const next = response.data
            .map((item, index) => {
              const symbol = (item.symbol || '').replace('-USD', '') || 'N/A';
              const price = pickNumber(item, ['current_price', 'price']);
              const prev3mRaw = pickNumber(item, ['initial_price_3min', 'prev_price_3m', 'prev3m', 'previous']);
              let pct3m = pickNumber(item, ['price_change_percentage_3min', 'pct_change_3m', 'change3m', 'gain', 'percentage']);

              // If backend provided N/A or omitted percent, derive it from price & prev
              if (pct3m == null && typeof price === 'number' && typeof prev3mRaw === 'number' && prev3mRaw !== 0) {
                pct3m = ((price - prev3mRaw) / prev3mRaw) * 100;
              }

              // Resolve previous price from given prev or reverse the percent math
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
            // keep GAINERS positive only and sort desc
            .filter(r => typeof r.change3m === 'number' && r.change3m > 0)
            .sort((a, b) => b.change3m - a.change3m);

          if (isMounted) setData(next.slice(0, 7));
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
      {data.map((r) => {
        const isInWatchlist = watchlist.includes(r.symbol);
        const isPopping = popStar === r.symbol;
        const url = `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD`;

        return (
          <div key={r.symbol} className="px-2 py-1 mb-1">
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

                {/* MAIN ROW — GRID: [minmax(0,1fr) | 152px | 108px | 28px] */}
                <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">

                  {/* LEFT flexible: rank + symbol */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0">{r.rank}</div>
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
                      {typeof r.prev3m === 'number'
                        ? `$${r.prev3m < 1 && r.prev3m > 0 ? r.prev3m.toFixed(4) : r.prev3m.toFixed(2)}`
                        : '--'}
                    </div>
                  </div>

                  {/* Col3: % change over 3-minutes */}
                  <div className={`w-[108px] pr-1.5 text-right align-top`}>
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap ${r.change3m != null && r.change3m < 0 ? 'text-pink' : 'text-[#C026D3]'}`}>
                      {typeof r.change3m === 'number' ? `${r.change3m > 0 ? '+' : ''}${formatPercentage(r.change3m)}` : 'N/A'}
                    </div>
                    {typeof r.peakCount === 'number' && r.peakCount > 0 && (
                      <div className="text-xs text-gray-400 leading-tight">Peak x{r.peakCount}</div>
                    )}
                    <div className="text-xs text-gray-400 leading-tight">3-min</div>
                  </div>

                  {/* Col4: Star (tight) */}
                  <div className="w-[28px] text-right">
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
                </div>
              </div>
            </a>
          </div>
        );
      })}
    </div>
  );
};

export default GainersTable;