import React from "react";
import TokenRow from "./TokenRow.jsx";
import { baselineOrNull } from "../utils/num.js";

export default function OneMinGainers({ rows = [], loading = false, error = null, onInfo }) {
  const top = Array.isArray(rows) ? rows.slice(0, 8) : [];
  const left = top.slice(0, 4);
  const right = top.slice(4, 8);
  const hasData = top.length > 0;

  return (
    <section className="w-full mb-8">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[18px] font-bold tracking-wide text-[#f9c86b] uppercase">1-min gainers</h2>
      </div>

      {loading && <div className="py-6 text-sm text-white/40">Loading…</div>}
      {!loading && error && !hasData && (
        <div className="py-6 text-sm text-white/40">Backend unavailable (no data)</div>
      )}

      {!loading && hasData && (
        <div className="one-min-grid">
          <div className="bg-black/0 rounded-md overflow-hidden panel-3m flex flex-col gap-1">
            {left.map((row, idx) => (
              <TokenRow
                key={row.symbol || idx}
                rank={idx + 1}
                symbol={row.symbol}
                currentPrice={row.currentPrice ?? row.current_price}
                previousPrice={baselineOrNull(row.previousPrice ?? row.previous_price ?? null)}
                priceChange1min={row.priceChange1min ?? row.price_change_percentage_1min}
                priceChange3min={row.priceChange3min ?? row.price_change_percentage_3min}
                isGainer={true}
                onInfo={onInfo}
              />
            ))}
          </div>

          <div className="bg-black/0 rounded-md overflow-hidden panel-3m flex flex-col gap-1">
            {right.map((row, idx) => (
              <TokenRow
                key={row.symbol || `r-${idx}`}
                rank={left.length + idx + 1}
                symbol={row.symbol}
                currentPrice={row.currentPrice ?? row.current_price}
                previousPrice={baselineOrNull(row.previousPrice ?? row.previous_price ?? null)}
                priceChange1min={row.priceChange1min ?? row.price_change_percentage_1min}
                priceChange3min={row.priceChange3min ?? row.price_change_percentage_3min}
                isGainer={true}
                onInfo={onInfo}
              />
            ))}
          </div>
        </div>
      )}

      {!loading && hasData && rows.length > 8 && (
        <div className="mt-4 flex justify-center">
          <button type="button" className="px-5 py-2 rounded-full bg-[#2a2335] text-sm text-white/80 hover:bg-[#3a314a] transition">
            Show More
          </button>
        </div>
      )}
    </section>
  );
}
