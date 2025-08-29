import React from 'react';
import StarIcon from './StarIcon.jsx';
import { formatPrice, formatPercentage } from '../utils/formatters.js';

export default function UniformCard({
  symbol = 'N/A',
  price = 0,
  change = 0,
  rank = null,
  streak = 0,
  windowLabel = '',
  filled = false,
  onToggle = () => {}
}) {
  // Render a px/px2/px3 label if streak > 0
  let streakLabel = null;
  if (streak > 0) {
    streakLabel = (
      <span
        className="ml-1 px-1 py-0.5 rounded bg-purple text-xs text-white font-mono"
        style={{ fontSize: '11px', fontWeight: 600, verticalAlign: 'middle', opacity: 0.85 }}
        title={`On list ${streak} refresh${streak > 1 ? 'es' : ''}`}
      >{streak === 1 ? 'px' : `px${streak}`}</span>
    );
  }
  return (
    <div className="relative group">
      <a href={`https://www.coinbase.com/advanced-trade/spot/${String(symbol).toLowerCase()}-usd`} target="_blank" rel="noopener noreferrer" className="block">
        <div className={`table-card flex items-center justify-between`} style={{ boxShadow: '0 2px 12px 0 rgba(129,9,150,0.06)' }}>
          <div className="flex items-center gap-4">
            <div className="flex items-center flex-col justify-center">
              <div className="text-xs text-gray-400 numeric">{rank ?? ''}</div>
              {/* peak/showPeak removed */}
            </div>

            <div className="flex-1 flex items-center gap-3">
              <span className="font-bold text-white text-lg tracking-wide">{symbol}</span>
              {streakLabel}
            </div>
          </div>

          <div className="flex flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto">
            <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px]">
              <span className="text-base sm:text-lg md:text-xl font-bold text-teal numeric">{formatPrice(price)}</span>
              {windowLabel ? <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">{windowLabel}</span> : null}
            </div>

            <div className={`flex flex-col items-end min-w-[56px] sm:min-w-[60px]`}>
                <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${Number(change) >= 0 ? 'text-purple' : 'text-red-400'}`}>
                  <span className="numeric">{Number.isFinite(Number(change)) ? `${Number(change) > 0 ? '+' : ''}${formatPercentage(change)}` : 'N/A'}</span>
                </div>
            </div>

            <StarIcon
              filled={filled}
              symbol={symbol}
              onToggled={(nextFilled) => {
                onToggle(symbol, price);
              }}
            />
          </div>
        </div>
      </a>
    </div>
  );
}
