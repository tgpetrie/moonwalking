import React, { useEffect, useRef } from "react";
import { map1hPriceBannerItem, formatPrice, formatPct, colorForDelta } from "../utils/format";

function buildCoinbaseUrl(symbol) {
  if (!symbol) return "#";
  let pair = symbol;
  if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
    pair = `${pair}-USD`;
  }
  return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
}

export default function TopBannerScroll({ rows = [], onRefresh }) {
  const items = Array.isArray(rows) ? rows : [];
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || items.length === 0) return;
    const anim = el.animate(
      [{ transform: "translateX(0)" }, { transform: "translateX(-50%)" }],
      { duration: 30000, iterations: Infinity, easing: "linear" }
    );
    return () => anim.cancel();
  }, [items.length]);

  if (!items.length) {
    // Render an empty-but-visible banner container so layout stays intact
    return (
      <div className="ticker bh-banner">
        <div className="bh-banner-track">
          <div className="bh-banner-wrap"><span className="banner-empty">No 1h price-change data available.</span></div>
        </div>
      </div>
    );
  }

  return (
    <div className="ticker bh-banner">
      <div className="track bh-banner-track" ref={ref}>
        {[...items, ...items].map((t, i) => {
          const it = map1hPriceBannerItem(t);
          const side = colorForDelta(it.pct);
          const cls = side === "gain" ? "is-gain" : side === "loss" ? "is-loss" : "is-neutral";

          const displaySymbol = it.symbol ? it.symbol.replace(/-(USD|USDT|PERP)$/i, "") : "--";

          return (
            <a
              key={`${it.symbol || "item"}-${i}`}
              href={buildCoinbaseUrl(it.symbol)}
              target="_blank"
              rel="noreferrer"
              className={`bh-banner-item ${cls}`}
            >
              <b className="bh-banner-symbol">{displaySymbol}</b>
              <span className="bh-banner-price">{formatPrice(it.price)}</span>
              <span className="bh-banner-pct">{formatPct(it.pct)}</span>
            </a>
          );
        })}
      </div>
      {onRefresh && (
        <button type="button" className="bh-banner-refresh" onClick={onRefresh}>
          Refresh
        </button>
      )}
    </div>
  );
}

