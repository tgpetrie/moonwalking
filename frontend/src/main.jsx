import './index.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './app.jsx';
import '../index.css';
import './styles/animations.css';

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
import { startSSE } from './lib/sse.js';

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
