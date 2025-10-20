import React, { useEffect, useMemo, useState } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';

// Tiny floating overlay for live debugging
export default function DebugOverlay() {
  const { isConnected, connectionStatus, isPolling, networkStatus, latestData, gainersTop20, gainers3mTop, losers3mTop, refreshNow } = useWebSocket();
  const initialVisible = useMemo(() => {
    try {
      const qs = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
      if (qs?.has('debug')) return true;
      if (typeof window !== 'undefined' && window.__DEBUG_HUD) return true;
      if (typeof localStorage !== 'undefined' && localStorage.getItem('debugHud') === '1') return true;
    } catch {}
    return false;
  }, []);
  const [visible, setVisible] = useState(initialVisible);
  const [expanded, setExpanded] = useState(false);

  const counts = useMemo(() => ({
    oneMin: Array.isArray(gainersTop20) ? gainersTop20.length : 0,
    crypto: Array.isArray(latestData?.crypto) ? latestData.crypto.length : 0,
    g3: Array.isArray(gainers3mTop) ? gainers3mTop.length : 0,
    l3: Array.isArray(losers3mTop) ? losers3mTop.length : 0,
  }), [gainersTop20, latestData?.crypto, gainers3mTop, losers3mTop]);

  const cDot = isConnected ? 'bg-emerald-400' : 'bg-red-500';
  const pDot = isPolling ? 'bg-yellow-400' : 'bg-gray-500';
  const nDot = networkStatus === 'good' ? 'bg-sky-400' : 'bg-orange-400';

  const preview = (arr) => Array.isArray(arr) ? arr.slice(0, 5).map(r => r.symbol).join(' · ') : '';

  useEffect(() => {
    const handler = (e) => {
      // Ctrl+Alt+D toggles
      if ((e.ctrlKey || e.metaKey) && e.altKey && (e.key === 'd' || e.key === 'D')) {
        e.preventDefault();
        setVisible(v => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    try { localStorage.setItem('debugHud', visible ? '1' : '0'); } catch {}
    try { window.__DEBUG_HUD = visible; } catch {}
  }, [visible]);

  return (
    <div className="fixed top-0 left-0 z-[60] select-text">
      {!visible && (
        <button
          aria-label="Open Debug HUD (Ctrl+Alt+D)"
          title="Open Debug HUD (Ctrl+Alt+D)"
          onClick={() => setVisible(true)}
          className="m-2 w-3 h-3 rounded-full bg-purple-500/60 hover:bg-purple-400/90 border border-purple-300/40 shadow"
        />
      )}
      {visible && (
      <div className="rounded-lg border border-purple-800/60 bg-black/75 backdrop-blur px-3 py-2 text-xs text-gray-200 shadow-xl">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${cDot}`} title="WebSocket" />
          <span className="font-mono">WS: {connectionStatus}</span>
          <span className={`inline-block w-2 h-2 rounded-full ${pDot}`} title="Polling" />
          <span>poll:{String(isPolling)}</span>
          <span className={`inline-block w-2 h-2 rounded-full ${nDot}`} title="Network" />
          <span>net:{networkStatus}</span>
          <span className="ml-2">1m:{counts.oneMin}</span>
          <span>3m↑:{counts.g3}</span>
          <span>3m↓:{counts.l3}</span>
          <button
            onClick={() => setExpanded(e => !e)}
            className="ml-2 px-2 py-0.5 rounded bg-purple-700/40 hover:bg-purple-700/60 text-white"
            aria-pressed={expanded}
          >{expanded ? 'Hide' : 'More'}</button>
          <button
            onClick={() => { try { refreshNow?.(); } catch {} }}
            className="ml-1 px-2 py-0.5 rounded bg-slate-700/50 hover:bg-slate-700/70"
          >Refresh</button>
          <button
            onClick={() => setVisible(false)}
            className="ml-1 px-2 py-0.5 rounded bg-zinc-700/50 hover:bg-zinc-700/70"
          >Close</button>
        </div>
        {expanded && (
          <div className="mt-2 space-y-1">
            <div><span className="text-gray-400">crypto:</span> {counts.crypto} {preview(latestData?.crypto)}</div>
            <div><span className="text-gray-400">1m:</span> {counts.oneMin} {preview(gainersTop20)}</div>
            <div><span className="text-gray-400">3m↑:</span> {counts.g3} {preview(gainers3mTop)}</div>
            <div><span className="text-gray-400">3m↓:</span> {counts.l3} {preview(losers3mTop)}</div>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
