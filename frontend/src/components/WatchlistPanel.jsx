import React, { useMemo, useState } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { tickerFromSymbol } from "../utils/format";
import TokenRow from "./TokenRow.jsx";
import { useDataFeed } from "../hooks/useDataFeed";

function deltaPct(baseline, current) {
  const base = Number(baseline);
  const curr = Number(current);
  if (!Number.isFinite(base) || !Number.isFinite(curr) || base === 0) return null;
  return ((curr - base) / base) * 100;
}

const pickPrice = (source = {}) => {
  if (!source) return null;
  return (
    source.current_price ??
    source.currentPrice ??
    source.price ??
    source.last_price ??
    source.latest_price ??
    null
  );
};

export default function WatchlistPanel({ title = "WATCHLIST", onInfo, bySymbol = {} }) {
  const { items, add } = useWatchlist();
  const [q, setQ] = useState("");
  const { data } = useDataFeed();
  const payload = data?.data ?? data ?? {};

  const liveBySymbol = useMemo(() => {
    const merged = { ...(bySymbol || {}) };
    const latest = payload.latest_by_symbol || {};
    Object.entries(latest).forEach(([k, v]) => {
      merged[String(k).toUpperCase()] = v;
    });
    return merged;
  }, [bySymbol, payload]);

  const filtered = useMemo(() => {
    const term = q.trim().toUpperCase();
    if (!term) return items;
    return items.filter((i) => i.symbol.toUpperCase().includes(term));
  }, [items, q]);

  const tryAdd = (e) => {
    e.preventDefault();
    const sym = q.trim().toUpperCase();
    if (!sym) return;
    const liveKey = tickerFromSymbol(sym);
    const live = liveBySymbol[liveKey] || liveBySymbol[sym];
    const livePrice = pickPrice(live);
    add({ symbol: sym, price: livePrice });
    setQ("");
  };

  const rows = useMemo(() => {
    if (!filtered.length) return [];

    return filtered.map((entry, index) => {
      const canonSymbol = tickerFromSymbol(entry.symbol) || entry.symbol;
      const live = liveBySymbol[canonSymbol] || {};
      const livePrice = pickPrice(live) ?? entry.current ?? entry.baseline ?? null;
      const baseline = entry.baseline ?? entry.current ?? pickPrice(live);
      const pct = deltaPct(baseline, livePrice);
      const rowType = pct == null ? undefined : pct >= 0 ? "gainer" : "loser";

      return {
        key: `${canonSymbol}-${index}`,
        rank: index + 1,
        symbol: canonSymbol,
        currentPrice: livePrice,
        previousPrice: baseline,
        pctChange: pct,
        rowType,
      };
    });
  }, [filtered, liveBySymbol]);

  return (
    <section className="panel bh-watchlist">
      <header className="panel-header panel-header--watchlist">
        <div className="section-head section-head--center section-head-gain">
          <span className="section-head__label">{title}</span>
          <span className="section-head-line section-head-line-gain" />
        </div>
      </header>
      <div className="panel-body">
        <form className="wl-search" onSubmit={tryAdd}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search & add coin (e.g. BTC, ETH)" />
          <div className="wl-search-underline" />
        </form>

        {rows.length === 0 ? (
          <div className="panel-empty">Star a token to pin it here.</div>
        ) : (
          <div className="wl-list">
            {rows.map((row) => (
              <TokenRow
                key={row.key}
                rank={row.rank}
                symbol={row.symbol}
                currentPrice={row.currentPrice}
                previousPrice={row.previousPrice}
                changePct={row.pctChange}
                rowType={row.rowType}
                onInfo={onInfo}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
