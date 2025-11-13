import React, { useState } from "react";
import TokenRow from "./TokenRow.jsx";

function SkeletonRow({ index }) {
  return (
    <tr className="table-row">
      <td className="bh-token-rank">{index + 1}</td>
      <td className="bh-token-symbol">---</td>
      <td className="bh-token-price">--.--</td>
      <td className="bh-token-change">---%</td>
      <td>
        <button type="button" className="bh-star" disabled>
          ★
        </button>
      </td>
    </tr>
  );
}

export default function Gainers1m({
  rows = [],
  loading = false,
  showTitle = true,
  onInfo,
}) {
  const INITIAL_LIMIT = 8; // 4+4 columns before "Show more"
  const EXPANDED_LIMIT = 16; // Max after expansion
  
  const [expanded, setExpanded] = useState(false);
  
  const limit = expanded ? EXPANDED_LIMIT : INITIAL_LIMIT;
  const visible = rows.slice(0, limit);
  const hasMore = rows.length > limit;
  
  // Split into left (ranks 1-4) and right (ranks 5-8, or 5-16 when expanded)
  const left = visible.slice(0, Math.min(4, visible.length));
  const right = visible.slice(4, limit);

  return (
    <section className="mt-4">
      <header className="mb-2 flex items-center gap-2">
        <span className="badge-gold">1-MIN GAINERS</span>
        <span className="rule-gold" />
      </header>

      <div className="one-min-grid">
        <div className="one-min-col">
          <table className="w-full border-collapse text-[12px] font-mono leading-5">
            <tbody>
              {left.length === 0 ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <SkeletonRow key={i} index={i} />
                ))
              ) : (
                left.map((row, idx) => (
                  <TokenRow 
                    key={row.symbol || idx} 
                    row={row} 
                    index={idx} 
                    isGainer 
                    changeKey="price_change_percentage_1min" 
                    onInfo={onInfo} 
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {right.length > 0 && (
          <div className="one-min-col">
            <table className="w-full border-collapse text-[12px] font-mono leading-5">
              <tbody>
                {right.map((row, idx) => (
                  <TokenRow 
                    key={row.symbol || idx} 
                    row={row} 
                    index={idx + left.length} 
                    isGainer 
                    changeKey="price_change_percentage_1min" 
                    onInfo={onInfo} 
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {hasMore && (
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="px-4 py-1 text-xs rounded-full border border-white/20 bg-transparent text-white/70 hover:bg-white/10 hover:text-white/90 transition-all"
          >
            {expanded ? "Show Less" : "Show More"}
          </button>
        </div>
      )}
    </section>
  );
}

