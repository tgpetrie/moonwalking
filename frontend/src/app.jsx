import './env-debug.js';
import React, { useEffect, useState, Suspense } from 'react';
import { API_ENDPOINTS } from './api.js';
import { WebSocketProvider, useWebSocket } from './context/websocketcontext.jsx';
import ToastProvider from './components/ToastProvider.jsx';
//
import OneMinGainersColumns from './components/OneMinGainersColumns.jsx';
import ManualRefreshButton from './components/ManualRefreshButton.jsx';
import FloatingActionMenu from './components/FloatingActionMenu.jsx';
import CountdownMeter from './components/CountdownMeter.jsx';
// Eager (tiny) components
import AuthPanel from './components/AuthPanel';
import AlertsIndicator from './components/AlertsIndicator.jsx';

const MoverTable = React.lazy(() => import('./components/MoverTable.jsx'));
const GainersTable1Min = React.lazy(() => import('./components/GainersTable1Min'));
import Watchlist from './components/Watchlist';
import TopBannerScroll from './components/TopBannerScroll.jsx';
import BottomBannerScroll from './components/BottomBannerScroll.jsx';
import DebugOverlay from './components/DebugOverlay.jsx';
// useWebSocket imported via provider consumers inside other components only
import { flags } from './config.js';
const WatchlistInsightsPanel = React.lazy(() => import('./components/WatchlistInsightsPanel.jsx'));
const LastAlertTicker = React.lazy(() => import('./components/LastAlertTicker.jsx'));
const AskCodexPanel = React.lazy(() => import('./components/AskCodexPanel.jsx'));
const CodexPanel = React.lazy(() => import('./components/CodexPanel.jsx'));
const SentimentPanel = React.lazy(() => import('./components/SentimentPanel.jsx'));
// Mobile debugging component
const LearnPanel = React.lazy(() => import('./components/LearnPanel.jsx'));
// Data flow test component
import DataFlowTest from './components/DataFlowTest.jsx';
import { WatchlistProvider, useWatchlistContext } from './hooks/useWatchlist.jsx';
// SharedOneMinGainers appears unused directly here; keep as deferred import if needed later.
// const SharedOneMinGainers = React.lazy(() => import('./components/SharedOneMinGainers.jsx'));

// Live data polling interval (ms)
const POLL_INTERVAL = 30000;
// Feature toggles
const ENABLE_WATCHLIST_QUICKVIEW = false; // disabled per request to hide mini watchlist

const TopBanner = () => <TopBannerScroll />;
const BottomBanner = () => <BottomBannerScroll />;

