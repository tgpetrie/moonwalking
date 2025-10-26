import React, { useState, useMemo } from "react";
import PropTypes from "prop-types";
// import SentimentCard from "./SentimentCard";
// import WatchStar from "./WatchStar";
// import { formatPrice, formatPercentage } from "../utils/formatters";

function getGlowClass(pct) {
  const n = Number(pct) || 0;
  if (n > 0) {
    // gold/orange glow for gainers
    return "text-yellow-300 drop-shadow-[0_0_6px_rgba(255,178,0,0.6)]";
  } else if (n < 0) {
    // purple glow for losers
    return "text-purple-300 drop-shadow-[0_0_6px_rgba(180,0,255,0.6)]";
  } else {
    return "text-gray-300";
  }
}

export default function MoverRow({ row }) {
  const [open, setOpen] = useState(false);

  const pct = useMemo(() => {
    // normalize % change; adapt keys as needed per API
    return row.changePct ?? row.change ?? row.deltaPct ?? row.price_change_percentage_1min ?? row.change3m ?? row.changePct3m ?? 0;
  }, [row]);

  const price = useMemo(() => {
    return row.price ?? row.current ?? row.current_price ?? 0;
  }, [row]);

  const glowClass = getGlowClass(pct);

  return (
    <tr className="relative group hover:bg-gray-800/40 transition-colors">
      {/* Symbol */}
      <td className="p-2 text-left font-medium text-gray-100 align-top">
        {row.symbol ?? "--"}
      </td>

      {/* Price */}
      <td className="p-2 text-right text-gray-200 align-top font-mono">
        ${Number(price).toFixed(2)}
      </td>

      {/* % Change */}
      <td className={"p-2 text-right font-semibold align-top font-mono " + glowClass}>
        {Number(pct).toFixed(2)}%
      </td>

      {/* Actions: star + info */}
      <td className="p-2 text-right align-top">
        <div className="flex items-center justify-end gap-1">
          {/* Simple star placeholder */}
          <button className="text-yellow-400 hover:text-yellow-300 text-sm">
            ★
          </button>

          {/* info placeholder */}
          <button
            className="text-gray-400 hover:text-gray-200 text-[12px] px-1 py-1 rounded transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(o => !o);
            }}
            title="Show sentiment"
          >
            ⓘ
          </button>

          {open && (
            <div className="absolute right-2 top-full mt-2 z-50 bg-gray-900 border border-gray-700 rounded p-2 text-xs">
              Sentiment placeholder
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

MoverRow.propTypes = {
  row: PropTypes.object.isRequired,
};