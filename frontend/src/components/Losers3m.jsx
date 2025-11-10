import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Losers3m({ rows = [], loading = false, onInfo }) {
  return (
    <section className="w-full panel-shell">
      <div className="text-center">
        <h2 className="section-title-purple">3-MIN LOSERS</h2>
        <div className="section-underline-purple"></div>
      </div>

      <div className="panel-3m">
        {loading && <div className="panel-3m-empty">Loading…</div>}

        {!loading && rows.length === 0 && (
          <div className="panel-3m-empty">No 3-min losers.</div>
        )}

        {!loading &&
          rows.length > 0 &&
          rows.slice(0, 8).map((row, i) => (
            <TokenRow
              key={row.symbol || i}
              index={i + 1}
              symbol={row.symbol}
              price={row.current_price}
              prevPrice={row.initial_price_3min}
              changePct={row.price_change_percentage_3min}
              side="loss"
              onInfo={onInfo}
            />
          ))}
      </div>
    </section>
  );
}
