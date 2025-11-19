// frontend/src/hooks/useData.js — cleaned single hook and normalization
import useSWR from "swr";
import { endpoints, fetchJson } from "../lib/api";

const KEY = endpoints.metrics || "/data";

function kit(rows = [], loading = false, msg = null) {
  return {
    rows: Array.isArray(rows) ? rows : [],
    loading: !!loading && (!rows || rows.length === 0),
    message: Array.isArray(rows) && rows.length === 0 ? msg : null,
  };
}

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

  const bySymbol = {};
  const push = (r) => {
    if (r && r.symbol) bySymbol[String(r.symbol).toUpperCase()] = r;
  };

  (payload.gainers_1m || []).forEach(push);
  (payload.gainers_3m || []).forEach(push);
  (payload.losers_3m || []).forEach(push);
  (payload.banner_1h_price || []).forEach(push);
  (payload.banner_1h_volume || []).forEach(push);

  const top1hPrice = kit(
    payload.banner_1h_price,
    isLoading,
    "Waiting for 1-hour price banner…"
  );
  const top1hVolume = kit(
    payload.banner_1h_volume,
    isLoading,
    "Waiting for 1-hour volume banner…"
  );

  return {
    data: {
      gainers1m: kit(
        payload.gainers_1m,
        isLoading,
        "Waiting for 1-minute snapshot…"
      ),
      gainers3m: kit(payload.gainers_3m, isLoading, null),
      losers3m: kit(payload.losers_3m, isLoading, null),
      top1hPrice,
      top1hVolume,
      meta: {
        ...meta,
        last_updated: payload.updated_at || meta.last_updated,
      },
    },
    bySymbol,
    isLoading,
    isError: !!error,
    mutate,
  };
}
