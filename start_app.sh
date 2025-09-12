import React, { useMemo, useState } from 'react';
import { formatNumber, formatPct } from '../lib/formatters';
import { useGainersLosersData } from '../hooks/useGainersLosersData';

/**
 * MoverTable
 * Always-visible table for gainers/losers with a given time window (e.g., 3min).
 * Ensures rows only highlight on hover for the specific row, not the whole table.
 * Replaces nested <button> elements with div + keyboard handler to avoid DOM warnings.
 */
export default function MoverTable({ variant = 'gainers', window = '3min', className = '' }) {
  const { rows, loading, error } = useGainersLosersData({ variant, window });

  const wrapperClasses = `block w-full overflow-x-auto ${className}`.trim();

  const [focusedRow, setFocusedRow] = useState(null);

  if (error) {
    return (
      <div className={wrapperClasses}>
        <div className="text-red-400 text-sm">Failed to load {variant} ({window})</div>
      </div>
    );
  }

  if (loading && (!rows || rows.length === 0)) {
    return (
      <div className={wrapperClasses}>
        <div className="text-slate-400 text-sm">Loading {variant} ({window})…</div>
      </div>
    );
  }

  const content = useMemo(() => {
    return (
      <div className={wrapperClasses}>
        <table className="w-full table-fixed border-separate border-spacing-0">
          <thead>
            <tr className="text-xs text-slate-300">
              <th className="text-left px-2 py-2 w-[28%]">Symbol</th>
              <th className="text-right px-2 py-2 hidden sm:table-cell w-[18%]">Price</th>
              <th className="text-right px-2 py-2 hidden md:table-cell w-[26%]">Vol (24h)</th>
              <th className="text-right px-2 py-2 w-[18%]">Δ {window}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, index) => (
              <tr
                key={r.symbol}
                className={`mover-row transition-colors ${
                  focusedRow === index ? 'bg-slate-700' : ''
                }`}
                tabIndex={0}
                onFocus={() => setFocusedRow(index)}
                onBlur={() => setFocusedRow(null)}
              >
                <td className="px-2 py-2">{r.symbol}</td>
                <td className="px-2 py-2 text-right hidden sm:table-cell">{formatNumber(r.price)}</td>
                <td className="px-2 py-2 text-right hidden md:table-cell">{formatNumber(r.volume_24h)}</td>
                <td
                  className={`px-2 py-2 text-right ${
                    r.change >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {formatPct(r.change)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }, [rows, loading, error, variant, window, wrapperClasses, focusedRow]);

  return content;
}
