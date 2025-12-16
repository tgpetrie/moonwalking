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
  const resolvedChange = Number.isFinite(rawChange) ? rawChange : 0;
  const change = Number.isFinite(resolvedChange) ? resolvedChange : 0;
  const rounded = Number(change.toFixed(2));
  const strongMove = Math.abs(change) >= 0.5;
  const isLoss = rounded < 0;
  let deltaClass = "bh-change-flat";
  let prefix = "";
  if (rounded > 0) {
    deltaClass = "bh-change-pos";
    prefix = "+";
  } else if (rounded < 0) {
    deltaClass = "bh-change-neg";
  }

  const currentPrice = token?.current_price;
  const prevPrice =
    token?.previous_price ?? token?.previous_price_1m ?? token?.previous_price_3m ?? null;
  const priceForBaseline =
    token?.current_price ??
    token?.currentPrice ??
    token?.price ??
    token?.current ??
    null;

  const changeClass = ["bh-change", deltaClass, strongMove ? "bh-change-strong" : ""]
    .filter(Boolean)
    .join(" ");

  const RowTag = renderAs === "tr" ? "tr" : "div";
  const CellTag = renderAs === "tr" ? "td" : "div";
  const rowClass = [
    "bh-row",
    density === "tight" ? "bh-row--tight" : "",
    isLoss ? "bh-row--loss" : "bh-row--gain",
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
        <span className={changeClass}>{`${prefix}${rounded.toFixed(2)}%`}</span>
      </CellTag>

      {/* 5. Actions – stacked on far right */}
      <CellTag className="bh-cell bh-cell-actions">
        <RowActions
          starred={Boolean(isWatchlisted)}
          onToggleStar={() => onToggleWatchlist?.(token.symbol, priceForBaseline)}
          onInfoClick={() => onInfo?.(token.symbol)}
        />
      </CellTag>
    </>
  );

  return (
    <RowTag className={rowClass}>
      <span className="bh-row-bunny" aria-hidden="true" />
      {renderAs !== "tr" && <div className="bh-row-hover-glow" />}
      {renderCells()}
    </RowTag>
  );
}
