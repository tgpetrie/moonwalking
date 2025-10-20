import React, { useMemo, useState } from 'react';
import { formatNumber } from '../utils/formatNumber';
import { formatPrice, formatPercentage, truncateSymbol } from '../utils/formatters';
import { useGainersLosersData } from '../hooks/useGainersLosersData';
import WatchStar from './WatchStar.jsx';

/**
 * MoverTable
 * Always-visible table for gainers/losers with a given time window (e.g., 3min).
 * Ensures rows only highlight on hover for the specific row, not the whole table.
 */
export default function MoverTable({ variant, tone, window = '3min', className = '', initialRows, maxRows, expanded, onSelectCoin }) {
  // Accept either `variant` ('gainers'|'losers') or `tone` ('gainer'|'loser'|'gainers'|'losers')
  const resolvedVariant = (variant && String(variant)) || (tone && String(tone)) || 'gainers';
  // Normalize to plural form expected by the data hook
  const normalizedVariant = resolvedVariant.toLowerCase().endsWith('s') ? resolvedVariant.toLowerCase() : `${resolvedVariant.toLowerCase()}s`;

  const { rows, loading, error } = useGainersLosersData({ variant: normalizedVariant, window });

  // Always start collapsed; ignore parent props by default
  const [localExpanded, setLocalExpanded] = useState(false);
  // lightweight pop feedback for star toggles to mirror GainersTable1Min behavior
  const [popStar, setPopStar] = useState(null);
  const handleStarFeedback = (active, symbol) => {
    setPopStar(symbol);
    setTimeout(() => setPopStar(null), 350);
  };

  // Do NOT unconditionally add `table-card` here — parent containers (e.g. app.jsx) already wrap the component.
  const wrapperClasses = `block w-full overflow-x-auto ${className}`.trim();

  const content = useMemo(() => {
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
          <div className="min-h-[180px] flex items-center justify-center">
            <div className="text-slate-400 text-sm">Loading ({String(window)})…</div>
          </div>
        </div>
      );
    }

    if (!loading && (!rows || rows.length === 0)) {
      return (
        <div className={wrapperClasses}>
          <div className="min-h-[180px] flex items-center justify-center">
            <div className="text-white/80 text-sm">No {String(window)} {String(resolvedVariant).toLowerCase()} data available</div>
          </div>
        </div>
      );
    }

    const toneName = resolvedVariant || 'gainers';
    const isGainer = String(toneName).toLowerCase().includes('gain');
    const accentGradient = isGainer
      ? 'radial-gradient(circle at 50% 50%, rgba(254,164,0,0.20) 0%, rgba(254,164,0,0.10) 45%, rgba(254,164,0,0.05) 70%, transparent 100%)'
      : 'radial-gradient(circle at 50% 50%, rgba(138,43,226,0.20) 0%, rgba(138,43,226,0.10) 45%, rgba(138,43,226,0.05) 70%, transparent 100%)';

    // Limit ONLY 3‑min tables: show top 7 by default, allow up to 13 on expand
    const isThreeMin = String(window).toLowerCase().includes('3');
    const baseLimit = 7;
    const expandLimit = 13;
    const allRows = Array.isArray(rows) ? rows : [];

    let visibleRows = allRows;
    if (isThreeMin) {
      if (localExpanded) {
        visibleRows = allRows.slice(0, expandLimit);
      } else {
        visibleRows = allRows.slice(0, baseLimit);
      }
    }

    return (
      <div className={wrapperClasses}>
        <div className="w-full h-full min-h-[300px] px-0 transition-all duration-300">
          {visibleRows.map((r, idx) => {
            const price = r.price ?? r.current ?? r.current_price ?? null;
            const changeRaw = r.change ?? r.change3m ?? r.changePct3m ?? r.price_change_percentage_3min ?? r.gain ?? r.gain3m ?? null;
            const changeNum = changeRaw == null ? null : (typeof changeRaw === 'number' ? changeRaw : (Number.isFinite(parseFloat(changeRaw)) ? parseFloat(changeRaw) : null));
            const isPositive = changeNum != null ? changeNum >= 0 : false;
            const displayRank = typeof r.rank === 'number' ? r.rank : idx + 1;
            // compute previous price similar to 1-min table: prefer server-provided initial price, else derive from pct
            let prevPrice = null;
            if (r && typeof r.initial_price_3min === 'number') {
              prevPrice = r.initial_price_3min;
            } else if (r && typeof price === 'number' && typeof changeNum === 'number' && changeNum !== 0) {
              prevPrice = price / (1 + changeNum / 100);
            }
            const coinbaseUrl = r.symbol ? `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD` : '#';

            return (
              <div key={r.symbol || displayRank} className="px-0 py-1 mb-1">
                <a
                  href={coinbaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`block group ${onSelectCoin ? 'cursor-pointer' : ''}`}
                  onClick={(e) => { if (onSelectCoin) { e.preventDefault(); onSelectCoin(r.symbol); } }}
                >
                  <div className="relative overflow-hidden rounded-xl p-4 h-[96px] hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform will-change-transform">
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                      style={{ background: accentGradient, top: '-15%', left: '-15%', position: 'absolute' }}
                    />
                  </span>

                  <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
                    <span className="block w-full h-full" style={{ background: isGainer ? 'radial-gradient(ellipse at 50% 140%, rgba(254,164,0,0.18) 0%, rgba(254,164,0,0.10) 35%, rgba(254,164,0,0.04) 60%, transparent 85%)' : 'radial-gradient(ellipse at 50% 140%, rgba(138,43,226,0.18) 0%, rgba(138,43,226,0.10) 35%, rgba(138,43,226,0.04) 60%, transparent 85%)' }} />
                  </span>

                  <div className="grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm shrink-0" style={{ background: isGainer ? 'rgba(254,164,0,0.28)' : 'rgba(138,43,226,0.28)', color: 'var(--pos)' }}>{displayRank}</div>
                      <div className="min-w-0 flex items-center gap-3">
                        <span className="font-headline font-bold text-white text-lg tracking-wide truncate">{r.symbol ? truncateSymbol(r.symbol, 6) : '—'}</span>
                        {r.peakCount > 1 && (
                          <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
                            {Array.from({ length: Math.min(3, r.peakCount) }).map((_, i) => (
                              <span key={`dot-${i}`} className="w-1.5 h-1.5 rounded-full" style={{ background: isGainer ? '#C026D3' : '#8A2BE2' }} />
                            ))}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="w-[152px] pr-6 text-right">
                      <div className="text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                        {price != null && Number.isFinite(price) ? formatPrice(price) : '—'}
                      </div>
                      <div className="text-sm leading-tight text-white/80 font-mono tabular-nums whitespace-nowrap">
                        {Number.isFinite(prevPrice) ? formatPrice(prevPrice) : '--'}
                      </div>
                    </div>

                    <div className="w-[108px] pr-1.5 text-right align-top">
                      <div className={`text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${changeNum != null ? (isPositive ? 'text-orange' : 'text-neg') : 'text-slate-400'}`}>
                        {changeNum != null && changeNum > 0 ? '+' : ''}{changeNum != null ? formatPercentage(changeNum) : '—'}
                      </div>
                      <div className={`text-xs text-gray-300 leading-tight ${localExpanded ? '' : 'opacity-0 select-none'}`} aria-hidden={!localExpanded}>
                        {/* Optional metric/subline when expanded (e.g., Px level) */}
                        {localExpanded ? (r.metric ?? r.px ?? null) : null}
                      </div>
                    </div>

                    <div className="w-[28px] text-right">
                      {!false && (
                        <WatchStar productId={r.symbol} className={popStar === (r && r.symbol) ? 'animate-star-pop' : ''} onToggled={handleStarFeedback} />
                      )}
                    </div>
                  </div>
                </div>
                </a>
              </div>
            );
          })}

          {!loading && !error && isThreeMin && Array.isArray(rows) && rows.length > baseLimit && (
            <div className="w-full mt-3 flex justify-center">
              <button
                type="button"
                onClick={() => setLocalExpanded((s) => !s)}
                className="text-sm font-medium text-slate-200 bg-white/5 hover:bg-white/10 px-3 py-1 rounded-md"
                aria-expanded={localExpanded}
              >
                {(() => {
                  const label = localExpanded ? 'Show less' : `Show more (${Math.min(expandLimit, (Array.isArray(rows) ? rows.length : 0))} max)`;
                  return label;
                })()}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }, [rows, loading, error, wrapperClasses, resolvedVariant, onSelectCoin, localExpanded, maxRows, variant, window, popStar, handleStarFeedback]);

  return content;
}
