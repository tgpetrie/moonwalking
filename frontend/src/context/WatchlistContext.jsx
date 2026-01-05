// frontend/src/context/WatchlistContext.jsx — cleaned Watchlist v2 provider
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { tickerFromSymbol } from "../utils/format";

const STORAGE_KEY = "bhabit_watchlist_v2";
const WatchlistContext = createContext(null);

// Normalize symbol to uppercase for consistent comparison
const normalize = (s) => String(s || "").toUpperCase();

function readInitial() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function WatchlistProvider({ children }) {
  const [items, setItems] = useState(readInitial);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {}
  }, [items]);

  const has = useCallback((symbol) => {
    const norm = normalize(tickerFromSymbol(symbol));
    return items.some((i) => normalize(i.symbol) === norm);
  }, [items]);

  const add = useCallback(({ symbol, baseline = null, price = null }) => {
    // Accept either { symbol, baseline } or { symbol, price } for backward compatibility
    const s = normalize(tickerFromSymbol(symbol));
    setItems((prev) => {
      if (!s) return prev;
      if (prev.some((i) => normalize(i.symbol) === s)) return prev;
      const seed = baseline ?? price;
      const numeric = seed == null ? null : Number(seed);
      const addedPrice = Number.isFinite(numeric) && numeric > 0 ? numeric : null;
      if (addedPrice === null) return prev; // Don't add without valid price
      const now = Date.now();
      return [
        ...prev,
        {
          symbol: s,
          addedPrice,
          addedAt: now,
        },
      ];
    });
  }, []);

  const remove = useCallback((symbol) => {
    const s = normalize(tickerFromSymbol(symbol));
    setItems((prev) => prev.filter((i) => normalize(i.symbol) !== s));
  }, []);

  const toggle = useCallback(({ symbol, price = null }) => {
    const s = normalize(tickerFromSymbol(symbol));
    setItems((prev) => {
      if (!s) return prev;
      const existing = prev.findIndex((i) => normalize(i.symbol) === s);
      if (existing >= 0) {
        // Remove if exists
        const next = [...prev];
        next.splice(existing, 1);
        return next;
      }
      // Add if doesn't exist
      const numeric = price == null ? null : Number(price);
      const addedPrice = Number.isFinite(numeric) && numeric > 0 ? numeric : null;
      if (addedPrice === null) return prev; // Don't add without valid price
      const now = Date.now();
      return [
        { symbol: s, addedPrice, addedAt: now },
        ...prev,
      ];
    });
  }, []);

  const value = useMemo(() => ({ items, has, add, remove, toggle }), [items, has, add, remove, toggle]);

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used inside WatchlistProvider");
  return ctx;
}
