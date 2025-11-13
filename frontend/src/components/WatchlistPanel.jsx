import React, { useMemo, useState } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { formatPrice, formatPct } from "../utils/format";

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

        {filtered.length === 0 && <div className="panel-empty">Star or add a token to pin it here.</div>}

        <div className="wl-list">
          {filtered.map((it) => {
            const pct = deltaPct(it.baseline, it.current);
            return (
              <div key={it.symbol} className="wl-row">
                <div className="wl-symbol">{it.symbol.replace(/-(USD|USDT|PERP)$/i, "")}</div>
                <div className="wl-price">{formatPrice(it.current)}</div>
                <div className="wl-delta">{pct == null ? "--" : formatPct(pct / 100)}</div>
                <div className="wl-actions">
                  <button type="button" className="bh-btn-icon" onClick={() => onInfo?.(it.symbol)}>i</button>
                  <button type="button" className="bh-btn-icon bh-btn-icon--danger" onClick={() => remove(it.symbol)}>×</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
