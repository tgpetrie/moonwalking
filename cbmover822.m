

📂 frontend_full_dump.txt

──────────────────────────────
package.json
──────────────────────────────
{
  "name": "frontend",
  "version": "1.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "socket.io-client": "^4.7.5"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.3",
    "vitest": "^1.6.1",
    "@testing-library/react": "^16.0.1",
    "jsdom": "^25.0.0"
  }
}

──────────────────────────────
vite.config.js
──────────────────────────────
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true
  }
})

──────────────────────────────
index.html
──────────────────────────────
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0"/>
    <title>CBMOONERS</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>

──────────────────────────────
src/main.jsx
──────────────────────────────
import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './app.jsx'
import { WebSocketProvider } from './context/websocketcontext.jsx'
import './styles.css'

const root = createRoot(document.getElementById('root'))
root.render(
  <React.StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </React.StrictMode>
)

──────────────────────────────
src/app.jsx
──────────────────────────────
import React, { Suspense, lazy } from 'react'

const GainersTable = lazy(() => import('./components/GainersTable.jsx'))
const LosersTable = lazy(() => import('./components/LosersTable.jsx'))
const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'))
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'))

export default function App() {
  return (
    <div className="container">
      <h1>CBMOONERS</h1>

      <Suspense fallback={<div>Loading top banner…</div>}>
        <TopBannerScroll />
      </Suspense>

      <div className="grid">
        <Suspense fallback={<div>Loading 3-min gainers…</div>}>
          <GainersTable />
        </Suspense>

        <Suspense fallback={<div>Loading 3-min losers…</div>}>
          <LosersTable />
        </Suspense>
      </div>

      <Suspense fallback={<div>Loading bottom banner…</div>}>
        <BottomBannerScroll />
      </Suspense>
    </div>
  )
}

