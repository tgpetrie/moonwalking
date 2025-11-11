import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const KEY = "bhabit_watchlist_v2";
const WatchlistCtx = createContext(null);

// helper: turn the old object shape into the new array shape
function normalizeStored(value) {
  if (!value) return [];
  // If it is already an array, just return it
  if (Array.isArray(value)) return value;

  // If it's an object from the old version, convert to array
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

  // Anything else -> start fresh
  return [];
}

export function WatchlistProvider({ children }) {
  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return normalizeStored(parsed);
    } catch (e) {
      console.warn("[watchlist] failed to read storage, resetting", e);
      return [];
    }
  });

  // always store as array
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch (e) {
      console.warn("[watchlist] failed to write storage", e);
    }
  }, [items]);

  const has = useCallback((symbol) => items.some((i) => i.symbol === symbol), [
    items,
  ]);

  const add = useCallback(({ symbol, price }) => {
    if (!symbol) return;
    setItems((prev) => {
      // if already there, keep it
      if (prev.some((i) => i.symbol === symbol)) return prev;
      return [
        ...prev,
        {
          symbol,
          baseline: typeof price === "number" ? price : null,
          current: typeof price === "number" ? price : null,
        },
      ];
    });
  }, []);

  const remove = useCallback((symbol) => {
    setItems((prev) => prev.filter((i) => i.symbol !== symbol));
  }, []);

  // called from App when /data updates
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
    <WatchlistCtx.Provider
      value={{ items, has, add, remove, refreshFromData }}
    >
      {children}
    </WatchlistCtx.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistCtx);
  if (!ctx) {
    throw new Error("useWatchlist must be used inside WatchlistProvider");
  }
  return ctx;
}
