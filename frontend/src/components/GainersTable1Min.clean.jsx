import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { FiInfo } from 'react-icons/fi';
import WatchStar from './WatchStar.jsx';
import StatusNote from './StatusNote.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import { colorForSentiment } from '../lib/sentiment';
import SentimentCard from './cards/SentimentCard.jsx';

/**
 * Finalized 1‑minute Gainers table (top‑8 collapsed → parent controls total).
 * - Single floating SentimentCard anchored to the clicked info icon (ⓘ)
 * - BHABIT color semantics: positive = gold (#f1b43a), negative = purple (#ae4bf5)
 * - Raleway-only typography (global), no Fragment Mono
 * - Click row → opens Coinbase advanced spot in a new tab
 */
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
  // Sentiment card state (single floating card anchored to the clicked row's info button)
  const [infoOpen, setInfoOpen] = useState(false);
  const [infoSymbol, setInfoSymbol] = useState(null);
  const [anchorRect, setAnchorRect] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [infoData, setInfoData] = useState({});

  const closeInfo = () => {
    setInfoOpen(false);
    setInfoSymbol(null);
    setActiveTab('overview');
    setAnchorRect(null);
    setInfoData({});
  };

  const pctColorClass = (pct) => {
    if (typeof pct !== 'number') return '';
    if (pct > 0) return 'text-[#f1b43a]';     // BHABIT gold for positive
    if (pct < 0) return 'text-[#ae4bf5]';     // BHABIT purple for negative
    return 'text-gray-300';
  };

  // Normalize inbound rows to a single canonical shape the UI expects
  const normalized = Array.isArray(rows)
    ? rows.map((it, i) => ({
        rank: it?.rank ?? (typeof startRank === 'number' ? startRank + i : i + 1),
        symbol: String(it?.symbol || it?.pair || it?.product_id || '').replace(/-USD$/i, ''),
        price: typeof it?.price === 'number'
          ? it.price
          : (typeof it?.current_price === 'number' ? it.current_price : null),
        change: typeof it?.change === 'number'
          ? it.change
          : (typeof it?.peak_gain === 'number'
              ? it.peak_gain
              : (typeof it?.price_change_percentage_1min === 'number'
                  ? it.price_change_percentage_1min
                  : null)),
        peakCount: typeof it?.peakCount === 'number'
          ? it.peakCount
          : (typeof it?.peak_count === 'number'
              ? it.peak_count
              : (typeof it?.trend_streak === 'number' ? it.trend_streak : 0)),
        changePct3m: typeof it?.price_change_percentage_3min === 'number' ? it.price_change_percentage_3min : null,
        changePct1h: typeof it?.price_change_percentage_1h === 'number' ? it.price_change_percentage_1h : null,
        volume1h: typeof it?.volume_1h === 'number' ? it.volume_1h : null,
      }))
    : [];

  const sliced = normalized; // already constrained by parent

  // Keep columns aligned — pad with placeholders if needed
  const minRows = allowEmpty ? Math.max(4, sliced.length) : sliced.length;
  const displayRows = Array.from({ length: minRows }, (_, i) => sliced[i] ?? null);

  if (loading && sliced.length === 0) {
    return <StatusNote state="loading" />;
  }
  if (!loading && error && sliced.length === 0 && !allowEmpty) {
    return <StatusNote state="error" />;
  }
  if (!loading && !error && sliced.length === 0 && !allowEmpty) {
    return <StatusNote state="empty" message="No 1‑min data available" />;
  }

  return (
    <div className="relative w-full h-full min-h-[320px] px-0 transition-all duration-300">
      {seeded && (
        <span className="absolute top-1 right-1 text-[10px] px-1.5 py-0.5 rounded bg-purple-700/70 text-white font-bold tracking-wide">seeded (dev)</span>
      )}

      {displayRows.map((item, idx) => {
        const isPlaceholder = !item;
        const pct = item?.change ?? 0;
        const prevPrice = item && Number.isFinite(item.price) && typeof pct === 'number' && pct !== 0
          ? item.price / (1 + pct / 100)
          : null;
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
              <div
                className={[
                  'relative overflow-hidden rounded-xl p-4 h-[96px] transition-colors',
                  'bg-white/5 hover:bg-white/10',
                ].join(' ')}
              >
                <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                  {/* Col1: rank + symbol + streak */}
                  <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                    <div className={'flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0 ' + (isPlaceholder ? 'opacity-0' : '')}>
                      {item ? item.rank : 0}
                    </div>
                    <div className={'min-w-0 flex items-center gap-2 sm:gap-3 ' + (isPlaceholder ? 'opacity-0' : '')}>
                      <span className="font-bold text-white text-lg tracking-wide truncate">{item ? truncateSymbol(item.symbol, 6) : '—'}</span>
                      {item && item.peakCount > 1 && (
                        <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
                          {Array.from({ length: Math.min(3, item.peakCount) }).map((_, i2) => (
                            <span key={`streak-${idx}-${i2}`} className="w-1.5 h-1.5 rounded-full bg-[#C026D3]" />
                          ))}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Col2: prices */}
                  <div className={'w-[152px] pr-6 text-right ' + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className="text-base sm:text-lg md:text-xl font-bold text-teal tabular-nums leading-none whitespace-nowrap">
                      {item && Number.isFinite(item.price) ? formatPrice(item.price) : '0.00'}
                    </div>
                    <div className="text-sm leading-tight text-gray-300 tabular-nums whitespace-nowrap">
                      {prevPrice != null ? formatPrice(prevPrice) : '--'}
                    </div>
                  </div>

                  {/* Col3: pct + peak + interval */}
                  <div className={'w-[108px] pr-1.5 text-right align-top ' + (isPlaceholder ? 'opacity-0' : '')}>
                    <div className={`text-base sm:text-lg md:text-xl font-bold tabular-nums leading-none whitespace-nowrap ${pctColorClass(pct)}`}>
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
                        ref={(el) => {
                          if (el && item) el.dataset.symbol = item.symbol || '';
                        }}
                        onClick={(e) => {
                          if (isPlaceholder) { e.preventDefault(); return; }
                          e.preventDefault(); e.stopPropagation();
                          const target = e.currentTarget;
                          const rect = target.getBoundingClientRect();
                          setAnchorRect(rect);
                          const sym = item?.symbol;
                          setInfoSymbol(sym || null);
                          setActiveTab('overview');

                          // Build data for the card from the row (no backend call needed)
                          setInfoData({
                            priceNow: item?.price ?? null,
                            pricePrev: prevPrice ?? null,
                            changePct1m: typeof item?.change === 'number' ? item.change : null,
                            changePct3m: typeof item?.changePct3m === 'number' ? item.changePct3m : null,
                            changePct1h: typeof item?.changePct1h === 'number' ? item.changePct1h : null,
                            volume1h: typeof item?.volume1h === 'number' ? item.volume1h : null,
                          });

                          setInfoOpen(true);

                          // preserve optional external handlers
                          if (typeof onSelectCoin === 'function') onSelectCoin(sym);
                          if (typeof onOpenSymbol === 'function') onOpenSymbol(sym, { initialTab: 'overview' });
                        }}
                        aria-label="Open sentiment panel"
                        className="flex items-center justify-center w-6 h-6 transition focus:outline-none focus:ring-1 focus:ring-purple-500/60 text-[#ae4bf5]"
                        title="More info"
                      >
                        <FiInfo className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </a>
          </div>
        );
      })}

      {infoOpen && (
        <SentimentCard
          symbol={infoSymbol}
          sentiment={
            typeof infoData?.changePct1m === 'number'
              ? (infoData.changePct1m > 0 ? 'positive' : (infoData.changePct1m < 0 ? 'negative' : 'neutral'))
              : 'neutral'
          }
          anchorRect={anchorRect}
          onClose={closeInfo}
          activeTab={activeTab}
          onTab={setActiveTab}
          data={infoData}
        />
      )}
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
