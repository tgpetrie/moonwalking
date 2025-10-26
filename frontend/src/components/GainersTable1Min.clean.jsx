import React from 'react';
import PropTypes from 'prop-types';
import { FiInfo } from 'react-icons/fi';
import WatchStar from './WatchStar.jsx';
import StatusNote from './StatusNote.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import { colorForSentiment } from '../lib/sentiment';

// Clean, presentational 1‑min gainers table. Replaces corrupted implementation.
export default function GainersTable1Min({
  rows = [],
  startRank,
  endRank,
  loading = false,
  error = null,
  seeded = false,
  allowEmpty = false,
  onSelectCoin,
  onOpenSymbol,
  compact = false,
}) {
  const normalized = Array.isArray(rows)
    ? rows.map((it, i) => ({
        rank: it?.rank ?? (typeof startRank === 'number' ? startRank + i : i + 1),
        symbol: String(it?.symbol || it?.pair || it?.product_id || '').replace(/-USD$/i, ''),
        price: typeof it?.price === 'number' ? it.price : (typeof it?.current_price === 'number' ? it.current_price : null),
        change: typeof it?.change === 'number' ? it.change : (typeof it?.peak_gain === 'number' ? it.peak_gain : (typeof it?.price_change_percentage_1min === 'number' ? it.price_change_percentage_1min : null)),
        peakCount: typeof it?.peakCount === 'number' ? it.peakCount : (typeof it?.peak_count === 'number' ? it.peak_count : (typeof it?.trend_streak === 'number' ? it.trend_streak : 0)),
      }))
    : [];

  const sliced = normalized; // already constrained by parent

  // Pad with placeholders to keep columns visually aligned (4 rows minimum per column in most layouts)
  const minRows = allowEmpty ? Math.max(4, sliced.length) : sliced.length;
  const displayRows = Array.from({ length: minRows }, (_, i) => sliced[i] ?? null);

  if (loading && sliced.length === 0) {
    return <StatusNote state="loading" />;
  }

  if (!loading && error && sliced.length === 0 && !allowEmpty) {
    return <StatusNote state="error" />;
  }

  if (!loading && !error && sliced.length === 0 && !allowEmpty) {
    return <StatusNote state="empty" message="No 1-min data available" />;
  }

  return (
    <div className="relative w-full h-full min-h-[320px] px-0 transition-all duration-300">
      {seeded && (
        <span className="absolute top-1 right-1 text-[10px] px-1.5 py-0.5 rounded bg-purple-700/70 text-white font-bold tracking-wide">DEV</span>
      )}

      {displayRows.map((item, idx) => {
        const isPlaceholder = !item;
        const pct = item?.change ?? 0;
        const prevPrice = item && typeof item.price === 'number' && typeof pct === 'number' && pct !== 0
          ? item.price / (1 + pct / 100)
          : null;
        const sentimentClass = item ? colorForSentiment(item) : '';
        const coinbaseUrl = item?.symbol ? `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD` : '#';

        return (
          <div key={item ? item.symbol : `placeholder-${idx}`} className="px-0 py-1 mb-1">
            <a
              href={coinbaseUrl}
              onClick={(e) => { if (isPlaceholder) e.preventDefault(); }}
              target={isPlaceholder ? undefined : '_blank'}
              rel={isPlaceholder ? undefined : 'noopener noreferrer'}
              className="block group"
            >
              <div className="relative overflow-hidden rounded-xl p-4 h-[96px] bg-white/5 hover:bg-white/10 transition-colors">
                <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                  {/* Col1: rank + symbol + streak */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className={"flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0 " + (isPlaceholder ? 'opacity-0' : '')}>
                      {item ? item.rank : 0}
                    </div>
                    <div className={"min-w-0 flex items-center gap-2 sm:gap-3 " + (isPlaceholder ? 'opacity-0' : '')}>
                      <span className="font-bold text-white text-lg tracking-wide truncate">{item ? truncateSymbol(item.symbol, 6) : '—'}</span>
                      {item && item.peakCount > 1 && (
                        <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
                          {Array.from({ length: Math.min(3, item.peakCount) }).map((_, i) => (
                            <span key={`streak-${idx}-${i}`} className="w-1.5 h-1.5 rounded-full bg-[#C026D3]" />
                          ))}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Col2: prices */}
                  <div className={"w-[152px] pr-6 text-right " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                    </div>
                    <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                      {prevPrice != null ? formatPrice(prevPrice) : '--'}
                    </div>
                  </div>

                  {/* Col3: pct + peak + interval */}
                  <div className={"w-[108px] pr-1.5 text-right align-top " + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className={`text-base sm:text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${pct > 0 ? 'text-[#C026D3]' : 'text-pink'}`}>
                      {pct > 0 && '+'}{typeof pct === 'number' ? formatPercentage(pct) : '0.00%'}
                    </div>
                    <div className="text-xs text-gray-400 leading-tight">
                      {item && typeof item.peakCount === 'number' && item.peakCount > 0
                        ? `Peak x${item.peakCount}`
                        : <span className="opacity-0 select-none">Peak x0</span>}
                    </div>
                    <div className="text-xs text-gray-400 leading-tight">1‑min</div>
                  </div>

                  {/* Col4: star + info */}
                  <div className="w-[44px] text-right flex items-center justify-end gap-2">
                    <div className={isPlaceholder ? 'opacity-0' : ''}>
                      <WatchStar productId={item ? item.symbol : undefined} />
                    </div>
                    <div className={isPlaceholder ? 'opacity-0' : ''}>
                      <button
                        type="button"
                        onClick={(e) => {
                          if (isPlaceholder) { e.preventDefault(); return; }
                          e.preventDefault(); e.stopPropagation();
                          const sym = item && item.symbol;
                          if (typeof onSelectCoin === 'function') onSelectCoin(sym);
                          if (typeof onOpenSymbol === 'function') onOpenSymbol(sym, { initialTab: 'social' });
                        }}
                        aria-label="Open sentiment panel"
                        className="flex items-center justify-center w-6 h-6 transition focus:outline-none focus:ring-1 focus:ring-purple-500/60"
                      >
                        <FiInfo className={`w-4 h-4 ${sentimentClass}`} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </a>
          </div>
        );
      })}
    </div>
  );
}

GainersTable1Min.propTypes = {
  rows: PropTypes.array,
  startRank: PropTypes.number,
  endRank: PropTypes.number,
  loading: PropTypes.bool,
  error: PropTypes.any,
  seeded: PropTypes.bool,
  allowEmpty: PropTypes.bool,
  onSelectCoin: PropTypes.func,
  onOpenSymbol: PropTypes.func,
  compact: PropTypes.bool,
};
