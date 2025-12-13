import React, { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";
import { API_BASE_URL } from "../api";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

// shallow-ish equality good enough for our aggregated shapes
const shallowEqual = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const ak = Object.keys(a), bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  for (const k of ak) {
    const av = a[k], bv = b[k];
    if (Array.isArray(av) && Array.isArray(bv)) {
      if (av.length !== bv.length) return false;
      for (let i = 0; i < av.length; i++) if (av[i] !== bv[i]) return false;
    } else if (av !== bv) return false;
  }
  return true;
};

export function DataProvider({ children, pollMs = 5000 }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const lastRef = useRef(null);
  const abortRef = useRef(null);

  const fetchUnified = useCallback(async () => {
    try {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();
      const res = await fetch(`${API_BASE_URL}/api/data`, { signal: abortRef.current.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();

      const normalized = {
        gainers_1m: json.data?.gainers_1m ?? json.gainers_1m ?? json.gainers1m ?? [],
        gainers_3m: json.data?.gainers_3m ?? json.gainers_3m ?? json.gainers3m ?? [],
        losers_3m:  json.data?.losers_3m  ?? json.losers_3m  ?? json.losers3m  ?? [],
        top_banner_1h: json.data?.banner_1h ?? json.banner_1h_price ?? json.top_banner_1h ?? json.banner_1h ?? [],
        volume_banner_1h: json.data?.volume_banner_1h ?? json.banner_1h_volume ?? json.volume_banner_1h ?? [],
        updated_at: json.updated_at ?? Date.now(),
      };

      if (!shallowEqual(lastRef.current, normalized)) {
        lastRef.current = normalized;
        setData(normalized);
      }
      setError(null);
      setLoading(false);
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.warn('[DataContext] Fetch failed:', e.message);
      setError(e);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    
    const doFetch = async () => {
      if (!mounted) return;
      await fetchUnified();
    };

    doFetch();
    const id = setInterval(doFetch, pollMs);
    
    return () => {
      mounted = false;
      clearInterval(id);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [fetchUnified, pollMs]);

  const value = useMemo(() => ({ data, error, loading, refetch: fetchUnified }), [data, error, loading, fetchUnified]);
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
