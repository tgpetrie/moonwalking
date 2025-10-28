import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";

export default function LosersTable3Min() {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table-3min",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const rows = Array.isArray(payload?.data) ? payload.data : [];
  const [expanded, setExpanded] = useState(false);

  const visibleRows = useMemo(() => (expanded ? rows : rows.slice(0, 8)), [rows, expanded]);

  return (
    <section className="text-left text-white font-mono text-[12px] max-w-[400px]">
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
                <TokenRow key={row.symbol || idx} {...row} isGainer={false} />
              ))}
            </tbody>
          </table>

          {rows.length > 8 && (
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
