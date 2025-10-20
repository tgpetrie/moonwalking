import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { endpoints, fetchJson, mapBanners, mapRows } from "../lib/api";

type PollOptions<T> = {
  refreshMs?: number;
  dedupeMs?: number;
  transform?: (payload: any) => T;
};

type PollState<T> = {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
};

const DEFAULT_REFRESH = 15_000;
const DEFAULT_DEDUPE = 5_000;

function usePollJson<T = any>(endpoint: string, options: PollOptions<T> = {}): PollState<T> {
  const { refreshMs = DEFAULT_REFRESH, dedupeMs = DEFAULT_DEDUPE, transform } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const lastFetchRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const runFetch = useCallback(
    async (force = false) => {
      const now = Date.now();
      if (!force && now - lastFetchRef.current < dedupeMs) return;
      lastFetchRef.current = now;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        setLoading((prev) => prev && !data);
        const json = await fetchJson(endpoint, { signal: controller.signal });
        const transformed = transform ? transform(json) : (json as T);
        setData(transformed);
        setError(null);
        setLoading(false);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        setError(err);
        setLoading(false);
      }
    },
    [endpoint, dedupeMs, transform, data]
  );

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    setLoading(true);
    runFetch(true);
    if (refreshMs > 0) {
      timer = setInterval(() => runFetch(false), refreshMs);
    }
    return () => {
      abortRef.current?.abort();
      if (timer) clearInterval(timer);
    };
  }, [runFetch, refreshMs]);

  const refresh = useCallback(() => runFetch(true), [runFetch]);

  return { data, loading, error, refresh };
}

const sortByChangeDesc = (rows: ReturnType<typeof mapRows>) =>
  [...rows].sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0));

const sortByChangeAsc = (rows: ReturnType<typeof mapRows>) =>
  [...rows].sort((a, b) => (a.changePct ?? 0) - (b.changePct ?? 0));

export function useGainers(interval: "1m" | "3m") {
  const endpoint = interval === "1m" ? endpoints.gainers1m : endpoints.gainers3m;
  const { data, loading, error, refresh } = usePollJson(endpoint, {
    refreshMs: 15_000,
    dedupeMs: 8_000,
    transform: (payload) => sortByChangeDesc(mapRows(payload)),
  });

  return {
    rows: data ?? [],
    loading,
    error,
    refresh,
  };
}

export function useLosers3m() {
  const { data, loading, error, refresh } = usePollJson(endpoints.losers3m, {
    refreshMs: 15_000,
    dedupeMs: 8_000,
    transform: (payload) => sortByChangeAsc(mapRows(payload)),
  });

  return {
    rows: data ?? [],
    loading,
    error,
    refresh,
  };
}

export function useBanner1h() {
  const { data, loading, error, refresh } = usePollJson(endpoints.banner1h, {
    refreshMs: 20_000,
    dedupeMs: 6_000,
    transform: (payload) => mapBanners(payload),
  });
  return {
    items: data ?? [],
    loading,
    error,
    refresh,
  };
}

export function useBannerVolume1h() {
  const { data, loading, error, refresh } = usePollJson(endpoints.bannerVolume1h, {
    refreshMs: 25_000,
    dedupeMs: 6_000,
    transform: (payload) => mapBanners(payload),
  });
  return {
    items: data ?? [],
    loading,
    error,
    refresh,
  };
}

export function useHealth() {
  return usePollJson(endpoints.health, { refreshMs: 30_000, dedupeMs: 15_000 });
}
