// src/components/Losers3m.jsx
import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Losers3m({
  rows = [],
  loading = false,
  onInfo = () => {},
  showTitle = true,
}) {
  return (
    <div className="panel">
      {showTitle && <div className="panel-title">3-MINUTE LOSERS</div>}
      <div className="panel-body">
        {loading ? (
          <div className="panel-empty">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="panel-empty">No data.</div>
        ) : (
          rows.map((row, idx) => (
            <TokenRow key={row.symbol || idx} index={idx} rank={idx + 1} row={row} changeKey="price_change_percentage_3min" onInfo={onInfo} />
          ))
        )}
      </div>
    </div>
  );
}
