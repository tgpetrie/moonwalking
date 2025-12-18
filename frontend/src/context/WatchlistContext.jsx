// frontend/src/context/WatchlistContext.jsx — cleaned Watchlist v2 provider
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { tickerFromSymbol } from "../utils/format";

const STORAGE_KEY = "bhabit_watchlist_v2";
const WatchlistContext = createContext(null);

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

  const has = useCallback((symbol) => items.some((i) => i.symbol === tickerFromSymbol(symbol)), [items]);

  const add = useCallback(({ symbol, baseline = null, price = null }) => {
    // Accept either { symbol, baseline } or { symbol, price } for backward compatibility
    const s = tickerFromSymbol(symbol);
    setItems((prev) => {
      if (!s) return prev;
      if (prev.some((i) => i.symbol === s)) return prev;
      const seed = baseline ?? price;
      const numeric = seed == null ? null : Number(seed);
      const entryPrice = Number.isFinite(numeric) ? numeric : null;
      const now = Date.now();
      return [
        ...prev,
        {
          symbol: s,
          baseline: entryPrice,
          current: entryPrice,
          priceAdded: entryPrice,
          addedAt: now,
        },
      ];
    });
  }, []);

  const remove = useCallback((symbol) => {
    const s = tickerFromSymbol(symbol);
    setItems((prev) => prev.filter((i) => i.symbol !== s));
  }, []);

  const toggle = useCallback(({ symbol, price = null }) => {
    const s = tickerFromSymbol(symbol);
    setItems((prev) => {
      if (!s) return prev;
      if (prev.some((i) => i.symbol === s)) {
        return prev.filter((i) => i.symbol !== s);
      }
      const numeric = price == null ? null : Number(price);
      const entry = Number.isFinite(numeric) ? numeric : null;
      const now = Date.now();
      return [
        ...prev,
        {
          symbol: s,
          baseline: entry,
          current: entry,
          priceAdded: entry,
          addedAt: now,
        },
      ];
    });
  }, []);

  const refreshFromData = useCallback((bySymbol = {}) => {
    setItems((prev) => prev.map((i) => {
      const live = bySymbol[i.symbol];
      if (!live) return i;
      const curr = live.current_price ?? live.price ?? i.current;
      return { ...i, current: curr };
    }));
  }, []);

  const value = useMemo(() => ({ items, has, add, remove, toggle, refreshFromData }), [items, has, add, remove, toggle, refreshFromData]);

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used inside WatchlistProvider");
  return ctx;
}
