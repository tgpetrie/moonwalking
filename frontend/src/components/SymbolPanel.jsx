import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';

/**
 * SymbolPanel
 * - 4 tabs: Overview, Technicals, News, Social
 * - Non-blocking fetches to:
 *    /api/technical-analysis/:symbol
 *    /api/news/:symbol
 *    /api/social-sentiment/:symbol
 * - CTA: Open in Coinbase (Advanced Trade spot)
 * - ESC / ✕ closes
 * - Minimal Tailwind-only styling to match your dark UI
 */
export default function SymbolPanel({ symbol, onClose, initialTab = 'overview' }) {
  const sym = (symbol || '').toUpperCase();
  const [tab, setTab] = useState(initialTab); // overview | technicals | news | social

  const [loadingTA, setLoadingTA] = useState(false);
  const [ta, setTA] = useState(null);
  const [loadingNews, setLoadingNews] = useState(false);
  const [news, setNews] = useState(null);
  const [loadingSocial, setLoadingSocial] = useState(false);
  const [social, setSocial] = useState(null);

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose?.();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Lazy-load per tab to keep costs low on free tier
  useEffect(() => {
    if (!sym) return;
    if (tab === 'technicals' && !ta && !loadingTA) {
      setLoadingTA(true);
      import('../lib/api').then(({ fetchJson }) => {
        fetchJson(`/api/technical-analysis/${sym}`).then(setTA).catch(() => {}).finally(() => setLoadingTA(false));
      }).catch(() => setLoadingTA(false));
    } else if (tab === 'news' && !news && !loadingNews) {
      setLoadingNews(true);
      import('../lib/api').then(({ fetchJson }) => {
        fetchJson(`/api/news/${sym}`).then(setNews).catch(() => {}).finally(() => setLoadingNews(false));
      }).catch(() => setLoadingNews(false));
    } else if (tab === 'social' && !social && !loadingSocial) {
      setLoadingSocial(true);
      import('../lib/api').then(({ fetchJson }) => {
        fetchJson(`/api/social-sentiment/${sym}`).then(setSocial).catch(() => {}).finally(() => setLoadingSocial(false));
      }).catch(() => setLoadingSocial(false));
    }
  }, [sym, tab, ta, news, social, loadingTA, loadingNews, loadingSocial]);

  const cbUrl = useMemo(() => {
    // Coinbase Advanced Trade spot page (common pattern)
    const pair = `${sym.toLowerCase()}-usd`;
    return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
  }, [sym]);

  if (!sym) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-end md:items-center justify-center">
      {/* backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close panel backdrop"
      />

      {/* panel */}
      <div className="relative w-full md:max-w-4xl md:rounded-2xl md:border md:border-zinc-800 bg-zinc-950 shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 md:px-6 md:py-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-200 font-semibold">
              {sym.slice(0, 2)}
            </div>
            <div className="flex flex-col">
              <div className="text-zinc-100 text-base md:text-lg font-semibold">{sym}/USD</div>
              <div className="text-xs text-zinc-400">Live snapshot · free tier</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={cbUrl}
              target="_blank"
              rel="noreferrer"
              className="hidden md:inline-flex px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-sm"
            >
              Open in Coinbase ↗
            </a>
            <button
              className="h-8 w-8 rounded-lg hover:bg-zinc-800 text-zinc-300"
              onClick={onClose}
              aria-label="Close"
              title="Close"
            >
              ×
            </button>
          </div>
        </div>

        {/* tabs */}
        <div className="px-4 md:px-6">
          <div className="mt-3 flex items-center gap-2">
            {['overview', 'technicals', 'news', 'social'].map(key => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={
                  'px-3 py-1.5 rounded-lg text-sm capitalize ' +
                  (tab === key
                    ? 'bg-zinc-200 text-zinc-900'
                    : 'bg-zinc-900 text-zinc-300 hover:bg-zinc-800')
                }
              >
                {key}
              </button>
            ))}
            <a
              href={cbUrl}
              target="_blank"
              rel="noreferrer"
              className="md:hidden ml-auto px-3 py-1.5 rounded-lg bg-zinc-200 text-zinc-900 text-sm"
            >
              Coinbase ↗
            </a>
          </div>
        </div>

        {/* content */}
        <div className="px-4 md:px-6 py-4 md:py-6">
          {tab === 'overview' && <Overview symbol={sym} />}
          {tab === 'technicals' && <Technicals loading={loadingTA} data={ta} />}
          {tab === 'news' && <News loading={loadingNews} data={news} />}
          {tab === 'social' && <Social loading={loadingSocial} data={social} />}
        </div>
      </div>
    </div>
  );
}

