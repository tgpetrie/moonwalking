import { useMemo, useState, useCallback } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { tickerFromSymbol } from "../utils/format";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { baselineOrNull, toFiniteNumber } from "../utils/num.js";

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

function deltaPct(baseline, current) {
  const base = baselineOrNull(baseline);
  const curr = toFiniteNumber(current);
  if (base === null || curr === null) return null;
  return ((curr - base) / base) * 100;
}

export default function WatchlistPanel({ onInfo }) {
  // useWatchlist wraps useContext(WatchlistContext) to keep panel in sync with starred items.
  const { items, toggle: toggleWatchlist, add } = useWatchlist();
  const { data } = useDataFeed();
  const payload = data?.data ?? data ?? {};
  const [search, setSearch] = useState("");

  const liveBySymbol = useMemo(() => {
    const latest = payload.latest_by_symbol || {};
    const merged = {};
    Object.entries(latest).forEach(([k, v]) => {
      merged[String(k).toUpperCase()] = v;
    });
    return merged;
  }, [payload]);

  const watchlistSet = useMemo(() => {
    const set = new Set();
    items.forEach((entry) => {
      const canonSymbol = tickerFromSymbol(entry.symbol) || entry.symbol;
      if (canonSymbol) {
        set.add(canonSymbol.toUpperCase());
      }
    });
    return set;
  }, [items]);

  const searchPool = useMemo(() => {
    const pool = [];
    Object.entries(liveBySymbol).forEach(([rawSymbol, details]) => {
      const canon = tickerFromSymbol(rawSymbol) || rawSymbol;
      if (!canon) return;
      pool.push({
        symbol: canon.toUpperCase(),
        display: canon,
        price: toFiniteNumber(pickPrice(details)),
      });
    });
    return pool;
  }, [liveBySymbol]);

  const searchResults = useMemo(() => {
    const query = search.trim().toUpperCase();
    if (!query) return [];
    const seen = new Set();
    return searchPool
      .filter(({ symbol }) => symbol.includes(query))
      .filter(({ symbol }) => !watchlistSet.has(symbol))
      .filter(({ symbol }) => {
        if (seen.has(symbol)) return false;
        seen.add(symbol);
        return true;
      })
      .slice(0, 6);
  }, [search, searchPool, watchlistSet]);

  const watchlistTokens = useMemo(() => {
    if (!items.length) return [];

    return items.map((entry, index) => {
      const canonSymbol = tickerFromSymbol(entry.symbol) || entry.symbol;
      const live = liveBySymbol[canonSymbol] || {};
      const livePrice = toFiniteNumber(pickPrice(live) ?? entry.current ?? entry.baseline ?? null);
      // Previous price should be the pinned baseline from when the token was added.
      // Fall back to historical fields if needed, but never default to live price.
      const baselineOrNullValue = baselineOrNull(entry.baseline ?? entry.priceAdded ?? entry.current ?? null);
      const pct = deltaPct(baselineOrNullValue, livePrice);

      return {
        key: `${canonSymbol}-${index}`,
        rank: index + 1,
        symbol: canonSymbol,
        current_price: livePrice,
        previous_price: baselineOrNullValue,
        change_1m: pct ?? 0,
      };
    });
  }, [items, liveBySymbol]);

  const handleToggleWatchlist = (symbol, price) => {
    if (!symbol) return;
    toggleWatchlist({ symbol, price });
  };

  const handleAddFromSearch = useCallback(
    (entry) => {
      if (!entry || !entry.display) return;
      add({ symbol: entry.display, price: entry.price });
      setSearch("");
    },
    [add]
  );

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    if (searchResults.length === 0) return;
    handleAddFromSearch(searchResults[0]);
  };

  return (
    <div className="bh-panel bh-panel-full watchlist-panel">
      <form className="bh-watchlist-search" onSubmit={handleSearchSubmit}>
        <input
          type="text"
          className="bh-watchlist-search-input"
          placeholder="Search symbols to pin (e.g. BTC)"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search tokens to add to watchlist"
        />
        {search && (
          <div className="bh-watchlist-search-results">
            {searchResults.length > 0 ? (
              searchResults.map((entry) => (
                <button
                  type="button"
                  key={entry.symbol}
                  className="bh-watchlist-search-option"
                  onClick={() => handleAddFromSearch(entry)}
                >
                  <span>{entry.display}</span>
                  <span className="bh-watchlist-search-price">
                    {entry.price != null ? `$${Number(entry.price).toLocaleString()}` : "--"}
                  </span>
                </button>
              ))
            ) : (
              <div className="bh-watchlist-search-empty">No matching symbols online.</div>
            )}
          </div>
        )}
      </form>

      {!items.length && <div className="bh-watchlist-empty">Star a token or search to pin it here.</div>}

      {items.length > 0 && (
        <div className="bh-table">
          {watchlistTokens.map((token, index) => (
            <TokenRowUnified
              key={token.key ?? `${token.symbol}-${index}`}
              token={token}
              rank={index + 1}
              changeField="change_1m"
              onToggleWatchlist={handleToggleWatchlist}
              onInfo={onInfo}
              isWatchlisted
            />
          ))}
        </div>
      )}
    </div>
  );
}
