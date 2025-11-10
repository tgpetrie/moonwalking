import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Losers3m({ rows = [], loading, onInfo }) {
  return (
    <div className="flex flex-col gap-1">
      <header className="panel-head">
        <h2 className="section-head section-head-loss">3-MIN LOSERS</h2>
        <div className="section-head-line section-head-line-loss" />
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
            side="loss"
            onInfo={onInfo}
          />
        ))}
    </div>
  );
}
