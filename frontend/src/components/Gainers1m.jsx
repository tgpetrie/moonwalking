import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Gainers1m({ rows = [], loading, onInfo }) {
  return (
    <section className="one-min-shell">
      <header className="panel-head">
        <h2 className="section-head section-head-gain">1-MIN GAINERS</h2>
        <div className="section-head-line section-head-line-gain" />
      </header>
      <div className="one-min-grid">
        {[0, 1].map((col) => (
          <div key={col} className="panel-3m flex flex-col gap-1">
            {loading && <div className="panel-placeholder">Loading…</div>}
            {!loading &&
              rows
                .filter((_, i) => i % 2 === col)
                .slice(0, 4)
                .map((row, i) => (
                  <TokenRow
                    key={row.symbol || i}
                    index={i}
                    symbol={row.symbol}
                    price={row.price}
                    prevPrice={row.initial_price_1min}
                    changePct={row.changePct}
                    side="gain"
                    onInfo={onInfo}
                  />
                ))}
          </div>
        ))}
      </div>
    </section>
  );
}
