import React, { createContext, useContext, useMemo, useState, useEffect } from "react";

const WatchlistCtx = createContext(null);

export function WatchlistProvider({ children }) {
  const STORAGE_KEY = 'crypto_watchlist';

  const [symbols, setSymbols] = useState(() => new Set());

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
  const arr = parsed.map((it) => (typeof it === 'string' ? it : (it?.symbol) || '')).filter(Boolean);
      if (arr.length) setSymbols(new Set(arr));
    } catch (e) {
      console.warn('WatchlistProvider hydrate error', e);
    }
  }, []);

  // Persist when symbols change
  useEffect(() => {
    try {
      const arr = Array.from(symbols || []);
      // Persist as objects (compat with existing addToWatchlist format)
      const toStore = arr.map((s) => ({ symbol: s }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
    } catch (e) {
      console.warn('WatchlistProvider persist error', e);
    }
  }, [symbols]);

  const toggle = (sym) => {
    if (!sym) return;
    setSymbols((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym); else next.add(sym);
      return next;
    });
  };

  const isWatched = (sym) => {
    if (!sym) return false;
    try {
      return symbols instanceof Set ? symbols.has(sym) : false;
    } catch (e) {
      return false;
    }
  };

  const value = useMemo(() => ({ symbols, toggle, isWatched }), [symbols]);
  return <WatchlistCtx.Provider value={value}>{children}</WatchlistCtx.Provider>;
}

export function useWatchlist() {
  return useContext(WatchlistCtx);
}
