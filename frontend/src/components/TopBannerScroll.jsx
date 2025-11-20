import React, { useEffect, useMemo, useState } from "react";
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
      .slice(0, 20);
    return mapped;
  }, [rawItems]);

  // Throttle visible updates so the banner can loop for a while
  // without jarringly swapping tokens every `/data` poll.
  const [displayItems, setDisplayItems] = useState(items);

  useEffect(() => {
    if (!items.length) return;

    // On first non-empty payload, seed immediately
    setDisplayItems((prev) => (prev?.length ? prev : items));

    const id = setInterval(() => {
      setDisplayItems(items);
    }, 60000); // refresh visible banner items at most once per minute

    return () => clearInterval(id);
  }, [items]);

  const source = displayItems && displayItems.length ? displayItems : items;
  const shouldScroll = (source?.length || 0) >= 15;
  const looped = shouldScroll ? [...source, ...source] : source;

  if (!items.length) {
    return (
      <section className="banner-section banner-section--price">
        <div className="banner-heading">
          <span className="banner-heading__label">1H PRICE</span>
          <span className="banner-heading__rail" />
        </div>
        <div className="bh-banner-wrap">
          <div className="ticker bh-banner">
            <div className="bh-banner-track">
              <span className="banner-empty">No 1h price-change data available.</span>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="banner-section banner-section--price">
      <div className="banner-heading">
        <span className="banner-heading__label">1H PRICE</span>
        <span className="banner-heading__rail" />
      </div>
      <div className="bh-banner-wrap">
        <div className="ticker bh-banner">
          <div className="bh-banner-strip bh-banner-strip--price">
            <div
              className={
                "bh-banner-strip__inner" +
                (shouldScroll ? " bh-banner-strip__inner--scroll" : "")
              }
            >
            {looped.map((it, i) => {
              if (!it) return null;
              const baseLen = source.length || 1;
              const pct = Number(it?.pctChange ?? 0);
              const chipState = pct > 0 ? "is-gain" : pct < 0 ? "is-loss" : "";
              const displaySymbol = it.symbol
                ? tickerFromSymbol(it.symbol)
                : "--";
              const rank = (i % baseLen) + 1;

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
    </section>
  );
}
