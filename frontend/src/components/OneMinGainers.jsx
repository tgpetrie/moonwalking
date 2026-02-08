import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";
import { baselineOrNull } from "../utils/num.js";

export default function OneMinGainers({ rows = [], loading = false, error = null, onInfo }) {
  const [expanded, setExpanded] = useState(false);

  // Visible rows: default 8, expand to 16 when user clicks "Show More".
  const visibleRows = useMemo(() => {
    const src = Array.isArray(rows) ? rows : [];
    const cap = expanded ? 16 : 8;
    return src.slice(0, cap);
  }, [rows, expanded]);

  const visibleCount = visibleRows.length;
  const hasData = visibleCount > 0;

  // Layout: single full-width column when 4 or fewer rows; otherwise two columns.
  const isSingleColumn = visibleCount <= 4;

  // Split for two-column layout; keep ranks global (1..N). When splitting,
  // prefer left column to hold the first Math.ceil(N/2) items (capped at 8).
  const [left, right] = useMemo(() => {
    if (isSingleColumn) return [visibleRows, []];
    const half = Math.min(8, Math.ceil(visibleCount / 2));
    const l = visibleRows.slice(0, half);
    const r = visibleRows.slice(half, half + 8);
    return [l, r];
  }, [visibleRows, isSingleColumn, visibleCount]);

  return (
    <section className="w-full mb-8">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[18px] font-bold tracking-wide text-[#f9c86b] uppercase">1-min gainers</h2>
      </div>

      {loading && <div className="py-6 text-sm text-white/40">Loading…</div>}
      {!loading && error && !hasData && (
        <div className="py-6 text-sm text-white/40">Backend unavailable (no data)</div>
      )}

      {!loading && hasData && (
        <div className={`one-min-grid ${isSingleColumn ? "one-min-single" : "one-min-two"}`}>
          {/* Left / only column */}
          <div className="bg-black/0 rounded-md overflow-hidden panel-3m flex flex-col gap-1">
            {left.map((row, idx) => (
              <TokenRow
                key={row.symbol || idx}
                rank={idx + 1}
                symbol={row.symbol}
                currentPrice={row.currentPrice ?? row.current_price}
                previousPrice={baselineOrNull(row.previousPrice ?? row.previous_price ?? null)}
                priceChange1min={row.priceChange1min ?? row.price_change_percentage_1min}
                priceChange3min={row.priceChange3min ?? row.price_change_percentage_3min}
                isGainer={true}
                onInfo={onInfo}
              />
            ))}
          </div>

          {/* Right column (may be empty for single-column mode) */}
          {!isSingleColumn && (
            <div className="bg-black/0 rounded-md overflow-hidden panel-3m flex flex-col gap-1">
              {right.map((row, idx) => (
                <TokenRow
                  key={row.symbol || `r-${idx}`}
                  rank={left.length + idx + 1}
                  symbol={row.symbol}
                  currentPrice={row.currentPrice ?? row.current_price}
                  previousPrice={baselineOrNull(row.previousPrice ?? row.previous_price ?? null)}
                  priceChange1min={row.priceChange1min ?? row.price_change_percentage_1min}
                  priceChange3min={row.priceChange3min ?? row.price_change_percentage_3min}
                  isGainer={true}
                  onInfo={onInfo}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {!loading && hasData && rows.length > 8 && (
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={() => setExpanded((s) => !s)}
            className="px-5 py-2 rounded-full bg-[#2a2335] text-sm text-white/80 hover:bg-[#3a314a] transition"
          >
            {expanded ? "Show Less" : "Show More"}
          </button>
        </div>
      )}
    </section>
  );
}
