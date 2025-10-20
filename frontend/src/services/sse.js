/**
 * Minimal SSE utility for ultra-live crypto updates
 * Sends tiny heartbeats, frontend refetches JSON on each update
 */

/**
 * Open SSE connection to Worker
 * @param {Object} options
 * @param {Function} options.onState - Called with {type, updatedAt, counts}
 * @param {Function} options.onError - Called on connection errors
 * @returns {Function} Cleanup function to close connection
 */
export function openSSE({ onState, onError } = {}) {
  // Pick origin: VITE_SSE_ORIGIN in prod, empty in dev (Vite proxy)
  const base =
    import.meta.env.VITE_SSE_ORIGIN?.replace(/\/$/, '') ||
    ''; // dev: '' = same-origin via Vite proxy
  const url = `${base}/api/events`;

  console.log('[SSE] Opening connection to:', url);
  const es = new EventSource(url, { withCredentials: false });

  es.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      // { type: "hello" | "state", updatedAt, counts?, v: 1 }
      if (msg && (msg.type === 'hello' || msg.type === 'state')) {
        onState?.(msg);
      }
    } catch (e) {
      console.error('[SSE] Failed to parse message:', e);
    }
  };

  es.onerror = (err) => {
    console.error('[SSE] Connection error:', err);
    onError?.(err);
    // Let browser auto-retry (built-in EventSource behavior)
  };

  es.onopen = () => {
    console.log('[SSE] Connection established');
  };

  // Return cleanup function
  return () => {
    console.log('[SSE] Closing connection');
    es.close();
  };
}
