// frontend/src/components/tables/RowActions.jsx
import React, { Suspense, useState } from "react";
import { useWatchlist } from "../../context/WatchlistContext.jsx";

const SentimentCard = React.lazy(() => import("../cards/SentimentCard.jsx"));

export default function RowActions({ symbol, priceNow, onInfo }) {
  const [open, setOpen] = useState(false);
  const { add, remove, has, baselineFor } = useWatchlist();

  const watching = has(symbol);
  const base = baselineFor(symbol);
  const delta =
    base && typeof priceNow === "number"
      ? ((priceNow - base.price) / base.price) * 100
      : null;

  const handleStar = () => {
    if (watching) {
      remove(symbol);
    } else {
      add(symbol, priceNow);
    }
  };

  const handleInfo = () => {
    if (onInfo) {
      onInfo();
    } else {
      setOpen((v) => !v);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleStar}
        className={`wl-btn ${watching ? "active" : ""}`}
        aria-label={watching ? "Remove from watchlist" : "Add to watchlist"}
      />
      <div className="text-[10px] leading-none opacity-80 select-none">
        {delta != null
          ? `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}%`
          : ""}
      </div>
      <button
        onClick={handleInfo}
        className="wl-btn"
        aria-label={`Sentiment for ${symbol}`}
      >
        i
      </button>
      {!onInfo && open && (
        <div className="sentiment-pop fade-in">
          <Suspense fallback={<div className="text-xs opacity-70">Loading…</div>}>
            <SentimentCard symbol={symbol} ttlSec={30} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

