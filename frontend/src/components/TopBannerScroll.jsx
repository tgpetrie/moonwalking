import React, { useEffect, useMemo, useState } from "react";
import { map1hPriceBannerItemBase, formatPrice, formatPct, tickerFromSymbol } from "../utils/format";
import StatusGate from "./ui/StatusGate";
import SkeletonBlock from "./ui/SkeletonBlock";
import { useDataFeed } from "../hooks/useDataFeed";

function buildCoinbaseUrl(symbol) {
  if (!symbol) return "#";
  let pair = symbol;
  if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
    pair = `${pair}-USD`;
  }
  return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
}

export default function TopBannerScroll({
  rows = [],
  items = [],
  loading = false,
  error = null,
}) {
  const { data, isLoading: feedLoading, isError: feedError } = useDataFeed();
  // Normalize incoming props to an array. Accept either `rows`/`items` arrays or
  // objects like { data: [...] } that some endpoints return.
  const feedRows = useMemo(() => {
    const list = data?.banner_1h_price || data?.banner_1h || data?.banner_price_1h;
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [data]);

  const rawItems = useMemo(() => {
    if (Array.isArray(rows) && rows.length) return rows;
    if (rows && Array.isArray(rows.data)) return rows.data;
    if (Array.isArray(items) && items.length) return items;
    if (items && Array.isArray(items.data)) return items.data;
    if (feedRows.length) return feedRows;
    return [];
  }, [rows, items, feedRows]);

  const mappedItems = useMemo(() => {
    const mapped = rawItems
      .map((row) => map1hPriceBannerItemBase(row))
      .filter((it) => it && it.currentPrice != null)
      .sort((a, b) => b.pctChange - a.pctChange)
      .slice(0, 20);
    return mapped;
  }, [rawItems]);

  // Throttle visible updates so the banner can loop for a while
  // without jarringly swapping tokens every `/data` poll.
  const [displayItems, setDisplayItems] = useState(mappedItems);

  useEffect(() => {
    if (!mappedItems.length) return;

    // On first non-empty payload, seed immediately
    setDisplayItems((prev) => (prev?.length ? prev : mappedItems));

    const id = setInterval(() => {
      setDisplayItems(mappedItems);
    }, 60000); // refresh visible banner items at most once per minute

    return () => clearInterval(id);
  }, [mappedItems]);

  const source = displayItems && displayItems.length ? displayItems : mappedItems;
  const looped = source && source.length ? [...source, ...source] : [];
  const panelStatus =
    error || feedError ? "error" :
    mappedItems.length > 0 ? "ready" :
    (loading || feedLoading) ? "loading" :
    "empty";

  return (
    <StatusGate
      status={panelStatus}
      skeleton={
        <div className="bh-banner-wrap">
          <SkeletonBlock lines={2} />
        </div>
      }
      empty={
        <div className="bh-banner-wrap">
          <div className="bh-banner-track">
            <span className="state-copy">No movers yet.</span>
          </div>
        </div>
      }
      error={<div className="state-copy">Feed hiccup. Retrying.</div>}
    >
      <div className="bh-banner-wrap">
        <div className="bh-banner-track">
          {(looped.length ? looped : [{ symbol: "--", currentPrice: 0, pctChange: 0 }]).map((it, i) => {
            if (!it) return null;
            const baseLen = source.length || 1;
            const pct = Number(it?.pctChange ?? 0);
            const pctClass =
              pct > 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--gain"
                : pct < 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--loss"
                : "bh-banner-chip__pct bh-banner-chip__pct--flat";
            const displaySymbol = it.symbol ? tickerFromSymbol(it.symbol) : "--";
            const rank = baseLen > 0 ? (i % baseLen) + 1 : i + 1;

            return (
              <a
                key={`${it.symbol || "item"}-${i}`}
                href={buildCoinbaseUrl(it.symbol)}
                target="_blank"
                rel="noreferrer"
                className={`bh-banner-chip bh-banner-chip--price ${
                  pct > 0 ? "is-gain" : pct < 0 ? "is-loss" : "is-flat"
                }`}
              >
                <span className="bh-banner-chip__rank">{rank}</span>
                <span className="bh-banner-chip__symbol">{displaySymbol}</span>
                <span className="bh-banner-price bh-banner-chip__price">
                  {formatPrice(it.currentPrice)}
                </span>
                <span className={pctClass}>
                  {formatPct(pct, { sign: true })}
                </span>
              </a>
            );
          })}
        </div>
      </div>
    </StatusGate>
  );
}
