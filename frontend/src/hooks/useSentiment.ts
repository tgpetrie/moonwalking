import { useEffect, useState } from 'react';
import { fetchJson } from '../lib/api';

type SentimentPayload = {
  overview?: { score?: number; label?: string };
  scores?: { bulls?: number; bears?: number; neutral?: number };
  social?: { buzz?: number; mentions?: number; sources?: number; top?: Array<{ source: string; count: number }> };
  news?: { articles?: Array<{ title?: string; url?: string; ts?: string }> };
  onchain?: { activeAddrs?: number; netflow?: number };
};

type SentimentState = {
  loading: boolean;
  error: Error | null;
  data: SentimentPayload | null;
};

const SECTION_ENDPOINTS = [
  ['overview', '/api/sentiment/overview?symbol='] as const,
  ['scores', '/api/sentiment/scores?symbol='] as const,
  ['social', '/api/sentiment/social?symbol='] as const,
  ['news', '/api/sentiment/news?symbol='] as const,
  ['onchain', '/api/sentiment/onchain?symbol='] as const,
];

function normalise(raw: any): SentimentPayload {
  if (!raw) return {};
  const overview = raw.overview ?? raw.meta ?? {};
  const scores = raw.scores ?? raw.sentiment ?? {};
  const social = raw.social ?? raw.socials ?? {};
  const news = raw.news ?? {};
  const onchain = raw.onchain ?? raw.chain ?? {};

  return {
    overview: {
      score: typeof overview.score === 'number' ? overview.score : overview.composite ?? overview.index,
      label: overview.label ?? overview.bucket ?? overview.tag,
    },
    scores: {
      bulls: scores.bulls ?? scores.bull ?? scores.pos ?? 0,
      bears: scores.bears ?? scores.bear ?? scores.neg ?? 0,
      neutral: scores.neutral ?? scores.neu ?? 0,
    },
    social: {
      buzz: social.buzz ?? social.activity ?? 0,
      mentions: social.mentions ?? social.count ?? 0,
      sources: social.sources ?? (Array.isArray(social.top) ? social.top.length : 0),
      top: (social.top ?? social.sourcesTop ?? []).map((item: any) => ({
        source: item.source ?? item.platform ?? item.name ?? 'unknown',
        count: item.count ?? item.mentions ?? item.value ?? 0,
      })),
    },
    news: {
      articles: (news.articles ?? news.items ?? []).map((item: any) => ({
        title: item.title ?? item.headline ?? '',
        url: item.url ?? item.link ?? '#',
        ts: item.ts ?? item.time ?? item.published_at,
      })),
    },
    onchain: {
      activeAddrs: onchain.activeAddrs ?? onchain.active_addresses ?? 0,
      netflow: onchain.netflow ?? onchain.exchange_netflow ?? 0,
    },
  };
}

async function fetchSentiment(symbol: string): Promise<SentimentPayload> {
  const query = encodeURIComponent(symbol);

  // 1) Preferred: unified endpoint with ?symbol=
  try {
    const combined = await fetchJson(`/api/sentiment?symbol=${query}`);
    return normalise(combined);
  } catch (primaryError) {
    // 2) Fallback A: backend batch endpoint uses ?symbols=
    try {
      const batch = await fetchJson<{ ok?: boolean; sentiment?: any[] }>(`/api/sentiment?symbols=${query}`);
      const item = Array.isArray(batch?.sentiment)
        ? batch!.sentiment!.find((s) => (s.symbol || '').toUpperCase() === symbol.toUpperCase())
        : null;

      // Fetch legacy social/news endpoints in parallel when available
      const [socialResp, newsResp] = await Promise.allSettled([
        fetchJson(`/api/social-sentiment/${symbol}`),
        fetchJson(`/api/news/${symbol}`),
      ]);

      const merged: Record<string, any> = {};

      if (item) {
        merged.overview = {
          score: item.score,
          label: item.label,
        };
        // scores are coarse in batch; leave detailed split to social payload if present
      }

      if (socialResp.status === 'fulfilled') {
        const s = socialResp.value?.data || socialResp.value || {};
        merged.scores = merged.scores || {};
        const dist = s.sentiment_distribution || {};
        merged.scores.bulls = dist.positive || dist.pos || 0;
        merged.scores.bears = dist.negative || dist.neg || 0;
        merged.scores.neutral = dist.neutral || dist.neu || 0;

        const sm = s.social_metrics || {};
        const twitter = sm.twitter || {};
        const reddit = sm.reddit || {};
        const news = sm.news || {};
        const youtube = sm.youtube || {};
        const mentions = (twitter.mentions_24h || 0) + (reddit.posts_24h || 0);
        const top = [
          { source: 'twitter', count: twitter.mentions_24h || 0 },
          { source: 'reddit', count: reddit.posts_24h || 0 },
          { source: 'news', count: news.articles_24h || 0 },
          { source: 'youtube', count: youtube.videos_24h || 0 },
        ].filter((x) => x.count > 0);

        merged.social = {
          buzz: (twitter.sentiment_score ?? 0) + (reddit.sentiment_score ?? 0),
          mentions,
          sources: top.length,
          top,
        };
      }

      if (newsResp.status === 'fulfilled') {
        const n = newsResp.value || {};
        merged.news = {
          articles: (n.articles || []).map((a: any) => ({
            title: a.title || a.headline,
            url: a.url || a.link,
            ts: a.published || a.ts || a.time,
          })),
        };
      }

      // onchain not provided by backend yet; leave defaults
      return normalise(merged);
    } catch (batchError) {
      // 3) Fallback B: hypothetical per-section endpoints (if provided by another backend flavor)
      try {
        const settled = await Promise.allSettled(
          SECTION_ENDPOINTS.map(([key, base]) => fetchJson(`${base}${query}`, { cache: 'no-store' }))
        );
        const merged: Record<string, any> = {};
        settled.forEach((entry, idx) => {
          if (entry.status === 'fulfilled') {
            const key = SECTION_ENDPOINTS[idx][0];
            merged[key] = entry.value;
          }
        });
        return normalise(merged);
      } catch (sectionError) {
        // propagate original
        throw primaryError;
      }
    }
  }
}

export function useSentiment(symbol: string | undefined, ttlSec = 30): SentimentState {
  const [state, setState] = useState<SentimentState>({ loading: Boolean(symbol), error: null, data: null });

  useEffect(() => {
    if (!symbol) {
      setState({ loading: false, error: null, data: null });
      return;
    }
    let cancelled = false;

    const run = async () => {
      setState((prev) => ({ ...prev, loading: true }));
      try {
        const payload = await fetchSentiment(symbol);
        if (!cancelled) setState({ loading: false, error: null, data: payload });
      } catch (err: any) {
        if (cancelled) return;
        setState({ loading: false, error: err, data: null });
      }
    };

    run();
    const timer = ttlSec > 0 ? setInterval(run, ttlSec * 1000) : undefined;
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [symbol, ttlSec]);

  return state;
}
