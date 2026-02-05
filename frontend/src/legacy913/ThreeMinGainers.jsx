import React from "react";
import TokenRow from "./TokenRow.jsx";
import { baselineOrNull } from "../utils/num.js";

export default function ThreeMinGainers({ rows = [], loading = false, error = null, onInfo, title = "3-min gainers" }) {
  const top = Array.isArray(rows) ? rows.slice(0, 8) : [];
  const hasData = top.length > 0;

  return (
    <section className="w-full">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[16px] font-bold tracking-wide text-[#f9c86b] uppercase">{title}</h2>
      </div>

      {loading && <div className="py-6 text-sm text-white/40">Loading…</div>}
      {!loading && error && !hasData && (
        <div className="py-6 text-sm text-white/40">Backend unavailable (no data)</div>
      )}

      {!loading && hasData && (
        <div className="bg-black/0 rounded-md overflow-hidden panel-3m flex flex-col gap-1">
          {top.map((row, idx) => (
            <TokenRow
              key={row.symbol || idx}
              rank={row.rank ?? idx + 1}
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
      )}

      {!loading && hasData && rows.length > 8 && (
        <div className="mt-3 flex justify-center">
          <button type="button" className="px-4 py-1.5 rounded-full bg-[#2a2335] text-sm text-white/80 hover:bg-[#3a314a]">
            Show More
          </button>
        </div>
      )}
    </section>
  );
}
