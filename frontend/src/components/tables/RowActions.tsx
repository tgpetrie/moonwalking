import React, { useState } from "react";
import { FiInfo } from "react-icons/fi";
import WatchStar from "../WatchStar.jsx";
import { useWatchlistContext } from "../../hooks/useWatchlist.jsx";
import SentimentCard from "../cards/SentimentCard.jsx";

type Props = {
  symbol: string;
  price?: number;
};

export default function RowActions({ symbol, price }: Props) {
  const { has, baselineFor } = useWatchlistContext();
  const [showInfo, setShowInfo] = useState(false);
  const watching = has(symbol);
  const baseline = baselineFor(symbol);
  const delta = baseline && typeof price === "number" && baseline.price > 0
    ? ((price - baseline.price) / baseline.price) * 100
    : null;

  return (
    <div className="relative flex flex-col items-end gap-1">
      <span data-test="watch-star">
        <WatchStar productId={symbol} price={price} onToggled={() => {}} />
      </span>
      {delta != null && (
        <span className={`text-[10px] tabular-nums ${delta >= 0 ? "text-gain" : "text-loss"}`}>
          {delta >= 0 ? "+" : ""}{delta.toFixed(2)}%
        </span>
      )}
      <button
        type="button"
        aria-label="Show sentiment"
        data-test="info-button"
        className="text-purple-200 hover:text-purple-100 fi-info"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setShowInfo((v) => !v);
        }}
      >
        <FiInfo size={16} />
      </button>
      {showInfo && (
        <div data-test="sentiment-popover" className="absolute right-7 top-1 z-30 w-64 rounded-xl border border-white/10 bg-black/90 p-3 shadow-xl text-left text-xs sentiment-popover">
          <SentimentCard symbol={symbol} ttlSec={45} />
        </div>
      )}
    </div>
  );
}
