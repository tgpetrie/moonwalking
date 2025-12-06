import { forwardRef, useEffect, useRef, useState } from "react";
import { formatPrice, formatPct, tickerFromSymbol } from "../utils/format.js";
import { Star, Info } from "lucide-react";

const TokenRow = forwardRef(function TokenRow(
  {
    rank,
    symbol,
    name,
    currentPrice,
    previousPrice,
    percentChange,
    onToggleWatchlist,
    onInfo,
    isWatchlisted,
  },
  ref
) {
  const numericChange =
    typeof percentChange === "number"
      ? percentChange
      : parseFloat(String(percentChange || "0").replace(/[%+]/g, ""));
  const isLoss = !Number.isNaN(numericChange) && numericChange < 0;
  const isPositive = !Number.isNaN(numericChange) && numericChange >= 0;
  const displaySymbol = tickerFromSymbol(symbol);

  // liveliness: flash row briefly when percentChange updates
  const [justUpdated, setJustUpdated] = useState(false);
  const prevPct = useRef(numericChange);
  useEffect(() => {
    if (prevPct.current !== numericChange) {
      if (!Number.isNaN(numericChange)) {
        setJustUpdated(true);
        const t = setTimeout(() => setJustUpdated(false), 700);
        return () => clearTimeout(t);
      }
      prevPct.current = numericChange;
    }
    prevPct.current = numericChange;
  }, [numericChange]);

  const rowClass = `bh-row ${isLoss ? "bh-row--loss is-loss" : ""} ${justUpdated ? "bh-row--updated" : ""}`;

  return (
    <div ref={ref} className={rowClass}>
      {/* hover glow layer */}
      <div className="bh-row-hover-glow" aria-hidden="true" />

      <div className="bh-cell bh-cell-rank">
        <span className="bh-rank">{rank}</span>
      </div>

      <div className="bh-cell bh-cell-symbol">
        <div className="bh-symbol">{displaySymbol}</div>
        {name && <div className="bh-name">{name}</div>}
      </div>

      <div className="bh-cell bh-cell-price">
        <div className="bh-price-current">{formatPrice(currentPrice)}</div>
        <div className="bh-price-previous">{formatPrice(previousPrice)}</div>
      </div>

      <div className="bh-cell bh-cell-change">
        <span className={"bh-change " + (isPositive ? "bh-change-pos" : "bh-change-neg")}>
          {formatPct(percentChange)}
        </span>
      </div>

      <div className="bh-cell bh-cell-actions">
        <div className="bh-row-actions">
          <button
            type="button"
            className={`bh-row-action ${isWatchlisted ? "is-active" : ""}`}
            onClick={onToggleWatchlist}
            aria-label={isWatchlisted ? "Remove from watchlist" : "Add to watchlist"}
          >
            <Star className="bh-row-icon" size={14} strokeWidth={1.5} />
          </button>
          <button
            type="button"
            className="bh-row-action"
            onClick={onInfo}
            aria-label="Show token details"
          >
            <Info className="bh-row-icon" size={14} strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </div>
  );
});

export default TokenRow;
