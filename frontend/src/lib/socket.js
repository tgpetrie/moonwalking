import { io } from 'socket.io-client';

/**
 * socket.js: Single shared socket instance connecting to VITE_WS_URL
 * - Reads import.meta.env.VITE_WS_URL (default ws://127.0.0.1:5100)
 * - Exposes getSocketInstance(), isSocketConnected(), on(event, cb), off(event, cb)
 * - Relays all socket events via listeners Map
 */

let socket = null;
let connected = false;
const listeners = new Map();

const emitLocal = (event, payload) => {
  const fns = listeners.get(event);
  if (!fns) return;
  for (const fn of fns) {
    try {
      fn(payload);
    } catch (err) {
      console.error('[socket.js] listener error', err);
    }
  }
};

export function getSocketInstance() {
  if (socket) return socket;

  const base = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:5100';
  console.log('[socket.js] Connecting to:', base);

  socket = io(base, {
    transports: ['websocket'],
    withCredentials: false,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    timeout: 8000,
  });

  socket.on('connect', () => {
    connected = true;
    console.info('[socket.js] connected', socket.id);
    emitLocal('connect', socket);
  });

  socket.on('disconnect', (reason) => {
    connected = false;
    console.warn('[socket.js] disconnected:', reason);
    emitLocal('disconnect', reason);
  });

  socket.on('connect_error', (err) => {
    connected = false;
    console.warn('[socket.js] connect_error:', err?.message || err);
    emitLocal('connect_error', err);
  });

  socket.onAny((event, payload) => {
    if (event === 'connect' || event === 'disconnect' || event === 'connect_error') return;
    console.log('[socket.js] Event received:', event, payload);
    emitLocal(event, payload);
  });

  return socket;
}

export function isSocketConnected() {
  return connected;
}

export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
  const s = getSocketInstance();
  if (event === 'connect' && s.connected) {
    queueMicrotask(() => fn(s));
  }
  return () => off(event, fn);
}

export function off(event, fn) {
  const fns = listeners.get(event);
  if (!fns) return;
  fns.delete(fn);
  if (fns.size === 0) listeners.delete(event);
}

// Backward compatibility exports
export function getSocket() {
  return getSocketInstance();
}

export function ensureSubscribed(event, handler) {
  const s = getSocketInstance();
  try {
    s.emit('subscribe', event);
  } catch (err) {
    console.warn('[socket.js] subscribe emit failed', err);
  }
  if (typeof handler === 'function') {
    return on(event, handler);
  }
  return () => {};
}


