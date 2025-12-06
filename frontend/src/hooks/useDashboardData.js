// frontend/src/hooks/useDashboardData.js
import useSWR from "swr";
import { fetchAllData } from "../api";

// map raw backend row to UI row while preserving initial prices for panels
function mapRowWithInitial(x = {}) {
  // normalize fields but keep initial price fields for 1m/3m
  const symbol = String(x.ticker ?? x.symbol ?? "").toUpperCase();
  const displaySymbol = symbol.replace(/-(USD|USDT|PERP)$/i, "");
  const price = Number(x.last ?? x.price ?? x.current_price ?? 0);
  const changePct =
    typeof x.changePct === "number"
      ? x.changePct
      : typeof x.pct === "number"
      ? x.pct
      : typeof x.price_change_percentage_1min === "number"
      ? x.price_change_percentage_1min
      : typeof x.price_change_percentage_3min === "number"
      ? x.price_change_percentage_3min
      : typeof x.change === "number"
      ? x.change
      : 0;
  return {
    symbol: displaySymbol,
    price,
    changePct: Number(changePct) || 0,
    initial_price_1min: x.initial_price_1min,
    initial_price_3min: x.initial_price_3min,
  };
}

export function useDashboardData() {
  const { data, error, isLoading, mutate } = useSWR("/data", fetchAllData, {
    revalidateOnFocus: true,
    keepPreviousData: true,
    dedupingInterval: 10000,
  });

  const payload = data?.data || data || {};
  const errors = data?.errors || payload?.errors || {};

  const g1 = Array.isArray(payload.gainers_1m) ? payload.gainers_1m : [];
  const g3 = Array.isArray(payload.gainers_3m) ? payload.gainers_3m : [];
  const l3 = Array.isArray(payload.losers_3m) ? payload.losers_3m : [];

  const gainers1m = g1.map(mapRowWithInitial);
  const gainers3m = g3.map(mapRowWithInitial);
  const losers3m = l3.map(mapRowWithInitial);

  // build a quick symbol → current price map for watchlist reconciliation
  const priceMap = {};
  for (const r of [...gainers1m, ...gainers3m, ...losers3m]) {
    if (r && r.symbol) priceMap[r.symbol] = r.price;
  }

  return {
    raw: data,
    gainers1m,
    gainers3m,
    losers3m,
    priceMap,
    errors,
    isLoading,
    error,
    mutate,
  };
}
