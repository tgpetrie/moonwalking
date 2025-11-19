import React, { useEffect, useRef } from "react";
import { map1hPriceBannerItem, formatPrice, formatPct } from "../utils/format";

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
      <div className="bh-banner-wrap">
        <div className="ticker bh-banner">
          <div className="bh-banner-track">
            <span className="banner-empty">No 1h price-change data available.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bh-banner-wrap">
      <div className="ticker bh-banner">
        <div className="bh-banner-track" ref={ref}>
          {[...items, ...items].map((t, i) => {
            const it = map1hPriceBannerItem(t);
            const pct = Number(it?.pct ?? 0);
            const pctClass =
              pct > 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--gain"
                : pct < 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--loss"
                : "bh-banner-chip__pct";

            const displaySymbol = it.symbol
              ? it.symbol.replace(/-(USD|USDT|PERP)$/i, "")
              : "--";

            return (
              <a
                key={`${it.symbol || "item"}-${i}`}
                href={buildCoinbaseUrl(it.symbol)}
                target="_blank"
                rel="noreferrer"
                className="bh-banner-chip"
              >
                <span className="bh-banner-chip__symbol">{displaySymbol}</span>
                <span className="bh-banner-chip__price">
                  {formatPrice(it.price)}
                </span>
                <span className={pctClass}>
                  {pct === 0
                    ? "0.0%"
                    : it.formattedPct ?? formatPct(pct, { sign: true })}
                </span>
              </a>
            );
          })}
        </div>
        {onRefresh && (
          <button
            type="button"
            className="bh-banner-refresh"
            onClick={onRefresh}
          >
            Refresh
          </button>
        )}
      </div>
    </div>
  );
}
