import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import MoverRow from "./MoverRow";

export default function MoverTable({ title, rows }) {
  // Sort and state (if needed: keep existing sortKey/direction logic)
  const [sortKey] = useState("changePct");
  const [direction] = useState("desc");

  const sorted = useMemo(() => {
    // Normalize
    const safeRows = Array.isArray(rows) ? rows : [];
    return [...safeRows].sort((a, b) => {
      const av = Number(a[sortKey] ?? 0);
      const bv = Number(b[sortKey] ?? 0);
      return direction === "desc" ? (bv - av) : (av - bv);
    });
  }, [rows, sortKey, direction]);

  return (
    <div className="bg-black/40 border border-gray-800 rounded-xl p-3 shadow-[0_0_20px_rgba(0,0,0,0.8)]">
      {/* Title/header */}
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-[11px] text-gray-400 uppercase tracking-wide">
          {title}
        </div>
        {/* optional controls: sort toggles, "show more", etc. */}
      </div>

      <table className="w-full text-[11px] text-gray-200">
        <thead className="text-gray-500 text-[10px] border-b border-gray-800">
          <tr>
            <th className="p-2 text-left font-normal">Symbol</th>
            <th className="p-2 text-right font-normal">Price</th>
            <th className="p-2 text-right font-normal">% Chg</th>
            <th className="p-2 text-right font-normal"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/60">
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={4}
                className="p-4 text-center text-gray-600 text-[11px]"
              >
                No data yet (cache empty / 503). Still live.
              </td>
            </tr>
          ) : (
            sorted.map((row) => <MoverRow key={row.symbol} row={row} />)
          )}
        </tbody>
      </table>
    </div>
  );
}

MoverTable.propTypes = {
  title: PropTypes.string.isRequired,
  rows: PropTypes.array,
};