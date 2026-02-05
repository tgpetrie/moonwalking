import React, { useState, Suspense } from 'react';
import TradingViewChart from './TradingViewChart.jsx';
import SentimentCard from './cards/SentimentCard.jsx';

const WatchlistInsightsPanel = React.lazy(() => import('./WatchlistInsightsPanel.jsx'));

export default function MetricsPanel() {
  const [tab, setTab] = useState('chart');

  return (
    <div className="w-48 bg-black/60 rounded-xl border border-gray-800 p-2 text-sm">
      <div className="flex space-x-1 mb-2">
        <button
          onClick={() => setTab('chart')}
          className={`flex-1 px-2 py-1 rounded ${tab === 'chart' ? 'bg-purple-700 text-white' : 'bg-black/30 text-gray-300'}`}>
          Chart
        </button>
        <button
          onClick={() => setTab('sentiment')}
          className={`flex-1 px-2 py-1 rounded ${tab === 'sentiment' ? 'bg-purple-700 text-white' : 'bg-black/30 text-gray-300'}`}>
          Sentiment
        </button>
        <button
          onClick={() => setTab('insights')}
          className={`flex-1 px-2 py-1 rounded ${tab === 'insights' ? 'bg-purple-700 text-white' : 'bg-black/30 text-gray-300'}`}>
          Insights
        </button>
      </div>

      <div className="h-28 overflow-hidden">
        {tab === 'chart' && (
          <div className="h-full">
            <TradingViewChart small />
          </div>
        )}

        {tab === 'sentiment' && (
          <div className="h-full flex items-center justify-center">
            <SentimentCard />
          </div>
        )}

        {tab === 'insights' && (
          <div className="h-full">
            <Suspense fallback={<div className="text-xs text-gray-400 p-2">Loading...</div>}>
              <WatchlistInsightsPanel compact />
            </Suspense>
          </div>
        )}
      </div>
    </div>
  );
}
