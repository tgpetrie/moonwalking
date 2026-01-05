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
  const { items, add, remove, toggle } = useWatchlist();
  const { data } = useDataFeed();
  const payload = data?.data ?? data ?? {};
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const liveBySymbol = useMemo(() => {
    const latest = payload.latest_by_symbol || {};
    const merged = {};
    Object.entries(latest).forEach(([k, v]) => {
      merged[String(k).toUpperCase()] = v;
    });
    return merged;
  }, [payload]);

  const canonize = (value) => {
    const canon = tickerFromSymbol(value) || value;
    return typeof canon === "string" ? canon.toUpperCase() : null;
  };

  const watchlistSet = useMemo(() => {
    const set = new Set();
    items.forEach((entry) => {
      const canonSymbol = canonize(entry.symbol);
      if (canonSymbol) set.add(canonSymbol);
    });
    return set;
  }, [items]);

  const searchPool = useMemo(() => {
    const pool = [];
    Object.entries(liveBySymbol).forEach(([rawSymbol, details]) => {
      const symbol = canonize(rawSymbol);
      if (!symbol) return;
      pool.push({
        symbol,
        display: symbol,
        price: toFiniteNumber(pickPrice(details)),
      });
    });
    return pool;
  }, [liveBySymbol]);

  const normalized = query.trim().toUpperCase();

  const suggestions = useMemo(() => {
    if (!normalized) return [];
    const hits = searchPool
      .filter(({ symbol }) => symbol.includes(normalized))
      .filter(({ symbol }) => !watchlistSet.has(symbol));
    hits.sort((a, b) => {
      const aStarts = a.symbol.startsWith(normalized) ? 0 : 1;
      const bStarts = b.symbol.startsWith(normalized) ? 0 : 1;
      if (aStarts !== bStarts) return aStarts - bStarts;
      return a.symbol.localeCompare(b.symbol);
    });
    return hits.slice(0, 8);
  }, [normalized, searchPool, watchlistSet]);

  const watchlistTokens = useMemo(() => {
    if (!items.length) return [];
    return items.map((entry, index) => {
      const canonSymbol = tickerFromSymbol(entry.symbol) || entry.symbol;
      const live = liveBySymbol[canonSymbol] || {};
      const livePrice = toFiniteNumber(
        pickPrice(live) ?? entry.current ?? entry.baseline ?? null
      );
      const baselineOrNullValue = baselineOrNull(
        entry.baseline ?? entry.priceAdded ?? entry.current ?? null
      );
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

  const addProduct = useCallback(
    (entry) => {
      if (!entry?.display) return;
      const sym = canonize(entry.display);
      if (!sym || watchlistSet.has(sym)) return;
      add({ symbol: sym, price: entry.price });
      setQuery("");
      setIsOpen(false);
    },
    [add, watchlistSet]
  );

  const handleSubmit = useCallback(
    (event) => {
      event.preventDefault();
      if (suggestions.length) {
        addProduct(suggestions[0]);
        return;
      }
      if (!normalized) return;
      const direct = searchPool.find((p) => p.symbol === normalized);
      if (direct) addProduct(direct);
    },
    [addProduct, normalized, searchPool, suggestions]
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        return;
      }
      if (event.key === "Enter") {
        handleSubmit(event);
      }
    },
    [handleSubmit]
  );

  const handleToggle = (symbol, price) => {
    if (!symbol) return;
    toggle({ symbol, price });
  };

  const isPinned = (symbol) => watchlistSet.has(canonize(symbol));

  return (
    <div className="bh-panel bh-panel--rail watchlist-panel">
      <form className="bh-watchlist-search" onSubmit={handleSubmit}>
        <div className="bh-watchlist__searchWrap">
          <input
            type="text"
            className="bh-watchlist-search-input"
            placeholder="Search symbols to pin (e.g. BTC)"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setIsOpen(true);
            }}
            aria-label="Search tokens to add to watchlist"
            onFocus={() => setIsOpen(true)}
            onBlur={(event) => {
              const related = event.relatedTarget;
              if (!related || !event.currentTarget.contains(related)) {
                setIsOpen(false);
              }
            }}
            onKeyDown={handleKeyDown}
            spellCheck={false}
            autoCapitalize="characters"
            autoCorrect="off"
          />
          {isOpen && suggestions.length > 0 && (
            <div className="bh-watchlist__dropdown">
              {suggestions.map((entry) => {
                const disabled = isPinned(entry.symbol);
                return (
                  <button
                    type="button"
                    key={entry.symbol}
                    className={`bh-watchlist__option ${
                      disabled ? "is-disabled" : ""
                    }`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => !disabled && addProduct(entry)}
                  >
                    <span className="bh-watchlist__optSym">{entry.symbol}</span>
                    <span className="bh-watchlist__optName">
                      {entry.display}
                    </span>
                    <span className="bh-watchlist__optHint">
                      {disabled ? "Pinned" : "Add"}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </form>

      {!items.length && (
        <div className="bh-watchlist-empty">
          Star a token or search to pin it here.
        </div>
      )}

      {items.length > 0 && (
        <div className="panel-row-watchlist panel-row--1m">
          <div className="bh-table">
            {watchlistTokens.map((token, index) => (
              <TokenRowUnified
                key={token.key ?? `${token.symbol}-${index}`}
                token={token}
                rank={index + 1}
                changeField="change_1m"
                onToggleWatchlist={handleToggle}
                onInfo={onInfo}
                isWatchlisted
                className="bh-row bh-row-grid"
                cellClassMap={{
                  rank: "bh-cell--rank",
                  symbol: "bh-cell--symbol",
                  name: "bh-cell--name",
                  price: "bh-cell--price",
                  pct: "bh-cell--pct",
                  actions: "bh-cell--actions",
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
