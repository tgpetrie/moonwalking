// frontend/src/hooks/useDashboardData.js
import { useEffect, useRef } from "react";
import { useData } from "../context/DataContext";

const LS_KEY = "bh_last_payload_v1";

function writeLastPayload(value) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(value));
  } catch {}
}

// map raw backend row to UI row while preserving ALL backend fields
function mapRowWithInitial(x = {}) {
  // normalize symbol display
  const symbol = String(x.ticker ?? x.symbol ?? "").toUpperCase();
  const displaySymbol = symbol.replace(/-(USD|USDT|PERP)$/i, "");

  // Return the ORIGINAL object with symbol normalization, don't destroy fields
  return {
    ...x, // preserve ALL backend fields (change_1m, change_3m, etc.)
    symbol: displaySymbol,
  };
}

export function useDashboardData() {
  // Use the optimized DataContext instead of direct SWR
  const { data, error, loading, oneMinRows, threeMin, banners, heartbeatPulse, lastFetchTs } = useData();

  const payload = data || {};

  // Use the granular slices from DataContext (which have independent publish cadences)
  const g1 = Array.isArray(oneMinRows) && oneMinRows.length > 0 ? oneMinRows : Array.isArray(payload.gainers_1m) ? payload.gainers_1m : [];
  const g3 = Array.isArray(threeMin?.gainers) && threeMin.gainers.length > 0 ? threeMin.gainers : Array.isArray(payload.gainers_3m) ? payload.gainers_3m : [];
  const l3 = Array.isArray(threeMin?.losers) && threeMin.losers.length > 0 ? threeMin.losers : Array.isArray(payload.losers_3m) ? payload.losers_3m : [];
  const bv = Array.isArray(banners?.volume) && banners.volume.length > 0 ? banners.volume : Array.isArray(payload.banner_1h_volume) ? payload.banner_1h_volume : [];
  const bp = Array.isArray(banners?.price) && banners.price.length > 0 ? banners.price : Array.isArray(payload.banner_1h_price) ? payload.banner_1h_price : [];

  const gainers1m = g1.map(mapRowWithInitial);
  const gainers3m = g3.map(mapRowWithInitial);
  const losers3m = l3.map(mapRowWithInitial);
  const bannerVolume1h = bv.map(mapRowWithInitial);
  const bannerPrice1h = bp.map(mapRowWithInitial);

  // build a quick symbol → current price map for watchlist reconciliation
  const priceMap = {};
  for (const r of [...gainers1m, ...gainers3m, ...losers3m]) {
    if (r && r.symbol) priceMap[r.symbol] = r.price;
  }

  // Persist last good payload for instant reloads
  const prevDataRef = useRef(null);
  useEffect(() => {
    if (!data || error) return;
    if (prevDataRef.current !== data) {
      prevDataRef.current = data;
      writeLastPayload(data);
    }
  }, [data, error]);

  // Last updated timestamp
  const lastUpdatedTsRef = useRef(null);
  useEffect(() => {
    if (!data || error) return;
    if (prevDataRef.current !== data) {
      lastUpdatedTsRef.current = Date.now();
    }
  }, [data, error]);

  const lastUpdatedTs = lastUpdatedTsRef.current;
  const lastUpdated = lastUpdatedTs ? new Date(lastUpdatedTs) : null;

  // Extract error/coverage metadata from payload
  const errors = payload.errors || {};
  const coverage = payload.coverage || {};
  const fatal = errors?.fatal || null;

  return {
    raw: data,
    gainers1m,
    gainers3m,
    losers3m,
    bannerVolume1h,
    bannerPrice1h,
    priceMap,
    errors,
    coverage,
    fatal,
    loading,
    isLoading: loading,
    isValidating: false, // No longer using SWR validation
    error,
    mutate: null, // No longer using SWR mutate
    lastUpdatedTs,
    lastUpdated,
    heartbeatPulse,
    lastFetchTs,
  };
}