function AppUI() {
  const { list: topWatchlist } = useWatchlistContext();
  const { isConnected, refreshNow } = useWebSocket();
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [user] = useState(() => {
    // Persist plan for easier testing across reloads
    const savedPlan = typeof window !== 'undefined' ? window.localStorage.getItem('userPlan') : 'free';
    return { id: 'dev-bypass', plan: savedPlan || 'free' };
  }); // 'free' or 'premium'
  const isPremium = user.plan === 'premium';
  const [checkingAuth] = useState(false);
  const [uiToggles, setUiToggles] = useState({ insights: false, sentiment: false, learn: false });
  const [oneMinExpanded, setOneMinExpanded] = useState(false);
  const [threeMinExpanded, setThreeMinExpanded] = useState(false);
  const [showCodex, setShowCodex] = useState(false);
  const setShowInsights = (updater) => setUiToggles(prev => ({ ...prev, insights: typeof updater === 'function' ? updater(prev.insights) : Boolean(updater) }));
  const setShowSentiment = (updater) => setUiToggles(prev => ({ ...prev, sentiment: typeof updater === 'function' ? updater(prev.sentiment) : Boolean(updater) }));
  const setShowLearn = (updater) => setUiToggles(prev => ({ ...prev, learn: typeof updater === 'function' ? updater(prev.learn) : Boolean(updater) }));
  const [codexCoin, setCodexCoin] = useState(null);

  // Poll backend connection and update countdown
  useEffect(() => {
    let intervalId;
    // This effect is now only for the timestamp display, not for data polling.
    intervalId = setInterval(() => setLastUpdate(new Date()), POLL_INTERVAL);
    return () => clearInterval(intervalId);
  }, []);
  
  const refreshGainersAndLosers = async () => {
    await refreshNow();
    setLastUpdate(new Date());
  };

  const handleSelectCoinForAnalysis = (symbol) => {
    setCodexCoin(symbol);
  };


  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark text-white text-xl">
        Checking authentication...
      </div>
    );
  }
  if (!user) {
    return <AuthPanel onAuth={() => window.location.reload()} />;
  }

  const chunkFallback = (label = 'Loading...') => (
    <div className="text-center text-xs text-gray-400 py-4 animate-pulse" aria-live="polite">{label}</div>
  );

  return (
    <div className="min-h-screen bg-dark text-white relative">
  <DebugOverlay />
      {/* MobileDebugger removed per request */}
      <DataFlowTest />
      {/* Background Purple Rabbit */}
      <div className="fixed inset-0 flex items-center justify-center pointer-events-none z-0">
        <img
          src="/purple-rabbit-bg.png"
          alt="BHABIT Background"
          className={"w-96 h-96 sm:w-[32rem] sm:h-[32rem] lg:w-[40rem] lg:h-[40rem] " + (typeof window !== 'undefined' && window.__BHABIT_BUNNY_ALERT ? 'bunny-alert' : '')}
          style={{ opacity: 0.05 }}
        />
      </div>

      {/* Countdown & Refresh (mini watchlist removed) */}
      <div className="fixed top-6 right-4 z-50 flex flex-col items-end gap-2">
        <div className="flex items-center gap-1 text-xs font-mono bg-black/40 px-3 py-1 rounded-full border border-gray-700">
          <span className={`inline-block w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}></span>
          <span>{isConnected ? 'LIVE' : 'OFFLINE'}</span>
        </div>
        <div className="flex items-center gap-2">
          <ManualRefreshButton onAfterRefresh={refreshGainersAndLosers} />
          <CountdownMeter durationMs={30000} running={!showCodex} keySeed={lastUpdate.getTime()} />
        </div>
        <div className="mt-1">
          <AlertsIndicator />
        </div>
        {/* Quickview removed (toggle retained if needed) */}
        {ENABLE_WATCHLIST_QUICKVIEW && topWatchlist.length > 0 && (
          <div className="mt-2 w-64 max-w-xs bg-black/70 rounded-xl shadow-lg border border-purple-900 p-2 animate-fade-in">
            <Watchlist quickview />
          </div>
        )}
      </div>

      {/* Panels toggled via floating menu */}
      <div className="fixed bottom-24 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
        {isPremium && (
          <Suspense fallback={chunkFallback('Loading panels...')}>
            {/* These components manage their own visibility and pointer events */}
            {/* Watchlist Insights */}
            <div className="pointer-events-auto"><WatchlistInsightsPanel /></div>
            {/* Sentiment Panel */}
            {uiToggles.sentiment && topWatchlist.length > 0 && (
              <div className="pointer-events-auto">
                <SentimentPanel symbols={topWatchlist.map(item => item.symbol || item.product_id || item)} />
              </div>
            )}
          </Suspense>
        )}
      </div>

      {/* Floating menu + lightweight operational metrics */}
      <FloatingActionMenu
        onRefresh={refreshGainersAndLosers}
        onToggleCodex={() => setShowCodex(s => !s)}
        onToggleInsights={() => setShowInsights(s => !s)}
        onToggleSentiment={() => setShowSentiment(s => !s)}
        onToggleLearn={() => setShowLearn(s => !s)}
        disabled={{
          refresh: false,
          codex: !isPremium,
          insights: !isPremium,
          sentiment: topWatchlist.length === 0 || !isPremium,
          learn: false,
        }}
      />
      {/* Metrics panel removed per user request */}

      {/* hidden state mounts: use toggles so linter sees state read */}
      <div className="hidden" aria-hidden>
        {uiToggles.insights ? 'insights-on' : 'insights-off'}
        {uiToggles.sentiment ? 'sentiment-on' : 'sentiment-off'}
        {uiToggles.learn ? 'learn-on' : 'learn-off'}
      </div>

      {/* Timestamp only at top-left */}
      <div className="fixed top-6 left-4 z-50">
        <div className="flex items-center gap-1 text-xs font-mono bg-black/40 px-3 py-1 rounded-full border border-gray-700">
          <span className="text-gray-400">Latest:</span>
          <span className="font-bold">{lastUpdate.toLocaleTimeString()}</span>
          <span className="text-gray-400">on</span>
          <span className="font-bold">{lastUpdate.toLocaleDateString()}</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header Section */}
        <header className="flex flex-col items-center justify-center pt-6 pb-5">
          {(() => {
            const size = flags.HEADER_SIZE || 'md';
            let mainHeights;
            if (size === 'sm') mainHeights = 'h-16 sm:h-20 lg:h-24';
            else if (size === 'lg') mainHeights = 'h-24 sm:h-28 lg:h-32';
            else mainHeights = 'h-20 sm:h-24 lg:h-28';
            let subHeights;
            if (size === 'sm') subHeights = 'h-8 sm:h-10 lg:h-12';
            else if (size === 'lg') subHeights = 'h-12 sm:h-14 lg:h-16';
            else subHeights = 'h-10 sm:h-12 lg:h-14';
            return (
              <>
                <div className="mb-3">
                  <img
                    src={flags.HEADER_LOGO_SRC}
                    alt="BHABIT"
                    className={`${mainHeights} animate-breathing`}
                  />
                </div>
                {flags.HEADER_SHOW_SUBLOGO && (
                  <img
                    src={flags.HEADER_SUBLOGO_SRC}
                    alt="PROFITS BY IMPULSE"
                    className={`${subHeights} mb-4 transition-all duration-300 hover:scale-105 hover:brightness-125`}
                  />
                )}
              </>
            );
          })()}
        </header>
  {/* Top Banner - 1H Price (lazy) */}
  <div className="mb-8 -mx-2 sm:-mx-8 lg:-mx-16 xl:-mx-24">
          <Suspense fallback={chunkFallback('Loading price banner...')}>
            <TopBanner />
          </Suspense>
        </div>
        {/* Refresh Button */}
        <div className="flex justify-center mb-8">
        </div>
        {/* Main Content - Side by Side Panels */}

  {/* 1-Minute Gainers - Two tables full width with a toggleable overlay Legend */}
  <div className="mb-4">
          <div className="px-0 py-6 bg-transparent w-full">
            <div className="relative">
              <div className="flex items-center justify-center gap-3 mb-6">
                <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400] text-center">
                  1-MIN GAINERS
                </h2>
              </div>
              {/* Line divider under header */}
              <div className="flex justify-center mb-4">
                <div className="section-divider" />
              </div>
              <Suspense fallback={chunkFallback('Loading 1-min gainers...')}>
                <OneMinGainersColumns
                  expanded={oneMinExpanded}
                  onSelectCoin={handleSelectCoinForAnalysis}
                />
              </Suspense>
              {/* Shared Show More below the two tables */}
              <div className="show-more-wrap">
                <button
                  onClick={() => setOneMinExpanded(v => !v)}
                  className="show-more"
                  aria-pressed={oneMinExpanded}
                >
                  {oneMinExpanded ? 'Show Less' : 'Show More'}
                </button>
              </div>
            </div>
          </div>
        </div>

  {/* 3-Minute Gainers and Losers (separate headers) */}
  <div className="mb-2">
          <div className="tables-grid">
            {/* Left Panel - 3-MIN GAINERS */}
            <div className="table-card">
              <div className="px-4 pt-4">
                <div className="flex items-center justify-center gap-3 mb-3">
                  <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400] text-center">3-MIN GAINERS</h2>
                </div>
                <div className="flex justify-center mb-2">
                  <div className="section-divider" />
                </div>
              </div>
              <Suspense fallback={(
                <div className="w-full h-full min-h-[400px] flex items-center justify-center">
                  <div className="animate-pulse text-muted font-mono">Loading 3-min gainers...</div>
                </div>
              )}>
                <MoverTable
                  tone="gainer"
                  fallbackEndpoint={API_ENDPOINTS.gainersTable3Min}
                  initialRows={7}
                  maxRows={13}
                  expanded={threeMinExpanded}
                  onSelectCoin={handleSelectCoinForAnalysis}
                />
              </Suspense>
            </div>

            {/* Right Panel - 3-MIN LOSERS */}
            <div className="table-card">
              <div className="px-4 pt-4">
                <div className="flex items-center justify-center gap-3 mb-3">
                  <h2 className="text-xl font-headline font-bold tracking-wide text-[#8A2BE2] text-center">3-MIN LOSERS</h2>
                </div>
                <div className="flex justify-center mb-2">
                  <div className="section-divider" />
                </div>
              </div>
              <Suspense fallback={(
                <div className="w-full h-full min-h-[400px] flex items-center justify-center">
                  <div className="animate-pulse text-muted font-mono">Loading 3-min losers...</div>
                </div>
              )}>
                <MoverTable
                  tone="loser"
                  fallbackEndpoint={API_ENDPOINTS.losersTable3Min}
                  initialRows={7}
                  maxRows={13}
                  expanded={threeMinExpanded}
                  onSelectCoin={handleSelectCoinForAnalysis}
                />
              </Suspense>
            </div>
          </div>

          {/* Shared Show More below the two 3‑min tables */}
          <div className="show-more-wrap">
            <button
              onClick={() => setThreeMinExpanded(v => !v)}
              className="show-more"
              aria-pressed={threeMinExpanded}
            >
              {threeMinExpanded ? 'Show Less' : 'Show More'}
            </button>
          </div>
        </div>

        {/* Watchlist below 3-Min tables */}
        <div className="mb-8">
          <div className="p-6 bg-transparent w-full">
            <div className="flex items-center justify-center gap-3 mb-6">
              <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400] text-center">WATCHLIST</h2>
            </div>
            <div className="flex justify-center mb-4">
              <div className="section-divider" />
            </div>
            <Watchlist onSelectCoin={handleSelectCoinForAnalysis} />
          </div>
        </div>
        {/* Last Alert Ticker + Bottom Banner - 1H Volume */}
        <div className="mb-8 -mx-2 sm:-mx-8 lg:-mx-16 xl:-mx-24">
          <div className="mx-2 sm:mx-8 lg:mx-16 xl:mx-24">
            <Suspense fallback={chunkFallback('Loading alerts...')}>
              <LastAlertTicker />
            </Suspense>
          </div>
          <Suspense fallback={chunkFallback('Loading volume banner...')}>
            <BottomBanner />
          </Suspense>
        </div>
        {/* Footer */}
        <footer className="text-center py-8 text-muted text-sm font-mono">
          <p className="flex items-center justify-center gap-2 flex-wrap">
            <span>© 2025 GUISAN DESIGN</span>
            <span className="inline-flex items-center align-middle">
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-orange text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
            </span>
            <span>BHABIT</span>
            <span className="inline-flex items-center align-middle">
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-orange text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
            </span>
            <span>TOM PETRIE</span>
          </p>
        </footer>
      </div>
      {isPremium && showCodex && (
        <Suspense fallback={chunkFallback('Loading Codex...')}>
          <AskCodexPanel onClose={() => setShowCodex(false)} />
        </Suspense>
      )}
      {codexCoin && (
        <Suspense fallback={chunkFallback('Loading Insights...')}>
          <CodexPanel
            isOpen={!!codexCoin}
            selectedCoin={codexCoin}
            onClose={() => setCodexCoin(null)}
          />
        </Suspense>
      )}
    </div>
  );
}

export default function App() {
  return (
    <WebSocketProvider>
      <ToastProvider>
        <WatchlistProvider refreshMs={10000}>
          <AppUI />
        </WatchlistProvider>
      </ToastProvider>
    </WebSocketProvider>
  );
}
