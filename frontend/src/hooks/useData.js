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
  const rows = (data?.rows ?? data ?? [])
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
  const rows = (data?.rows ?? data ?? [])
    .map(mapRow)
    .sort((a, b) => (a.changePct ?? 0) - (b.changePct ?? 0));
  return { rows, loading: isLoading && !rows.length, error, mutate };
}

export function useBanner1h() {
  const { data, ...rest } = useSWR(endpoints.banner1h, fetchJson, {
    ...SWR_COMMON,
    refreshInterval: 20000,
  });
  const items = (data?.items ?? data ?? []).map(mapBanner);
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

