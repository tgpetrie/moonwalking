import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";
import { formatSymbol } from "../lib/format";
import SymbolInfoPanel from "./SymbolInfoPanel";

export default function GainersTable1Min({ items: incoming }) {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/gainers-table-1min",
    eventName: "gainers1m",
    pollMs: 6000,
    initial: [],
  });

  // prefer top-level prop (from useDataFeed) when available, otherwise live hook
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
      previous_price: row.initial_price_1min,
      price_change_percentage_1min: row.price_change_percentage_1min,
      price_change_percentage_3min: undefined,
      isGainer: true,
    };
  });

  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const twoCol = mapped.length > 4;
  const visible = useMemo(
    () => (twoCol ? mapped.slice(0, 8) : mapped.slice(0, 4)),
    [mapped, twoCol]
  );
  const hasData = visible.length > 0;

  return (
    <section className="text-left text-white text-[12px] font-mono">
      {/* header & underline per style guide */}
      <div className="inline-block rounded-[3px] border border-[#f9c86b80] bg-black/70 px-2 py-[4px] text-[12px] font-semibold text-[#f9c86b] shadow-glowGold">
        1-MIN GAINERS
      </div>
      <div className="mt-2 h-px w-full max-w-[240px] border-b border-[#f9c86b80] shadow-glowGold" />

      {hasData ? (
        <div className={`mt-4 w-full ${twoCol ? "grid grid-cols-1 sm:grid-cols-2 gap-3" : "overflow-x-auto"}`}>
          {twoCol ? (
            visible.map((rowProps, idx) => (
              <table
                key={`${rowProps.symbol}-${idx}`}
                className="w-full border-collapse min-w-[260px]"
              >
                <tbody>
                  <TokenRow
                    {...rowProps}
                    onInfo={(sym) => setSelectedSymbol(sym)}
                  />
                </tbody>
              </table>
            ))
          ) : (
            <table className="w-full border-collapse min-w-[260px]">
              <tbody>
                {visible.map((rowProps, idx) => (
                  <TokenRow
                    key={`${rowProps.symbol}-${idx}`}
                    {...rowProps}
                    onInfo={(sym) => setSelectedSymbol(sym)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="mt-4 text-white/50">Loading (1min)..</div>
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
