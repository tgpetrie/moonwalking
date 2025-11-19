// src/components/Losers3m.jsx
import React, { useState } from "react";
import TokenRow from "./TokenRow.jsx";

export default function Losers3m({
  rows = [],
  loading = false,
  onInfo = () => {},
  showTitle = true,
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const MAX_BASE = 8;
  const MAX_EXPANDED = 16;
  const allRows = Array.isArray(rows) ? rows : [];

  const losers = React.useMemo(() => {
    return allRows
      .map((row) => {
        const key = "price_change_percentage_3min";
        const raw =
          row?.[key] ??
          row?.gain ??
          0;
        const num = Number(raw);
        const pct = Number.isFinite(num) ? num : 0;
        return { ...row, pct, _pct: pct };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct < 0)
      .sort((a, b) => a._pct - b._pct);
  }, [allRows]);

  const count = losers.length;
  const visible = isExpanded ? losers.slice(0, MAX_EXPANDED) : losers.slice(0, MAX_BASE);
  const renderHeader = () => {
    if (!showTitle) return null;
    return (
      <div className="panel-header panel-header-3m panel-header-3m-losers">
        <div className="panel-header-main">
          <span className="panel-kicker">Top Losers</span>
          <span className="panel-timeframe">(3m)</span>
        </div>
      </div>
    );
  };

  return (
    <div className="panel panel-3m">
      {renderHeader()}
      <div className="panel-body">
        {loading ? (
          <div className="panel-empty">Loading…</div>
        ) : count === 0 ? (
          <div className="panel-empty">No data.</div>
        ) : (
          visible.map((row, idx) => {
            const key = "price_change_percentage_3min";
            const forced = -Math.abs(row.pct ?? row._pct ?? 0);
            const cloned = { ...row, [key]: forced };

            return (
              <TokenRow
                key={row.symbol || idx}
                rank={cloned.rank ?? idx + 1}
                symbol={cloned.symbol}
                currentPrice={cloned.current_price}
                previousPrice={cloned.initial_price_3min}
                changePct={cloned[key]}
                rowType="loser"
                onInfo={onInfo}
              />
            );
          })
        )}

        {count > MAX_BASE && (
          <div className="panel-footer">
            <div className="panel-show-more">
              <button
                className="btn-show-more"
                aria-expanded={isExpanded}
                aria-controls="losers-3m-list"
                onClick={() => setIsExpanded((s) => !s)}
              >
                {isExpanded ? "Show Less" : "Show More"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
