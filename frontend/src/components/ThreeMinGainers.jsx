// src/components/ThreeMinGainers.jsx
import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function ThreeMinGainers({
  rows = [],
  loading = false,
  onInfo = () => {},
  showTitle = true,
}) {
  return (
    <div className="panel">
      {showTitle && <div className="panel-title">3-MINUTE GAINERS</div>}
      <div className="panel-body">
        {loading ? (
          <div className="panel-empty">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="panel-empty">No data.</div>
        ) : (
          rows.map((row, idx) => (
            <TokenRow key={row.symbol || idx} index={idx} row={row} onInfo={onInfo} />
          ))
        )}
      </div>
    </div>
  );
}
