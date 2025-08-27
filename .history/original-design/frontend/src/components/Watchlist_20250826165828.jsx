import React, { useEffect, useState } from 'react';
import { loadWatchlistItems, pctSinceAdded } from '../lib/watchlist.js';

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n); const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${v.toFixed(digits)}`;
import React, { useEffect, useState } from 'react';
import { loadWatchlistItems, pctSinceAdded } from '../lib/watchlist.js';

function fmtPrice(n) {
  if (!Number.isFinite(n)) return '-';
  const v = Number(n); const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${v.toFixed(digits)}`;
}

export default function Watchlist() {
  const [items, setItems] = useState(() => loadWatchlistItems());
  const [prices, setPrices] = useState({});

  useEffect(() => {
    const onStorage = (e) => { if (e?.key === 'watchlist:symbols') setItems(loadWatchlistItems()); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function fetchPrices() {
      const syms = (items || []).map(i => i.symbol).slice(0, 50);
      const pmap = {};
      await Promise.all(syms.map(async (s) => {
        try {
          const res = await fetch(`https://api.coinbase.com/v2/prices/${s}-USD/spot`);
          if (!res.ok) return;
          const json = await res.json();
          const amt = json?.data?.amount ? Number(json.data.amount) : null;
          if (!cancelled) pmap[s] = amt;
        } catch (e) {
          // ignore per-item errors
        }
      }));
      if (!cancelled) setPrices(pmap);
    }
    if (items && items.length) fetchPrices();
    const id = setInterval(fetchPrices, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [items]);

  if (!items || items.length === 0) return null;

  return (
    <div className="panel">
      <div className="panel__header"><h3>My Watchlist</h3><div className="meta">assets {items.length}</div></div>
      <ul className="watchlist">
        {items.map(it => (
          <li key={it.symbol} className="watchlist-item" style={{display:'flex',justifyContent:'space-between',padding:'8px 12px',alignItems:'center'}}>
            <div style={{display:'flex',flexDirection:'column'}}>
              <div className="mono" style={{fontWeight:600}}>{it.symbol}</div>
              <div className="meta small" style={{fontSize:12,color:'#9aa6b2'}}>
                {it.addedPrice ? `added ${fmtPrice(it.addedPrice)}` : 'added —'}{it.addedAt ? ` • ${new Date(it.addedAt).toLocaleString()}` : ''}
              </div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontWeight:700}}>{prices[it.symbol] ? fmtPrice(prices[it.symbol]) : '—'}</div>
              <div style={{fontSize:12,color: prices[it.symbol] && it.addedPrice && pctSinceAdded(it.addedPrice, prices[it.symbol]) >= 0 ? '#a78bfa' : '#ff4fa3'}}>
                {it.addedPrice && prices[it.symbol] ? (() => { const p = pctSinceAdded(it.addedPrice, prices[it.symbol]); return p == null ? '—' : `${p.toFixed(2)}%`; })() : '--'}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
}
