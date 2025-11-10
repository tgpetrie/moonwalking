import React from 'react';
import Panel from './Panel.jsx';
import { useWatchlist } from '../context/WatchlistContext.jsx';

function pctFrom(baseline, current) {
  if (typeof baseline !== 'number' || typeof current !== 'number' || baseline === 0) return null;
  return ((current - baseline) / baseline) * 100;
}

export default function WatchlistPanel({ onInfo }) {
  const { items, remove } = useWatchlist();
  const list = Array.isArray(items) ? items : [];

  return (
    <Panel title="Watchlist">
      {!list.length && <div className="panel-empty">Star a token to pin it here.</div>}
      {list.map((it) => {
        const pct = pctFrom(it.baselinePrice, it.currentPrice);
        return (
          <div key={it.symbol} className="token-row">
            <div className="tr-col tr-col-symbol">
              <div className="tr-symbol">{it.symbol}</div>
            </div>
            <div className="tr-col tr-col-price">
              <div className="tr-price-current">{typeof it.currentPrice === 'number' ? `$${it.currentPrice.toFixed(4)}` : '—'}</div>
              <div className="tr-price-prev">{typeof it.baselinePrice === 'number' ? `$${it.baselinePrice.toFixed(4)}` : ''}</div>
            </div>
            <div className="tr-col tr-col-pct">
              <span className={pct != null && pct < 0 ? 'token-pct-loss' : 'token-pct-gain'}>
                {pct == null ? '—' : `${pct.toFixed(2)}%`}
              </span>
            </div>
            <div className="tr-col tr-col-actions">
              <button className="wl-btn" onClick={() => onInfo?.(it.symbol)}>i</button>
              <button className="wl-btn" onClick={() => remove(it.symbol)}>×</button>
            </div>
          </div>
        );
      })}
    </Panel>
  );
}
