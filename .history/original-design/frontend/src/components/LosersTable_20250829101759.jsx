import React, { useEffect, useState, useMemo, useRef } from 'react';
import UniformCard from './UniformCard.jsx';
import { fetchWithSWR, API_ENDPOINTS } from '../lib/api.js';

function normalize(raw) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const pct = Number(r.change_3m ?? r.change ?? r.pct ?? r.delta ?? r.price_change_percentage_3m ?? 0) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? r.current ?? 0) || 0;
    const entry = { symbol: sym, price: px, change: pct };
    const prev = map.get(sym);
    if (!prev || entry.change < prev.change) map.set(sym, entry);
  }
  return Array.from(map.values()).sort((a, b) => a.change - b.change);
}

export default function LosersTable({ view = 'table' }) {
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set());
  // streakMap: symbol -> streak count
  const streakMapRef = useRef({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchWithSWR(API_ENDPOINTS.losersTable);
        if (!cancelled) setRows(normalize(res?.data ?? res ?? []));
      } catch (e) {}
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const { loadWatchlist } = await import('../lib/watchlist.js');
        setWatchlist(new Set(loadWatchlist()));
      } catch (e) {}
    })();
  }, []);

  // Update streakMapRef on each rows refresh
  useEffect(() => {
    const newSyms = new Set();
    for (const r of rows) {
      const symbol = String(r.symbol).replace('-USD','');
      newSyms.add(symbol);
    }
    const streakMap = streakMapRef.current;
    for (const symbol of newSyms) {
      if (streakMap[symbol]) {
        streakMap[symbol] += 1;
      } else {
        streakMap[symbol] = 1;
      }
    }
    for (const symbol in streakMap) {
      if (!newSyms.has(symbol)) {
        delete streakMap[symbol];
      }
    }
  }, [rows]);

  const topRows = useMemo(() => rows.slice(0, 8), [rows]);

  const onToggle = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist } = await import('../lib/watchlist.js');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(loadWatchlist()));
    } catch (e) {}
  };

  if (!rows.length) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  if (view === 'tiles') {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
        <div className="gainers-tiles">
          {topRows.map((r, idx) => {
            const symbol = String(r.symbol).replace('-USD','');
            const streak = streakMapRef.current[symbol] || 0;
            return (
              <UniformCard
                key={r.symbol}
                symbol={symbol}
                price={r.price}
                change={r.change}
                rank={idx+1}
                streak={streak}
                windowLabel="3-min"
                filled={watchlist.has(r.symbol)}
                onToggle={onToggle}
              />
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th><th/></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const symbol = String(r.symbol).replace('-USD','');
            const streak = streakMapRef.current[symbol] || 0;
            return (
              <tr key={`${r.symbol}-${i}`}>
                <td className="mono">{symbol}</td>
                <td className="num">{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
                <td className={`num ${r.change >= 0 ? 'positive' : 'negative'}`}>{Number.isFinite(r.change) ? `${r.change.toFixed(2)}%` : '-'}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="badge" onClick={() => onToggle(r.symbol, r.price)} aria-pressed={watchlist.has(r.symbol)}>{watchlist.has(r.symbol) ? '★' : '☆'}</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
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
    import React, { useEffect, useState } from 'react';
    import { io } from 'socket.io-client';

    const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
    const ENDPOINTS = {
      t3m: `${API_BASE}/api/component/losers-table`,
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

    function normalize(raw) {
      let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
      if (!Array.isArray(rows)) rows = [];
      const map = new Map();
      for (const r of rows) {
        const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
        if (!sym) continue;
        const pct = Number(r.change_3m ?? r.change ?? r.pct ?? r.delta ?? 0) || 0;
        const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
        const entry = { symbol: sym, price: px, pct };
        const prev = map.get(sym);
        if (!prev || pct < prev.pct) map.set(sym, entry);
      }
      return Array.from(map.values()).sort((a, b) => a.pct - b.pct);
    }

    export default function LosersTable({ view = 'table' }) {
      const socketNs = `${API_BASE}/stream`;
      const [rows, setRows] = useState([]);

      useEffect(() => {
        let cancelled = false;
        let sock;
        try {
          sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
          sock.on('tables:update', (payload) => {
            const raw = payload?.t3m;
            if (!cancelled && raw) setRows(normalize(raw));
          });
        } catch {}

        (async () => {
          try {
            const res = await fetch(ENDPOINTS.t3m);
            if (res.ok) {
              const json = await res.json();
              if (!cancelled) setRows(normalize(json));
            }
          } catch {}
        })();

        return () => { cancelled = true; try { sock && sock.close(); } catch {} };
      }, [socketNs]);

      const title = '3-minute Losers';

      const onAddToWatchlist = async (symbol, price) => {
        try {
          const { toggleWatchlist } = await import('../lib/watchlist');
          await toggleWatchlist(symbol, price);
        } catch (err) {
          // ignore
        }
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
                    title={`Add ${r.symbol} to Watchlist`}
                    onClick={() => onAddToWatchlist(r.symbol, r.price)}
                  >
                    ☆
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
                      onClick={() => onAddToWatchlist(r.symbol, r.price)}
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

import React, { useEffect, useMemo, useRef, useState } from 'react';
import UniformCard from './UniformCard.jsx';
import { fetchWithSWR, API_ENDPOINTS } from '../lib/api.js';

// Normalize various backend payload shapes into a simple losers array
function normalize(raw) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const pct = Number(
      r.change_3m ?? r.change ?? r.pct ?? r.delta ?? r.price_change_percentage_3m ?? 0
    ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? r.current ?? 0) || 0;
    const entry = { symbol: sym, price: px, change: pct };
    const prev = map.get(sym);
    // keep the most negative change per symbol
    if (!prev || entry.change < prev.change) map.set(sym, entry);
  }
  return Array.from(map.values()).sort((a, b) => a.change - b.change);
}

export default function LosersTable({ view = 'table' }) {
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set());
  // streakMap: symbol (no -USD) -> consecutive render count
  const streakMapRef = useRef({});

  // Fetch losers once (SWR under the hood updates on interval)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchWithSWR(API_ENDPOINTS.losersTable);
        if (!cancelled) setRows(normalize(res?.data ?? res ?? []));
      } catch (e) {
        // swallow; UI will show empty state
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Seed watchlist
  useEffect(() => {
    (async () => {
      try {
        const { loadWatchlist } = await import('../lib/watchlist.js');
        setWatchlist(new Set(loadWatchlist()));
      } catch (e) {}
    })();
  }, []);

  // Maintain simple consecutive-presence streak counter per symbol
  useEffect(() => {
    const newSyms = new Set();
    for (const r of rows) newSyms.add(String(r.symbol).replace('-USD', ''));

    const streakMap = streakMapRef.current;
    // increment or start streaks for symbols still present
    for (const symbol of newSyms) streakMap[symbol] = (streakMap[symbol] || 0) + 1;
    // drop streaks for symbols that disappeared
    for (const symbol of Object.keys(streakMap)) if (!newSyms.has(symbol)) delete streakMap[symbol];
  }, [rows]);

  const topRows = useMemo(() => rows.slice(0, 8), [rows]);

  const onToggle = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist } = await import('../lib/watchlist.js');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(loadWatchlist()));
    } catch (e) {}
  };

  if (!rows.length) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  if (view === 'tiles') {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
        <div className="gainers-tiles">
          {topRows.map((r, idx) => {
            const symbol = String(r.symbol).replace('-USD', '');
            const streak = streakMapRef.current[symbol] || 0;
            return (
              <UniformCard
                key={r.symbol}
                symbol={symbol}
                price={r.price}
                change={r.change}
                rank={idx + 1}
                streak={streak}
                windowLabel="3-min"
                filled={watchlist.has(r.symbol)}
                onToggle={onToggle}
              />
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th><th/></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const symbol = String(r.symbol).replace('-USD', '');
            const streak = streakMapRef.current[symbol] || 0;
            const priceTxt = Number.isFinite(r.price) ? r.price.toFixed(4) : '-';
            const changeTxt = Number.isFinite(r.change) ? `${r.change.toFixed(2)}%` : '-';
            return (
              <tr key={`${r.symbol}-${i}`}>
                <td className="mono">{symbol}{streak > 1 ? <span className="meta" style={{marginLeft:6}}>px{streak}</span> : null}</td>
                <td className="num">{priceTxt}</td>
                <td className={`num ${r.change >= 0 ? 'positive' : 'negative'}`}>{changeTxt}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="badge" onClick={() => onToggle(r.symbol, r.price)} aria-pressed={watchlist.has(r.symbol)}>
                    {watchlist.has(r.symbol) ? '★' : '☆'}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}