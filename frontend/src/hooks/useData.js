// frontend/src/hooks/useData.js
import useSWR from "swr";
import { endpoints, fetchJson, normalizeRow } from "../lib/api.js";

const SWR_COMMON = {
  revalidateOnFocus: true,
  keepPreviousData: true,
  dedupingInterval: 10000,
  refreshInterval: () => (document.visibilityState === "visible" ? 15000 : 0),
  errorRetryCount: 3,
  errorRetryInterval: (attempt) => Math.min(10000, 1000 * 2 ** attempt),
};

// Aggregate data hook that returns panel-shaped data and a symbol map
export function useData() {
  const { data, error, isLoading, mutate } = useSWR(
    endpoints.metrics,
    fetchJson,
    SWR_COMMON
  );
  const buckets = data?.data ?? data ?? {};
  const errs = data?.errors ?? {};

  const g1 = Array.isArray(buckets.gainers_1m) ? buckets.gainers_1m.map(normalizeRow) : [];
  const g3 = Array.isArray(buckets.gainers_3m) ? buckets.gainers_3m.map(normalizeRow) : [];
  const l3 = Array.isArray(buckets.losers_3m) ? buckets.losers_3m.map(normalizeRow) : [];

  const bySymbol = {};
  [...g1, ...g3, ...l3].forEach((r) => {
    if (r?.symbol) bySymbol[r.symbol] = r;
  });

  const panels = {
    gainers1m: {
      rows: g1,
      loading: isLoading || errs.gainers_1m === "missing_snapshot",
      message: errs.gainers_1m === "missing_snapshot" ? "Waiting for 1-minute snapshot…" : null,
    },
    gainers3m: { rows: g3, loading: isLoading, message: null },
    losers3m: { rows: l3, loading: isLoading, message: null },
  };

  return { data: panels, isLoading, error, mutate, bySymbol };
}
