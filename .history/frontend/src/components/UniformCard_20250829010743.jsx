import React from 'react';
import StarIcon from './StarIcon.jsx';
import { formatPrice, formatPercentage } from '../utils/formatters.js';

export default function UniformCard({
  symbol = 'N/A',
  price = 0,
  change = 0,
  rank = null,
  peak = 0,
  showPeak = false,
  windowLabel = '',
  filled = false,
  onToggle = () => {},
  percentClassName = ''
}) {
  return (
    <div className="relative group">
      <a href={`https://www.coinbase.com/advanced-trade/spot/${String(symbol).toLowerCase()}-usd`} target="_blank" rel="noopener noreferrer" className="block">
        <div className={`table-card flex items-center justify-between`} style={{ boxShadow: '0 2px 12px 0 rgba(129,9,150,0.06)' }}>
          <div className="flex items-center gap-4">
            <div className="flex items-center flex-col justify-center">
              <div className="text-xs text-gray-400 numeric">{rank ?? ''}</div>
              {showPeak ? (
                <div className="mt-1" style={{ height: '6px' }}>
                  <div style={{ width: `${peak}px`, height: '6px', background: '#810996', borderRadius: 2, opacity: 0.9 }} />
                </div>
              ) : null}
            </div>

            <div className="flex-1 flex items-center gap-3">
              <span className="font-bold text-white text-lg tracking-wide">{symbol}</span>
            </div>
          </div>

          <div className="flex flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto">
            <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px]">
              <span className="text-base sm:text-lg md:text-xl font-bold text-teal numeric">{formatPrice(price)}</span>
              {windowLabel ? <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">{windowLabel}</span> : null}
            </div>

            <div className={`flex flex-col items-end min-w-[56px] sm:min-w-[60px]`}>
                <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${Number(change) >= 0 ? 'text-purple' : 'text-red-400'} ${percentClassName}`}>
                  <span className="numeric">{Number.isFinite(Number(change)) ? `${Number(change) > 0 ? '+' : ''}${formatPercentage(change)}` : 'N/A'}</span>
                </div>
            </div>

            <button onClick={(e) => { e.preventDefault(); onToggle(symbol, price); }} className="bg-transparent border-none p-0 m-0 cursor-pointer" aria-label={filled ? `Remove ${symbol} from watchlist` : `Add ${symbol} to watchlist`}>
              <StarIcon filled={filled} />
            </button>
          </div>
        </div>
      </a>
    </div>
  );
}
