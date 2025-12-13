// src/components/TokenRowUnified.jsx
import React from "react";
import RowActions from "./tables/RowActions.jsx";

/**
 * Format prices into readable ranges to avoid noisy decimals.
 */
function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return "-";
  const n = Number(value);

  if (n >= 100) return n.toFixed(0);
  if (n >= 1) return n.toFixed(2);
  if (n >= 0.01) return n.toFixed(4);
  return n.toFixed(6);
}

/**
 * Plain, non-animated BHABIT token row.
 * One layout used across:
 * - 1m gainers
 * - 3m gainers
 * - 3m losers
 * - Watchlist
 */
/**
 * Classify percentage change into tri-state: positive, negative, or flat.
 * Flat if rounded to 0.00%.
 */
function classifyPct(rawValue) {
  const num = Number.isFinite(rawValue) ? Number(rawValue) : 0;
  const rounded = Math.round(num * 100) / 100;

  if (rounded === 0) {
    return { state: "flat", display: "0.00%", className: "bh-change-flat" };
  }

  if (rounded > 0) {
    return { state: "positive", display: `+${rounded.toFixed(2)}%`, className: "bh-change-pos" };
  }

  return { state: "negative", display: `${rounded.toFixed(2)}%`, className: "bh-change-neg" };
}

export function TokenRowUnified({
  token,
  rank,
  changeField, // "change_1m" or "change_3m"
  onToggleWatchlist,
  onInfo,
  isWatchlisted,
  renderAs = "div",
  density = "normal", // "normal" | "tight"
}) {
  const rawChange = token?.[changeField];
  const change = Number.isFinite(rawChange) ? Number(rawChange) : 0;
  const pctInfo = classifyPct(change);

  const currentPrice = token?.current_price;
  const prevPrice =
    token?.previous_price_1m ?? token?.previous_price_3m ?? null;

  const RowTag = renderAs === "tr" ? "tr" : "div";
  const CellTag = renderAs === "tr" ? "td" : "div";
  const rowClass = [
    "bh-row",
    density === "tight" ? "bh-row--tight" : "",
    pctInfo.state === "negative" ? "bh-row--loss" : "",
    pctInfo.state === "positive" ? "is-gain" : pctInfo.state === "negative" ? "is-loss" : "is-flat",
  ]
    .filter(Boolean)
    .join(" ");

  const renderCells = () => (
    <>
      {/* 1. Rank circle */}
      <CellTag className="bh-cell bh-cell-rank">
        <div className="bh-rank">{rank}</div>
      </CellTag>

      {/* 2. Token name */}
      <CellTag className="bh-cell bh-cell-symbol">
        <div className="bh-symbol">{token.symbol}</div>
        {token.base && <div className="bh-name">{token.base}</div>}
      </CellTag>

      {/* 3. Price stack (current / previous) */}
      <CellTag className="bh-cell bh-cell-price">
        <div className="bh-price-current">${formatPrice(currentPrice)}</div>
        <div className="bh-price-previous">${formatPrice(prevPrice)}</div>
      </CellTag>

      {/* 4. Percent change – main focal point */}
      <CellTag className="bh-cell bh-cell-change">
        <span className={`bh-change ${pctInfo.className}`}>{pctInfo.display}</span>
      </CellTag>

      {/* 5. Actions – stacked on far right */}
      <CellTag className="bh-cell bh-cell-actions">
        <RowActions
          starred={Boolean(isWatchlisted)}
          onToggleStar={() => onToggleWatchlist?.(token.symbol)}
          onInfoClick={() => onInfo?.(token.symbol)}
        />
      </CellTag>
    </>
  );

  return (
    <RowTag className={rowClass}>
      {renderAs !== "tr" && <div className="bh-row-hover-glow" />}
      {renderCells()}
    </RowTag>
  );
}
