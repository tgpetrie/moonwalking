// frontend/src/hooks/useData.js — explicit lanes, no legacy payload leakage
import useSWR from "swr";
import { endpoints, fetchJson } from "../lib/api";

const KEY = endpoints.metrics || "/data";

export function useData() {
  const { data, error, isLoading, mutate } = useSWR(
    KEY,
    () => fetchJson(KEY),
    {
      revalidateOnFocus: false,
      dedupingInterval: 8000,
      refreshInterval: 2000, // poll /data every 2s for fresher updates
    }
  );

  const payload = data?.data ?? data ?? {};
  const meta = payload?.meta ?? data?.meta ?? {};

  const gainers1m = payload.gainers_1m ?? [];
  const gainers3m = payload.gainers_3m ?? [];
  const losers3m = payload.losers_3m ?? [];
  const banner1hPrice = payload.banner_1h_price ?? [];
  const banner1hVolume = payload.banner_1h_volume ?? [];
  const latestBySymbol = payload.latest_by_symbol ?? {};

  const bySymbol = {};
  const push = (r) => {
    if (r && r.symbol) bySymbol[String(r.symbol).toUpperCase()] = r;
  };

  [...gainers1m, ...gainers3m, ...losers3m, ...banner1hPrice, ...banner1hVolume].forEach(push);

  return {
    gainers1m,
    gainers3m,
    losers3m,
    banner1hPrice,
    banner1hVolume,
    latestBySymbol,
    meta: {
      ...meta,
      last_updated: payload.updated_at || meta.last_updated,
    },
    loading: isLoading,
    error,
    bySymbol,
    mutate,
  };
}
