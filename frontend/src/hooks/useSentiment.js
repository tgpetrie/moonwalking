// frontend/src/hooks/useSentiment.js
import useSWR from "swr";

async function fetchJson(url, ms = 8000) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try {
    const r = await fetch(url, {
      signal: c.signal,
      headers: { accept: "application/json" },
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

function normalize(raw) {
  if (!raw) return {};
  const o = raw.overview ?? raw.meta ?? {};
  const s = raw.scores ?? raw.sentiment ?? {};
  const soc = raw.social ?? raw.socials ?? {};
  const nw = raw.news ?? {};
  const oc = raw.onchain ?? raw.chain ?? {};

  return {
    overview: {
      score: o.score ?? o.composite ?? o.index,
      label: o.label ?? o.bucket ?? o.tag,
    },
    scores: {
      bulls: s.bulls ?? s.bull ?? s.pos ?? 0,
      bears: s.bears ?? s.bear ?? s.neg ?? 0,
      neutral: s.neutral ?? s.neu ?? 0,
    },
    social: {
      buzz: soc.buzz ?? soc.activity ?? 0,
      mentions: soc.mentions ?? soc.count ?? 0,
      sources: soc.sources ?? (Array.isArray(soc.top) ? soc.top.length : 0),
      top: (soc.top ?? soc.sourcesTop ?? []).map((x) => ({
        source: x.source ?? x.platform ?? x.name ?? "unknown",
        count: x.count ?? x.mentions ?? x.value ?? 0,
      })),
    },
    news: {
      articles: (nw.articles ?? nw.items ?? []).map((a) => ({
        title: a.title ?? a.headline ?? "",
        url: a.url ?? a.link ?? "#",
        ts: a.ts ?? a.time ?? a.published_at,
      })),
    },
    onchain: {
      activeAddrs: oc.activeAddrs ?? oc.active_addresses ?? 0,
      netflow: oc.netflow ?? oc.exchange_netflow ?? 0,
    },
  };
}

async function fetchSentimentComposite(symbol) {
  try {
    const combined = await fetchJson(
      `/api/sentiment?symbol=${encodeURIComponent(symbol)}`,
      8000
    );
    return normalize(combined);
  } catch {
    const q = `symbol=${encodeURIComponent(symbol)}`;
    const settle = (p) => p.then((v) => ({ ok: true, v })).catch(() => ({ ok: false }));
    const [overview, scores, social, news, onchain] = await Promise.all([
      settle(fetchJson(`/api/sentiment/overview?${q}`, 4000)),
      settle(fetchJson(`/api/sentiment/scores?${q}`, 4000)),
      settle(fetchJson(`/api/sentiment/social?${q}`, 4000)),
      settle(fetchJson(`/api/sentiment/news?${q}`, 4000)),
      settle(fetchJson(`/api/sentiment/onchain?${q}`, 4000)),
    ]);
    const raw = {
      overview: overview.ok ? overview.v : undefined,
      scores: scores.ok ? scores.v : undefined,
      social: social.ok ? social.v : undefined,
      news: news.ok ? news.v : undefined,
      onchain: onchain.ok ? onchain.v : undefined,
    };
    return normalize(raw);
  }
}

export function useSentiment(symbol, ttlSec = 30) {
  return useSWR(
    symbol ? ["sentiment", symbol] : null,
    () => fetchSentimentComposite(symbol),
    {
      keepPreviousData: true,
      dedupingInterval: ttlSec * 1000,
      refreshInterval: ttlSec * 1000,
      revalidateOnFocus: true,
      errorRetryCount: 2,
    }
  );
}

