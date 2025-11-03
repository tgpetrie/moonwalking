import { useEffect, useState, useRef } from "react";

const safeFetch = async (url) => {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    const json = await res.json();
    return json || [];
  } catch (e) {
    console.warn("useDataFeed fetch failed", url, e);
    return [];
  }
};

export function useDataFeed(pollMs = 5000) {
  const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:5001";
  const [banner1h, setBanner1h] = useState([]);
  const [vol1h, setVol1h] = useState([]);
  const [gainers1m, setGainers1m] = useState([]);
  const [gainers3m, setGainers3m] = useState([]);
  const [losers3m, setLosers3m] = useState([]);

  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  useEffect(() => {
    let alive = true;
    const fetchAll = async () => {
      const [b1, v1, g1, g3, l3] = await Promise.all([
        safeFetch(`${API}/api/banner/price1h`),
        safeFetch(`${API}/api/banner/volume1h`),
        safeFetch(`${API}/api/component/gainers1m`),
        safeFetch(`${API}/api/component/gainers3m`),
        safeFetch(`${API}/api/component/losers3m`),
      ]);
      if (!alive || !mounted.current) return;
      setBanner1h(Array.isArray(b1) ? b1 : []);
      setVol1h(Array.isArray(v1) ? v1 : []);
      // normalize if backend wraps in { data: [] }
      setGainers1m(Array.isArray(g1) ? g1 : g1?.data ?? []);
      setGainers3m(Array.isArray(g3) ? g3 : g3?.data ?? []);
      setLosers3m(Array.isArray(l3) ? l3 : l3?.data ?? []);
    };

    fetchAll();
    const id = setInterval(fetchAll, pollMs);
    return () => { alive = false; clearInterval(id); };
  }, [API, pollMs]);

  return { banner1h, vol1h, gainers1m, gainers3m, losers3m };
}

export default useDataFeed;