SymbolPanel.propTypes = {
  symbol: PropTypes.string,
  onClose: PropTypes.func,
  initialTab: PropTypes.oneOf(['overview', 'technicals', 'news', 'social']),
};

function Overview({ symbol }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Stat label="Symbol" value={`${symbol}/USD`} />
      <Stat label="Updated" value="near-live (SSE)" />
      <Stat label="Source" value="Coinbase REST" />
      <div className="md:col-span-3 text-sm text-zinc-400">
        Click other tabs for technicals, sentiment, and recent headlines. Panel is
        lightweight and won’t interrupt live tables.
      </div>
    </div>
  );
}

function Technicals({ loading, data }) {
  if (loading) return <Skeleton label="Loading technical analysis…" />;
  if (!data?.success) return <Empty label="No technicals yet." />;
  const d = data.data || {};
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Stat label="Price" value={fmt(d.current_price)} />
      <Stat label="RSI" value={fmt(d.rsi)} />
      <Stat label="MACD" value={d.macd ? `${d.macd.macd} / ${d.macd.signal}` : '—'} />
      <Card title="Bollinger Bands" className="md:col-span-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <Stat label="Upper" value={fmt(d.bollinger_bands?.upper)} compact />
          <Stat label="Middle" value={fmt(d.bollinger_bands?.middle)} compact />
          <Stat label="Lower" value={fmt(d.bollinger_bands?.lower)} compact />
        </div>
      </Card>
      <Card title="Recommendation" className="md:col-span-3">
        <div className="text-zinc-200 text-sm">{d.recommendation || '—'}</div>
      </Card>
    </div>
  );
}

function News({ loading, data }) {
  if (loading) return <Skeleton label="Loading headlines…" />;
  if (!data?.success && !Array.isArray(data?.articles)) return <Empty label="No headlines yet." />;
  const items = data.articles || [];
  return (
    <div className="space-y-3">
      {items.map((a) => (
        <a
          key={a.id}
          href={a.url || '#'}
          target="_blank"
          rel="noreferrer"
          className="block rounded-xl border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 px-4 py-3"
        >
          <div className="text-zinc-100 text-sm font-medium">{a.title}</div>
          <div className="text-xs text-zinc-400 mt-1 line-clamp-2">{a.summary}</div>
          <div className="text-[11px] text-zinc-500 mt-1">
            {a.source} · {new Date(a.published).toLocaleString()}
          </div>
        </a>
      ))}
      {items.length === 0 && <Empty label="No headlines yet." />}
    </div>
  );
}

function Social({ loading, data }) {
  if (loading) return <Skeleton label="Loading social sentiment…" />;
  if (!data?.success && !data?.data) return <Empty label="No social metrics yet." />;
  const s = data.data || {};
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Stat label="Overall" value={`${s.overall_sentiment?.label || '—'} (${fmt(s.overall_sentiment?.score)})`} />
      <Stat label="Confidence" value={fmt(s.overall_sentiment?.confidence)} />
      <Stat label="Fear/Greed" value={fmt(s.fear_greed_index)} />

      <Card title="Distribution" className="md:col-span-3">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Positive" value={fmt(s.sentiment_distribution?.positive)} compact />
          <Stat label="Neutral" value={fmt(s.sentiment_distribution?.neutral)} compact />
          <Stat label="Negative" value={fmt(s.sentiment_distribution?.negative)} compact />
        </div>
      </Card>
      <Card title="Social metrics" className="md:col-span-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <Stat label="Twitter 24h" value={fmt(s.social_metrics?.twitter?.mentions_24h)} compact />
          <Stat label="Reddit posts" value={fmt(s.social_metrics?.reddit?.posts_24h)} compact />
          <Stat label="Telegram 24h" value={fmt(s.social_metrics?.telegram?.messages_24h)} compact />
        </div>
      </Card>
    </div>
  );
}