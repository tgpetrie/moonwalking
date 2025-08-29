import React from 'react';
import { formatPrice, formatPercentage } from '../utils/formatters.js';

// Reusable amount renderer for currency and percentage values.
// Props:
// - value: number
// - type: 'currency' | 'percent' | 'auto' (auto infers by value sign/usage)
// - className: extra classes for the wrapper
export default function Amount({ value, type = 'auto', className = '' }) {
  const isNumber = typeof value === 'number' && Number.isFinite(value);
  const t = type === 'auto' ? (String(value).includes('%') ? 'percent' : 'currency') : type;

  if (t === 'percent') {
    const formatted = isNumber ? formatPercentage(value) : (String(value) || 'N/A');
    // split number and trailing % for separate styling
    const endsWithPct = formatted.endsWith('%');
    const num = endsWithPct ? formatted.slice(0, -1) : formatted;
    return (
      <span className={`rubik-amount ${className}`.trim()} data-amount-type="percent">
        <span className="rubik-number">{num}</span>
        {endsWithPct && <span className="rubik-symbol">%</span>}
      </span>
    );
  }

  // currency
  const formatted = isNumber ? formatPrice(value) : (String(value) || 'N/A');
  const startsWithDollar = formatted.startsWith('$');
  const num = startsWithDollar ? formatted.slice(1) : formatted;
  return (
    <span className={`rubik-amount ${className}`.trim()} data-amount-type="currency">
      {startsWithDollar && <span className="rubik-symbol">$</span>}
      <span className="rubik-number">{num}</span>
    </span>
  );
}
