import React from 'react';
import { endpoints, httpGet as fetchJSON } from '../lib/api';
// @ts-ignore - Vite injects import.meta.env at build/runtime
const pollMs = Number((import.meta as any).env?.VITE_POLL_MS || 10000);

/**
 * Live data hook with progressive transports:
 * 1) Socket.IO (websocket-only) to `${API_BASE}` (path '/socket.io'), event 'gainers-losers'
 * 2) Native WebSocket to `${wsBase}/ws/gainers-losers` expecting JSON array or {data:[]}
 * 3) HTTP polling to endpoints.gainers
 *
 * No extra config needed; falls back automatically.
 */
export default function useGainersLosersData() {
  const [data, setData] = React.useState<any[]>([]);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<any>(null);
  const wsRef = React.useRef<any>(null);
  const stopRef = React.useRef(false);

  React.useEffect(() => {
    stopRef.current = false;

    const setRows = (rows: any) => {
      const out = Array.isArray(rows) ? rows : (rows?.data ?? []);
      setData(out);
  setIsLoading(false);
    };

    const startPolling = () => {
      let alive = true;
      const tick = async () => {
        try {
          const j = await fetchJSON(endpoints.gainers);
          if (!alive || stopRef.current) return;
          setRows(j);
        } catch (e) {
          if (!alive || stopRef.current) return;
          setError(e);
          setIsLoading(false);
        }
      };
      tick();
      const id = setInterval(tick, pollMs);
      return () => {
        alive = false;
        clearInterval(id);
      };
    };

    const tryNativeWS = (): (() => void) | null => {
      try {
        const httpBase = new URL(endpoints.gainers, window.location.origin);
        const wsOrigin = httpBase.origin.replace(/^http/i, 'ws');
        const url = `${wsOrigin}/ws/gainers-losers`;
        const sock = new WebSocket(url);
        wsRef.current = sock;

        let hb: any = null;
        const heartbeat = () => {
          try { sock.readyState === 1 && sock.send('ping'); } catch {}
        };

        sock.onopen = () => {
          setIsLoading(true);
          hb = setInterval(heartbeat, 20000);
        };
        sock.onmessage = (ev) => {
          if (stopRef.current) return;
          try {
            const parsed = JSON.parse(ev.data);
            if (parsed) setRows(parsed);
          } catch {
            // ignore
          }
        };
        sock.onerror = (ev) => {
          if (stopRef.current) return;
          setError(new Error('WebSocket error'));
        };
        sock.onclose = () => {
          if (hb) clearInterval(hb);
        };

        return () => {
          try { sock.close(1000, 'component unmount'); } catch {}
          if (hb) clearInterval(hb);
        };
      } catch {
        return null;
      }
    };

    const trySocketIO = async (): Promise<(() => void) | null> => {
      try {
        // dynamic import so we don't require socket.io-client if unused
        // Use any to avoid TS type dependency for socket.io-client
        const mod: any = await import(/* @vite-ignore */ 'socket.io-client').catch(() => null as any);
        if (!mod || !mod.io) return null;

        const { io } = mod as any;
        const httpBase = new URL(endpoints.gainers, window.location.origin);
        const socket = io(httpBase.origin, {
          path: '/socket.io',
          transports: ['websocket'],
          reconnectionAttempts: 5,
          timeout: 5000,
        });
        wsRef.current = socket;

  socket.on('connect', () => setIsLoading(true));
        // server should emit 'gainers-losers' with rows payload
        socket.on('gainers-losers', (rows: any) => {
          if (stopRef.current) return;
          setRows(rows);
        });
        // optional subscribe pattern if your server expects it
        try { socket.emit?.('subscribe', { stream: 'gainers-losers' }); } catch {}

        socket.on('connect_error', (err: any) => {
          if (stopRef.current) return;
          setError(err || new Error('socket.io connect_error'));
        });
        socket.on('error', (err: any) => {
          if (stopRef.current) return;
          setError(err || new Error('socket.io error'));
        });

        return () => {
          try { socket.off('gainers-losers'); } catch {}
          try { socket.close(); } catch {}
        };
      } catch {
        return null;
      }
    };

    let cleanup: (() => void) | null = null;
    let cancelPolling: (() => void) | null = null;

    (async () => {
      // 1) Try Socket.IO first
      cleanup = await trySocketIO();
      if (cleanup) return;

      // 2) Then native WS
      cleanup = tryNativeWS();
      if (cleanup) return;

      // 3) Fallback: HTTP polling
      cancelPolling = startPolling();
    })();

    return () => {
      stopRef.current = true;
      if (cleanup) cleanup();
      if (cancelPolling) cancelPolling();
    };
  }, []);

  return { data, isLoading, error };
}
