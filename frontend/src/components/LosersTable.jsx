import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";
import { formatSymbol } from "../lib/format";
import SymbolInfoPanel from "./SymbolInfoPanel";

export default function LosersTable({ items: incoming }) {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const source = Array.isArray(incoming) && incoming.length ? incoming : payload?.data;

  // unwrap { data: [...] }
  const raw = Array.isArray(source) ? source : [];

  // map backend row -> TokenRow props (ticker-only symbol)
  const mapped = raw.map((row, idx) => {
    const ticker = formatSymbol(row.symbol) || row.symbol;
    return {
      rank: row.rank ?? idx + 1,
      symbol: ticker,
      current_price: row.current_price,
      previous_price: row.initial_price_3min,
      price_change_percentage_1min: undefined,
      price_change_percentage_3min: row.price_change_percentage_3min,
      isGainer: false, // loser styling (purple)
    };
  });

  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const visible = useMemo(() => mapped.slice(0, 12), [mapped]);
  const hasData = visible.length > 0;

  return (
    <section className="text-left text-white text-[12px] font-mono">
      {/* header & underline per style guide */}
      <div className="inline-block rounded-[3px] border border-[#a16dff80] bg-black/70 px-2 py-[4px] text-[12px] font-semibold text-[#a16dff] shadow-glowPurple">
        3-MIN LOSERS
      </div>
      <div className="mt-2 h-px w-full max-w-[240px] border-b border-[#a16dff80] shadow-glowPurple" />

      {hasData ? (
        <div className="mt-4 w-full overflow-x-auto">
          <table className="w-full border-collapse min-w-[260px]">
            <tbody>
              {visible.map((rowProps, idx) => (
                <TokenRow
                  key={`${rowProps.symbol}-${idx}`}
                  {...rowProps}
                  onInfo={(sym) => setSelectedSymbol(sym)}
                  isGainer={false}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4 text-white/50">Loading (3min)..</div>
      )}

      {selectedSymbol && (
        <SymbolInfoPanel
          symbol={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
        />
      )}
    </section>
  );
}
