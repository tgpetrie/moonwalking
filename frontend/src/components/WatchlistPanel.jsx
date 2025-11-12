import React, { useState } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { useData } from "../context/DataContext.jsx";
import { formatPrice } from "../utils/format.js";

export default function WatchlistPanel() {
  const { items, add, remove } = useWatchlist();
  const { data } = useData();
  const [query, setQuery] = useState("");

  const liveIndex = buildLiveIndex(data);

  function handleSubmit(e) {
    e.preventDefault();
    const sym = query.trim().toUpperCase();
    if (!sym) return;
    add({ symbol: sym });
    setQuery("");
  }

  return (
    <div className="bh-panel watchlist-panel">
      <div className="watchlist-header">
        <h3>Watchlist</h3>
      </div>
      <form onSubmit={handleSubmit} className="watchlist-search">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Add symbol e.g. SOL-USD"
        />
        <button type="submit">Add</button>
      </form>
      <div className="watchlist-items">
        {items.length === 0 && (
          <p className="watchlist-empty">Star a token or add one above.</p>
        )}
        {items.map((it) => {
          const live = liveIndex[it.symbol];
          return (
            <div key={it.symbol} className="watchlist-item-row">
              <span className="watchlist-symbol">{it.symbol}</span>
              <span className="watchlist-price">
                {live ? formatPrice(live.current_price) : "—"}
              </span>
              <button
                type="button"
                className="watchlist-remove"
                onClick={() => remove(it.symbol)}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function buildLiveIndex(data) {
  const idx = {};
  if (!data) return idx;
  // support both shapes: envelope { data: {...} } or direct data object
  const payload = data.data || data;
  if (!payload) return idx;
  const { banner_1h, gainers_3m, losers_3m, gainers_1m, losers_1m } = payload;
  [banner_1h, gainers_3m, losers_3m, gainers_1m, losers_1m].forEach((list) => {
    if (Array.isArray(list)) {
      list.forEach((t) => {
        if (t && t.symbol) idx[t.symbol] = t;
      });
    }
  });
  return idx;
}
