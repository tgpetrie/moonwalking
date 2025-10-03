// Minimal SSE client with auto-retry and backoff
/**
 * Type definitions are informal to keep compatibility with plain JS setup
 */
export function startSSE(onUpdate) {
  let es = null;
  let retryMs = 1000; // backoff cap ~30s
  const maxMs = 30000;

  const connect = () => {
    // NOTE: use a relative URL so it works on localhost and Pages
    es = new EventSource('/api/events', { withCredentials: false });

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        onUpdate && onUpdate(data);
      } catch (e) {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      try { es.close(); } catch (e) {}
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
    if (es) {
      try { es.close(); } catch (e) {}
      es = null;
    }
  };
}
