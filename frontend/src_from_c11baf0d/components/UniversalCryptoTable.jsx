import React, { useState } from "react";
import CryptoTableRow from "./CryptoTableRow.jsx";

const UniversalCryptoTable = ({
  title,
  data,
  timeframeLabel,
  tone = "blue",
  onToggleWatchlist,
  isInWatchlist,
  linkBuilder,
}) => {
  const [expanded, setExpanded] = useState(false);
  const rowsPerColumn = expanded ? data.length : 10;
  const midpoint = Math.ceil(data.length / 2);
  const columns = [
    data.slice(0, midpoint),
    data.slice(midpoint, data.length),
  ];

  return (
    <div className="w-full">
      {title && (
        <h2 className="text-lg font-semibold mb-2 text-center">{title}</h2>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
        {columns.map((col, colIndex) => (
          <div key={colIndex} className="flex flex-col space-y-2">
            {col.slice(0, rowsPerColumn).map((coin, index) => (
              <CryptoTableRow
                key={coin.symbol}
                rank={colIndex * midpoint + index + 1}
                coin={coin}
                timeframeLabel={timeframeLabel}
                tone={tone}
                onToggleWatchlist={onToggleWatchlist}
                isInWatchlist={isInWatchlist}
                linkBuilder={linkBuilder}
              />
            ))}
          </div>
        ))}
      </div>
      {data.length > 10 && (
        <div className="flex justify-center mt-4">
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-1 text-sm text-purple-400 hover:text-purple-200 transition"
          >
            {expanded ? "Show Less" : "Show More"}
          </button>
        </div>
      )}
    </div>
  );
};

export default UniversalCryptoTable;
