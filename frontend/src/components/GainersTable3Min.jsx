import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";
import SymbolInfoPanel from "./SymbolInfoPanel";

export default function GainersTable3Min() {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/gainers-table",
    eventName: "gainers3m",
    pollMs: 8000,
    initial: [],
  });

  // unwrap { data: [...] }
  const raw = Array.isArray(payload?.data) ? payload.data : [];

  // map backend row -> TokenRow props
  const mapped = raw.map((row, idx) => {
    const ticker = (row.symbol || "").replace(/-USD$/i, "") || row.symbol;
    return {
      rank: row.rank ?? idx + 1,
      symbol: ticker, // ticker-only (no "-USD")
      current_price: row.current_price,
      previous_price: row.initial_price_3min,
      price_change_percentage_1min: undefined,
      price_change_percentage_3min: row.price_change_percentage_3min,
      isGainer: true, // ORANGE accent
    };
  });

  const [expanded, setExpanded] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const visible = useMemo(
    () => (expanded ? mapped : mapped.slice(0, 8)),
    [mapped, expanded]
  );

  const hasData = visible.length > 0;

  return (
    <section className="text-left text-white text-[12px] font-mono max-w-[480px]">
      {/* orange header pill */}
      <div className="inline-block rounded-[3px] border border-[#f9c86b80] bg-black/70 px-2 py-[4px] text-[12px] font-semibold text-[#f9c86b] shadow-glowGold">
        3-MIN GAINERS
      </div>

      {/* underline */}
      <div className="mt-2 h-px w-full max-w-[240px] border-b border-[#f9c86b80] shadow-glowGold" />

      {hasData ? (
        <>
          <div className="mt-4 w-full overflow-x-auto">
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
          </div>

          {!expanded && mapped.length > 8 && (
            <button
              className="mt-4 inline-block rounded-[4px] border border-[#f9c86b80] bg-black/70 px-3 py-1 text-[11px] text-white shadow-glowGold"
              onClick={() => setExpanded(true)}
            >
              Show more
            </button>
          )}
        </>
      ) : (
        <div className="mt-4 text-white/50">Loading (3min)..</div>
      )}

      <SymbolInfoPanel
        symbol={selectedSymbol}
        onClose={() => setSelectedSymbol(null)}
      />
    </section>
  );
}
