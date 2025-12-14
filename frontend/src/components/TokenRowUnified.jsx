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
  const change = Number.isFinite(rawChange) ? rawChange : 0;
  const isPositive = change >= 0;
  const strongMove = Math.abs(change) >= 0.5;

  const currentPrice = token?.current_price;
  const prevPrice =
    token?.previous_price_1m ?? token?.previous_price_3m ?? null;
  const priceForBaseline =
    token?.current_price ??
    token?.currentPrice ??
    token?.price ??
    token?.current ??
    null;

  const changeClass = [
    "bh-change",
    isPositive ? "bh-change-pos" : "bh-change-neg",
    strongMove ? "bh-change-strong" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const RowTag = renderAs === "tr" ? "tr" : "div";
  const CellTag = renderAs === "tr" ? "td" : "div";
  const rowClass = [
    "bh-row",
    density === "tight" ? "bh-row--tight" : "",
    !isPositive ? "bh-row--loss" : "",
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
        <span className={changeClass}>{change.toFixed(3)}%</span>
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
      {renderAs !== "tr" && <div className="bh-row-hover-glow" />}
      {renderCells()}
    </RowTag>
  );
}
