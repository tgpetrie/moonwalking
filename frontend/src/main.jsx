import './index.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './app.jsx';
import '../index.css';
import './styles/animations.css';
import './styles/glow.css';
import './styles/rows.css';

// Responsive best practices: index.css already includes Tailwind and responsive settings.
// No changes needed here, but ensure root element is used for hydration.
try {
  console.info('[app.debug] Mounting React app to #root');
} catch (e) {
  console.warn('debug log failed', e);
}
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Option B: module-based loader wiring for bundlers. Import relative module.
import './bhabitLogoLoaderModule.js';
import { startSSE } from './lib/sse.js';
import { endpoints } from './lib/api.ts';

// Listen for DO updates and lightly refresh data when needed
try {
  const stop = startSSE((msg) => {
    try {
      const type = msg?.type;
      const changed = msg?.changed;
      if (type === 'update' || (type === 'tick' && changed)) {
        fetch(endpoints.gainers1m).catch(() => {});
        fetch(endpoints.gainers3m).catch(() => {});
        fetch(endpoints.losers3m).catch(() => {});
        fetch(endpoints.banner1h).catch(() => {});
        fetch(endpoints.bannerVolume1h).catch(() => {});
      }
    } catch (e) {
      console.warn('sse message handler failed', e);
    }
  });

  // HMR cleanup
  if (import.meta.hot) import.meta.hot.dispose(() => stop());
} catch (e) {
  console.warn('sse init failed', e);
}
