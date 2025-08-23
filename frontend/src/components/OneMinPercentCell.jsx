import React from 'react';
import { formatPercentage } from '../utils/formatters.js';

export default function OneMinPercentCell({ value, peak, interval = '1-min', className = '' }) {
  const formatted = (typeof value === 'number' && Number.isFinite(value)) ? formatPercentage(value) : 'N/A';
  const positive = typeof value === 'number' && value > 0;

  const peakCount = typeof peak === 'number' ? Math.floor(Math.max(0, peak)) : 0;
  const peakLabel = peakCount <= 1 ? 'x' : `x${peakCount}`;

  return (
    <div className={`pct num ${className}`}>
      <div className={`text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap ${positive ? 'text-pct-positive' : 'text-pct-negative'}`}>
        {positive && '+'}{formatted}
      </div>
      {peakCount > 0 && (
        <span className="badge-peak badge-peak--compact" aria-hidden>{peakLabel}</span>
      )}
      <div className="text-xs text-gray-400 leading-tight">{interval}</div>
    </div>
  );
}
