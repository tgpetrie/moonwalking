import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { io } from 'socket.io-client';
import { getApiBaseUrl, bus, shareTables, shareAlerts } from '../lib/api';

export const WebSocketContext = createContext({
  tables: {},
  alerts: { items: [] }
});

export const WebSocketProvider = ({ children }) => {
  const [tables, setTables] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('tables:last') || '{}');
    } catch {
      return {};
    }
  });
  const [alerts, setAlerts] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('alerts:last') || '{"items": []}');
    } catch {
      return { items: [] };
    }
  });

  useEffect(() => {
    const socket = io(getApiBaseUrl(), {
      path: '/socket.io',
      transports: ['websocket']
    });

    socket.on('connect', () => console.info('[ws] connected'));
    socket.on('disconnect', () => console.warn('[ws] disconnected'));

    socket.on('tables:update', (payload) => {
      console.info('[ws] tables:update t3m=', Array.isArray(payload?.t3m) ? payload.t3m.length : 'missing');
      setTables(payload ?? {});
      try {
        sessionStorage.setItem('tables:last', JSON.stringify(payload ?? {}));
      } catch {}
      shareTables(payload ?? {});
      bus.emit('tables:update', payload ?? {});
    });

    socket.on('alerts:update', (payload) => {
      setAlerts(payload ?? { items: [] });
      try {
        sessionStorage.setItem('alerts:last', JSON.stringify(payload ?? { items: [] }));
      } catch {}
      shareAlerts(payload ?? { items: [] });
      bus.emit('alerts:update', payload ?? { items: [] });
    });

    return () => {
      try {
        socket.close();
      } catch {}
    };
  }, []);

  // listen for bus messages (posted via local CustomEvent or BroadcastChannel)
  useEffect(() => {
    if (!bus || typeof bus.on !== 'function') return () => {}
    const unsub = bus.on((msg) => {
      if (!msg) return
      try {
        if (msg.type === 'tables:update') setTables(msg.payload ?? {})
        if (msg.type === 'alerts:update') setAlerts(msg.payload?.items ?? [])
      } catch (e) {}
    })
    return typeof unsub === 'function' ? unsub : () => {}
  }, [])

  const value = useMemo(() => ({ tables, alerts, setTables, setAlerts }), [tables, alerts]);
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
};

export const useWebSocketData = () => useContext(WebSocketContext);