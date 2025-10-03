import './index.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './app.jsx';
import '../index.css';

// Responsive best practices: index.css already includes Tailwind and responsive settings.
// No changes needed here, but ensure root element is used for hydration.
try {
  console.info('[app.debug] Mounting React app to #root');
} catch (e) {}
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Option B: module-based loader wiring for bundlers. Import relative module.
import './bhabitLogoLoaderModule.js';

// Start lightweight SSE subscription to the DO and trigger small refetches on updates
try {
  // dynamic import to avoid blocking if the file isn't present in test env
  import('./lib/sse').then(({ startSSE }) => {
    const stop = startSSE((msg) => {
      try {
        if (msg?.type === 'update' || (msg?.type === 'tick' && msg?.changed)) {
          // Fire-and-forget light refetches; edge cache will make these cheap
          fetch('/api/component/gainers-table-1min').catch(() => {});
          fetch('/api/component/gainers-table-3min').catch(() => {});
          fetch('/api/component/losers-table-3min').catch(() => {});
          fetch('/api/component/top-banner-scroll').catch(() => {});
          fetch('/api/component/bottom-banner-scroll').catch(() => {});
        }
      } catch (e) {}
    });

    // HMR cleanup
    if (import.meta.hot) import.meta.hot.dispose(() => stop());
  }).catch(() => {});
} catch (e) {}
