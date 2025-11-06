import React, { useState, useMemo } from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import TokenRow from "./TokenRow";
import { normalizeTableRow } from "../lib/adapters";

export default function LosersTable3Min() {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const raw = Array.isArray(payload?.data) ? payload.data : [];

  const mapped = raw.map((row, idx) => {
    const nr = normalizeTableRow(row);
    return {
      rank: nr.rank ?? row.rank ?? idx + 1,
      symbol: nr.symbol ?? row.symbol,
      current_price: nr.currentPrice ?? row.current_price,
      previous_price: row.initial_price_3min ?? nr._raw?.initial_price_3min ?? null,
      price_change_percentage_1min: undefined,
      price_change_percentage_3min: row.price_change_percentage_3min ?? nr._raw?.price_change_percentage_3min ?? null,
      isGainer: false, // PURPLE accent
    };
  });

  const [expanded, setExpanded] = useState(false);
  const visible = useMemo(
    () => (expanded ? mapped : mapped.slice(0, 8)),
    [mapped, expanded]
  );

  const hasData = visible.length > 0;

  return (
    <section className="text-left text-white text-[12px] font-mono max-w-[480px]">
      {/* purple header pill */}
      <div className="inline-block rounded-[3px] border border-[#a24bff80] bg-black/70 px-2 py-[4px] text-[12px] font-semibold text-[#a24bff] shadow-glowPurple">
        3-MIN LOSERS
      </div>

      {/* purple underline */}
      <div className="mt-2 h-px w-full max-w-[240px] border-b border-[#a24bff80] shadow-glowPurple" />

      {hasData ? (
        <>
          <div className="mt-4 w-full overflow-x-auto">
            <table className="w-full border-collapse min-w-[260px]">
              <tbody>
                {visible.map((rowProps, idx) => (
                  <TokenRow key={`${rowProps.symbol}-${idx}`} {...rowProps} />
                ))}
              </tbody>
            </table>
          </div>

          {!expanded && mapped.length > 8 && (
            <button
              className="mt-4 inline-block rounded-[4px] border border-[#a24bff80] bg-black/70 px-3 py-1 text-[11px] text-white shadow-glowPurple"
              onClick={() => setExpanded(true)}
            >
              Show more
            </button>
          )}
        </>
      ) : (
        <div className="mt-4 text-white/50">Loading (3min)..</div>
      )}
    </section>
  );
}
