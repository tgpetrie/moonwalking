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
            ? { ...m, [s]: { price: priceNow, current: priceNow, at: Date.now() } }
            : m
        ),
      remove: (s) =>
        setStore((m) => {
          const { [s]: _, ...rest } = m;
          return rest;
        }),
      baselineFor: (s) => store[s],
      // derive arrays for rendering
      symbols: Object.keys(store),
      items: Object.entries(store).map(([symbol, v]) => ({
        symbol,
        baselinePrice: v?.price,
        currentPrice: v?.current,
        at: v?.at,
      })),
      // New: refresh prices from a symbol→row map (supports {price} or {current_price})
      refreshFromData: (bySymbol = {}) =>
        setStore((m) => {
          let changed = false;
          const next = { ...m };
          for (const key of Object.keys(m)) {
            const row = bySymbol[key];
            const p = row?.price ?? row?.current_price;
            if (typeof p === "number" && next[key]?.current !== p) {
              next[key] = { ...next[key], current: p };
              changed = true;
            }
          }
          return changed ? next : m;
        }),
      // Update current prices without altering baseline price
      reconcilePrices: (priceMap = {}) =>
        setStore((m) => {
          let changed = false;
          const next = { ...m };
          for (const key of Object.keys(m)) {
            const p = priceMap[key];
            if (typeof p === "number" && m[key]?.current !== p) {
              next[key] = { ...m[key], current: p };
              changed = true;
            }
          }
          return changed ? next : m;
        }),
    }),
    [store]
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useWatchlist() {
  return useContext(Ctx);
}
