import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { toggleWatchlist } from '../lib/watchlist.js';

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
  // LosersTable does not read the watchlist; it only allows adding items to it.
  return () => {};
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
                  title={`Add ${r.symbol} to Watchlist`}
                  onClick={() => { toggleWatchlist(r.symbol, r.price); }}
                >
                  ☆
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import StarIcon from './StarIcon';
import { loadWatchlist, toggleWatchlist } from '../lib/watchlist.js';

const LosersTable = ({ refreshTrigger }) => {
  // Inject animation styles for pop/fade effects
  useEffect(() => {
    if (typeof window !== 'undefined' && !document.getElementById('losers-table-animations')) {
      const style = document.createElement('style');
      style.id = 'losers-table-animations';
      style.innerHTML = `
        @keyframes starPop {
          0% { transform: scale(1); }
          40% { transform: scale(1.35); }
          70% { transform: scale(0.92); }
          100% { transform: scale(1); }
        }
        .animate-star-pop {
          animation: starPop 0.35s cubic-bezier(.4,2,.6,1) both;
        }
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(-8px) scale(0.9); }
          10% { opacity: 1; transform: translateY(0) scale(1.05); }
          80% { opacity: 1; transform: translateY(0) scale(1.05); }
          100% { opacity: 0; transform: translateY(-8px) scale(0.9); }
        }
        .animate-fade-in-out {
          animation: fadeInOut 1.2s cubic-bezier(.4,2,.6,1) both;
        }
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [popStar, setPopStar] = useState(null); // symbol for pop animation
  const [addedBadge, setAddedBadge] = useState(null); // symbol for 'Added!' badge

  const getDotStyle = (badge) => {
    if (badge === 'STRONG HIGH') {
      return 'bg-red-400 shadow-red-400/50';
    } else if (badge === 'STRONG') {
      return 'bg-orange-400 shadow-orange-400/50';
    } else {
      return 'bg-yellow-400 shadow-yellow-400/50';
    }
  };

  const getBadgeText = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
    return 'MODERATE';
  };

  useEffect(() => {
    let isMounted = true;
    const fetchLosersData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.losersTable);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const losersWithRanks = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_3min || 0,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3min || 0))
          }));
          if (isMounted) setData(losersWithRanks.slice(0, 7));
        } else if (isMounted && data.length === 0) {
          // Fallback data showing some crypto with negative/low gains
          setData([
            { rank: 1, symbol: 'PEPE', price: 0.00000996, change: -2.45, badge: 'MODERATE' },
            { rank: 2, symbol: 'SHIB', price: 0.00002156, change: -1.82, badge: 'MODERATE' },
            { rank: 3, symbol: 'FLOKI', price: 0.000234, change: -0.95, badge: 'MODERATE' },
            { rank: 4, symbol: 'BONK', price: 0.00001717, change: -0.67, badge: 'MODERATE' },
            { rank: 5, symbol: 'WIF', price: 2.543, change: -0.23, badge: 'MODERATE' },
            { rank: 6, symbol: 'NEW1', price: 1.234, change: -0.45, badge: 'MODERATE' },
            { rank: 7, symbol: 'NEW2', price: 0.567, change: -0.32, badge: 'MODERATE' }
          ]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching losers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          
          // Fallback mock data when backend is offline
          const fallbackData = [
            { rank: 1, symbol: 'SEI-USD', current_price: 0.2244, price_change_percentage_3m: -12.89 },
            { rank: 2, symbol: 'AVAX-USD', current_price: 24.56, price_change_percentage_3m: -8.45 },
            { rank: 3, symbol: 'DOT-USD', current_price: 4.78, price_change_percentage_3m: -6.23 },
            { rank: 4, symbol: 'ATOM-USD', current_price: 7.89, price_change_percentage_3m: -9.34 },
            { rank: 5, symbol: 'NEAR-USD', current_price: 3.45, price_change_percentage_3m: -5.67 },
            { rank: 6, symbol: 'NEW1', current_price: 1.234, price_change_percentage_3m: -0.45 },
            { rank: 7, symbol: 'NEW2', current_price: 0.567, price_change_percentage_3m: -0.32 }
          ].map(item => ({
            ...item,
            price: item.current_price,
            change: item.price_change_percentage_3m,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3m))
          }));
          setData(fallbackData);
        }
      }
    };
    fetchLosersData();
    const interval = setInterval(fetchLosersData, 30000);
    return () => { isMounted = false; clearInterval(interval); };
  }, [refreshTrigger]);

  useEffect(() => {
    // Prime watchlist from centralized helper
    setWatchlist(loadWatchlist());
  }, [refreshTrigger]);

  const handleToggleWatchlist = (symbol, price = null) => {
    const exists = watchlist.includes(symbol);
    if (!exists) {
      setPopStar(symbol);
      setAddedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setAddedBadge(null), 1200);
    }
    toggleWatchlist(symbol, price);
    setWatchlist(loadWatchlist());
  };

  if (loading && data.length === 0) {
    return (
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
                        }}
