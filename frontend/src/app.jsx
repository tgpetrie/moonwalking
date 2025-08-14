import './env-debug.js';
import React, { useEffect, useState, Suspense } from 'react';
import { API_ENDPOINTS, fetchData } from './api.js';
import { WebSocketProvider } from './context/websocketcontext.jsx';
import { FiRefreshCw } from 'react-icons/fi';
// Eager (tiny) components
import AuthPanel from './components/AuthPanel';
const IndicatorLegend = React.lazy(() => import('./components/IndicatorLegend.jsx'));
import AlertsIndicator from './components/AlertsIndicator.jsx';

// Lazy-loaded (code split) heavier UI regions
const TopBannerScroll = React.lazy(() => import('./components/TopBannerScroll'));
const BottomBannerScroll = React.lazy(() => import('./components/BottomBannerScroll'));
const GainersTable = React.lazy(() => import('./components/GainersTable'));
const LosersTable = React.lazy(() => import('./components/LosersTable'));
const GainersTable1Min = React.lazy(() => import('./components/GainersTable1Min'));
import Watchlist from './components/Watchlist';
const WatchlistInsightsPanel = React.lazy(() => import('./components/WatchlistInsightsPanel.jsx'));
const LastAlertTicker = React.lazy(() => import('./components/LastAlertTicker.jsx'));
const AskCodexPanel = React.lazy(() => import('./components/AskCodexPanel.jsx'));
// SharedOneMinGainers appears unused directly here; keep as deferred import if needed later.
// const SharedOneMinGainers = React.lazy(() => import('./components/SharedOneMinGainers.jsx'));

// Live data polling interval (ms)
const POLL_INTERVAL = 30000;
// Feature toggles
const ENABLE_WATCHLIST_QUICKVIEW = false; // disabled per request to hide mini watchlist


