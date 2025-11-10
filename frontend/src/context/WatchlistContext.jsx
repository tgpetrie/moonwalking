import React, { createContext, useContext, useState, useCallback } from "react";

const STORAGE_KEY = "bhabit_watchlist_v2";
const WatchlistCtx = createContext(null);

function loadInitial() {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

export function WatchlistProvider({ children }) {
  const [items, setItems] = useState(loadInitial);

  const persist = (next) => {
    setItems(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  };

  const has = useCallback(
    (symbol) => items.some((it) => it.symbol === symbol),
    [items]
  );

  const add = useCallback(
    ({ symbol, price }) => {
      if (!symbol) return;
      if (items.some((it) => it.symbol === symbol)) return;
      const baseline = typeof price === "number" ? price : null;
      const next = [
        ...items,
        {
          symbol,
          baseline,
          current: price ?? null,
        },
      ];
      persist(next);
    },
    [items]
  );

  const remove = useCallback(
    (symbol) => {
      persist(items.filter((it) => it.symbol !== symbol));
    },
    [items]
  );

  const refreshFromData = useCallback(
    (bySymbol) => {
      if (!bySymbol) return;
      const next = items.map((it) => {
        const live = bySymbol[it.symbol];
        if (live && typeof live.current_price === "number") {
          return { ...it, current: live.current_price };
        }
        return it;
      });
      persist(next);
    },
    [items]
  );

  return (
    <WatchlistCtx.Provider
      value={{ items, has, add, remove, refreshFromData }}
    >
      {children}
    </WatchlistCtx.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistCtx);
  if (!ctx) throw new Error("useWatchlist must be used inside provider");
  return ctx;
}
