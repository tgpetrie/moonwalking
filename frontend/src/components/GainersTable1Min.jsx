import React, { useState } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";

/**
 * 1-MIN GAINERS
 * - Uses eventName "gainers1m"
 * - Backend field: price_change_percentage_1min
 * - Collapses to top 8 unless "Show more"
 */
export default function GainersTable1Min() {
  const { data } = useHybridLiveNamed({
    endpoint: "/api/component/gainers-table-1min",
    eventName: "gainers1m",
    pollMs: 6000,
    initial: [],
  });

  // unwrap transport payload: { data: [...] }
  const rows = Array.isArray(data?.data) ? data.data : [];
  const [expanded, setExpanded] = useState(false);

  const visibleRows = expanded ? rows : rows.slice(0, 8);
  const showToggle = rows.length > 8;

  return (
    <section className="text-center text-white font-mono">
      {/* gold pill header */}
      <div className="inline-block rounded-[4px] border border-yellow-300/40 bg-black/70 px-2 py-1 text-[12px] font-semibold text-yellow-300 shadow-[0_0_30px_rgba(249,200,107,.45)]">
        1-MIN GAINERS
      </div>

      {/* table or empty state */}
      {rows.length === 0 ? (
        <div className="mt-4 text-[12px] text-white/70">
          No 1-min gainers data available
        </div>
      ) : (
        <div className="mt-4 inline-block text-left">
          <table className="min-w-[260px] border border-yellow-300/20 rounded-md shadow-[0_0_30px_rgba(249,200,107,.2)] bg-black/40">
            <tbody>
              {visibleRows.map((row, idx) => (
                <TokenRow key={idx} row={row} isGainer={true} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Show more */}
      {showToggle && (
        <button
          className="mt-4 inline-block rounded-[4px] border border-yellow-300/40 bg-black/70 px-3 py-1 text-[11px] font-mono text-white shadow-[0_0_30px_rgba(249,200,107,.35)]"
          onClick={() => setExpanded((x) => !x)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </section>
  );
}
