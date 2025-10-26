import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { AnimatePresence, motion } from 'framer-motion';
import { API_ENDPOINTS, fetchData } from '../api.js';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'social', label: 'Social' },
  { id: 'news', label: 'News' },
];

export default function SentimentCard({ symbol, symbols = [], onClose }) {
  const [tab, setTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({});

  const activeSymbol = useMemo(() => {
    const source = symbol || symbols[0] || 'BTC';
    return source.toUpperCase().replace(/-USD$/, '');
  }, [symbol, symbols]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchData(API_ENDPOINTS.sentiment(activeSymbol), { signal: controller.signal });
        if (cancelled) return;
        const payload = response?.data ?? response ?? {};
        const normalized = payload[activeSymbol] || payload;
        setData(normalized || {});
      } catch (err) {
        if (cancelled) return;
        if (err.name === 'AbortError') {
          return;
        }
        console.error('[SentimentCard] fetch failed', err);
        setError('Unable to load sentiment right now.');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeSymbol]);

  const overview = data?.overview || data;
  const social = data?.social || {};
  const news = Array.isArray(data?.news) ? data.news : (Array.isArray(data?.articles) ? data.articles : []);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-modal flex items-center justify-center bg-black/50 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="card w-[90%] max-w-xl p-5 text-left"
          initial={{ opacity: 0, y: 30, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h2 className="text-sm font-bold tracking-widest uppercase text-gray-200">
              Sentiment — {activeSymbol}
            </h2>
            <button className="badge" type="button" onClick={onClose}>
              ✕
            </button>
          </div>

          <div className="flex gap-4 mt-4">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`text-sm font-semibold uppercase tracking-widest ${
                  tab === t.id ? 'text-blue border-b-2 border-blue' : 'text-gray-400'
                }`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="mt-4 text-[13px] text-gray-200 min-h-[120px]">
            {loading && <div>Loading sentiment…</div>}
            {!loading && error && <div className="text-pink">{error}</div>}
            {!loading && !error && (
              <>
                {tab === 'overview' && <Overview data={overview} />}
                {tab === 'social' && <Social data={social} />}
                {tab === 'news' && <News data={news} />}
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function Overview({ data = {} }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div className="card p-3">
        <div className="section-title mb-2">Aggregate</div>
        <Row label="Score" value={formatValue(data.sentiment_score)} />
        <Row label="Momentum" value={formatValue(data.momentum)} />
      </div>
      <div className="card p-3">
        <div className="section-title mb-2">Distribution</div>
        <Row label="Bullish" value={formatPercent(data.bull_pct)} />
        <Row label="Bearish" value={formatPercent(data.bear_pct)} />
      </div>
    </div>
  );
}

function Social({ data = {} }) {
  return (
    <div className="card p-3">
      <div className="section-title mb-2">Social Buzz</div>
      <Row label="Mentions" value={formatValue(data.volume)} />
      <Row label="Positivity" value={formatPercent(data.positive)} />
      <Row label="Trending" value={formatValue(data.trending_topic || '—')} />
    </div>
  );
}

function News({ data = [] }) {
  if (!data.length) {
    return <div className="text-dim">No recent news.</div>;
  }
  return (
    <div className="grid gap-2">
      {data.map((item, idx) => (
        <a
          key={`${item?.url || idx}`}
          href={item?.url || '#'}
          target="_blank"
          rel="noreferrer"
          className="card p-3 hover:opacity-90 transition-opacity"
        >
          <div className="text-xs text-gray-400 uppercase">{item?.source || 'Newswire'}</div>
          <div className="text-sm font-semibold">{item?.title || 'Untitled headline'}</div>
        </a>
      ))}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between text-[13px] py-0.5">
      <span className="text-gray-400">{label}</span>
      <span>{value}</span>
    </div>
  );
}

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'number') {
    return value.toFixed(2);
  }
  return value;
};

const formatPercent = (value) => {
  if (typeof value !== 'number') {
    return value || '—';
  }
  return `${value.toFixed(0)}%`;
};

SentimentCard.propTypes = {
  symbol: PropTypes.string,
  symbols: PropTypes.arrayOf(PropTypes.string),
  onClose: PropTypes.func,
};

SentimentCard.defaultProps = {
  symbol: undefined,
  symbols: [],
  onClose: undefined,
};

Overview.propTypes = {
  data: PropTypes.object,
};

Social.propTypes = {
  data: PropTypes.object,
};

News.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
};

Row.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
};
