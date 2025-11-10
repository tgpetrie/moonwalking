import React from "react";
import RowActions from "./tables/RowActions.jsx";

function formatSymbol(sym = "") {
  return sym.replace(/-(USD|USDT|PERP)$/i, "");
}
function formatPrice(val) {
  const n = Number(val);
  if (!Number.isFinite(n)) return "—";
  if (n >= 1000) return `$${n.toFixed(0)}`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(3)}`;
  return `$${n.toFixed(6)}`;
}
function computePct(cur, prev, fallback) {
  const c = Number(cur);
  const p = Number(prev);
  if (p && Number.isFinite(c) && Number.isFinite(p)) {
    return ((c - p) / p) * 100;
  }
  return typeof fallback === "number" ? fallback : null;
}

export default function TokenRow({
  index = 0,
  symbol,
  price,
  prevPrice,
  changePct,
  side = "gain",
  onInfo,
}) {
  const pct = computePct(price, prevPrice, changePct);
  const pctDisplay = typeof pct === "number" ? `${pct.toFixed(3)}%` : "—";
  const cleanSymbol = formatSymbol(symbol);

  return (
    <div className={`token-row ${side === "loss" ? "is-loss" : "is-gain"}`}>
      <div className="token-row-line" aria-hidden />

      <div className="tr-col tr-col-symbol">
        <span className="tr-rank">{index + 1}</span>
        <span className="tr-symbol">{cleanSymbol}</span>
      </div>

      <div className="tr-col tr-col-price">
        <div className="tr-price-current">{formatPrice(price)}</div>
        <div className="tr-price-prev">
          {prevPrice ? formatPrice(prevPrice) : ""}
        </div>
      </div>

      <div className="tr-col tr-col-pct">
        <span className={side === "loss" ? "token-pct-loss" : "token-pct-gain"}>
          {pctDisplay}
        </span>
      </div>

      <div className="tr-col tr-col-actions">
        <RowActions
          symbol={cleanSymbol}
          priceNow={typeof price === "number" ? price : Number(price)}
          onInfo={
            onInfo
              ? () =>
                  onInfo({
                    symbol: cleanSymbol,
                    price,
                    prevPrice,
                    changePct: pct,
                  })
              : undefined
          }
        />
      </div>
    </div>
  );
}
