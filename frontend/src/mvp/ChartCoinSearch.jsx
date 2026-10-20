import { useEffect, useRef, useState } from 'react';
import { UiButton, UiCard, UiField } from '../components/ui/DesignSystem.jsx';
import { publicHistoryClient } from '../utils/publicChartHistory.js';

export default function ChartCoinSearch({ onHistory, onBegin, onBusyChange, hasHistory, client = publicHistoryClient }) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState(null);
  const [busy, setBusy] = useState('');
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');
  const active = useRef(null);
  const revision = useRef(0);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => { onBusyChange?.(!!busy); }, [busy, onBusyChange]);
  const run = async (product) => {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    const id = ++revision.current;
    setBusy(product ? product.symbol : 'search'); setError(''); setProgress(null);
    onBegin?.();
    try {
      if (!product) {
        const found = await client.search(query, { signal: controller.signal });
        if (id === revision.current) setMatches(found);
      } else {
        const history = await client.history(product.id, { signal: controller.signal, force: true, includeLatestTrade: true,
          onProgress: (value) => { if (id === revision.current) setProgress(value); } });
        if (id === revision.current && !controller.signal.aborted) { onHistory(history); setMatches(null); }
      }
    } catch (failure) {
      if (id === revision.current && failure.name !== 'AbortError') setError(failure.message || 'History could not be loaded. Try again.');
    } finally { if (id === revision.current) setBusy(''); }
  };
  const cancel = () => { active.current?.abort(); revision.current += 1; setBusy(''); setProgress(null); };
  return <UiCard className="macro-search" tone="subtle">
    <form onSubmit={(e) => { e.preventDefault(); if (query.trim() && !busy) run(); }}>
      <UiField label="Search coin" placeholder="AMP, BTC, SOL…" value={query} maxLength={20}
        onChange={(e) => { if (busy) cancel(); setQuery(e.target.value); setMatches(null); setError(''); }}
        hint="Enter a coin symbol. History loads automatically from Coinbase’s USD markets." />
      <UiButton type="submit" variant="primary" disabled={!!busy || !query.trim()}>Search</UiButton>
      {busy && <UiButton onClick={cancel}>Cancel</UiButton>}
    </form>
    {busy && <div role="status" className="macro-search-progress">{busy === 'search' ? 'Finding coins…' : <>
      Loading {busy} history… {progress ? `${progress.completed} of ${progress.total} date ranges checked · ${progress.candles.toLocaleString()} daily candles` : 'Preparing download…'}
      <p>This can take a minute. The chart stays available while another coin loads.</p>
    </>}</div>}
    {error && <p role="alert" className="macro-error">{error}{hasHistory ? ' Your previous chart has been kept.' : ''}</p>}
    {matches && <div className="macro-search-results" aria-label="Coin search results">
      {matches.length ? matches.map((p) => <UiButton key={p.id} disabled={!!busy} onClick={() => run(p)}>
        Analyse {p.symbol} <span className="macro-muted">· {p.venue} · {p.quote}{p.status !== 'online' ? ' · historical market' : ''}</span>
      </UiButton>) : <p>No matching USD market is available from this source. Try another symbol. Coins from other exchanges are not connected yet.</p>}
    </div>}
  </UiCard>;
}
