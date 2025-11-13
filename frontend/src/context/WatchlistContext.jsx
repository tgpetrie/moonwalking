import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const STORAGE_KEY = "bhabit_watchlist_v2";
const WatchlistContext = createContext(null);

// normalize old shapes -> array of { symbol, baseline, current }
function normalizeStored(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "object") {
    return Object.keys(value).map((symbol) => {
      const entry = value[symbol] || {};
      import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

      const KEY = "bhabit_watchlist_v2";
      const Ctx = createContext(null);

      export function WatchlistProvider({ children }) {
        const [items, setItems] = useState(() => {
          try {
            return JSON.parse(localStorage.getItem(KEY)) || [];
          } catch {
            return [];
          }
        });

        useEffect(() => {
          try {
            localStorage.setItem(KEY, JSON.stringify(items));
          } catch {
            // ignore
          }
        }, [items]);

        const has = useCallback((symbol) => items.some((i) => i.symbol === symbol), [items]);

        const add = useCallback(({ symbol, price }) => {
          setItems((prev) => {
            if (!symbol || prev.some((i) => i.symbol === symbol)) return prev;
            const v = typeof price === "number" ? price : null;
            return [...prev, { symbol, baseline: v, current: v }];
          });
        }, []);

        const remove = useCallback((symbol) => {
          setItems((prev) => prev.filter((i) => i.symbol !== symbol));
        }, []);

        const refreshFromData = useCallback((symbolMap) => {
          if (!symbolMap) return;
          setItems((prev) =>
            prev.map((i) => {
              const live = symbolMap[i.symbol];
              if (live?.current_price == null) return i;
              return { ...i, current: live.current_price };
            })
          );
        }, []);

        return <Ctx.Provider value={{ items, has, add, remove, refreshFromData }}>{children}</Ctx.Provider>;
      }

      export const useWatchlist = () => useContext(Ctx);
        return i;
      });
      // If nothing changed, return prev to avoid needless re-renders
      return changed ? next : prev;
    });
  }, []);

  const value = useMemo(
    () => ({ items, has, add, remove, refreshFromData }),
    [items, has, add, remove, refreshFromData]
  );

  return (
    <WatchlistContext.Provider value={value}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) {
    throw new Error("useWatchlist must be used inside WatchlistProvider");
  }
  return ctx;
}
