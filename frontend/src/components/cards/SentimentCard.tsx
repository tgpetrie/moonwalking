import React, { useEffect, useState } from 'react';
import useGainersData from '../../hooks/useGainersData';
import useGainersLosersData from '../../hooks/useGainersLosersData';

type SentimentVariant = 'inline' | 'modal';

type SentimentCardProps = {
  open?: boolean;            // when variant === 'modal', controls visibility
  onClose?: () => void;      // called when close requested (X, overlay click, or Escape)
  variant?: SentimentVariant;
};

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
  if (score == null) return 'No signal';
  if (score >= 0.7) return 'Very Bullish';
  if (score >= 0.6) return 'Bullish';
  if (score <= 0.3) return 'Very Bearish';
  if (score <= 0.4) return 'Bearish';
  return 'Neutral';
};

const coinbaseUrlFor = (symbol?: string) =>
  symbol ? `https://www.coinbase.com/price/${symbol.toLowerCase()}` : '#';

export default function SentimentCard({
  open = true,
  onClose,
  variant = 'inline',
}: SentimentCardProps): JSX.Element {
  const { data: gainers = [], isLoading: gLoading, error: gError } = useGainersData();
  const { data: glData = [], isLoading: glLoading, error: glError } = useGainersLosersData();

  const [activeTab, setActiveTab] = useState<TabId | null>(null);

  const loading = Boolean(gLoading || glLoading);
  const error = gError || glError || null;

  const handleToggleTab = (tabId: TabId) => {
    setActiveTab((current) => (current === tabId ? null : tabId));
  };

  // Close on Escape when used as a modal
  useEffect(() => {
    if (variant !== 'modal' || !open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [variant, open, onClose]);

  const renderShell = (content: React.ReactNode) => {
    if (variant !== 'modal') return content;
    if (!open) return null;

    return (
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-0 z-50 flex items-center justify-center"
      >
        {/* overlay */}
        <button
          aria-label="Close sentiment"
          onClick={onClose}
          className="absolute inset-0 bg-black/60"
        />
        {/* panel */}
        <div className="relative w-full max-w-md mx-4 rounded-2xl bg-black/80 border border-white/10 backdrop-blur-md shadow-2xl outline-none">
          {/* close button */}
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="absolute right-2 top-2 h-8 w-8 grid place-items-center rounded-full bg-white/10 text-white/80 hover:bg-white/20"
          >
            ×
          </button>
          <div className="p-4">
            {content}
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return renderShell(
      <div className="rounded-2xl p-4 bg-black/30 border border-white/5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Market Sentiment</h3>
          <span>LIVE</span>
        </div>
        <div className="animate-pulse h-6 w-40 mt-3 mb-2 bg-white/10 rounded" />
        <div className="animate-pulse h-4 w-64 bg-white/10 rounded" />
      </div>
    );
  }

  if (error) {
    return renderShell(
      <div className="rounded-2xl p-4 bg-black/30 border border-pink-500/30 text-pink-300">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Market Sentiment</h3>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="ml-2 h-7 w-7 grid place-items-center rounded-full bg-white/10 text-white/80 hover:bg-white/20"
          >
            ×
          </button>
        </div>
        <div className="mt-2">Sentiment feed error</div>
        <div className="opacity-80">{String(error)}</div>
      </div>
    );
  }

  return renderShell(
    <div className="rounded-2xl p-4 bg-black/30 border border-white/5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Market Sentiment</h3>
        <div className="flex items-center gap-2">
          <span>LIVE</span>
          {variant === 'modal' && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="h-7 w-7 grid place-items-center rounded-full bg-white/10 text-white/80 hover:bg-white/20"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Placeholder for future alert integration */}
      <div className="mt-2 mb-3">
        {/* Alerts will appear here */}
      </div>

      {activeTab === null && (
        <div className="mt-3 grid gap-2">
          {Array.isArray(gainers) && gainers.slice(0, 8).map((row: any) => (
            <a
              key={row?.symbol}
              href={coinbaseUrlFor(row?.symbol)}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative flex items-center justify-between py-1.5 rounded hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
            >
              <div className="underline decoration-transparent group-hover:decoration-current">
                {row?.symbol}
              </div>
              <div className={`tabular-nums ${row?.changePct >= 0 ? 'text-blue-300' : 'text-pink-300'}`}>
                {typeof row?.changePct === 'number' ? `${row.changePct.toFixed(2)}%` : String(row?.changePct ?? '—')}
              </div>
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-blue-400/0 via-orange-400/40 to-pink-400/0" />
            </a>
          ))}
        </div>
      )}

      {Array.isArray(glData) && glData.length > 0 && activeTab === null && (
        <div className="mt-4 opacity-70">
          {glData.length} pairs monitored
        </div>
      )}

      {/* Tabs */}
      <div className="mt-4 flex space-x-3 select-none">
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab.id}
            onClick={() => handleToggleTab(tab.id)}
            className={`px-3 py-1 rounded-full transition-colors ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-white/70 hover:bg-white/20'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab !== null && (
        <div className="mt-4">
          {activeTab === 'overview' && (
            <div>Overview content coming soon.</div>
          )}
          {activeTab === 'bulls' && (
            <div>Bullish sentiment data will be displayed here.</div>
          )}
          {activeTab === 'bears' && (
            <div>Bearish sentiment data will be displayed here.</div>
          )}
          {activeTab === 'social' && (
            <div>Social buzz data will be displayed here.</div>
          )}
        </div>
      )}
    </div>
  );
}
