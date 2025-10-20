export type TrendKind = 'up' | 'down' | 'flat';

export interface SwrMeta {
  source?: string;
  cached_at?: number;
  ttl?: number;
  ttl_seconds?: number;
  stale_window?: number;
  revalidate_seconds?: number;
  served_cached?: boolean;
  note?: string;
}

export interface SentimentSummary {
  score: number;
  trend: TrendKind;
  sample_n: number;
  updated_at: number;
  buckets: {
    bull: number;
    bear: number;
    neutral: number;
  };
  breadth?: {
    gainers: number;
    losers: number;
  };
}

export interface SentimentSummaryResponse {
  summary: SentimentSummary | null;
  swr?: SwrMeta;
  empty?: boolean;
  error?: string;
}

export interface AssetSentimentResponse {
  asset?: {
    symbol: string;
    score: number;
    spark: number[];
    updated_at: number;
    gain_pct?: number;
    trend_direction?: TrendKind;
    trend_streak?: number;
  };
  swr?: SwrMeta;
  empty?: boolean;
  error?: string;
}

export interface InsightItem {
  id: string;
  kind: string;
  title: string;
  detail: string;
  severity: 'low' | 'medium' | 'high';
  ts: number;
  action?: string;
}

export interface InsightsResponse {
  insights: InsightItem[];
  swr?: SwrMeta;
  empty?: boolean;
  error?: string;
}

export interface SentimentBatchItem {
  symbol: string;
  score: number;
  label?: string;
  confidence?: number;
  fear_greed?: number;
  twitter_mentions?: number;
  reddit_posts?: number;
}

export interface SentimentBatchResponse {
  ok: boolean;
  sentiment: SentimentBatchItem[];
  timestamp?: string;
  swr?: SwrMeta;
  error?: string;
}

export interface AskLogEntry {
  q: string;
  ts: number;
}

export interface AskRecentResponse {
  items: AskLogEntry[];
  swr?: SwrMeta;
}

export interface LearnProgress {
  completed: number;
  streak: number;
  last_ts: number;
}

export interface LearnProgressResponse {
  progress: LearnProgress;
  swr?: SwrMeta;
}

const envBase = ((import.meta as any)?.env?.VITE_API_BASE ?? '').trim();
const API_BASE = envBase.replace(/\/$/, '');

const buildUrl = (path: string): string => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (!API_BASE) {
    return normalizedPath;
  }
  const base = API_BASE.replace(/\/$/, '');
  if (base.endsWith('/api') && normalizedPath.startsWith('/api/')) {
    return `${base}${normalizedPath.slice(4)}`;
  }
  return `${base}${normalizedPath}`;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildUrl(path);
  const response = await fetch(url, {
    headers: { accept: 'application/json', ...(init?.headers || {}) },
    ...init,
  });

  if (response.status === 503) {
    const fallback = await response.json().catch(() => ({}));
    return { ...(fallback || {}), empty: true } as T;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`${response.status} ${response.statusText} on ${url}${text ? `: ${text}` : ''}`);
  }

  return response.json();
}

export const fetchSentimentSummary = () =>
  requestJson<SentimentSummaryResponse>('/api/sentiment/summary');

export const fetchAssetSentiment = (symbol: string) =>
  requestJson<AssetSentimentResponse>(`/api/sentiment/asset/${encodeURIComponent(symbol)}`);

export const fetchSentimentBatch = (symbols: string[]) => {
  const uniqueSymbols = Array.from(
    new Set(
      symbols
        .map((value) => value?.toString().trim().toUpperCase())
        .filter((value): value is string => Boolean(value))
    )
  );
  if (!uniqueSymbols.length) {
    return Promise.resolve<SentimentBatchResponse>({ ok: false, sentiment: [], error: 'no symbols' });
  }
  const query = uniqueSymbols.map(encodeURIComponent).join(',');
  return requestJson<SentimentBatchResponse>(`/api/sentiment?symbols=${query}`);
};

export const fetchInsights = () =>
  requestJson<InsightsResponse>('/api/insights');

export const postAsk = async (q: string) => {
  const res = await requestJson<{ ok: boolean; logged?: AskLogEntry; error?: string; total?: number }>(
    '/api/ask/log',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ q }),
    }
  );
  if (!res.ok) {
    throw new Error(res.error || 'ask/log failed');
  }
  return res;
};

export const recentAsks = () => requestJson<AskRecentResponse>('/api/ask/recent');

export const learnComplete = () =>
  requestJson<{ ok: boolean; progress: LearnProgress }>('/api/learn/complete', { method: 'POST' });

export const learnProgress = () => requestJson<LearnProgressResponse>('/api/learn/progress');
