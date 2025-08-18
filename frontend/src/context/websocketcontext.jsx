// src/context/websocketcontext.jsx
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { io } from 'socket.io-client'

// Robust WebSocket context with safe defaults and state management
const initialState = {
  connected: false,
  prices: {},         // latest prices by symbol
  crypto: [],         // latest crypto array (gain/loss payloads)
  alerts: [],         // alert array
  server: null,       // server info
}
export const WebSocketContext = createContext({
  state: initialState,
  latestData: initialState,
  isConnected: false,
  isPolling: false,
  oneMinThrottleMs: 7000,
  getPrice: () => null,
})

export function useWebSocket() {
  return useContext(WebSocketContext)
}

export function WebSocketProvider({ children }) {
  const [state, setState] = useState(initialState)
  const socketRef = useRef(null)

  useEffect(() => {
    let canceled = false
  // Prefer an explicit WS/API env var if provided (Vite: VITE_*). Support multiple names used historically.
  const envBackend = import.meta.env.VITE_WS_URL || import.meta.env.VITE_BACKEND_URL || import.meta.env.VITE_API_URL

    // Helper: probe a candidate baseUrl by hitting /api/health
    const probe = async (candidate) => {
      try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 1200);
        const resp = await fetch(`${candidate.replace(/\/$/, '')}/api/health`, { signal: controller.signal });
        clearTimeout(id);
        return resp.ok;
      } catch (e) {
        return false;
      }
    }

    const startSocket = async () => {
      if (canceled) return;
      let baseUrl = null;
      if (envBackend) baseUrl = String(envBackend).replace(/\/+$/, '');
      else {
        // Prefer the exact current origin first (handles dev server ports like :5177)
        const origin = window.location.origin;
        const hostNoPort = `${window.location.protocol}//${window.location.hostname}`;
        // Try origin first. If the current origin has no port, also try common backend ports on the host.
        const candidates = [origin];
        if (!window.location.port) {
          candidates.push(`${hostNoPort}:5001`, `${hostNoPort}:5002`);
        }
        // Localhost fallbacks
        candidates.push('http://127.0.0.1:5001', 'http://127.0.0.1:5002');
        for (const c of candidates) {
          if (canceled) break;
          // eslint-disable-next-line no-await-in-loop
          const ok = await probe(c);
          if (ok) { baseUrl = c; break; }
        }
      }
      // Fallback to default (non-probed) if nothing responsive found
      if (!baseUrl) baseUrl = envBackend ? String(envBackend).replace(/\/+$/, '') : `${window.location.protocol}//${window.location.hostname}:5001`;

      try {
        // Debug: surface which backend we ended up choosing (helps diagnose connection-refused issues)
        try { console.debug('[WS] selected backend baseUrl ->', baseUrl) } catch (e) {}
        const socket = io(baseUrl, { transports: ['websocket', 'polling'], path: '/socket.io' })
        socketRef.current = socket
      const onConnect = () => { if (!canceled) setState(prev => ({ ...prev, connected: true })) }
      const onDisconnect = () => { if (!canceled) setState(prev => ({ ...prev, connected: false })) }
      const onPrices = payload => { 
        if (canceled) return
        try {
          // Normalize payload shapes:
          // - server may send { prices: { 'BTC-USD': {...} } }
          // - or a compact map { 'BTC-USD': { price, change, timestamp }}
          // - or a flat numeric mapping { 'BTC-USD': 12345 }
          let normalized = {}
          if (!payload) normalized = {}
          else if (payload.prices && typeof payload.prices === 'object') {
            normalized = payload.prices
          } else if (typeof payload === 'object' && !Array.isArray(payload)) {
            // assume keyed by symbol
            normalized = payload
          } else {
            normalized = {}
          }
          // Map compact keys to a consistent shape: { price, change24h }
          const mapped = {}
          Object.keys(normalized).forEach(sym => {
            const v = normalized[sym]
            if (v == null) return
            if (typeof v === 'number') mapped[sym] = { price: v }
            else if (typeof v === 'object') {
              // Prioritize common keys
              const price = v.price ?? v.current_price ?? v.currentPrice ?? v.p ?? v.last ?? v.value
              const change24h = v.change24h ?? v.change_24h ?? v['24h'] ?? v.change
              mapped[sym] = { price, change24h, ...v }
            }
          })
          // Temporary debug: surface compact arrival info for quick verification in browser DevTools
          try {
            const keys = Object.keys(mapped)
            console.debug('[WS] prices arrived', { count: keys.length, sample: keys.slice(0, 5) })
          } catch (d) {}
          if (!canceled) setState(prev => ({ ...prev, prices: mapped }))
        } catch (e) {
          // If normalization fails, keep previous prices
        }
      }
      const onCrypto = payload => {
        if (canceled) return
        try {
          // payload may be:
          // - an array of coin objects (legacy)
          // - an object { crypto: [...] }
          // - an object { gainers: [...], losers: [...], banner: [...], top24h: [...] }
          if (Array.isArray(payload)) {
            // log arrival (array legacy shape)
            try { console.debug('[WS] crypto arrived (array)', { count: payload.length }) } catch (d) {}
            setState(prev => ({ ...prev, crypto: payload, crypto_meta: null }))
            return
          }
          if (Array.isArray(payload?.crypto)) {
            try { console.debug('[WS] crypto arrived (payload.crypto)', { count: payload.crypto.length }) } catch (d) {}
            setState(prev => ({ ...prev, crypto: payload.crypto, crypto_meta: null }))
            return
          }
          // If backend sends structured object with categories
          if (payload && (Array.isArray(payload.gainers) || Array.isArray(payload.losers))) {
            const gainers = Array.isArray(payload.gainers) ? payload.gainers : []
            try { console.debug('[WS] crypto arrived (structured)', { gainers: gainers.length, losers: Array.isArray(payload.losers) ? payload.losers.length : 0 }) } catch (d) {}
            setState(prev => ({ ...prev, crypto: gainers, crypto_meta: payload }))
            return
          }
        } catch (e) {
          // ignore and keep previous crypto state
        }
      }
      const onAlerts = payload => { if (!canceled) setState(prev => ({ ...prev, alerts: Array.isArray(payload) ? payload : prev.alerts })) }
      socket.on('connect', onConnect)
      socket.on('disconnect', onDisconnect)
  socket.on('prices', onPrices)
  socket.on('crypto', onCrypto)
  socket.on('alerts', onAlerts)
      // seed server info if available
      import('../lib/api').then(({ getJSON }) => getJSON('/api/server-info')
        .then(server => { if (!canceled) setState(prev => ({ ...prev, server })) })
        .catch(() => {})
      )
      return () => { canceled = true; try { socketRef.current && socketRef.current.off('prices', onPrices); socketRef.current && socketRef.current.off('crypto', onCrypto); socketRef.current && socketRef.current.off('alerts', onAlerts); socketRef.current && socketRef.current.off('connect'); socketRef.current && socketRef.current.off('disconnect'); } catch {} ; socketRef.current && socketRef.current.close() }
      } catch {
        setState(prev => ({ ...prev, connected: false }))
      }
    }
    startSocket()
  }, [])

  const value = useMemo(() => ({
    state,
    latestData: state,
    isConnected: !!state.connected,
    isPolling: false,
    oneMinThrottleMs: state.server?.oneMinThrottleMs ?? 7000,
    // small helpers
    getPrice: (sym) => state.prices?.[sym] ?? null,
  }), [state])
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}
export default WebSocketProvider