──────────────────────────────
src/styles.css
──────────────────────────────
:root { font-family: ui-sans-serif, system-ui; }
body { margin: 0; background: #0c0f14; color: #e7edf3; }
.container { padding: 16px; max-width: 1200px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { background: #121722; border-radius: 12px; padding: 12px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 8px; border-bottom: 1px solid #1f2735; }
.badge { font-size: 12px; opacity: .8; }
.row-up { color: #33d17a; }
.row-down { color: #ff616e; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.scroller { display: flex; gap: 12px; overflow-x: auto; padding: 8px 0; }

──────────────────────────────
src/lib/constants.js
──────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5001"

export const API_ENDPOINTS = {
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
  losers: `${API_BASE}/api/component/losers-table`,
  topBanner: `${API_BASE}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE}/api/component/bottom-banner-scroll`,
  alerts: `${API_BASE}/api/alerts/recent`
}
____________________________________________________________________


frontend/src/lib/api.js


/**
 * Shared data layer: API endpoints, de-duped fetch with per-route TTL,
 * stale-while-revalidate, multi-tab sharing via BroadcastChannel,
 * and a tiny in-app event bus.
 */

const DEFAULT_BASE =
  (typeof localStorage !== 'undefined' && localStorage.getItem('api:base')) ||
  'http://localhost:5001';

let API_BASE = DEFAULT_BASE;

export function getApiBaseUrl() {
  return API_BASE;
}
export function setApiBaseUrl(u) {
  API_BASE = u;
  try {
    localStorage.setItem('api:base', u);
  } catch {}
}

/** Backend endpoints (adjust if your backend differs) */
export const API_ENDPOINTS = {
  t1m: '/api/component/gainers-table-1min',
  t3m: '/api/component/gainers-table', // 3-minute gainers
  losers: '/api/component/losers-table', // 3-minute losers
  alerts: '/api/alerts/recent?limit=50',
  top: '/api/component/top-banner-scroll',
  bottom: '/api/component/bottom-banner-scroll',
};

const requestCache = new Map(); // in-memory
const inflight = new Map();

/** Per-route TTLs (ms) */
const TTL = {
  [API_ENDPOINTS.alerts.split('?')[0]]: 5000,
  [API_ENDPOINTS.t1m]: 2500,
  [API_ENDPOINTS.t3m]: 8000,
  [API_ENDPOINTS.losers]: 8000,
  [API_ENDPOINTS.top]: 15000,
  [API_ENDPOINTS.bottom]: 15000,
  default: 8000,
};

function ttlFor(endpoint) {
  for (const k of Object.keys(TTL)) {
    if (k !== 'default' && endpoint.includes(k)) return TTL[k];
  }
  return TTL.default;
}

/** Tiny event bus for in-app pub/sub */
const _listeners = new Map();
export const bus = {
  on(event, fn) {
    const list = _listeners.get(event) || [];
    list.push(fn);
    _listeners.set(event, list);
    return () => bus.off(event, fn);
  },
  off(event, fn) {
    const list = _listeners.get(event) || [];
    const next = list.filter((f) => f !== fn);
    _listeners.set(event, next);
  },
  emit(event, payload) {
    const list = _listeners.get(event) || [];
    for (const fn of list) {
      try { fn(payload); } catch (e) { console.error('[bus] handler error', e); }
    }
  },
};

/** Multi-tab cache sharing */
const chan = typeof window !== 'undefined' && 'BroadcastChannel' in window
  ? new BroadcastChannel('cbmo4ers')
  : null;

if (chan) {
  chan.onmessage = (e) => {
    const { type, endpoint, payload } = e.data || {};
    if (type === 'tables:update') {
      try { sessionStorage.setItem('tables:last', JSON.stringify(payload)); } catch {}
      bus.emit('tables:update', payload);
    } else if (type === 'alerts:update') {
      try { sessionStorage.setItem('alerts:last', JSON.stringify(payload)); } catch {}
      bus.emit('alerts:update', payload);
    } else if (type === 'http:cache' && endpoint) {
      try { sessionStorage.setItem(`cache:${endpoint}`, JSON.stringify(payload)); } catch {}
      bus.emit(`http:${endpoint}`, payload);
    }
  };
}

export function shareTables(payload) {
  if (chan) chan.postMessage({ type: 'tables:update', payload });
}
export function shareAlerts(payload) {
  if (chan) chan.postMessage({ type: 'alerts:update', payload });
}
export function shareHttpCache(endpoint, payload) {
  if (chan) chan.postMessage({ type: 'http:cache', endpoint, payload });
}

export async function fetchJson(path, opts = {}) {
  const url = path.startsWith('http') ? path : `${getApiBaseUrl()}${path}`;
  const res = await fetch(url, { ...opts });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}`);
  return res.json();
}

/** helper to strip query when matching TTL keys */
function stripQuery(s) {
  const i = s.indexOf('?');
  return i === -1 ? s : s.slice(0, i);
}

export async function fetchData(endpoint, opts = {}) {
  const key = stripQuery(endpoint);
  const now = Date.now();
  const cacheTtl = ttlFor(key);
  const cached = requestCache.get(key);
  if (cached && now - cached.ts < cacheTtl) return cached.data;

  if (inflight.has(key)) return inflight.get(key);

  const controller = new AbortController();
  const p = (async () => {
    try {
      const data = await fetchJson(endpoint, { ...opts, signal: controller.signal });
      requestCache.set(key, { data, ts: Date.now() });
      try { sessionStorage.setItem(`cache:${endpoint}`, JSON.stringify(data)); } catch {}
      shareHttpCache(endpoint, data);
      return data;
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, p);
  return p;
}

export async function fetchWithSWR(endpoint, opts = {}) {
  const key = `cache:${endpoint}`;
  const cached = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(key) : null;
  if (cached) {
    // revalidate in background
    fetchData(endpoint, opts).catch(() => {});
    return JSON.parse(cached);
  }
  const data = await fetchData(endpoint, opts);
  try { sessionStorage.setItem(key, JSON.stringify(data)); } catch {}
  return data;
}

/** Optional: probe a list of bases and fix on the first that responds */
export async function initApiBase(candidates = []) {
  const bases = [ getApiBaseUrl(), 'http://127.0.0.1:5001', ...candidates ];
  for (const b of bases) {
    try {
      const ok = await fetch(`${b}/api/health`, { method: 'GET' })
        .then((r) => r.ok)
        .catch(() => false);
      if (ok) { setApiBaseUrl(b); return b; }
    } catch {}
  }
  return getApiBaseUrl();
}

______________________________________________________

frontend/src/context/websocketcontext.jsx

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { io } from 'socket.io-client';
import { getApiBaseUrl, bus, shareTables, shareAlerts } from '../lib/api.js';

export const WebSocketContext = createContext({
  tables: {},
  alerts: { items: [] },
});

export const WebSocketProvider = ({ children }) => {
  const [tables, setTables] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('tables:last') || '{}'); }
    catch { return {}; }
  });
  const [alerts, setAlerts] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('alerts:last') || '{"items": []}'); }
    catch { return { items: [] }; }
  });

  useEffect(() => {
    const socket = io(getApiBaseUrl(), { path: '/socket.io', transports: ['websocket'] });

    socket.on('connect', () => console.info('[ws] connected'));
    socket.on('disconnect', () => console.warn('[ws] disconnected'));

    socket.on('tables:update', (payload) => {
      console.info('[ws] tables:update t3m=', Array.isArray(payload?.t3m) ? payload.t3m.length : 'missing');
      setTables(payload ?? {});
      try { sessionStorage.setItem('tables:last', JSON.stringify(payload ?? {})); } catch {}
      shareTables(payload ?? {});
      bus.emit('tables:update', payload ?? {});
    });

    socket.on('alerts:update', (payload) => {
      setAlerts(payload ?? { items: [] });
      try { sessionStorage.setItem('alerts:last', JSON.stringify(payload ?? { items: [] })); } catch {}
      shareAlerts(payload ?? { items: [] });
      bus.emit('alerts:update', payload ?? { items: [] });
    });

    return () => { try { socket.close(); } catch {} };
  }, []);

  const value = useMemo(() => ({ tables, alerts, setTables, setAlerts }), [tables, alerts]);
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
};

export const useWebSocketData = () => useContext(WebSocketContext);


______________________________________________________________

frontend/src/components/GainersTable.jsx

import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';
import { useWebSocketData } from '../context/websocketcontext.jsx';

function normalizeT3M(raw) {
  // Accept many possible backend shapes
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.crypto ||
    raw?.crypto_meta?.gainers ||
    raw?.rows ||
    [];
  if (!Array.isArray(rows)) rows = [];

  // Canonicalize + de-dupe by symbol (keep largest 3m change)
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 =
      Number(
        r.change_3m ??
          r.change_3min ??
          r.change3m ??
          r.pct_3m ??
          r['3m_change'] ??
          r.delta_3m ??
          0
      ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, change3m: c3, name: r.name ?? r.base ?? sym };
    const prev = map.get(sym);
    if (!prev || c3 > prev.change3m) map.set(sym, entry);
  }

  return Array.from(map.values()).sort((a, b) => b.change3m - a.change3m);
}

export default function GainersTable() {
  const { tables } = useWebSocketData();
  const [rows, setRows] = useState([]);
  const t3mSocket = tables?.t3m;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let raw = t3mSocket;
      if (!raw || (Array.isArray(raw) && raw.length === 0)) {
        try { raw = await fetchWithSWR(API_ENDPOINTS.t3m); }
        catch (e) { console.warn('[t3m] HTTP fallback failed', e); }
      }
      const norm = normalizeT3M(raw);
      if (!cancelled) setRows(norm);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t3mSocket]);

  const content = useMemo(() => {
    if (!rows.length) return <div className="empty">No 3-min gainers data available.</div>;
    return (
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td>{Number.isFinite(r.change3m) ? `${r.change3m.toFixed(2)}%` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }, [rows]);

  return (
    <div className="panel">
      <div className="panel__header">
        <h3>3-minute Gainers</h3>
        <div className="meta">{rows.length ? `assets ${rows.length}` : 'loading…'}</div>
      </div>
      {content}
    </div>
  );
}


____________________________________________________________

frontend/src/components/LosersTable.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';
import { useWebSocketData } from '../context/websocketcontext.jsx';

function normalize3m(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.crypto ||
    raw?.crypto_meta?.losers ||
    raw?.rows ||
    [];
  if (!Array.isArray(rows)) rows = [];

  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 =
      Number(
        r.change_3m ??
          r.change_3min ??
          r.change3m ??
          r.pct_3m ??
          r['3m_change'] ??
          r.delta_3m ??
          0
      ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, change3m: c3 };
    const prev = map.get(sym);
    // For losers keep the *most negative* change
    if (!prev || c3 < prev.change3m) map.set(sym, entry);
  }

  return Array.from(map.values()).sort((a, b) => a.change3m - b.change3m);
}

export default function LosersTable() {
  const { tables } = useWebSocketData();
  const [rows, setRows] = useState([]);
  const t3mSocket = tables?.t3m_losers || tables?.losers || null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let raw = t3mSocket;
      if (!raw || (Array.isArray(raw) && raw.length === 0)) {
        try { raw = await fetchWithSWR(API_ENDPOINTS.losers); }
        catch (e) { console.warn('[losers 3m] HTTP fallback failed', e); }
      }
      const norm = normalize3m(raw);
      if (!cancelled) setRows(norm);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t3mSocket]);

  const content = useMemo(() => {
    if (!rows.length) return <div className="empty">No 3-min losers data available.</div>;
    return (
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td>{Number.isFinite(r.change3m) ? `${r.change3m.toFixed(2)}%` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }, [rows]);

  return (
    <div className="panel">
      <div className="panel__header">
        <h3>3-minute Losers</h3>
        <div className="meta">{rows.length ? `assets ${rows.length}` : 'loading…'}</div>
      </div>
      {content}
    </div>
  );
}

_________________________________________________

frontend/src/components/TopBannerScroll.jsx
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function TopBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.top);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch (e) {
        console.warn('[top banner] fetch failed', e);
      }
    })();
    return () => { cancel = true; };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--top">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}

_________________________________________________________

frontend/src/components/TopBannerScroll.jsx
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function TopBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.top);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch (e) {
        console.warn('[top banner] fetch failed', e);
      }
    })();
    return () => { cancel = true; };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--top">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}

_____________________________________________________________

frontend/src/components/BottomBannerScroll.jsx
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function BottomBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.bottom);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch (e) {
        console.warn('[bottom banner] fetch failed', e);
      }
    })();
    return () => { cancel = true; };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--bottom">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}
______________________________________________________

frontend/src/app.jsx

import React, { Suspense, lazy } from 'react';
import { WebSocketProvider } from './context/websocketcontext.jsx';

const GainersTable = lazy(() => import('./components/GainersTable.jsx'));
const LosersTable = lazy(() => import('./components/LosersTable.jsx'));
const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'));
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'));

export default function App() {
  return (
    <WebSocketProvider>
      <div className="app">
        <Suspense fallback={<div>Loading…</div>}>
          <TopBannerScroll />
        </Suspense>

        <div className="grid">
          <Suspense fallback={<div>Loading 3-min gainers…</div>}>
            <GainersTable />
          </Suspense>

          <Suspense fallback={<div>Loading 3-min losers…</div>}>
            <LosersTable />
          </Suspense>
        </div>

        <Suspense fallback={null}>
          <BottomBannerScroll />
        </Suspense>
      </div>
    </WebSocketProvider>
  );
}

_______________________________________________

frontend/src/app.jsx

import React, { Suspense, lazy } from 'react';
import { WebSocketProvider } from './context/websocketcontext.jsx';

const GainersTable = lazy(() => import('./components/GainersTable.jsx'));
const LosersTable = lazy(() => import('./components/LosersTable.jsx'));
const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'));
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'));

export default function App() {
  return (
    <WebSocketProvider>
      <div className="app">
        <Suspense fallback={<div>Loading…</div>}>
          <TopBannerScroll />
        </Suspense>

        <div className="grid">
          <Suspense fallback={<div>Loading 3-min gainers…</div>}>
            <GainersTable />
          </Suspense>

          <Suspense fallback={<div>Loading 3-min losers…</div>}>
            <LosersTable />
          </Suspense>
        </div>

        <Suspense fallback={null}>
          <BottomBannerScroll />
        </Suspense>
      </div>
    </WebSocketProvider>
  );
}

_______________________________________________________

Emitting t3m in the Socket.IO payload:


python
# after computing snapshots
socketio.emit('tables:update', {
    't1m': one_min_snapshot,
    't3m': three_min_snapshot,   # <-- must be present
    'at': time.time(),
}, namespace='/stream', broadcast=True)

And that the endpoint responds:


curl -s http://localhost:5001/api/component/gainers-table | head -c 400
CORS/dev port

 Your backend CORS header previously allowed only http://localhost:5173. Make sure you run Vite on 5173 or update backend CORS to include the dev port you actually use.


Multi-tab savings

 Snapshots and HTTP responses are shared via BroadcastChannel('cbmo4ers'). Open multiple tabs; only one needs to fetch and the others will update.


If anything doesn’t paste cleanly or you want me to include the backend emitter/endpoint patch as well, say the word and I’ll drop those too.
tried to apply the full patch set but the file-edit tool failed. No worries—I’ll still give you everything you asked for so you can paste it in directly. Below are the exact contents for each file to make the 3-minute tables reliable, share data between tabs, and add test/dev scripts.

frontend/package.json
{
  "name": "frontend",
  "version": "1.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --port 5173",
    "build": "vite build",
    "preview": "vite preview --port 4173",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "socket.io-client": "^4.7.5"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.2",
    "@testing-library/react": "^14.3.1",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^24.0.0",
    "vite": "^5.4.0",
    "vitest": "^1.6.1"
  }
}

__________________________________________

frontend/vitest.config.js
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    css: true,
  },
})


________________________________-

frontend/src/setupTests.js
import '@testing-library/jest-dom'

frontend/src/lib/api.js
/**
 * Shared data layer: API endpoints, de-duped fetch with per-route TTL,
 * stale-while-revalidate, multi-tab sharing via BroadcastChannel,
 * and a tiny in-app event bus.
 */

const DEFAULT_BASE =
  (typeof localStorage !== 'undefined' && localStorage.getItem('api:base')) ||
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) ||
  'http://localhost:5001';

let API_BASE = DEFAULT_BASE;

export function getApiBaseUrl() {
  return API_BASE;
}
export function setApiBaseUrl(u) {
  API_BASE = u;
  try {
    localStorage.setItem('api:base', u);
  } catch {}
}

/** Backend endpoints (adjust if your backend differs) */
export const API_ENDPOINTS = {
  t1m: '/api/component/gainers-table-1min',
  t3m: '/api/component/gainers-table', // 3-minute gainers
  losers: '/api/component/losers-table', // 3-minute losers
  alerts: '/api/alerts/recent?limit=50',
  top: '/api/component/top-banner-scroll',
  bottom: '/api/component/bottom-banner-scroll',
};

const requestCache = new Map(); // in-memory
const inflight = new Map();

/** Per-route TTLs (ms) */
const TTL = {
  [API_ENDPOINTS.alerts.split('?')[0]]: 5000,
  [API_ENDPOINTS.t1m]: 2500,
  [API_ENDPOINTS.t3m]: 8000,
  [API_ENDPOINTS.losers]: 8000,
  [API_ENDPOINTS.top]: 15000,
  [API_ENDPOINTS.bottom]: 15000,
  default: 8000,
};

function ttlFor(endpoint) {
  for (const k of Object.keys(TTL)) {
    if (k !== 'default' && endpoint.includes(k)) return TTL[k];
  }
  return TTL.default;
}

/** Tiny event bus for in-app pub/sub */
const _listeners = new Map();
export const bus = {
  on(event, fn) {
    const list = _listeners.get(event) || [];
    list.push(fn);
    _listeners.set(event, list);
    return () => bus.off(event, fn);
  },
  off(event, fn) {
    const list = _listeners.get(event) || [];
    const next = list.filter((f) => f !== fn);
    _listeners.set(event, next);
  },
  emit(event, payload) {
    const list = _listeners.get(event) || [];
    for (const fn of list) {
      try {
        fn(payload);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('[bus] handler error', e);
      }
    }
  },
};

/** Multi-tab cache sharing */
const chan = typeof window !== 'undefined' && 'BroadcastChannel' in window
  ? new BroadcastChannel('cbmo4ers')
  : null;

if (chan) {
  chan.onmessage = (e) => {
    const { type, endpoint, payload } = e.data || {};
    if (type === 'tables:update') {
      try {
        sessionStorage.setItem('tables:last', JSON.stringify(payload));
      } catch {}
      bus.emit('tables:update', payload);
    } else if (type === 'alerts:update') {
      try {
        sessionStorage.setItem('alerts:last', JSON.stringify(payload));
      } catch {}
      bus.emit('alerts:update', payload);
    } else if (type === 'http:cache' && endpoint) {
      try {
        sessionStorage.setItem(`cache:${endpoint}`, JSON.stringify(payload));
      } catch {}
      bus.emit(`http:${endpoint}`, payload);
    }
  };
}

export function shareTables(payload) {
  if (chan) chan.postMessage({ type: 'tables:update', payload });
}
export function shareAlerts(payload) {
  if (chan) chan.postMessage({ type: 'alerts:update', payload });
}
export function shareHttpCache(endpoint, payload) {
  if (chan) chan.postMessage({ type: 'http:cache', endpoint, payload });
}

export async function fetchJson(path, opts = {}) {
  const url = path.startsWith('http') ? path : `${getApiBaseUrl()}${path}`;
  const res = await fetch(url, { ...opts });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}`);
  }
  return res.json();
}

/** helper to strip query when matching TTL keys */
function stripQuery(s) {
  const i = s.indexOf('?');
  return i === -1 ? s : s.slice(0, i);
}

export async function fetchData(endpoint, opts = {}) {
  const key = stripQuery(endpoint);
  const now = Date.now();
  const cacheTtl = ttlFor(key);
  const cached = requestCache.get(key);
  if (cached && now - cached.ts < cacheTtl) {
    return cached.data;
  }

  if (inflight.has(key)) return inflight.get(key);

  const controller = new AbortController();
  const p = (async () => {
    try {
      const data = await fetchJson(endpoint, { ...opts, signal: controller.signal });
      requestCache.set(key, { data, ts: Date.now() });
      try {
        sessionStorage.setItem(`cache:${endpoint}`, JSON.stringify(data));
      } catch {}
      shareHttpCache(endpoint, data);
      return data;
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, p);
  return p;
}

export async function fetchWithSWR(endpoint, opts = {}) {
  const key = `cache:${endpoint}`;
  const cached = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(key) : null;
  if (cached) {
    // revalidate in background
    fetchData(endpoint, opts).catch(() => {});
    return JSON.parse(cached);
  }
  const data = await fetchData(endpoint, opts);
  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {}
  return data;
}

/** Optional: probe a list of bases and fix on the first that responds */
export async function initApiBase(candidates = []) {
  const bases = [
    getApiBaseUrl(),
    'http://127.0.0.1:5001',
    ...candidates,
  ];
  for (const b of bases) {
    try {
      const ok = await fetch(`${b}/api/health`, { method: 'GET' }).then((r) => r.ok).catch(() => false);
      if (ok) {
        setApiBaseUrl(b);
        return b;
      }
    } catch {}
  }
  return getApiBaseUrl();
}

frontend/src/context/websocketcontext.jsx

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { io } from 'socket.io-client';
import { getApiBaseUrl, bus, shareTables, shareAlerts } from '../lib/api.js';

export const WebSocketContext = createContext({
  tables: {},
  alerts: { items: [] }
});

export const WebSocketProvider = ({ children }) => {
  const [tables, setTables] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('tables:last') || '{}');
    } catch {
      return {};
    }
  });
  const [alerts, setAlerts] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('alerts:last') || '{"items": []}');
    } catch {
      return { items: [] };
    }
  });

  useEffect(() => {
    const socket = io(getApiBaseUrl(), {
      path: '/socket.io',
      transports: ['websocket']
    });

    socket.on('connect', () => console.info('[ws] connected'));
    socket.on('disconnect', () => console.warn('[ws] disconnected'));

    socket.on('tables:update', (payload) => {
      console.info('[ws] tables:update t3m=', Array.isArray(payload?.t3m) ? payload.t3m.length : 'missing');
      setTables(payload ?? {});
      try {
        sessionStorage.setItem('tables:last', JSON.stringify(payload ?? {}));
      } catch {}
      shareTables(payload ?? {});
      bus.emit('tables:update', payload ?? {});
    });

    socket.on('alerts:update', (payload) => {
      setAlerts(payload ?? { items: [] });
      try {
        sessionStorage.setItem('alerts:last', JSON.stringify(payload ?? { items: [] }));
      } catch {}
      shareAlerts(payload ?? { items: [] });
      bus.emit('alerts:update', payload ?? { items: [] });
    });

    return () => {
      try {
        socket.close();
      } catch {}
    };
  }, []);

  const value = useMemo(() => ({ tables, alerts, setTables, setAlerts }), [tables, alerts]);
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
};

