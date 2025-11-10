import React, { createContext, useContext, useMemo, useState, useEffect } from "react";

const Ctx = createContext(null);
const KEY = "bhabit_watchlist_v2";

export function WatchlistProvider({ children }) {
  const [store, setStore] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "{}");
    } catch {
      return {};
    }
  });

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(store));
  }, [store]);

  const api = useMemo(
    () => ({
      has: (s) => !!store[s],
      add: (s, priceNow) =>
        setStore((m) =>
          typeof priceNow === "number"
            ? { ...m, [s]: { price: priceNow, at: Date.now() } }
            : m
        ),
      remove: (s) =>
        setStore((m) => {
          const { [s]: _, ...rest } = m;
          return rest;
        }),
      baselineFor: (s) => store[s],
    }),
    [store]
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useWatchlist() {
  return useContext(Ctx);
}
