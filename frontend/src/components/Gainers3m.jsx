import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Gainers3m({ rows = [], loading, onInfo }) {
  return (
    <section className="w-full">
      <h2 className="section-title-gold">3-MIN GAINERS</h2>
      <div className="section-underline-gold" />

      {loading && <div className="text-sm text-white/35 py-3">Loading…</div>}
      {!loading && !rows.length && (
        <div className="text-sm text-white/35 py-3">No 3-min gainers.</div>
      )}

      {!loading && rows.length > 0 && (
        <div className="flex flex-col gap-1 panel-3m">
          {rows.slice(0, 8).map((row, i) => (
            <TokenRow
              key={row.symbol || i}
              index={i}
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

      {rows.length > 8 && (
        <div className="mt-5">
          <button className="px-5 py-2 rounded-full bg-[#242131] text-xs">
            Show More
          </button>
        </div>
      )}
    </section>
  );
}
