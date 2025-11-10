import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function Gainers1m({ rows = [], loading, error, onInfo }) {
  const left = rows.slice(0, 4);
  const right = rows.slice(4, 8);

  return (
    <section className="panel-shell">
      <div className="text-center">
        <h2 className="section-title-gold">1-MIN GAINERS</h2>
        <div className="section-underline-gold" />
      </div>

      {loading && <div className="text-sm text-white/35 py-3">Loading…</div>}
      {!loading && error && !rows.length && (
        <div className="text-sm text-white/35 py-3">Backend unavailable (no data)</div>
      )}

      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          <div className="flex flex-col gap-1">
            {left.map((row, i) => (
              <TokenRow
                key={row.symbol || i}
                index={i + 1}
                symbol={row.symbol}
                price={row.current_price}
                prevPrice={row.initial_price_1min}
                changePct={row.price_change_percentage_1min}
                side="gain"
                onInfo={onInfo}
              />
            ))}
          </div>
          <div className="flex flex-col gap-1">
            {right.map((row, i) => (
              <TokenRow
                key={row.symbol || i}
                index={i + 1 + left.length}
                symbol={row.symbol}
                price={row.current_price}
                prevPrice={row.initial_price_1min}
                changePct={row.price_change_percentage_1min}
                side="gain"
                onInfo={onInfo}
              />
            ))}
          </div>
        </div>
      )}

      {rows.length > 8 && (
        <div className="mt-4">
          <button className="px-4 py-2 rounded-full bg-[#242131] text-xs">Show More</button>
        </div>
      )}
    </section>
  );
}
