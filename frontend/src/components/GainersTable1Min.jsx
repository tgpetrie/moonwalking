import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";

export default function GainersTable1Min() {
  // hook gives us socket+poll data
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/gainers-table-1min",
    eventName: "gainers1m",
    pollMs: 6000,
    initial: [],
  });

  // unwrap backend shape: { data: [...] }
  const rows = Array.isArray(payload?.data) ? payload.data : [];

  // collapse behavior: show top 8 until expanded
  const [expanded, setExpanded] = useState(false);
  const visibleRows = useMemo(() => {
    if (!rows || rows.length === 0) return [];
    return expanded ? rows : rows.slice(0, 8);
  }, [rows, expanded]);

  const hasData = rows.length > 0;

  return (
    <section className="text-center text-white max-w-[480px] mx-auto">
      {/* header pill */}
      <div className="inline-block rounded-[3px] border border-[#f9c86b80] bg-black/70 px-2 py-[4px] text-[12px] font-mono font-semibold text-[#f9c86b] shadow-glowGold">
        1-MIN GAINERS
      </div>

      {/* table or empty (prefer positive condition to satisfy lint) */}
      {hasData ? (
        <div className="mt-6 w-full overflow-x-auto">
          <table className="w-full border-collapse min-w-[260px]">
            <tbody>
              {visibleRows.map((row, idx) => (
                <TokenRow
                  key={row.symbol || idx}
                  {...row}
                  isGainer={true}
                />
              ))}
            </tbody>
          </table>

          {!expanded && rows.length > 8 && (
            <button
              className="mt-4 inline-block rounded-[4px] border border-[#f9c86b80] bg-black/70 px-3 py-1 text-[11px] font-mono text-white shadow-glowGold"
              onClick={() => setExpanded(true)}
            >
              Show more
            </button>
          )}
        </div>
      ) : (
        <div className="mt-6 text-[12px] font-mono text-white/70">
          No 1-min gainers data available
        </div>
      )}
    </section>
  );
}
