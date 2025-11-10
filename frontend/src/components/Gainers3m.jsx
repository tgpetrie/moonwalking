import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Gainers3m({ rows = [], loading, onInfo }) {
  return (
    <div className="flex flex-col gap-1">
      <header className="panel-head">
        <h2 className="section-head section-head-gain">3-MIN GAINERS</h2>
        <div className="section-head-line section-head-line-gain" />
      </header>
      {loading && <div className="panel-placeholder">Loading…</div>}
      {!loading &&
        rows.slice(0, 8).map((row, i) => (
          <TokenRow
            key={row.symbol || i}
            index={i}
            symbol={row.symbol}
            price={row.price}
            prevPrice={row.initial_price_3min}
            changePct={row.changePct}
            side="gain"
            onInfo={onInfo}
          />
        ))}
    </div>
  );
}
