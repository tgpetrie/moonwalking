import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Gainers3m({ rows = [], loading, onInfo }) {
  return (
    <section className="w-full panel-shell">
      <div className="text-center">
        <h2 className="section-title-gold">3-MIN GAINERS</h2>
        <div className="section-underline-gold"></div>
      </div>

      {loading && <div className="panel-3m panel-3m-empty text-sm text-white/35">Loading…</div>}

      {!loading && !rows.length && (
        <div className="panel-3m panel-3m-empty">No 3-min gainers.</div>
      )}

      {!loading && rows.length > 0 && (
        <div className="flex flex-col gap-1 panel-3m">
          {rows.slice(0, 8).map((row, i) => (
            <TokenRow
              key={row.symbol || i}
              index={i + 1}
              symbol={row.symbol}
              price={row.current_price}
              prevPrice={row.initial_price_3min}
              changePct={row.price_change_percentage_3min}
              side="gain"
              onInfo={onInfo}
            />
          ))}
        </div>
      )}

      {/* Show more is handled by the ThreeMinSection wrapper when present */}
    </section>
  );
}
