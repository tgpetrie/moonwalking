// src/components/TokenRowSimple.jsx
import React from "react";
import RowActions from "./tables/RowActions.jsx";

function formatPrice(value) {
  if (value == null) return "--";
  const n = Number(value);
  if (Number.isNaN(n)) return "--";
  if (n >= 1000) return `$${n.toLocaleString()}`;
  return `$${n.toFixed(3)}`;
}

function formatPct(value) {
  if (value == null) return "--";
  const n = Number(value);
  if (Number.isNaN(n)) return "--";
  return `${n.toFixed(2)}%`;
}

export default function TokenRowSimple({ index, row }) {
  // defensive picks
  const symbol =
    (row?.symbol && String(row.symbol).replace(/-USD$/i, "")) ||
    (row?.ticker && String(row.ticker).replace(/-USD$/i, "")) ||
    "--";

  const price = row?.price ?? row?.current_price ?? null;

  const pct =
    row?.pct ??
    row?.price_change_percentage_1min ??
    row?.price_change_percentage_3min ??
    null;

  return (
    <div
      className="token-row token-row--live"
      style={{ "--row-delay": `${(index % 12) * 90}ms` }}
    >
      <div className="token-rank">{index + 1}</div>
      <div className="token-symbol">{symbol}</div>
      <div className="token-price">
        <div>{formatPrice(price)}</div>
        {price != null && (
          <div className="token-price-sub">${Number(price).toFixed(3)}</div>
        )}
      </div>
      <div
        className={`token-pct ${
          pct != null && pct < 0 ? "token-pct-loss" : "token-pct-gain"
        }`}
      >
        {formatPct(pct)}
      </div>
      <div className="token-actions">
        <RowActions symbol={symbol} price={price} onInfo={() => {}} />
      </div>
    </div>
  );
}
