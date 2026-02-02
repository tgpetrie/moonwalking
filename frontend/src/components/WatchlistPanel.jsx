import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { tickerFromSymbol } from "../utils/format";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { baselineOrNull, toFiniteNumber } from "../utils/num.js";

const parseLooseNumber = (v) => {
  if (v == null) return null;
  if (typeof v === "string") {
    const s = v.trim().replace(/,/g, "").replace(/[$]/g, "");
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }
  return Number.isFinite(v) ? v : null;
};

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
  const { items, add, toggle } = useWatchlist();
  const { data, lastGoodLatestBySymbol, getActiveAlert } = useDataFeed();
  const payload = data?.data ?? data ?? {};
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [addError, setAddError] = useState("");
  const [spotUniverse, setSpotUniverse] = useState([]);
  const priceCacheRef = useRef(new Map());

  function canonize(value) {
    const canon = tickerFromSymbol(value) || value;
    return typeof canon === "string" ? canon.toUpperCase() : null;
  }

  const liveBySymbol = useMemo(() => {
    const latest = payload.latest_by_symbol || {};
    const fallback = lastGoodLatestBySymbol || {};
    const merged = {};
    const ingest = (source) => {
      Object.entries(source || {}).forEach(([k, v]) => {
        const canon = canonize(v?.symbol ?? k);
        if (canon) merged[canon] = v;
        merged[String(k).toUpperCase()] = v;
      });
    };
    // Cached baseline first, live data wins on overlap
    ingest(fallback);
    ingest(latest);
    return merged;
  }, [payload, lastGoodLatestBySymbol]);

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
    const seen = new Set();
    const addEntry = (symbol, details = null) => {
      const canon = canonize(symbol);
      if (!canon || seen.has(canon)) return;
      const livePrice = baselineOrNull(parseLooseNumber(pickPrice(details || liveBySymbol[canon])));
      pool.push({
        symbol: canon,
        display: canon,
        price: livePrice,
        hasPrice: Number.isFinite(livePrice) && livePrice > 0,
      });
      seen.add(canon);
    };

    spotUniverse.forEach((sym) => addEntry(sym));
    Object.entries(liveBySymbol).forEach(([rawSymbol, details]) => addEntry(rawSymbol, details));
    return pool;
  }, [liveBySymbol, spotUniverse]);

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
      const canonSymbol = String(entry.symbol || "").toUpperCase();
      const live = liveBySymbol[canonSymbol] || {};

      // Get current price from live feed
      const currentPrice = baselineOrNull(parseLooseNumber(pickPrice(live)));

      // Get baseline (price when added) - this NEVER changes unless user removes + re-adds
      const addedPrice = baselineOrNull(entry.addedPrice);

      // Calculate % change since added
      const changeWatch = deltaPct(addedPrice, currentPrice);

      return {
        key: `${canonSymbol}-${index}`,
        rank: index + 1,
        symbol: canonSymbol,
        ...live, // spread live data for badges, base name, etc.
        current_price: currentPrice,
        previous_price: addedPrice,        // baseline for "previous price" line
        change_watch: changeWatch,         // % change since added
        watch_added_at: entry.addedAt,
      };
    });
  }, [items, liveBySymbol]);

  const livePriceForSymbol = useCallback(
    (sym) => {
      const canon = canonize(sym);
      if (!canon) return null;
      const live = liveBySymbol[canon];
      return baselineOrNull(parseLooseNumber(pickPrice(live)));
    },
    [liveBySymbol]
  );

  const fetchSpotPrice = useCallback(async (symbol) => {
    const canon = canonize(symbol);
    if (!canon) return null;
    const cached = priceCacheRef.current.get(canon);
    if (cached && Number.isFinite(cached)) return cached;
    const quotes = ["USD", "USDC"];
    for (const quote of quotes) {
      try {
        const res = await fetch(`https://api.coinbase.com/v2/prices/${canon}-${quote}/spot`);
        if (!res.ok) continue;
        const json = await res.json();
        const amount = parseLooseNumber(json?.data?.amount);
        if (Number.isFinite(amount) && amount > 0) {
          priceCacheRef.current.set(canon, amount);
          return amount;
        }
      } catch {
        // ignore and try next quote
      }
    }
    return null;
  }, []);

  useEffect(() => {
    const CACHE_KEY = "bh_spot_universe_v1";
    const TS_KEY = "bh_spot_universe_ts_v1";
    const TTL_MS = 6 * 60 * 60 * 1000;
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      const ts = Number(localStorage.getItem(TS_KEY) || 0);
      if (Array.isArray(cached) && cached.length && Date.now() - ts < TTL_MS) {
        setSpotUniverse(cached);
        return;
      }
    } catch {}

    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch("https://api.exchange.coinbase.com/products");
        if (!res.ok) return;
        const data = await res.json();
        const symbols = Array.isArray(data)
          ? data
              .filter((p) => p && p.status === "online" && (p.quote_currency === "USD" || p.quote_currency === "USDC"))
              .map((p) => String(p.base_currency || "").toUpperCase())
              .filter(Boolean)
          : [];
        const uniq = Array.from(new Set(symbols));
        if (!cancelled && uniq.length) {
          setSpotUniverse(uniq);
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify(uniq));
            localStorage.setItem(TS_KEY, String(Date.now()));
          } catch {}
        }
      } catch {
        // silently ignore; manual add still works
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const addProduct = useCallback(
    async (entry) => {
      if (!entry?.display) return;
      const sym = canonize(entry.display);
      if (!sym || watchlistSet.has(sym)) return;
      let livePrice = Number.isFinite(entry?.price) ? entry.price : livePriceForSymbol(sym);
      if (!Number.isFinite(livePrice)) {
        livePrice = await fetchSpotPrice(sym);
      }
      if (!Number.isFinite(livePrice)) {
        setAddError(`No spot price found for ${sym}.`);
        return;
      }
      add({ symbol: sym, price: livePrice });
      // Dev-only sanity check that clicks flow through even with overlays
      if (import.meta.env.DEV) {
        console.debug("[watchlist] add", sym, livePrice);
      }
      setAddError("");
      setQuery("");
      setIsOpen(false);
    },
    [add, fetchSpotPrice, livePriceForSymbol, watchlistSet]
  );

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (suggestions.length) {
        await addProduct(suggestions[0]);
        return;
      }
      if (!normalized) return;
      const direct = searchPool.find((p) => p.symbol === normalized);
      if (direct) {
        await addProduct(direct);
        return;
      }
      await addProduct({ display: normalized, symbol: normalized });
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
    <>
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
              setAddError("");
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
                      {isPinned(entry.symbol)
                        ? "Pinned"
                        : entry.hasPrice
                        ? "Add"
                        : "Lookup"}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {addError ? <div className="bh-watchlist-error">{addError}</div> : null}
      </form>

      {!items.length && (
        <div className="bh-watchlist-empty">
          Star a token or search to pin it here.
        </div>
      )}

      {items.length > 0 && (
        <>
          {watchlistTokens.map((token, index) => (
            <TokenRowUnified
              key={token.key ?? `${token.symbol}-${index}`}
              token={token}
              rank={index + 1}
              changeField="change_watch"
              side={token.change_watch != null && token.change_watch < 0 ? "loser" : "gainer"}
              onToggleWatchlist={handleToggle}
              onInfo={onInfo}
              isWatchlisted
              activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(token.symbol) : null}
            />
          ))}
        </>
      )}
    </>
  );
}
