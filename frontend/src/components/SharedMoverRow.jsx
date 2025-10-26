import React from 'react';
import PropTypes from 'prop-types';
import { FiInfo } from 'react-icons/fi';
import WatchStar from './WatchStar.jsx';
import { colorForSentiment } from '../lib/sentiment';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';

export default function SharedMoverRow({
  row,
  rank,
  isGainer = true,
  streakCount = 0,
  badgeActive = false,
  onStarToggle = () => {},
  onInfoClick = () => {},
  onSelectCoin = () => {},
}) {
  const positive = Number.isFinite(Number(row.change || row.price_change_percentage_1min || row.change3m)) && (Number(row.change || row.price_change_percentage_1min || row.change3m) >= 0);
  let prevPrice = null;
  if (Number.isFinite(row.prevPrice)) prevPrice = row.prevPrice;
  else if (Number.isFinite(row.initial_price_1min)) prevPrice = row.initial_price_1min;
  const rankBg = isGainer ? 'rgba(254,164,0,0.28)' : 'rgba(138,43,226,0.28)';
  const dotColor = isGainer ? '#C026D3' : '#8A2BE2';

  // Normalize streakCount: allow either number or {level, minutes}
  const streakNum = (() => {
    if (streakCount && typeof streakCount === 'object') {
      return Number(streakCount.level || streakCount.minutes || 0);
    }
    return Number(streakCount || 0);
  })();

  const handleInfo = (e) => {
    e.preventDefault();
    e.stopPropagation();
    onInfoClick(row.symbol);
  };

  return (
    <div className="grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-center">
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm shrink-0" style={{ background: rankBg, color: 'var(--pos)' }}>
          {rank}
        </div>
        <div className="min-w-0 flex items-center gap-3">
          <span className="font-headline font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(row.symbol, 6)}</span>
          {streakNum > 1 && (
            <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
              {Array.from({ length: Math.min(3, streakNum) }).map((_, dotIdx) => (
                <span key={`dot-${row.symbol}-${dotIdx}`} className="w-1.5 h-1.5 rounded-full" style={{ background: dotColor }} />
              ))}
            </span>
          )}
        </div>
      </div>

      <div className="w-[152px] pr-6 text-right">
        <div className="text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
          {Number.isFinite(row.price) ? formatPrice(row.price) : '—'}
        </div>
        <div className="text-sm leading-tight text-white/80 font-mono tabular-nums whitespace-nowrap">
          {prevPrice != null ? formatPrice(prevPrice) : '--'}
        </div>
      </div>

      <div className="w-[108px] pr-1.5 text-right align-top">
        <div className={`text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${positive ? 'text-orange' : 'text-neg'}`}>
          {positive && '+'}{formatPercentage(Number(row.change ?? row.price_change_percentage_1min ?? row.change3m ?? 0))}
        </div>
      </div>

  <div className="w-[28px] flex flex-col items-end gap-1">
        <WatchStar
          productId={row.symbol}
          className={badgeActive ? 'animate-star-pop' : ''}
          onToggled={(active) => onStarToggle(active ? row.symbol : null)}
        />
        <button
          type="button"
          onClick={handleInfo}
          className="flex items-center justify-center w-6 h-6 transition focus:outline-none focus:ring-1 focus:ring-purple-500/60"
          aria-label={`Open sentiment panel`}
        >
          <FiInfo className={`w-4 h-4 ${colorForSentiment(row)}`} />
        </button>
      </div>
    </div>
  );
}

SharedMoverRow.propTypes = {
  row: PropTypes.object.isRequired,
  rank: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  isGainer: PropTypes.bool,
  streakCount: PropTypes.oneOfType([PropTypes.number, PropTypes.object]),
  badgeActive: PropTypes.bool,
  onStarToggle: PropTypes.func,
  onInfoClick: PropTypes.func,
  onSelectCoin: PropTypes.func,
};
