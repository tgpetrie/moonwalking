import React, { useMemo, useState, useCallback } from 'react';
import { useGainersLosersData } from '../hooks/useGainersLosersData';
import SharedMoverRow from './SharedMoverRow.jsx';
import StatusNote from './StatusNote.jsx';

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
  const handleStarFeedback = useCallback((symbol) => {
    setPopStar(symbol);
    setTimeout(() => setPopStar(null), 350);
  }, []);

  // Do NOT unconditionally add `table-card` here — parent containers (e.g. app.jsx) already wrap the component.
  const wrapperClasses = `block w-full overflow-x-auto ${className}`.trim();

  const content = useMemo(() => {
    const wrapStatus = (node) => (
      <div className={wrapperClasses}>
        <div className="min-h-[180px] flex items-center justify-center">
          {node}
        </div>
      </div>
    );
    const noRows = !rows || rows.length === 0;

    if (error) {
      return wrapStatus(<StatusNote state="error" />);
    }

    if (loading && noRows) {
      return wrapStatus(<StatusNote state="loading" />);
    }

    if (!loading && noRows) {
      return wrapStatus(<StatusNote state="empty" message={`No ${String(window)} ${String(resolvedVariant).toLowerCase()} data available`} />);
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
            let changeNum = null;
            if (typeof changeRaw === 'number') changeNum = changeRaw;
            else if (changeRaw != null && Number.isFinite(parseFloat(changeRaw))) changeNum = parseFloat(changeRaw);
            const displayRank = typeof r.rank === 'number' ? r.rank : idx + 1;
            // compute previous price similar to 1-min table: prefer server-provided initial price, else derive from pct
            let prevPrice = null;
            if (r && typeof r.initial_price_3min === 'number') {
              prevPrice = r.initial_price_3min;
            } else if (r && typeof price === 'number' && typeof changeNum === 'number' && changeNum !== 0) {
              prevPrice = price / (1 + changeNum / 100);
            }
            const coinbaseUrl = r.symbol ? `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD` : '#';
            const handleInfoClick = (event) => {
              event.preventDefault();
              event.stopPropagation();
              if (typeof onSelectCoin === 'function' && r.symbol) {
                onSelectCoin(r.symbol);
              }
            };
            // kept for parity with former MoverTable styling if needed later

            return (
              <div key={r.symbol || displayRank} className="px-0 py-1 mb-1">
                <a
                  href={coinbaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block group"
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

                    <SharedMoverRow
                      row={{ ...r, price, prevPrice, change: changeNum }}
                      rank={displayRank}
                      isGainer={isGainer}
                      streakCount={r.peakCount || 0}
                      badgeActive={popStar === (r && r.symbol)}
                      onStarToggle={(activeSymbol) => handleStarFeedback(activeSymbol, r && r.symbol)}
                      onInfoClick={() => handleInfoClick(r && r.symbol)}
                    />
                  </div>
                </a>
              </div>
            );
          })}

          {!loading && !error && isThreeMin && Array.isArray(rows) && rows.length > baseLimit && (
            <div className="w-full mt-3 flex justify-center">
              {(() => {
                const count = Array.isArray(rows) ? rows.length : 0;
                const label = localExpanded ? 'Show Less' : `Show more (${Math.min(expandLimit, count)} max)`;
                return (
                  <button
                    type="button"
                    onClick={() => setLocalExpanded((s) => !s)}
                    className="text-sm font-medium text-slate-200 bg-white/5 hover:bg-white/10 px-3 py-1 rounded-md"
                    aria-expanded={localExpanded}
                  >
                    {label}
                  </button>
                );
              })()}
            </div>
          )}
        </div>
      </div>
    );

  }, [rows, loading, error, wrapperClasses, resolvedVariant, onSelectCoin, localExpanded, variant, window, popStar, handleStarFeedback]);

  return content;
}
