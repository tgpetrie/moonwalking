import React from 'react';
import {
  fetchSentimentBatch,
  SentimentBatchItem,
} from '../../api/sentiment';
import { useWatchlistContext } from '../../hooks/useWatchlist.jsx';

const MIN_TTL_SECONDS = 30;
const DEFAULT_SYMBOLS = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'AVAX'];

type TabId = 'overview' | 'bulls' | 'bears' | 'social';

type WatchlistValue = {
  list?: string[];
  loading?: boolean;
};

const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'bulls', label: 'Bullish' },
  { id: 'bears', label: 'Bearish' },
  { id: 'social', label: 'Social Buzz' },
];

const formatPercent = (value?: number | null) =>
  typeof value === 'number' ? `${Math.round(value * 100)}%` : '—';

const scoreLabel = (score?: number | null) => {
  import React from 'react';
  import useGainersData from '../../hooks/useGainersData';
  import useGainersLosersData from '../../hooks/useGainersLosersData';

  const formatPercent = (value?: number | null) =>
    typeof value === 'number' ? `${Math.round(value * 100)}%` : '—';

  const scoreLabel = (score?: number | null) => {
    if (score == null) return 'No signal';
    if (score >= 0.7) return 'Very Bullish';
    if (score >= 0.6) return 'Bullish';
    if (score <= 0.3) return 'Very Bearish';
    if (score <= 0.4) return 'Bearish';
    return 'Neutral';
  };

  export default function SentimentCard(): JSX.Element {
    const { data: gainers = [], isLoading: gLoading, error: gError } = useGainersData();
    const { data: glData = [], isLoading: glLoading, error: glError } = useGainersLosersData();

    const loading = Boolean(gLoading || glLoading);
    const error = gError || glError || null;

    if (loading) {
      return (
        <div className="rounded-2xl p-4 bg-black/30 border border-white/5">
          <div className="animate-pulse h-6 w-40 mb-2 bg-white/10 rounded" />
          <div className="animate-pulse h-4 w-64 bg-white/10 rounded" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="rounded-2xl p-4 bg-black/30 border border-pink-500/30 text-pink-300">
          <div className="font-semibold">Sentiment feed error</div>
          <div className="text-sm opacity-80">{String(error)}</div>
        </div>
      );
    }

    return (
      <div className="rounded-2xl p-4 bg-black/30 border border-white/5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold tracking-wide">Market Sentiment</h3>
          <span className="text-xs opacity-70">LIVE</span>
        </div>

        <div className="mt-3 grid gap-2">
          {Array.isArray(gainers) && gainers.slice(0, 8).map((row: any) => (
            <div
              key={row?.symbol}
              className="group relative flex items-center justify-between py-1.5"
            >
              <div className="text-sm font-mono">{row?.symbol}</div>
              <div className={`text-sm font-mono ${row?.changePct >= 0 ? 'text-blue-300' : 'text-pink-300'}`}>
                {typeof row?.changePct === 'number' ? `${row.changePct.toFixed(2)}%` : String(row?.changePct ?? '—')}
              </div>
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-blue-400/0 via-orange-400/40 to-pink-400/0" />
            </div>
          ))}
        </div>

        {Array.isArray(glData) && glData.length > 0 && (
          <div className="mt-4 text-xs opacity-70">
            {glData.length} pairs monitored
          </div>
        )}
      </div>
    );
  }
        setError(null);