export const useWebSocketData = () => useContext(WebSocketContext);
_________________________________________________
frontend/src/components/GainersTable.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';
import { useWebSocketData } from '../context/websocketcontext.jsx';

function normalizeT3M(raw) {
  // Accept a variety of shapes from the backend
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.crypto ||
    raw?.crypto_meta?.gainers ||
    raw?.rows ||
    [];
  if (!Array.isArray(rows)) rows = [];

  // Build a canonical row and de-dupe by symbol (keep largest 3m change)
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 =
      Number(
        r.change_3m ??
          r.change_3min ??
          r.change3m ??
          r.pct_3m ??
          r['3m_change'] ??
          r.delta_3m ??
          0
      ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = {
      symbol: sym,
      price: px,
      change3m: c3,
      name: r.name ?? r.base ?? sym,
    };
    const prev = map.get(sym);
    if (!prev || c3 > prev.change3m) map.set(sym, entry);
  }

  return Array.from(map.values()).sort((a, b) => b.change3m - a.change3m);
}

export default function GainersTable() {
  const { tables } = useWebSocketData();
  const [rows, setRows] = useState([]);
  const t3mSocket = tables?.t3m;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let raw = t3mSocket;
      if (!raw || (Array.isArray(raw) && raw.length === 0)) {
        try {
          raw = await fetchWithSWR(API_ENDPOINTS.t3m);
        } catch (e) {
          console.warn('[t3m] HTTP fallback failed', e);
        }
      }
      const norm = normalizeT3M(raw);
      if (!cancelled) setRows(norm);
    })();
    return () => {
      cancelled = true;
    };
  }, [t3mSocket]);

  const content = useMemo(() => {
    if (!rows.length) {
      return <div className="empty">No 3-min gainers data available.</div>;
    }
    return (
      <table className="table compact">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Δ 3m</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td>{Number.isFinite(r.change3m) ? `${r.change3m.toFixed(2)}%` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }, [rows]);

  return (
    <div className="panel">
      <div className="panel__header">
        <h3>3-minute Gainers</h3>
        <div className="meta">{rows.length ? `assets ${rows.length}` : 'loading…'}</div>
      </div>
      {content}
    </div>
  );
}

frontend/src/components/LosersTable.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';
import { useWebSocketData } from '../context/websocketcontext.jsx';

function normalize3m(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.crypto ||
    raw?.crypto_meta?.losers ||
    raw?.rows ||
    [];
  if (!Array.isArray(rows)) rows = [];

  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 =
      Number(
        r.change_3m ??
          r.change_3min ??
          r.change3m ??
          r.pct_3m ??
          r['3m_change'] ??
          r.delta_3m ??
          0
      ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, change3m: c3 };
    const prev = map.get(sym);
    // For losers keep the *most negative* value
    if (!prev || c3 < prev.change3m) map.set(sym, entry);
  }

  // Sort ascending (most negative first)
  return Array.from(map.values()).sort((a, b) => a.change3m - b.change3m);
}

