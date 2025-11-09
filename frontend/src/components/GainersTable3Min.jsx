import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";
import { formatSymbol } from "../lib/format";
import { normalizeTableRow } from "../lib/adapters";
import SymbolInfoPanel from "./SymbolInfoPanel";

export default function GainersTable3Min({ items: incoming, rows, loading, error, onInfo }) {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/gainers-table",
    eventName: "gainers3m",
    pollMs: 8000,
    initial: [],
  });

  const external = Array.isArray(rows) ? rows : null;
  const source = external ?? (Array.isArray(incoming) && incoming.length ? incoming : payload?.data);

  // unwrap { data: [...] }
  const raw = Array.isArray(source) ? source : [];

  // map backend row -> TokenRow props
  const mapped = raw.map((row, idx) => {
    const nr = normalizeTableRow(row);
    const ticker = formatSymbol(nr.symbol || row.symbol) || nr.symbol || row.symbol;
    return {
      rank: nr.rank ?? row.rank ?? idx + 1,
      symbol: ticker,
      current_price: nr.currentPrice ?? row.current_price,
      previous_price: row.initial_price_3min ?? nr._raw?.initial_price_3min ?? null,
      price_change_percentage_1min: undefined,
      price_change_percentage_3min: row.price_change_percentage_3min ?? nr._raw?.price_change_percentage_3min ?? null,
      isGainer: true,
    };
  });

  const [expanded, setExpanded] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const visible = useMemo(
    () => (expanded ? mapped : mapped.slice(0, 8)),
    [mapped, expanded]
  );

  const hasData = visible.length > 0;
  const showError = !external && !loading && error && !hasData;

  return (
    <section className="text-left text-white text-[12px]">
      {/* orange header pill */}
      <div className="inline-block rounded-[3px] border border-[#f9c86b80] bg-black/70 px-2 py-[4px] text-[12px] font-semibold text-[#f9c86b] shadow-glowGold">
        3-MIN GAINERS
      </div>

      {/* underline */}
      <div className="mt-2 h-px w-full max-w-[240px] border-b border-[#f9c86b80] shadow-glowGold" />

      {showError ? (
        <div className="mt-4 text-white/50">Backend unavailable (no data)</div>
      ) : hasData ? (
        <>
          <div className="mt-4 w-full overflow-x-hidden panel-3m flex flex-col gap-1">
            {visible.map((rowProps, idx) => (
              <TokenRow
                key={`${rowProps.symbol}-${idx}`}
                {...rowProps}
                onInfo={onInfo || ((sym) => setSelectedSymbol(sym))}
              />
            ))}
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

      {selectedSymbol && (
        <SymbolInfoPanel
          symbol={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
        />
      )}
    </section>
  );
}
