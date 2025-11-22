import React, { useMemo, useState } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { formatPrice, formatPct } from "../utils/format";
import TokenRow from "./TokenRow.jsx";

function deltaPct(baseline, current) {
  if (baseline == null || current == null) return null;
  return ((current - baseline) / baseline) * 100;
}

export default function WatchlistPanel({ title = "WATCHLIST", onInfo }) {
  const { items, add, remove } = useWatchlist();
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const term = q.trim().toUpperCase();
    if (!term) return items;
    return items.filter((i) => i.symbol.toUpperCase().includes(term));
  }, [items, q]);

  const tryAdd = (e) => {
    e.preventDefault();
    const sym = q.trim().toUpperCase();
    if (!sym) return;
    add({ symbol: sym, price: null });
    setQ("");
  };

  return (
    <section className="panel bh-watchlist">
      <div className="panel-header">
        <h2 className="panel-title">{title}</h2>
        <div className="panel-line" />
      </div>
      <div className="panel-body">
        <form className="wl-search" onSubmit={tryAdd}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search & add coin (e.g. BTC, ETH)" />
          <div className="wl-search-underline" />
        </form>

        {filtered.length === 0 ? (
          <div className="panel-empty">Star or add a token to pin it here.</div>
        ) : (
          <div className="wl-list">
            {filtered.map((it, index) => {
              const pct = deltaPct(it.baseline, it.current);
              const displaySymbol = it.symbol.replace(/-(USD|USDT|PERP)$/i, "");
              const rowType =
                pct == null ? undefined : pct >= 0 ? "gainer" : "loser";

              return (
                <TokenRow
                  key={it.symbol}
                  rank={index + 1}
                  symbol={displaySymbol}
                  currentPrice={it.current}
                  previousPrice={it.baseline}
                  changePct={pct}
                  rowType={rowType}
                  onInfo={onInfo}
                />
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
