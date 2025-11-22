import React, { useEffect, useMemo, useState } from "react";
import { map1hPriceBannerItemBase, formatPrice, formatPct, tickerFromSymbol } from "../utils/format";
import PanelShell from "./ui/PanelShell";
import StatusGate from "./ui/StatusGate";
import SkeletonBlock from "./ui/SkeletonBlock";

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
  onRefresh,
  historyMinutes = 0,
  loading = false,
  error = null,
}) {
  const rawItems = Array.isArray(rows) && rows.length ? rows : Array.isArray(items) ? items : [];

  const mappedItems = useMemo(() => {
    const mapped = rawItems
      .map((row) => map1hPriceBannerItemBase(row))
      .filter((it) => it && it.currentPrice != null && it.pctChange !== 0)
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
  const shouldScroll = (source?.length || 0) >= 15;
  const looped = shouldScroll ? [...source, ...source] : source;
  const required = 60;
  const panelStatus =
    error ? "error" :
    mappedItems.length > 0 ? "ready" :
    loading ? "loading" :
    historyMinutes < required ? "loading" : "empty";

  return (
    <PanelShell title="1H PRICE">
      <StatusGate
        status={panelStatus}
        skeleton={
          <div className="bh-banner-wrap">
            <SkeletonBlock lines={2} />
          </div>
        }
        empty={
          <div className="bh-banner-wrap">
            <div className="ticker bh-banner">
              <div className="bh-banner-track">
                <span className="state-copy">No movers yet.</span>
              </div>
            </div>
          </div>
        }
        error={<div className="state-copy">Feed hiccup. Retrying.</div>}
      >
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
      </StatusGate>
    </PanelShell>
  );
}
