import React, { Suspense, lazy } from 'react';
import WebSocketProvider, { useWebSocket } from './context/websocketcontext.jsx';

const TopBannerScroll    = lazy(() => import('./components/TopBannerScroll.jsx'));
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'));
const Gainers1m          = lazy(() => import('./components/Gainers1MinSplit.tsx'));
const Gainers3m          = lazy(() => import('./components/Gainers3Min.tsx'));
const Losers3m           = lazy(() => import('./components/Losers3Min.tsx'));
const Watchlist          = lazy(() => import('./components/Watchlist.tsx'));

function LiveDot(){
  const { socket } = useWebSocket() || {};
  const online = !!(socket && socket.connected);
  return <span className={`fx-live ${online? '' : 'off'}`} title={online? 'live':'offline'} />;
}

export default function App() {
  return (
    <WebSocketProvider>
      <div className="min-h-screen bg-bhblack text-white font-headline">
        <Suspense fallback={<div className="p-6 text-sm text-zinc-400">Loading…</div>}>
          <div className="flex items-center justify-between px-4 py-3">
            <TopBannerScroll />
            <div className="flex items-center gap-2 text-xs opacity-70">
              <LiveDot /> <span className="hidden sm:inline">LIVE</span>
            </div>
          </div>
          
          <div className="cbm-layout-main">
            {/* 1-Minute Gainers Split Layout (1-4, 5-8) */}
            <Gainers1m />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <Gainers3m />
              <Losers3m />
            </div>
            
            {/* Full-Width Watchlist */}
            <div className="cbm-watchlist-container">
              <Watchlist />
            </div>
          </div>
          
          <BottomBannerScroll />
        </Suspense>
      </div>
    </WebSocketProvider>
  );
}
