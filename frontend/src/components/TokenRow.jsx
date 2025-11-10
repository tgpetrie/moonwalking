import React, { useEffect, useRef } from "react";
import { formatSymbol, smartPrice } from "../utils/formatters.js";

function computePercent(price, prevPrice, fallback) {
  const c = Number(price);
  const p = Number(prevPrice);
  if (p && !Number.isNaN(c) && !Number.isNaN(p)) {
    return ((c - p) / p) * 100;
  }
  return typeof fallback === "number" ? fallback : null;
}

export default function TokenRow({
  index = 0,
  symbol = "—",
  price,
  prevPrice,
  changePct,
  side = "gain",          // "gain" | "loss"
  onInfo,
}) {
  const rootRef = useRef(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    // simple one-shot reveal
    el.classList.add("reveal");
    const t = setTimeout(() => el.classList.remove("reveal"), 400);
    return () => clearTimeout(t);
  }, []);

  const pct = computePercent(price, prevPrice, changePct);
  const pctDisplay = typeof pct === "number" ? `${Number(pct).toFixed(3).replace(/\.?0+$/, "")}%` : "—";

  return (
    <div
      ref={rootRef}
      className={`token-row ${side === "loss" ? "is-loss" : "is-gain"}`}
      data-state={side}
    >
      {/* inner line, goes behind content */}
      <div className="token-row-line" aria-hidden />

      {/* col 1: rank + symbol */}
      <div className="tr-col tr-col-symbol">
        <span className="tr-rank">{typeof index === "number" ? index : ""}</span>
        <span className="tr-symbol">{formatSymbol(symbol)}</span>
      </div>

      {/* col 2: price block (2 lines) */}
      <div className="tr-col tr-col-price price-block">
        <div className="tr-price-current">{price ? `$${smartPrice(price)}` : "—"}</div>
        <div className="tr-price-prev">{prevPrice ? `$${smartPrice(prevPrice)}` : ""}</div>
      </div>

      {/* col 3: percent */}
      <div className="tr-col tr-col-pct">
        <span
          className={side === "loss" ? "token-pct-loss" : "token-pct-gain"}
        >
          {pctDisplay}
        </span>
      </div>

      {/* col 4: actions (star on top, info below) */}
      <div className="tr-col tr-col-actions row-actions">
        <button type="button" className="action-btn" data-stop>
          ★
        </button>
        <button
          type="button"
          className="action-btn"
          data-stop
          onClick={() => onInfo && onInfo(symbol)}
        >
          ⓘ
        </button>
      </div>
    </div>
  );
}
