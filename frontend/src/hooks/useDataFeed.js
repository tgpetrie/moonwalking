import { useEffect, useState, useRef } from "react";
import { fetchJson } from "../lib/api";
import { normalizeBannerRow, normalizeTableRow } from "../lib/adapters";

const safeFetch = async (url) => {
  try {
    const json = await fetchJson(url, { cache: 'no-store' });
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
        // backend exposes component-style banner endpoints
        safeFetch(`${API}/api/component/top-banner-scroll`),
        safeFetch(`${API}/api/component/bottom-banner-scroll`),
        // map legacy frontend names to current component endpoints
        safeFetch(`${API}/api/component/gainers-table-1min`),
        safeFetch(`${API}/api/component/gainers-table-3min`),
        safeFetch(`${API}/api/component/losers-table-3min`),
      ]);
      if (!alive || !mounted.current) return;
      // normalize banner payloads: backend returns { component, data, ... }
      const rawB = Array.isArray(b1) ? b1 : (b1?.data ?? []);
      const rawV = Array.isArray(v1) ? v1 : (v1?.data ?? []);
      const rawG1 = Array.isArray(g1) ? g1 : (g1?.data ?? []);
      const rawG3 = Array.isArray(g3) ? g3 : (g3?.data ?? []);
      const rawL3 = Array.isArray(l3) ? l3 : (l3?.data ?? []);

      // map to stable frontend shapes using adapters
      try {
        setBanner1h(rawB.map((r) => normalizeBannerRow(r)));
      } catch (e) {
        console.warn('useDataFeed: banner1h normalize failed', e);
        setBanner1h(rawB);
      }
      try {
        setVol1h(rawV.map((r) => normalizeBannerRow(r)));
      } catch (e) {
        console.warn('useDataFeed: vol1h normalize failed', e);
        setVol1h(rawV);
      }

      try { setGainers1m(rawG1.map((r) => normalizeTableRow(r))); } catch (e) { setGainers1m(rawG1); }
      try { setGainers3m(rawG3.map((r) => normalizeTableRow(r))); } catch (e) { setGainers3m(rawG3); }
      try { setLosers3m(rawL3.map((r) => normalizeTableRow(r))); } catch (e) { setLosers3m(rawL3); }
    };

    fetchAll();
    const id = setInterval(fetchAll, pollMs);
    return () => { alive = false; clearInterval(id); };
  }, [API, pollMs]);

  return { banner1h, vol1h, gainers1m, gainers3m, losers3m };
}

export default useDataFeed;
