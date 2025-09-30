import * as React from 'react';
import PropTypes from 'prop-types';
// import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../lib/api.js'; // Disabled for localStorage-only

const Ctx = React.createContext(null);

export function WatchlistProvider({ children, refreshMs = 10000 }) {
  const value = useWatchlistInternal({ refreshMs });
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

WatchlistProvider.propTypes = {
  children: PropTypes.node,
  refreshMs: PropTypes.number,
};

export function useWatchlistContext() {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error('useWatchlist must be used within WatchlistProvider');
  return ctx;
}

export function useWatchlist({ refreshMs } = {}) {
  // Public hook that reads from provider; allows per-component override of refreshMs via provider props
  return useWatchlistContext();
}

function useWatchlistInternal({ refreshMs = 10000 } = {}) {
  const [list, setList] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const lastLoadRef = React.useRef(0);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const stored = localStorage.getItem('watchlist');
      const wl = stored ? JSON.parse(stored) : [];
      setList(Array.isArray(wl) ? wl : []);
    } finally {
      setLoading(false);
      lastLoadRef.current = Date.now();
    }
  }, []);

  // Optimistic toggle with localStorage sync
  const toggle = React.useCallback(async (symbol) => {
    const sym = String(symbol || '').toUpperCase();
    if (!sym) return;
    setSaving(true);
    const wasIn = list.includes(sym);
    // optimistic update
    const newList = wasIn ? list.filter((s) => s !== sym) : [...list, sym];
    setList(newList);
  try {
      localStorage.setItem('watchlist', JSON.stringify(newList));
    } catch (e) {
      // rollback on failure silently; persistence layer failed
      setList(list);
    } finally {
      setSaving(false);
    }
  }, [list]);

  // Initial load + polling to keep in sync with other tabs/devices
  React.useEffect(() => {
    load();
    if (!refreshMs) return;
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);

  return { list, loading, saving, load, toggle, setList };
}
