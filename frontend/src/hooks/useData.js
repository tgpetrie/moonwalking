// frontend/src/hooks/useData.js
import useSWR from "swr";
import { endpoints, fetchJson, mapRow, mapBanner } from "../lib/api";

const SWR_COMMON = {
  revalidateOnFocus: true,
  keepPreviousData: true,
  dedupingInterval: 10000,
  refreshInterval: () =>
    document.visibilityState === "visible" ? 15000 : 0,
  errorRetryCount: 3,
  errorRetryInterval: (attempt) => Math.min(10000, 1000 * 2 ** attempt),
};

export function useHealth() {
  return useSWR(endpoints.health, fetchJson, {
    refreshInterval: 30000,
    dedupingInterval: 30000,
  });
}

export function useGainers(interval) {
  const key = interval === "1m" ? endpoints.gainers1m : endpoints.gainers3m;
  const { data, error, isLoading, mutate } = useSWR(key, fetchJson, SWR_COMMON);
  // backend /data returns { data: { gainers_1m: [], gainers_3m: [], losers_3m: [] } }
  const unwrapped = data?.data ?? data ?? {};
  const rowsRaw = interval === "1m" ? unwrapped.gainers_1m : unwrapped.gainers_3m;
  const rows = (rowsRaw ?? [])
    .map(mapRow)
    .sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0));
  return { rows, loading: isLoading && !rows.length, error, mutate };
}

export function useLosers3m() {
  const { data, error, isLoading, mutate } = useSWR(
    endpoints.losers3m,
    fetchJson,
    SWR_COMMON
  );
  const unwrapped = data?.data ?? data ?? {};
  const rows = (unwrapped.losers_3m ?? [])
    .map(mapRow)
    .sort((a, b) => (a.changePct ?? 0) - (b.changePct ?? 0));
  return { rows, loading: isLoading && !rows.length, error, mutate };
}

export function useBanner1h() {
  const { data, ...rest } = useSWR(endpoints.banner1h, fetchJson, {
    ...SWR_COMMON,
    refreshInterval: 20000,
  });
  const unwrapped = data?.data ?? data ?? {};
  const items = (unwrapped.banner_1h ?? []).map(mapBanner);
  return { items, ...rest };
}

export function useBannerVolume1h() {
  const { data, ...rest } = useSWR(endpoints.bannerVolume1h, fetchJson, {
    ...SWR_COMMON,
    refreshInterval: 25000,
  });
  const items = (data?.items ?? data ?? []).map(mapBanner);
  return { items, ...rest };
}

// Aggregate data hook that returns the full backend /data payload.
export function useData() {
  const { data, error, isLoading, mutate } = useSWR('/data', fetchJson, SWR_COMMON);
  const unwrapped = data?.data ?? data ?? {};
  return { data: unwrapped, isLoading, error, mutate };
}

