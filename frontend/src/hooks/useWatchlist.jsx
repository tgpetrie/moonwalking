import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';

const STORAGE_KEY = 'bhabit_watchlist_v2';

const WatchlistContext = createContext(null);

export function WatchlistProvider({ children }) {
  const value = useMemo(() => createWatchlistApi(), []);
  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
}

WatchlistProvider.propTypes = {
  children: PropTypes.node,
};

export function useWatchlistContext() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error('useWatchlistContext must be used within WatchlistProvider');
  return ctx;
}

export function useWatchlist() {
  return useWatchlistContext();
}

function createWatchlistApi() {
  const [store, setStore] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    } catch {
      // ignore storage failures
    }
  }, [store]);

  const has = (symbol) => Boolean(symbol && store[symbol]);

  const add = (symbol, priceNow) => {
    if (!symbol) return;
    const numeric = typeof priceNow === 'number' && !Number.isNaN(priceNow) ? priceNow : null;
    setStore((prev) => ({
      ...prev,
      [symbol]: { price: numeric, at: Date.now() },
    }));
  };

  const remove = (symbol) => {
    if (!symbol) return;
    setStore((prev) => {
      if (!prev[symbol]) return prev;
      const next = { ...prev };
      delete next[symbol];
      return next;
    });
  };

  const baselineFor = (symbol) => (symbol ? store[symbol] : undefined);

  const toggle = (symbol, priceNow) => {
    if (!symbol) return;
    if (has(symbol)) remove(symbol);
    else add(symbol, priceNow);
  };

  const list = Object.keys(store);

  return {
    has,
    add,
    remove,
    baselineFor,
    toggle,
    list,
    loading: false,
    saving: false,
    all: store,
  };
}
