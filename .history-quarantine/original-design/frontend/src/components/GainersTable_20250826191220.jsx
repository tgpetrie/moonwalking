import React, { useEffect, useRef, useState } from 'react';
import { io } from 'socket.io-client';
import StarIcon from './StarIcon.jsx';
import { loadWatchlist } from '../lib/watchlist.js';

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
const ENDPOINTS = {
  // Use the 3-minute gainers snapshot as a reasonable fallback snapshot endpoint
  snapshot: `${API_BASE}/api/component/gainers-table`,
};

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n);
  const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${v.toFixed(digits)}`;
}

function fmtPct(n) {
  if (n == null || !Number.isFinite(n)) return '--';
  const s = n > 0 ? '+' : '';
  return `${s}${n.toFixed(2)}%`;
}

// Helper: compute pct = (now - past)/past * 100
function computePct(past, now) {
  if (!Number.isFinite(past) || past === 0) return null;
  return ((now - past) / past) * 100;
}

export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
  const socketNs = `${API_BASE}/stream`;
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

  // Keep price history in a ref to avoid re-renders on every tick.
  // Map<string, Array<{ts:number, price:number}>>
  const priceHistoryRef = useRef(new Map());

  // How far back we need to keep history (ms)
  const keepMs = 3 * 60 * 1000; // 3 minutes

  // Socket key doesn't need to determine pct logic; we compute client-side
  const socketKey = windowMinutes === 1 ? 't1m' : 't3m';

  // Add a price sample to history and prune old samples
  function pushPrice(symbol, price, ts = Date.now()) {
    if (!symbol) return;
    const key = symbol.toUpperCase();
    let arr = priceHistoryRef.current.get(key);
    if (!arr) {
      arr = [];
      priceHistoryRef.current.set(key, arr);
    }
    // push newest
    arr.push({ ts, price });
    // prune older than keepMs
    const cutoff = ts - keepMs;
    let i = 0;
    while (i < arr.length && arr[i].ts < cutoff) i++;
    if (i > 0) arr.splice(0, i);
  }

  // get past price closest-to-or-before targetTs
  function getPastPrice(symbol, targetTs) {
    const key = symbol.toUpperCase();
    const arr = priceHistoryRef.current.get(key) || [];
    if (!arr.length) return null;
    // binary search or linear from end (small arrays expected)
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i].ts <= targetTs) return arr[i].price;
    }
    // if nothing earlier, return earliest
    return arr[0].price;
  }

  // Build rows from a list of latest price points (array of {symbol, price})
  function buildRows(latestList) {
    const now = Date.now();
    const windowMs = windowMinutes === 1 ? 60 * 1000 : 3 * 60 * 1000;
    const cutoffTs = now - windowMs;
    const items = (latestList || []).map((r) => {
      const symbol = (r.symbol || r.ticker || r.s || r.base || '').toUpperCase();
      const price = Number(r.price ?? r.last ?? r.p ?? r.close ?? r.current ?? 0) || 0;
      // ensure history has this price
      pushPrice(symbol, price, now);
      const past = getPastPrice(symbol, cutoffTs);
      const pct = past == null ? null : computePct(past, price);
      return { symbol, price, pct: pct == null ? 0 : pct };
    });
    // sort by pct descending (null/undefined treated as -Infinity => push last)
    items.sort((a, b) => (b.pct || -Infinity) - (a.pct || -Infinity));
    return items;
  }

  // Listen for watchlist changes (only for star UI state)
  useEffect(() => {
    const onStorage = (e) => {
      if (e?.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist()));
    };
    const onWatchlistChanged = () => setWatchlist(new Set(loadWatchlist()));
    window.addEventListener('storage', onStorage);
    window.addEventListener('watchlist:changed', onWatchlistChanged);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('watchlist:changed', onWatchlistChanged);
    };
  }, []);

  // Socket + initial snapshot
  useEffect(() => {
    let cancelled = false;
    let sock;

    try {
      sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
      sock.on('tables:update', (payload) => {
        // payload may be { t1m: [...], t3m: [...] } or a flat array/map
        const raw = payload?.[socketKey] ?? payload;
        if (cancelled || !raw) return;
        let list = Array.isArray(raw) ? raw : Object.values(raw);
        const built = buildRows(list);
        if (!cancelled) setRows(built);
      });
    } catch (err) {
      // ignore socket errors
    }

    // initial snapshot fetch (fallback)
    (async () => {
      try {
        const res = await fetch(ENDPOINTS.snapshot);
        if (!res.ok) return;
        const json = await res.json();
        if (cancelled) return;
        const list = Array.isArray(json) ? json : json?.data ?? json?.rows ?? [];
        setRows(buildRows(list));
      } catch (err) {
        // ignore
      }
    })();

    const pruneTimer = setInterval(() => {
      // occasionally prune histories and recompute rows to keep UI fresh
      const now = Date.now();
      for (const [k, arr] of priceHistoryRef.current.entries()) {
        let i = 0;
        while (i < arr.length && arr[i].ts < now - keepMs) i++;
        if (i > 0) arr.splice(0, i);
        if (!arr.length) priceHistoryRef.current.delete(k);
      }
      // recompute current rows from latest known prices
      const latest = Array.from(priceHistoryRef.current.entries()).map(([sym, arr]) => ({ symbol: sym, price: arr[arr.length - 1].price }));
      if (latest.length) setRows(buildRows(latest));
    }, 5000);

    return () => {
      cancelled = true;
      try { sock && sock.close(); } catch (e) {}
      clearInterval(pruneTimer);
    };
  }, [socketNs, socketKey, windowMinutes]);

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  const toggleStar = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(_load()));
    } catch (err) {
      // ignore
    }
  };

  if (!rows || !rows.length) {
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
          {top8.map((r) => (
            <div key={r.symbol} className="tile">
              <div className="mono" style={{ fontWeight: 600 }}>{r.symbol}</div>
              <div className="num">{fmtPrice(r.price)}</div>
              <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
              <StarIcon filled={watchlist.has(r.symbol)} onClick={() => toggleStar(r.symbol, r.price)} />
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
          <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th/></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td className="mono">{r.symbol}</td>
              <td className="num">{fmtPrice(r.price)}</td>
              <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
              <td style={{ textAlign: 'right' }}>
                <StarIcon filled={watchlist.has(r.symbol)} onClick={() => toggleStar(r.symbol, r.price)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import StarIcon from './StarIcon.jsx';
import { loadWatchlist } from '../lib/watchlist.js';

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
const ENDPOINTS = {
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
};

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n);
  const abs = Math.abs(v);
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
    import React, { useEffect, useState } from 'react';
    import { io } from 'socket.io-client';
    import StarIcon from './StarIcon.jsx';
    import { loadWatchlist } from '../lib/watchlist.js';

    const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
    const ENDPOINTS = {
      t1m: `${API_BASE}/api/component/gainers-table-1min`,
      t3m: `${API_BASE}/api/component/gainers-table`,
    };

    function fmtPrice(n) {
      if (!Number.isFinite(n)) return '-';
      const v = Number(n);
      return `$${v.toFixed(v >= 1 ? 2 : 4)}`;
    }

    function fmtPct(n) {
      if (!Number.isFinite(n)) return '-';
      const s = n > 0 ? '+' : '';
      return `${s}${n.toFixed(2)}%`;
    }

    function normalize(raw) {
      const rows = Array.isArray(raw) ? raw : raw?.data || raw?.rows || [];
      return (rows || [])
        .map((r) => ({
          symbol: (r.symbol || r.ticker || r.s || r.base || '').toUpperCase(),
          price: Number(r.price || r.last || r.p || r.close || 0),
          pct: Number(r.change || r.pct || 0),
        }))
        .filter((x) => x.symbol)
        .sort((a, b) => b.pct - a.pct);
    }

    export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
      const endpoint = windowMinutes === 1 ? ENDPOINTS.t1m : ENDPOINTS.t3m;
      const [rows, setRows] = useState([]);
      const [watchlist, setWatchlist] = useState(() => new Set(loadWatchlist()));

      useEffect(() => {
        let cancelled = false;
        (async () => {
          try {
            const res = await fetch(endpoint);
            if (res.ok) {
              const j = await res.json();
              if (!cancelled) setRows(normalize(j));
            }
          } catch (err) {
            // ignore
          }
        })();
        return () => {
          cancelled = true;
        };
      }, [endpoint]);

      const onToggle = async (symbol, price) => {
        try {
          const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
          await toggleWatchlist(symbol, price);
          setWatchlist(new Set(_load()));
        } catch (err) {
          // ignore
        }
      };

      if (!rows.length) {
        return (
          <div className="panel">
            <div className="panel__header">
              <h3>Gainers</h3>
            </div>
            <div className="empty">No data</div>
          </div>
        );
      }

      return (
        <div className="panel">
          <div className="panel__header">
            <h3>Gainers</h3>
            <div className="meta">{rows.length} assets</div>
          </div>
          <table className="table compact">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>Δ</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol}>
                  <td className="mono">{r.symbol}</td>
                  <td className="num">{fmtPrice(r.price)}</td>
                  <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onToggle(r.symbol, r.price)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
      } catch (err) {
        // ignore fetch errors
      }
    })();

    return () => {
      cancelled = true;
      try { sock && sock.close(); } catch {}
    };
  }, [socketNs, socketKey, endpoint, changeKey]);

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  const onAddToWatchlist = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(_load()));
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
          {top8.map((r) => (
            <div key={r.symbol} className="tile">
              <div className="mono" style={{ fontWeight: 600 }}>{r.symbol}</div>
              <div className="num">{fmtPrice(r.price)}</div>
              <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
              <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
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
          <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th /></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td className="mono">{r.symbol}</td>
              <td className="num">{fmtPrice(r.price)}</td>
              <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
              <td style={{ textAlign: 'right' }}>
                <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import StarIcon from './StarIcon.jsx';
import { loadWatchlist } from '../lib/watchlist.js';

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_BACKEND_ORIGIN) || 'http://localhost:5001';
const ENDPOINTS = {
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
};

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n);
  const abs = Math.abs(v);
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
    const onStorage = (e) => {
      if (e?.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist()));
    };
    const onWatchlistChanged = () => setWatchlist(new Set(loadWatchlist()));
    window.addEventListener('storage', onStorage);
    window.addEventListener('watchlist:changed', onWatchlistChanged);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('watchlist:changed', onWatchlistChanged);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let sock;

    try {
      sock = io(socketNs, { path: '/socket.io', transports: ['websocket'] });
      sock.on('tables:update', (payload) => {
        const raw = payload?.[socketKey];
        if (!cancelled && raw) setRows(normalize(raw, changeKey));
      });
    } catch (err) {
      // ignore socket errors
    }

    (async () => {
      try {
        const res = await fetch(endpoint);
        if (res.ok) {
          const json = await res.json();
          if (!cancelled) setRows(normalize(json, changeKey));
        }
      } catch (err) {
        // ignore fetch errors
      }
    })();

    return () => {
      cancelled = true;
      try { sock && sock.close(); } catch {}
    };
  }, [socketNs, socketKey, endpoint, changeKey]);

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  const onAddToWatchlist = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(_load()));
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
          {top8.map((r) => (
            <div key={r.symbol} className="tile">
              <div className="mono" style={{ fontWeight: 600 }}>{r.symbol}</div>
              <div className="num">{fmtPrice(r.price)}</div>
              <div className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</div>
              <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
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
          <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th /></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td className="mono">{r.symbol}</td>
              <td className="num">{fmtPrice(r.price)}</td>
              <td className={`num ${r.pct >= 0 ? 'positive' : 'negative'}`}>{fmtPct(r.pct)}</td>
              <td style={{ textAlign: 'right' }}>
                <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
      window.removeEventListener('watchlist:changed', onWatchlistChanged);
    };
  }, []);

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

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  const onAddToWatchlist = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(_load()));
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
              <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
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
                <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import StarIcon from './StarIcon.jsx';
import { loadWatchlist } from '../lib/watchlist.js';

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
    const onStorage = (e) => { if (e?.key === 'watchlist:symbols') setWatchlist(new Set(loadWatchlist())); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

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

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

  const onAddToWatchlist = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist: _load } = await import('../lib/watchlist');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(_load()));
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
              <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
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
                <StarIcon filled={watchlist.has(r.symbol)} onClick={() => onAddToWatchlist(r.symbol, r.price)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

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

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

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
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

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

  const title = windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers';

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