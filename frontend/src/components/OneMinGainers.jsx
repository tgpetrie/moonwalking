import React from "react";
import TokenRow from "./TokenRow.jsx";
import PanelShell from "./ui/PanelShell";

export default function OneMinGainers({ rows = [], loading = false, error = null, onInfo }) {
  const top = Array.isArray(rows) ? rows.slice(0, 8) : [];
  const left = top.slice(0, 4);
  const right = top.slice(4, 8);
  const hasData = top.length > 0;

  return (
    <PanelShell title={"1-MIN GAINERS"}>

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
                rank={row.rank ?? idx + 1}
                symbol={row.symbol}
                currentPrice={row.currentPrice ?? row.current_price}
                previousPrice={row.previousPrice ?? row.previous_price}
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
                rank={row.rank ?? left.length + idx + 1}
                symbol={row.symbol}
                currentPrice={row.currentPrice ?? row.current_price}
                previousPrice={row.previousPrice ?? row.previous_price}
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
    </PanelShell>
  );
}
