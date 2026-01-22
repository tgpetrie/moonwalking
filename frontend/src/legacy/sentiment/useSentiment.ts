import { useEffect, useRef, useState } from 'react';

type SentimentData = Record<string, unknown> | null;

type SentimentState = {
  loading: boolean;
  data: SentimentData;
  error: Error | null;
};

type CacheEntry = {
  ts: number;
  data: SentimentData;
};

type Options = {
  prefetch?: boolean;
  ttlMs?: number;
};

const CACHE = new Map<string, CacheEntry>();
const DEFAULT_TTL = 60_000;

import { fetchJson } from '../lib/api';

async function fetchSentiment(symbol: string): Promise<SentimentData> {
  const payload = await fetchJson(`/api/sentiment?symbol=${encodeURIComponent(symbol)}`, { cache: 'no-store' });
  if (payload && typeof payload === 'object' && 'data' in payload) return (payload as any).data;
  return payload as SentimentData;
}

export function useSentiment(symbol: string | undefined, options: Options = {}): SentimentState {
  const { prefetch = false, ttlMs = DEFAULT_TTL } = options;
  const [state, setState] = useState<SentimentState>({
    loading: Boolean(symbol),
    data: null,
    error: null,
  });
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!symbol) {
      setState({ loading: false, data: null, error: null });
      return;
    }

    const now = Date.now();
    const cached = CACHE.get(symbol);
    if (cached && now - cached.ts < ttlMs) {
      setState({ loading: false, data: cached.data, error: null });
      return;
    }

    let aborted = false;
    setState((prev) => ({ ...prev, loading: true, error: null }));

    (async () => {
      try {
        const data = await fetchSentiment(symbol);
        if (aborted || !mountedRef.current) return;
        CACHE.set(symbol, { ts: Date.now(), data });
        setState({ loading: false, data, error: null });
      } catch (err: unknown) {
        if (aborted || !mountedRef.current) return;
        setState({ loading: false, data: null, error: err instanceof Error ? err : new Error('Sentiment fetch failed') });
      }
    })();

    return () => {
      aborted = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, prefetch, ttlMs]);

  return state;
}
