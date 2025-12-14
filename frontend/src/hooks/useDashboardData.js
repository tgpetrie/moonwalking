// frontend/src/hooks/useDashboardData.js
import useSWR from "swr";
import { API_BASE_URL, fetchAllData } from "../api";

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
  const { data, error, isLoading, mutate, isValidating } = useSWR(`${API_BASE_URL}/data`, fetchAllData, {
    revalidateOnFocus: true,
    keepPreviousData: true,
    dedupingInterval: 10000,
    refreshInterval: 4000, // Poll every 4 seconds
  });

  const payload = data?.data || data || {};
  const errors = data?.errors || payload?.errors || {};
  const coverage = data?.coverage || payload?.coverage || {};
  const fatal = (errors && errors.fatal) ? errors.fatal : null;

  const g1 = Array.isArray(payload.gainers_1m) ? payload.gainers_1m : [];
  const g3 = Array.isArray(payload.gainers_3m) ? payload.gainers_3m : [];
  const l3 = Array.isArray(payload.losers_3m) ? payload.losers_3m : [];
  const bv = Array.isArray(payload.banner_1h_volume) ? payload.banner_1h_volume : [];
  const bp = Array.isArray(payload.banner_1h_price) ? payload.banner_1h_price : [];

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

  // Track last successful update time
  const lastUpdated = data ? new Date() : null;

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
    loading: isLoading,
    isLoading,
    isValidating,
    error,
    mutate,
    lastUpdated,
  };
}
