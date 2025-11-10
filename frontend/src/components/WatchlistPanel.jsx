import React, { useMemo, useState } from 'react';
import Panel from './Panel.jsx';
import { useWatchlist } from '../context/WatchlistContext.jsx';
import { formatPrice, normalizeSymbol } from '../lib/format.js';

function pctFrom(baseline, current) {
  if (typeof baseline !== 'number' || typeof current !== 'number' || baseline === 0) return null;
  return ((current - baseline) / baseline) * 100;
}

export default function WatchlistPanel({ bySymbol = {}, onInfo }) {
  const { items, add, remove } = useWatchlist();
  const list = Array.isArray(items) ? items : [];

  const [query, setQuery] = useState('');
  const suggestions = useMemo(() => {
    const keys = Object.keys(bySymbol || {});
    const base = ['BTC','ETH','SOL','AAVE','XRP','DOGE','ADA'];
    return Array.from(new Set([...base, ...keys.map(normalizeSymbol)])).slice(0, 40);
  }, [bySymbol]);

  const handleAdd = (sym) => {
    const clean = normalizeSymbol(sym);
    if (!clean) return;
    const live = bySymbol[clean] || bySymbol[`${clean}-USD`] || bySymbol[`${clean}-USDT`];
    const price = typeof live?.current_price === 'number' ? live.current_price : null;
    add({ symbol: clean, price });
    setQuery('');
  };

  return (
    <Panel title="Watchlist">
      <form className="bh-watchlist-search" onSubmit={(e)=>{e.preventDefault(); handleAdd(query);}}>
        <span className="bh-search-icon">🔍</span>
        <input className="bh-watchlist-input" placeholder="Search & add coin (e.g. BTC, ETH)" value={query} onChange={(e)=>setQuery(e.target.value)} />
        <div className="bh-search-underline" />
      </form>

      {!list.length && <div className="panel-empty">Star a token to pin it here.</div>}
      {list.map((it) => {
        const pct = pctFrom(it.baseline, it.current);
        return (
          <div key={it.symbol} className="token-row">
            <div className="tr-col tr-col-symbol">
              <div className="tr-symbol">{it.symbol}</div>
            </div>
            <div className="tr-col tr-col-price">
              <div className="tr-price-current">{typeof it.current === 'number' ? formatPrice(it.current) : '—'}</div>
              <div className="tr-price-prev">{typeof it.baseline === 'number' ? formatPrice(it.baseline) : ''}</div>
            </div>
            <div className="tr-col tr-col-pct">
              <span className={pct != null && pct < 0 ? 'token-pct-loss' : 'token-pct-gain'}>
                {pct == null ? '—' : `${pct.toFixed(2)}%`} <span className="bh-wl-timeframe">1m</span>
              </span>
            </div>
            <div className="tr-col tr-col-actions">
              <button className="wl-btn" onClick={() => onInfo?.(it.symbol)}>i</button>
              <button className="wl-btn" onClick={() => remove(it.symbol)}>×</button>
            </div>
          </div>
        );
      })}

      {suggestions.length > 0 && (
        <div className="bh-watchlist-suggestions">
          {suggestions.slice(0, 8).map((s)=> (
            <button key={s} type="button" className="bh-wl-suggestion" onClick={()=>handleAdd(s)}>{s}</button>
          ))}
        </div>
      )}
    </Panel>
  );
}
