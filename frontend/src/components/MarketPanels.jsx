import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import TopBannerScroll from './TopBannerScroll.jsx';
import BottomBannerScroll from './BottomBannerScroll.jsx';

const TopOneMinGainers = lazy(() => import('./TopOneMinGainers.jsx'));
const Gainers3Min      = lazy(() => import('./Gainers3Min.jsx'));
const Losers3Min       = lazy(() => import('./Losers3Min.jsx'));
const Watchlist        = lazy(() => import('./Watchlist.jsx'));

const TABS = [
  { key: 'g1', label: '1m Gainers', Component: TopOneMinGainers },
  { key: 'g3', label: '3m Gainers', Component: Gainers3Min },
  { key: 'l3', label: '3m Losers',  Component: Losers3Min },
];
const STORAGE_KEY = 'ui:activeTab';

export default function MarketPanels() {
  const [active, setActive] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || 'g1'; } catch { return 'g1'; }
  });
  useEffect(() => { try { localStorage.setItem(STORAGE_KEY, active); } catch {} }, [active]);
  const current = useMemo(() => TABS.find(t => t.key === active) || TABS[0], [active]);
  // JSX requires component variables to be capitalized; extract here for safe rendering
  const Active = current.Component;

  return (
    <div className="mp space-y-4">
      <TopBannerScroll />

      <div className="only-mobile">
        <div className="mp__tabs">
          {TABS.map(t => (
            <button key={t.key} className={`mp__tab ${active === t.key ? 'is-active' : ''}`} onClick={() => setActive(t.key)} type="button">{t.label}</button>
          ))}
        </div>
        <div className="mp__single">
          <Suspense fallback={<PanelLoading />}>
            <Active />
          </Suspense>
        </div>
        <div className="mp__single">
          <SectionCaption>WATCHLIST</SectionCaption>
          <Suspense fallback={<PanelLoading />}>
            <Watchlist />
          </Suspense>
        </div>
      </div>

      <div className="only-desktop mp__grid-3">
        <Suspense fallback={<PanelLoading />}><TopOneMinGainers /></Suspense>
        <Suspense fallback={<PanelLoading />}><Gainers3Min /></Suspense>
        <Suspense fallback={<PanelLoading />}><Losers3Min /></Suspense>
      </div>

      <div className="only-desktop">
        <SectionCaption className="mt-2">WATCHLIST</SectionCaption>
        <Suspense fallback={<PanelLoading />}>
          <Watchlist />
        </Suspense>
      </div>

      <BottomBannerScroll />
    </div>
  );
}

function PanelLoading() {
  return <div className="app-panel p-4 text-sm text-zinc-400">Loading…</div>;
}
function SectionCaption({ children, className = '' }) {
  return <div className={`px-1 py-2 text-[11px] tracking-wide text-zinc-400 ${className}`}>{children}</div>;
}
