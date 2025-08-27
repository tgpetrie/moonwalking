import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { loadWatchlist, toggleWatchlist } from '../lib/watchlist.js';

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
const ENDPOINTS = {
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
};

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n); const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${v.toFixed(digits)}`;
}
function fmtPct(n) {
  if (!Number.isFinite(n)) return '-';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function normalize(raw, key) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const pct = Number(r[key] ?? r[`change_${key}`] ?? r[`pct_${key}`] ?? r[`delta_${key}`] ?? r.change ?? 0) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, pct };
    const prev = map.get(sym);
    if (!prev || pct > prev.pct) map.set(sym, entry);
  }
  return Array.from(map.values()).sort((a, b) => b.pct - a.pct);
}

export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
  const socketNs = `${API_BASE}/stream`;
  const socketKey = windowMinutes === 1 ? 't1m' : 't3m';
  const endpoint = windowMinutes === 1 ? ENDPOINTS.t1m : ENDPOINTS.t3m;
  const changeKey = windowMinutes === 1 ? 'change_1m' : 'change_3m';

  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

  useEffect(() => {
    let cancelled = false;
    let sock;
    try {
      sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
      sock.on('tables:update', (payload) => {
        const raw = payload?.[socketKey];
        if (!cancelled && raw) setRows(normalize(raw, changeKey));
      });
    } catch {}

    (async () => {
      try {
        const res = await fetch(endpoint);
        if (res.ok) {
          const json = await res.json();
          if (!cancelled) setRows(normalize(json, changeKey));
        }
      } catch {}
    })();

    return () => { cancelled = true; try { sock && sock.close(); } catch {} };
  }, [socketNs, socketKey, endpoint, changeKey]);

  useEffect(() => {
    const onStorage = (e) => { if (e?.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist())); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  if (!rows.length) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>{title}</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  if (view === 'tiles') {
    const top8 = rows.slice(0, 8);
    return (
      <div className="panel">
        <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
        <div className="gainers-tiles">
          {top8.map(r => (
            <div key={r.symbol} className="tile">
              <div className="mono" style={{fontWeight:600}}>{r.symbol}</div>
              <div className="num">{fmtPrice(r.price)}</div>
              <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
              <button
                className="badge"
                aria-pressed={watchlist.has(r.symbol)}
                title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                onClick={() => {
                  // pass current price so we can store addedPrice
                  toggleWatchlist(r.symbol, r.price);
                  setWatchlist(new Set(loadWatchlist()));
                }}
              >
                {watchlist.has(r.symbol) ? '★' : '☆'}
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.symbol}>
              <td className="mono">{r.symbol}</td>
              <td className="num">{fmtPrice(r.price)}</td>
              <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
              <td style={{textAlign:'right'}}>
                <button
                  className="badge"
                  aria-pressed={watchlist.has(r.symbol)}
                  title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                  onClick={() => { toggleWatchlist(r.symbol, r.price); setWatchlist(new Set(loadWatchlist())); }}
                >
                  {watchlist.has(r.symbol) ? '★' : '☆'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

    if (!Number.isFinite(n)) return '-';
    const v = Number(n); const abs = Math.abs(v);
    const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
    return `$${v.toFixed(digits)}`;
  }
  function fmtPct(n) {
    if (!Number.isFinite(n)) return '-';
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(2)}%`;
  }

  function normalize(raw, key) {
    let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
    if (!Array.isArray(rows)) rows = [];
    const map = new Map();
    for (const r of rows) {
      const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
      if (!sym) continue;
      const pct = Number(r[key] ?? r[`change_${key}`] ?? r[`pct_${key}`] ?? r[`delta_${key}`] ?? r.change ?? 0) || 0;
      const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
      const entry = { symbol: sym, price: px, pct };
      const prev = map.get(sym);
      if (!prev || pct > prev.pct) map.set(sym, entry);
    }
    return Array.from(map.values()).sort((a, b) => b.pct - a.pct);
  }

  export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
    const socketNs = `${API_BASE}/stream`;
    const socketKey = windowMinutes === 1 ? 't1m' : 't3m';
    const endpoint = windowMinutes === 1 ? ENDPOINTS.t1m : ENDPOINTS.t3m;
    const changeKey = windowMinutes === 1 ? 'change_1m' : 'change_3m';

    const [rows, setRows] = useState([]);
    const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

    useEffect(() => {
      let cancelled = false;
      let sock;
      try {
        sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
        sock.on('tables:update', (payload) => {
          const raw = payload?.[socketKey];
          if (!cancelled && raw) setRows(normalize(raw, changeKey));
        });
      } catch {}

      (async () => {
        try {
          const res = await fetch(endpoint);
          if (res.ok) {
            const json = await res.json();
            if (!cancelled) setRows(normalize(json, changeKey));
          }
        } catch {}
      })();

      return () => { cancelled = true; try { sock && sock.close(); } catch {} };
    }, [socketNs, socketKey, endpoint, changeKey]);

    useEffect(() => {
      const onStorage = (e) => { if (e.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist())); };
      window.addEventListener('storage', onStorage);
      return () => window.removeEventListener('storage', onStorage);
    }, []);

    const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

    if (!rows.length) {
      return (
        <div className="panel">
          <div className="panel__header"><h3>{title}</h3><div className="meta">loading…</div></div>
          <div className="empty">No data available.</div>
        </div>
      );
    }

    if (view === 'tiles') {
      const top8 = rows.slice(0, 8);
      return (
        <div className="panel">
          <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
          <div className="gainers-tiles">
            {top8.map(r => (
              <div key={r.symbol} className="tile">
                <div className="mono" style={{fontWeight:600}}>{r.symbol}</div>
                <div className="num">{fmtPrice(r.price)}</div>
                <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
                <button
                  className="badge"
                  aria-pressed={watchlist.has(r.symbol)}
                  title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                  onClick={() => {
                    // pass current price so we can store addedPrice
                    toggleWatchlist(r.symbol, r.price);
                    setWatchlist(new Set(loadWatchlist()));
                  }}
                >
                  {watchlist.has(r.symbol) ? '★' : '☆'}
                </button>
              </div>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className="panel">
        <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
        <table className="table compact">
          <thead>
            <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.symbol}>
                <td className="mono">{r.symbol}</td>
                <td className="num">{fmtPrice(r.price)}</td>
                <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
                <td style={{textAlign:'right'}}>
                  <button
                    className="badge"
                    aria-pressed={watchlist.has(r.symbol)}
                    title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                    onClick={() => { toggleWatchlist(r.symbol, r.price); setWatchlist(new Set(loadWatchlist())); }}
                  >
                    {watchlist.has(r.symbol) ? '★' : '☆'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return String(sym || '').trim().toUpperCase();
}

export function loadWatchlist() {
  try {
    // If Codex exposes a getter, use it
    if (typeof window !== 'undefined') {
      const cx = window.codex || window.CODEX || null;
      const api = cx && (cx.watchlist || cx.watch || cx.favorites);
      if (api && typeof api.get === 'function') {
        const list = api.get();
        if (Array.isArray(list)) return list.map(_norm);
      } else if (cx && typeof cx.getWatchlist === 'function') {
        const list = cx.getWatchlist();
        if (Array.isArray(list)) return list.map(_norm);
      }
    }
  } catch {}
  // Fallback: localStorage
  try {
    const raw = localStorage.getItem('watchlist:symbols');
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.map(_norm) : [];
  } catch { return []; }
}

export function saveWatchlist(list) {
  const uniq = Array.from(new Set((list || []).map(_norm)));
  try {
    if (typeof window !== 'undefined') {
      const cx = window.codex || window.CODEX || null;
      const api = cx && (cx.watchlist || cx.watch || cx.favorites);
      if (api && typeof api.set === 'function') {
        api.set(uniq);
      } else if (cx && typeof cx.setWatchlist === 'function') {
        cx.setWatchlist(uniq);
      }
    }
  } catch {}
  try {
    localStorage.setItem('watchlist:symbols', JSON.stringify(uniq));
  } catch {}
  try {
    import React, { useEffect, useState } from 'react';
    import { io } from 'socket.io-client';
    import { loadWatchlist, toggleWatchlist } from '../lib/watchlist.js';

    const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
    const ENDPOINTS = {
      t1m: `${API_BASE}/api/component/gainers-table-1min`,
      t3m: `${API_BASE}/api/component/gainers-table`,
    };

    function fmtPrice(n) {
      if (!Number.isFinite(n)) return '-';
      const v = Number(n); const abs = Math.abs(v);
      const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
      return `$${v.toFixed(digits)}`;
    }
    function fmtPct(n) {
      if (!Number.isFinite(n)) return '-';
      const sign = n > 0 ? '+' : '';
      return `${sign}${n.toFixed(2)}%`;
    }

    function normalize(raw, key) {
      let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
      if (!Array.isArray(rows)) rows = [];
      const map = new Map();
      for (const r of rows) {
        const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
        if (!sym) continue;
        const pct = Number(r[key] ?? r[`change_${key}`] ?? r[`pct_${key}`] ?? r[`delta_${key}`] ?? r.change ?? 0) || 0;
        const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
        const entry = { symbol: sym, price: px, pct };
        const prev = map.get(sym);
        if (!prev || pct > prev.pct) map.set(sym, entry);
      }
      return Array.from(map.values()).sort((a, b) => b.pct - a.pct);
    }

    export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
      const socketNs = `${API_BASE}/stream`;
      const socketKey = windowMinutes === 1 ? 't1m' : 't3m';
      const endpoint = windowMinutes === 1 ? ENDPOINTS.t1m : ENDPOINTS.t3m;
      const changeKey = windowMinutes === 1 ? 'change_1m' : 'change_3m';

      const [rows, setRows] = useState([]);
      const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

      useEffect(() => {
        let cancelled = false;
        let sock;
        try {
          sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
          sock.on('tables:update', (payload) => {
            const raw = payload?.[socketKey];
            if (!cancelled && raw) setRows(normalize(raw, changeKey));
          });
        } catch {}

        (async () => {
          try {
            const res = await fetch(endpoint);
            if (res.ok) {
              const json = await res.json();
              if (!cancelled) setRows(normalize(json, changeKey));
            }
          } catch {}
        })();

        return () => { cancelled = true; try { sock && sock.close(); } catch {} };
      }, [socketNs, socketKey, endpoint, changeKey]);

      useEffect(() => {
        const onStorage = (e) => { if (e?.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist())); };
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
      }, []);

      const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

      const onToggle = (symbol, price) => {
        toggleWatchlist(symbol, price);
        setWatchlist(new Set(loadWatchlist()));
      };

      if (!rows.length) {
        return (
          <div className="panel">
            <div className="panel__header"><h3>{title}</h3><div className="meta">loading…</div></div>
            <div className="empty">No data available.</div>
          </div>
        );
      }

      if (view === 'tiles') {
        const top8 = rows.slice(0, 8);
        return (
          <div className="panel">
            <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
            <div className="gainers-tiles">
              {top8.map(r => (
                <div key={r.symbol} className="tile">
                  <div className="mono" style={{fontWeight:600}}>{r.symbol}</div>
                  <div className="num">{fmtPrice(r.price)}</div>
                  <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
                  <button
                    className="badge"
                    aria-pressed={watchlist.has(r.symbol)}
                    title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                    onClick={() => onToggle(r.symbol, r.price)}
                  >
                    {watchlist.has(r.symbol) ? '★' : '☆'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        );
      }

      return (
        <div className="panel">
          <div className="panel__header"><h3>{title}</h3><div className="meta">assets {rows.length}</div></div>
          <table className="table compact">
            <thead>
              <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.symbol}>
                  <td className="mono">{r.symbol}</td>
                  <td className="num">{fmtPrice(r.price)}</td>
                  <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
                  <td style={{textAlign:'right'}}>
                    <button
                      className="badge"
                      aria-pressed={watchlist.has(r.symbol)}
                      title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                      onClick={() => onToggle(r.symbol, r.price)}
                    >
                      {watchlist.has(r.symbol) ? '★' : '☆'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
        </tbody>
      </table>
    </div>
  );
}

// File: original-design/frontend/src/components/LosersTable.jsx
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { loadWatchlist, toggleWatchlist } from '../lib/watchlist.js';

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
const ENDPOINT = `${API_BASE}/api/component/losers-table`;

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n); const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${v.toFixed(digits)}`;
}
function fmtPct(n) {
  if (!Number.isFinite(n)) return '-';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function normalize3m(raw) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.crypto_meta?.losers || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 = Number(
      r.change_3m ?? r.change3m ?? r.pct_3m ?? r['3m_change'] ?? r.delta_3m ?? r.change ?? 0
    ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, pct: c3 };
    const prev = map.get(sym);
    if (!prev || c3 < prev.pct) map.set(sym, entry); // most negative wins
  }
  return Array.from(map.values()).sort((a, b) => a.pct - b.pct);
}

export default function LosersTable() {
  const socketNs = `${API_BASE}/stream`;
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

  useEffect(() => {
    let cancelled = false;
    let sock;
    try {
      sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
      sock.on('tables:update', (payload) => {
        const raw = payload?.t3m_losers || payload?.losers || null;
        if (!cancelled && raw) setRows(normalize3m(raw));
      });
    } catch {}

    (async () => {
      try {
        const res = await fetch(ENDPOINT);
        if (res.ok) {
          const json = await res.json();
          if (!cancelled) setRows(normalize3m(json));
        }
      } catch {}
    })();

    return () => { cancelled = true; try { sock && sock.close(); } catch {} };
  }, [socketNs]);

  useEffect(() => {
    const onStorage = (e) => { if (e.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist())); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  if (!rows.length) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.symbol}>
              <td className="mono">{r.symbol}</td>
              <td className="num">{fmtPrice(r.price)}</td>
              <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
              <td style={{textAlign:'right'}}>
                <button
                  className="badge"
                  aria-pressed={watchlist.has(r.symbol)}
                  title={watchlist.has(r.symbol) ? 'Remove from Watchlist' : 'Add to Watchlist'}
                  onClick={() => { toggleWatchlist(r.symbol, r.price); setWatchlist(new Set(loadWatchlist())); }}
                >
                  {watchlist.has(r.symbol) ? '★' : '☆'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// File: original-design/frontend/src/components/Watchlist.jsx
import React, { useEffect, useState } from 'react';
import { loadWatchlist } from '../lib/watchlist.js';

export default function Watchlist() {
  const [symbols, setSymbols] = useState(() => loadWatchlist());
  const [items, setItems] = useState(() => loadWatchlistItems());

  useEffect(() => {
    import React, { useEffect, useMemo, useState } from 'react';