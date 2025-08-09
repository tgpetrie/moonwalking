import './env-debug.js';
import React, { useEffect, useState } from 'react';
import { WebSocketProvider } from './context/websocketcontext.jsx';
// import { supabase } from './api'; // Supabase removed
import AuthPanel from './components/AuthPanel';
import GainersTable from './components/GainersTable';
import LosersTable from './components/LosersTable';
import TopBannerScroll from './components/TopBannerScroll';
import BottomBannerScroll from './components/BottomBannerScroll';
import { FiRefreshCw } from 'react-icons/fi';
import GainersTable1Min from './components/GainersTable1Min';
import Watchlist from './components/Watchlist';
import WatchlistInsightsPanel from './components/WatchlistInsightsPanel.jsx';

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
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5001'}/api`);
        setIsConnected(response.ok);
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
    // If we are checking auth, but user is already null, show AuthPanel
    if (!user) {
      return <AuthPanel onAuth={() => window.location.reload()} />;
    }
    return <div className="min-h-screen flex items-center justify-center bg-dark text-white text-xl">Checking authentication...</div>;
  }
  if (!user) {
    return <AuthPanel onAuth={() => window.location.reload()} />;
  }

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
          className="w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-r from-purple-600 to-purple-900 text-white shadow-lg transform transition-all duration-300 hover:scale-105 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-purple-400"
          aria-label="Refresh"
        >
          <FiRefreshCw className="text-xl text-purple-300" />
        </button>
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
        <button
          onClick={() => setShowInsights(s => !s)}
          className="rounded-full px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white text-xs font-bold shadow-lg focus:outline-none focus:ring-2 focus:ring-purple-400"
          aria-pressed={showInsights}
        >
          {showInsights ? 'Hide Insights' : 'Insights'}
        </button>
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
        {/* Top Banner - 1H Price */}
        <div className="mb-8 -mx-16 sm:-mx-24 lg:-mx-32 xl:-mx-40">
          <TopBannerScroll refreshTrigger={lastUpdate} />
        </div>
        {/* Refresh Button */}
        <div className="flex justify-center mb-8">
        </div>
        {/* Main Content - Side by Side Panels */}

        {/* 1-Minute Gainers Table & Watchlist Side by Side */}
        <div className="mb-8">
          <div className="flex flex-col lg:flex-row gap-8">
            {/* 1-Minute Gainers Table */}
            <div className={`p-6 bg-transparent ${topWatchlist.length === 0 ? 'w-full' : 'flex-1'}`}>
              <div className="flex items-center gap-3 mb-6">
                <h2 className="text-xl font-headline font-bold text-blue tracking-wide">
                  1-MIN GAINERS
                </h2>
              </div>
              {/* Line divider directly under 1-MIN GAINERS header */}
              <div className="flex justify-start mb-4">
                <img
                  src="/linediv.png"
                  alt="Divider"
                  className="w-48 h-auto"
                  style={{ maxWidth: '100%' }}
                />
              </div>
              <GainersTable1Min onWatchlistChange={handleWatchlistChange} topWatchlist={topWatchlist} />
            </div>
            {/* Watchlist column removed intentionally for cleaner layout */}
          </div>
        </div>

        {/* 3-Minute Gainers and Losers Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Left Panel - 3-MIN GAINERS */}
          <div className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-xl font-headline font-bold text-blue tracking-wide">
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
            <GainersTable refreshTrigger={lastUpdate} />
          </div>

          {/* Right Panel - 3-MIN LOSERS */}
          <div className="p-6">
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
            <LosersTable refreshTrigger={lastUpdate} />
          </div>
        </div>
  {/* Full watchlist section removed */}
        {/* Bottom Banner - 1H Volume */}
        <div className="mb-8 -mx-16 sm:-mx-24 lg:-mx-32 xl:-mx-40">
          <BottomBannerScroll refreshTrigger={lastUpdate} />
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
    </div>
    </WebSocketProvider>
  );
}