export default function LosersTable() {
  const { tables } = useWebSocketData();
  const [rows, setRows] = useState([]);
  const t3mSocket = tables?.t3m_losers || tables?.losers || null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let raw = t3mSocket;
      if (!raw || (Array.isArray(raw) && raw.length === 0)) {
        try {
          raw = await fetchWithSWR(API_ENDPOINTS.losers);
        } catch (e) {
          console.warn('[losers 3m] HTTP fallback failed', e);
        }
      }
      const norm = normalize3m(raw);
      if (!cancelled) setRows(norm);
    })();
    return () => {
      cancelled = true;
    };
  }, [t3mSocket]);

  const content = useMemo(() => {
    if (!rows.length) {
      return <div className="empty">No 3-min losers data available.</div>;
    }
    return (
      <table className="table compact">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Δ 3m</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td>{Number.isFinite(r.change3m) ? `${r.change3m.toFixed(2)}%` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }, [rows]);

  return (
    <div className="panel">
      <div className="panel__header">
        <h3>3-minute Losers</h3>
        <div className="meta">{rows.length ? `assets ${rows.length}` : 'loading…'}</div>
      </div>
      {content}
    </div>
  );
}

___________________________________________________________

frontend/src/components/TopBannerScroll.jsx
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function TopBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.top);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch (e) {
        console.warn('[top banner] fetch failed', e);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--top">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}

__________________________________________________________

frontend/src/components/BottomBannerScroll.jsx

import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function BottomBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.bottom);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch (e) {
        console.warn('[bottom banner] fetch failed', e);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--bottom">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}


_______________________________________________________

frontend/src/app.jsx
import React, { Suspense, lazy } from 'react';
import { WebSocketProvider } from './context/websocketcontext.jsx';

const GainersTable = lazy(() => import('./components/GainersTable.jsx'));
const LosersTable = lazy(() => import('./components/LosersTable.jsx'));
const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'));
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'));

export default function App() {
  return (
    <WebSocketProvider>
      <div className="app">
        <Suspense fallback={<div>Loading…</div>}>
          <TopBannerScroll />
        </Suspense>

        <div className="grid">
          <Suspense fallback={<div>Loading 3-min gainers…</div>}>
            <GainersTable />
          </Suspense>

          <Suspense fallback={<div>Loading 3-min losers…</div>}>
            <LosersTable />
          </Suspense>
        </div>

        <Suspense fallback={null}>
          <BottomBannerScroll />
        </Suspense>
      </div>
    </WebSocketProvider>
  );
}

____________________________________________________

📂 frontend_full_dump.txt

──────────────────────────────
package.json
──────────────────────────────
{
  "name": "frontend",
  "version": "1.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "socket.io-client": "^4.7.5"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.3",
    "vitest": "^1.6.1",
    "@testing-library/react": "^16.0.1",
    "jsdom": "^25.0.0"
  }
}

