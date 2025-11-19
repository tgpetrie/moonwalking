import React, { useMemo } from "react";
import { map1hPriceBannerItemBase, formatPrice, formatPct, tickerFromSymbol } from "../utils/format";

function buildCoinbaseUrl(symbol) {
  if (!symbol) return "#";
  let pair = symbol;
  if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
    pair = `${pair}-USD`;
  }
  return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
}

export default function TopBannerScroll({ rows = [], onRefresh }) {
  const rawItems = Array.isArray(rows) ? rows : [];

  const items = useMemo(() => {
    const mapped = rawItems
      .map((row) => map1hPriceBannerItemBase(row))
      .filter((it) => it && it.currentPrice != null && it.pctChange !== 0)
      .sort((a, b) => b.pctChange - a.pctChange)
      .slice(0, 20)
      .map((it, index) => ({ ...it, rank: index + 1 }));
    return mapped;
  }, [rawItems]);

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
        <div className="bh-banner-strip bh-banner-strip--price">
          <div className="bh-banner-strip__inner bh-banner-strip__inner--scroll">
            {[...items, ...items].map((it, i) => {
              const pct = Number(it?.pctChange ?? 0);
              const chipState = pct > 0 ? "is-gain" : pct < 0 ? "is-loss" : "";
              const displaySymbol = it.symbol
                ? tickerFromSymbol(it.symbol)
                : "--";
              const rank = (i % items.length) + 1;

              return (
                <a
                  key={`${it.symbol || "item"}-${i}`}
                  href={buildCoinbaseUrl(it.symbol)}
                  target="_blank"
                  rel="noreferrer"
                  className={`bh-banner-chip bh-banner-chip--price ${chipState}`}
                >
                  <span className="bh-banner-chip__rank">{rank}</span>
                  <span className="bh-banner-chip__symbol">{displaySymbol}</span>
                  <span className="bh-banner-chip__price">
                    {formatPrice(it.currentPrice)}
                  </span>
                  <span className="bh-banner-chip__pct">
                    {formatPct(pct, { sign: true })}
                  </span>
                </a>
              );
            })}
          </div>
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
