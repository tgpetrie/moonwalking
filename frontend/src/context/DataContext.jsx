import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

const DataContext = createContext(null);

export function DataProvider({ children, pollMs = 15000 }) {
  const [data, setData] = useState(null);       // aggregated component data
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      async function get(path) {
        try {
          const r = await fetch(path);
          if (!r.ok) return null;
          return await r.json();
        } catch (_e) {
          return null;
        }
      }

      const [g1m, g3m, l3m, topbar, b1h] = await Promise.all([
        get("/api/component/gainers-table-1min"),
        get("/api/component/gainers-table"),
        get("/api/component/losers-table"),
        get("/api/component/top-movers-bar"),
        get("/api/component/banner-volume-1h"),
      ]);

      const agg = {
        data: {
          gainers_1m: Array.isArray(g1m?.data) ? g1m.data : [],
          gainers_3m: Array.isArray(g3m?.data) ? g3m.data : [],
          losers_3m: Array.isArray(l3m?.data) ? l3m.data : [],
          banner_1h: Array.isArray(b1h?.data)
            ? b1h.data
            : Array.isArray(topbar?.data)
            ? topbar.data
            : [],
        },
      };
      setData(agg);
      setError(null);
    } catch (err) {
      console.error("[data] failed:", err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, pollMs);
    return () => clearInterval(id);
  }, [fetchData, pollMs]);

  return (
    <DataContext.Provider value={{ data, loading, error, refetch: fetchData }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error("useData must be used inside DataProvider");
  return ctx;
}

// backwards-compat alias
export const useDataContext = useData;
