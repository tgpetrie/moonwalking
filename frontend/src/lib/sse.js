// Minimal SSE client (lint-friendly)
// Payload: { type: 'hello'|'tick'|'update', updatedAt?: number, changed?: boolean }
export function startSSE(onUpdate, url = '/api/events') {
  let es = null;
  let retryMs = 1000;
  const MAX_MS = 30000;

  const safeJSON = (s) => {
    try { return JSON.parse(s); } catch { return null; }
  };

  const connect = () => {
    es = new EventSource(url);

    es.addEventListener('message', (ev) => {
      const data = safeJSON(ev.data);
      if (data) onUpdate(data);
    });

    es.addEventListener('error', () => {
      if (es) {
        try { es.close(); } catch {}
        es = null;
      }
      setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, MAX_MS);
    });

    es.addEventListener('open', () => {
      retryMs = 1000;
    });
  };

  connect();

  return () => {
    if (es) {
      try { es.close(); } catch {}
      es = null;
    }
  };
}
