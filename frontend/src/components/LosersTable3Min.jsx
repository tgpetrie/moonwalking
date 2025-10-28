import React, { useState } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";

/**
 * 3-MIN LOSERS TABLE (right side)
 * - Uses eventName "losers3m"
 * - Same row renderer, but purple styling + isGainer={false}
 */
export default function LosersTable3Min() {
  const { data } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const rows = Array.isArray(data?.data) ? data.data : [];
  const [expanded, setExpanded] = useState(false);

  const visibleRows = expanded ? rows : rows.slice(0, 8);
  const showToggle = rows.length > 8;

  return (
    <section className="text-left text-white font-mono text-[12px] max-w-[400px]">
      {/* purple header + glow bar */}
      <div className="inline-block rounded-[3px] border border-purple-400/40 bg-black/60 px-2 py-[4px] text-[12px] font-semibold text-purple-300 shadow-[0_0_30px_rgba(162,75,255,.5)]">
        3-MIN LOSERS
      </div>
      <div className="mt-2 h-px w-full max-w-[200px] border-b border-purple-400/60 shadow-[0_0_30px_rgba(162,75,255,.35)]" />

      {rows.length === 0 ? (
        <div className="mt-4 text-white/60">Loading (3min)..</div>
      ) : (
        <div className="mt-4 inline-block text-left">
          <table className="min-w-[260px] border border-purple-400/20 rounded-md shadow-[0_0_30px_rgba(162,75,255,.3)] bg-black/40">
            <tbody>
              {visibleRows.map((row, idx) => (
                <TokenRow key={idx} row={row} isGainer={false} />
              ))}
            </tbody>
          </table>

          {showToggle && (
            <button
              className="mt-4 inline-block rounded-[4px] border border-purple-400/40 bg-black/70 px-3 py-1 text-[11px] font-mono text-white shadow-[0_0_30px_rgba(162,75,255,.35)]"
              onClick={() => setExpanded((x) => !x)}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
