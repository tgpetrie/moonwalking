// Debug helper: log resolved API/WS env without forcing localhost defaults
try {
  const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').toString();
  const WS_URL = (import.meta.env.VITE_WS_URL ?? '').toString();
  const isDev = Boolean(import.meta.env && import.meta.env.DEV);
  console.info('[env]', { API_BASE_URL, WS_URL, isDev });
} catch (_) { /* noop */ }
