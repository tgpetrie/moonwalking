import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
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
      return {
        symbol,
        baseline: entry.baseline ?? entry.price ?? null,
        current: entry.current ?? entry.price ?? null,
      };
    });
  }
  return [];
}

export function WatchlistProvider({ children }) {
  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return normalizeStored(JSON.parse(raw));
    } catch (e) {
      console.warn("[watchlist] failed to read localStorage", e);
      return [];
    }
  });

  // persist
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.warn("[watchlist] failed to write localStorage", e);
    }
  }, [items]);

  const has = useCallback(
    (symbol) => items.some((i) => i.symbol === symbol),
    [items]
  );

  const add = useCallback(({ symbol, price }) => {
    if (!symbol) return;
    const sym = symbol.toUpperCase();
    setItems((prev) => {
      if (prev.some((i) => i.symbol === sym)) return prev;
      return [
        ...prev,
        {
          symbol: sym,
          baseline: typeof price === "number" ? price : null,
          current: typeof price === "number" ? price : null,
        },
      ];
    });
  }, []);

  const remove = useCallback((symbol) => {
    const sym = symbol.toUpperCase();
    setItems((prev) => prev.filter((i) => i.symbol !== sym));
  }, []);

  // let the app push fresh prices into the watchlist
  const refreshFromData = useCallback((symbolMap) => {
    if (!symbolMap) return;
    setItems((prev) =>
      prev.map((i) => {
        const live = symbolMap[i.symbol];
        if (live && typeof live.current_price === "number") {
          return { ...i, current: live.current_price };
        }
        return i;
      })
    );
  }, []);

  return (
    <WatchlistContext.Provider
      value={{ items, has, add, remove, refreshFromData }}
    >
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
