// Safe preconnect helper: create preconnect & dns-prefetch links for API host if available.
function coerceBase(raw) {
  try {
    if (!raw || raw === 'relative') return '';
    const url = new URL(raw, window.location.origin);
    return (url.origin || '').replace(/\/$/, '');
  } catch (e) {
    return '';
  }
}

export function injectPreconnectFromEnv() {
  try {
    const raw = (import.meta && import.meta.env && import.meta.env.VITE_API_URL) ? String(import.meta.env.VITE_API_URL) : '';
    const host = raw ? coerceBase(raw) : (window.__VITE_API_URL__ || '');
    if (!host) return;
    // create preconnect
    const link1 = document.createElement('link');
    link1.rel = 'preconnect';
    link1.href = host;
    link1.crossOrigin = '';
    document.head.appendChild(link1);
    // create dns-prefetch
    try {
      const hostOnly = new URL(host).host;
      const link2 = document.createElement('link');
      link2.rel = 'dns-prefetch';
      link2.href = '//' + hostOnly;
      document.head.appendChild(link2);
    } catch (e) {
      // ignore malformed origin
    }
  } catch (e) {
    // swallow errors; preconnect is an optimization only
  }
}

// Side-effectful default export for easy import in main.jsx
export default injectPreconnectFromEnv;