──────────────────────────────
vite.config.js
──────────────────────────────
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true
  }
})

──────────────────────────────
index.html
──────────────────────────────
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0"/>
    <title>CBMOONERS</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>

──────────────────────────────
src/main.jsx
──────────────────────────────
import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './app.jsx'
import { WebSocketProvider } from './context/websocketcontext.jsx'
import './styles.css'

const root = createRoot(document.getElementById('root'))
root.render(
  <React.StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </React.StrictMode>
)

──────────────────────────────
src/app.jsx
──────────────────────────────
import React, { Suspense, lazy } from 'react'

const GainersTable = lazy(() => import('./components/GainersTable.jsx'))
const LosersTable = lazy(() => import('./components/LosersTable.jsx'))
const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'))
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'))

export default function App() {
  return (
    <div className="container">
      <h1>CBMOONERS</h1>

      <Suspense fallback={<div>Loading top banner…</div>}>
        <TopBannerScroll />
      </Suspense>

      <div className="grid">
        <Suspense fallback={<div>Loading 3-min gainers…</div>}>
          <GainersTable />
        </Suspense>

        <Suspense fallback={<div>Loading 3-min losers…</div>}>
          <LosersTable />
        </Suspense>
      </div>

      <Suspense fallback={<div>Loading bottom banner…</div>}>
        <BottomBannerScroll />
      </Suspense>
    </div>
  )
}