export default function App() {
  const [isConnected, setIsConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [countdown, setCountdown] = useState(POLL_INTERVAL / 1000);
  const [topWatchlist, setTopWatchlist] = useState([]);
  const [user, setUser] = useState({ id: 'dev-bypass' });
  const [checkingAuth, setCheckingAuth] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [oneMinExpanded, setOneMinExpanded] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [showCodex, setShowCodex] = useState(false);

  // Handler to sync watchlist state from children
  const handleWatchlistChange = (list) => {
    setTopWatchlist(list || []);
  };

  // Poll backend connection and update countdown
  useEffect(() => {
    let intervalId;
    let countdownId;
    const checkConnection = async () => {
      try {
        const res = await fetchData(API_ENDPOINTS.serverInfo);
        setIsConnected(!!res && res.status === 'running');
      } catch (error) {
        setIsConnected(false);
      }
    };
    checkConnection();
    intervalId = setInterval(() => {
      checkConnection();
      setLastUpdate(new Date()); // Trigger refresh in child components
      setCountdown(POLL_INTERVAL / 1000);
    }, POLL_INTERVAL);
    countdownId = setInterval(() => {
      setCountdown((prev) => (prev > 1 ? prev - 1 : POLL_INTERVAL / 1000));
    }, 1000);
    return () => {
      clearInterval(intervalId);
      clearInterval(countdownId);
    };
  }, []);

  const refreshGainersAndLosers = () => {
    setLastUpdate(new Date()); // Trigger refresh in child components
    setCountdown(POLL_INTERVAL / 1000);
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
    <WebSocketProvider>
    <div className="min-h-screen bg-dark text-white relative">
      {/* Background Purple Rabbit */}
      <div className="fixed inset-0 flex items-center justify-center pointer-events-none z-0">
        <img
          src="/purple-rabbit-bg.png"
          alt="BHABIT Background"
          className="w-96 h-96 sm:w-[32rem] sm:h-[32rem] lg:w-[40rem] lg:h-[40rem]"
          style={{ opacity: 0.05 }}
        />
      </div>

      {/* Countdown & Refresh (mini watchlist removed) */}
      <div className="fixed top-6 right-4 z-50 flex flex-col items-end gap-2">
        <div className="flex flex-col items-end gap-1 w-28">
          <div className="flex items-center gap-1 text-xs font-mono bg-black/40 px-3 py-1 rounded-full border border-gray-700 w-full justify-between">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            <span className="font-bold tabular-nums">{String(countdown).padStart(2, '0')}</span>
          </div>
          {/* Progress bar for next refresh */}
            <div className="w-full h-1 bg-gray-700/60 rounded overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-600 via-purple-400 to-purple-700 transition-all duration-1000 ease-linear"
                style={{ width: `${((POLL_INTERVAL/1000 - countdown) / (POLL_INTERVAL/1000)) * 100}%` }}
              />
            </div>
        </div>
        <button
          onClick={refreshGainersAndLosers}
          className="w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-r from-purple-600 to-purple-900 text-white shadow-lg transform transition-all duration-300 hover:scale-110 hover:shadow-[0_0_25px_rgba(168,85,247,0.6)] focus:outline-none focus:ring-2 focus:ring-purple-400"
          aria-label="Refresh"
          title="Refresh"
        >
          <FiRefreshCw className="text-xl text-purple-300" />
        </button>
        <div className="mt-1">
          <AlertsIndicator />
        </div>
        {/* Quickview removed (toggle retained if needed) */}
        {ENABLE_WATCHLIST_QUICKVIEW && topWatchlist.length > 0 && (
          <div className="mt-2 w-64 max-w-xs bg-black/70 rounded-xl shadow-lg border border-purple-900 p-2 animate-fade-in">
            <Watchlist quickview topWatchlist={topWatchlist} onWatchlistChange={handleWatchlistChange} />
          </div>
        )}
      </div>

      {/* Floating Insights Toggle */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        {showInsights && (
          <WatchlistInsightsPanel />
        )}
        <div className="flex flex-col gap-2 items-end">
          <button
            onClick={() => setShowCodex(s => !s)}
            className="rounded-full px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white text-xs font-bold shadow-lg focus:outline-none focus:ring-2 focus:ring-purple-400"
            aria-pressed={showCodex}
          >{showCodex ? 'Close Codex' : 'Ask Codex'}</button>
          <button
            onClick={() => setShowInsights(s => !s)}
            className="rounded-full px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white text-xs font-bold shadow-lg focus:outline-none focus:ring-2 focus:ring-purple-400"
            aria-pressed={showInsights}
          >{showInsights ? 'Hide Insights' : 'Insights'}</button>
        </div>
        <button
          onClick={() => setShowInsights(s => !s)}
          className="hidden" aria-hidden="true" tabIndex={-1}>Insights</button>
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
        <header className="flex flex-col items-center justify-center pt-8 pb-6">
          <div className="mb-4">
            <img
              src="/bhabit-logo.png"
              alt="BHABIT"
              className="h-20 sm:h-24 lg:h-28 animate-breathing"
            />
          </div>
          <img
            src="/pbi.png"
            alt="PROFITS BY IMPULSE"
            className="h-10 sm:h-12 lg:h-14 mb-4 transition-all duration-300 hover:scale-105 hover:brightness-125"
          />
        </header>
  {/* Top Banner - 1H Price (lazy) */}
  <div className="mb-8 -mx-2 sm:-mx-8 lg:-mx-16 xl:-mx-24">
          <Suspense fallback={chunkFallback('Loading price banner...')}>
            <TopBannerScroll refreshTrigger={lastUpdate} />
          </Suspense>
        </div>
        {/* Refresh Button */}
        <div className="flex justify-center mb-8">
        </div>
        {/* Main Content - Side by Side Panels */}

  {/* 1-Minute Gainers - Two tables full width with a toggleable overlay Legend */}
  <div className="mb-4">
          <div className="p-6 bg-transparent w-full">
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400]">
                  1-MIN GAINERS
                </h2>
                <button
                  onClick={() => setShowLegend(v => !v)}
                  className="ml-2 px-2 py-1 rounded bg-black/40 hover:bg-black/60 border border-purple-900 text-[11px] text-white"
                  aria-pressed={showLegend}
                  aria-label="Toggle indicator legend"
                >
                  {showLegend ? 'Hide Legend' : 'Legend'}
                </button>
              </div>
              {/* Line divider under header */}
              <div className="flex justify-start mb-4">
                <img
                  src="/linediv.png"
                  alt="Divider"
                  className="w-48 h-auto"
                  style={{ maxWidth: '100%' }}
                />
              </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-3">
                <Suspense fallback={chunkFallback('Loading 1-min gainers...')}>
          <div className="p-6">
                    <GainersTable1Min
                      refreshTrigger={lastUpdate}
                      onWatchlistChange={handleWatchlistChange}
                      topWatchlist={topWatchlist}
                      sliceStart={0}
                      sliceEnd={20}
                      fixedRows={oneMinExpanded ? 6 : 4}
                      hideShowMore
                    />
                  </div>
          <div className="p-6">
                    <GainersTable1Min
                      refreshTrigger={lastUpdate}
                      onWatchlistChange={handleWatchlistChange}
                      topWatchlist={topWatchlist}
                      sliceStart={oneMinExpanded ? 6 : 4}
                      sliceEnd={20}
                      fixedRows={oneMinExpanded ? 6 : 4}
                      hideShowMore
                    />
                  </div>
                </Suspense>
              </div>
              {/* Shared Show More below the two tables */}
              <div className="w-full flex justify-center mt-2 mb-1">
                <button
                  onClick={() => setOneMinExpanded(v => !v)}
                  className="px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
                  aria-pressed={oneMinExpanded}
                >
                  {oneMinExpanded ? 'Show Less' : 'Show More'}
                </button>
              </div>
              {/* Overlay Legend (does not affect layout) */}
              {showLegend && (
                <div className="absolute top-0 right-0 z-40 w-full md:w-[420px] lg:w-[480px] xl:w-[520px] drop-shadow-xl">
                  <Suspense fallback={chunkFallback('Loading legend...')}>
                    <div className="font-raleway">
                      <IndicatorLegend onClose={() => setShowLegend(false)} />
                    </div>
                  </Suspense>
                </div>
              )}
            </div>
          </div>
        </div>

  {/* 3-Minute Gainers and Losers Tables (treat as single paired component for equal sizing) */}
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 items-stretch content-stretch">
          {/* Left Panel - 3-MIN GAINERS */}
    <div className="p-6 flex flex-col h-full">
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400]">
                3-MIN GAINERS
              </h2>
            </div>
            {/* Line divider directly under 3-MIN GAINERS header */}
            <div className="flex justify-start mb-4">
              <img
                src="/linediv.png"
                alt="Divider"
                className="w-48 h-auto"
                style={{ maxWidth: '100%' }}
              />
            </div>
            <div className="flex-1 flex flex-col">
              <Suspense fallback={chunkFallback('Loading 3-min gainers...')}>
                <GainersTable refreshTrigger={lastUpdate} />
              </Suspense>
            </div>
          </div>

          {/* Right Panel - 3-MIN LOSERS */}
          <div className="p-6 flex flex-col h-full">
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-xl font-headline font-bold text-pink tracking-wide">
                3-MIN LOSERS
              </h2>
            </div>
            {/* Line divider */}
            <div className="flex justify-start mb-4">
              <img
                src="/linediv.png"
                alt="Divider"
                className="w-48 h-auto"
                style={{ maxWidth: '100%' }}
              />
            </div>
            <div className="flex-1 flex flex-col">
              <Suspense fallback={chunkFallback('Loading 3-min losers...')}>
                <LosersTable refreshTrigger={lastUpdate} />
              </Suspense>
            </div>
          </div>
        </div>

        {/* Watchlist below 3-Min tables */}
        <div className="mb-8">
          <div className="p-6 bg-transparent w-full">
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-xl font-headline font-bold tracking-wide text-[#FEA400]">
                WATCHLIST
              </h2>
            </div>
            <div className="flex justify-start mb-4">
              <img
                src="/linediv.png"
                alt="Divider"
                className="w-48 h-auto"
                style={{ maxWidth: '100%' }}
              />
            </div>
            <Watchlist topWatchlist={topWatchlist} onWatchlistChange={handleWatchlistChange} />
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
            <BottomBannerScroll refreshTrigger={lastUpdate} />
          </Suspense>
        </div>
        {/* Footer */}
        <footer className="text-center py-8 text-muted text-sm font-mono">
          <p>
            © 2025 GUISAN DESIGN
            &nbsp;
            <span className="inline-flex items-center align-middle">
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-orange text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
            </span>
            &nbsp; BHABIT &nbsp;
            <span className="inline-flex items-center align-middle">
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-orange text-lg" style={{fontWeight: 900}}>⋆</span>
              <span className="text-purple text-lg mx-0.5" style={{fontWeight: 900}}>⋆</span>
              <span className="text-pink-400 text-lg" style={{fontWeight: 900}}>⋆</span>
            </span>
            &nbsp; TOM PETRIE
          </p>
        </footer>
      </div>
      {showCodex && (
        <Suspense fallback={chunkFallback('Loading Codex...')}>
          <AskCodexPanel onClose={() => setShowCodex(false)} />
        </Suspense>
      )}
    </div>
    </WebSocketProvider>
  );
}
