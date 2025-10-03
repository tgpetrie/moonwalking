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

// --- Minimal SSE client (inline) ---
// NOTE: adapted to JS from the TS snippet. The payload shape is:
// { type: 'hello'|'tick'|'update'|..., updatedAt?: number, changed?: boolean }
function startSSE(onUpdate) {
  let es = null;
  let retryMs = 1000;
  const maxMs = 30000;

  const connect = () => {
    es = new EventSource('/api/events');

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        onUpdate(data);
      } catch (err) {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      try {
        if (es) es.close();
      } catch (e) {}
      es = null;
      setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, maxMs);
    };

    es.onopen = () => {
      retryMs = 1000;
    };
  };

  connect();

  return () => {
    try {
      if (es) {
        es.close();
        es = null;
      }
    } catch (e) {}
  };
}
// --- End SSE client ---

// Listen for DO updates and lightly refresh data when needed
try {
  const stop = startSSE((msg) => {
    try {
      const type = msg?.type;
      const changed = msg?.changed;
      if (type === 'update' || (type === 'tick' && changed)) {
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
} catch (e) {}