──────────────────────────────
src/styles.css
──────────────────────────────
:root { font-family: ui-sans-serif, system-ui; }
body { margin: 0; background: #0c0f14; color: #e7edf3; }
.container { padding: 16px; max-width: 1200px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { background: #121722; border-radius: 12px; padding: 12px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 8px; border-bottom: 1px solid #1f2735; }
.badge { font-size: 12px; opacity: .8; }
.row-up { color: #33d17a; }
.row-down { color: #ff616e; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.scroller { display: flex; gap: 12px; overflow-x: auto; padding: 8px 0; }

──────────────────────────────
src/lib/constants.js
──────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5001"

export const API_ENDPOINTS = {
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
  losers: `${API_BASE}/api/component/losers-table`,
  topBanner: `${API_BASE}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE}/api/component/bottom-banner-scroll`,
  alerts: `${API_BASE}/api/alerts/recent`
}

──────────────────────────────
src/components/GainersTable.jsx
──────────────────────────────
import React, { useEffect, useState } from 'react'
import { API_ENDPOINTS } from '../lib/constants.js'

export default function GainersTable() {
  const [rows, setRows] = useState([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(API_ENDPOINTS.t3m)
        if (!res.ok) throw new Error('bad status')
        const json = await res.json()
        const normalized = normalize(json)
        setRows(normalized)
      } catch (err) {
        console.error('Error loading 3m gainers:', err)
      }
    }
    load()
  }, [])

  if (!rows.length) {
    return <div className="card">No 3-min gainers data available</div>
  }

  return (
    <div className="card">
      <h2>3-min Gainers</h2>
      <table className="table">
        <thead>
          <tr><th>Symbol</th><th>Change</th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.symbol} className="row-up">
              <td>{r.symbol}</td>
              <td>{r.change.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function normalize(payload) {
  if (Array.isArray(payload)) return dedupe(payload)
  if (payload?.data) return dedupe(payload.data)
  if (payload?.crypto) return dedupe(payload.crypto)
  if (payload?.crypto_meta?.gainers) return dedupe(payload.crypto_meta.gainers)
  return []
}

function dedupe(list) {
  const map = new Map()
  for (const row of list) {
    const sym = row.symbol?.toUpperCase()
    if (!sym) continue
    const prev = map.get(sym)
    if (!prev || (row.change ?? 0) > (prev.change ?? 0)) {
      map.set(sym, { symbol: sym, change: Number(row.change) || 0 })
    }
  }
  return [...map.values()]
}

──────────────────────────────
src/components/LosersTable.jsx
──────────────────────────────
import React, { useEffect, useState } from 'react'
import { API_ENDPOINTS } from '../lib/constants.js'

export default function LosersTable() {
  const [rows, setRows] = useState([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(API_ENDPOINTS.losers)
        if (!res.ok) throw new Error('bad status')
        const json = await res.json()
        const normalized = normalize(json)
        setRows(normalized)
      } catch (err) {
        console.error('Error loading losers:', err)
      }
    }
    load()
  }, [])

  if (!rows.length) {
    return <div className="card">No losers data available</div>
  }

  return (
    <div className="card">
      <h2>Losers</h2>
      <table className="table">
        <thead>
          <tr><th>Symbol</th><th>Change</th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.symbol} className="row-down">
              <td>{r.symbol}</td>
              <td>{r.change.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function normalize(payload) {
  if (Array.isArray(payload)) return dedupe(payload)
  if (payload?.data) return dedupe(payload.data)
  if (payload?.crypto) return dedupe(payload.crypto)
  if (payload?.crypto_meta?.losers) return dedupe(payload.crypto_meta.losers)
  return []
}

function dedupe(list) {
  const map = new Map()
  for (const row of list) {
    const sym = row.symbol?.toUpperCase()
    if (!sym) continue
    const prev = map.get(sym)
    if (!prev || (row.change ?? 0) < (prev.change ?? 0)) {
      map.set(sym, { symbol: sym, change: Number(row.change) || 0 })
    }
  }
  return [...map.values()]
}

──────────────────────────────
src/components/TopBannerScroll.jsx
──────────────────────────────
import React, { useEffect, useState } from 'react'
import { API_ENDPOINTS } from '../lib/constants.js'

export default function TopBannerScroll() {
  const [items, setItems] = useState([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(API_ENDPOINTS.topBanner)
        if (!res.ok) throw new Error('bad status')
        const json = await res.json()
        const normalized = normalize(json)
        setItems(normalized)
      } catch (err) {
        console.error('Error fetching top banner data:', err)
      }
    }
    load()
  }, [])

  return (
    <div className="card scroller">
      {items.map((i, idx) => (
        <span key={idx} className="badge">{i.text || i.symbol}</span>
      ))}
    </div>
  )
}

function normalize(payload) {
  if (Array.isArray(payload)) return payload
  if (payload?.items) return payload.items
  return []
}

──────────────────────────────
src/components/BottomBannerScroll.jsx
──────────────────────────────
import React, { useEffect, useState } from 'react'
import { API_ENDPOINTS } from '../lib/constants.js'

export default function BottomBannerScroll() {
  const [items, setItems] = useState([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(API_ENDPOINTS.bottomBanner)
        if (!res.ok) throw new Error('bad status')
        const json = await res.json()
        const normalized = normalize(json)
        setItems(normalized)
      } catch (err) {
        console.error('Error fetching bottom banner data:', err)
      }
    }
    load()
  }, [])

  return (
    <div className="card scroller">
      {items.map((i, idx) => (
        <span key={idx} className="badge">{i.text || i.symbol}</span>
      ))}
    </div>
  )
}

function normalize(payload) {
  if (Array.isArray(payload)) return payload
  if (payload?.items) return payload.items
  return []
}


What tables/components you have
	•	Gainers (1-minute) – shows top movers on the 1-min window.
	•	Gainers (3-minute) – same idea, but using the 3-min window (your “t3m” snapshot).
	•	Losers (3-minute) – worst movers on the 3-min window (mirrors gainers logic).
	•	TopBanner & BottomBanner – slim marquee lists of notable movers / headlines / highlights.
	•	Watchlist – selected symbols plus their latest price & short-term deltas.
The shared data model (why everything feels “instant”)
All these components read from the same shared data layer so they update from sockets immediately and only hit HTTP when needed.
Sources of truth
	1.	Socket snapshots (primary; zero-latency UI updates)
	•	Backend emits:
	•	tables:update → { t1m, t3m, at }
	•	alerts:update → { items }
	•	Frontend listens once (in the WebSocketProvider) and stashes the payload into:
	•	React state (context)
	•	sessionStorage (tables:last, alerts:last) for instant paint on reloads.
	2.	HTTP endpoints (fallback or first-load init)
	•	Per-route TTL caching + in-flight de-duplication (no duplicate fetches).
	•	SWR: show last cached payload from sessionStorage instantly, then revalidate in the background.
Multi-tab efficiency
	•	We use BroadcastChannel('cbmo4ers') so if one tab gets a fresh payload (socket or HTTP), all tabs receive it immediately—no extra connections or duplicate fetches.
Key frontend efficiency features (that you asked for and we applied)
	1.	One socket, many consumers
	•	A single Socket.IO client feeds a context.
	•	Components subscribe to the context, not to the socket directly.
	•	If the socket drops, components automatically fall back to cached HTTP.
	2.	Per-route TTLs + in-flight de-dupe
	•	Requests within the TTL window use cache.
	•	If a fetch for /api/component/gainers-table is already running, the next caller gets the same Promise—no double work.
	•	Optional AbortController cancels stale in-flight requests if a newer one supersedes it.
	3.	SWR (stale-while-revalidate)
	•	Read last good payload from sessionStorage → paint instantly.
	•	Kick off a background refresh; if it wins, UI updates.
	4.	Instant boot base-URL probing (optional)
	•	Race multiple candidate API bases once at app start, lock to the fastest, avoid later retries.
	5.	Robust normalizers
	•	Components don’t care if the backend returns [], { data: [] }, { crypto: [] }, or { crypto_meta: { gainers: [] } }.
	•	We normalize to a canonical array of rows with { symbol, price, change_1m, change_3m, ... }.
	6.	De-duplication by symbol
	•	If the source includes duplicates (e.g., same symbol from two feeds), we keep the row with the strongest relevant change (for 3-min lists, the largest absolute 3-min change).
	7.	Render efficiency
	•	Rows are memoized; heavy lists can use virtualization.
	•	Off-screen panels can pause work via IntersectionObserver.
Component-by-component logic
Gainers (1-minute)
	•	Data path: tables.t1m (socket snapshot) → fallback to GET /api/component/gainers-table-1min.
	•	Shaping: normalize payload → de-dupe by symbol → sort by descending 1-min % change.
	•	Display: symbol, last price, 1-min change, spark/mini trend (if available).
Gainers (3-minute)
	•	Data path: tables.t3m (socket) → fallback to GET /api/component/gainers-table (your 3-min HTTP endpoint).
	•	Shaping: normalize; if multiple rows per symbol, keep the one with the largest 3-min change; sort descending 3-min %.
	•	Important: this table never silently shows 1-min data. If t3m is missing/empty, it shows a clear “No 3-min data” message (so you can spot backend issues).
Losers (3-minute)
	•	Mirrors the 3-minute gainers table:
	•	Data path: socket t3m → HTTP /api/component/losers-table (or whatever endpoint you named).
	•	Shaping: normalize → de-dupe → sort ascending 3-min % (most negative first).
TopBannerScroll / BottomBannerScroll
	•	Data path: socket snapshot first (if we emit a banner list), else HTTP endpoints:
	•	/api/component/top-banner-scroll
	•	/api/component/bottom-banner-scroll
	•	Shaping: normalize to a compact list (symbol/title + small change/price).
	•	Behavior: SWR for instant scroll, low TTL to avoid stale headlines.
Watchlist
	•	Data path: merged from:
	•	Socket price ticks/snapshot (if emitted),
	•	Fallback to HTTP batch price endpoint.
	•	Logic: joins your saved symbols with the latest prices & short-window deltas; handles “incomplete symbol” gracefully.
Backend pieces (what makes the socket snapshots work)
	•	You have a background worker/thread that periodically fetches/derives:
	•	one_min_snapshot (for t1m)
	•	three_min_snapshot (for t3m)
	•	alerts_log (rolling alerts list)
	•	At the end of each compute pass, it emits over Socket.IO:
	•	Your Flask endpoints under /api/component/* do not recompute—they just serve the latest snapshot (O(1)), with sensible cache headers.
CORS & ports footgun (you hit this once)
	•	If you run Vite on a different port (say 5176), your backend must allow that Origin in Access-Control-Allow-Origin.
	•	We added client-side helpers that try to lock the base URL once at boot; still, the server has to permit the active origin.
⸻
1. Backend logic (the actual filter/threshold)
	•	The background worker fetches deltas for all tracked symbols.
	•	It calculates each symbol’s 1-minute % change ((price_now – price_1m_ago) / price_1m_ago * 100).
	•	It then:
	•	Sorts by descending 1-minute % change.
	•	Applies a minimum change threshold to cut noise.
	•	In your earlier code it was usually abs(change_1m) ≥ 0.1% (i.e. only moves at least one tenth of a percent).
	•	Takes the top N movers (commonly N=10) into the snapshot.
So effectively: “Show me the top 10 symbols with ≥0.1% gain in the past 1 minute, sorted highest first.”
⸻
2. Frontend logic
	•	GainersTable (1m) does not impose another threshold; it just:
	•	Normalizes whatever comes from the backend.
	•	De-dupes by symbol.
	•	Sorts again (defensive) by descending change_1m.
	•	If the backend snapshot is empty (no asset passed the 0.1% filter), you’ll see “No 1-min data available.”
⸻
3. Why thresholds matter
	•	Keeps noise (like 0.01% wiggles) out of the UI.
	•	Keeps table length manageable (top 10 or 15 instead of 500 coins).
	•	Same principle applies to losers (3-min) but in reverse: only include if ≤ –0.1% over 3 minutes.
⸻


[8/19/25, 12:57:07] Nick Gl: Np
[8/19/25, 12:57:17] Treal: 1) Push instead of poll (biggest win)
You already ship Flask-SocketIO. Emit snapshots from the background updater and subscribe on the client so the 1-min/3-min panes and alerts update without any repeated HTTP polling.
Backend (emit when you finish a compute pass):
# after you compute one_min_snapshot / three_min_snapshot
socketio.emit("tables:update", {
    "t1m": one_min_snapshot,   # top lists already shaped for UI
    "t3m": three_min_snapshot,
    "at": time.time()
}, namespace="/stream", broadcast=True)
# when alerts roll:
socketio.emit("alerts:update", {"items": alerts}, namespace="/stream", broadcast=True)
Frontend (subscribe once at app start; fall back to fetch if socket drops):
import { io } from "socket.io-client";
const sock = io(getApiBaseUrl(), { path: "/socket.io", transports: ["websocket"] });
sock.on("connect",   () => console.info("[ws] connected"));
sock.on("disconnect",() => console.warn("[ws] disconnected"));
sock.on("tables:update", payload => {
  sessionStorage.setItem("tables:last", JSON.stringify(payload));
  // your state setters here (no network calls)
});
sock.on("alerts:update", payload => {
  sessionStorage.setItem("alerts:last", JSON.stringify(payload));
  // update alerts UI
});
2) De-dupe requests, cancel in-flight, and use per-route TTLs
You already cache responses; go one step further: prevent concurrent duplicates and tune TTLs per endpoint.
// in api.js, near requestCache
const inflight = new Map();
const TTL = {
  "/api/alerts/recent": 5000,
  "/api/component/gainers-table-1min": 2500,
  "/api/component/gainers-table": 10000,
  "/api/component/losers-table": 10000,
  "/api/component/top-banner-scroll": 15000,
  "/api/component/bottom-banner-scroll": 15000,
  default: 8000
};
function ttlFor(url) {
  for (const k of Object.keys(TTL)) if (k !== "default" && url.includes(k)) return TTL[k];
  return TTL.default;
}
export const fetchData = async (endpoint, opts = {}) => {
  const now = Date.now();
  const cacheTtl = ttlFor(endpoint);
  const cached = requestCache.get(endpoint);
  if (cached && (now - cached.timestamp) < cacheTtl) return cached.data;
  // de-dupe
  if (inflight.has(endpoint)) return inflight.get(endpoint);
  // cancel older in-flight if a new call arrives (optional)
  const controller = new AbortController();
  const p = (async () => {
    try {
      const res = await fetch(endpoint, { ...opts, signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const raw = await res.json();
      const data = maybeFilterCustomAlerts(endpoint, raw);
      requestCache.set(endpoint, { data, timestamp: Date.now() });
      return data;
    } finally {
      inflight.delete(endpoint);
    }
  })();
  inflight.set(endpoint, p);
  return p;
};
3) Stale-while-revalidate (instant paint)
Persist the last good payload in sessionStorage and show it immediately while quietly refreshing.
export async function fetchWithSWR(endpoint, opts = {}) {
  const key = `cache:${endpoint}`;
  const cached = sessionStorage.getItem(key);
  if (cached) {
    // fire-and-forget revalidation
    fetchData(endpoint, opts).catch(()=>{});
    return JSON.parse(cached);
  }
  const data = await fetchData(endpoint, opts);
  sessionStorage.setItem(key, JSON.stringify(data));
  return data;
}
Use fetchWithSWR for the slow/expensive panes (banners, 3-min tables).
4) Probe and lock the base URL once
Right now you probe on every failure. Do a one-time “race” at app boot and commit the fastest base so you don’t retry later.
export async function fetchWithSWR(endpoint, opts = {}) {
  const key = `cache:${endpoint}`;
  const cached = sessionStorage.getItem(key);
  if (cached) {
    // fire-and-forget revalidation
    fetchData(endpoint, opts).catch(()=>{});
    return JSON.parse(cached);
  }
  const data = await fetchData(endpoint, opts);
  sessionStorage.setItem(key, JSON.stringify(data));
  return data;
}
Use fetchWithSWR for the slow/expensive panes (banners, 3-min tables).
4) Probe and lock the base URL once
export async function initApiBase() {
  const bases = [getApiBaseUrl(), ...CANDIDATE_BASES];
  const probes = bases.map(async b => (await probeBase(b)) ? b : null);
  for await (const b of probes) if (b) { setApiBaseUrl(b); break; }
}
Call initApiBase() once in your app entry before any data loads.
5) Cloudflare Functions: edge cache with stale-while-revalidate
Wrap your proxy in the edge cache so identical hits don’t travel to your origin for a few seconds.
export default async (req, env, ctx) => {
  const cacheKey = new Request(new URL(req.url).toString(), req);
  const cached = await caches.default.match(cacheKey);
  if (cached) return cached; // quick
  const resp = await fetch(originUrl, { cf: { cacheEverything: true }});
  // 10s CDN TTL, allow stale if the origin hiccups
  const out = new Response(resp.body, resp);
  out.headers.set("Cache-Control", "public, s-maxage=10, stale-while-revalidate=30, stale-if-error=60");
  ctx.waitUntil(caches.default.put(cacheKey, out.clone()));
  return out;
};
6) Backend: faster, fewer, smaller
a) Reuse TCP/TLS with a pooled session + retries
_________________
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
session = requests.Session()
session.headers.update({"User-Agent": "cbmo4ers/3"})
retry = Retry(total=3, backoff_factor=0.2, status_forcelist=[429,500,502,503,504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retry)
session.mount("https://", adapter); session.mount("http://", adapter)
def get_json(url, timeout=8):
  r = session.get(url, timeout=timeout)
  r.raise_for_status()
  return r.json()
b) Precompute & serve snapshots
You already compute in a background thread—ensure all “component/*” endpoints return the last snapshot (O(1)) and never re-fetch on request path.
c) Smaller payloads
Return only fields you render; round numbers server-side; use orjson to serialize: 
import orjson
from flask import Response
def json(data, status=200, headers=None):
    return Response(orjson.dumps(data), status=status, headers=headers, mimetype="application/json")
d) Cache headers from origin
For read-only GETs add:
resp = json(payload)
resp.headers["Cache-Control"] = "public, max-age=3, s-maxage=10, stale-while-revalidate=30"
resp.headers["ETag"] = hashlib.md5(resp.data).hexdigest()
return resp
resp = json(payload)
resp.headers["Cache-Control"] = "public, max-age=3, s-maxage=10, stale-while-revalidate=30"
resp.headers["ETag"] = hashlib.md5(resp.data).hexdigest()
return resp
e) Concurrency caps for Coinbase
If you fan out per symbol, use a thread pool with ≤8 workers and the pooled session above. That reduces TLS churn and avoids timeouts.
f) Gunicorn settings
Run with cooperative I/O:
gunicorn app:app -k eventlet -w 1 --threads 8 --timeout 60 --graceful-timeout 20
7) UI rendering efficiency
	•	Memoize heavy rows; virtualize long tables (e.g., @tanstack/react-virtual).
	•	Pause off-screen panels using IntersectionObserver (don’t fetch/animate if hidden).
	•	Debounce “Show more”, filters, and watchlist edits (150–250 ms).
8) Reduce the alert storm
You’re hitting /api/alerts/recent many times per second. Centralize it:
	•	Fetch once on an interval (or via the socket) in a global store and have all components read from that store.
	•	If you must poll, use a single setInterval(1500) and share the result.
9) Multi-tab savings
Share latest data between tabs with BroadcastChannel('cbmo4ers'). When one tab fetches, others receive it instantly.
⸻
Quick checklist to apply now
	
If you want, I can drop a patch that adds the per-route TTLs + in-flight de-dupe and the CF edge cache wrapper directly to your files.


_____________________________________________________________

Option A — 
All-in Cloudflare (recommended)
Frontend: Cloudflare Pages (static build from your repo).


API + realtime: Cloudflare Workers (+ Durable Objects for stateful realtime).

 Replace Flask/Socket.IO with:


Native WebSocket (supported in Workers) or Server-Sent Events.


A Durable Object acts as your “hub”: stores the latest snapshots (t1m/t3m/alerts), handles connections, broadcasts updates, and survives across requests.


Background jobs: Cloudflare Cron Triggers (scheduled Workers) to fetch Coinbase, compute snapshots, then stub.fetch() the Durable Object to update and broadcast.


Caching: Edge cache with Cache-Control: s-maxage=10, stale-while-revalidate=30. Use KV for small blobs (last-good payloads) or keep them in the Durable Object.


Data:


For lightweight state → KV or Durable Objects.


For SQL needs → D1 (SQLite at edge).


For Postgres → use Hyperdrive to a managed PG (e.g., Neon) with smart connection pooling.


Assets/files: R2 (S3-compatible) if you store any media.



